import cv2
import hashlib
import mediapipe as mp
import numpy as np
import sys
import os
import urllib.request
import math
import logging
import time
from deepface import DeepFace
from ultralytics import YOLO
import requests

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
logging.getLogger("deepface").setLevel(logging.ERROR)

BG_DARK = (23, 11, 3)
SURFACE = (47, 25, 10)
ACCENT_RED = (70, 57, 230)
ACCENT_GRN = (65, 255, 0)
TEXT_DIM = (130, 98, 74)
TEXT_WHITE = (255, 255, 255)

if len(sys.argv) < 2: sys.exit("Error: Student ID not provided.")
student_id = sys.argv[1]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if not os.path.exists("best.pt"): sys.exit("CRITICAL: 'best.pt' anti-spoof model missing!")
ai_model = YOLO("best.pt")

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

def draw_corner_brackets(img, xmin, ymin, xmax, ymax, color, length=20, thickness=3):
    cv2.line(img, (xmin, ymin), (xmin + length, ymin), color, thickness)
    cv2.line(img, (xmin, ymin), (xmin, ymin + length), color, thickness)
    cv2.line(img, (xmax, ymin), (xmax - length, ymin), color, thickness)
    cv2.line(img, (xmax, ymin), (xmax, ymin + length), color, thickness)
    cv2.line(img, (xmin, ymax), (xmin + length, ymax), color, thickness)
    cv2.line(img, (xmin, ymax), (xmin, ymax - length), color, thickness)
    cv2.line(img, (xmax, ymax), (xmax - length, ymax), color, thickness)
    cv2.line(img, (xmax, ymax), (xmax, ymax - length), color, thickness)

LEFT_EYE, RIGHT_EYE = [362, 263, 386, 374], [33, 133, 159, 145]
cap = cv2.VideoCapture(0)

window_name = "Z-TAP Bio-Enrollment"
cv2.namedWindow(window_name)

straight_encs, left_encs, right_encs = [], [], []
stage = "ALIGN"
pose_hold_start = None
eye_was_closed = False
progress_val = 0.0
frame_count = 0

print(f"Starting Strict Enrollment for {student_id}...")

