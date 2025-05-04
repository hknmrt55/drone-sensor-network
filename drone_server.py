import socket
import threading
import json
import tkinter as tk
from datetime import datetime
from queue import Queue

# Create the main window
root = tk.Tk()
root.title("Drone Server")

# Configuration
HOST = 'localhost'
PORT = 5050

# Message Queue
message_queue = Queue()

def handle_sensor(conn, addr):
    print(f"[{datetime.now()}] Connected by {addr}")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            try:
                msg = json.loads(data.decode())
                message = f"[{datetime.now()}] Received from {addr}: {msg}"
                print(message)
                message_queue.put(message)
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

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((HOST, PORT))
        server.listen()
        startup_msg = f"[{datetime.now()}] Drone server listening on {HOST}:{PORT}..."
        print(startup_msg)
        message_queue.put(startup_msg)
        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_sensor, args=(conn, addr), daemon=True)
            thread.start()

def update_gui():
    while not message_queue.empty():
        message = message_queue.get()
        listbox_history.insert(tk.END, message)
        listbox_history.yview(tk.END) # Auto-scrolls to the bottom
    
    # Schedule this function to run again after 100ms
    root.after(100, update_gui)

# tkinter GUI setup

# history frame start
frm_history = tk.Frame(master=root, relief=tk.RIDGE, borderwidth=3)

listbox_history = tk.Listbox(master=frm_history, width=150, height=50)
listbox_history.pack(side=tk.LEFT, fill=tk.BOTH)

scrollbar = tk.Scrollbar(master=frm_history, orient="vertical")
scrollbar.pack(side=tk.RIGHT, fill=tk.BOTH)

listbox_history.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=listbox_history.yview)

frm_history.grid(row=0, column=1)
# history frame end

# Start the server in a separate thread
server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

# Start the GUI update loop
root.after(100, update_gui)

root.mainloop()

#if __name__ == "__main__":
#    start_server()


