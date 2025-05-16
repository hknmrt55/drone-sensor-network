import socket
import threading
import json
import tkinter as tk
from datetime import datetime
from queue import Queue
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
from collections import defaultdict
import time

# Global variables
PORT = 6000
server_socket = None
stop_server = False #unused
restart_server = False

# GUI queues
log_queue = Queue()
avg_queue = Queue()
anomaly_queue = Queue()
plot_queue = Queue()

# For plotting
plot_data = defaultdict(lambda: {"time": [], "temp": [], "hum": []})

def handle_drone(conn, addr):
    log_queue.put(f"[{datetime.now()}] Connected to Drone: {addr}")
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            try:
                payload = json.loads(data.decode())
                log_queue.put(f"[{datetime.now()}] Received packet.")
                timestamp = datetime.utcnow()
                for sid, stats in payload.get("averages", {}).items():
                    avg_queue.put(f"{sid}: Temp={stats['avg_temperature']}°C | Hum={stats['avg_humidity']}%")
                    plot_queue.put((sid, timestamp, stats['avg_temperature'], stats['avg_humidity']))
                for a in payload.get("anomalies", []):
                    anomaly_queue.put(f"{a['sensor_id']} | {a['type']} | {a['value']}")
            except json.JSONDecodeError:
                log_queue.put(f"[{datetime.now()}] ❌ Invalid JSON received.")
    finally:
        conn.close()
        log_queue.put(f"[{datetime.now()}] Connection closed: {addr}")

def start_server():
    global server_socket, restart_server, stop_server

    while not stop_server:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                server_socket = s
                s.settimeout(1.0)  # Makes all operations interruptible
                s.bind(('localhost', PORT))
                s.listen(1)
                log_queue.put(f"[{datetime.now()}] Central Server started listening on port {PORT}...")
                while not (stop_server or restart_server):
                    try:
                        conn, addr = server_socket.accept()
                        threading.Thread(target=handle_drone, args=(conn, addr), daemon=True).start()
                    except socket.timeout:
                        continue
                    except OSError:
                        log_queue.put(f"[{datetime.now()}] Closing current server...")
                        break
                    except Exception as e:
                        log_queue.put(f"[{datetime.now()}] Error: {str(e)}")
                        time.sleep(2)
                if restart_server:
                    log_queue.put(f"[{datetime.now()}] Restarting server on port {PORT}...")
                    restart_server = False
                    continue
        except Exception as e:
            log_queue.put(f"[{datetime.now()}] Error starting server: {str(e)}")
            time.sleep(2)

def update_gui():
    while not log_queue.empty():
        msg = log_queue.get()
        list_log.insert(tk.END, msg)
        list_log.yview(tk.END)
    while not avg_queue.empty():
        msg = avg_queue.get()
        list_avg.insert(tk.END, msg)
        list_avg.yview(tk.END)
    while not anomaly_queue.empty():
        msg = anomaly_queue.get()
        list_anom.insert(tk.END, msg)
        list_anom.itemconfig(tk.END, {'fg': 'red'})
        list_anom.yview(tk.END)
    root.after(100, update_gui)

def update_plot():
    while not plot_queue.empty():
        sid, timestamp, temp, hum = plot_queue.get()
        d = plot_data[sid]
        d["time"].append(timestamp)
        d["temp"].append(temp)
        d["hum"].append(hum)
        if len(d["time"]) > 20:
            d["time"].pop(0)
            d["temp"].pop(0)
            d["hum"].pop(0)

    ax.clear()
    for sid, d in plot_data.items():
        ax.plot(d["time"], d["temp"], label=f"{sid} Temp")
        ax.plot(d["time"], d["hum"], label=f"{sid} Hum")
    ax.set_title("Sensor Averages")
    ax.set_xlabel("Time")
    ax.set_ylabel("Value")
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    fig.autofmt_xdate()
    canvas.draw()
    root.after(5000, update_plot)

# GUI setup
root = tk.Tk()
root.title("Central Server")

frame = tk.Frame(root)
frame.pack(padx=10, pady=10)

tk.Label(frame, text="Live Logs").grid(row=0, column=0)
tk.Label(frame, text="Averages").grid(row=0, column=1)
tk.Label(frame, text="Anomalies").grid(row=0, column=2)

list_log = tk.Listbox(frame, width=50, height=15)
list_avg = tk.Listbox(frame, width=50, height=15)
list_anom = tk.Listbox(frame, width=50, height=15)

list_log.grid(row=1, column=0, padx=5)
list_avg.grid(row=1, column=1, padx=5)
list_anom.grid(row=1, column=2, padx=5)

# Plot panel
fig, ax = plt.subplots(figsize=(10, 4))
plot_frame = tk.Frame(root)
plot_frame.pack()
canvas = FigureCanvasTkAgg(fig, master=plot_frame)
canvas.get_tk_widget().pack()

# port config
frm_port = tk.Frame(frame)
frm_port.grid(row=1, column=3, padx=10, pady=5)	

tk.Label(frm_port, text="Server Port:").pack(side=tk.TOP)
ent_port = tk.Entry(frm_port, width=10)
ent_port.insert(0, "6000")  # Default
ent_port.pack(side=tk.TOP, pady=5)

def change_port():
    global PORT, restart_server
    try:
        new_port = int(ent_port.get())
        if not (0 < new_port < 65536):
            raise ValueError
    except ValueError:
        log_queue.put(f"[{datetime.now()}] Invalid port number. Must be between 1 and 65535.")
        return
    
    if new_port == PORT:
        log_queue.put(f"[{datetime.now()}] Port is already set to {PORT}.")
        return
    
    if server_socket:
        try:
            server_socket.close()
        except:
            pass
    
    PORT = new_port
    restart_server = True
    log_queue.put(f"[{datetime.now()}] Changing to port {PORT}...")

btn_check = tk.Button(frm_port, text="Change Ports", command=change_port)
btn_check.pack(side = tk.TOP, pady=5)

# Start everything
threading.Thread(target=start_server, daemon=True).start()
root.after(100, update_gui)
root.after(1000, update_plot)
root.mainloop()
