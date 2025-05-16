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
PORT = 5000
new_sensor_port = PORT
CENTRAL_SERVER_HOST = 'localhost'
CENTRAL_SERVER_PORT = 6000

drone_socket = None
stop_server = False  # unused
restart_server = False

# Shared state
message_queue = Queue()
buffers = defaultdict(lambda: deque(maxlen=5))
outgoing_data = []
battery_level = 100
return_to_base = False
lock = threading.Lock()
reported_anomalies = set()

# GUI setup
root = tk.Tk()
root.title("Drone Server")

top_frame = tk.Frame(root)
top_frame.grid(row=0, column=0, padx=10, pady=5)

# battery gui start
battery_frame = tk.Frame(top_frame)
battery_frame.grid(row=0, column=0, padx=10, pady=5)

battery_label = tk.Label(battery_frame, text=f"Battery Level: {battery_level}%", font=("Arial", 12, "bold"))
battery_label.grid(row=0, column=0, padx=10, pady=5)

battery_slider = tk.Scale(battery_frame, from_=0, to=100, orient="horizontal", label="Adjust Battery Level",
                          command=lambda val: set_battery_level(int(val)))
battery_slider.set(100)
battery_slider.grid(row=1, column=0, padx=10, pady=5)
# battery gui end

# port config start
frm_ports = tk.Frame(top_frame)
frm_ports.grid(row=0, column=1, padx=10)

tk.Label(frm_ports, text="Sensor Port").pack()
ent_sensor_port = tk.Entry(frm_ports)
ent_sensor_port.insert(0, "5000")  # Default
ent_sensor_port.pack()

tk.Label(frm_ports, text="Central Server Port").pack()
ent_central_port = tk.Entry(frm_ports)
ent_central_port.insert(0, "6000")  # Default
ent_central_port.pack()

def change_ports():
    global PORT, CENTRAL_SERVER_PORT, restart_server, drone_socket, new_sensor_port
    try:
        new_sensor_port = int(ent_sensor_port.get())
        new_central_port = int(ent_central_port.get())
        if not (0 < new_sensor_port < 65536) or not (0 < new_central_port < 65536):
            raise ValueError
    except ValueError:
        message_queue.put(f"[{datetime.now()}] Invalid port number. Must be between 1 and 65535.")
        return
    
    if new_sensor_port == PORT and new_central_port == CENTRAL_SERVER_PORT:
        message_queue.put(f"[{datetime.now()}] Ports are already set to {PORT} and {CENTRAL_SERVER_PORT}.")
        return

    CENTRAL_SERVER_PORT = new_central_port

    if new_sensor_port !=  PORT:
        if drone_socket:
            try:
                drone_socket.close()
            except:
                pass
        restart_server = True
    
    message = f"[{datetime.now()}] Current Ports, Sensor Port: {new_sensor_port}, Central Server Port: {CENTRAL_SERVER_PORT}"
    message_queue.put(message)

btn_check = tk.Button(frm_ports, text="Change Ports", command=change_ports)
btn_check.pack(pady=5)

# port config end

frm_log = tk.Frame(master=root, relief=tk.RIDGE, borderwidth=3)
listbox = tk.Listbox(master=frm_log, width=120, height=35)
scrollbar = tk.Scrollbar(master=frm_log, orient="vertical")
listbox.pack(side=tk.LEFT, fill=tk.BOTH)
scrollbar.pack(side=tk.RIGHT, fill=tk.BOTH)
listbox.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=listbox.yview)
frm_log.grid(row=2, column=0, padx=10, pady=10)

# ------------ Sensor TCP Server ------------

def handle_sensor(conn, addr):
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
                message = f"[{datetime.now()}] Received from {sensor_id}: {msg}"
                message_queue.put(message)
            except json.JSONDecodeError:
                message_queue.put(f"[{datetime.now()}] Invalid JSON from {addr}")
    finally:
        conn.close()
        message_queue.put(f"[{datetime.now()}] Connection closed for {addr}")

