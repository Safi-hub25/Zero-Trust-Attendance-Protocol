import os
import glob

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Find all files that look like face_ZT-XXXX.npy
search_pattern = os.path.join(BASE_DIR, "face_*.npy")
old_files = glob.glob(search_pattern)

if not old_files:
    print("✨ No old biometric data files found. Your workspace is already clean!")
else:
    print(f"🧹 Found {len(old_files)} old biometric file(s). Deleting...")
    for file_path in old_files:
        try:
            os.remove(file_path)
            print(f"✅ Successfully deleted: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"❌ Could not delete {os.path.basename(file_path)}. Error: {e}")
            
    print("\n🎉 Cleanup complete! You can now launch the app and re-register your face with the new True 3D geometry engine.")