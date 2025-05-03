import socket
import time
import json
import random
from datetime import datetime

# Configuration
DRONE_HOST = 'localhost'
DRONE_PORT = 5050
SENSOR_ID = 'sensor1'
INTERVAL = 3  # seconds between sends

def generate_payload():
    return {
        "sensor_id": SENSOR_ID,
        "temperature": round(random.uniform(18.0, 35.0), 2),
        "humidity": round(random.uniform(30.0, 80.0), 2),
        "timestamp": datetime.utcnow().isoformat()
    }

def run_sensor():
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((DRONE_HOST, DRONE_PORT))
                print(f"[{datetime.now()}] ✅ Connected to Drone at {DRONE_HOST}:{DRONE_PORT}")
                while True:
                    payload = generate_payload()
                    s.sendall(json.dumps(payload).encode())
                    print(f"[{datetime.now()}] 📤 Sent: {payload}")
                    time.sleep(INTERVAL)
        except ConnectionRefusedError:
            print(f"[{datetime.now()}] ❌ Drone not available. Retrying in 3 seconds...")
            time.sleep(3)
        except BrokenPipeError:
            print(f"[{datetime.now()}] 🔌 Connection lost. Reconnecting...")
            time.sleep(3)

if __name__ == "__main__":
    run_sensor()
