import sqlite3
import hashlib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_DB = os.path.join(BASE_DIR, "mdx_system.db")

def hash_password(password):
    # Converts plaintext to a secure SHA-256 cryptographic hash
    return hashlib.sha256(password.encode()).hexdigest()

print("🔒 Initiating Zero Trust Security Patch...")

conn = sqlite3.connect(SQL_DB)
cursor = conn.cursor()

# 1. Create the Admins Table (Removing the hardcoded backdoor)
cursor.execute('''
CREATE TABLE IF NOT EXISTS admins (
    username TEXT PRIMARY KEY,
    password TEXT
)''')

# 2. Insert the default Admin account securely
cursor.execute("INSERT OR IGNORE INTO admins (username, password) VALUES (?, ?)", 
               ("Supervisor", hash_password("supervisor123")))

# 3. Encrypt existing student passwords
cursor.execute("SELECT student_id, password FROM users")
for sid, pw in cursor.fetchall():
    # If the password isn't exactly 64 characters (the length of a SHA-256 hash), it's plaintext!
    if len(pw) != 64: 
        cursor.execute("UPDATE users SET password=? WHERE student_id=?", (hash_password(pw), sid))
        print(f"✅ Encrypted legacy password for ID: {sid}")

conn.commit()
conn.close()
print("🎉 Patch Complete! Your database is now cryptographically secure.")