def start_sensor_server():
    global PORT, drone_socket, stop_server, restart_server

    while not stop_server:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                drone_socket = server
                server.settimeout(1.0)  # Makes all operations interruptible
                server.bind((HOST, PORT))
                server.listen()
                message_queue.put(f"[{datetime.now()}] Drone started listening on {HOST}:{PORT}...")

                while not (stop_server or restart_server):
                    try:
                        conn, addr = server.accept()
                        threading.Thread(target=handle_sensor, args=(conn, addr), daemon=True).start()
                    except socket.timeout:
                        continue
                    except OSError:
                        message_queue.put(f"[{datetime.now()}] Closing current server...")
                        break
                    except Exception as e:
                        message_queue.put(f"[{datetime.now()}] Error: {str(e)}")
                        time.sleep(2)
                
                if restart_server:
                    message_queue.put(f"[{datetime.now()}] Restarting server on {HOST}:{PORT}...")
                    restart_server = False
                    PORT = new_sensor_port
                    continue
        except Exception as e:
            message_queue.put(f"[{datetime.now()}] Error starting server: {str(e)}")
            time.sleep(2)
        
            

# ------------ Edge Processing + Anomaly Detection ------------

def edge_processing():
    global reported_anomalies
    while True:
        time.sleep(10)
        packet = {
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
                packet["averages"][sensor_id] = {
                    "avg_temperature": round(avg_temp, 2),
                    "avg_humidity": round(avg_hum, 2)
                }
                for r in readings:
                    anomaly_key = f"{sensor_id}_{r['timestamp']}"
                    if r["temperature"] > 50 and anomaly_key not in reported_anomalies:
                        packet["anomalies"].append({
                            "sensor_id": sensor_id,
                            "type": "temperature_high",
                            "value": r["temperature"],
                            "timestamp": r["timestamp"]
                        })
                        reported_anomalies.add(anomaly_key)
                    if r["humidity"] < 10 and anomaly_key not in reported_anomalies:
                        packet["anomalies"].append({
                            "sensor_id": sensor_id,
                            "type": "humidity_low",
                            "value": r["humidity"],
                            "timestamp": r["timestamp"]
                        })
                        reported_anomalies.add(anomaly_key)

            if return_to_base:
                outgoing_data.append(packet)
                message_queue.put(f"[{datetime.now()}] Queued data (return-to-base active)")
            else:
                send_to_central(packet)

# ------------ Central Server Forwarding ------------

def send_to_central(packet):
    global CENTRAL_SERVER_PORT
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((CENTRAL_SERVER_HOST, CENTRAL_SERVER_PORT))
            s.sendall(json.dumps(packet).encode())
            for sensor in packet["averages"]:
                message_queue.put(f"[{datetime.now()}] {sensor} averages: Temp={packet['averages'][sensor]['avg_temperature']}°C | "
                                  f"Hum={packet['averages'][sensor]['avg_humidity']}%")
            for anomaly in packet["anomalies"]:
                message_queue.put(f"[{datetime.now()}] Anomaly detected: {anomaly['sensor_id']} | {anomaly['type']} | "
                                  f"Value={anomaly['value']} | Timestamp={anomaly['timestamp']}")
            message_queue.put(f"[{datetime.now()}] Forwarded data to Central Server.")
    except Exception as e:
        message_queue.put(f"[{datetime.now()}] Error sending to Central Server: {str(e)}")

def forward_queued_data():
    global outgoing_data
    while True:
        time.sleep(5)
        with lock:
            if not return_to_base and outgoing_data:
                message_queue.put(f"[{datetime.now()}] Sending queued data...")
                for packet in outgoing_data:
                    send_to_central(packet)
                outgoing_data.clear()

# ------------ Battery Simulation ------------

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

# ------------ GUI Updater ------------

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

# ------------ Thread Starters ------------

threading.Thread(target=start_sensor_server, daemon=True).start()
threading.Thread(target=edge_processing, daemon=True).start()
threading.Thread(target=forward_queued_data, daemon=True).start()
threading.Thread(target=battery_drain, daemon=True).start()
root.after(100, update_gui)
root.mainloop()
