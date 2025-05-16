import socket
import threading
import time
import json
import random
import argparse
from datetime import datetime

running = False  # Flag to control the sensor thread

# Used to control anomaly timing
last_anomaly_time = time.time()

def generate_payload(sensor_id):
    global last_anomaly_time
    now = time.time()
    inject_anomaly = (now - last_anomaly_time) > random.randint(15, 20)

    if inject_anomaly:
        last_anomaly_time = now
        if random.choice([True, False]):
            # Temperature anomaly
            return {
                "sensor_id": sensor_id,
                "temperature": round(random.uniform(51.0, 60.0), 2),
                "humidity": round(random.uniform(30.0, 80.0), 2),
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            # Humidity anomaly
            return {
                "sensor_id": sensor_id,
                "temperature": round(random.uniform(18.0, 35.0), 2),
                "humidity": round(random.uniform(1.0, 9.0), 2),
                "timestamp": datetime.utcnow().isoformat()
            }

    # Normal payload
    return {
        "sensor_id": sensor_id,
        "temperature": round(random.uniform(18.0, 35.0), 2),
        "humidity": round(random.uniform(30.0, 80.0), 2),
        "timestamp": datetime.utcnow().isoformat()
    }


def sensor_thread(host, port, sensor_id, interval):
    global running

    print(f"[{datetime.now()}] {sensor_id} started. Trying to connect to Drone at {host}:{port}...")

    while running:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)  # Makes all operations interruptible
                s.connect((host, port))
                print(f"[{datetime.now()}] Connected to Drone at {host}:{port}")
                while running:
                    payload = generate_payload(sensor_id)
                    s.sendall(json.dumps(payload).encode())
                    print(f"[{datetime.now()}] Sent: {payload}")
                    time.sleep(interval)
        except ConnectionRefusedError:
            print(f"[{datetime.now()}] Drone not available. Retrying in 3 seconds...")
            time.sleep(3)
        except BrokenPipeError:
            print(f"[{datetime.now()}] Connection lost. Reconnecting...")
            time.sleep(3)
        except Exception as e:
            print(f"[{datetime.now()}] Error: {str(e)}")
            time.sleep(3)

def main():
    global running

    parser = argparse.ArgumentParser(description="Sensor Node")
    parser.add_argument("host", type=str, help="Drone Server Host Address")
    parser.add_argument("port", type=int, help="Drone Server Port Number")
    parser.add_argument("sensor_id", type=str, help="Sensor ID (e.g. 'sensor1')")
    parser.add_argument("--interval", type=int, default=3, help="Interval between payloads in seconds (default: 3)")

    args = parser.parse_args()

    running = True
    try:
        print(f"[{datetime.now()}] Starting {args.sensor_id}: Connecting to {args.host}:{args.port}")
        print("Press Ctrl+C to stop the sensor node.")
        sensor_thread(args.host, args.port, args.sensor_id, args.interval)
    except KeyboardInterrupt:
        print(f"[{datetime.now()}] Stopping {args.sensor_id}...")
        running = False
    

if __name__ == "__main__":
    main()