import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import os
import sqlite3
import time
import re
import calendar
import hashlib
from datetime import datetime, timedelta

# Configs
APP_TITLE = "Middlesex University Dubai - Student Portal"
BG_COLOR = "#2C2658"       
ACCENT_COLOR = "#E84C3D"   

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SQL_DB = os.path.join(BASE_DIR, "mdx_system.db")
FILE_REGISTER_SCRIPT = "01_register_student.py"
FILE_ATTENDANCE_SCRIPT = "02_take_attendance.py"
FILE_ADMIN_DASHBOARD = "03_admin_dashboard.py" 

class MenuListItem(tk.Button):
    def __init__(self, parent, icon, text, command=None):
        super().__init__(
            parent, 
            text=f"   {icon}     {text}", 
            font=("Arial", 11, "bold"), 
            bg="white", 
            fg="#2C2658", 
            bd=0, 
            anchor="w", 
            padx=15, 
            pady=8, 
            cursor="hand2", 
            command=command
        )

# --- MAIN APPLICATION CLASS ---
class MDXApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("400x800")
        self.configure(bg=BG_COLOR)
        self.resizable(False, False)
        self.eval('tk::PlaceWindow . center')

        self.current_user = None
        self.current_user_id = None
        self.container = tk.Frame(self, bg=BG_COLOR)
        self.container.pack(fill="both", expand=True)
        
        self.tt_date = datetime.now()
        self.selected_date = datetime.now()

        self.show_login()

    def clear_screen(self):
        for widget in self.container.winfo_children(): widget.destroy()

    # --- SQL HELPERS ---
    def load_timetables(self):
        data = {}
        try:
            conn = sqlite3.connect(SQL_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT date, name, type, start, end FROM timetables")
            for row in cursor.fetchall():
                date_str, name, ctype, start, end = row
                if date_str not in data: data[date_str] = []
                data[date_str].append({"name": name, "type": ctype, "start": start, "end": end})
            conn.close()
        except: pass
        return data

    def get_attendance_status(self, check_date_obj, class_start_str, class_end_str):
        csv_date = check_date_obj.strftime('%Y-%m-%d')
        status = "Pending" 
        
        try:
            class_end_dt = datetime.strptime(f"{check_date_obj.strftime('%d/%m/%Y')} {class_end_str}", "%d/%m/%Y %H:%M")
            if datetime.now() > class_end_dt: status = "Absent" 
        except: pass

        try:
            conn = sqlite3.connect(SQL_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT time, status FROM attendance WHERE student_id=? AND date=?", (self.current_user_id, csv_date))
            
            for row in cursor.fetchall():
                log_time_str, db_status = row
                log_time = datetime.strptime(log_time_str, "%H:%M:%S").time()
                c_start = (datetime.strptime(class_start_str, "%H:%M") - timedelta(minutes=15)).time()
                c_end = datetime.strptime(class_end_str, "%H:%M").time()
                
                if c_start <= log_time <= c_end:
                    status = db_status 
                    break
            conn.close()
        except Exception as e: print(f"DB Error: {e}")

        return status

    # ==========================================
    # PAGE 1 & 1.5: LOGINS
    # ==========================================
    def show_login(self):
        self.clear_screen()
        self.configure(bg=BG_COLOR)
        self.container.configure(bg=BG_COLOR)
        
        tk.Label(self.container, text="\n🛡️", font=("Arial", 60), bg=BG_COLOR, fg="white").pack()
        tk.Label(self.container, text="Middlesex", font=("Helvetica", 24, "bold"), bg=BG_COLOR, fg="white").pack()
        tk.Label(self.container, text="University Dubai", font=("Helvetica", 14), bg=BG_COLOR, fg="#BDC3C7").pack()
        tk.Label(self.container, text="", bg=BG_COLOR).pack(pady=20)

        form_frame = tk.Frame(self.container, bg=BG_COLOR, padx=40)
        form_frame.pack(fill="x")

        tk.Label(form_frame, text="Student ID (ZT-XXXX)", font=("Arial", 10), bg=BG_COLOR, fg="white", anchor="w").pack(fill="x")
        self.entry_login_id = tk.Entry(form_frame, font=("Arial", 12), width=30)
        self.entry_login_id.pack(pady=5)

        tk.Label(form_frame, text="Password", font=("Arial", 10), bg=BG_COLOR, fg="white", anchor="w").pack(fill="x", pady=(10, 0))
        self.entry_login_pass = tk.Entry(form_frame, font=("Arial", 12), width=30, show="*")
        self.entry_login_pass.pack(pady=5)

        tk.Button(self.container, text="LOGIN", font=("Arial", 12, "bold"), bg=ACCENT_COLOR, fg="white", width=20, height=2, bd=0, cursor="hand2", command=self.perform_login).pack(pady=30)
        tk.Button(self.container, text="New Student? Register Here", font=("Arial", 10, "underline"), bg=BG_COLOR, fg="#BDC3C7", bd=0, cursor="hand2", command=self.show_register).pack()
        tk.Button(self.container, text="Staff Access", font=("Arial", 9), bg=BG_COLOR, fg="#7F8C8D", bd=0, cursor="hand2", command=self.show_staff_login).pack(side="bottom", pady=20)

    def perform_login(self):
        student_id = self.entry_login_id.get().strip()
        raw_password = self.entry_login_pass.get().strip()
        hashed_password = hashlib.sha256(raw_password.encode()).hexdigest()
        
        try:
            conn = sqlite3.connect(SQL_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT name, course FROM users WHERE student_id=? AND password=?", (student_id, hashed_password))
            result = cursor.fetchone()
            conn.close()

            if result:
                self.current_user = {"name": result[0], "course": result[1]}
                self.current_user_id = student_id 
                self.show_home()
            else: messagebox.showerror("Failed", "Invalid Student ID or Password")
        except sqlite3.OperationalError:
            messagebox.showerror("Error", "Database not found! Please run the DB migration script.")

    def show_staff_login(self):
        self.clear_screen()
        tk.Button(self.container, text="< Back to Student Login", bg=BG_COLOR, fg="white", bd=0, font=("Arial", 10), command=self.show_login, anchor="w").pack(fill="x", padx=20, pady=10)
        tk.Label(self.container, text="💼", font=("Arial", 50), bg=BG_COLOR, fg="white").pack(pady=(20,0))
        tk.Label(self.container, text="Staff Portal", font=("Helvetica", 20, "bold"), bg=BG_COLOR, fg="white").pack(pady=10)

        form_frame = tk.Frame(self.container, bg=BG_COLOR, padx=40)
        form_frame.pack(fill="x", pady=20)

        tk.Label(form_frame, text="Username", font=("Arial", 10), bg=BG_COLOR, fg="white", anchor="w").pack(fill="x")
        self.entry_staff_id = tk.Entry(form_frame, font=("Arial", 12))
        self.entry_staff_id.pack(fill="x", pady=5)

        tk.Label(form_frame, text="Password", font=("Arial", 10), bg=BG_COLOR, fg="white", anchor="w").pack(fill="x", pady=(10, 0))
        self.entry_staff_pass = tk.Entry(form_frame, font=("Arial", 12), show="*")
        self.entry_staff_pass.pack(fill="x", pady=5)

        tk.Button(self.container, text="ACCESS DASHBOARD", font=("Arial", 12, "bold"), bg="#27AE60", fg="white", width=25, height=2, bd=0, cursor="hand2", command=self.perform_staff_login).pack(pady=30)

    def perform_staff_login(self):
        username = self.entry_staff_id.get().strip()
        raw_password = self.entry_staff_pass.get().strip()
        hashed_password = hashlib.sha256(raw_password.encode()).hexdigest()
        
        try:
            conn = sqlite3.connect(SQL_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM admins WHERE username=? AND password=?", (username, hashed_password))
            admin_result = cursor.fetchone()
            conn.close()

            if admin_result:
                path = os.path.join(BASE_DIR, FILE_ADMIN_DASHBOARD)
                self.iconify() 
                try: subprocess.run([sys.executable, path], check=True)
                except Exception as e: messagebox.showerror("Error", f"Admin Dashboard Failed: {e}")
                finally: 
                    self.deiconify() 
                    self.show_login() 
            else: messagebox.showerror("Access Denied", "Invalid Admin Credentials")
        except Exception as e:
            messagebox.showerror("Error", "Database error. Did you run the security patch?")

    # ==========================================
    # PAGE 3: REGISTER 
    # ==========================================
    def show_register(self):
        self.clear_screen()
        self.face_scanned_this_session = False
        
        tk.Button(self.container, text="< Back", bg=BG_COLOR, fg="white", bd=0, font=("Arial", 10), command=self.show_login, anchor="w").pack(fill="x", padx=20, pady=10)
        tk.Label(self.container, text="Student Registration", font=("Helvetica", 18, "bold"), bg=BG_COLOR, fg="white").pack(pady=5)

        form_frame = tk.Frame(self.container, bg=BG_COLOR, padx=40)
        form_frame.pack(fill="x")

        tk.Label(form_frame, text="Full Name", bg=BG_COLOR, fg="white", anchor="w").pack(fill="x")
        self.reg_name = tk.Entry(form_frame, font=("Arial", 11))
        self.reg_name.pack(fill="x", pady=5)

        tk.Label(form_frame, text="Date of Birth (DD/MM/YYYY)", bg=BG_COLOR, fg="white", anchor="w").pack(fill="x", pady=(10,0))
        self.reg_dob = tk.Entry(form_frame, font=("Arial", 11))
        self.reg_dob.pack(fill="x", pady=5)

        tk.Label(form_frame, text="Student Number (Format: ZT-XXXX)", bg=BG_COLOR, fg="white", anchor="w").pack(fill="x", pady=(10,0))
        self.reg_id = tk.Entry(form_frame, font=("Arial", 11))
        self.reg_id.pack(fill="x", pady=5)
        
        tk.Label(form_frame, text="Undergraduate Course", bg=BG_COLOR, fg="white", anchor="w").pack(fill="x", pady=(10,0))
        self.reg_course = ttk.Combobox(form_frame, font=("Arial", 11), state="readonly")
        self.reg_course['values'] = ("BSc Computer Science", "BSc Cyber Security", "BSc Data Science", "BSc Information Technology", "BEng Computer Systems Engineering")
        self.reg_course.pack(fill="x", pady=5)
        self.reg_course.set("Select your course...")

        tk.Label(form_frame, text="Password", bg=BG_COLOR, fg="white", anchor="w").pack(fill="x", pady=(10,0))
        self.reg_pass = tk.Entry(form_frame, font=("Arial", 11), show="*")
        self.reg_pass.pack(fill="x", pady=5)

        tk.Label(self.container, text="________________________________", bg=BG_COLOR, fg="#555").pack(pady=10)
        self.btn_face_scan = tk.Button(self.container, text="📷  Scan My Face", font=("Arial", 12), bg="#3498DB", fg="white", width=25, height=2, bd=0, cursor="hand2", command=self.launch_face_registration)
        self.btn_face_scan.pack(pady=10)

        tk.Button(self.container, text="COMPLETE REGISTRATION", font=("Arial", 12, "bold"), bg="#2ECC71", fg="white", width=25, height=2, bd=0, cursor="hand2", command=self.perform_registration).pack(pady=15)

    def launch_face_registration(self):
        student_id = self.reg_id.get().strip()
        if not student_id or not re.match(r"^ZT-\d+$", student_id): return messagebox.showerror("Invalid ID", "Please enter a valid Student ID (ZT-XXXX).")

        path = os.path.join(BASE_DIR, FILE_REGISTER_SCRIPT)
        self.iconify()
        try:
            subprocess.run([sys.executable, path, student_id], check=True)
            time.sleep(1) 
            if os.path.exists(os.path.join(BASE_DIR, f"face_{student_id}.npy")):
                messagebox.showinfo("Success", "Face Captured Successfully!")
                self.btn_face_scan.config(bg="#27AE60", text="✅ Face Scanned")
                self.face_scanned_this_session = True 
            else: messagebox.showerror("Error", "Biometric file missing. Scan aborted.")
        except Exception as e: messagebox.showerror("Error", f"Registration Failed: {e}")
        finally: self.deiconify()

    def perform_registration(self):
        name, dob, sid, pwd, course = self.reg_name.get().strip(), self.reg_dob.get().strip(), self.reg_id.get().strip(), self.reg_pass.get().strip(), self.reg_course.get()
        if not name or not dob or not sid or not pwd or course == "Select your course...": return messagebox.showwarning("Incomplete", "Fill all fields.")
        if not getattr(self, 'face_scanned_this_session', False): return messagebox.showwarning("Error", "Scan your face first.")

        hashed_password = hashlib.sha256(pwd.encode()).hexdigest()

        try:
            conn = sqlite3.connect(SQL_DB)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (student_id, name, dob, course, password, registered_at) VALUES (?, ?, ?, ?, ?, ?)", 
                           (sid, name, dob, course, hashed_password, str(datetime.now())))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", "Registration Complete!")
            self.show_login()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "That Student ID is already registered!")

    # ==========================================
    # PAGE 4: DASHBOARD (Vertical List Update)
    # ==========================================
    def show_home(self):
        self.clear_screen()
        header = tk.Frame(self.container, bg=BG_COLOR, height=80)
        header.pack(fill="x", pady=20)
        tk.Label(header, text="🛡️ Middlesex", font=("Helvetica", 16, "bold"), bg=BG_COLOR, fg="white").pack()
        tk.Label(header, text=f"Hi, {self.current_user['name']}", font=("Arial", 12), bg=BG_COLOR, fg=ACCENT_COLOR).pack()
        tk.Label(header, text=self.current_user.get('course', 'ZT Student'), font=("Arial", 9), bg=BG_COLOR, fg="#BDC3C7").pack()

        list_frame = tk.Frame(self.container, bg=BG_COLOR)
        list_frame.pack(fill="both", expand=True, padx=40, pady=10)

        buttons = [
            ("👤", "Profile", None), ("ℹ️", "FAQs", None),
            ("📅", "Timetable", self.show_timetable),
            ("📂", "Documents", None),
            ("📝", "Attendance", None), ("🏫", "Campus", None),
            ("⚙️", "Logout", self.show_login)
        ]

        for icon, text, cmd in buttons:
            btn = MenuListItem(list_frame, icon, text, cmd)
            btn.pack(fill="x", pady=3)

    # ==========================================
    # PAGE 5: MULTI-CLASS TIMETABLE
    # ==========================================
    def show_timetable(self):
        self.clear_screen()
        self.configure(bg="#F4F4F4") 
        self.container.configure(bg="#F4F4F4")

        header = tk.Frame(self.container, bg="#2C2658", height=60, padx=15, pady=15)
        header.pack(fill="x")
        tk.Button(header, text="<", bg="#2C2658", fg="white", bd=0, font=("Arial", 16, "bold"), command=self.show_home, cursor="hand2").pack(side="left")
        tk.Label(header, text="Timetable", font=("Helvetica", 16), bg="#2C2658", fg="white").pack(side="left", expand=True)
        tk.Button(header, text="🔄", bg="#2C2658", fg="white", bd=0, font=("Arial", 16), command=self.show_timetable, cursor="hand2").pack(side="right")

        month_frame = tk.Frame(self.container, bg="#1EAE98", pady=10)
        month_frame.pack(fill="x")
        tk.Button(month_frame, text="←", bg="#1EAE98", fg="white", bd=0, font=("Arial", 14, "bold"), cursor="hand2", command=self.prev_month).pack(side="left", padx=20)
        tk.Label(month_frame, text=self.tt_date.strftime("%B %Y"), font=("Arial", 12, "bold"), bg="#1EAE98", fg="white").pack(side="left", expand=True)
        tk.Button(month_frame, text="→", bg="#1EAE98", fg="white", bd=0, font=("Arial", 14, "bold"), cursor="hand2", command=self.next_month).pack(side="right", padx=20)

        cal_bg = tk.Frame(self.container, bg="white")
        cal_bg.pack(fill="x")

        for i, day in enumerate(["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]):
            tk.Label(cal_bg, text=day, font=("Arial", 9, "bold"), bg="#004B73" if i in [0, 4] else "white", fg="white" if i in [0, 4] else "#333", pady=8).grid(row=0, column=i, sticky="nsew")
            cal_bg.grid_columnconfigure(i, weight=1)

        cal = calendar.Calendar(firstweekday=6) 
        tt_data = self.load_timetables()

        for row_idx, week in enumerate(cal.monthdayscalendar(self.tt_date.year, self.tt_date.month)):
            for col_idx, day in enumerate(week):
                if day != 0:
                    btn_bg, btn_fg = "white", "#333"
                    
                    check_date_str = f"{day:02d}/{self.tt_date.month:02d}/{self.tt_date.year}"
                    if check_date_str in tt_data and len(tt_data[check_date_str]) > 0:
                        btn_bg, btn_fg = "#F9E79F", "#B7950B"

                    if day == self.selected_date.day and self.tt_date.month == self.selected_date.month and self.tt_date.year == self.selected_date.year:
                        btn_bg, btn_fg = "#00B4D8", "white"
                    elif day == datetime.now().day and self.tt_date.month == datetime.now().month and self.tt_date.year == datetime.now().year:
                        btn_fg = "#27AE60"

                    tk.Button(cal_bg, text=str(day), bg=btn_bg, fg=btn_fg, bd=0, font=("Arial", 10, "bold"), pady=8,
                                    command=lambda d=day: self.select_date(d), cursor="hand2").grid(row=row_idx+1, column=col_idx, sticky="nsew", padx=1, pady=1)

        canvas = tk.Canvas(self.container, bg="#F4F4F4", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.container, orient="vertical", command=canvas.yview)
        self.classes_container = tk.Frame(canvas, bg="#F4F4F4")
        
        self.classes_container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.classes_container, anchor="nw", width=370)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=(15,0))
        scrollbar.pack(side="right", fill="y")

        self.render_classes_for_date()

    def prev_month(self):
        self.tt_date = self.tt_date.replace(day=1) - timedelta(days=1)
        self.show_timetable()
    def next_month(self):
        self.tt_date = self.tt_date.replace(day=calendar.monthrange(self.tt_date.year, self.tt_date.month)[1]) + timedelta(days=1)
        self.show_timetable()
    def select_date(self, day):
        self.selected_date = self.tt_date.replace(day=day)
        self.show_timetable()

    def render_classes_for_date(self):
        selected_date_str = self.selected_date.strftime("%d/%m/%Y")
        tt_data = self.load_timetables()
        classes_today = tt_data.get(selected_date_str, [])

        # DEV OVERRIDE: Unlocks the scanner button permanently for documentation purposes 
        # as long as there is at least one class on the selected date.
        any_class_active = True if classes_today else False
        now = datetime.now()

        if not classes_today:
            tk.Label(self.classes_container, text="No classes scheduled for this date.", font=("Arial", 10), bg="#F4F4F4", fg="#777").pack(pady=30)
        else:
            for c_data in classes_today:
                c_name = c_data.get("name", "Unknown Class")
                c_type = c_data.get("type", "Seminar")
                c_start = c_data.get("start", "00:00")
                c_end = c_data.get("end", "23:59")
                
                attendance_status = self.get_attendance_status(self.selected_date, c_start, c_end)
                
                card = tk.Frame(self.classes_container, bg="white", highlightbackground="#ddd", highlightthickness=1)
                card.pack(fill="x", pady=5)

                date_box = tk.Frame(card, bg="#EEEEEE", width=70)
                date_box.pack(side="left", fill="y")
                date_box.pack_propagate(False)
                tk.Frame(date_box, bg="#1EAE98", width=5).pack(side="left", fill="y")
                tk.Label(date_box, text=self.selected_date.strftime("%d"), font=("Arial", 16, "bold"), bg="#EEEEEE", fg="#333").pack(pady=(15,0))
                tk.Label(date_box, text=self.selected_date.strftime("%b'%y"), font=("Arial", 9), bg="#EEEEEE", fg="#555").pack()

                info = tk.Frame(card, bg="white", padx=10, pady=10)
                info.pack(side="left", fill="both", expand=True)

                tk.Label(info, text=c_name, font=("Arial", 10, "bold"), bg="white", fg="#333", anchor="w").pack(fill="x")
                tk.Label(info, text=f"Session Type : {c_type}", font=("Arial", 9), bg="white", fg="#555", anchor="w").pack(fill="x")

                att_color = "#27AE60" if attendance_status == "Present" else "#E84C3D" if attendance_status == "Absent" else "#7F8C8D"
                tk.Label(info, text=f"Attendance : {attendance_status}", font=("Arial", 9, "bold"), bg="white", fg=att_color, anchor="w").pack(fill="x", pady=(2,0))

                tk.Frame(info, bg="#eee", height=1).pack(fill="x", pady=5)
                bottom = tk.Frame(info, bg="white")
                bottom.pack(fill="x")
                tk.Label(bottom, text=f"🕒 {c_start} - {c_end}", font=("Arial", 8), bg="white", fg="#555").pack(side="left")

        # The button logic now relies entirely on the Dev Override above
        if any_class_active:
            btn_text, btn_bg, btn_state = "+", ACCENT_COLOR, "normal"
            cursor_type = "hand2"
        else:
            btn_text, btn_bg, btn_state = "🔒", "#95A5A6", "disabled"
            cursor_type = "arrow"

        tk.Button(self.container, text=btn_text, font=("Arial", 24, "bold"), bg=btn_bg, fg="white", bd=0, 
                  activebackground="#C0392B", cursor=cursor_type, state=btn_state, command=self.launch_ztap).place(relx=0.85, rely=0.9, anchor="center", width=60, height=60)

    def launch_ztap(self):
        path = os.path.join(BASE_DIR, FILE_ATTENDANCE_SCRIPT)
        self.iconify()
        try:
            subprocess.run([sys.executable, path, self.current_user_id], check=True)
            messagebox.showinfo("Success", "Attendance Marked Successfully!")
        except Exception as e: messagebox.showerror("Failed", "Attendance Verification Failed.")
        finally: 
            self.deiconify()
            self.show_timetable() 

if __name__ == "__main__":
    app = MDXApp()
    app.mainloop()