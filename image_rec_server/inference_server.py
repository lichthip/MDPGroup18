import os
import cv2
import threading
import time
import numpy as np
import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from ultralytics import YOLO
import tempfile
import shutil
from typing import List, Dict
from datetime import datetime
import torch

# --- CONFIGURATION ---
RTSP_URL = os.getenv("RTSP_URL", "rtsp://192.168.18.18:8554/cam")
ENABLE_STREAM = os.getenv("ENABLE_STREAM", "auto").lower()  # "auto", "true", or "false"
stream_available = False  # Will be set during startup

# ID Map
ID_MAP = {
    0: '0_Bulls Eye',
    1: '111',
    2: '122',
    3: '133',
    4: '144',
    5: '155',
    6: '166',
    7: '177',
    8: '188',
    9: '199',
    10: '20_A',
    11: '21_B',
    12: '22_C',
    13: '23_D',
    14: '24_E',
    15: '25_F',
    16: '26_G',
    17: '27_H',
    18: '28_S',
    19: '29_T',
    20: '30_U',
    21: '31_V',
    22: '32_W',
    23: '33_X',
    24: '34_Y',
    25: '35_Z',
    26: '36_Up',
    27: '37_Down',
    28: '38_Right',
    29: '39_Left',
    30: '40_Stop'
}

MODEL_CONFIG = {"conf": 0.3, "path": "models/best_yolov8m.pt"}
device = "cuda" if torch.cuda.is_available() else "cpu"

app = FastAPI()


# --- GLOBAL STATE FOR LIVE STREAM ---
class VideoStreamState:
    def __init__(self):
        self.frame = None  # The latest annotated frame (image)
        self.detections = []  # The latest JSON data
        self.lock = threading.Lock()
        self.running = True


stream_state = VideoStreamState()
model = None  # Global model instance


def get_model():
    """Singleton model loader"""
    global model
    if model is None:
        print(f"Loading model from {MODEL_CONFIG['path']}...")
        model = YOLO(MODEL_CONFIG["path"])
        model.to(device)
    return model


def map_detection(class_id_str: str, class_name: str) -> int:
    """Helper to map detections to ID_MAP"""
    if class_id_str in ID_MAP:
        return ID_MAP[class_id_str]
    if class_name in ID_MAP:
        return ID_MAP[class_name]
    return -1


def check_stream_available(url: str, max_attempts: int = 3, timeout: int = 3) -> bool:
    """Check if RTSP stream is available."""
    print(f"Checking stream availability at {url}...")
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    
    for attempt in range(max_attempts):
        print(f"Attempt {attempt + 1}/{max_attempts}...")
        cap = cv2.VideoCapture(url)
        
        # Give it some time to connect
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None:
                    print("✓ Stream is available!")
                    return True
            time.sleep(0.5)
        
        cap.release()
        if attempt < max_attempts - 1:
            print("Stream not available, retrying...")
            time.sleep(1)
    
    print("✗ Stream is not available. Disabling stream features.")
    return False


# --- BACKGROUND WORKER (THE "PRODUCER") ---
def processing_thread():
    """Continuously reads RTSP stream, runs YOLO, and updates global state."""
    global stream_available
    print(f"Starting background worker. Connecting to {RTSP_URL}...")

    # Load model inside the thread or ensure global model is loaded
    worker_model = get_model()

    # Optimization for OpenCV Latency
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

    cap = cv2.VideoCapture(RTSP_URL)
    connection_failures = 0
    max_failures = 10  # After 10 failures (20 seconds), disable stream

    while stream_state.running:
        if not cap.isOpened():
            connection_failures += 1
            if connection_failures >= max_failures:
                print(f"Failed to connect after {max_failures} attempts. Disabling stream.")
                stream_available = False
                break
            print(f"Stream not found. Retrying in 2s... (attempt {connection_failures}/{max_failures})")
            time.sleep(2)
            cap.open(RTSP_URL, cv2.CAP_FFMPEG)
            continue
        
        # Reset failure counter on successful connection
        connection_failures = 0

        ret, frame = cap.read()
        if not ret or frame is None or frame.size == 0 or frame.shape[0] == 0 or frame.shape[1] == 0:
            print("Invalid frame received, skipping...")
            continue

        # --- LIVE INFERENCE ---
        # Run YOLO on the frame (numpy array)
        results = worker_model(frame, conf=MODEL_CONFIG["conf"], verbose=False)

        # 1. Generate Annotated Frame
        annotated_frame = results[0].plot()

        # 2. Extract Data
        current_detections = []
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            cls_name = worker_model.names[cls_id]
            conf = float(box.conf[0])
            bbox = box.xyxy[0].tolist()

            image_id = map_detection(str(cls_id), cls_name)

            current_detections.append(
                {
                    "image_id": image_id,
                    "class_name": cls_name,
                    "confidence": conf,
                    "bbox": bbox,
                }
            )

        # --- UPDATE SHARED STATE ---
        with stream_state.lock:
            stream_state.frame = annotated_frame
            stream_state.detections = current_detections

    cap.release()
    print("Background worker stopped.")


