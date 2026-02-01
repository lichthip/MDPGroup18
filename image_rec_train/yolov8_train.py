from ultralytics import YOLO

def train_model():
    # 1. Load a pretrained YOLOv8 model
    # 'yolov8n.pt' is nano (fastest), 'yolov8m.pt' or 'yolov8l.pt' are better for accuracy
    model = YOLO('yolov8m.pt') 

    # 2. Train the model
    # point 'data' to the data.yaml file downloaded by Roboflow
    model.train(
        data='datasets/MDP-Merged-1/data.yaml',
        epochs=100,
        imgsz=640,

        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=5,
        fliplr=0.0,
        flipud=0.0,
        auto_augment=None,

        cos_lr=True,
        device=[0, 1],
        batch=256,
        name='yolov8_custom',
        workers=16,
        cache=True,
        amp=True
    )

    print("Training Complete. Best model saved at runs/detect/yolov8_custom/weights/best.pt")

def resume_training():
    model = YOLO('runs/detect/yolov8_custom/weights/last.pt')

    model.train(resume=True, device=[0, 1])

if __name__ == '__main__':
    train_model()
    # resume_training()