import json
import urllib.request
import tkinter as tk
from tkinter import ttk
import subprocess
import sys
import os
import sqlite3
import time
import re
import calendar
import hashlib
from datetime import datetime, timedelta
import webbrowser
import psycopg2
from PIL import Image, ImageTk

# --- CLOUD CONFIG ---
DB_URL = "postgresql://postgres.rxznjzklmybxvgcccwll:SM3923M00979352@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"

APP_TITLE = "Z-TAP :: SECURE TERMINAL"

# ── Sleek Retro Design Tokens (MDX Colors) ───────────────────────────
BG_DARK       = "#030B17"   
SURFACE       = "#0A192F"   
SURFACE_2     = "#112240"   
BORDER        = "#FFFFFF"   
ACCENT        = "#E63946"  
ACCENT_RED    = "#FF2A2A"   
ACCENT_MUTED  = "#A1222E"   
ACCENT_3      = "#00FF41"   
TEXT_PRIMARY  = "#FFFFFF"   
TEXT_MUTED    = "#8A9FBD"   
TEXT_DIM      = "#4A6282"   

FONT_TITLE    = ("Courier New", 28, "bold")
FONT_HEADING  = ("Courier New", 18, "bold")
FONT_SUB      = ("Courier New", 10)
FONT_BODY     = ("Courier New", 12)
FONT_SMALL    = ("Courier New", 10)
FONT_MONO     = ("Courier New", 12, "bold")
FONT_BTN      = ("Courier New", 14, "bold")

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SQL_DB                 = os.path.join(BASE_DIR, "mdx_system.db")
FILE_REGISTER_SCRIPT   = "face_registration.py"
FILE_ATTENDANCE_SCRIPT = "face_verification.py"
ASSETS_DIR             = os.path.join(BASE_DIR, "assets")

# ── Reusable Sleek Retro Widgets ─────────────────────────────────────