@app.on_event("startup")
def startup_event():
    global stream_available
    
    # Determine if we should enable streaming
    if ENABLE_STREAM == "true":
        # Force enable
        stream_available = True
        print("Stream forcibly enabled via ENABLE_STREAM=true")
    elif ENABLE_STREAM == "false":
        # Force disable
        stream_available = False
        print("Stream forcibly disabled via ENABLE_STREAM=false")
    else:
        # Auto-detect (default)
        stream_available = check_stream_available(RTSP_URL)
    
    # Start the processing thread if stream is available
    if stream_available:
        print("Starting background processing thread...")
        t = threading.Thread(target=processing_thread, daemon=True)
        t.start()
    else:
        print("Stream disabled. Only file upload endpoints (/image, /stitch, /ping) will be available.")


# --- NEW LIVE ENDPOINTS ---


@app.get("/live_data")
async def get_live_data():
    """Returns the latest inference results as JSON."""
    if not stream_available:
        raise HTTPException(status_code=503, detail="Live stream is not available. Only file upload endpoints are enabled.")
    with stream_state.lock:
        return {
            "timestamp": datetime.now().isoformat(),
            "detections": stream_state.detections,
        }


@app.get("/live_video")
async def get_live_video():
    """Returns the MJPEG video stream."""
    if not stream_available:
        raise HTTPException(status_code=503, detail="Live stream is not available. Only file upload endpoints are enabled.")
    return StreamingResponse(
        generate_mjpeg(), media_type="multipart/x-mixed-replace;boundary=frame"
    )


@app.get("/snapshot")
async def get_snapshot():
    """Returns a single JPEG frame from the live stream."""
    if not stream_available:
        raise HTTPException(status_code=503, detail="Live stream is not available. Only file upload endpoints are enabled.")
    with stream_state.lock:
        if stream_state.frame is None:
            raise HTTPException(status_code=503, detail="No frame available")
        
        # Encode frame to JPEG
        (flag, encodedImage) = cv2.imencode(".jpg", stream_state.frame)
        if not flag:
            raise HTTPException(status_code=500, detail="Failed to encode frame")
    
    return StreamingResponse(
        iter([bytes(encodedImage)]),
        media_type="image/jpeg"
    )


def generate_mjpeg():
    """Generator for MJPEG stream"""
    while True:
        with stream_state.lock:
            if stream_state.frame is None:
                time.sleep(0.05)
                continue

            # Encode frame to JPEG
            (flag, encodedImage) = cv2.imencode(".jpg", stream_state.frame)
            if not flag:
                continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + bytearray(encodedImage) + b"\r\n"
        )

        # Cap framerate to save bandwidth (e.g., 20 FPS)
        time.sleep(0.05)


# --- EXISTING UPLOAD ENDPOINTS (PRESERVED) ---


@app.get("/ping")
async def ping():
    return {"status": "pong"}


@app.post("/image")
async def process_image(file: UploadFile = File(...)):
    # Uses the shared model
    model = get_model()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        results = model(tmp_path, conf=MODEL_CONFIG["conf"])
        detections = []
        annotated_frame = results[0].plot()

        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                cls_name = result.names[cls_id]
                conf = float(box.conf[0])
                bbox = box.xyxy[0].tolist()
                image_id = map_detection(str(cls_id), cls_name)

                detections.append(
                    {
                        "image_id": image_id,
                        "class_name": cls_name,
                        "confidence": conf,
                        "bbox": bbox,
                    }
                )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = "inference_results"
        os.makedirs(results_dir, exist_ok=True)
        filename_base = os.path.splitext(file.filename)[0]
        output_path = os.path.join(results_dir, f"{filename_base}_{timestamp}.jpg")
        cv2.imwrite(output_path, annotated_frame)

        return {
            "filename": file.filename,
            "detections": detections,
            "saved_image": output_path,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/stitch")
async def stitch_images(files: List[UploadFile] = File(...)):
    # ... (Stitching logic kept exactly as is)
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 images to stitch")

    temp_files = []
    images = []

    try:
        for file in files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                shutil.copyfileobj(file.file, tmp)
                tmp_path = tmp.name
                temp_files.append(tmp_path)

            img = cv2.imread(tmp_path)
            if img is not None:
                images.append(img)

        if len(images) < 2:
            raise HTTPException(
                status_code=400, detail="Could not decode enough images"
            )

        stitcher = cv2.Stitcher_create()
        status, stitched = stitcher.stitch(images)

        if status == cv2.Stitcher_OK:
            output_path = os.path.join(tempfile.gettempdir(), "stitched_output.jpg")
            cv2.imwrite(output_path, stitched)
            return FileResponse(
                output_path, media_type="image/jpeg", filename="stitched.jpg"
            )
        else:
            raise HTTPException(
                status_code=500, detail=f"Stitching failed with status code {status}"
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for p in temp_files:
            if os.path.exists(p):
                os.remove(p)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)