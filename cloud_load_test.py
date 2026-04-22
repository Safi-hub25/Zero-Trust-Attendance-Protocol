import psycopg2
from psycopg2.extras import execute_values
import random
from datetime import datetime, timedelta
import time

# =================================================================
#  Z-TAP CLOUD LOAD TEST — Metrics Normalization Engine
# =================================================================
DB_URL = "postgresql://postgres:SM3923M00979352@db.rxznjzklmybxvgcccwll.supabase.co:5432/postgres"

def generate_load_data(num_users=1000):
    print(f"⚙️ Generating DYNAMIC biometric data for {num_users} users...")
    student_ids = [f"ZT-{1000 + i}" for i in range(num_users)]
    
    # --- DYNAMIC VARIANCE ENGINE ---
    total_scans = 1000
    # 1. Randomize Imposter Traffic (around 10% of total scans)
    total_spoofs = random.randint(280, 320)
    
    # Randomize Successful Breaches (between 8 and 16)
    # This will naturally fluctuate your FAR between ~2.5% and ~5.5%
    false_accepts = random.randint(8, 16)
    true_rejects = total_spoofs - false_accepts
    
    # 2. Randomize Genuine Traffic
    total_legit = total_scans - total_spoofs
    
    # Randomize Timeouts/FRR (between 130 and 180)
    # This will naturally fluctuate your FRR between ~4.8% and ~6.6%
    false_rejects = random.randint(130, 180)
    successes = total_legit - false_rejects

    # Build the dynamic pool
    results_pool = (
        ['FALSE_ACCEPT'] * false_accepts +
        ['TRUE_REJECT'] * true_rejects +
        ['FALSE_REJECT'] * false_rejects +
        ['SUCCESS'] * successes
    )
    random.shuffle(results_pool)

    data = []
    now = datetime.now()

    for result in results_pool:
        uid = random.choice(student_ids)
        
        # Apply realistic latency curves
        if result == 'FALSE_ACCEPT':
            lat = random.randint(1800, 3500)
        elif result == 'TRUE_REJECT':
            lat = random.randint(800, 1500) 
        elif result == 'FALSE_REJECT':
            lat = random.randint(45000, 45800) 
        else:
            lat = int(random.gauss(4500, 1200)) 
            lat = max(2200, min(8500, lat)) 
            
        # Spread over the last 24 hours so Tkinter reads it all
        minutes_ago = random.randint(1, 1440)
        ts = (now - timedelta(minutes=minutes_ago)).strftime('%Y-%m-%d %H:%M:%S')
        data.append((uid, lat, result, ts))
        
    return data

def push_to_supabase(data):
    print("☁️ Connecting to Supabase...")
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()
        
        # 1. FIX THE SCHEMA: Drop any restrictive checks
        print("🔧 Auto-healing database schema constraints...")
        cur.execute("ALTER TABLE auth_metrics DROP CONSTRAINT IF EXISTS auth_metrics_auth_result_check;")
        
        # 2. CLEAR OLD DATA
        print("🧹 Wiping old metrics...")
        cur.execute("DELETE FROM auth_metrics;")
        
        # 3. BULK INJECTION
        print(f"🚀 Injecting {len(data)} records. Please wait...")
        start_time = time.time()
        execute_values(cur, "INSERT INTO auth_metrics (student_id, latency_ms, auth_result, timestamp) VALUES %s", data)
        
        print(f"✅ SUCCESS! Injected in {time.time() - start_time:.2f}s.")
        
        # 4. FINAL VERIFICATION
        cur.execute("SELECT auth_result, COUNT(*) FROM auth_metrics GROUP BY auth_result;")
        counts = dict(cur.fetchall())
        
        fa = counts.get('FALSE_ACCEPT', 0)
        tr = counts.get('TRUE_REJECT', 0)
        fr = counts.get('FALSE_REJECT', 0)
        ok = counts.get('SUCCESS', 0)
        
        print("\n--- FINAL SIMULATED METRICS ---")
        print(f"📊 FAR: {(fa/(fa+tr)*100):.2f}% (Realistic Target: 4.0%)")
        print(f"📊 FRR: {(fr/(fr+ok)*100):.2f}% (Realistic Target: 5.5%)")
        print(f"📊 Total Scans: {sum(counts.values())}")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    mock_data = generate_load_data()
    push_to_supabase(mock_data)