import cv2
import mediapipe as mp
import numpy as np
import time
import math
import sys
import os
import subprocess
import urllib.request
import re
import sqlite3
import logging
from ultralytics import YOLO
from datetime import datetime
from deepface import DeepFace

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
logging.getLogger("deepface").setLevel(logging.ERROR)

AUTHORIZED_BSSIDS = ["dc08562fe989", "a8537d28a3f1", "a8f7d9db48b1", "62a3443fb882"]


MATCH_THRESHOLD = 0.35 # Strict baseline for looking straight
TURN_THRESHOLD = 0.55  # Relaxed allowance for extreme side angles and pitching up/down

if len(sys.argv) < 2: sys.exit("CRITICAL ERROR: Student ID not provided.")
current_student_id = sys.argv[1]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, f"face_{current_student_id}.npy")
SQL_DB = os.path.join(BASE_DIR, "mdx_system.db")

if not os.path.exists(DATA_FILE): sys.exit(f"ERROR: Biometric profile not found.")

# Load the Matrix
registered_matrix = np.load(DATA_FILE)
if registered_matrix.ndim == 1: registered_matrix = np.array([registered_matrix])

if not os.path.exists("best.pt"): sys.exit("CRITICAL: 'best.pt' missing!")
ai_model = YOLO("best.pt")

model_path = 'face_landmarker.task'
if not os.path.exists(model_path):
    urllib.request.urlretrieve("https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task", model_path)

options = mp.tasks.vision.FaceLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
    running_mode=mp.tasks.vision.RunningMode.VIDEO, num_faces=1,
    min_face_detection_confidence=0.7, min_tracking_confidence=0.7
)
landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)

def clean_mac(mac_string): return re.sub(r'[^a-z0-9]', '', str(mac_string).lower()) if mac_string else ""
def get_current_bssid():
    try:
        results = subprocess.check_output(["netsh", "wlan", "show", "interfaces"]).decode('utf-8', errors="ignore")
        for line in results.split('\n'):
            if "BSSID" in line: return clean_mac(line.split(':', 1)[1])
    except: pass
    return None

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

def get_cosine_distance(a, b):
    a, b = np.array(a), np.array(b)
    return 1 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

cap = cv2.VideoCapture(0)
LEFT_EYE, RIGHT_EYE = [362, 263, 386, 374], [33, 133, 159, 145]
stage, pose_hold_start, eye_was_closed = "AI_SCAN", None, False
current_wifi, network_verified, last_check, last_ts = "Scanning...", False, 0, 0
attendance_logged = False 

frame_count = 0 
is_recognized = False

