import os
import json
import sys
import shutil
import time
import signal
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk

# Windows DPI Awareness (Prevents Display Scaling Offset)
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
    """Sorts gadgets chronologically: Season -> Episode -> Timestamp -> ID."""
    season = gadget.get("season", 0) or 0
    episode = gadget.get("episode", 0) or 0
    ts_seconds = parse_timestamp_to_seconds(gadget.get("timestamp"))
    return (season, episode, ts_seconds, gadget.get("id", ""))


class ImageViewerModal(tk.Toplevel):
    """Enlarged Image Inspector Modal Window."""
    def __init__(self, parent, image_path, title_text="Image Details"):
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
                self.canvas.create_text(450, 350, text=f"Failed to open image:\n{e}", fill="white", font=("Arial", 14))
        else:
            self.canvas.create_text(450, 350, text="Image file not found!", fill="red", font=("Arial", 14, "bold"))

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
        self.title("Rick C-137 Gadget Viewer & Editor")
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

        # Signal Handlers for Ctrl+C
        self.after(500, self.check_signal)
        self.setup_signal_handlers()

    def check_signal(self):
        self.after(500, self.check_signal)

    def setup_signal_handlers(self):
        def handle_sigint(sig, frame):
            print("\n[LOG] Ctrl+C detected. Exiting application safely...", flush=True)
            self.after(0, self.on_closing)

        try:
            signal.signal(signal.SIGINT, handle_sigint)
        except Exception:
            pass

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
            messagebox.showerror("Error", f"Failed to read gadgets.json: {e}")
            return []

    def reload_data(self):
        self.gadgets_data = self.load_gadgets()
        self.update_combobox_values()
        self.apply_filter()

    def update_combobox_values(self):
        cat_names = ["All"] + [f"[{c['id']}] {c['name']}" for c in self.categories_data]
        self.filter_cat_combobox["values"] = cat_names
        self.filter_cat_combobox.current(0)

        threat_names = ["All"] + [f"[{t['id']}] {t['name']}" for t in self.threat_levels_data]
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
        filter_frame = ttk.LabelFrame(left_frame, text=" Search & Filter ", padding=5)
        filter_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(filter_frame, text="Search:").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.search_entry = ttk.Entry(filter_frame)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        self.search_entry.bind("<KeyRelease>", lambda e: self.apply_filter())

        ttk.Label(filter_frame, text="Category:").grid(row=1, column=0, sticky="w", padx=2, pady=2)
        self.filter_cat_combobox = ttk.Combobox(filter_frame, state="readonly")
        self.filter_cat_combobox.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        self.filter_cat_combobox.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        ttk.Label(filter_frame, text="Threat Level:").grid(row=2, column=0, sticky="w", padx=2, pady=2)
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
        self.tree.heading("code", text="Season/Ep")
        self.tree.heading("name", text="Gadget Name")

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
        
        btn_refresh = ttk.Button(left_bottom_frame, text="Refresh", command=self.reload_data)
        btn_refresh.pack(side="left")

        self.count_label = ttk.Label(left_bottom_frame, text="Total: 0 items")
        self.count_label.pack(side="right")

        # ---------------- RIGHT PANEL ----------------
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=3)

        # Image Previews Frame
        img_frame = ttk.LabelFrame(right_frame, text=" Image Preview (Click to Enlarge) ", padding=5)
        img_frame.pack(fill="both", expand=True, padx=5, pady=5)

        img_frame.columnconfigure(0, weight=1)
        img_frame.columnconfigure(1, weight=1)
        img_frame.rowconfigure(0, weight=1)

        # Full Scene Image Box
        full_box = ttk.Frame(img_frame)
        full_box.grid(row=0, column=0, sticky="nsew", padx=5, pady=2)

        ttk.Label(full_box, text="1/2: Full Scene", font=("Arial", 9, "bold")).pack(anchor="w")
        self.full_img_label = tk.Label(full_box, text="No Image", bg="#2b2b2b", fg="white", cursor="hand2")
        self.full_img_label.pack(fill="both", expand=True, pady=2)
        self.full_img_label.bind("<Button-1>", lambda e: self.open_modal(self.current_full_path, "Full Scene"))

        # Focus Gadget Image Box
        focus_box = ttk.Frame(img_frame)
        focus_box.grid(row=0, column=1, sticky="nsew", padx=5, pady=2)

        ttk.Label(focus_box, text="2/2: Gadget Focus", font=("Arial", 9, "bold")).pack(anchor="w")
        self.focus_img_label = tk.Label(focus_box, text="No Image", bg="#2b2b2b", fg="white", cursor="hand2")
        self.focus_img_label.pack(fill="both", expand=True, pady=2)
        self.focus_img_label.bind("<Button-1>", lambda e: self.open_modal(self.current_focus_path, "Gadget Focus"))

        # Edit Form Frame
        form_frame = ttk.LabelFrame(right_frame, text=" Edit Gadget Details ", padding=10)
        form_frame.pack(fill="x", padx=5, pady=5)

        form_frame.columnconfigure(1, weight=1)

        # ID & Season / Episode / Timestamp
        row = 0
        ttk.Label(form_frame, text="ID:").grid(row=row, column=0, sticky="w", pady=3)
        self.id_var = tk.StringVar(value="-")
        ttk.Label(form_frame, textvariable=self.id_var, font=("Arial", 10, "bold"), foreground="#2196F3").grid(row=row, column=1, sticky="w", pady=3)

        row += 1
        ttk.Label(form_frame, text="Season / Episode / Time:").grid(row=row, column=0, sticky="w", pady=3)
        se_frame = ttk.Frame(form_frame)
        se_frame.grid(row=row, column=1, sticky="w", pady=3)

        ttk.Label(se_frame, text="S:").pack(side="left")
        self.season_spin = ttk.Spinbox(se_frame, from_=1, to=999, width=4)
        self.season_spin.pack(side="left", padx=(2, 8))

        ttk.Label(se_frame, text="E:").pack(side="left")
        self.episode_spin = ttk.Spinbox(se_frame, from_=1, to=999, width=4)
        self.episode_spin.pack(side="left", padx=(2, 8))

        ttk.Label(se_frame, text="Timestamp (MM:SS):").pack(side="left")
        self.time_entry = ttk.Entry(se_frame, width=8)
        self.time_entry.pack(side="left", padx=(2, 2))

        # Name
        row += 1
        ttk.Label(form_frame, text="Gadget Name:").grid(row=row, column=0, sticky="w", pady=3)
        self.name_entry = ttk.Entry(form_frame)
        self.name_entry.grid(row=row, column=1, sticky="ew", pady=3)

        # Category
        row += 1
        ttk.Label(form_frame, text="Category:").grid(row=row, column=0, sticky="w", pady=3)
        self.cat_combobox = ttk.Combobox(form_frame, state="readonly")
        self.cat_combobox.grid(row=row, column=1, sticky="ew", pady=3)
        self.cat_combobox.bind("<Key>", self.on_cat_key_press)
        self.cat_combobox.bind("<<ComboboxSelected>>", lambda e: self.save_current_form_to_memory())

        # Threat Level
        row += 1
        ttk.Label(form_frame, text="Threat Level:").grid(row=row, column=0, sticky="w", pady=3)
        self.threat_combobox = ttk.Combobox(form_frame, state="readonly")
        self.threat_combobox.grid(row=row, column=1, sticky="ew", pady=3)
        self.threat_combobox.bind("<Key>", self.on_threat_key_press)
        self.threat_combobox.bind("<<ComboboxSelected>>", lambda e: self.save_current_form_to_memory())

        # C-137 Checkbox
        row += 1
        self.c137_var = tk.BooleanVar(value=True)
        self.c137_check = ttk.Checkbutton(form_frame, text="Confirmed C-137 Rick Invention / Usage", variable=self.c137_var)
        self.c137_check.grid(row=row, column=1, sticky="w", pady=3)

        # Description
        row += 1
        ttk.Label(form_frame, text="Description:").grid(row=row, column=0, sticky="nw", pady=3)
        self.desc_text = tk.Text(form_frame, height=3, wrap="word", font=("Arial", 9))
        self.desc_text.grid(row=row, column=1, sticky="ew", pady=3)

        # Action Buttons Frame
        btn_frame = ttk.Frame(right_frame)
        btn_frame.pack(fill="x", padx=5, pady=5)

        self.btn_save = tk.Button(btn_frame, text="SAVE CHANGES", bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), command=self.save_changes)
        self.btn_save.pack(side="left", fill="x", expand=True, padx=2)

        self.btn_delete = tk.Button(btn_frame, text="DELETE GADGET", bg="#F44336", fg="white", font=("Arial", 10, "bold"), command=self.delete_gadget)
        self.btn_delete.pack(side="left", padx=2)

        self.btn_git = tk.Button(btn_frame, text="Push to GitHub", bg="#9C27B0", fg="white", font=("Arial", 10, "bold"), command=self.git_push)
        self.btn_git.pack(side="right", padx=2)

        # Status Bar
        self.status_bar = ttk.Label(self, text="Ready", relief="sunken", anchor="w")
        self.status_bar.pack(side="bottom", fill="x")

    def update_status(self, message, color="black"):
        self.status_bar.config(text=message, foreground=color)

    def apply_filter(self):
        search_query = self.search_entry.get().strip().lower()
        selected_cat_str = self.filter_cat_combobox.get()
        selected_threat_str = self.filter_threat_combobox.get()
        
        target_cat_id = None
        if selected_cat_str and selected_cat_str != "All":
            try:
                target_cat_id = int(selected_cat_str.split("]")[0].replace("[", ""))
            except ValueError:
                target_cat_id = None

        target_threat_id = None
        if selected_threat_str and selected_threat_str != "All":
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
            gname = g.get("name") or "(Unnamed)"
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

        self.count_label.config(text=f"Showing: {count} / {len(self.gadgets_data)}")

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
            gname = name or "(Unnamed)"
            if self.tree.exists(self.selected_gadget_id):
                self.tree.item(self.selected_gadget_id, values=(self.selected_gadget_id, code, gname))

    def select_next_gadget(self, event=None):
        """Advances selection to the next gadget in the list when AltGr is pressed."""
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Text, ttk.Entry, ttk.Spinbox)) and not isinstance(focused, ttk.Combobox):
            return

        was_threat_focused = (focused == self.threat_combobox)
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

        self.update_status(f"Selected: {gid} ({gadget.get('name') or 'Unnamed'})", "blue")

    def load_thumbnail(self, path, label_widget, img_type):
        if not path or not os.path.exists(path):
            label_widget.config(image="", text="Image Not Found", bg="#333333", fg="#ff6b6b")
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
            label_widget.config(image="", text=f"Error: {e}", bg="#333333", fg="#ff6b6b")

    def open_modal(self, image_path, title_suffix):
        if not image_path or not os.path.exists(image_path):
            messagebox.showwarning("Warning", "Image file not found!")
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
        self.full_img_label.config(image="", text="No Image Selected", bg="#2b2b2b", fg="white")
        self.focus_img_label.config(image="", text="No Image Selected", bg="#2b2b2b", fg="white")
        self.current_full_path = None
        self.current_focus_path = None

    def save_changes(self):
        self.save_current_form_to_memory()

        if not self.unsaved_changes and not self.selected_gadget_id:
            messagebox.showwarning("Warning", "Please select a gadget to edit first!")
            return

        if os.path.exists(GADGETS_FILE):
            try:
                os.makedirs(BACKUP_DIR, exist_ok=True)
                latest_backup = os.path.join(BACKUP_DIR, "gadgets_latest_backup.json")
                shutil.copy2(GADGETS_FILE, latest_backup)
            except Exception:
                pass

        try:
            self.gadgets_data.sort(key=gadget_sort_key)

            with open(GADGETS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.gadgets_data, f, ensure_ascii=False, indent=2)

            saved_tags = sorted(list(self.unsaved_changes)) if self.unsaved_changes else ([self.selected_gadget_id] if self.selected_gadget_id else [])
            self.unsaved_changes.clear()

            tag_list_str = ", ".join(saved_tags)
            self.update_status(f"Changes saved: {tag_list_str}", "green")
            
            try:
                import update_readme
                update_readme.update_readme()
            except Exception:
                pass

            messagebox.showinfo("Success", f"Successfully saved gadgets to database:\n{tag_list_str}")
        except Exception as err:
            messagebox.showerror("Save Error", f"Failed to save file: {err}")

    def on_closing(self):
        print("[LOG] Closing Arsenal Viewer cleanly...", flush=True)
        self.save_current_form_to_memory()
        if self.unsaved_changes:
            items_lines = []
            for gid in sorted(self.unsaved_changes):
                g = next((item for item in self.gadgets_data if item["id"] == gid), None)
                g_name = (g.get("name") if g else None) or "Unnamed"
                items_lines.append(f"• {gid} ({g_name})")
            
            msg = (
                "You have unsaved changes on the following gadget(s):\n\n"
                + "\n".join(items_lines) +
                "\n\nAre you sure you want to exit without saving?"
            )
            confirm = messagebox.askyesno("Unsaved Changes", msg, icon="warning")
            if not confirm:
                return

        try:
            self.destroy()
        except Exception:
            pass
        sys.exit(0)

    def delete_gadget(self):
        if not self.selected_gadget_id:
            messagebox.showwarning("Warning", "Please select a gadget to delete first!")
            return

        gid = self.selected_gadget_id
        gadget = next((g for g in self.gadgets_data if g["id"] == gid), None)
        if not gadget:
            return

        confirm = messagebox.askyesno(
            "Delete Record",
            f"Are you sure you want to delete '{gid}' ({gadget.get('name') or 'Unnamed'}) from the database?"
        )
        if not confirm:
            return

        delete_files = messagebox.askyesno(
            "Delete Images",
            "Do you also want to delete the image files associated with this gadget from disk?"
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
                            print(f"Failed to delete image {abs_path}: {e}")

        self.gadgets_data = [g for g in self.gadgets_data if g["id"] != gid]

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

            try:
                import update_readme
                update_readme.update_readme()
            except Exception:
                pass

            self.update_status(f"{gid} deleted.", "red")
            self.selected_gadget_id = None
            self.apply_filter()
            messagebox.showinfo("Deleted", f"Record {gid} was successfully deleted!")
        except Exception as err:
            messagebox.showerror("Error", f"Failed to save deletion: {err}")

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
            commit_msg = f"update: {g_name} (S{s_val:02d}E{e_val:02d})"
        else:
            commit_msg = "update: gadgets via viewer"

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
    print("Rick C-137 Arsenal Viewer starting...", flush=True)
    app = GadgetViewerApp()
    print("Viewer UI active, entering main loop.", flush=True)
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("\n[LOG] Ctrl+C detected. Exiting Viewer safely...", flush=True)
        app.on_closing()
