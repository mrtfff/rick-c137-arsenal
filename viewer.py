import os
import json
import sys
import shutil
import time
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk

# Windows DPI Awareness (Ekran Ölçekleme Kaymalarını Önler)
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
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
    """Aletleri Sezon -> Bölüm -> Zaman Kodu -> ID sırasına göre dizer."""
    season = gadget.get("season", 0) or 0
    episode = gadget.get("episode", 0) or 0
    ts_seconds = parse_timestamp_to_seconds(gadget.get("timestamp"))
    return (season, episode, ts_seconds, gadget.get("id", ""))


class ImageViewerModal(tk.Toplevel):
    """Büyütülmüş resim gösterici modal penceresi."""
    def __init__(self, parent, image_path, title_text="Görsel Detayı"):
        super().__init__(parent)
        self.title(title_text)
        self.geometry("900x700")
        self.attributes("-topmost", True)
        
        self.canvas = tk.Canvas(self, bg="#1e1e1e")
        self.canvas.pack(fill="both", expand=True)

        self.image_path = image_path
        self.pil_img = None
        self.tk_img = None

        if os.path.exists(image_path):
            try:
                self.pil_img = Image.open(image_path)
                self.bind("<Configure>", self.on_resize)
                self.bind("<Escape>", lambda e: self.destroy())
            except Exception as e:
                self.canvas.create_text(450, 350, text=f"Görsel açılamadı:\n{e}", fill="white", font=("Arial", 14))
        else:
            self.canvas.create_text(450, 350, text="Görsel dosyası bulunamadı!", fill="red", font=("Arial", 14, "bold"))

    def on_resize(self, event):
        if not self.pil_img:
            return
        cw = event.width
        ch = event.height
        if cw <= 10 or ch <= 10:
            return

        img_w, img_h = self.pil_img.size
        ratio = min(cw / img_w, ch / img_h)
        new_w = max(1, int(img_w * ratio))
        new_h = max(1, int(img_h * ratio))

        resample_filter = getattr(Image, 'Resampling', Image).LANCZOS
        resized = self.pil_img.resize((new_w, new_h), resample_filter)
        self.tk_img = ImageTk.PhotoImage(resized)

        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self.tk_img, anchor="center")


class GadgetViewerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Rick C-137 Gadget Görüntüleyici ve Düzenleyici")
        self.geometry("1100x750")
        self.minsize(950, 600)

        self.categories_data = self.load_categories()
        self.categories_dict = {c["id"]: c["name"] for c in self.categories_data}
        
        self.threat_levels_data = self.load_threat_levels()
        self.threat_levels_dict = {t["id"]: t["name"] for t in self.threat_levels_data}
        
        self.gadgets_data = []

        self.selected_gadget_id = None
        self.full_img_tk = None
        self.focus_img_tk = None
        self.current_full_path = None
        self.current_focus_path = None
        self.unsaved_changes = set()

        self.setup_ui()
        self.reload_data()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # AltGr shortcut to jump to next gadget
        self.bind_all("<Alt_R>", self.select_next_gadget)
        self.bind_all("<ISO_Level3_Shift>", self.select_next_gadget)

    def load_categories(self):
        if not os.path.exists(CATEGORIES_FILE):
            return []
        try:
            with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("categories", [])
        except Exception:
            return []

    def load_threat_levels(self):
        if not os.path.exists(THREAT_LEVELS_FILE):
            return []
        try:
            with open(THREAT_LEVELS_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("threat_levels", [])
        except Exception:
            return []

    def load_gadgets(self):
        if not os.path.exists(GADGETS_FILE):
            return []
        try:
            with open(GADGETS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            messagebox.showerror("Hata", f"gadgets.json okunamadı: {e}")
            return []

    def reload_data(self):
        self.gadgets_data = self.load_gadgets()
        self.update_combobox_values()
        self.apply_filter()

    def update_combobox_values(self):
        cat_names = ["Hepsi"] + [f"[{c['id']}] {c['name']}" for c in self.categories_data]
        self.filter_cat_combobox["values"] = cat_names
        self.filter_cat_combobox.current(0)

        threat_names = ["Hepsi"] + [f"[{t['id']}] {t['name']}" for t in self.threat_levels_data]
        self.filter_threat_combobox["values"] = threat_names
        self.filter_threat_combobox.current(0)

        form_cats = [f"[{c['id']}] {c['name']}" for c in self.categories_data]
        self.cat_combobox["values"] = form_cats

        form_threats = [f"[{t['id']}] {t['name']}" for t in self.threat_levels_data]
        self.threat_combobox["values"] = form_threats

    def setup_ui(self):
        # Master Layout: Left Panel (List & Filter), Right Panel (Preview & Form)
        main_paned = ttk.PanedWindow(self, orient="horizontal")
        main_paned.pack(fill="both", expand=True, padx=5, pady=5)

        # ---------------- LEFT PANEL ----------------
        left_frame = ttk.Frame(main_paned, width=380)
        main_paned.add(left_frame, weight=1)

        # Filter Frame
        filter_frame = ttk.LabelFrame(left_frame, text=" 🔍 Arama ve Filtreleme ", padding=5)
        filter_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(filter_frame, text="Arama:").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.search_entry = ttk.Entry(filter_frame)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        self.search_entry.bind("<KeyRelease>", lambda e: self.apply_filter())

        ttk.Label(filter_frame, text="Kategori:").grid(row=1, column=0, sticky="w", padx=2, pady=2)
        self.filter_cat_combobox = ttk.Combobox(filter_frame, state="readonly")
        self.filter_cat_combobox.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        self.filter_cat_combobox.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        ttk.Label(filter_frame, text="Tehdit Seviyesi:").grid(row=2, column=0, sticky="w", padx=2, pady=2)
        self.filter_threat_combobox = ttk.Combobox(filter_frame, state="readonly")
        self.filter_threat_combobox.grid(row=2, column=1, sticky="ew", padx=2, pady=2)
        self.filter_threat_combobox.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        filter_frame.columnconfigure(1, weight=1)

        # Gadget Treeview
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        columns = ("id", "code", "name")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("id", text="ID")
        self.tree.heading("code", text="Sezon/Bölüm")
        self.tree.heading("name", text="Alet İsmi")

        self.tree.column("id", width=65, anchor="center")
        self.tree.column("code", width=80, anchor="center")
        self.tree.column("name", width=180, anchor="w")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self.on_gadget_selected)

        # Refresh / Count Bar below list
        left_bottom_frame = ttk.Frame(left_frame)
        left_bottom_frame.pack(fill="x", padx=5, pady=5)
        
        btn_refresh = ttk.Button(left_bottom_frame, text="🔄 Yenile", command=self.reload_data)
        btn_refresh.pack(side="left")

        self.count_label = ttk.Label(left_bottom_frame, text="Toplam: 0 alet")
        self.count_label.pack(side="right")

        # ---------------- RIGHT PANEL ----------------
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=3)

        # Image Previews Frame
        img_frame = ttk.LabelFrame(right_frame, text=" 🖼️ Görsel Önizleme (Büyütmek İçin Tıklayın) ", padding=5)
        img_frame.pack(fill="both", expand=True, padx=5, pady=5)

        img_frame.columnconfigure(0, weight=1)
        img_frame.columnconfigure(1, weight=1)
        img_frame.rowconfigure(0, weight=1)

        # Full Scene Image Box
        full_box = ttk.Frame(img_frame)
        full_box.grid(row=0, column=0, sticky="nsew", padx=5, pady=2)

        ttk.Label(full_box, text="1/2: Tam Sahne", font=("Arial", 9, "bold")).pack(anchor="w")
        self.full_img_label = tk.Label(full_box, text="Görsel Yok", bg="#2b2b2b", fg="white", cursor="hand2")
        self.full_img_label.pack(fill="both", expand=True, pady=2)
        self.full_img_label.bind("<Button-1>", lambda e: self.open_modal(self.current_full_path, "Tam Sahne"))

        # Focus Gadget Image Box
        focus_box = ttk.Frame(img_frame)
        focus_box.grid(row=0, column=1, sticky="nsew", padx=5, pady=2)

        ttk.Label(focus_box, text="2/2: Alet Odağı", font=("Arial", 9, "bold")).pack(anchor="w")
        self.focus_img_label = tk.Label(focus_box, text="Görsel Yok", bg="#2b2b2b", fg="white", cursor="hand2")
        self.focus_img_label.pack(fill="both", expand=True, pady=2)
        self.focus_img_label.bind("<Button-1>", lambda e: self.open_modal(self.current_focus_path, "Alet Odağı"))

        # Edit Form Frame
        form_frame = ttk.LabelFrame(right_frame, text=" ✏️ Gadget Bilgilerini Düzenle ", padding=10)
        form_frame.pack(fill="x", padx=5, pady=5)

        form_frame.columnconfigure(1, weight=1)

        # ID & Season / Episode / Timestamp
        row = 0
        ttk.Label(form_frame, text="ID:").grid(row=row, column=0, sticky="w", pady=3)
        self.id_var = tk.StringVar(value="-")
        ttk.Label(form_frame, textvariable=self.id_var, font=("Arial", 10, "bold"), foreground="#2196F3").grid(row=row, column=1, sticky="w", pady=3)

        row += 1
        ttk.Label(form_frame, text="Sezon / Bölüm / Zaman:").grid(row=row, column=0, sticky="w", pady=3)
        se_frame = ttk.Frame(form_frame)
        se_frame.grid(row=row, column=1, sticky="w", pady=3)

        ttk.Label(se_frame, text="S:").pack(side="left")
        self.season_spin = ttk.Spinbox(se_frame, from_=1, to=999, width=4)
        self.season_spin.pack(side="left", padx=(2, 8))

        ttk.Label(se_frame, text="E:").pack(side="left")
        self.episode_spin = ttk.Spinbox(se_frame, from_=1, to=999, width=4)
        self.episode_spin.pack(side="left", padx=(2, 8))

        ttk.Label(se_frame, text="Zaman (MM:SS):").pack(side="left")
        self.time_entry = ttk.Entry(se_frame, width=8)
        self.time_entry.pack(side="left", padx=(2, 2))

        # Name
        row += 1
        ttk.Label(form_frame, text="Alet İsmi:").grid(row=row, column=0, sticky="w", pady=3)
        self.name_entry = ttk.Entry(form_frame)
        self.name_entry.grid(row=row, column=1, sticky="ew", pady=3)

        # Category
        row += 1
        ttk.Label(form_frame, text="Kategori:").grid(row=row, column=0, sticky="w", pady=3)
        self.cat_combobox = ttk.Combobox(form_frame, state="readonly")
        self.cat_combobox.grid(row=row, column=1, sticky="ew", pady=3)
        self.cat_combobox.bind("<Key>", self.on_cat_key_press)
        self.cat_combobox.bind("<<ComboboxSelected>>", lambda e: self.save_current_form_to_memory())

        # Threat Level
        row += 1
        ttk.Label(form_frame, text="Tehdit Seviyesi:").grid(row=row, column=0, sticky="w", pady=3)
        self.threat_combobox = ttk.Combobox(form_frame, state="readonly")
        self.threat_combobox.grid(row=row, column=1, sticky="ew", pady=3)
        self.threat_combobox.bind("<Key>", self.on_threat_key_press)
        self.threat_combobox.bind("<<ComboboxSelected>>", lambda e: self.save_current_form_to_memory())

        # C-137 Checkbox
        row += 1
        self.c137_var = tk.BooleanVar(value=True)
        self.c137_check = ttk.Checkbutton(form_frame, text="C-137 Rick İcadı / Kullanımı Onaylı", variable=self.c137_var)
        self.c137_check.grid(row=row, column=1, sticky="w", pady=3)

        # Description
        row += 1
        ttk.Label(form_frame, text="Açıklama:").grid(row=row, column=0, sticky="nw", pady=3)
        self.desc_text = tk.Text(form_frame, height=3, wrap="word", font=("Segoe UI", 9))
        self.desc_text.grid(row=row, column=1, sticky="ew", pady=3)

        # Action Buttons Frame
        btn_frame = ttk.Frame(right_frame)
        btn_frame.pack(fill="x", padx=5, pady=5)

        self.btn_save = tk.Button(btn_frame, text="💾 DEĞİŞİKLİKLERİ KAYDET", bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), command=self.save_changes)
        self.btn_save.pack(side="left", fill="x", expand=True, padx=2)

        self.btn_delete = tk.Button(btn_frame, text="🗑️ KAYDI SİL", bg="#F44336", fg="white", font=("Arial", 10, "bold"), command=self.delete_gadget)
        self.btn_delete.pack(side="left", padx=2)

        self.btn_git = tk.Button(btn_frame, text="🚀 GitHub'a Push Et", bg="#9C27B0", fg="white", font=("Arial", 10, "bold"), command=self.git_push)
        self.btn_git.pack(side="right", padx=2)

        # Status Bar
        self.status_bar = ttk.Label(self, text="Hazır", relief="sunken", anchor="w")
        self.status_bar.pack(side="bottom", fill="x")

    def update_status(self, message, color="black"):
        self.status_bar.config(text=message, foreground=color)

    def apply_filter(self):
        search_query = self.search_entry.get().strip().lower()
        selected_cat_str = self.filter_cat_combobox.get()
        selected_threat_str = self.filter_threat_combobox.get()
        
        target_cat_id = None
        if selected_cat_str and selected_cat_str != "Hepsi":
            try:
                target_cat_id = int(selected_cat_str.split("]")[0].replace("[", ""))
            except ValueError:
                target_cat_id = None

        target_threat_id = None
        if selected_threat_str and selected_threat_str != "Hepsi":
            try:
                target_threat_id = int(selected_threat_str.split("]")[0].replace("[", ""))
            except ValueError:
                target_threat_id = None

        # Clear Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Chronological sort: Season -> Episode -> Timestamp -> ID
        sorted_gadgets = sorted(self.gadgets_data, key=gadget_sort_key)

        count = 0
        for g in sorted_gadgets:
            gid = g.get("id", "")
            gname = g.get("name") or "(İsimsiz)"
            s = g.get("season", 0)
            e = g.get("episode", 0)
            code = f"S{s:02d}E{e:02d}"
            cat_id = g.get("category_id")
            threat_id = g.get("threat_level", 99)
            desc = g.get("description") or ""

            # Category Filter
            if target_cat_id is not None and cat_id != target_cat_id:
                continue

            # Threat Level Filter
            if target_threat_id is not None and threat_id != target_threat_id:
                continue

            # Search Filter
            if search_query:
                combined_text = f"{gid} {gname} {code} {desc} {self.categories_dict.get(cat_id, '')} {self.threat_levels_dict.get(threat_id, '')}".lower()
                if search_query not in combined_text:
                    continue

            self.tree.insert("", "end", iid=gid, values=(gid, code, gname))
            count += 1

        self.count_label.config(text=f"Gösterilen: {count} / {len(self.gadgets_data)}")

        # Select first item if available and none selected
        children = self.tree.get_children()
        if children:
            if self.selected_gadget_id in children:
                self.tree.selection_set(self.selected_gadget_id)
            else:
                self.tree.selection_set(children[0])
        else:
            self.clear_form()

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
                self.save_current_form_to_memory()
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
                self.save_current_form_to_memory()
                return "break"

    def save_current_form_to_memory(self):
        if not self.selected_gadget_id:
            return
        gadget = next((g for g in self.gadgets_data if g["id"] == self.selected_gadget_id), None)
        if not gadget:
            return

        try:
            season_str = self.season_spin.get().strip()
            episode_str = self.episode_spin.get().strip()
            season = int(season_str) if season_str else 1
            episode = int(episode_str) if episode_str else 1
        except Exception:
            return

        timestamp = self.time_entry.get().strip() or "00:00"
        name = self.name_entry.get().strip() or None
        desc = self.desc_text.get("1.0", tk.END).strip() or None
        c137 = self.c137_var.get()

        cat_idx = self.cat_combobox.current()
        cat_id = self.categories_data[cat_idx]["id"] if cat_idx >= 0 else 7

        threat_idx = self.threat_combobox.current()
        threat_level = self.threat_levels_data[threat_idx]["id"] if threat_idx >= 0 else 99

        changed = (
            gadget.get("season") != season or
            gadget.get("episode") != episode or
            gadget.get("timestamp") != timestamp or
            gadget.get("name") != name or
            gadget.get("category_id") != cat_id or
            gadget.get("threat_level") != threat_level or
            gadget.get("c137_confirmed") != c137 or
            gadget.get("description") != desc
        )

        if changed:
            gadget["season"] = season
            gadget["episode"] = episode
            gadget["timestamp"] = timestamp
            gadget["name"] = name
            gadget["category_id"] = cat_id
            gadget["threat_level"] = threat_level
            gadget["c137_confirmed"] = c137
            gadget["description"] = desc
            
            self.unsaved_changes.add(self.selected_gadget_id)

            code = f"S{season:02d}E{episode:02d}"
            gname = name or "(İsimsiz)"
            if self.tree.exists(self.selected_gadget_id):
                self.tree.item(self.selected_gadget_id, values=(self.selected_gadget_id, code, gname))

    def select_next_gadget(self, event=None):
        """AltGr tuşuna basıldığında listedeki bir sonraki alete geçer."""
        focused = self.focus_get()
        # Sadece serbest metin girilen alanlarda (Entry/Text) Türkçe karakter kombinasyonları için AltGr serbest bırakılır.
        # Combobox kutularında AltGr aktif çalışır.
        if isinstance(focused, (tk.Entry, tk.Text, ttk.Entry, ttk.Spinbox)) and not isinstance(focused, ttk.Combobox):
            return

        was_threat_focused = (focused == self.threat_combobox)

        # Mevcut form verisini hafızaya al
        self.save_current_form_to_memory()

        children = self.tree.get_children()
        if not children:
            return

        if self.selected_gadget_id in children:
            idx = children.index(self.selected_gadget_id)
            next_idx = (idx + 1) % len(children)
        else:
            next_idx = 0

        next_id = children[next_idx]
        self.tree.selection_set(next_id)
        self.tree.see(next_id)
        
        if was_threat_focused:
            self.threat_combobox.focus_set()
        else:
            self.tree.focus(next_id)

    def on_gadget_selected(self, event):
        # Auto-stage pending changes in active form before loading new selection
        self.save_current_form_to_memory()

        selected = self.tree.selection()
        if not selected:
            self.clear_form()
            return

        gid = selected[0]
        self.selected_gadget_id = gid

        gadget = next((g for g in self.gadgets_data if g["id"] == gid), None)
        if not gadget:
            self.clear_form()
            return

        # Populate Form
        self.id_var.set(gadget.get("id", "-"))
        
        self.season_spin.delete(0, tk.END)
        self.season_spin.insert(0, str(gadget.get("season", 1)))

        self.episode_spin.delete(0, tk.END)
        self.episode_spin.insert(0, str(gadget.get("episode", 1)))

        self.time_entry.delete(0, tk.END)
        self.time_entry.insert(0, gadget.get("timestamp", ""))

        self.name_entry.delete(0, tk.END)
        self.name_entry.insert(0, gadget.get("name") or "")

        cat_id = gadget.get("category_id", 7)
        cat_idx = next((i for i, c in enumerate(self.categories_data) if c["id"] == cat_id), 0)
        self.cat_combobox.current(cat_idx)

        threat_id = gadget.get("threat_level", 99)
        threat_idx = next((i for i, t in enumerate(self.threat_levels_data) if t["id"] == threat_id), 0)
        self.threat_combobox.current(threat_idx)

        self.c137_var.set(gadget.get("c137_confirmed", True))

        self.desc_text.delete("1.0", tk.END)
        if gadget.get("description"):
            self.desc_text.insert("1.0", gadget["description"])

        # Load Images
        imgs = gadget.get("images", {})
        full_rel = imgs.get("full", "")
        focus_rel = imgs.get("focus", "")

        self.current_full_path = os.path.join(BASE_DIR, full_rel) if full_rel else None
        self.current_focus_path = os.path.join(BASE_DIR, focus_rel) if focus_rel else None

        self.load_thumbnail(self.current_full_path, self.full_img_label, "full")
        self.load_thumbnail(self.current_focus_path, self.focus_img_label, "focus")

        self.update_status(f"Seçildi: {gid} ({gadget.get('name') or 'İsimsiz'})", "blue")

    def load_thumbnail(self, path, label_widget, img_type):
        if not path or not os.path.exists(path):
            label_widget.config(image="", text="Görsel Bulunamadı", bg="#333333", fg="#ff6b6b")
            return

        try:
            img = Image.open(path)
            img.thumbnail((320, 220), getattr(Image, 'Resampling', Image).LANCZOS)
            photo = ImageTk.PhotoImage(img)

            if img_type == "full":
                self.full_img_tk = photo
            else:
                self.focus_img_tk = photo

            label_widget.config(image=photo, text="", bg="#1e1e1e")
        except Exception as e:
            label_widget.config(image="", text=f"Hata: {e}", bg="#333333", fg="#ff6b6b")

    def open_modal(self, image_path, title_suffix):
        if not image_path or not os.path.exists(image_path):
            messagebox.showwarning("Uyarı", "Görsel dosyası bulunamadı!")
            return
        gid = self.selected_gadget_id or ""
        ImageViewerModal(self, image_path, f"{gid} - {title_suffix}")

    def clear_form(self):
        self.selected_gadget_id = None
        self.id_var.set("-")
        self.season_spin.delete(0, tk.END)
        self.episode_spin.delete(0, tk.END)
        self.time_entry.delete(0, tk.END)
        self.name_entry.delete(0, tk.END)
        self.desc_text.delete("1.0", tk.END)
        self.full_img_label.config(image="", text="Görsel Seçilmedi", bg="#2b2b2b", fg="white")
        self.focus_img_label.config(image="", text="Görsel Seçilmedi", bg="#2b2b2b", fg="white")
        self.current_full_path = None
        self.current_focus_path = None

    def save_changes(self):
        # Stage current active form inputs
        self.save_current_form_to_memory()

        if not self.unsaved_changes and not self.selected_gadget_id:
            messagebox.showwarning("Uyarı", "Lütfen önce düzenlenecek bir gadget seçin!")
            return

        # Backup & Save to File
        if os.path.exists(GADGETS_FILE):
            try:
                os.makedirs(BACKUP_DIR, exist_ok=True)
                latest_backup = os.path.join(BACKUP_DIR, "gadgets_latest_backup.json")
                shutil.copy2(GADGETS_FILE, latest_backup)
            except Exception:
                pass

        try:
            # Chronological sort before writing to file
            self.gadgets_data.sort(key=gadget_sort_key)

            with open(GADGETS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.gadgets_data, f, ensure_ascii=False, indent=2)

            saved_tags = sorted(list(self.unsaved_changes)) if self.unsaved_changes else ([self.selected_gadget_id] if self.selected_gadget_id else [])
            self.unsaved_changes.clear()

            tag_list_str = ", ".join(saved_tags)
            self.update_status(f"✅ Değişiklikler kaydedildi: {tag_list_str}", "green")
            
            # Automatically update README statistics
            try:
                import update_readme
                update_readme.update_readme()
            except Exception:
                pass

            messagebox.showinfo("Başarılı", f"Veritabanına başarıyla kaydedilen aletler:\n{tag_list_str}")
        except Exception as err:
            messagebox.showerror("Kaydetme Hatası", f"Dosya kaydedilemedi: {err}")

    def on_closing(self):
        self.save_current_form_to_memory()
        if self.unsaved_changes:
            items_lines = []
            for gid in sorted(self.unsaved_changes):
                g = next((item for item in self.gadgets_data if item["id"] == gid), None)
                g_name = (g.get("name") if g else None) or "İsimsiz"
                items_lines.append(f"• {gid} ({g_name})")
            
            msg = (
                "Aşağıdaki alet(ler) üzerinde değişiklik yaptınız fakat henüz kaydetmediniz:\n\n"
                + "\n".join(items_lines) +
                "\n\nKaydetmeden çıkmak istediğinize emin misiniz?"
            )
            confirm = messagebox.askyesno("Kaydedilmemiş Değişiklikler Var!", msg, icon="warning")
            if not confirm:
                return

        self.destroy()

    def delete_gadget(self):
        if not self.selected_gadget_id:
            messagebox.showwarning("Uyarı", "Lütfen önce silinecek bir gadget seçin!")
            return

        gid = self.selected_gadget_id
        gadget = next((g for g in self.gadgets_data if g["id"] == gid), None)
        if not gadget:
            return

        confirm = messagebox.askyesno(
            "Kaydı Sil",
            f"'{gid}' ({gadget.get('name') or 'İsimsiz'}) kaydını veritabanından silmek istediğinize emin misiniz?"
        )
        if not confirm:
            return

        # Ask if image files should also be deleted
        delete_files = messagebox.askyesno(
            "Görselleri de Sil",
            f"Bu alete ait ekran görüntüsü dosyalarını da diskten silmek istiyor musunuz?"
        )

        if delete_files:
            imgs = gadget.get("images", {})
            for key in ("full", "focus"):
                rel_path = imgs.get(key)
                if rel_path:
                    abs_path = os.path.join(BASE_DIR, rel_path)
                    if os.path.exists(abs_path):
                        try:
                            os.remove(abs_path)
                        except Exception as e:
                            print(f"Görsel silinemedi {abs_path}: {e}")

        # Remove from list
        self.gadgets_data = [g for g in self.gadgets_data if g["id"] != gid]

        # Backup & Save
        if os.path.exists(GADGETS_FILE):
            try:
                os.makedirs(BACKUP_DIR, exist_ok=True)
                latest_backup = os.path.join(BACKUP_DIR, "gadgets_latest_backup.json")
                shutil.copy2(GADGETS_FILE, latest_backup)
            except Exception:
                pass

        try:
            with open(GADGETS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.gadgets_data, f, ensure_ascii=False, indent=2)

            # Automatically update README statistics
            try:
                import update_readme
                update_readme.update_readme()
            except Exception:
                pass

            self.update_status(f"🗑️ {gid} silindi.", "red")
            self.selected_gadget_id = None
            self.apply_filter()
            messagebox.showinfo("Silindi", f"{gid} kaydı başarıyla silindi!")
        except Exception as err:
            messagebox.showerror("Hata", f"Silme işlemi kaydedilemedi: {err}")

    def git_push(self):
        if self.gadgets_data:
            last_g = self.gadgets_data[-1]
            g_name = last_g.get("name") or last_g.get("id") or "Gadget"
            s_val = last_g.get("season", 1)
            e_val = last_g.get("episode", 1)
            commit_msg = f"update: {g_name} (S{s_val:02d}E{e_val:02d})"
        else:
            commit_msg = "update: gadgets via viewer"

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
    app = GadgetViewerApp()
    app.mainloop()
