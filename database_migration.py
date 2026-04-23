import sqlite3
import json
import csv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_DB = os.path.join(BASE_DIR, "mdx_system.db")

print("⚙️ Initializing SQLite Database Migration...")

# 1. Connect to SQLite (This creates the file if it doesn't exist)
conn = sqlite3.connect(SQL_DB)
cursor = conn.cursor()

# 2. Create the Tables
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    student_id TEXT PRIMARY KEY,
    name TEXT,
    dob TEXT,
    course TEXT,
    password TEXT,
    registered_at TEXT
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    date TEXT,
    time TEXT,
    status TEXT,
    photo TEXT
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS timetables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    name TEXT,
    type TEXT,
    start TEXT,
    end TEXT
)''')

# 3. Migrate Users (from users_db.json)
if os.path.exists("users_db.json"):
    with open("users_db.json", "r") as f:
        try:
            users = json.load(f)
            for sid, data in users.items():
                cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?, ?)", 
                            (sid, data.get("name"), data.get("dob"), data.get("course"), data.get("password"), data.get("registered_at")))
            print("✅ Users successfully migrated to SQL.")
        except json.JSONDecodeError:
            print("⚠️ Could not read users_db.json")

# 4. Migrate Attendance (from attendance_log.csv)
if os.path.exists("attendance_log.csv"):
    with open("attendance_log.csv", "r") as f:
        reader = csv.reader(f)
        next(reader, None) # Skip headers
        for row in reader:
            if len(row) >= 4:
                photo = row[4] if len(row) >= 5 else "No Photo"
                cursor.execute("INSERT INTO attendance (student_id, date, time, status, photo) VALUES (?, ?, ?, ?, ?)", 
                               (row[0], row[1], row[2], row[3], photo))
    print("✅ Attendance logs successfully migrated to SQL.")

# 5. Migrate Timetables (from timetables.json)
if os.path.exists("timetables.json"):
    with open("timetables.json", "r") as f:
        try:
            tt = json.load(f)
            for date_str, classes in tt.items():
                if isinstance(classes, list):
                    for cls in classes:
                        cursor.execute("INSERT INTO timetables (date, name, type, start, end) VALUES (?, ?, ?, ?, ?)", 
                                       (date_str, cls.get("name"), cls.get("type", "Seminar"), cls.get("start"), cls.get("end")))
            print("✅ Timetables successfully migrated to SQL.")
        except json.JSONDecodeError:
            print("⚠️ Could not read timetables.json")

# 6. Save and Close
conn.commit()
conn.close()
print("🎉 Migration Complete! You are now running on SQLite.")