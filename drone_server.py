import socket
import threading
import json
import tkinter as tk
from datetime import datetime
from queue import Queue
from collections import defaultdict, deque
import time

# Configuration
HOST = 'localhost'
PORT = 5050
CENTRAL_SERVER_HOST = 'localhost'
CENTRAL_SERVER_PORT = 6000

# Shared States
message_queue = Queue()
buffers = defaultdict(lambda: deque(maxlen=5))
outgoing_data = []
battery_level = 100
return_to_base = False
lock = threading.Lock()

# GUI setup
root = tk.Tk()
root.title("Drone Server")

battery_label = tk.Label(root, text=f"Battery Level: {battery_level}%", font=("Arial", 12, "bold"))
battery_label.grid(row=0, column=0, padx=10, pady=5)
battery_slider = tk.Scale(root, from_=0, to=100, orient="horizontal", label="Adjust Battery Level",
                          command=lambda val: set_battery_level(int(val)))
battery_slider.set(100)
battery_slider.grid(row=1, column=0, padx=10, pady=5)

frm_log = tk.Frame(master=root, relief=tk.RIDGE, borderwidth=3)
listbox = tk.Listbox(master=frm_log, width=120, height=35)
scrollbar = tk.Scrollbar(master=frm_log, orient="vertical")
listbox.pack(side=tk.LEFT, fill=tk.BOTH)
scrollbar.pack(side=tk.RIGHT, fill=tk.BOTH)
listbox.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=listbox.yview)
frm_log.grid(row=2, column=0, padx=10, pady=10)

# -------- TCP Server for Sensors --------

def handle_sensor(conn, addr):
    print(f"[{datetime.now()}] Connected by {addr}")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            try:
                msg = json.loads(data.decode())
                sensor_id = msg.get("sensor_id", "unknown")
                with lock:
                    buffers[sensor_id].append(msg)
                log_msg = f"[{datetime.now()}] Received from {addr}: {msg}"
                print(log_msg)
                message_queue.put(log_msg)
            except json.JSONDecodeError:
                error_msg = f"[{datetime.now()}] Invalid JSON from {addr}"
                print(error_msg)
                message_queue.put(error_msg)
    except ConnectionResetError:
        error_msg = f"[{datetime.now()}] Sensor {addr} disconnected unexpectedly."
        print(error_msg)
        message_queue.put(error_msg)
    finally:
        conn.close()
        close_msg = f"[{datetime.now()}] Connection closed for {addr}"
        print(close_msg)
        message_queue.put(close_msg)

def start_sensor_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((HOST, PORT))
        server.listen()
        startup = f"[{datetime.now()}] Drone listening on {HOST}:{PORT}..."
        print(startup)
        message_queue.put(startup)
        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_sensor, args=(conn, addr), daemon=True)
            thread.start()

# -------- Edge Processing + Forwarding --------

def edge_processing_loop():
    while True:
        time.sleep(10)
        data_packet = {
            "drone_id": "drone1",
            "timestamp": datetime.utcnow().isoformat(),
            "averages": {},
            "anomalies": []
        }

        with lock:
            for sensor_id, readings in buffers.items():
                if not readings:
                    continue
                avg_temp = sum(r["temperature"] for r in readings) / len(readings)
                avg_hum = sum(r["humidity"] for r in readings) / len(readings)

                data_packet["averages"][sensor_id] = {
                    "avg_temperature": round(avg_temp, 2),
                    "avg_humidity": round(avg_hum, 2)
                }

                summary = f"[{datetime.now()}] {sensor_id} | Avg Temp: {avg_temp:.2f}°C | Avg Hum: {avg_hum:.2f}%"
                print(summary)
                message_queue.put(summary)

                for r in readings:
                    if r["temperature"] > 50:
                        anomaly = f"[{datetime.now()}] Anomaly (Temp > 50) from {sensor_id}: {r['temperature']:.2f}"
                        print(anomaly)
                        message_queue.put(anomaly)
                        data_packet["anomalies"].append({
                            "sensor_id": sensor_id,
                            "type": "temperature_high",
                            "value": r["temperature"],
                            "timestamp": r["timestamp"]
                        })
                    if r["humidity"] < 10:
                        anomaly = f"[{datetime.now()}] Anomaly (Hum < 10) from {sensor_id}: {r['humidity']:.2f}"
                        print(anomaly)
                        message_queue.put(anomaly)
                        data_packet["anomalies"].append({
                            "sensor_id": sensor_id,
                            "type": "humidity_low",
                            "value": r["humidity"],
                            "timestamp": r["timestamp"]
                        })

        # Store for sending
        outgoing_data.append(data_packet)

# -------- Forward to Central Server --------

def forward_loop():
    while True:
        if not outgoing_data:
            time.sleep(2)
            continue

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((CENTRAL_SERVER_HOST, CENTRAL_SERVER_PORT))
                message_queue.put(f"[{datetime.now()}] Connected to Central Server at {CENTRAL_SERVER_HOST}:{CENTRAL_SERVER_PORT}")

                while outgoing_data:
                    packet = outgoing_data.pop(0)
                    s.sendall(json.dumps(packet).encode())
                    message_queue.put(f"[{datetime.now()}] Forwarded data to Central Server.")
                    time.sleep(10)

        except ConnectionRefusedError:
            message_queue.put(f"[{datetime.now()}] Central Server unavailable. Retrying in 5s...")
            time.sleep(5)
        except Exception as e:
            message_queue.put(f"[{datetime.now()}] Error forwarding to Central Server: {str(e)}")
            time.sleep(5)

# -------- Battery Simulation --------

def battery_drain():
    global battery_level, return_to_base
    while True:
        time.sleep(5)
        with lock:
            if battery_level > 0:
                battery_level -= 1
                message_queue.put(("update_battery", battery_level))

            if battery_level <= 20 and not return_to_base:
                return_to_base = True
                message_queue.put(f"[{datetime.now()}] Battery low. Entering return-to-base mode.")

            elif battery_level > 20 and return_to_base:
                return_to_base = False
                message_queue.put(f"[{datetime.now()}] Battery restored. Resuming normal operation.")

def set_battery_level(val):
    global battery_level, return_to_base
    with lock:
        battery_level = val
        battery_label.config(text=f"Battery Level: {battery_level}%")
        if battery_level <= 20:
            return_to_base = True
            message_queue.put(f"[{datetime.now()}] Manual battery low. Return-to-base mode ON.")
        else:
            if return_to_base:
                return_to_base = False
                message_queue.put(f"[{datetime.now()}] Manual battery restore. Normal mode ON.")

# -------- GUI Update --------

def update_gui():
    while not message_queue.empty():
        msg = message_queue.get()
        if isinstance(msg, tuple) and msg[0] == "update_battery":
            battery_slider.set(msg[1])
            battery_label.config(text=f"Battery Level: {msg[1]}%")
        else:
            listbox.insert(tk.END, msg)
            listbox.yview(tk.END)
    root.after(100, update_gui)

# -------- Start Threads --------

threading.Thread(target=start_sensor_server, daemon=True).start()
threading.Thread(target=edge_processing_loop, daemon=True).start()
threading.Thread(target=forward_loop, daemon=True).start()
threading.Thread(target=battery_drain, daemon=True).start()

root.after(100, update_gui)
root.mainloop()