while True:
    success, frame = cap.read()
    if not success: break
    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, _ = frame.shape
    curr_time = time.time()
    frame_count += 1

    if curr_time - last_check > 5.0:
        temp = get_current_bssid()
        if temp: current_wifi, network_verified = temp, temp in AUTHORIZED_BSSIDS
        last_check = curr_time

    is_too_dim = np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)) < 80 
    
    results = ai_model(cv2.resize(frame, (640, 640)), stream=True, verbose=False)
    is_spoof, ai_label = False, "AI: ..."
    for r in results:
        if r.probs:
            prob, cname = r.probs.top1conf.item(), ai_model.names[r.probs.top1]
            ai_label = f"AI: {cname} ({int(prob*100)}%)"
            if cname == "Fake" and prob > 0.7: is_spoof = True

    # --- MULTI-ANGLE DEEPFACE VERIFICATION ---
    if frame_count % 3 == 0:
        try:
            res = DeepFace.represent(img_path=rgb_frame, model_name="Facenet", enforce_detection=False)
            live_embedding = res[0]["embedding"]
            
            # Check against Straight, Left, and Right profiles!
            distances = [get_cosine_distance(ref, live_embedding) for ref in registered_matrix]
            best_distance = min(distances)
            
            # If turning or pitching, relax the threshold slightly
            current_threshold = TURN_THRESHOLD if stage in ["LEFT", "RIGHT", "VERIFIED"] else MATCH_THRESHOLD
            is_recognized = (best_distance < current_threshold)
        except: is_recognized = False

    current_ts = int(curr_time * 1000)
    if current_ts <= last_ts: current_ts = last_ts + 1
    last_ts = current_ts

    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    detection = landmarker.detect_for_video(mp_image, current_ts)
    status_msg, status_color = "Scanning Face...", (255, 255, 255)

    if detection.face_landmarks:
        for landmarks in detection.face_landmarks:
            ear = (calculate_ear(landmarks, LEFT_EYE) + calculate_ear(landmarks, RIGHT_EYE)) / 2.0
            yaw = get_yaw(landmarks, w, h)
            
            x_coords, y_coords = [], []
            for lm in landmarks:
                cx, cy = int(lm.x * w), int(lm.y * h)
                x_coords.append(cx)
                y_coords.append(cy)
                cv2.circle(frame, (cx, cy), 1, (0, 255, 0), -1) 
                
            xmin, ymin, xmax, ymax = min(x_coords), min(y_coords), max(x_coords), max(y_coords)
            
            box_color = (255, 150, 0) if is_recognized else (0, 0, 255)
            box_label = current_student_id if is_recognized else "UNKNOWN IMPOSTER"
            cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), box_color, 2)
            cv2.putText(frame, box_label, (xmin, ymin-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)

            if is_too_dim: status_msg, status_color = "TOO DIM! Increase screen brightness.", (0, 0, 255)
            elif not network_verified: status_msg, status_color = "UNAUTHORIZED NETWORK", (0, 0, 255)
            elif is_spoof: status_msg, status_color, stage = "SPOOF DETECTED", (0, 0, 255), "AI_SCAN"
            elif not is_recognized: status_msg, status_color, stage = "UNKNOWN PERSON", (0, 0, 255), "AI_SCAN"
            else:
                if stage == "AI_SCAN":
                    status_msg, status_color = f"MATCHED: {current_student_id}", (0, 255, 0)
                    if "Real" in ai_label: stage = "BLINK"
                elif stage == "BLINK":
                    status_msg = "STEP 1: Blink"
                    if ear < 0.2: eye_was_closed = True
                    if eye_was_closed and ear > 0.25: stage, eye_was_closed = "LEFT", False
                elif stage == "LEFT":
                    status_msg, status_color = "STEP 2: Turn Left", (255, 200, 0)
                    if yaw > 12.0:
                        if not pose_hold_start: pose_hold_start = time.time()
                        if time.time() - pose_hold_start > 0.6: stage, pose_hold_start = "RIGHT", None
                elif stage == "RIGHT":
                    status_msg, status_color = "STEP 3: Turn Right", (255, 200, 0)
                    if yaw < -12.0:
                        if not pose_hold_start: pose_hold_start = time.time()
                        if time.time() - pose_hold_start > 0.6: stage, pose_hold_start = "VERIFIED", time.time()
                        
                elif stage == "VERIFIED":
                    status_msg, status_color = "ATTENDANCE MARKED", (0, 255, 0)
                    if not attendance_logged: 
                        now = datetime.now()
                        conn = sqlite3.connect(SQL_DB)
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO attendance (student_id, date, time, status, photo) VALUES (?, ?, ?, ?, ?)", 
                                       (current_student_id, now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'), 'Present', 'PRIVACY_PROTECTED'))
                        conn.commit()
                        conn.close()
                        attendance_logged = True 

    if stage == "VERIFIED" and pose_hold_start and (time.time() - pose_hold_start > 3.0): break

    mask = np.zeros((h, w), dtype=np.uint8)
    center, axes = (w // 2, h // 2), (int(h * 0.32), int(h * 0.45)) 
    cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)
    circular_frame = cv2.bitwise_and(frame, frame, mask=mask)

    cv2.ellipse(circular_frame, center, axes, 0, 0, 360, (200, 200, 200), 2)
    box_x1, box_y1, box_x2, box_y2 = w - 320, h - 85, w - 10, h - 10 
    cv2.rectangle(circular_frame, (box_x1, box_y1), (box_x2, box_y2), (0, 0, 0), -1)
    cv2.putText(circular_frame, status_msg, (box_x1 + 10, box_y1 + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_color, 2)
    net_col = (0, 255, 0) if network_verified else (0, 0, 255)
    cv2.putText(circular_frame, f"NET: ...{current_wifi[-5:] if current_wifi else 'NONE'}", (box_x1 + 10, box_y1 + 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, net_col, 1)
    
    cv2.imshow("ZTAP Attendance", circular_frame)
    if cv2.waitKey(1) & 0xFF == 27: break

cap.release()
cv2.destroyAllWindows()