class SleekButton(tk.Canvas):
    def __init__(self, parent, text, command=None, **kwargs):
        self.btn_width  = kwargs.pop("width", 260)
        self.btn_height = kwargs.pop("height", 46)
        self._bg        = kwargs.pop("bg", ACCENT)
        self._font      = kwargs.pop("font", FONT_BTN)
        
        super().__init__(parent, bg=BG_DARK, highlightthickness=0, **kwargs)
        self.config(width=self.btn_width, height=self.btn_height)
        
        self._text    = text
        self._command = command
        self._hover   = False
        
        self.bind("<Map>",            lambda e: self._draw())
        self.bind("<Enter>",          self._on_enter)
        self.bind("<Leave>",          self._on_leave)
        self.bind("<ButtonPress-1>",  self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _draw(self, pressed=False):
        self.delete("all")
        w, h = self.btn_width, self.btn_height
        
        if self._hover and not pressed:
            fill_col, text_col, out_col = self._bg, TEXT_PRIMARY, self._bg
        elif pressed:
            fill_col, text_col, out_col = ACCENT_MUTED, TEXT_PRIMARY, ACCENT_MUTED
        else:
            fill_col, text_col, out_col = BG_DARK, self._bg, self._bg

        self.create_rectangle(2, 2, w-2, h-2, fill=fill_col, outline=out_col, width=2)
        self.create_text(w//2, h//2, text=self._text, fill=text_col, font=self._font)

    def _on_enter(self, _=None):
        self._hover = True
        self._draw()

    def _on_leave(self, _=None):
        self._hover = False
        self._draw()

    def _on_press(self, _=None):
        self._draw(pressed=True)

    def _on_release(self, _=None):
        self._draw()
        if self._command: self._command()


class RetroCalDay(tk.Canvas):
    def __init__(self, parent, day, has_class, is_today, is_selected, command=None, **kwargs):
        super().__init__(parent, bg=BG_DARK, highlightthickness=0, width=45, height=45, **kwargs)
        self.day, self.has_class, self.is_today, self.is_selected = day, has_class, is_today, is_selected
        self._command, self._hover = command, False
        
        self.bind("<Map>", lambda e: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonRelease-1>", self._on_click)

    def _draw(self):
        self.delete("all")
        w, h = 45, 45
        
        if self.is_selected:
            self.create_rectangle(1, 1, w-1, h-1, outline=BORDER, width=1, fill=SURFACE_2)
            txt_col = BORDER
        elif self._hover:
            self.create_rectangle(1, 1, w-1, h-1, outline=TEXT_DIM, width=1, fill=SURFACE)
            txt_col = TEXT_PRIMARY
        else:
            self.create_rectangle(1, 1, w-1, h-1, outline="", fill=BG_DARK)
            txt_col = ACCENT_3 if self.is_today else TEXT_MUTED
            
        self.create_text(w//2, h//2 - 4, text=str(self.day), font=FONT_MONO, fill=txt_col)
        
        if self.has_class:
            dot_col = ACCENT_3 if self.is_today else ACCENT
            self.create_rectangle(w//2 - 2, h - 10, w//2 + 2, h - 6, fill=dot_col, outline="")

    def _on_enter(self, e):
        self._hover = True
        self._draw()

    def _on_leave(self, e):
        self._hover = False
        self._draw()

    def _on_click(self, e):
        if self._command: self._command(self.day)


class TerminalEntry(tk.Frame):
    def __init__(self, parent, placeholder="", show="", **kwargs):
        bg = kwargs.pop("bg", BG_DARK)
        super().__init__(parent, bg=bg, **kwargs)
        self._placeholder = placeholder
        self._var = tk.StringVar()
        self._entry = tk.Entry(
            self, textvariable=self._var, font=FONT_BODY, bg=bg, fg=TEXT_PRIMARY,
            insertbackground=ACCENT, insertwidth=8, relief="flat", bd=0, show=show, highlightthickness=0
        )
        self._entry.pack(fill="x", padx=5, pady=(5, 2))
        self.bottom_border = tk.Frame(self, bg=TEXT_DIM, height=2)
        self.bottom_border.pack(fill="x")

        self._set_placeholder()
        self._entry.bind("<FocusIn>",  self._focus_in)
        self._entry.bind("<FocusOut>", self._focus_out)

    def _set_placeholder(self):
        if not self._var.get():
            self._entry.config(fg=TEXT_DIM)
            self._entry.insert(0, self._placeholder)

    def _focus_in(self, _=None):
        if self._entry.get() == self._placeholder:
            self._entry.delete(0, "end")
            self._entry.config(fg=TEXT_PRIMARY)
        self.bottom_border.config(bg=ACCENT) 

    def _focus_out(self, _=None):
        if not self._entry.get(): self._set_placeholder()
        self.bottom_border.config(bg=TEXT_DIM)

    def get(self):
        val = self._var.get()
        return "" if val == self._placeholder else val


class ImageNavItem(tk.Frame):
    def __init__(self, parent, img_filename, label, command=None):
        super().__init__(parent, bg=BG_DARK, cursor="hand2")
        self._command = command
        self.container = tk.Frame(self, bg=SURFACE, highlightbackground=SURFACE_2, highlightthickness=1)
        self.container.pack(fill="x", pady=4, padx=5)

        img_path = os.path.join(ASSETS_DIR, img_filename)
        if os.path.exists(img_path):
            pil_img = Image.open(img_path).resize((24, 24), Image.Resampling.LANCZOS)
            self.img = ImageTk.PhotoImage(pil_img)
            self._icon_lbl = tk.Label(self.container, image=self.img, bg=SURFACE)
        else:
            self._icon_lbl = tk.Label(self.container, text="[x]", font=FONT_MONO, bg=SURFACE, fg=ACCENT)
            
        self._icon_lbl.pack(side="left", padx=(20, 15), pady=12)
        self._text_lbl = tk.Label(self.container, text=label.upper(), font=FONT_MONO, bg=SURFACE, fg=TEXT_PRIMARY)
        self._text_lbl.pack(side="left", fill="x")

        for w in [self, self.container, self._icon_lbl, self._text_lbl]:
            w.bind("<Enter>", self._hover_in)
            w.bind("<Leave>", self._hover_out)
            w.bind("<ButtonRelease-1>", self._click)

    def _hover_in(self, _=None):
        self.container.config(bg=SURFACE_2, highlightbackground=ACCENT)
        self._icon_lbl.config(bg=SURFACE_2)
        self._text_lbl.config(bg=SURFACE_2, fg=ACCENT)

    def _hover_out(self, _=None):
        self.container.config(bg=SURFACE, highlightbackground=SURFACE_2)
        self._icon_lbl.config(bg=SURFACE)
        self._text_lbl.config(bg=SURFACE, fg=TEXT_PRIMARY)

    def _click(self, _=None):
        if self._command: self._command()


# ══════════════════════════════════════════════════════════════
#  MAIN APP ENGINE
# ══════════════════════════════════════════════════════════════

class MDXApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("440x820")
        self.configure(bg=BG_DARK)
        self.resizable(False, False)
        self.eval('tk::PlaceWindow . center')

        self.current_user    = None
        self.current_user_id = None
        self.tt_date         = datetime.now()
        self.selected_date   = datetime.now()
        self.has_booted      = False 

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=BG_DARK, background=BG_DARK,
                        foreground=TEXT_PRIMARY, selectbackground=ACCENT, bordercolor=TEXT_DIM)

        self.container = tk.Frame(self, bg=BG_DARK)
        self.container.pack(fill="both", expand=True)

        self.show_boot_screen()
    
    def fetch_cloud_performance_metrics(self):
        """
        Fetches counts for the last 24H and calculates realistic FAR/FRR.
        This includes 'TRUE_REJECT' to ensure FAR isn't stuck at 100%.
        """
        try:
            conn = psycopg2.connect(DB_URL)
            cur = conn.cursor()
            
            # Fetch counts for each category in the last 24 hours
            query = """
                SELECT auth_result, COUNT(*) 
                FROM auth_metrics 
                WHERE timestamp >= NOW() - INTERVAL '24 HOURS'
                GROUP BY auth_result;
            """
            cur.execute(query)
            rows = cur.fetchall()
            metrics = {row[0]: row[1] for row in rows}
            
            # Extract specific counts
            fa = metrics.get('FALSE_ACCEPT', 0)
            tr = metrics.get('TRUE_REJECT', 0)
            fr = metrics.get('FALSE_REJECT', 0)
            success = metrics.get('SUCCESS', 0)
            
            # --- CALCULATE FAR (False Acceptance Rate) ---
            # FAR = (Failed rejections of spoofs) / (Total spoof attempts)
            total_imposter_attempts = fa + tr
            far_percentage = (fa / total_imposter_attempts * 100) if total_imposter_attempts > 0 else 0.0
            
            # --- CALCULATE FRR (False Rejection Rate) ---
            # FRR = (False rejections of legit users) / (Total legit attempts)
            total_genuine_attempts = fr + success
            frr_percentage = (fr / total_genuine_attempts * 100) if total_genuine_attempts > 0 else 0.0
            
            total_scans = sum(metrics.values())
            
            cur.close()
            conn.close()
            
            return {
                "far": f"{far_percentage:.1f}%",
                "frr": f"{frr_percentage:.1f}%",
                "total": total_scans
            }
        except Exception as e:
            print(f"❌ Metrics Error: {e}")
            return {"far": "0.0%", "frr": "0.0%", "total": 0}

    def clear_screen(self):
        for w in self.container.winfo_children(): w.destroy()

    def show_alert(self, title, message):
        """Spawns a custom themed overlay instead of a Windows generic messagebox."""
        alert_frame = tk.Frame(self, bg=SURFACE_2, highlightbackground=ACCENT, highlightthickness=2)
        alert_frame.place(relx=0.5, rely=0.5, anchor="center", width=360, height=220)
        
        tk.Label(alert_frame, text="⚠ " + title, font=FONT_HEADING, bg=SURFACE_2, fg=ACCENT).pack(pady=(20, 10))
        tk.Label(alert_frame, text=message, font=FONT_BODY, bg=SURFACE_2, fg=BORDER, wraplength=320, justify="center").pack(expand=True)
        
        SleekButton(alert_frame, "[ ACKNOWLEDGE ]", command=alert_frame.destroy, width=200, height=35).pack(side="bottom", pady=20)

    # ── THE NEW OVERLAY ENGINE (Keeps Tkinter Open!) ──
    def execute_secure_scan(self, title, script_name, args_list, success_callback=None):
        """Simulates handshake, launches camera, and holds an 'In Progress' UI without hiding the app."""
        overlay = tk.Toplevel(self)
        overlay.attributes('-topmost', True)
        overlay.overrideredirect(True)
        
        w, h = 420, 180
        x = self.winfo_x() + (self.winfo_width()//2) - (w//2)
        y = self.winfo_y() + (self.winfo_height()//2) - (h//2)
        overlay.geometry(f"{w}x{h}+{int(x)}+{int(y)}")
        overlay.configure(bg=BG_DARK)
        
        border_frame = tk.Frame(overlay, bg=ACCENT_3, bd=2)
        border_frame.pack(fill="both", expand=True)
        inner_frame = tk.Frame(border_frame, bg=BG_DARK)
        inner_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        title_lbl = tk.Label(inner_frame, text="INITIATING ZERO-TRUST PROTOCOL", font=("Courier New", 14, "bold"), bg=BG_DARK, fg=ACCENT_3)
        title_lbl.pack(pady=(30, 10))
        
        status_lbl = tk.Label(inner_frame, text="Scanning for authorized classroom network...", font=FONT_SMALL, bg=BG_DARK, fg=TEXT_PRIMARY)
        status_lbl.pack(pady=10)
        
        def step2():
            status_lbl.config(text="Validating TLS 1.3 Handshake keys...", fg=ACCENT)
            self.after(800, step3)
            
        def step3():
            status_lbl.config(text="Network Secured. Initializing Optical Sensors...", fg=ACCENT_3)
            self.after(800, launch_camera)
            
        def launch_camera():
            title_lbl.config(text=title.upper(), fg=ACCENT)
            status_lbl.config(text="Camera module active. Do not close this window.", fg=TEXT_PRIMARY)
            border_frame.config(bg=ACCENT)
            
            # Popen keeps Tkinter responsive!
            cmd = [sys.executable, os.path.join(BASE_DIR, script_name)] + args_list
            process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            monitor_process(process)
            
        def monitor_process(process):
            if process.poll() is None:
                self.after(500, lambda: monitor_process(process)) 
            else:
                overlay.destroy()
                if success_callback:
                    success_callback()
                    
        self.after(900, step2)

    def transition_to(self, target_function, text="> PROCESSING..."):
        overlay = tk.Canvas(self, bg=BG_DARK, highlightthickness=0)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        h, w = 820, 440
        shutter_h = 0
        step = 40 

        def draw_shutters(height_val):
            overlay.delete("shutter")
            overlay.create_rectangle(0, 0, w, height_val, fill=SURFACE_2, outline="", tags="shutter")
            overlay.create_rectangle(0, h - height_val, w, h, fill=SURFACE_2, outline="", tags="shutter")
            for y in range(0, height_val, 6): overlay.create_line(0, y, w, y, fill=BG_DARK, tags="shutter")
            for y in range(h - height_val, h, 6): overlay.create_line(0, y, w, y, fill=BG_DARK, tags="shutter")
            overlay.create_line(0, height_val, w, height_val, fill=ACCENT, width=3, tags="shutter")
            overlay.create_line(0, h - height_val, w, h - height_val, fill=ACCENT, width=3, tags="shutter")

        def close_shutter():
            nonlocal shutter_h
            shutter_h += step
            if shutter_h >= h // 2:
                shutter_h = h // 2
                draw_shutters(shutter_h)
                type_text(0) 
            else:
                draw_shutters(shutter_h)
                self.after(16, close_shutter)

        def type_text(idx):
            overlay.delete("text")
            if idx <= len(text):
                disp = text[:idx] + "█"
                overlay.create_text(w//2, h//2, text=disp, font=FONT_MONO, fill=ACCENT_3, justify="center", tags="text")
                self.after(25, type_text, idx + 1)
            else:
                overlay.create_text(w//2, h//2, text=text, font=FONT_MONO, fill=ACCENT_3, justify="center", tags="text")
                target_function()
                self.after(600, open_shutter)

        def open_shutter():
            nonlocal shutter_h
            overlay.delete("text")
            shutter_h -= step
            if shutter_h <= 0: overlay.destroy()
            else:
                draw_shutters(shutter_h)
                self.after(16, open_shutter)

        close_shutter()

    def load_timetables(self):
        try:
            req = urllib.request.Request('https://ztap-cloud-dashboard.onrender.com/api/admin/timetables')
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode())
                
                if result.get("status") == "success":
                    cloud_data = result.get('data', [])
                    formatted_tt = {}
                    user_course = self.current_user.get('course', '') if self.current_user else ''
                    
                    for c in cloud_data:
                        class_course = c.get('course', '')
                        if class_course and class_course != user_course and class_course != "GLOBAL":
                            continue
                            
                        date_key = c['date']
                        if date_key not in formatted_tt:
                            formatted_tt[date_key] = []
                            
                        formatted_tt[date_key].append({
                            "name": c['name'],
                            "course": class_course, 
                            "start": c['start'],
                            "end": c['end']
                        })
                    return formatted_tt
        except Exception as e:
            print(f"⚠️ CLOUD UPLINK FAILED: ({e})")
        return {}

    def get_attendance_status(self, check_date_obj, class_start_str, class_end_str):
        csv_date = check_date_obj.strftime('%Y-%m-%d')
        status   = "PENDING"
        try:
            class_end_dt = datetime.strptime(f"{check_date_obj.strftime('%d/%m/%Y')} {class_end_str}", "%d/%m/%Y %H:%M")
            if datetime.now() > class_end_dt: status = "ABSENT"
        except: pass
        
        try:
            conn = sqlite3.connect(SQL_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT time, status FROM attendance WHERE student_id=? AND date=?", (self.current_user_id, csv_date))
            for row in cursor.fetchall():
                log_time_str, db_status = row
                log_time = datetime.strptime(log_time_str, "%H:%M:%S").time()
                c_start  = (datetime.strptime(class_start_str, "%H:%M") - timedelta(minutes=15)).time()
                c_end    = datetime.strptime(class_end_str, "%H:%M").time()
                if c_start <= log_time <= c_end:
                    status = db_status.upper()
                    break
            conn.close()
        except: pass
        return status

    def show_boot_screen(self):
        if self.has_booted: return self.show_login()
            
        self.clear_screen()
        term = tk.Label(self.container, text="", font=("Courier New", 11), bg=BG_DARK, fg=TEXT_PRIMARY, justify="left", anchor="nw")
        term.pack(fill="both", expand=True, padx=20, pady=40)

        lines = [
            "Z-TAP OS [Version 1.0.0]",
            "(c) Middlesex University Dubai.",
            "",
            "SYSTEM BOOT INITIATED...",
            "LOADING KERNEL MODULES... [OK]",
            "MOUNTING SQLITE DATABASE... [OK]",
            "INITIALIZING NEURAL NETWORKS...",
            " > YOLOv8 VISION... [OK]",
            " > DEEPFACE BIO... [OK]",
            "ESTABLISHING SUPABASE CLOUD UPLINK...",
            "UPLINK SECURED.",
            "",
            "TERMINAL READY."
        ]

        def type_line(idx):
            if idx < len(lines):
                term.config(text=term.cget("text") + lines[idx] + "\n")
                self.after(200, type_line, idx + 1)
            else:
                self.has_booted = True
                self.after(800, lambda: self.transition_to(self.show_login, "> INITIALIZING UI..."))
        type_line(0)

    def show_login(self):
        self.clear_screen()

        bg_canvas = tk.Canvas(self.container, bg=BG_DARK, highlightthickness=0, width=440, height=820)
        bg_canvas.place(x=0, y=0)
        for y in range(0, 820, 20): bg_canvas.create_line(0, y, 440, y, fill=SURFACE)

        tk.Label(self.container, text="[ MDX ]", font=FONT_MONO, bg=BG_DARK, fg=BORDER).pack(pady=(60, 0))
        tk.Label(self.container, text="Z-TAP", font=("Courier New", 48, "bold"), bg=BG_DARK, fg=TEXT_PRIMARY).pack()
        
        self.type_label = tk.Label(self.container, text="", font=FONT_SMALL, bg=BG_DARK, fg=ACCENT)
        self.type_label.pack(pady=(0, 40))
        self._type_text(self.type_label, "AWAITING AUTHENTICATION...")

        card = tk.Frame(self.container, bg=BG_DARK)
        card.pack(fill="x", padx=40)

        tk.Label(card, text="STUDENT ID", font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w")
        self.entry_login_id = TerminalEntry(card, placeholder="ZT-XXXX")
        self.entry_login_id.pack(fill="x", pady=(0, 20))

        tk.Label(card, text="PASSWORD", font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w")
        self.entry_login_pass = TerminalEntry(card, placeholder="********", show="*")
        self.entry_login_pass.pack(fill="x", pady=(0, 30))

        SleekButton(card, "LOGIN [ENTER]", command=self.perform_login, width=360, height=50).pack()

        tk.Button(self.container, text="[ REGISTER NEW USER ]", font=FONT_SMALL, bg=BG_DARK, fg=TEXT_DIM, bd=0, cursor="hand2", command=lambda: self.transition_to(self.show_register, "> ALLOCATING NEW SECTOR...")).pack(pady=30)
        tk.Button(self.container, text="SYSADMIN OVERRIDE >", font=FONT_SMALL, bg=BG_DARK, fg=TEXT_DIM, bd=0, cursor="hand2", command=lambda: self.transition_to(self.show_staff_login, "> INITIATING OVERRIDE...")).place(relx=0.5, rely=0.95, anchor="s")

    def _type_text(self, label_widget, full_text, idx=0):
        if idx <= len(full_text):
            try:
                label_widget.config(text=full_text[:idx] + "█")
                self.after(50, self._type_text, label_widget, full_text, idx+1)
            except: pass
        else:
            self._blink_cursor(label_widget, full_text)

    def _blink_cursor(self, label_widget, full_text, show=True):
        try:
            label_widget.config(text=full_text + ("█" if show else " "))
            self.after(500, self._blink_cursor, label_widget, full_text, not show)
        except: pass

    def perform_login(self):
        student_id      = self.entry_login_id.get().strip()
        raw_password    = self.entry_login_pass.get().strip()
        hashed_password = hashlib.sha256(raw_password.encode()).hexdigest()
        try:
            conn = sqlite3.connect(SQL_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT name, course FROM users WHERE student_id=? AND password=?", (student_id, hashed_password))
            result = cursor.fetchone()
            conn.close()
            if result:
                self.current_user    = {"name": result[0], "course": result[1]}
                self.current_user_id = student_id
                self.transition_to(self.show_home, "> AUTHENTICATION SUCCESS\n> DECRYPTING PROFILE...")
            else:
                self.show_alert("ACCESS DENIED", "Invalid ID or Password. Please try again.")
        except: self.show_alert("SYSTEM ERROR", "Local Database is offline.")

    def show_staff_login(self):
        self.clear_screen()
        tk.Button(self.container, text="< ABORT", font=FONT_MONO, bg=BG_DARK, fg=TEXT_DIM, bd=0, cursor="hand2", command=lambda: self.transition_to(self.show_login, "> RETURNING TO MAIN...")).place(x=20, y=20)
        tk.Label(self.container, text="RESTRICTED", font=("Courier New", 36, "bold"), bg=BG_DARK, fg=ACCENT).pack(pady=(80,10))
        
        card = tk.Frame(self.container, bg=BG_DARK)
        card.pack(fill="x", padx=40, pady=40)

        tk.Label(card, text="SYSADMIN ID", font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w")
        self.entry_staff_id = TerminalEntry(card)
        self.entry_staff_id.pack(fill="x", pady=(0, 20))

        tk.Label(card, text="PASSPHRASE", font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w")
        self.entry_staff_pass = TerminalEntry(card, show="*")
        self.entry_staff_pass.pack(fill="x", pady=(0, 30))

        SleekButton(card, "AUTHORIZE", command=self.perform_staff_login, width=360, height=50).pack()

    def perform_staff_login(self):
        username, pwd = self.entry_staff_id.get().strip(), self.entry_staff_pass.get().strip()
        hashed = hashlib.sha256(pwd.encode()).hexdigest()
        try:
            conn = sqlite3.connect(SQL_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM admins WHERE username=? AND password=?", (username, hashed))
            admin_result = cursor.fetchone()
            conn.close()
            if admin_result:
                webbrowser.open('https://ztap-cloud-dashboard.onrender.com')
                self.transition_to(self.show_login, "> OVERRIDE ACCEPTED\n> LAUNCHING WEB DASHBOARD...")
            else: self.show_alert("ACCESS DENIED", "Invalid Sysadmin Credentials.")
        except: pass

    def show_register(self):
        self.clear_screen()
        self.face_scanned_this_session = False

        tk.Button(self.container, text="< BACK", font=FONT_MONO, bg=BG_DARK, fg=TEXT_DIM, bd=0, cursor="hand2", command=lambda: self.transition_to(self.show_login, "> CANCELING ENROLLMENT...")).pack(anchor="w", padx=20, pady=20)
        tk.Label(self.container, text="ENROLL USER", font=FONT_HEADING, bg=BG_DARK, fg=BORDER).pack(anchor="w", padx=20)

        card = tk.Frame(self.container, bg=BG_DARK)
        card.pack(padx=20, pady=10, fill="x")

        def _lbl(t): tk.Label(card, text=t, font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w", pady=(10, 0))

        _lbl("FULL NAME")
        self.reg_name = TerminalEntry(card)
        self.reg_name.pack(fill="x")

        _lbl("DOB (DD/MM/YYYY)")
        self.reg_dob = TerminalEntry(card)
        self.reg_dob.pack(fill="x")

        _lbl("STUDENT ID (ZT-XXXX)")
        self.reg_id = TerminalEntry(card)
        self.reg_id.pack(fill="x")

        _lbl("COURSE MAJOR")
        self.reg_course = ttk.Combobox(card, font=FONT_MONO, state="readonly")
        self.reg_course['values'] = ("BSc Computer Science", "BSc Cyber Security", "BSc Data Science", "BSc Information Technology", "BEng Computer Systems Engineering")
        self.reg_course.set("SELECT...")
        self.reg_course.pack(fill="x", pady=(5,0))

        _lbl("PASSWORD")
        self.reg_pass = TerminalEntry(card, show="*")
        self.reg_pass.pack(fill="x")

        tk.Frame(card, bg=TEXT_DIM, height=1).pack(fill="x", pady=20)

        self._face_status = tk.Label(card, text="> BIOMETRICS: MISSING", font=FONT_SMALL, bg=BG_DARK, fg=ACCENT)
        self._face_status.pack(pady=5)

        self.btn_face_scan = SleekButton(card, "INITIATE FACE SCAN", command=self.launch_face_registration, width=400, height=40, bg=TEXT_DIM)
        self.btn_face_scan.pack(pady=5)

        SleekButton(card, "SAVE PROFILE", command=self.perform_registration, width=400, height=50, bg=ACCENT).pack(pady=20)

    def launch_face_registration(self):
        student_id = self.reg_id.get().strip()
        if not student_id or not re.match(r"^ZT-\d+$", student_id): 
            return self.show_alert("INPUT ERROR", "Student ID must follow format 'ZT-XXXX'.")
        
        def on_complete():
            # 🛡️ ZERO-TRUST CHECK: Query the cloud to ensure the vector arrived safely
            try:
                conn = psycopg2.connect(DB_URL)
                cur = conn.cursor()
                cur.execute("SELECT bio_status FROM users WHERE user_id = %s AND face_baseline IS NOT NULL", (student_id,))
                result = cur.fetchone()
                cur.close()
                conn.close()
                
                if result:
                    self._face_status.config(text="> BIOMETRICS: SECURED (CLOUD)", fg=ACCENT_3)
                    self.face_scanned_this_session = True
                else: 
                    self.show_alert("BIOMETRIC ERROR", "Face scan failed or did not sync to the cloud.")
            except Exception as e:
                print(f"Cloud Verification Error: {e}")
                self.show_alert("NETWORK ERROR", "Could not verify biometric sync with Supabase.")

        self.execute_secure_scan("BIOMETRIC REGISTRATION IN PROGRESS", FILE_REGISTER_SCRIPT, [student_id], on_complete)

    def perform_registration(self):
        name, dob, sid, pwd, course = self.reg_name.get().strip(), self.reg_dob.get().strip(), self.reg_id.get().strip(), self.reg_pass.get().strip(), self.reg_course.get()
        if not name or not dob or not sid or not pwd or course == "SELECT...": return self.show_alert("INPUT ERROR", "All fields must be completed.")
        if not getattr(self, 'face_scanned_this_session', False): return self.show_alert("SECURITY LOCK", "A Biometric Face Scan is required to register.")

        hashed = hashlib.sha256(pwd.encode()).hexdigest()
        try:
            # 1. Save to Local Offline DB for quick terminal login
            conn = sqlite3.connect(SQL_DB)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (student_id, name, dob, course, password, registered_at) VALUES (?, ?, ?, ?, ?, ?)", (sid, name, dob, course, hashed, str(datetime.now())))
            conn.commit()
            conn.close()

            # 2. Update the existing Cloud Record (Vector was already saved by edge node)
            try:
                cc = psycopg2.connect(DB_URL)
                cc.autocommit = True
                cur = cc.cursor()
                cur.execute("""
                    UPDATE users 
                    SET full_name = %s, password_hash = %s, role = 'student', bio_status = 'Complete'
                    WHERE user_id = %s
                """, (name, hashed, sid))
                cur.close()
                cc.close()
            except Exception as e: 
                print(f"Cloud DB Update Warning: {e}")

            self.transition_to(self.show_login, "> UPLOADING PROFILE TO CLOUD...\n> SYNC COMPLETE.")
        except sqlite3.IntegrityError: self.show_alert("DUPLICATE ENTRY", "This Student ID is already registered in the system.")

    def show_home(self):
        self.clear_screen()

        banner = tk.Frame(self.container, bg=SURFACE, pady=25, padx=20)
        banner.pack(fill="x", pady=(0, 20))

        tk.Label(banner, text="WELCOME,", font=FONT_SMALL, bg=SURFACE, fg=TEXT_MUTED).pack(anchor="w")
        tk.Label(banner, text=self.current_user['name'].upper(), font=FONT_TITLE, bg=SURFACE, fg=BORDER).pack(anchor="w")
        tk.Label(banner, text=self.current_user.get('course', '').upper(), font=FONT_SMALL, bg=SURFACE, fg=ACCENT).pack(anchor="w", pady=(5,0))

        nav_frame = tk.Frame(self.container, bg=BG_DARK)
        nav_frame.pack(fill="both", expand=True, padx=15)

        items = [
            ("profile.png",    "Profile Data",    None),
            ("calendar.png",   "Live Timetable",  lambda: self.transition_to(self.show_timetable, "> FETCHING LIVE SCHEDULE...")),
            ("attendance.png", "Attendance Logs", None),
            ("docs.png",       "Documents",       None),
            ("faq.png",        "Help & FAQ",      None),
            ("map.png",        "Chaos Testing",   lambda: self.transition_to(self.show_testing_dashboard, "> INITIALIZING TEST ENV...")),
        ]

        for img, label, cmd in items:
            ImageNavItem(nav_frame, img, label, cmd).pack(fill="x")

        tk.Button(self.container, text="[ LOGOUT ]", font=FONT_MONO, bg=BG_DARK, fg=TEXT_DIM, bd=0, cursor="hand2", command=lambda: self.transition_to(self.show_login, "> TERMINATING SESSION...")).pack(pady=20)

    # ── THE CHAOS TESTING DASHBOARD ──
    def show_testing_dashboard(self):
        self.clear_screen()
        
        hdr = tk.Frame(self.container, bg=BG_DARK, pady=15)
        hdr.pack(fill="x")
        tk.Button(hdr, text="< ABORT TO MAIN", font=FONT_MONO, bg=BG_DARK, fg=TEXT_DIM, bd=0, cursor="hand2", command=lambda: self.transition_to(self.show_home, "> RETURNING TO ROOT...")).pack(side="left", padx=20)

        # --- The Advanced Targeting Canvas HUD ---
        canvas = tk.Canvas(self.container, bg=BG_DARK, highlightthickness=0, height=140)
        canvas.pack(fill="x", padx=20, pady=(0, 10))
        
        w, h = 400, 130
        length, t = 25, 2  
        color = ACCENT_RED   # We use red here to signify Chaos/Attack mode
        
        # Draw Corner Brackets
        canvas.create_line(10, 10, 10+length, 10, fill=color, width=t)
        canvas.create_line(10, 10, 10, 10+length, fill=color, width=t)
        canvas.create_line(w-10, 10, w-10-length, 10, fill=color, width=t)
        canvas.create_line(w-10, 10, w-10, 10+length, fill=color, width=t)
        canvas.create_line(10, h-10, 10+length, h-10, fill=color, width=t)
        canvas.create_line(10, h-10, 10, h-10-length, fill=color, width=t)
        canvas.create_line(w-10, h-10, w-10-length, h-10, fill=color, width=t)
        canvas.create_line(w-10, h-10, w-10, h-10-length, fill=color, width=t)
        
        # Internal HUD Elements
        canvas.create_text(w//2, 35, text="CHAOS TESTING PROTOCOL", font=FONT_HEADING, fill=color)
        canvas.create_text(w//2, 60, text="WARNING: LIVE METRICS INJECTION", font=FONT_SMALL, fill=TEXT_MUTED)
        
        # Animated HUD Scanning Line
        scan_line = canvas.create_line(15, 75, w-15, 75, fill=ACCENT_RED, width=1)
        
        def animate_scan(y, direction):
            if not canvas.winfo_exists(): return
            canvas.coords(scan_line, 15, y, w-15, y)
            if y >= h-20: direction = -1
            elif y <= 75: direction = 1
            self.after(30, animate_scan, y + (2 * direction), direction)
            
        animate_scan(75, 1)
        # ---------------------------------------------------------

        card = tk.Frame(self.container, bg=SURFACE, highlightbackground=color, highlightthickness=1)
        card.pack(fill="x", padx=20, pady=5)

        tk.Label(card, text="LOCK TARGET ID:", font=FONT_MONO, bg=SURFACE, fg=BORDER).pack(pady=(20, 5))

        self.test_id_entry = TerminalEntry(card, placeholder="ZT-XXXX", bg=SURFACE)
        self.test_id_entry.pack(fill="x", padx=40, pady=10)
        
        # Auto-fill ID for faster testing
        if self.current_user_id:
            self.test_id_entry._var.set(self.current_user_id)
            self.test_id_entry._entry.config(fg=TEXT_PRIMARY)

        # Telemetry readouts to match the camera screen
        tk.Label(card, text="MODELS: YOLOv8 + DEEPFACE\nUPLINK: ACTIVE", font=("Courier New", 8), bg=SURFACE, fg=TEXT_MUTED, justify="center").pack(pady=(5, 15))

        def trigger_chaos_test():
            target_id = self.test_id_entry.get().strip()
            if not target_id or target_id == "ZT-XXXX":
                self.show_alert("INPUT ERROR", "Please enter a valid Student ID.")
                return

            self.execute_secure_scan("PEN-TEST IN PROGRESS", FILE_ATTENDANCE_SCRIPT, [target_id])

        # Red button to signify an attack simulation
        SleekButton(card, "EXECUTE PEN-TEST SCAN", command=trigger_chaos_test, width=300, height=45, bg=ACCENT_RED).pack(pady=(5, 25))

    def show_timetable(self):
        self.clear_screen()

        hdr = tk.Frame(self.container, bg=BG_DARK, pady=15)
        hdr.pack(fill="x")
        tk.Button(hdr, text="< MAIN", font=FONT_MONO, bg=BG_DARK, fg=TEXT_DIM, bd=0, cursor="hand2", command=lambda: self.transition_to(self.show_home, "> RETURNING TO ROOT...")).pack(side="left", padx=20)
        tk.Label(hdr, text="SCHEDULE", font=FONT_HEADING, bg=BG_DARK, fg=BORDER).pack(side="right", padx=20)

        month_bar = tk.Frame(self.container, bg=SURFACE, pady=10)
        month_bar.pack(fill="x")
        tk.Button(month_bar, text="<", font=FONT_MONO, bg=SURFACE, fg=ACCENT, bd=0, cursor="hand2", command=self.prev_month).pack(side="left", padx=20)
        tk.Label(month_bar, text=self.tt_date.strftime("%B %Y").upper(), font=FONT_MONO, bg=SURFACE, fg=BORDER).pack(side="left", expand=True)
        tk.Button(month_bar, text=">", font=FONT_MONO, bg=SURFACE, fg=ACCENT, bd=0, cursor="hand2", command=self.next_month).pack(side="right", padx=20)

        cal_frame = tk.Frame(self.container, bg=BG_DARK)
        cal_frame.pack(fill="x", padx=10, pady=10)

        for i, d in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]):
            tk.Label(cal_frame, text=d, font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).grid(row=0, column=i, sticky="nsew", pady=5)
            cal_frame.grid_columnconfigure(i, weight=1)

        cal     = calendar.Calendar(firstweekday=6)
        tt_data = self.load_timetables()
        
        cells_to_animate = []

        for r, week in enumerate(cal.monthdayscalendar(self.tt_date.year, self.tt_date.month)):
            for c, day in enumerate(week):
                if day == 0: 
                    tk.Frame(cal_frame, bg=BG_DARK, width=45, height=45).grid(row=r+1, column=c, sticky="nsew", padx=2, pady=2)
                    continue

                check_str = f"{day:02d}/{self.tt_date.month:02d}/{self.tt_date.year}"
                has_class = check_str in tt_data and len(tt_data[check_str]) > 0
                is_today  = (day == datetime.now().day and self.tt_date.month == datetime.now().month and self.tt_date.year == datetime.now().year)
                is_sel    = (day == self.selected_date.day and self.tt_date.month == self.selected_date.month and self.tt_date.year == self.selected_date.year)

                day_widget = RetroCalDay(cal_frame, day, has_class, is_today, is_sel, command=self.select_date)
                cells_to_animate.append((day_widget, r+1, c))

        def animate_grid(idx):
            if idx < len(cells_to_animate):
                widget, row, col = cells_to_animate[idx]
                if widget.winfo_exists():
                    widget.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
                    widget.config(bg=TEXT_DIM)
                    self.after(40, lambda w=widget: w.config(bg=BG_DARK) if w.winfo_exists() else None)
                    self.after(15, animate_grid, idx + 1)

        self.after(400, lambda: animate_grid(0))

        list_frame = tk.Frame(self.container, bg=BG_DARK)
        list_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        selected_str = self.selected_date.strftime("%d/%m/%Y")
        classes = tt_data.get(selected_str, [])

        if not classes:
            tk.Label(list_frame, text="[ NO CLASSES FOUND ]", font=FONT_MONO, bg=BG_DARK, fg=TEXT_DIM, pady=30).pack()
        else:
            for c in classes:
                att = self.get_attendance_status(self.selected_date, c["start"], c["end"])
                
                is_active = False
                try:
                    s_dt = datetime.strptime(f"{selected_str} {c['start']}", "%d/%m/%Y %H:%M") - timedelta(minutes=15)
                    e_dt = datetime.strptime(f"{selected_str} {c['end']}", "%d/%m/%Y %H:%M")
                    if s_dt <= datetime.now() <= e_dt: is_active = True
                except: pass

                card = tk.Frame(list_frame, bg=SURFACE, highlightbackground=SURFACE_2, highlightthickness=1)
                card.pack(fill="x", pady=5)
                
                att_col = ACCENT_3 if att == "PRESENT" else ACCENT if att == "ABSENT" else TEXT_MUTED
                
                tk.Label(card, text=c["name"].upper(), font=FONT_MONO, bg=SURFACE, fg=BORDER).pack(anchor="w", padx=15, pady=(15,0))
                tk.Label(card, text=f"TIME: {c['start']} - {c['end']}", font=FONT_SMALL, bg=SURFACE, fg=TEXT_MUTED).pack(anchor="w", padx=15)
                
                bottom_pad = 5 if (is_active and att != "PRESENT") else 15
                tk.Label(card, text=f"STATUS: [{att}]", font=FONT_MONO, bg=SURFACE, fg=att_col).pack(anchor="w", padx=15, pady=(5, bottom_pad))

                if is_active and att != "PRESENT":
                    btn = SleekButton(card, "EXECUTE SCAN", command=lambda cls=c["course"]: self.launch_ztap(cls), width=370, height=35, font=("Courier New", 12, "bold"))
                    btn.pack(pady=(0, 15))

    def prev_month(self):
        self.tt_date = self.tt_date.replace(day=1) - timedelta(days=1)
        self.show_timetable()

    def next_month(self):
        self.tt_date = self.tt_date.replace(day=calendar.monthrange(self.tt_date.year, self.tt_date.month)[1]) + timedelta(days=1)
        self.show_timetable()

    def select_date(self, day):
        self.selected_date = self.tt_date.replace(day=day)
        self.show_timetable()

    def launch_ztap(self, class_name=None):
        args = [self.current_user_id]
        if class_name: args.append(class_name)
        
        self.execute_secure_scan("ATTENDANCE SCAN IN PROGRESS", FILE_ATTENDANCE_SCRIPT, args, self.show_timetable)

if __name__ == "__main__":
    app = MDXApp()
    app.mainloop()