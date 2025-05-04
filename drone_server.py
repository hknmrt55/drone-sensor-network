import socket
import threading
import json
from datetime import datetime

# Configuration
HOST = 'localhost'
PORT = 5050

def handle_sensor(conn, addr):
    print(f"[{datetime.now()}] Connected by {addr}")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            try:
                msg = json.loads(data.decode())
                print(f"[{datetime.now()}] Received from {addr}: {msg}")
            except json.JSONDecodeError:
                print(f"[{datetime.now()}] Invalid JSON from {addr}")
    except ConnectionResetError:
        print(f"[{datetime.now()}] Sensor {addr} disconnected unexpectedly.")
    finally:
        conn.close()
        print(f"[{datetime.now()}] Connection closed for {addr}")

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((HOST, PORT))
        server.listen()
        print(f"[{datetime.now()}] Drone server listening on {HOST}:{PORT}...")
        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_sensor, args=(conn, addr), daemon=True)
            thread.start()

if __name__ == "__main__":
    start_server()
