import tkinter as tk
from tkinter import filedialog
import csv
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os
import sys
import sqlite3
import re
import calendar
from datetime import datetime, timedelta

# --- CONFIGURATION ---
BG_COLOR = "#2C2658"       
ACCENT_COLOR = "#E84C3D"   
ADMIN_BG = "#ECF0F1"       

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SQL_DB = os.path.join(BASE_DIR, "mdx_system.db")
PHOTO_DIR = os.path.join(BASE_DIR, "attendance_photos")

class AdminDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Middlesex Admin Portal")
        self.geometry("900x750") 
        self.configure(bg=ADMIN_BG)
        self.eval('tk::PlaceWindow . center')
        
        self.tt_date = datetime.now()
        self.selected_date = datetime.now()
        self.setup_ui()

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
        except Exception as e: print(f"DB Error: {e}")
        return data

    def save_timetable_class(self, date_str, class_data):
        conn = sqlite3.connect(SQL_DB)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO timetables (date, name, type, start, end) VALUES (?, ?, ?, ?, ?)", 
                       (date_str, class_data["name"], class_data["type"], class_data["start"], class_data["end"]))
        conn.commit()
        conn.close()

    def delete_specific_class(self, date_str, class_name, start_time):
        conn = sqlite3.connect(SQL_DB)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM timetables WHERE date=? AND name=? AND start=?", (date_str, class_name, start_time))
        conn.commit()
        conn.close()
        self.build_timetable_section()

    # --- UI SETUP ---
    def setup_ui(self):
        sidebar = tk.Frame(self, bg=BG_COLOR, width=180)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False) 

        tk.Label(sidebar, text="\n🛡️\nAdmin Panel", font=("Helvetica", 14, "bold"), bg=BG_COLOR, fg="white", justify="center").pack(pady=(20,40))
        sections = [("👤 Students", "students"), ("📝 Attendance", "attendance"), ("📅 Timetable", "timetable"), ("🚌 Ask MDX", None)]

        for text, section in sections:
            if section: tk.Button(sidebar, text=f" {text}", font=("Arial", 11), bg=BG_COLOR, fg="white", bd=0, anchor="w", padx=20, height=2, cursor="hand2", command=lambda s=section: self.load_admin_section(s)).pack(fill="x", pady=5)
            else: tk.Label(sidebar, text=f" {text}", font=("Arial", 11), bg=BG_COLOR, fg="#7F8C8D", anchor="w", padx=20, height=2).pack(fill="x", pady=5)

        tk.Button(sidebar, text=" Logout", font=("Arial", 11, "bold"), bg=ACCENT_COLOR, fg="white", bd=0, cursor="hand2", command=self.destroy).pack(side="bottom", fill="x", pady=20, padx=10)

        self.admin_content = tk.Frame(self, bg="white", padx=20, pady=20)
        self.admin_content.pack(side="left", fill="both", expand=True, padx=15, pady=15)

        header = tk.Frame(self.admin_content, bg="white")
        header.pack(fill="x", pady=(0, 10))
        tk.Label(header, text="Middlesex Unified Data", font=("Helvetica", 16, "bold"), bg="white", fg="#333").pack(side="left")

        self.tab_content = tk.Frame(self.admin_content, bg="white")
        self.tab_content.pack(fill="both", expand=True)
        self.load_admin_section("timetable") 

    def load_admin_section(self, section):
        for widget in self.tab_content.winfo_children(): widget.destroy()
        style = ttk.Style()
        style.configure("Treeview.Heading", font=('Arial', 10, 'bold'))
        style.configure("Treeview", font=('Arial', 9), rowheight=25)

        if section == "students": self.build_students_section()
        elif section == "attendance": self.build_attendance_section()
        elif section == "timetable": self.build_timetable_section()

    def build_students_section(self):
        tk.Label(self.tab_content, text="📂 Student Directory", font=("Arial", 12, "bold"), bg="white", anchor="w").pack(fill="x", pady=(10,5))
        cols2 = ("ID", "Name", "DOB", "Course", "Registered At")
        self.dir_tree = ttk.Treeview(self.tab_content, columns=cols2, show="headings")
        for col in cols2:
            self.dir_tree.heading(col, text=col)
            self.dir_tree.column(col, anchor="center")
        self.dir_tree.pack(fill="both", expand=True)
        
        try:
            conn = sqlite3.connect(SQL_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT student_id, name, dob, course, registered_at FROM users")
            for row in cursor.fetchall():
                self.dir_tree.insert("", "end", values=(row[0], row[1], row[2], row[3], row[4][:10] if row[4] else "N/A"))
            conn.close()
        except: pass

    def build_attendance_section(self):
        tk.Label(self.tab_content, text="📸 Attendance Logs", font=("Arial", 12, "bold"), bg="white", anchor="w").pack(fill="x", pady=(10,5))
        split_frame = tk.Frame(self.tab_content, bg="white")
        split_frame.pack(fill="both", expand=True)
        left_panel = tk.Frame(split_frame, bg="white")
        left_panel.pack(side="left", fill="both", expand=True)
        self.right_panel = tk.Frame(split_frame, bg="#F9F9F9", width=280, relief="groove", bd=2)
        self.right_panel.pack(side="right", fill="y", padx=10)
        self.right_panel.pack_propagate(False)

        cols = ("ID", "Name", "Course", "Date", "Time", "Status", "Photo")
        self.att_tree = ttk.Treeview(left_panel, columns=cols, show="headings")
        for col in cols:
            self.att_tree.heading(col, text=col)
            self.att_tree.column(col, width=150 if col in ["Name", "Course"] else 80, anchor="center")
        self.att_tree.column("Photo", width=0, stretch=tk.NO)
        self.att_tree.pack(fill="both", expand=True)

        tk.Label(self.right_panel, text="Record Details", font=("Arial", 11, "bold"), bg="#F9F9F9").pack(pady=10)
        self.lbl_photo = tk.Label(self.right_panel, text="Select a record...", bg="#E0E0E0", width=30, height=12)
        self.lbl_photo.pack(pady=10)

        self.status_var = tk.StringVar()
        ttk.Combobox(self.right_panel, textvariable=self.status_var, state="readonly", values=["Present", "Absent", "Late", "Excused"]).pack(fill="x", padx=20, pady=5)
        
        # Save Changes Button
        tk.Button(self.right_panel, text="💾 Save Changes", bg="#27AE60", fg="white", font=("Arial", 10, "bold"), cursor="hand2", command=self.update_attendance_status).pack(fill="x", padx=20, pady=20)
        
        # --- NEW EXPORT BUTTON ---
        tk.Button(self.right_panel, text="📥 Export to CSV", bg="#3498DB", fg="white", font=("Arial", 10, "bold"), cursor="hand2", command=self.export_csv).pack(fill="x", padx=20, pady=(0, 20))

        self.att_tree.bind("<<TreeviewSelect>>", self.on_attendance_select)
        
        try:
            conn = sqlite3.connect(SQL_DB)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.student_id, u.name, u.course, a.date, a.time, a.status, a.photo 
                FROM attendance a 
                LEFT JOIN users u ON a.student_id = u.student_id
            """)
            for row in cursor.fetchall():
                self.att_tree.insert("", "end", values=(row[0], row[1] or "Unknown", row[2] or "N/A", row[3], row[4], row[5], row[6] or "No Photo"))
            conn.close()
        except: pass
        
    def export_csv(self):
        # Opens a system dialog to let the Admin choose where to save the report!
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv", 
            filetypes=[("CSV Files", "*.csv")], 
            title="Export Attendance Data",
            initialfile=f"MDX_Attendance_{datetime.now().strftime('%Y%m%d')}.csv"
        )
        if not file_path: return # User cancelled
        
        try:
            with open(file_path, "w", newline="") as f:
                writer = csv.writer(f)
                # Write standard Headers
                writer.writerow(["Student ID", "Full Name", "Course", "Date", "Time", "Attendance Status", "Biometric Privacy Flag"])
                # Dump UI Treeview data to CSV
                for child in self.att_tree.get_children():
                    writer.writerow(self.att_tree.item(child)["values"])
            messagebox.showinfo("Success", f"Attendance report successfully exported to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export data: {e}")

    def on_attendance_select(self, event):
        selected = self.att_tree.selection()
        if not selected: return
        values = self.att_tree.item(selected[0], "values")
        self.status_var.set(values[5])
        
        # --- THE FIX: Graceful Privacy UI ---
        photo_flag = values[6]
        
        if photo_flag == "PRIVACY_PROTECTED" or photo_flag == "No Photo":
            self.lbl_photo.config(
                image='', 
                text="🔒 PRIVACY PROTECTED\n\nBiometric Match Confirmed\nNo Raw Images Stored", 
                width=25, height=10, 
                bg="#EAECEE", fg="#2C2658", font=("Arial", 10, "bold")
            )
        else:
            # Fallback just in case an older legacy photo is clicked
            photo_path = os.path.join(PHOTO_DIR, photo_flag)
            if os.path.exists(photo_path):
                try:
                    img = Image.open(photo_path)
                    img.thumbnail((200, 200), Image.Resampling.LANCZOS)
                    self.current_photo = ImageTk.PhotoImage(img)
                    self.lbl_photo.config(image=self.current_photo, text="", width=200, height=200, bg="#F9F9F9")
                except: self.lbl_photo.config(image='', text="Error", width=30, height=12, bg="#E0E0E0")
            else: self.lbl_photo.config(image='', text="No Photo", width=30, height=12, bg="#E0E0E0")

    def update_attendance_status(self):
        selected = self.att_tree.selection()
        if not selected: return
        new_status = self.status_var.get()
        item_id = selected[0]
        values = list(self.att_tree.item(item_id, "values"))
        values[5] = new_status
        self.att_tree.item(item_id, values=values)
        
        conn = sqlite3.connect(SQL_DB)
        cursor = conn.cursor()
        cursor.execute("UPDATE attendance SET status=? WHERE student_id=? AND date=? AND time=?", 
                       (new_status, values[0], values[3], values[4]))
        conn.commit()
        conn.close()
        messagebox.showinfo("Success", "Status updated!")

    # --- MULTI-CLASS TIMETABLE EDITOR ---
    def build_timetable_section(self):
        for widget in self.tab_content.winfo_children(): widget.destroy()

        tk.Label(self.tab_content, text="📅 Timetable Manager", font=("Arial", 12, "bold"), bg="white", anchor="w").pack(fill="x", pady=(10,5))
        header = tk.Frame(self.tab_content, bg="#1EAE98", pady=10)
        header.pack(fill="x")
        tk.Button(header, text="←", bg="#1EAE98", fg="white", bd=0, font=("Arial", 14, "bold"), cursor="hand2", command=self.prev_month).pack(side="left", padx=20)
        tk.Label(header, text=self.tt_date.strftime("%B %Y"), font=("Arial", 12, "bold"), bg="#1EAE98", fg="white").pack(side="left", expand=True)
        tk.Button(header, text="→", bg="#1EAE98", fg="white", bd=0, font=("Arial", 14, "bold"), cursor="hand2", command=self.next_month).pack(side="right", padx=20)

        cal_bg = tk.Frame(self.tab_content, bg="white")
        cal_bg.pack(fill="x", pady=5)
        
        for i, day in enumerate(["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]):
            tk.Label(cal_bg, text=day, font=("Arial", 9, "bold"), bg="#004B73" if i in [0, 6] else "#eee", fg="white" if i in [0, 6] else "#333", pady=5).grid(row=0, column=i, sticky="nsew")
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

                    tk.Button(cal_bg, text=str(day), bg=btn_bg, fg=btn_fg, bd=1, font=("Arial", 10, "bold"), pady=5, command=lambda d=day: self.select_date(d), cursor="hand2").grid(row=row_idx+1, column=col_idx, sticky="nsew", padx=1, pady=1)

        self.editor_frame = tk.Frame(self.tab_content, bg="#F9F9F9", padx=20, pady=20, relief="groove", bd=1)
        self.editor_frame.pack(fill="both", expand=True, pady=10)
        self.update_editor_ui()

    def prev_month(self):
        self.tt_date = (self.tt_date.replace(day=1) - timedelta(days=1))
        self.build_timetable_section()
    def next_month(self):
        self.tt_date = (self.tt_date.replace(day=calendar.monthrange(self.tt_date.year, self.tt_date.month)[1]) + timedelta(days=1))
        self.build_timetable_section()
    def select_date(self, day):
        self.selected_date = self.tt_date.replace(day=day)
        self.build_timetable_section()

    def update_editor_ui(self):
        for widget in self.editor_frame.winfo_children(): widget.destroy()
        sel_date_str = self.selected_date.strftime("%d/%m/%Y")
        tt_data = self.load_timetables()
        classes_today = tt_data.get(sel_date_str, [])

        header_frame = tk.Frame(self.editor_frame, bg="#F9F9F9")
        header_frame.pack(fill="x", pady=(0, 10))
        tk.Label(header_frame, text=f"Classes on {sel_date_str}", font=("Arial", 12, "bold"), bg="#F9F9F9").pack(side="left")
        tk.Button(header_frame, text="+ Create Class", bg="#3498DB", fg="white", font=("Arial", 9, "bold"), cursor="hand2", bd=0, padx=10, pady=5, command=self.open_create_class_popup).pack(side="right")

        if not classes_today: tk.Label(self.editor_frame, text="No classes scheduled for this date.", bg="#F9F9F9", fg="#777").pack(pady=20)
        else:
            for c in classes_today:
                cf = tk.Frame(self.editor_frame, bg="white", highlightbackground="#ddd", highlightthickness=1, pady=5, padx=10)
                cf.pack(fill="x", pady=5)
                tk.Label(cf, text=f"{c.get('name')} ({c.get('type')})", font=("Arial", 10, "bold"), bg="white").pack(anchor="w")
                tk.Label(cf, text=f"🕒 {c.get('start')} - {c.get('end')}", font=("Arial", 9), bg="white", fg="#555").pack(anchor="w")
                tk.Button(cf, text="🗑️ Delete", fg="white", bg="#E84C3D", bd=0, cursor="hand2", command=lambda class_del=c: self.delete_specific_class(sel_date_str, class_del['name'], class_del['start'])).pack(side="right", pady=5)

    def open_create_class_popup(self):
        popup = tk.Toplevel(self)
        popup.title("Create New Class")
        popup.geometry("350x380")
        popup.configure(bg="white")
        popup.grab_set() 
        
        tk.Label(popup, text=f"New Class for {self.selected_date.strftime('%d/%m/%Y')}", font=("Arial", 12, "bold"), bg="white").pack(pady=15)
        form = tk.Frame(popup, bg="white", padx=20)
        form.pack(fill="both", expand=True)

        tk.Label(form, text="Class Name:", bg="white", anchor="w").pack(fill="x")
        e_name = tk.Entry(form, font=("Arial", 11), bg="#F1F1F1", relief="flat")
        e_name.pack(fill="x", pady=(2, 10), ipady=5)

        tk.Label(form, text="Session Type:", bg="white", anchor="w").pack(fill="x")
        e_type = ttk.Combobox(form, font=("Arial", 11), state="readonly", values=["Seminar", "Lab", "Lecture", "Workshop"])
        e_type.set("Seminar")
        e_type.pack(fill="x", pady=(2, 10), ipady=5)

        tk.Label(form, text="Start Time (HH:MM):", bg="white", anchor="w").pack(fill="x")
        e_start = tk.Entry(form, font=("Arial", 11), bg="#F1F1F1", relief="flat")
        e_start.pack(fill="x", pady=(2, 10), ipady=5)

        tk.Label(form, text="End Time (HH:MM):", bg="white", anchor="w").pack(fill="x")
        e_end = tk.Entry(form, font=("Arial", 11), bg="#F1F1F1", relief="flat")
        e_end.pack(fill="x", pady=(2, 15), ipady=5)

        def save_and_close():
            name, ctype, start, end = e_name.get().strip(), e_type.get(), e_start.get().strip(), e_end.get().strip()
            if not name or not re.match(r"^\d{2}:\d{2}$", start) or not re.match(r"^\d{2}:\d{2}$", end): return messagebox.showerror("Error", "Fill all fields (HH:MM format).", parent=popup)
            self.save_timetable_class(self.selected_date.strftime("%d/%m/%Y"), {"name": name, "type": ctype, "start": start, "end": end})
            self.build_timetable_section()
            popup.destroy()

        tk.Button(form, text="💾 Save Class", bg=ACCENT_COLOR, fg="white", font=("Arial", 11, "bold"), bd=0, pady=8, cursor="hand2", command=save_and_close).pack(fill="x")

if __name__ == "__main__":
    app = AdminDashboard()
    app.mainloop()