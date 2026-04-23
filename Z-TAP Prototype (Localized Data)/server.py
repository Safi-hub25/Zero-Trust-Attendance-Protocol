from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import uvicorn
import cv2
import mediapipe as mp
import numpy as np
import os
import tempfile
import urllib.request

app = FastAPI(title="MDX Biometric Server")

# --- PATHS & FOLDERS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(IMAGE_DIR, exist_ok=True)

# --- MEDIAPIPE SETUP ---
model_path = 'face_landmarker.task'
url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
if not os.path.exists(model_path):
    print("Downloading MediaPipe model...")
    urllib.request.urlretrieve(url, model_path)

options = mp.tasks.vision.FaceLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
    running_mode=mp.tasks.vision.RunningMode.IMAGE, # Changed to IMAGE mode for processing video frames
    num_faces=1,
    min_face_detection_confidence=0.5
)
landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)

# --- HELPERS ---
def get_face_vector(landmarks):
    nose = landmarks[1] 
    vector = []
    for lm in landmarks:
        vector.extend([lm.x - nose.x, lm.y - nose.y, lm.z - nose.z])
    return np.array(vector)

def get_bounding_box(landmarks, w, h):
    x_coords = [lm.x for lm in landmarks]
    y_coords = [lm.y for lm in landmarks]
    x_min, x_max = int(min(x_coords) * w), int(max(x_coords) * w)
    y_min, y_max = int(min(y_coords) * h), int(max(y_coords) * h)
    pad_x, pad_y = int((x_max - x_min) * 0.2), int((y_max - y_min) * 0.2)
    return max(0, x_min - pad_x), max(0, y_min - int(pad_y * 1.5)), min(w, x_max + pad_x), min(h, y_max + pad_y)

# --- API ROUTES ---
@app.get("/")
def ping():
    return {"status": "online", "message": "MDX AI Server is running!"}

@app.post("/api/register_face")
async def register_face(
    student_id: str = Form(...),
    video: UploadFile = File(...)
):
    """Receives a video from Flutter, extracts 100 faces, and saves the .npy profile."""
    if not student_id.startswith("ZT-"):
        raise HTTPException(status_code=400, detail="Invalid Student ID format.")

    # 1. Save the uploaded video to a temporary file
    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    content = await video.read()
    temp_video.write(content)
    temp_video.close()

    # 2. Open the video with OpenCV
    cap = cv2.VideoCapture(temp_video.name)
    
    face_data_buffer = []
    images_saved = 0
    
    while cap.isOpened() and images_saved < 100:
        success, frame = cap.read()
        if not success: break
        
        h, w, _ = frame.shape
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        detection = landmarker.detect(mp_image)
        
        if detection.face_landmarks:
            for landmarks in detection.face_landmarks:
                vector = get_face_vector(landmarks)
                x1, y1, x2, y2 = get_bounding_box(landmarks, w, h)
                
                if y1 < y2 and x1 < x2:
                    face_crop = frame[y1:y2, x1:x2]
                    if face_crop.size != 0:
                        images_saved += 1
                        # Save the JPG for the assignment
                        file_path = os.path.join(IMAGE_DIR, f"user.{student_id}.{images_saved}.jpg")
                        cv2.imwrite(file_path, cv2.resize(cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY), (450, 450)))
                        
                        # Save the math for the .npy vector
                        face_data_buffer.append(vector)

    cap.release()
    os.remove(temp_video.name) # Clean up the temp file

    # 3. Check if we got enough data
    if len(face_data_buffer) < 10:
        raise HTTPException(status_code=400, detail="Could not detect a clear face in the video. Please try again.")

    # 4. Save the highly secure .npy file
    data_file = os.path.join(BASE_DIR, f"face_{student_id}.npy")
    np.save(data_file, np.mean(face_data_buffer, axis=0))

    return {
        "status": "success",
        "message": "Biometric profile created successfully.",
        "images_extracted": images_saved
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)