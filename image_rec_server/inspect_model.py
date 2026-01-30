from ultralytics import YOLO

# Load the model
model = YOLO('models/best_yolov8m.pt')  # or your custom model.pt

# Print the class names dictionary
print(model.names)