while stage != "DONE":
    ret, frame = cap.read()
    if not ret: break
    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, _ = frame.shape
    curr_time = time.time()
    frame_count += 1
    
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_lighting = np.mean(gray_frame)
    is_too_dim = mean_lighting < 80 
    is_too_bright = mean_lighting > 190 
    
    results = ai_model(cv2.resize(frame, (640, 640)), stream=True, verbose=False)
    is_spoof, ai_label = False, "AI: ..."
    for r in results:
        if r.probs:
            prob, cname = r.probs.top1conf.item(), ai_model.names[r.probs.top1]
            ai_label = f"AI: {cname} ({int(prob*100)}%)"
            if cname == "Fake" and prob > 0.65:
                is_spoof = True
    
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    timestamp = int(cv2.getTickCount() / cv2.getTickFrequency() * 1000)
    detection = landmarker.detect_for_video(mp_image, timestamp)

    if detection.face_landmarks:
        for face_landmarks in detection.face_landmarks:
            for lm in face_landmarks:
                cx, cy = int(lm.x * w), int(lm.y * h)
                cv2.circle(frame, (cx, cy), 1, (220, 220, 220), -1)
    
    status_msg, status_color, box_color = "SEARCHING FOR SUBJECT...", TEXT_WHITE, TEXT_DIM
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 80), BG_DARK, -1)
    cv2.rectangle(overlay, (0, h - 120), (w, h), BG_DARK, -1)
    cv2.addWeighted(overlay, 0.9, frame, 0.1, 0, frame)

    cv2.putText(frame, "Z-TAP :: SECURE ENROLLMENT", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, ACCENT_RED, 2)
    cv2.putText(frame, f"TARGET NODE: {student_id} | {ai_label}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, TEXT_DIM, 1)
    
    if detection.face_landmarks:
        landmarks = detection.face_landmarks[0]
        yaw = get_yaw(landmarks, w, h)
        ear = (calculate_ear(landmarks, LEFT_EYE) + calculate_ear(landmarks, RIGHT_EYE)) / 2.0
        
        x_coords, y_coords = [], []
        for lm in landmarks:
            cx, cy = int(lm.x * w), int(lm.y * h)
            x_coords.append(cx)
            y_coords.append(cy)
            
        xmin, ymin, xmax, ymax = min(x_coords), min(y_coords), max(x_coords), max(y_coords)
        face_width = xmax - xmin
        center_x = (xmin + xmax) / 2
        
        if is_too_dim:
            status_msg, status_color, box_color = "ERROR: LIGHTING TOO DIM", ACCENT_RED, ACCENT_RED
            stage = "ALIGN"
            progress_val = 0.0
        elif is_too_bright:
            status_msg, status_color, box_color = "ERROR: EXTREME GLARE / TOO BRIGHT", ACCENT_RED, ACCENT_RED
            stage = "ALIGN"
            progress_val = 0.0
        elif is_spoof:
            status_msg, status_color, box_color = "SECURITY ALERT: SPOOF DETECTED", ACCENT_RED, ACCENT_RED
            stage = "ALIGN" 
            progress_val = 0.0
            straight_encs, left_encs, right_encs = [], [], [] 
        else:
            if stage == "ALIGN":
                progress_val = 0.1
                if face_width < w * 0.25:
                    status_msg, status_color, box_color = "MOVE CLOSER", TEXT_DIM, TEXT_DIM
                    pose_hold_start = None
                elif center_x < w * 0.35 or center_x > w * 0.65:
                    status_msg, status_color, box_color = "CENTER YOUR FACE", TEXT_DIM, TEXT_DIM
                    pose_hold_start = None
                else:
                    status_msg, status_color, box_color = "HOLD STEADY...", TEXT_WHITE, ACCENT_GRN
                    if not pose_hold_start: pose_hold_start = time.time()
                    if time.time() - pose_hold_start > 1.5: 
                        stage = "STRAIGHT"
                        pose_hold_start = None
            elif stage == "STRAIGHT":
                progress_val = 0.3
                box_color = ACCENT_GRN
                status_msg, status_color = f"ENROLL 1/4: LOOK STRAIGHT [{len(straight_encs)}/5]", TEXT_WHITE
                if frame_count % 3 == 0: 
                    try:
                        res = DeepFace.represent(img_path=rgb_frame, model_name="Facenet", enforce_detection=False)
                        straight_encs.append(res[0]["embedding"])
                    except: pass
                if len(straight_encs) >= 5: stage = "BLINK"
            elif stage == "BLINK":
                progress_val = 0.5
                box_color = SURFACE
                status_msg, status_color = "ENROLL 2/4: BLINK YOUR EYES", TEXT_WHITE
                if ear < 0.2: eye_was_closed = True
                if eye_was_closed and ear > 0.25: stage, eye_was_closed = "LEFT", False
            elif stage == "LEFT":
                progress_val = 0.7
                box_color = ACCENT_GRN if yaw > 15.0 else SURFACE
                status_msg, status_color = f"ENROLL 3/4: TURN LEFT [{len(left_encs)}/5]", TEXT_WHITE
                if yaw > 15.0 and frame_count % 3 == 0:
                    try:
                        res = DeepFace.represent(img_path=rgb_frame, model_name="Facenet", enforce_detection=False)
                        left_encs.append(res[0]["embedding"])
                    except: pass
                if len(left_encs) >= 5: stage = "RIGHT"
            elif stage == "RIGHT":
                progress_val = 0.9
                box_color = ACCENT_GRN if yaw < -15.0 else SURFACE
                status_msg, status_color = f"ENROLL 4/4: TURN RIGHT [{len(right_encs)}/5]", TEXT_WHITE
                if yaw < -13.0 and frame_count % 3 == 0:
                    try:
                        res = DeepFace.represent(img_path=rgb_frame, model_name="Facenet", enforce_detection=False)
                        right_encs.append(res[0]["embedding"])
                    except: pass
                if len(right_encs) >= 5: stage = "DONE"

        pad = 20
        draw_corner_brackets(frame, xmin-pad, ymin-pad, xmax+pad, ymax+pad, box_color, length=30, thickness=2)

    cv2.putText(frame, status_msg, (30, h - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
    bar_x, bar_y, bar_w, bar_h = 30, h - 45, w - 60, 10
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), TEXT_DIM, 1)
    
    fill_w = int(bar_w * progress_val)
    if fill_w > 0: cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), ACCENT_GRN, -1)

    cv2.imshow(window_name, frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q') or key == 27: break
    try:
        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1: break
    except cv2.error: break

cap.release()
cv2.destroyAllWindows()

# ==========================================
# --- DATA COMPILATION & CLOUD SYNC ---
# ==========================================
if stage == "DONE":
    print("\nProcessing Biometric Topography...")
    
    v_straight = np.mean(straight_encs, axis=0)
    v_left     = np.mean(left_encs, axis=0)
    v_right    = np.mean(right_encs, axis=0)
    
    # Condense to one master 128D array and convert to JSON-serializable list
    final_baseline = np.mean([v_straight, v_left, v_right], axis=0).tolist()
    
    # 1. Convert the embedding to a 32-bit float numpy array (for exact byte consistency)
    vector_array = np.array(final_baseline, dtype=np.float32)

    # 2. Generate the SHA-256 Fingerprint from the raw bytes
    fingerprint = hashlib.sha256(vector_array.tobytes()).hexdigest()

    print(f"\n🔒 Biometric Fingerprint Generated: {fingerprint[:15]}...")

    # 3. Add it to the payload
    payload = {
        "student_id": student_id,
        "full_name": "New Enrollment", 
        "baseline_vector": final_baseline,
        "biometric_hash": fingerprint
    }

    print("☁️ Encrypting and transmitting biometric baseline to the cloud...")
    try:
        response = requests.post("https://ztap-cloud-dashboard.onrender.com/register", json=payload, timeout=10)
        
        if response.status_code == 200:
            print("✅ Student successfully registered in the Zero-Trust cloud ledger.")
        else:
            try:
                # Try to parse the JSON error message
                print(f"🚨 Registration failed: {response.json()}")
            except:
                # 🛡️ FIX: If the server returns HTML instead of JSON, catch it here!
                print(f"🚨 API Error (Code {response.status_code}): Server crashed. Check app_engine.py terminal!")
                
    except Exception as e:
        print(f"🚨 API Connection Error. Is app_engine.py running? Error: {e}")
else:
    print("Enrollment canceled or failed.")