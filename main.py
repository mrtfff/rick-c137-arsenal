import os
import json
import sys
import subprocess
import threading
import shutil
import time
import signal
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageGrab, ImageTk

# Windows DPI Awareness (Prevents Display Scaling Offset)
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI Aware
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# File & Directory Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
GADGETS_FILE = os.path.join(DATA_DIR, "gadgets.json")
CATEGORIES_FILE = os.path.join(DATA_DIR, "categories.json")
THREAT_LEVELS_FILE = os.path.join(DATA_DIR, "threat_levels.json")
WORK_TIMER_FILE = os.path.join(DATA_DIR, "work_timer.json")


def parse_timestamp_to_seconds(ts_str):
    if not ts_str or not isinstance(ts_str, str):
        return 0
    parts = ts_str.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 1:
            return int(parts[0])
    except ValueError:
        return 0
    return 0


def gadget_sort_key(gadget):
    """Sorts gadgets chronologically: Season -> Episode -> Timestamp -> ID."""
    season = gadget.get("season", 0) or 0
    episode = gadget.get("episode", 0) or 0
    ts_seconds = parse_timestamp_to_seconds(gadget.get("timestamp"))
    return (season, episode, ts_seconds, gadget.get("id", ""))


def initialize_environment():
    """Automatically creates directories and default JSON data files if missing."""
    print("[LOG] Checking file environment...", flush=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # Categories JSON Auto-creation
    if not os.path.exists(CATEGORIES_FILE):
        default_cats = {
            "categories": [
                { "id": 0, "name": "Handheld Weapon / Device" },
                { "id": 1, "name": "Cybernetic / Body Implant" },
                { "id": 2, "name": "Vehicle / Transport / Adaptation" },
                { "id": 3, "name": "Garage / Lab Equipment" },
                { "id": 4, "name": "Wearable Equipment / Armor / Jetpack" },
                { "id": 5, "name": "Biological / Genetic / Chemical Invention" },
                { "id": 6, "name": "Other / Special Invention" },
                { "id": 7, "name": "Unclassified / Unknown" },
                { "id": 8, "name": "Ship-Mounted Device" }
            ]
        }
        with open(CATEGORIES_FILE, "w", encoding="utf-8") as f:
            json.dump(default_cats, f, ensure_ascii=False, indent=2)

    # Threat Levels JSON Auto-creation
    if not os.path.exists(THREAT_LEVELS_FILE):
        default_threats = {
            "threat_levels": [
                { "id": 0, "name": "Harmless / Utility" },
                { "id": 1, "name": "Indirect Hazard / Tactical" },
                { "id": 2, "name": "Personal Lethality" },
                { "id": 3, "name": "Area Destruction" },
                { "id": 4, "name": "Planetary Threat" },
                { "id": 5, "name": "Multiversal / Reality Bending" },
                { "id": 99, "name": "Unclassified / Unknown" }
            ]
        }
        with open(THREAT_LEVELS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_threats, f, ensure_ascii=False, indent=2)

    # Gadgets JSON Auto-creation
    if not os.path.exists(GADGETS_FILE):
        with open(GADGETS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
    print("[LOG] File environment check completed.", flush=True)


# Ensure file environment before application launch
initialize_environment()


class SnippingTool:
    """Screen sniper overlay for selecting regions."""
    def __init__(self, prompt_text="Select Region", screen_img=None):
        self.root = tk.Toplevel()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.config(cursor="cross")
        self.root.withdraw()

        if screen_img is None:
            time.sleep(0.15)
            self.screen_img = ImageGrab.grab()
        else:
            self.screen_img = screen_img

        self.root.update_idletasks()
        scr_w = self.root.winfo_screenwidth()
        scr_h = self.root.winfo_screenheight()

        img_w, img_h = self.screen_img.size
        self.scale_x = img_w / float(scr_w) if scr_w > 0 else 1.0
        self.scale_y = img_h / float(scr_h) if scr_h > 0 else 1.0

        resample_filter = getattr(Image, 'Resampling', Image).LANCZOS
        if (img_w, img_h) != (scr_w, scr_h):
            display_pil = self.screen_img.resize((scr_w, scr_h), resample_filter)
        else:
            display_pil = self.screen_img

        self.tk_screen_img = ImageTk.PhotoImage(display_pil)

        self.canvas = tk.Canvas(self.root, cursor="cross", highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.create_image(0, 0, image=self.tk_screen_img, anchor="nw")

        # Prompt Banner
        banner_w = min(640, max(300, scr_w - 40))
        banner_h = 44
        bx1 = (scr_w - banner_w) // 2
        by1 = 20
        bx2 = bx1 + banner_w
        by2 = by1 + banner_h

        self.canvas.create_rectangle(bx1, by1, bx2, by2, fill="#1e1e1e", outline="#4CAF50", width=2)
        self.canvas.create_text(
            scr_w // 2, by1 + (banner_h // 2),
            text=prompt_text, font=("Helvetica", 14, "bold"), fill="#FFFFFF"
        )

        # Mouse Listeners
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        
        # Cancel Mechanisms (ESC or Right Click)
        self.root.bind("<Escape>", self.on_escape)
        self.canvas.bind("<Escape>", self.on_escape)
        self.root.bind("<Button-3>", self.on_escape)
        self.canvas.bind("<Button-3>", self.on_escape)

        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None
        self.rect = None
        self.cropped_img = None

        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.canvas.focus_set()

    def on_escape(self, event=None):
        """Cancels snipping when ESC or Right-Click is pressed."""
        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None
        self.cropped_img = None
        self.root.destroy()

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline='#00E676', width=2
        )

    def on_move_press(self, event):
        cur_x, cur_y = (event.x, event.y)
        if self.rect and self.start_x is not None and self.start_y is not None:
            self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        self.end_x = event.x
        self.end_y = event.y

        if self.start_x is not None and self.end_x is not None:
            x1 = min(self.start_x, self.end_x)
            y1 = min(self.start_y, self.end_y)
            x2 = max(self.start_x, self.end_x)
            y2 = max(self.start_y, self.end_y)

            if x2 - x1 >= 10 and y2 - y1 >= 10:
                rx1 = int(x1 * self.scale_x)
                ry1 = int(y1 * self.scale_y)
                rx2 = int(x2 * self.scale_x)
                ry2 = int(y2 * self.scale_y)
                self.cropped_img = self.screen_img.crop((rx1, ry1, rx2, ry2))

        self.root.destroy()

    def get_image(self):
        self.root.wait_window()
        return self.cropped_img

    def get_bbox(self):
        self.root.wait_window()
        if self.start_x is None or self.end_x is None:
            return None
        x1 = min(self.start_x, self.end_x)
        y1 = min(self.start_y, self.end_y)
        x2 = max(self.start_x, self.end_x)
        y2 = max(self.start_y, self.end_y)
        if x2 - x1 < 10 or y2 - y1 < 10:
            return None
        return (x1, y1, x2, y2)


class App(tk.Tk):
    def __init__(self):
        print("[LOG 1] Instantiating App...", flush=True)
        super().__init__()
        self.title("Rick C-137 Gadget Logger")
        self.geometry("460x620")

        self.full_img = None
        self.focus_img = None
        self.is_capturing = False

        print("[LOG 2] Loading categories...", flush=True)
        self.categories_data = self.load_categories()

        print("[LOG 3] Loading threat levels...", flush=True)
        self.threat_levels_data = self.load_threat_levels()

        print("[LOG 4] Loading gadget data...", flush=True)
        self.gadgets_data = self.load_gadgets()

        print("[LOG 5] Loading timer data...", flush=True)
        self.total_work_seconds, self.timer_running = self.load_timer_data()

        print("[LOG 6] Setting up UI components...", flush=True)
        self.setup_ui()
        print("[LOG 7] UI setup completed.", flush=True)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(500, self.start_hotkey_listener)
        self.after(1000, self.update_timer_tick)
        self.after(500, self.check_signal)
        self.setup_signal_handlers()

        print("[LOG 8] Displaying and focusing main window...", flush=True)
        self.deiconify()
        self.lift()
        self.focus_force()
        print("[LOG 9] App.__init__ completed successfully.", flush=True)

    def check_signal(self):
        self.after(500, self.check_signal)

    def setup_signal_handlers(self):
        def handle_sigint(sig, frame):
            print("\n[LOG] Ctrl+C detected. Closing application safely...", flush=True)
            self.after(0, self.on_closing)

        try:
            signal.signal(signal.SIGINT, handle_sigint)
        except Exception:
            pass

    def load_categories(self):
        try:
            with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)["categories"]
        except Exception as e:
            if os.path.exists(CATEGORIES_FILE):
                messagebox.showwarning("Category Error", f"Failed to read categories.json: {e}")
            return []

    def load_threat_levels(self):
        try:
            with open(THREAT_LEVELS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)["threat_levels"]
        except Exception as e:
            if os.path.exists(THREAT_LEVELS_FILE):
                messagebox.showwarning("Threat Level Error", f"Failed to read threat_levels.json: {e}")
            return []

    def load_gadgets(self):
        if not os.path.exists(GADGETS_FILE):
            return []
        try:
            with open(GADGETS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    raise ValueError("gadgets.json data format must be a list [].")
                return data
        except Exception as e:
            # Backup corrupted file
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            corrupted_backup = os.path.join(BACKUP_DIR, f"gadgets_corrupted_{timestamp}.json")
            try:
                shutil.copy2(GADGETS_FILE, corrupted_backup)
                backup_note = f"\nCorrupted file backed up to:\n{corrupted_backup}"
            except Exception:
                backup_note = ""

            # Check latest working backup
            latest_backup = os.path.join(BACKUP_DIR, "gadgets_latest_backup.json")
            restored_data = None
            if os.path.exists(latest_backup):
                try:
                    with open(latest_backup, "r", encoding="utf-8") as bf:
                        restored_data = json.load(bf)
                except Exception:
                    restored_data = None

            if restored_data is not None:
                res = messagebox.askyesno(
                    "Data Read Error",
                    f"gadgets.json is unreadable or corrupted!\nError: {e}{backup_note}\n\n"
                    f"Restore data from the latest working backup?"
                )
                if res:
                    try:
                        shutil.copy2(latest_backup, GADGETS_FILE)
                        messagebox.showinfo("Success", "Data restored successfully from backup.")
                        return restored_data
                    except Exception as restore_err:
                        messagebox.showerror("Restore Error", f"Failed to restore backup: {restore_err}")

            messagebox.showerror(
                "Critical Data Error",
                f"gadgets.json is corrupted and could not be restored from backup!\nError: {e}{backup_note}\n\n"
                f"Please check the file manually."
            )
            return []

    def validate_length_and_digit(self, P, max_len):
        """Validates entry input for max length and numeric digits."""
        max_l = int(max_len)
        if len(P) <= max_l and (P.isdigit() or P == ""):
            return True
        return False

    def setup_ui(self):
        print("[LOG 6.1] Creating settings bar...", flush=True)
        top_frame = tk.Frame(self)
        top_frame.pack(fill="x", padx=10, pady=5)

        self.always_top_var = tk.BooleanVar(value=False)
        tk.Checkbutton(top_frame, text="Always on Top", variable=self.always_top_var, command=self.toggle_always_top).pack(side="left")

        tk.Label(top_frame, text="Opacity:").pack(side="left", padx=(10, 2))
        self.alpha_scale = tk.Scale(top_frame, from_=0.3, to=1.0, resolution=0.1, orient="horizontal", command=self.change_alpha)
        self.alpha_scale.set(1.0)
        self.alpha_scale.pack(side="left")

        print("[LOG 6.2] Creating capture button...", flush=True)
        btn_capture = tk.Button(self, text="Capture Screen (or press 'x')", bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), command=self.start_capture)
        btn_capture.pack(fill="x", padx=10, pady=5)

        print("[LOG 6.3] Creating form frame...", flush=True)
        form_frame = tk.LabelFrame(self, text=" Gadget Details ")
        form_frame.pack(fill="both", expand=True, padx=10, pady=5)

        vcmd_2 = (self.register(lambda P: self.validate_length_and_digit(P, 2)), '%P')
        vcmd_3 = (self.register(lambda P: self.validate_length_and_digit(P, 3)), '%P')

        se_frame = tk.Frame(form_frame)
        se_frame.pack(fill="x", pady=5)

        tk.Label(se_frame, text="S:").pack(side="left")
        self.season_entry = tk.Entry(se_frame, width=3, validate="key", validatecommand=vcmd_3)
        self.season_entry.insert(0, "1")
        self.season_entry.pack(side="left", padx=(2, 8))

        tk.Label(se_frame, text="E:").pack(side="left")
        self.episode_entry = tk.Entry(se_frame, width=3, validate="key", validatecommand=vcmd_3)
        self.episode_entry.insert(0, "1")
        self.episode_entry.pack(side="left", padx=(2, 8))

        tk.Label(se_frame, text="Time:").pack(side="left")
        self.min_entry = tk.Entry(se_frame, width=3, validate="key", validatecommand=vcmd_2)
        self.min_entry.pack(side="left", padx=(2, 1))
        self.min_entry.bind("<KeyRelease>", self.on_min_key_release)

        tk.Label(se_frame, text=":", font=("Arial", 10, "bold")).pack(side="left")

        self.sec_entry = tk.Entry(se_frame, width=3, validate="key", validatecommand=vcmd_2)
        self.sec_entry.pack(side="left", padx=(1, 5))

        print("[LOG 6.4] Creating name and category fields...", flush=True)
        tk.Label(form_frame, text="Gadget Name (Optional):").pack(anchor="w", padx=5, pady=(5, 0))
        self.name_entry = tk.Entry(form_frame)
        self.name_entry.pack(fill="x", padx=5, pady=2)

        tk.Label(form_frame, text="Category:").pack(anchor="w", padx=5, pady=(5, 0))
        cat_names = [f"[{c['id']}] {c['name']}" for c in self.categories_data]
        self.cat_combobox = ttk.Combobox(form_frame, values=cat_names, state="readonly")
        if cat_names:
            self.cat_combobox.current(0)
        self.cat_combobox.pack(fill="x", padx=5, pady=2)
        self.cat_combobox.bind("<Key>", self.on_cat_key_press)

        print("[LOG 6.5] Creating threat level field...", flush=True)
        tk.Label(form_frame, text="Threat Level:").pack(anchor="w", padx=5, pady=(5, 0))
        threat_names = [f"[{t['id']}] {t['name']}" for t in self.threat_levels_data]
        self.threat_combobox = ttk.Combobox(form_frame, values=threat_names, state="readonly")
        if threat_names:
            idx_99 = next((i for i, t in enumerate(self.threat_levels_data) if t["id"] == 99), 0)
            self.threat_combobox.current(idx_99)
        self.threat_combobox.pack(fill="x", padx=5, pady=2)
        self.threat_combobox.bind("<Key>", self.on_threat_key_press)

        self.c137_var = tk.BooleanVar(value=True)
        tk.Checkbutton(form_frame, text="Confirmed C-137 Rick Invention / Usage", variable=self.c137_var).pack(anchor="w", padx=5, pady=5)

        tk.Label(form_frame, text="Description (Optional):").pack(anchor="w", padx=5, pady=(5, 0))
        self.desc_entry = tk.Entry(form_frame)
        self.desc_entry.pack(fill="x", padx=5, pady=2)

        print("[LOG 6.6] Creating timer panel...", flush=True)
        timer_frame = tk.Frame(self, bg="#263238", bd=1, relief="ridge")
        timer_frame.pack(fill="x", padx=10, pady=(6, 3))

        initial_status = "Work Duration:" if self.timer_running else "Paused:"
        initial_color = "#80D8FF" if self.timer_running else "#FFE082"
        initial_btn_text = "Pause" if self.timer_running else "Start"
        initial_btn_bg = "#37474F" if self.timer_running else "#4E342E"

        self.timer_label = tk.Label(
            timer_frame,
            text=f"{initial_status} {self.format_time_str(self.total_work_seconds)}",
            font=("Arial", 9, "bold"),
            fg=initial_color,
            bg="#263238"
        )
        self.timer_label.pack(side="left", padx=8, pady=3)

        self.btn_toggle_timer = tk.Button(
            timer_frame,
            text=initial_btn_text,
            font=("Arial", 8, "bold"),
            bg=initial_btn_bg,
            fg="#ECEFF1",
            activebackground="#455A64",
            activeforeground="white",
            bd=0,
            padx=8,
            pady=1,
            cursor="hand2",
            command=self.toggle_timer
        )
        self.btn_toggle_timer.pack(side="right", padx=6, pady=2)

        print("[LOG 6.7] Creating action buttons...", flush=True)
        btn_save = tk.Button(self, text="SAVE GADGET", bg="#2196F3", fg="white", font=("Arial", 11, "bold"), command=self.save_gadget)
        btn_save.pack(fill="x", padx=10, pady=3)

        self.btn_git = tk.Button(self, text="Push to GitHub", bg="#9C27B0", fg="white", font=("Arial", 10), command=self.git_push)
        self.btn_git.pack(fill="x", padx=10, pady=3)

        print("[LOG 6.8] Adding status bar and keybindings...", flush=True)
        self.status_bar = tk.Label(self, text="Waiting for capture (press 'x')", bd=1, relief="sunken", anchor="w", fg="red")
        self.status_bar.pack(side="bottom", fill="x")

        # Local Tkinter Keybindings for 'x' and 'X'
        self.bind_all("<Key-x>", self.on_local_x_press)
        self.bind_all("<Key-X>", self.on_local_x_press)
        print("[LOG 6.9] All setup_ui sub-steps finished.", flush=True)

    def on_local_x_press(self, event=None):
        if self.is_capturing:
            return
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox)):
            return
        self.start_capture()

    def on_cat_key_press(self, event):
        key = event.char
        mapping = {
            '1': 0,
            '2': 1,
            '3': 2,
            '4': 3,
            '5': 4,
            '6': 5,
            '7': 6,
            '8': 7,
            '9': 8,
            '0': 0
        }
        if key in mapping:
            idx = mapping[key]
            if idx < len(self.categories_data):
                self.cat_combobox.current(idx)
                return "break"

    def on_threat_key_press(self, event):
        key = event.char
        mapping = {
            '1': 0,
            '2': 1,
            '3': 2,
            '4': 3,
            '5': 4,
            '6': 5,
            '7': 6,
            '9': 6,
            '0': 0
        }
        if key in mapping:
            idx = mapping[key]
            if idx < len(self.threat_levels_data):
                self.threat_combobox.current(idx)
                return "break"

    def on_min_key_release(self, event):
        """Auto-jumps cursor to seconds entry when 2 digits are entered in minutes."""
        if event.keysym in ("Tab", "BackSpace", "Left", "Right"):
            return
        val = self.min_entry.get().strip()
        if len(val) >= 2:
            self.sec_entry.focus_set()
            self.sec_entry.selection_range(0, tk.END)

    def toggle_always_top(self):
        self.attributes("-topmost", self.always_top_var.get())

    def change_alpha(self, val):
        self.attributes("-alpha", float(val))

    def load_timer_data(self):
        default_seconds = 6 * 3600 + 22 * 60
        if not os.path.exists(WORK_TIMER_FILE):
            return default_seconds, True
        try:
            with open(WORK_TIMER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                sec = data.get("total_seconds", default_seconds)
                running = data.get("is_running", True)
                return sec, running
        except Exception:
            return default_seconds, True

    def save_timer_data(self):
        try:
            with open(WORK_TIMER_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "total_seconds": self.total_work_seconds,
                    "is_running": self.timer_running
                }, f, indent=2)
        except Exception:
            pass

    def format_time_str(self, total_seconds):
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"

    def update_timer_tick(self):
        if self.timer_running:
            self.total_work_seconds += 1
            self.timer_label.config(
                text=f"Work Duration: {self.format_time_str(self.total_work_seconds)}",
                fg="#80D8FF"
            )
            if self.total_work_seconds % 5 == 0:
                self.save_timer_data()
        self.after(1000, self.update_timer_tick)

    def toggle_timer(self):
        if self.timer_running:
            self.timer_running = False
            self.btn_toggle_timer.config(text="Start", bg="#4E342E", fg="#FFECB3")
            self.timer_label.config(
                text=f"Paused: {self.format_time_str(self.total_work_seconds)}",
                fg="#FFE082"
            )
        else:
            self.timer_running = True
            self.btn_toggle_timer.config(text="Pause", bg="#37474F", fg="#ECEFF1")
            self.timer_label.config(
                text=f"Work Duration: {self.format_time_str(self.total_work_seconds)}",
                fg="#80D8FF"
            )
        self.save_timer_data()

    def auto_resume_timer(self):
        if not self.timer_running:
            self.toggle_timer()

    def on_closing(self):
        print("[LOG] Saving data and closing application safely...", flush=True)
        try:
            self.save_timer_data()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        sys.exit(0)

    def update_status(self, text, color="black"):
        self.status_bar.config(text=text, fg=color)

    def start_capture(self):
        if self.is_capturing:
            return
        self.is_capturing = True
        self.after(100, self.capture_flow)

    def capture_flow(self):
        try:
            self.iconify()  # Minimize window during capture
            self.update()
            time.sleep(0.2)

            # Grab background screen image once
            screen_img = ImageGrab.grab()

            # Step 1: Full Scene
            tool1 = SnippingTool("1/2: Draw FULL SCENE region (Cancel: ESC / Right Click)", screen_img=screen_img)
            img1 = tool1.get_image()
            if not img1:
                self.deiconify()
                self.update_status("Scene capture cancelled.", "red")
                return
            self.full_img = img1

            # Step 2: Focus Gadget
            tool2 = SnippingTool("2/2: Draw GADGET FOCUS region (Cancel: ESC / Right Click)", screen_img=screen_img)
            img2 = tool2.get_image()
            if not img2:
                self.deiconify()
                self.update_status("Gadget focus capture cancelled.", "red")
                return
            self.focus_img = img2

            self.deiconify()
            self.update_status("Images captured! Fill the form and click Save.", "green")
        finally:
            self.is_capturing = False

    def start_hotkey_listener(self):
        # Native Tkinter keybindings for 'x' / 'X' are active in setup_ui (bind_all)
        pass

    def get_next_tag_id(self):
        max_num = 0
        for g in self.gadgets_data:
            try:
                num = int(g["id"].replace("tag#", ""))
                if num > max_num:
                    max_num = num
            except ValueError:
                continue
        return f"tag#{max_num + 1:03d}"

    def check_duplicate_name(self, name):
        if not name:
            return False
        for g in self.gadgets_data:
            if g.get("name") and g["name"].strip().lower() == name.strip().lower():
                return True
        return False

    def validate_inputs(self):
        """Validates user inputs and formats timestamp to 'MM:SS'."""
        try:
            season = int(self.season_entry.get().strip())
            episode = int(self.episode_entry.get().strip())
            if season < 1 or episode < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Season and Episode must be positive integers!")
            return None, None, None

        min_str = self.min_entry.get().strip()
        sec_str = self.sec_entry.get().strip()

        min_val = int(min_str) if min_str else 0
        sec_val = int(sec_str) if sec_str else 0

        if sec_val >= 60:
            min_val += sec_val // 60
            sec_val = sec_val % 60

        timestamp = f"{min_val:02d}:{sec_val:02d}"
        return season, episode, timestamp

    def save_gadget(self):
        if self.full_img is None or self.focus_img is None:
            messagebox.showerror("Error", "Please capture images first by pressing 'x' or clicking Capture Screen!")
            return

        season, episode, timestamp = self.validate_inputs()
        if season is None:
            return

        name = self.name_entry.get().strip() or None
        description = self.desc_entry.get().strip() or None
        c137 = self.c137_var.get()

        cat_idx = self.cat_combobox.current()
        cat_id = self.categories_data[cat_idx]["id"] if cat_idx >= 0 else 7

        threat_idx = self.threat_combobox.current()
        threat_level = self.threat_levels_data[threat_idx]["id"] if threat_idx >= 0 else 99

        # Duplicate Warning
        if name and self.check_duplicate_name(name):
            res = messagebox.askyesno("Duplicate Warning", f"A gadget named '{name}' has already been registered!\nDo you still want to create a new entry?")
            if not res:
                return

        tag_id = self.get_next_tag_id()

        # Paths
        ep_dir = os.path.join(ASSETS_DIR, f"season_{season:02d}", f"episode_{episode:02d}")
        os.makedirs(ep_dir, exist_ok=True)

        full_abs_path = os.path.join(ep_dir, f"{tag_id}_full.png")
        focus_abs_path = os.path.join(ep_dir, f"{tag_id}_focus.png")

        full_rel_path = os.path.relpath(full_abs_path, BASE_DIR).replace("\\", "/")
        focus_rel_path = os.path.relpath(focus_abs_path, BASE_DIR).replace("\\", "/")

        # Save Images
        self.full_img.save(full_abs_path)
        self.focus_img.save(focus_abs_path)

        # Build Entry
        entry = {
            "id": tag_id,
            "name": name,
            "season": season,
            "episode": episode,
            "timestamp": timestamp,
            "category_id": cat_id,
            "threat_level": threat_level,
            "c137_confirmed": c137,
            "description": description,
            "images": {
                "full": full_rel_path,
                "focus": focus_rel_path
            }
        }

        self.gadgets_data.append(entry)
        self.gadgets_data.sort(key=gadget_sort_key)

        # Save Backup before overwriting GADGETS_FILE
        if os.path.exists(GADGETS_FILE):
            try:
                latest_backup = os.path.join(BACKUP_DIR, "gadgets_latest_backup.json")
                shutil.copy2(GADGETS_FILE, latest_backup)
            except Exception:
                pass

        with open(GADGETS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.gadgets_data, f, ensure_ascii=False, indent=2)

        self.auto_resume_timer()

        # Reset Image Buffers & Text Inputs
        self.full_img = None
        self.focus_img = None
        self.name_entry.delete(0, tk.END)
        self.desc_entry.delete(0, tk.END)
        self.min_entry.delete(0, tk.END)
        self.sec_entry.delete(0, tk.END)

        self.update_status(f"{tag_id} saved successfully!", "blue")
        messagebox.showinfo("Success", f"{tag_id} saved to database!")

    def check_and_prompt_git_identity(self):
        res_name = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True)
        res_email = subprocess.run(["git", "config", "user.email"], capture_output=True, text=True)
        if not res_name.stdout.strip() or not res_email.stdout.strip():
            dialog = GitIdentityDialog(self)
            self.wait_window(dialog)
            return dialog.result
        return True

    def git_push(self):
        if not self.check_and_prompt_git_identity():
            self.update_status("Git Push cancelled (Identity required).", "red")
            return

        if self.gadgets_data:
            last_g = self.gadgets_data[-1]
            g_name = last_g.get("name") or last_g.get("id") or "Gadget"
            s_val = last_g.get("season", 1)
            e_val = last_g.get("episode", 1)
            commit_msg = f"add: {g_name} (S{s_val:02d}E{e_val:02d})"
        else:
            season, episode, _ = self.validate_inputs()
            if season is None:
                return
            commit_msg = f"add: gadgets (S{season:02d}E{episode:02d})"

        self.btn_git.config(state="disabled", text="Pushing...")
        self.update_status("Pushing to GitHub, please wait...", "orange")

        def run_git_commands():
            try:
                try:
                    import update_readme
                    update_readme.update_readme()
                except Exception:
                    pass

                status_res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
                has_uncommitted = bool(status_res.stdout.strip())

                unpushed_res = subprocess.run(["git", "log", "@{u}..HEAD", "--oneline"], capture_output=True, text=True)
                has_unpushed = bool(unpushed_res.stdout.strip())

                if not has_uncommitted and not has_unpushed:
                    self.after(0, lambda: messagebox.showinfo("Info", "GitHub is already up to date! No changes to push."))
                    self.after(0, lambda: self.update_status("GitHub is up to date.", "blue"))
                    return

                if has_uncommitted:
                    subprocess.run(["git", "add", "."], check=True, capture_output=True)
                    subprocess.run(["git", "commit", "-m", commit_msg], check=True, capture_output=True)

                subprocess.run(["git", "push"], check=True, capture_output=True)

                self.after(0, lambda: messagebox.showinfo("GitHub Push", f"'{commit_msg}' successfully pushed to GitHub!"))
                self.after(0, lambda: self.update_status("GitHub Push Completed!", "green"))
            except subprocess.CalledProcessError as err:
                err_msg = err.stderr.decode('utf-8', errors='ignore') if err.stderr else str(err)
                if any(k in err_msg for k in ["Author identity unknown", "Please tell me who you are", "unable to auto-detect email address"]):
                    def retry_identity():
                        if self.check_and_prompt_git_identity():
                            self.git_push()
                    self.after(0, retry_identity)
                else:
                    self.after(0, lambda: messagebox.showerror("Git Error", f"Error occurred during push:\n{err_msg}"))
                    self.after(0, lambda: self.update_status("Git Push Failed!", "red"))
            finally:
                self.after(0, lambda: self.btn_git.config(state="normal", text="Push to GitHub"))

        threading.Thread(target=run_git_commands, daemon=True).start()


class GitIdentityDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("GitHub Kimlik Girişi")
        self.geometry("450x290")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = False

        self.update_idletasks()
        try:
            x = parent.winfo_rootx() + (parent.winfo_width() // 2) - 225
            y = parent.winfo_rooty() + (parent.winfo_height() // 2) - 145
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        lbl_header = tk.Label(
            self, text="GitHub Kimlik ve Giriş Bilgileri",
            font=("Arial", 11, "bold"), fg="#333333"
        )
        lbl_header.pack(padx=15, pady=(15, 5), anchor="w")

        lbl_info = tk.Label(
            self, text="Git push işlemi için kullanıcı adınız ve e-postanız gereklidir:",
            justify="left", font=("Arial", 9), fg="#555555"
        )
        lbl_info.pack(padx=15, pady=(0, 10), anchor="w")

        frame_form = tk.Frame(self)
        frame_form.pack(padx=15, pady=5, fill="x")

        tk.Label(frame_form, text="GitHub Kullanıcı Adı:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", pady=5)
        self.ent_name = tk.Entry(frame_form, font=("Arial", 10))
        self.ent_name.grid(row=0, column=1, sticky="ew", pady=5, padx=(10, 0))
        self.ent_name.insert(0, "mrtfff")

        tk.Label(frame_form, text="E-posta Adresi:", font=("Arial", 9, "bold")).grid(row=1, column=0, sticky="w", pady=5)
        self.ent_email = tk.Entry(frame_form, font=("Arial", 10))
        self.ent_email.grid(row=1, column=1, sticky="ew", pady=5, padx=(10, 0))

        frame_form.columnconfigure(1, weight=1)

        self.var_global = tk.BooleanVar(value=True)
        chk_global = tk.Checkbutton(
            self, text="Bu bilgileri tüm projeler için kaydet (--global)",
            variable=self.var_global, font=("Arial", 9)
        )
        chk_global.pack(padx=15, pady=5, anchor="w")

        btn_frame = tk.Frame(self)
        btn_frame.pack(padx=15, pady=(15, 10), fill="x")

        btn_save = tk.Button(
            btn_frame, text="Giriş Yap & Push Et", bg="#9C27B0", fg="white",
            font=("Arial", 10, "bold"), command=self.on_save
        )
        btn_save.pack(side="right", padx=(5, 0))

        btn_cancel = tk.Button(
            btn_frame, text="İptal", bg="#757575", fg="white",
            font=("Arial", 10), command=self.destroy
        )
        btn_cancel.pack(side="right")

    def on_save(self):
        name = self.ent_name.get().strip()
        email = self.ent_email.get().strip()
        if not name or not email:
            messagebox.showwarning("Eksik Bilgi", "Lütfen hem kullanıcı adınızı hem de e-postanızı girin.", parent=self)
            return

        cmd_name = ["git", "config"]
        cmd_email = ["git", "config"]
        if self.var_global.get():
            cmd_name.append("--global")
            cmd_email.append("--global")

        cmd_name.extend(["user.name", name])
        cmd_email.extend(["user.email", email])

        try:
            subprocess.run(cmd_name, check=True)
            subprocess.run(cmd_email, check=True)
            self.result = True
            self.destroy()
        except Exception as e:
            messagebox.showerror("Hata", f"Git ayarları kaydedilemedi:\n{e}", parent=self)


if __name__ == "__main__":
    print("Rick C-137 Gadget Logger starting...", flush=True)
    app = App()
    print("UI active, entering main loop.", flush=True)
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("\n[LOG] Ctrl+C detected. Exiting application safely...", flush=True)
        app.on_closing()