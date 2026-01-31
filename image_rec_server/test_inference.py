from ultralytics import YOLO

# Load the YOLOv8 model
model = YOLO('models/best_yolov8m.pt')

# Perform inference on a test image
results = model.predict('test_images/image.jpg', save=True, conf=0.5)

# Print the results
for result in results:
    print("Detected objects:")
    for box in result.boxes:
        print(f"  Class: {model.names[int(box.cls)]}, Confidence: {box.conf.item():.2f}, BBox: {box.xyxy.tolist()}")

print("Inference completed. Check the output image in the runs/detect/ directory.")