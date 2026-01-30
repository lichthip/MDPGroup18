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
RTSP_URL = "rtsp://192.168.18.18:8554/cam"

# ID Map
ID_MAP = {
    "10": 10,  # Bullseye
    "11": 11,  # 1
    "12": 12,  # 2
    "13": 13,  # 3
    "14": 14,  # 4
    "15": 15,  # 5
    "16": 16,  # 6
    "17": 17,  # 7
    "18": 18,  # 8
    "19": 19,  # 9
    "20": 20,  # a
    "21": 21,  # b
    "22": 22,  # c
    "23": 23,  # d
    "24": 24,  # e
    "25": 25,  # f
    "26": 26,  # g
    "27": 27,  # h
    "28": 28,  # s
    "29": 29,  # t
    "30": 30,  # u
    "31": 31,  # v
    "32": 32,  # w
    "33": 33,  # x
    "34": 34,  # y
    "35": 35,  # z
    "36": 36,  # Up Arrow
    "37": 37,  # Down Arrow
    "38": 38,  # Right Arrow
    "39": 39,  # Left Arrow
    "40": 40,  # target
}

MODEL_CONFIG = {"conf": 0.3, "path": "models/best_JH.pt"}
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


# --- BACKGROUND WORKER (THE "PRODUCER") ---
def processing_thread():
    """Continuously reads RTSP stream, runs YOLO, and updates global state."""
    print(f"Starting background worker. Connecting to {RTSP_URL}...")

    # Load model inside the thread or ensure global model is loaded
    worker_model = get_model()

    # Optimization for OpenCV Latency
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

    cap = cv2.VideoCapture(RTSP_URL)

    while stream_state.running:
        if not cap.isOpened():
            print("Stream not found. Retrying in 2s...")
            time.sleep(2)
            cap.open(RTSP_URL, cv2.CAP_FFMPEG)
            continue

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
    # Start the processing thread when API launches
    t = threading.Thread(target=processing_thread, daemon=True)
    t.start()


# --- NEW LIVE ENDPOINTS ---


@app.get("/live_data")
async def get_live_data():
    """Returns the latest inference results as JSON."""
    with stream_state.lock:
        return {
            "timestamp": datetime.now().isoformat(),
            "detections": stream_state.detections,
        }


@app.get("/live_video")
async def get_live_video():
    """Returns the MJPEG video stream."""
    return StreamingResponse(
        generate_mjpeg(), media_type="multipart/x-mixed-replace;boundary=frame"
    )


@app.get("/snapshot")
async def get_snapshot():
    """Returns a single JPEG frame from the live stream."""
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
