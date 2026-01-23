import os
import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from ultralytics import YOLO
import tempfile
import shutil
from typing import List, Dict
from datetime import datetime
import torch
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
    "40": 40   # target
}

# confidence threshold for the YOLO model during inference and file path to weights
MODEL_CONFIG = {"conf": 0.3, "path": "models/best_JH.pt"}  # model trained on 50k images
device = "cuda" if torch.cuda.is_available() else "cpu"
app = FastAPI()

def get_model():
    global model
    model = YOLO(MODEL_CONFIG["path"])
    model.to(device)
    return model

def map_detection(class_id_str: str, class_name: str) -> int:
    """
    Try to map the detection to the ID_MAP.
    Checks class_id_str first, then tries to match class_name if possible.
    Returns -1 if not found.
    """
    if class_id_str in ID_MAP:
        return ID_MAP[class_id_str]
    # Fallback: maybe the model returns class names that match the keys?
    if class_name in ID_MAP:
        return ID_MAP[class_name]
    return -1

@app.get("/ping")
async def ping():
    return {"status": "pong"}

@app.post("/image")
async def process_image(file: UploadFile = File(...)):
    model = get_model()
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        # Run inference
        results = model(tmp_path)
        detections = []
        
        annotated_frame = results[0].plot()
        
        # Prepare JSON data
        for result in results:
            for box in result.boxes:
                # Extract details
                cls_id = int(box.cls[0])
                cls_name = result.names[cls_id]
                conf = float(box.conf[0])
                bbox = box.xyxy[0].tolist() # [x1, y1, x2, y2]
                
                # Use str(cls_id) or cls_name to map
                image_id = map_detection(str(cls_id), cls_name)
                
                detections.append({
                    "image_id": image_id,
                    "class_name": cls_name,
                    "confidence": conf,
                    "bbox": bbox
                })

        # Save annotated image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = "inference_results"
        os.makedirs(results_dir, exist_ok=True)
        filename_base = os.path.splitext(file.filename)[0]
        output_path = os.path.join(results_dir, f"{filename_base}_{timestamp}.jpg")
        
        cv2.imwrite(output_path, annotated_frame)
        print(f"Saved annotated image to {output_path}")

        return {"filename": file.filename, "detections": detections, "saved_image": output_path}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.post("/video")
async def process_video(file: UploadFile = File(...)):
    model = get_model()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        cap = cv2.VideoCapture(tmp_path)
        frame_detections = []
        frame_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            # Run inference on the frame
            results = model(frame)
            
            frame_dets = []
            for result in results:
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    cls_name = result.names[cls_id]
                    conf = float(box.conf[0])
                    bbox = box.xyxy[0].tolist()
                    
                    image_id = map_detection(str(cls_id), cls_name)
                    
                    frame_dets.append({
                        "image_id": image_id,
                        "class_id": cls_id,
                        "class_name": cls_name,
                        "confidence": conf,
                        "bbox": bbox
                    })
            
            if frame_dets:
                 frame_detections.append({
                     "frame_index": frame_count,
                     "detections": frame_dets
                 })
            
            frame_count += 1

        cap.release()
        return {"filename": file.filename, "total_frames": frame_count, "results": frame_detections}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.post("/stitch")
async def stitch_images(files: List[UploadFile] = File(...)):
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 images to stitch")

    temp_files = []
    images = []

    try:
        # Read all images
        for file in files:
            # Create temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                shutil.copyfileobj(file.file, tmp)
                tmp_path = tmp.name
                temp_files.append(tmp_path)
            
            # Read with OpenCV
            img = cv2.imread(tmp_path)
            if img is None:
                continue
            images.append(img)

        if len(images) < 2:
             raise HTTPException(status_code=400, detail="Could not decode enough images")

        # Stitch
        stitcher = cv2.Stitcher_create()
        status, stitched = stitcher.stitch(images)

        if status == cv2.Stitcher_OK:
            # Save result to temp file
            output_path = os.path.join(tempfile.gettempdir(), "stitched_output.jpg")
            cv2.imwrite(output_path, stitched)
            return FileResponse(output_path, media_type="image/jpeg", filename="stitched.jpg")
        else:
            raise HTTPException(status_code=500, detail=f"Stitching failed with status code {status}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup input temp files
        for p in temp_files:
            if os.path.exists(p):
                os.remove(p)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
