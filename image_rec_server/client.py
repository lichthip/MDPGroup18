import requests
import os
import sys

# Configuration
SERVER_URL = "http://localhost:8000"
IMAGE_FOLDER = "test_images"

def main():
    # check if server is up
    try:
        requests.get(f"{SERVER_URL}/ping", timeout=2)
    except requests.exceptions.ConnectionError:
        print(f"Could not connect to server at {SERVER_URL}. Is it running?")
        sys.exit(1)

    # Get image
    if not os.path.exists(IMAGE_FOLDER):
        print(f"Folder {IMAGE_FOLDER} does not exist.")
        sys.exit(1)

    files = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not files:
        print(f"No images found in {IMAGE_FOLDER}")
        sys.exit(1)

    # Use the first image
    for i in range(len(files)):
        filename = files[i]
        image_path = os.path.join(IMAGE_FOLDER, filename)
        print(f"Sending {image_path} to {SERVER_URL}/image...")

        url = f"{SERVER_URL}/image"
        try:
            with open(image_path, "rb") as f:
                # multipart/form-data
                files_dict = {"file": (filename, f, "image/jpeg")}
                response = requests.post(url, files=files_dict)
        
            if response.status_code == 200:
                print("\n--- Server Response ---")
                print(response.json())
                print("-----------------------")
            else:
                print(f"Error {response.status_code}: {response.text}")

        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
