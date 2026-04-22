import os
from flask import Flask, jsonify, render_template, request
import psycopg2
from waitress import serve
from datetime import datetime, timedelta

# 1. Force Flask to look for the 'templates' folder locally
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'app_templates')
app = Flask(__name__, template_folder=TEMPLATE_DIR)

# --- CLOUD CONFIG ---
# Pulls from Render, but falls back to your local IPv4 URL if testing locally
DB_URL = os.environ.get('DATABASE_URL', "postgresql://postgres.rxznjzklmybxvgcccwll:SM3923M00979352@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres")

def get_db_connection():
    return psycopg2.connect(DB_URL)

# ==========================================
# 1. ADMIN WEB PORTAL ROUTE
# ==========================================
@app.route('/')
def admin_dashboard():
    return render_template('admin_dashboard.html')

# ==========================================
# 2. FETCH LIVE ATTENDANCE (API for Dashboard)
# ==========================================
@app.route('/api/admin/attendance', methods=['GET'])
def get_admin_attendance():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = """
            SELECT a.timestamp, a.student_id, COALESCE(u.full_name, 'UNKNOWN_USER'), a.course_code, a.status, a.auth_score 
            FROM attendance a
            LEFT JOIN users u ON a.student_id = u.user_id
            ORDER BY a.timestamp DESC
            LIMIT 50;
        """
        cur.execute(query)
        records = cur.fetchall()

        attendance_list = []
        for row in records:
            time_val = row[0]
            try:
                time_str = time_val.strftime("%Y-%m-%d %H:%M:%S") if time_val else "Unknown"
            except:
                time_str = str(time_val)

            attendance_list.append({
                "time": time_str,
                "student_id": row[1],
                "name": row[2],
                "course": row[3],
                "status": row[4],
                "auth_score": float(row[5]) if row[5] is not None else 'null' 
            })

        return jsonify({"status": "success", "data": attendance_list}), 200

    except Exception as e:
        print(f"🚨 DB Error (/api/admin/attendance): {e}")
        return jsonify({"status": "error", "message": "Failed to fetch attendance data."}), 500
        
    finally:
        if cur: cur.close()
        if conn: conn.close()

# ==========================================
# 3. UPDATE ATTENDANCE STATUS
# ==========================================
@app.route('/api/admin/update_attendance', methods=['POST'])
def update_attendance():
    data = request.json
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE attendance 
            SET status = %s 
            WHERE student_id = %s AND timestamp = %s::TIMESTAMP
        """, (data['status'], data['student_id'], data['timestamp']))
        
        conn.commit()
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        print(f"🚨 DB Error (/api/admin/update_attendance): {e}")
        return jsonify({"status": "error", "message": "Failed to update record."}), 500
        
    finally:
        if cur: cur.close()
        if conn: conn.close()

# ==========================================
# 3.5. FLAG SECURITY BREACH (Update FAR)
# ==========================================
@app.route('/api/admin/flag_imposter', methods=['POST'])
def flag_imposter():
    data = request.json
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE attendance 
            SET status = 'Rejected' 
            WHERE student_id = %s AND timestamp = %s::TIMESTAMP
        """, (data['student_id'], data['timestamp']))
        
        cur.execute("""
            UPDATE auth_metrics 
            SET auth_result = 'FALSE_ACCEPT' 
            WHERE student_id = %s AND auth_result = 'SUCCESS'
            AND timestamp >= %s::TIMESTAMP - INTERVAL '1 MINUTE'
            AND timestamp <= %s::TIMESTAMP + INTERVAL '1 MINUTE'
        """, (data['student_id'], data['timestamp'], data['timestamp']))
        
        conn.commit()
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        print(f"🚨 DB Error (/api/admin/flag_imposter): {e}")
        return jsonify({"status": "error", "message": "Failed to flag imposter."}), 500
        
    finally:
        if cur: cur.close()
        if conn: conn.close()
    
