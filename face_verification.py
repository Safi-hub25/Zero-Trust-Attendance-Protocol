import cv2
import mediapipe as mp
import numpy as np
import time
import math
import sys
import os
import sqlite3
import logging
from ultralytics import YOLO
from datetime import datetime
from deepface import DeepFace
import csv 
import requests

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
logging.getLogger("deepface").setLevel(logging.ERROR)

# ==========================================
# --- TESTING CONFIGURATION (CHAPTER 5) ---
# ==========================================
TEST_SCENARIO = "Genuine_Optimal" 
cloud_latency_ms = 0.0  

def log_chaos_test(scenario, result, total_lat, yolo_lat, df_lat, cloud_lat):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(BASE_DIR, "testing_metrics.csv")
    file_exists = os.path.isfile(file_path)
    
    with open(file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Timestamp", "Scenario", "Result", "Total_ms", "YOLO_ms", "DeepFace_ms", "Cloud_ms"])
        writer.writerow([datetime.now().strftime("%H:%M:%S"), scenario, result, 
                         round(total_lat, 2), round(yolo_lat, 2), round(df_lat, 2), round(cloud_lat, 2)])
    print(f"\n📊 [TEST LOGGED TO CSV] Scenario: {scenario} | Result: {result}")

# ==========================================
# --- CLOUD API CONFIGURATION ---
# ==========================================
def push_telemetry(student_id, latency_ms, result):
    global cloud_latency_ms
    try:
        start_cloud = time.time()  
        requests.post("https://ztap-cloud-dashboard.onrender.com/log_telemetry", json={
            "student_id": student_id,
            "latency_ms": int(latency_ms),
            "result": result
        }, timeout=5)
        cloud_latency_ms = (time.time() - start_cloud) * 1000  
    except Exception as e: 
        print(f"📊 Telemetry Error: {e}")

def push_attendance_to_cloud(student_id, course_code, local_timestamp, score):
    print(f"\n☁️ Syncing audit data (Match Distance: {score:.4f}) to cloud via API...")
    try:
        if course_code == "Test Class" or course_code == "TEST_ENV":
            course_code = "CSE4000"
            
        requests.post("https://ztap-cloud-dashboard.onrender.com/log_attendance", json={
            "student_id": student_id,
            "course_code": course_code,
            "timestamp": local_timestamp,
            "score": float(score)
        }, timeout=5)
    except Exception as e: 
        print(f"❌ Cloud Error: {e}")

# ==========================================
# --- LOCAL DATABASE & MODELS ---
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "mdx_system.db") 
MODEL_PATH = os.path.join(BASE_DIR, "models", "best.pt")

ai_model = YOLO(MODEL_PATH)
mp_face_mesh = mp.solutions.face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.7)

GLOBAL_TIMEOUT_SEC = 45  

def calculate_ear(landmarks, indices):
    v_dist = math.dist([landmarks[indices[2]].x, landmarks[indices[2]].y], [landmarks[indices[3]].x, landmarks[indices[3]].y])
    h_dist = math.dist([landmarks[indices[0]].x, landmarks[indices[0]].y], [landmarks[indices[1]].x, landmarks[indices[1]].y])
    return v_dist / h_dist if h_dist != 0 else 0.0

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

