from ultralytics import YOLO

# Load a pre-trained Nano model (lightweight and fast)
model = YOLO('yolov8n-cls.pt') 

# Train it on your data
# Note: Ensure your 'Dataset' folder is in the same directory
results = model.train(
    data='Dataset', # Point to the folder created in Step 1
    epochs=15,      # 15 runs through the data is enough for this
    imgsz=640       # Standard size
)

print("Training Complete! Model saved in runs/classify/train/weights/best.pt")





