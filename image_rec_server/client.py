import requests
import os
import sys

# Configuration
SERVER_URL = "http://localhost:8000"

def main():
    # check if server is up
    try:
        requests.get(f"{SERVER_URL}/ping", timeout=2)
    except requests.exceptions.ConnectionError:
        print(f"Could not connect to server at {SERVER_URL}. Is it running?")
        sys.exit(1)

    print("Capturing a snapshot from the live stream...")
    
    # Get snapshot from server
    try:
        response = requests.get(f"{SERVER_URL}/snapshot", timeout=10)
        if response.status_code != 200:
            print(f"Failed to get snapshot: {response.status_code} - {response.text}")
            sys.exit(1)
        
        # Save the frame
        captured_path = "captured_frame.jpg"
        with open(captured_path, "wb") as f:
            f.write(response.content)
        
        print(f"Saved captured frame to {captured_path}")
        
    except Exception as e:
        print(f"Error capturing snapshot: {e}")
        sys.exit(1)
    
    # Now send it to /image endpoint
    print(f"Sending captured frame to {SERVER_URL}/image...")
    
    try:
        with open(captured_path, "rb") as f:
            files_dict = {"file": ("captured_frame.jpg", f, "image/jpeg")}
            response = requests.post(f"{SERVER_URL}/image", files=files_dict)
        
        if response.status_code == 200:
            print("\n--- Server Response ---")
            print(response.json())
            print("-----------------------")
        else:
            print(f"Error {response.status_code}: {response.text}")
    
    except Exception as e:
        print(f"An error occurred: {e}")
    
    # Keep the file for inspection

if __name__ == "__main__":
    main()