def verify_face(current_student_id, target_course="TEST_ENV"):
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    ACCENT_RED  = (50, 50, 235)
    ACCENT_GRN  = (65, 255, 0)
    ACCENT_BLU  = (255, 150, 50)
    PANEL_BG    = (25, 15, 10)  
    TEXT_MUTED  = (150, 150, 150)
    TEXT_WHITE  = (255, 255, 255)
    SURFACE     = (47, 25, 10)

    LEFT_EYE, RIGHT_EYE = [362, 263, 386, 374], [33, 133, 159, 145]

    stage = "SCANNING"
    auth_start_time = None
    pose_hold_start = None
    stage_timer_start = None  
    error_hold_start = None 
    last_error_msg = ""
    
    captured_scores = []
    session_logged = False
    status_msg = "AWAITING SUBJECT ALIGNMENT..."
    box_color = ACCENT_RED
    env_warning = ""
    eye_was_closed = False

    current_yolo_latency = 0.0
    current_df_latency = 0.0
    frame_counter = 0
    is_spoof = False 
    
    ai_label = "Scanning"
    ai_conf = 0.0

    def draw_corner_brackets(img, xmin, ymin, xmax, ymax, color, length=25, thickness=2):
        cv2.line(img, (xmin, ymin), (xmin + length, ymin), color, thickness)
        cv2.line(img, (xmin, ymin), (xmin, ymin + length), color, thickness)
        cv2.line(img, (xmax, ymin), (xmax - length, ymin), color, thickness)
        cv2.line(img, (xmax, ymin), (xmax, ymin + length), color, thickness)
        cv2.line(img, (xmin, ymax), (xmin + length, ymax), color, thickness)
        cv2.line(img, (xmin, ymax), (xmin, ymax - length), color, thickness)
        cv2.line(img, (xmax, ymax), (xmax - length, ymax), color, thickness)
        cv2.line(img, (xmax, ymax), (xmax, ymax - length), color, thickness)

    print(f"\n▶️ Starting Zero-Trust Validation for {current_student_id}")

    while True:
        ret, frame = cap.read()
        if not ret: break
        
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        curr_time = time.time()
        progress_val = 0.1

        if auth_start_time and (curr_time - auth_start_time > GLOBAL_TIMEOUT_SEC) and stage not in ["VERIFIED", "SPOOF_BLOCKED"]:
            push_telemetry(current_student_id, (curr_time - auth_start_time)*1000, "FALSE_REJECT")
            total_time_ms = (curr_time - auth_start_time) * 1000
            log_chaos_test(TEST_SCENARIO, "FALSE_REJECT", total_time_ms, current_yolo_latency, current_df_latency, 0)
            break

        mesh_res = mp_face_mesh.process(rgb_frame)
        if mesh_res.multi_face_landmarks:
            if not auth_start_time: auth_start_time = curr_time
            
            landmarks = mesh_res.multi_face_landmarks[0].landmark
            for lm in landmarks:
                cx, cy = int(lm.x * w), int(lm.y * h)
                cv2.circle(frame, (cx, cy), 1, (220, 220, 220), -1)

            xs = [int(l.x * w) for l in landmarks]
            ys = [int(l.y * h) for l in landmarks]
            xmin, xmax, ymin, ymax = max(0, min(xs)), min(w, max(xs)), max(0, min(ys)), min(h, max(ys))

            gray = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2GRAY)
            mean_lighting = np.mean(gray)
            if mean_lighting > 190: env_warning = "ERROR: EXTREME GLARE / TOO BRIGHT"
            elif mean_lighting < 40: env_warning = "ERROR: ENVIRONMENT TOO DARK"
            else: env_warning = ""

            frame_counter += 1
            if frame_counter % 5 == 0 and stage != "SPOOF_BLOCKED":
                start_yolo = time.time() 
                res_yolo = ai_model(cv2.resize(frame, (320, 320)), stream=True, verbose=False)
                
                ai_label, ai_conf = "Scanning", 0.0
                for r in res_yolo:
                    if r.probs:
                        ai_label = ai_model.names[r.probs.top1]
                        ai_conf = r.probs.top1conf.item()
                        if ai_label == "Fake" and ai_conf > 0.65:
                            is_spoof = True
                current_yolo_latency = (time.time() - start_yolo) * 1000 

            yaw = get_yaw(landmarks, w, h)
            ear = (calculate_ear(landmarks, LEFT_EYE) + calculate_ear(landmarks, RIGHT_EYE)) / 2.0

            if is_spoof:
                stage = "SPOOF_BLOCKED"
                box_color = ACCENT_RED
                status_msg = "SPOOF DETECTED: CONNECTION SEVERED"
                progress_val = 1.0
                
                if not session_logged:
                    latency = (curr_time - auth_start_time) * 1000
                    push_telemetry(current_student_id, latency, "TRUE_REJECT")
                    log_chaos_test(TEST_SCENARIO, "TRUE_REJECT", latency, current_yolo_latency, 0.0, cloud_latency_ms)
                    session_logged = True
                    pose_hold_start = curr_time
                    
                if pose_hold_start and (time.time() - pose_hold_start > 2.0): break
            else:
                if stage == "SCANNING":
                    stage = "CHECK_STRAIGHT"
                    box_color = ACCENT_BLU
                    progress_val = 0.2

                elif stage == "CHECK_STRAIGHT":
                    progress_val = 0.2
                    if -15.0 <= yaw <= 15.0:
                        if stage_timer_start is None: stage_timer_start = curr_time
                        elapsed = curr_time - stage_timer_start
                        status_msg = f"LIVENESS 1/4: HOLD STRAIGHT ({max(0, 5.0 - elapsed):.1f}s)"
                        box_color = ACCENT_BLU

                        if elapsed >= 5.0:
                            status_msg = "EXTRACTING VECTOR MATRIX..."
                            try:
                                start_df = time.time() 
                                rep = DeepFace.represent(rgb_frame, model_name="Facenet", enforce_detection=False)[0]["embedding"]
                                current_df_latency = (time.time() - start_df) * 1000 
                                
                                # 🛡️ CLOUD VALIDATION (ZERO-TRUST) 🛡️
                                payload = {
                                    "student_id": current_student_id,
                                    "live_vector": rep
                                }
                                response = requests.post("https://ztap-cloud-dashboard.onrender.com/authenticate", json=payload, timeout=5)
                                print(f"📡 Sending payload to Cloud... Status Code: {response.status_code}")
                                print(f"☁️ Cloud Response: {response.text}")
                                
                                if response.status_code == 200:
                                    current_score = response.json().get('score', 0)
                                    captured_scores.append(current_score)
                                    stage = "LIVENESS_BLINK"
                                    stage_timer_start = None
                                    box_color = ACCENT_BLU
                                elif response.status_code == 403:
                                    current_score = response.json().get('score', 1.0)
                                    stage = "MATCH_ERROR"
                                    error_hold_start = curr_time
                                    last_error_msg = f"CLOUD REJECT: ({current_score:.2f} > 0.25)"
                                    box_color = ACCENT_RED
                                else:
                                    stage = "MATCH_ERROR"
                                    error_hold_start = curr_time
                                    last_error_msg = "USER NOT FOUND OR API ERROR"
                                    box_color = ACCENT_RED
                                    
                            except Exception as e:
                                stage = "MATCH_ERROR"
                                error_hold_start = curr_time
                                last_error_msg = "API CONNECTION FAILED"
                                box_color = ACCENT_RED
                    else:
                        stage_timer_start = None
                        status_msg = "ALIGN FACE IN FRAME (LOOK STRAIGHT)"
                        box_color = ACCENT_RED
                
                elif stage == "MATCH_ERROR":
                    status_msg = last_error_msg
                    box_color = ACCENT_RED
                    progress_val = 0.2
                    if curr_time - error_hold_start > 2.0:
                        stage = "SCANNING"
                        stage_timer_start = None

                elif stage == "LIVENESS_BLINK":
                    status_msg = "LIVENESS 2/4: BLINK TO CONFIRM"
                    progress_val = 0.4
                    box_color = SURFACE
                    if ear < 0.2: eye_was_closed = True
                    if eye_was_closed and ear > 0.25: 
                        stage, eye_was_closed = "LIVENESS_LEFT", False
                        stage_timer_start = None

                elif stage == "LIVENESS_LEFT":
                    progress_val = 0.6
                    if yaw > 15.0:
                        if stage_timer_start is None: stage_timer_start = curr_time
                        elapsed = curr_time - stage_timer_start
                        status_msg = f"LIVENESS 3/4: HOLD LEFT ({max(0, 5.0 - elapsed):.1f}s)"
                        box_color = ACCENT_GRN
                        if elapsed >= 5.0:
                            stage = "LIVENESS_RIGHT"
                            stage_timer_start = None
                    else:
                        stage_timer_start = None
                        status_msg = "LIVENESS 3/4: TURN HEAD LEFT"
                        box_color = SURFACE

                elif stage == "LIVENESS_RIGHT":
                    progress_val = 0.8
                    if yaw < -15.0:
                        if stage_timer_start is None: stage_timer_start = curr_time
                        elapsed = curr_time - stage_timer_start
                        status_msg = f"LIVENESS 4/4: HOLD RIGHT ({max(0, 5.0 - elapsed):.1f}s)"
                        box_color = ACCENT_GRN
                        if elapsed >= 5.0:
                            stage = "VERIFIED"
                            pose_hold_start = curr_time
                            box_color = ACCENT_GRN
                    else:
                        stage_timer_start = None
                        status_msg = "LIVENESS 4/4: TURN HEAD RIGHT"
                        box_color = SURFACE

                elif stage == "VERIFIED":
                    status_msg = "ATTENDANCE SECURED"
                    progress_val = 1.0
                    box_color = ACCENT_GRN
                    if not session_logged:
                        latency = (curr_time - auth_start_time) * 1000
                        avg_score = sum(captured_scores) / len(captured_scores) if captured_scores else 0.0
                        now = datetime.now()
                        
                        try:
                            conn = sqlite3.connect(DB_PATH)
                            cur = conn.cursor()
                            cur.execute("INSERT INTO attendance (student_id, date, time, status, photo) VALUES (?, ?, ?, ?, ?)", 
                                       (current_student_id, now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'), 'Present', 'SECURED'))
                            conn.commit(); conn.close()
                        except: pass
                        
                        push_telemetry(current_student_id, latency, "SUCCESS")
                        push_attendance_to_cloud(current_student_id, target_course, now.strftime('%Y-%m-%d %H:%M:%S'), avg_score)
                        session_logged = True
                        log_chaos_test(TEST_SCENARIO, "SUCCESS", latency, current_yolo_latency, current_df_latency, cloud_latency_ms)
                        
                    if time.time() - pose_hold_start > 2.0: break

            draw_corner_brackets(frame, xmin-20, ymin-20, xmax+20, ymax+20, box_color)

        cv2.rectangle(frame, (0, 0), (w, 75), PANEL_BG, -1)
        cv2.putText(frame, "Z-TAP :: SECURE VERIFICATION", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, ACCENT_RED, 2)
        yolo_str = f"| AI: {ai_label} ({int(ai_conf*100)}%)" if ai_conf > 0 else "| AI: Initializing..."
        cv2.putText(frame, f"TARGET NODE: {current_student_id} {yolo_str}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_MUTED, 1)

        cv2.rectangle(frame, (0, h - 110), (w, h), PANEL_BG, -1)
        
        if env_warning and stage not in ["VERIFIED", "SPOOF_BLOCKED"]:
            cv2.putText(frame, env_warning, (20, h - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, ACCENT_RED, 2)
        else:
            txt_color = ACCENT_RED if "SPOOF" in status_msg else ACCENT_GRN if stage == "VERIFIED" else TEXT_WHITE
            cv2.putText(frame, status_msg, (20, h - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, txt_color, 2)

        bar_w = w - 40
        cv2.rectangle(frame, (20, h - 45), (20 + bar_w, h - 30), TEXT_MUTED, 1) 
        bar_color = ACCENT_RED if stage == "SPOOF_BLOCKED" else ACCENT_GRN if stage == "VERIFIED" else ACCENT_BLU
        if progress_val > 0:
            cv2.rectangle(frame, (20, h - 45), (20 + int(bar_w * progress_val), h - 30), bar_color, -1) 

        cv2.imshow('Z-TAP :: EDGE VALIDATION TERMINAL', frame)
        if cv2.waitKey(1) & 0xFF == 27: break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    if len(sys.argv) > 2:
        verify_face(sys.argv[1], sys.argv[2])
    elif len(sys.argv) > 1:
        verify_face(sys.argv[1])
    else:
        print("Usage: python face_verification.py <student_id> [course_name]")