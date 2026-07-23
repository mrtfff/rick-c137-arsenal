import os
import json
import sys
import subprocess
import threading
import shutil
import time
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageGrab
from pynput import keyboard

# Windows DPI Awareness (Ekran Ölçekleme Kaymalarını Önler)
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
WORK_TIMER_FILE = os.path.join(DATA_DIR, "work_timer.json")


def initialize_environment():
    """Klasörler ve varsayılan JSON dosyaları yoksa otomatik oluşturur."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # Categories JSON Auto-creation
    if not os.path.exists(CATEGORIES_FILE):
        default_cats = {
            "categories": [
                { "id": 0, "name": "Elde Taşınır Silah / Cihaz" },
                { "id": 1, "name": "Sibernetik / Vücut İmplantı" },
                { "id": 2, "name": "Araç / Taşıt / Uyarlama" },
                { "id": 3, "name": "Garaj / Laboratuvar Ekipmanı" },
                { "id": 4, "name": "Giyilebilir Ekipman / Zırh / Jetpack" },
                { "id": 5, "name": "Biyolojik / Genetik / Kimyasal İcat" },
                { "id": 6, "name": "Diğer / Özel İcat" },
                { "id": 7, "name": "Emin Değilim / Bilinmiyor" }
            ]
        }
        with open(CATEGORIES_FILE, "w", encoding="utf-8") as f:
            json.dump(default_cats, f, ensure_ascii=False, indent=2)

    # Gadgets JSON Auto-creation
    if not os.path.exists(GADGETS_FILE):
        with open(GADGETS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


# Uygulama başlamadan önce dosya ortamını garantile
initialize_environment()


class SnippingTool:
    """Screen sniper overlay for selecting regions."""
    def __init__(self, prompt_text="Alan Seçin"):
        self.root = tk.Toplevel()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-alpha", 0.3)
        self.root.attributes("-topmost", True)
        self.root.config(cursor="cross")

        self.canvas = tk.Canvas(self.root, cursor="cross", bg="grey")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.create_text(
            self.root.winfo_screenwidth() // 2, 60,
            text=prompt_text, font=("Helvetica", 22, "bold"), fill="red"
        )

        # Mouse Dinleyicileri
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        
        # İptal Mekanizmaları (ESC veya Sağ Tık)
        self.root.bind("<Escape>", self.on_escape)
        self.canvas.bind("<Escape>", self.on_escape)
        self.root.bind("<Button-3>", self.on_escape)
        self.canvas.bind("<Button-3>", self.on_escape)

        # Klavye Odağını Zorla
        self.root.lift()
        self.root.focus_force()
        self.canvas.focus_set()

        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None
        self.rect = None

    def on_escape(self, event=None):
        """ESC tuşuna veya Sağ Tık'a basıldığında kırpmayı iptal eder."""
        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None
        self.root.destroy()

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline='red', width=2)

    def on_move_press(self, event):
        cur_x, cur_y = (event.x, event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        self.end_x = event.x
        self.end_y = event.y
        self.root.destroy()

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
        super().__init__()
        self.title("Rick C-137 Gadget Logger")
        self.geometry("460x620")
        self.attributes("-topmost", True)

        self.full_img = None
        self.focus_img = None
        self.is_capturing = False

        self.categories_data = self.load_categories()
        self.gadgets_data = self.load_gadgets()

        # Work Timer Initialization
        self.total_work_seconds, self.timer_running = self.load_timer_data()

        self.setup_ui()
        self.start_hotkey_listener()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(1000, self.update_timer_tick)

    def load_categories(self):
        try:
            with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)["categories"]
        except Exception as e:
            if os.path.exists(CATEGORIES_FILE):
                messagebox.showwarning("Kategori Hatası", f"categories.json okunamadı: {e}")
            return []

    def load_gadgets(self):
        if not os.path.exists(GADGETS_FILE):
            return []
        try:
            with open(GADGETS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    raise ValueError("gadgets.json veri formatı liste [] olmalıdır.")
                return data
        except Exception as e:
            # Bozuk dosyayı yedekle
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            corrupted_backup = os.path.join(BACKUP_DIR, f"gadgets_corrupted_{timestamp}.json")
            try:
                shutil.copy2(GADGETS_FILE, corrupted_backup)
                backup_note = f"\nBozuk dosya şuraya yedeklendi:\n{corrupted_backup}"
            except Exception:
                backup_note = ""

            # Son çalışan yedeği kontrol et
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
                    "Veri Okuma Hatası",
                    f"gadgets.json okunamadı veya bozulmuş!\nHata: {e}{backup_note}\n\n"
                    f"Son çalışan yedekten veriler geri yüklensin mi?"
                )
                if res:
                    try:
                        shutil.copy2(latest_backup, GADGETS_FILE)
                        messagebox.showinfo("Başarılı", "Veriler son yedekten başarıyla geri yüklendi.")
                        return restored_data
                    except Exception as restore_err:
                        messagebox.showerror("Geri Yükleme Hatası", f"Yedekten yükleme başarısız: {restore_err}")

            messagebox.showerror(
                "Kritik Veri Okuma Hatası",
                f"gadgets.json dosyası bozulmuş ve otomatik yedekten yüklenemedi!\nHata: {e}{backup_note}\n\n"
                f"Lütfen dosyayı manuel olarak kontrol edin!"
            )
            return []

    def validate_length_and_digit(self, P, max_len):
        """Kutulara yazılırken sadece rakam ve maksimum uzunluk kontrolü yapar."""
        max_l = int(max_len)
        if len(P) <= max_l and (P.isdigit() or P == ""):
            return True
        return False

    def setup_ui(self):
        # Settings Bar
        top_frame = tk.Frame(self)
        top_frame.pack(fill="x", padx=10, pady=5)

        self.always_top_var = tk.BooleanVar(value=True)
        tk.Checkbutton(top_frame, text="Her Zaman Üstte", variable=self.always_top_var, command=self.toggle_always_top).pack(side="left")

        tk.Label(top_frame, text="Şeffaflık:").pack(side="left", padx=(10, 2))
        self.alpha_scale = tk.Scale(top_frame, from_=0.3, to=1.0, resolution=0.1, orient="horizontal", command=self.change_alpha)
        self.alpha_scale.set(1.0)
        self.alpha_scale.pack(side="left")

        # Capture Button
        btn_capture = tk.Button(self, text="📸 Ekran Yakala (veya 'x'e bas)", bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), command=self.start_capture)
        btn_capture.pack(fill="x", padx=10, pady=5)

        # Form Inputs
        form_frame = tk.LabelFrame(self, text=" Gadget Detayları ")
        form_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Register Validation Commands
        vcmd_2 = (self.register(lambda P: self.validate_length_and_digit(P, 2)), '%P')
        vcmd_3 = (self.register(lambda P: self.validate_length_and_digit(P, 3)), '%P')

        # Season / Episode / Time Frame
        se_frame = tk.Frame(form_frame)
        se_frame.pack(fill="x", pady=5)

        # Season (Maks 3 Hane)
        tk.Label(se_frame, text="S:").pack(side="left")
        self.season_entry = tk.Entry(se_frame, width=3, validate="key", validatecommand=vcmd_3)
        self.season_entry.insert(0, "1")
        self.season_entry.pack(side="left", padx=(2, 8))

        # Episode (Maks 3 Hane)
        tk.Label(se_frame, text="E:").pack(side="left")
        self.episode_entry = tk.Entry(se_frame, width=3, validate="key", validatecommand=vcmd_3)
        self.episode_entry.insert(0, "1")
        self.episode_entry.pack(side="left", padx=(2, 8))

        # Time Inputs: [ DK (Maks 2) ] : [ SN (Maks 2) ]
        tk.Label(se_frame, text="Zaman:").pack(side="left")
        self.min_entry = tk.Entry(se_frame, width=3, validate="key", validatecommand=vcmd_2)
        self.min_entry.pack(side="left", padx=(2, 1))
        self.min_entry.bind("<KeyRelease>", self.on_min_key_release)

        tk.Label(se_frame, text=":", font=("Arial", 10, "bold")).pack(side="left")

        self.sec_entry = tk.Entry(se_frame, width=3, validate="key", validatecommand=vcmd_2)
        self.sec_entry.pack(side="left", padx=(1, 5))

        # Name
        tk.Label(form_frame, text="Alet İsmi (Boş Bırakılabilir):").pack(anchor="w", padx=5, pady=(5, 0))
        self.name_entry = tk.Entry(form_frame)
        self.name_entry.pack(fill="x", padx=5, pady=2)

        # Category
        tk.Label(form_frame, text="Kategori:").pack(anchor="w", padx=5, pady=(5, 0))
        cat_names = [f"[{c['id']}] {c['name']}" for c in self.categories_data]
        self.cat_combobox = ttk.Combobox(form_frame, values=cat_names, state="readonly")
        if cat_names:
            self.cat_combobox.current(0)
        self.cat_combobox.pack(fill="x", padx=5, pady=2)

        # C-137 Checkbox
        self.c137_var = tk.BooleanVar(value=True)
        tk.Checkbutton(form_frame, text="C-137 Rick İcadı / Kullanımı Onaylı", variable=self.c137_var).pack(anchor="w", padx=5, pady=5)

        # Description
        tk.Label(form_frame, text="Açıklama (Boş Bırakılabilir):").pack(anchor="w", padx=5, pady=(5, 0))
        self.desc_entry = tk.Entry(form_frame)
        self.desc_entry.pack(fill="x", padx=5, pady=2)

        # Work Timer Bar (Placing right above KAYDET button)
        timer_frame = tk.Frame(self, bg="#263238", bd=1, relief="ridge")
        timer_frame.pack(fill="x", padx=10, pady=(6, 3))

        initial_status = "⏱️ Çalışma Süresi:" if self.timer_running else "⏸️ Duraklatıldı:"
        initial_color = "#80D8FF" if self.timer_running else "#FFE082"
        initial_btn_text = "⏸️ Durdur" if self.timer_running else "▶️ Başlat"
        initial_btn_bg = "#37474F" if self.timer_running else "#4E342E"

        self.timer_label = tk.Label(
            timer_frame,
            text=f"{initial_status} {self.format_time_str(self.total_work_seconds)}",
            font=("Segoe UI", 9, "bold"),
            fg=initial_color,
            bg="#263238"
        )
        self.timer_label.pack(side="left", padx=8, pady=3)

        self.btn_toggle_timer = tk.Button(
            timer_frame,
            text=initial_btn_text,
            font=("Segoe UI", 8, "bold"),
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

        # Action Buttons
        btn_save = tk.Button(self, text="💾 KAYDET", bg="#2196F3", fg="white", font=("Arial", 11, "bold"), command=self.save_gadget)
        btn_save.pack(fill="x", padx=10, pady=3)

        self.btn_git = tk.Button(self, text="🚀 GitHub'a Push Et", bg="#9C27B0", fg="white", font=("Arial", 10), command=self.git_push)
        self.btn_git.pack(fill="x", padx=10, pady=3)

        # Status Bar (UX Display)
        self.status_bar = tk.Label(self, text="🔴 Görsel Bekleniyor ('x' tuşuna basın)", bd=1, relief="sunken", anchor="w", fg="red")
        self.status_bar.pack(side="bottom", fill="x")

    def on_min_key_release(self, event):
        """Dakika kutusuna 2 rakam girildiğinde imleç otomatik Saniye kutusuna atlar."""
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
        # 19:00 -> 01:22 = 6 saat 22 dakika (22920 saniye)
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
        return f"{hours:02d}sa {minutes:02d}dk {seconds:02d}sn"

    def update_timer_tick(self):
        if self.timer_running:
            self.total_work_seconds += 1
            self.timer_label.config(
                text=f"⏱️ Çalışma Süresi: {self.format_time_str(self.total_work_seconds)}",
                fg="#80D8FF"
            )
            if self.total_work_seconds % 5 == 0:
                self.save_timer_data()
        self.after(1000, self.update_timer_tick)

    def toggle_timer(self):
        if self.timer_running:
            self.timer_running = False
            self.btn_toggle_timer.config(text="▶️ Başlat", bg="#4E342E", fg="#FFECB3")
            self.timer_label.config(
                text=f"⏸️ Duraklatıldı: {self.format_time_str(self.total_work_seconds)}",
                fg="#FFE082"
            )
        else:
            self.timer_running = True
            self.btn_toggle_timer.config(text="⏸️ Durdur", bg="#37474F", fg="#ECEFF1")
            self.timer_label.config(
                text=f"⏱️ Çalışma Süresi: {self.format_time_str(self.total_work_seconds)}",
                fg="#80D8FF"
            )
        self.save_timer_data()

    def auto_resume_timer(self):
        if not self.timer_running:
            self.toggle_timer()

    def on_closing(self):
        self.save_timer_data()
        self.destroy()

    def update_status(self, text, color="black"):
        self.status_bar.config(text=text, fg=color)

    def start_capture(self):
        if self.is_capturing:
            return
        self.is_capturing = True
        self.after(100, self.capture_flow)

    def capture_flow(self):
        try:
            self.iconify()  # Capture sırasında pencereyi simge durumuna küçült
            self.update()

            # Step 1: Full Scene
            tool1 = SnippingTool("1/2: TAM SAHNE alanını çizin (İptal: ESC / Sağ Tık)")
            bbox1 = tool1.get_bbox()
            if not bbox1:
                self.deiconify()
                self.update_status("❌ Sahne seçimi iptal edildi.", "red")
                return
            self.full_img = ImageGrab.grab(bbox1)

            # Step 2: Focus Gadget
            tool2 = SnippingTool("2/2: Sadece ALETİN ODAK alanını çizin (İptal: ESC / Sağ Tık)")
            bbox2 = tool2.get_bbox()
            if not bbox2:
                self.deiconify()
                self.update_status("❌ Alet odak seçimi iptal edildi.", "red")
                return
            self.focus_img = ImageGrab.grab(bbox2)

            self.deiconify()
            self.update_status("🟢 Görseller Hazır! Formu doldurup Kaydet'e basın.", "green")
        finally:
            self.is_capturing = False

    def start_hotkey_listener(self):
        def on_press(key):
            try:
                if key.char and key.char.lower() == 'x':
                    if self.is_capturing:
                        return
                    # Metin kutularında yazarken 'x' basılırsa ekran yakalamayı çalıştırma
                    focused = self.focus_get()
                    if isinstance(focused, (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox)):
                        return
                    self.start_capture()
            except AttributeError:
                pass

        listener = keyboard.Listener(on_press=on_press)
        listener.daemon = True
        listener.start()

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
        """Kullanıcı girdilerini doğrular ve zamanı 'MM:SS' formatına getirir."""
        try:
            season = int(self.season_entry.get().strip())
            episode = int(self.episode_entry.get().strip())
            if season < 1 or episode < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Hata", "Sezon ve Bölüm pozitif bir tam sayı olmalıdır!")
            return None, None, None

        # Dakika ve Saniye Ayrıştırma
        min_str = self.min_entry.get().strip()
        sec_str = self.sec_entry.get().strip()

        min_val = int(min_str) if min_str else 0
        sec_val = int(sec_str) if sec_str else 0

        # Saniye 60 veya üzeriyse dakikaya devret
        if sec_val >= 60:
            min_val += sec_val // 60
            sec_val = sec_val % 60

        timestamp = f"{min_val:02d}:{sec_val:02d}"
        return season, episode, timestamp

    def save_gadget(self):
        if self.full_img is None or self.focus_img is None:
            messagebox.showerror("Hata", "Lütfen önce 'x'e basarak görselleri yakalayın!")
            return

        season, episode, timestamp = self.validate_inputs()
        if season is None:
            return

        name = self.name_entry.get().strip() or None
        description = self.desc_entry.get().strip() or None
        c137 = self.c137_var.get()

        cat_idx = self.cat_combobox.current()
        cat_id = self.categories_data[cat_idx]["id"] if cat_idx >= 0 else 7

        # Duplicate Warning
        if name and self.check_duplicate_name(name):
            res = messagebox.askyesno("Mükerrer Uyarısı", f"'{name}' isimli alet daha önce kaydedilmiş!\nSadece İLK defa görünen aletleri kaydediyoruz.\nYine de yeni bir kayıt açmak istiyor musunuz?")
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
            "c137_confirmed": c137,
            "description": description,
            "images": {
                "full": full_rel_path,
                "focus": focus_rel_path
            }
        }

        self.gadgets_data.append(entry)

        # Save Backup before overwriting GADGETS_FILE
        if os.path.exists(GADGETS_FILE):
            try:
                latest_backup = os.path.join(BACKUP_DIR, "gadgets_latest_backup.json")
                shutil.copy2(GADGETS_FILE, latest_backup)
            except Exception:
                pass

        with open(GADGETS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.gadgets_data, f, ensure_ascii=False, indent=2)

        # Veri kaydı yapıldığında duraklatılmışsa sayacı otomatik devam ettir
        self.auto_resume_timer()

        # Reset Image Buffers & Text Inputs
        self.full_img = None
        self.focus_img = None
        self.name_entry.delete(0, tk.END)
        self.desc_entry.delete(0, tk.END)
        self.min_entry.delete(0, tk.END)
        self.sec_entry.delete(0, tk.END)

        self.update_status(f"✅ {tag_id} başarıyla kaydedildi!", "blue")
        messagebox.showinfo("Başarılı", f"{tag_id} veritabanına kaydedildi!")

    def git_push(self):
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

        # Non-blocking Threading Implementation
        self.btn_git.config(state="disabled", text="⏳ Push Ediliyor...")
        self.update_status("🔄 GitHub'a push ediliyor, lütfen bekleyin...", "orange")

        def run_git_commands():
            try:
                try:
                    import update_readme
                    update_readme.update_readme()
                except Exception:
                    pass

                # Değişiklik var mı kontrol et
                status_res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
                has_uncommitted = bool(status_res.stdout.strip())

                # Push edilmemiş yerel commit var mı kontrol et
                unpushed_res = subprocess.run(["git", "log", "@{u}..HEAD", "--oneline"], capture_output=True, text=True)
                has_unpushed = bool(unpushed_res.stdout.strip())

                if not has_uncommitted and not has_unpushed:
                    self.after(0, lambda: messagebox.showinfo("Bilgi", "GitHub zaten güncel! Gönderilecek yeni bir değişiklik bulunmuyor."))
                    self.after(0, lambda: self.update_status("ℹ️ Değişiklik yok. GitHub zaten güncel.", "blue"))
                    return

                if has_uncommitted:
                    subprocess.run(["git", "add", "."], check=True, capture_output=True)
                    subprocess.run(["git", "commit", "-m", commit_msg], check=True, capture_output=True)

                subprocess.run(["git", "push"], check=True, capture_output=True)

                self.after(0, lambda: messagebox.showinfo("GitHub Push", f"'{commit_msg}' başarıyla GitHub'a gönderildi!"))
                self.after(0, lambda: self.update_status("✅ GitHub Push Tamamlandı!", "green"))
            except subprocess.CalledProcessError as err:
                err_msg = err.stderr.decode('utf-8', errors='ignore') if err.stderr else str(err)
                self.after(0, lambda: messagebox.showerror("Git Hata", f"Push sırasında hata oluştu:\n{err_msg}"))
                self.after(0, lambda: self.update_status("❌ Git Push Başarısız!", "red"))
            finally:
                self.after(0, lambda: self.btn_git.config(state="normal", text="🚀 GitHub'a Push Et"))

        threading.Thread(target=run_git_commands, daemon=True).start()


if __name__ == "__main__":
    app = App()
    app.mainloop()