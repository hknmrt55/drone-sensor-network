import socket
import threading
import json
import tkinter as tk
from datetime import datetime
from queue import Queue

# Configuration
HOST = 'localhost'
PORT = 6000

# GUI and threading setup
root = tk.Tk()
root.title("Central Server")
message_queue = Queue()

# --------- TCP SERVER ---------

def handle_drone(conn, addr):
    print(f"[{datetime.now()}] Connection from Drone at {addr}")
    message_queue.put(f"[{datetime.now()}] Connected to Drone: {addr}")

    try:
        while True:
            data = conn.recv(2048)
            if not data:
                break
            try:
                payload = json.loads(data.decode())
                formatted = f"[{datetime.now()}] Received: {json.dumps(payload)}"
                print(formatted)
                message_queue.put(formatted)
            except json.JSONDecodeError:
                error_msg = f"[{datetime.now()}] Invalid JSON from Drone"
                print(error_msg)
                message_queue.put(error_msg)
    except ConnectionResetError:
        disconnect_msg = f"[{datetime.now()}] Drone disconnected unexpectedly."
        print(disconnect_msg)
        message_queue.put(disconnect_msg)
    finally:
        conn.close()
        close_msg = f"[{datetime.now()}] Connection closed for {addr}"
        print(close_msg)
        message_queue.put(close_msg)

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((HOST, PORT))
        server.listen(1)
        startup = f"[{datetime.now()}] Central Server listening on {HOST}:{PORT}..."
        print(startup)
        message_queue.put(startup)

        while True:
            conn, addr = server.accept()
            threading.Thread(target=handle_drone, args=(conn, addr), daemon=True).start()

# --------- GUI ---------

def update_gui():
    while not message_queue.empty():
        msg = message_queue.get()
        listbox_logs.insert(tk.END, msg)
        listbox_logs.yview(tk.END)
    root.after(100, update_gui)

frm_logs = tk.Frame(master=root, relief=tk.RIDGE, borderwidth=3)
listbox_logs = tk.Listbox(master=frm_logs, width=120, height=40)
scrollbar = tk.Scrollbar(master=frm_logs, orient="vertical")
listbox_logs.pack(side=tk.LEFT, fill=tk.BOTH)
scrollbar.pack(side=tk.RIGHT, fill=tk.BOTH)
listbox_logs.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=listbox_logs.yview)
frm_logs.grid(row=0, column=0, padx=10, pady=10)

# --------- Startup ---------

threading.Thread(target=start_server, daemon=True).start()
root.after(100, update_gui)
root.mainloop()