# ==========================================
# 4. TIMETABLE API & DIRECTORY & METRICS
# ==========================================
@app.route('/api/admin/timetables', methods=['GET'])
def get_timetables():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, date_str, name, session_type, start_time, end_time, course_code FROM timetables")
        records = cur.fetchall()
        
        classes = [{"id": r[0], "date": r[1], "name": r[2], "type": r[3], "start": r[4], "end": r[5], "course": r[6]} for r in records]
        return jsonify({"status": "success", "data": classes}), 200
    except Exception: return jsonify({"status": "error"}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/api/admin/add_class', methods=['POST'])
def add_class():
    data = request.json
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        base_date = datetime.strptime(data['date'], "%d/%m/%Y")
        weeks_to_repeat = int(data.get('weeks', 1))
        
        for i in range(weeks_to_repeat):
            target_date = base_date + timedelta(days=7 * i)
            date_string = target_date.strftime("%d/%m/%Y")
            cur.execute(
                "INSERT INTO timetables (date_str, name, session_type, start_time, end_time, course_code) VALUES (%s, %s, %s, %s, %s, %s)",
                (date_string, data['name'], data['type'], data['start'], data['end'], data['course'])
            )
        conn.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e: 
        print(f"🚨 ADD CLASS ERROR: {e}")
        return jsonify({"status": "error"}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/api/admin/delete_class/<int:class_id>', methods=['DELETE'])
def delete_class(class_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM timetables WHERE id = %s", (class_id,))
        conn.commit()
        return jsonify({"status": "success"}), 200
    except Exception: return jsonify({"status": "error"}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/api/admin/students', methods=['GET'])
def get_admin_students():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id, full_name, bio_status FROM users WHERE role = 'student'")
        records = cur.fetchall()
        student_list = [{"id": r[0], "name": r[1], "bio_status": r[2]} for r in records]
        return jsonify({"status": "success", "data": student_list}), 200
    except Exception: return jsonify({"status": "error"}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/api/admin/metrics', methods=['GET'])
def get_system_metrics():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT auth_result, COUNT(*) 
            FROM auth_metrics 
            WHERE timestamp >= NOW() - INTERVAL '24 HOURS'
            GROUP BY auth_result
        """)
        counts = dict(cur.fetchall())
        
        success = counts.get('SUCCESS', 0)
        false_reject = counts.get('FALSE_REJECT', 0)
        false_accept = counts.get('FALSE_ACCEPT', 0)
        true_reject = counts.get('TRUE_REJECT', 0)
        
        total_scans = sum(counts.values())

        cur.execute("""
            SELECT AVG(latency_ms) 
            FROM auth_metrics 
            WHERE auth_result = 'SUCCESS' AND timestamp >= NOW() - INTERVAL '24 HOURS'
        """)
        avg_latency_row = cur.fetchone()
        avg_latency = (float(avg_latency_row[0]) / 1000.0) if avg_latency_row[0] else 0.0

        cur.execute("""
            SELECT latency_ms 
            FROM auth_metrics 
            WHERE auth_result = 'SUCCESS'
            ORDER BY timestamp DESC 
            LIMIT 50
        """)
        history = [r[0] for r in cur.fetchall()]
        history.reverse()

        valid_attempts = success + false_reject
        frr = (false_reject / valid_attempts) * 100 if valid_attempts > 0 else 0.0
        
        imposter_attempts = false_accept + true_reject
        far = (false_accept / imposter_attempts) * 100 if imposter_attempts > 0 else 0.0

        return jsonify({
            "status": "success",
            "data": {
                "avg_latency": round(avg_latency, 2),
                "frr": round(frr, 1),
                "far": round(far, 1),
                "total_scans": total_scans,
                "latency_history": history
            }
        }), 200
    except Exception: return jsonify({"status": "error"}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

# ==========================================
# 5. ZERO-TRUST EDGE API PROTOCOLS
# ==========================================
@app.route('/register', methods=['POST'])
def register_student():
    """Cloud endpoint to securely enroll a new student's biometric vector and SHA-256 hash."""
    data = request.json
    conn = None  
    cur = None   
    
    try:
        student_id = data.get('student_id')
        full_name = data.get('full_name', 'New Enrollment')
        raw_vector = data.get('baseline_vector')
        
        # 🔒 EXTRACT THE FINGERPRINT FROM THE PAYLOAD
        biometric_hash = data.get('biometric_hash', 'NO_HASH_PROVIDED')

        # 🛡️ BULLETPROOF VECTOR FORMATTING
        vector_str = "[" + ",".join(str(x) for x in raw_vector) + "]"

        conn = get_db_connection()
        conn.autocommit = True
        cur = conn.cursor()

        # 💾 INSERT VECTOR AND HASH INTO SUPABASE
        cur.execute("""
            INSERT INTO users (user_id, full_name, password_hash, role, bio_status, face_baseline, biometric_hash)
            VALUES (%s, %s, 'PENDING_SETUP', 'student', 'Complete', %s::vector, %s)
            ON CONFLICT (user_id) DO UPDATE 
            SET face_baseline = EXCLUDED.face_baseline, 
                bio_status = 'Complete',
                biometric_hash = EXCLUDED.biometric_hash;
        """, (student_id, full_name, vector_str, biometric_hash))
        
        return jsonify({"status": "success", "message": "Biometric vector and cryptographic hash secured."}), 200

    except Exception as e:
        print(f"🚨 DB Error during registration: {e}")
        return jsonify({"status": "error", "message": "Database insertion failed."}), 500
        
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/authenticate', methods=['POST'])
def authenticate():
    """Validates the live vector against the pgvector baseline using Cosine Distance."""
    data = request.json
    try:
        student_id = data.get('student_id')
        live_vector = data.get('live_vector') 
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Natively calculates Cosine Distance in the cloud
        cur.execute("""
            SELECT (face_baseline <=> %s::vector) AS distance 
            FROM users 
            WHERE user_id = %s AND face_baseline IS NOT NULL
        """, (live_vector, student_id))
        
        result = cur.fetchone()
        
        if not result:
            return jsonify({"status": "error", "message": "User not found or no biometric baseline."}), 404
            
        distance = float(result[0])
        
        if distance > 0.25:
            print(f"🚨 CLOUD FAILSAFE TRIPPED for {student_id}! Distance: {distance:.4f} > 0.25")
            return jsonify({"status": "rejected", "message": "Zero-Trust Failsafe Tripped.", "score": distance}), 403
            
        print(f"✅ Access Granted for {student_id}. Distance: {distance:.4f}")
        return jsonify({"status": "success", "message": "Biometric verification accepted.", "score": distance}), 200

    except Exception as e:
        print(f"🚨 Auth Route Error: {e}")
        return jsonify({"status": "error", "message": "Authentication payload malformed."}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/log_telemetry', methods=['POST'])
def log_telemetry():
    data = request.json
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("INSERT INTO auth_metrics (student_id, latency_ms, auth_result) VALUES (%s, %s, %s)",
                    (data['student_id'], data['latency_ms'], data['result']))
        return jsonify({"status": "success"}), 200
    except Exception: return jsonify({"status": "error"}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/log_attendance', methods=['POST'])
def log_attendance():
    data = request.json
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cur = conn.cursor()
        student_id = data['student_id']
        course_code = data['course_code']
        score = data['score']
        timestamp = data['timestamp']
        
        if float(score) > 0.25:
            final_status = 'Rejected'
            cur.execute("""
                UPDATE auth_metrics SET auth_result = 'FALSE_ACCEPT' 
                WHERE student_id = %s AND auth_result = 'SUCCESS' 
                AND timestamp >= NOW() - INTERVAL '1 MINUTE'
            """, (student_id,))
        else:
            final_status = 'Present'

        cur.execute("INSERT INTO attendance (student_id, course_code, status, timestamp, auth_score) VALUES (%s, %s, %s, %s, %s)",
                        (student_id, course_code, final_status, timestamp, float(score)))
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"🚨 CLOUD SYNC ERROR: {e}") 
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

if __name__ == '__main__':
    # Grab Render's dynamic port, or use 5000 if testing locally
    port = int(os.environ.get('PORT', 5000))
    
    print(f"🚀 Z-TAP Cloud Server spinning up on port {port}...")
    serve(app, host='0.0.0.0', port=port)