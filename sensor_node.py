import socket
import threading
import time
import json
import random
import tkinter as tk
from tkinter import DISABLED
from datetime import datetime

# Create the main window
root = tk.Tk()
root.title("Sensor Node")

# Configuration
#DRONE_HOST = 'localhost'
#DRONE_PORT = 5050
SENSOR_ID = 'sensor1'
INTERVAL = 3  # seconds between sends
running = False  # Flag to control the sensor thread

def generate_payload():
    return {
        "sensor_id": SENSOR_ID,
        "temperature": round(random.uniform(18.0, 35.0), 2),
        "humidity": round(random.uniform(30.0, 80.0), 2),
        "timestamp": datetime.utcnow().isoformat()
    }

def sensor_thread():
    global running
    DRONE_HOST = ent_server.get()
    DRONE_PORT = int(ent_port.get())
    display_message(f"[{datetime.now()}] {SENSOR_ID} started. Trying to connect to Drone at {DRONE_HOST}:{DRONE_PORT}...")

    while running:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)  # Makes all operations interruptible
                s.connect((DRONE_HOST, DRONE_PORT))
                display_message(f"[{datetime.now()}] Connected to Drone at {DRONE_HOST}:{DRONE_PORT}")
                while running:
                    payload = generate_payload()
                    s.sendall(json.dumps(payload).encode())
                    display_message(f"[{datetime.now()}] Sent: {payload}")
                    time.sleep(INTERVAL)
        except ConnectionRefusedError:
            display_message(f"[{datetime.now()}] Drone not available. Retrying in 3 seconds...")
            time.sleep(3)
        except BrokenPipeError:
            display_message(f"[{datetime.now()}] Connection lost. Reconnecting...")
            time.sleep(3)

def start_sensor():
    global running
    if not running:
        running = True
        btn_connect.config(text="Disconnect")
        # Start sensor in a separate thread
        thread = threading.Thread(target=sensor_thread, daemon=True)
        thread.start()
    else:
        running = False
        btn_connect.config(text="Connect")

def display_message(message):
    print(message)
    message_box.config(state=tk.NORMAL)
    message_box.insert(tk.END, message + "\n")
    message_box.config(state=DISABLED)
    message_box.see(tk.END)

# -----GUI Elements-----

# server configuration part start
frm_input = tk.Frame(master=root, relief=tk.RIDGE, borderwidth=3)

lbl_server = tk.Label(master=frm_input, text="Server Address")
ent_server = tk.Entry(master=frm_input, width=30)

lbl_port = tk.Label(master=frm_input, text="Port")
ent_port = tk.Entry(master=frm_input, width=10)

lbl_colon = tk.Label(master=frm_input, text=":")

lbl_server.grid(row=0, column=0)
ent_server.grid(row=1, column=0, padx=5, pady=5)

lbl_colon.grid(row=1, column=1)

lbl_port.grid(row=0, column=2)
ent_port.grid(row=1, column=2, padx=5, pady=5)

frm_input.grid(row=0, column=0, padx=10, pady=20)
# server configuration part end

# connect button part start
btn_connect = tk.Button(master=root, text="Connect", relief=tk.RAISED, borderwidth=2, command=start_sensor)
btn_connect.grid(row=3, column=0)
# connect button part end

# message display part start
message_box = tk.Text(root, width=35, height=8, state=DISABLED,)
message_box.grid(row=0, column=3, columnspan=3, padx=10, pady=10, sticky="WSEN")
# message display part end

root.mainloop()
