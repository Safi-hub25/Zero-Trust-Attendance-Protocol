import cv2
import os
import time

# Create folders
save_path = "Dataset_New"
os.makedirs(f"{save_path}/Real", exist_ok=True)
os.makedirs(f"{save_path}/Fake", exist_ok=True)

cap = cv2.VideoCapture(0)
count = 0

print("--- DATA COLLECTOR ---")
print("Press '1' to save REAL face (Capture yourself)")
print("Press '2' to save FAKE face (Capture phone/photo)")
print("Press 'q' to Quit")

while True:
    success, img = cap.read()
    if not success: break
    
    # Resize for faster training later (640x640 is standard for YOLO)
    img_resized = cv2.resize(img, (640, 640))
    
    cv2.imshow("Data Collector", img)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('1'): # Save Real
        count += 1
        filename = f"{save_path}/Real/Image_{time.time()}.jpg"
        cv2.imwrite(filename, img_resized)
        print(f"[SAVED REAL] {filename}")
        
    elif key == ord('2'): # Save Fake
        count += 1
        filename = f"{save_path}/Fake/Image_{time.time()}.jpg"
        cv2.imwrite(filename, img_resized)
        print(f"[SAVED FAKE] {filename}")
        
    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()   

