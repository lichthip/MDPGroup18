import requests
import os
import sys

# Configuration
SERVER_URL = "http://127.0.0.1:8000"

def main():
    # check if server is up
    try:
        requests.get(f"{SERVER_URL}/ping", timeout=2)
    except requests.exceptions.ConnectionError:
        print(f"Could not connect to server at {SERVER_URL}. Is it running?")
        sys.exit(1)

    print("Using test image from test_images/image.jpg...")
    
    # Use local test image
    test_image_path = "test_images/image.jpg"
    if not os.path.exists(test_image_path):
        print(f"Test image not found at {test_image_path}")
        sys.exit(1)
    
    # Now send it to /image endpoint
    print(f"Sending test image to {SERVER_URL}/image...")
    
    try:
        with open(test_image_path, "rb") as f:
            files_dict = {"file": ("image.jpg", f, "image/jpeg")}
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
