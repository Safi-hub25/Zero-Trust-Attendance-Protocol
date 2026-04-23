import requests
import time
from datetime import datetime

API_URL = "https://ztap-cloud-dashboard.onrender.com/log_attendance" 

def test_cloud_handshake(score_value, test_name):
    print(f"--- Running: {test_name} ---")
    
    # 1. Package the Zero-Trust Payload (matching app_engine.py requirements)
    payload = {
        "student_id": "ZT-2000",
        "course_code": "CSE4000",
        "score": score_value,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    print(f"[EDGE NODE]  Transmitting Payload: Score={score_value}")
    start_time = time.time()

    try:
        # 2. Fire the POST request to the API
        response = requests.post(API_URL, json=payload, timeout=5)
        latency = (time.time() - start_time) * 1000 # Calculate ping in milliseconds

        # 3. Read the Cloud's Response
        print(f"[CLOUD API]  Status Received: HTTP {response.status_code}")
        print(f"[CLOUD API]  Response Data: {response.json()}")
        print(f"[TELEMETRY]  End-to-End Latency: {latency:.2f} ms")

        if response.status_code == 200:
            print("INTEGRATION SUCCESS: Decoupled communication verified.\n")
        else:
            print("INTEGRATION FAILED: Unexpected server response.\n")

    except requests.exceptions.ConnectionError:
        print("INTEGRATION FAILED: Could not reach the cloud. Is the Flask API running?\n")

# --- Execute the Live Network Tests ---
if __name__ == "__main__":
    # Test 1: Simulating a highly accurate face scan
    test_cloud_handshake(0.12, "TC-INT-01: Valid Biometric Payload Handshake")
    
    # Test 2: Simulating an active spoofing attempt sending a bad score
    test_cloud_handshake(0.48, "TC-INT-02: Spoof Payload Handshake (Testing DB Overwrite)")










    