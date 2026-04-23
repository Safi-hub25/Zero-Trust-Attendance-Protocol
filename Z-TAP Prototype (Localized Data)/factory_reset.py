import os
import sqlite3
import hashlib
import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_DB = os.path.join(BASE_DIR, "mdx_system.db")

print("🚨 INITIATING TOTAL FACTORY RESET 🚨\n")

# --- 1. DELETE OLD BIOMETRICS ---
old_npy_files = glob.glob(os.path.join(BASE_DIR, "face_*.npy"))
for f in old_npy_files:
    try:
        os.remove(f)
        print(f"🗑️ Deleted biometric: {os.path.basename(f)}")
    except: pass

# --- 2. DELETE LOCKED DATABASE ---
if os.path.exists(SQL_DB):
    try:
        os.remove(SQL_DB)
        print("💥 Vaporized old locked database!")
    except Exception as e:
        print(f"❌ ERROR: Cannot delete database. A Python script is still running in the background! Please restart VS Code or your computer. Error: {e}")
        exit()

# --- 3. BUILD FRESH DATABASE ---
print("🏗️ Building fresh, secure database...")
conn = sqlite3.connect(SQL_DB)
cursor = conn.cursor()

# Create Tables
cursor.execute('''CREATE TABLE users (student_id TEXT PRIMARY KEY, name TEXT, dob TEXT, course TEXT, password TEXT, registered_at TEXT)''')
cursor.execute('''CREATE TABLE attendance (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, date TEXT, time TEXT, status TEXT, photo TEXT)''')
cursor.execute('''CREATE TABLE timetables (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, name TEXT, type TEXT, start TEXT, end TEXT)''')
cursor.execute('''CREATE TABLE admins (username TEXT PRIMARY KEY, password TEXT)''')

# Create Default Admin
admin_pass = hashlib.sha256("1234".encode()).hexdigest()
cursor.execute("INSERT INTO admins (username, password) VALUES (?, ?)", ("supervisor", admin_pass))

conn.commit()
conn.close()

print("\n✨ RESET COMPLETE! Your system is now 100% clean and ready for fresh testing.")