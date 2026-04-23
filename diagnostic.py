import psycopg2

DB_URL = "postgresql://postgres:dD52CkDPZB7QVtCN@db.rxznjzklmybxvgcccwll.supabase.co:5432/postgres"

def run_diagnostics():
    print("🔍 RUNNING DATABASE X-RAY...\n")
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Test 1: What is in the database ALL TIME?
        cur.execute("SELECT auth_result, COUNT(*) FROM auth_metrics GROUP BY auth_result;")
        all_time = dict(cur.fetchall())
        print("📊 TEST 1: ALL-TIME RECORDS IN DATABASE")
        print(all_time)
        print("-" * 40)
        
        # Test 2: What is in the database for the LAST 24 HOURS? (This is what Tkinter uses)
        cur.execute("SELECT auth_result, COUNT(*) FROM auth_metrics WHERE timestamp >= NOW() - INTERVAL '24 HOURS' GROUP BY auth_result;")
        last_24h = dict(cur.fetchall())
        print("⏱️ TEST 2: RECORDS IN THE LAST 24 HOURS (Tkinter's View)")
        print(last_24h)
        print("-" * 40)

        # Test 3: The Math Test
        fa = last_24h.get('FALSE_ACCEPT', 0)
        tr = last_24h.get('TRUE_REJECT', 0)
        
        print(f"🧮 MATH CHECK:")
        print(f"False Accepts found: {fa}")
        print(f"True Rejects found:  {tr}")
        
        if (fa + tr) > 0:
            print(f"Calculated FAR: {(fa / (fa + tr) * 100):.2f}%")
        else:
            print("Calculated FAR: 0.00% (No imposter data found in last 24h)")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    run_diagnostics()