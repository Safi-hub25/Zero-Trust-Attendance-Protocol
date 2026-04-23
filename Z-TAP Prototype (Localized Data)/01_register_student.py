import cv2
import mediapipe as mp
import numpy as np
import sys
import os
import urllib.request
import math
import logging
from deepface import DeepFace

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
logging.getLogger("deepface").setLevel(logging.ERROR)

if len(sys.argv) < 2: sys.exit("Error: Student ID not provided.")
student_id = sys.argv[1]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(BASE_DIR, 'face_landmarker.task')
if not os.path.exists(model_path):
    urllib.request.urlretrieve("https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task", model_path)

options = mp.tasks.vision.FaceLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
    running_mode=mp.tasks.vision.RunningMode.VIDEO, num_faces=1,
    min_face_detection_confidence=0.7, min_tracking_confidence=0.7
)
landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)

def get_yaw(landmarks, img_w, img_h):
    face_2d, face_3d = [], []
    for idx in [1, 152, 33, 263, 61, 291]:
        lm = landmarks[idx]
        face_2d.append([int(lm.x * img_w), int(lm.y * img_h)])
        face_3d.append([int(lm.x * img_w), int(lm.y * img_h), lm.z]) 
    cam_matrix = np.array([[img_w, 0, img_h/2], [0, img_w, img_w/2], [0, 0, 1]])
    _, rot_vec, _ = cv2.solvePnP(np.array(face_3d, dtype=np.float64), np.array(face_2d, dtype=np.float64), cam_matrix, np.zeros((4,1)))
    rmat, _ = cv2.Rodrigues(rot_vec)
    angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)
    return angles[1] * -360 

def calculate_ear(landmarks, indices):
    v_dist = math.dist([landmarks[indices[2]].x, landmarks[indices[2]].y], [landmarks[indices[3]].x, landmarks[indices[3]].y])
    h_dist = math.dist([landmarks[indices[0]].x, landmarks[indices[0]].y], [landmarks[indices[1]].x, landmarks[indices[1]].y])
    return v_dist / h_dist if h_dist != 0 else 0.0

LEFT_EYE, RIGHT_EYE = [362, 263, 386, 374], [33, 133, 159, 145]

cap = cv2.VideoCapture(0)

# --- THE FIX: Multi-Angle Galleries ---
straight_encs, left_encs, right_encs = [], [], []
stage = "STRAIGHT"
eye_was_closed = False

print(f"Starting Enrollment for {student_id}...")

while stage != "DONE":
    ret, frame = cap.read()
    if not ret: break
    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, _ = frame.shape
    
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    timestamp = int(cv2.getTickCount() / cv2.getTickFrequency() * 1000)
    detection = landmarker.detect_for_video(mp_image, timestamp)
    
    status_msg, status_color = "Locating face...", (255, 255, 255)
    
    if detection.face_landmarks:
        landmarks = detection.face_landmarks[0]
        yaw = get_yaw(landmarks, w, h)
        ear = (calculate_ear(landmarks, LEFT_EYE) + calculate_ear(landmarks, RIGHT_EYE)) / 2.0
        
        x_coords, y_coords = [], []
        for lm in landmarks:
            cx, cy = int(lm.x * w), int(lm.y * h)
            x_coords.append(cx)
            y_coords.append(cy)
            cv2.circle(frame, (cx, cy), 1, (0, 255, 0), -1) 
            
        xmin, ymin, xmax, ymax = min(x_coords), min(y_coords), max(x_coords), max(y_coords)
        cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (255, 150, 0), 2)
        
        # --- CAPTURE EMBEDDINGS AT EVERY ANGLE ---
        if stage == "STRAIGHT":
            status_msg, status_color = "Look straight at the camera.", (0, 255, 255)
            try:
                res = DeepFace.represent(img_path=rgb_frame, model_name="Facenet", enforce_detection=False)
                straight_encs.append(res[0]["embedding"])
            except: pass
            if len(straight_encs) >= 4: stage = "BLINK"
                
        elif stage == "BLINK":
            status_msg, status_color = "STEP 1: Blink your eyes", (0, 255, 0)
            if ear < 0.2: eye_was_closed = True
            if eye_was_closed and ear > 0.25: stage = "LEFT"
                
        elif stage == "LEFT":
            status_msg, status_color = "STEP 2: Turn head LEFT", (0, 165, 255)
            if yaw > 12.0: # Wait until you are actually turning to capture!
                try:
                    res = DeepFace.represent(img_path=rgb_frame, model_name="Facenet", enforce_detection=False)
                    left_encs.append(res[0]["embedding"])
                except: pass
                if len(left_encs) >= 3: stage = "RIGHT"
                    
        elif stage == "RIGHT":
            status_msg, status_color = "STEP 3: Turn head RIGHT", (0, 165, 255)
            if yaw < -12.0: # Wait until you are actually turning to capture!
                try:
                    res = DeepFace.represent(img_path=rgb_frame, model_name="Facenet", enforce_detection=False)
                    right_encs.append(res[0]["embedding"])
                except: pass
                if len(right_encs) >= 3: stage = "DONE"

    cv2.rectangle(frame, (0, h - 60), (w, h), (0, 0, 0), -1)
    cv2.putText(frame, status_msg, (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
    cv2.putText(frame, "Zero Trust Enrollment", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
    cv2.imshow("ZTAP Registration", frame)
    if cv2.waitKey(1) & 0xFF == 27: break 

cap.release()
cv2.destroyAllWindows()

if stage == "DONE":
    # Bundle the Straight, Left, and Right profiles into one matrix
    v_s = np.mean(straight_encs, axis=0)
    v_l = np.mean(left_encs, axis=0)
    v_r = np.mean(right_encs, axis=0)
    
    master_matrix = np.array([v_s, v_l, v_r])
    save_path = os.path.join(BASE_DIR, f"face_{student_id}.npy")
    np.save(save_path, master_matrix)
    print("Profile saved successfully!")
else:
    print("Enrollment canceled.")