import requests
import os
import sys
import time

# Configuration
SERVER_URL = "http://127.0.0.1:8000"
IMAGE_FOLDER = "test_images"

def main():
    # check if server is up
    try:
        requests.get(f"{SERVER_URL}/ping", timeout=2)
    except requests.exceptions.ConnectionError:
        print(f"Could not connect to server at {SERVER_URL}. Is it running?")
        sys.exit(1)

    print("Connecting to live feed... Press Ctrl+C to stop.")

    try:
        while True:
            try:
                response = requests.get(f"{SERVER_URL}/live_data", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    print(f"\n--- Live Detections at {data['timestamp']} ---")
                    if data['detections']:
                        for det in data['detections']:
                            print(f"ID: {det['image_id']}, Class: {det['class_name']}, Conf: {det['confidence']:.2f}, BBox: {det['bbox']}")
                    else:
                        print("No detections")
                    print("---------------------------------------------")
                else:
                    print(f"Error {response.status_code}: {response.text}")
            except requests.exceptions.RequestException as e:
                print(f"Request error: {e}")
            
            time.sleep(1)  # Poll every second

    except KeyboardInterrupt:
        print("\nStopped live feed.")

if __name__ == "__main__":
    main()
