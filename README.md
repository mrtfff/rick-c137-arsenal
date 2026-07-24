# Rick C-137 Gadget Logger & Multiverse Arsenal

A high-precision manual screen-capture logging and archiving system designed to manually snapshot, categorize, and record all inventions, weapons, and experimental technologies used by Rick Sanchez (Dimension C-137) while watching the show.

---

## Multiverse Arsenal Metrics

<!-- STATS:START -->
| Metric | Value |
| :--- | :--- |
| Total Registered Inventions | **71** |
| Seasons Analyzed | **2** (Season 01 - 02) |
| Episodes Analyzed | **17** |
| Confirmed C-137 Invention Ratio | **97%** (69/71) |

### Category Breakdown
- **Handheld Weapon / Device:** 29 items
- **Cybernetic / Body Implant:** 0 items
- **Vehicle / Adaptation:** 3 items
- **Garage / Lab Equipment:** 6 items
- **Wearable Equipment / Armor / Jetpack:** 12 items
- **Biological / Genetic / Chemical Invention:** 6 items
- **Other / Special Invention:** 7 items
- **Unclassified / Unknown:** 0 items
- **Ship-Mounted Device:** 8 items

### Threat Level Breakdown
- **[0] Harmless / Utility:** 23 items
- **[1] Indirect Hazard / Tactical:** 17 items
- **[2] Personal Lethality:** 20 items
- **[3] Area Destruction:** 6 items
- **[4] Planetary Threat:** 1 items
- **[5] Multiversal / Reality Bending:** 0 items
- **[99] Unclassified / Unknown:** 4 items
<!-- STATS:END -->

---

## Architecture & System Modules

### 1. Main Logger Interface (`main.py`)
Primary screen capture overlay and cataloging interface used during episode analysis to snapshot and record gadgets in real time.

```bash
python main.py
```

| Control | Action |
| :--- | :--- |
| **`x` Key** | Triggers dual-region screen capture overlay (bypassed when typing in text inputs). |
| **Capture Step 1** | Draw bounding box for full scene context (ESC or Right-Click to cancel). |
| **Capture Step 2** | Draw targeted bounding box specifically around the gadget/weapon. |
| **Form Entry** | Specify Season, Episode, Timestamp (`MM:SS`), Category, Threat Level, and Save. |

---

### 2. Arsenal Viewer & Editor (`viewer.py`)
Interactive dashboard for exploring, filtering, multi-item editing, and synchronizing catalog data.

```bash
python viewer.py
```

* **Live Multi-Criteria Search:** Instant filtering by ID (`tag#003`), name, episode code (`S01E01`), description, category, or threat level.
* **Dual Preview & Inspection:** Side-by-side view of full scene and focus crops with interactive full-screen zoom modal.
* **Batch Staged Editing:** Modify multiple items sequentially in memory and save all changes to disk in a single atomic operation.
* **Keyboard Speed Classification:** Use number keys (`1` - `6`, `7`/`9`/`0`) to set threat level or category instantly, and press `AltGr` to jump directly to the next gadget while preserving control focus.
* **GitHub Integration:** One-click repository commit and push workflow with automated stat updates.

---

### 3. Automated Readme Stats Generator (`update_readme.py`)
Dynamically parses `data/gadgets.json` and updates metric tables in `README.md`.

```bash
python update_readme.py
```

---

## Data Schema (`data/gadgets.json`)

Screen capture assets are organized under `assets/season_XX/episode_YY/`. Each gadget entry strictly adheres to the following JSON structure:

```json
{
  "id": "tag#003",
  "name": "portal gun",
  "season": 1,
  "episode": 1,
  "timestamp": "07:36",
  "category_id": 0,
  "threat_level": 1,
  "c137_confirmed": true,
  "description": "Can travel anywhere and everywhere",
  "images": {
    "full": "assets/season_01/episode_01/tag#003_full.png",
    "focus": "assets/season_01/episode_01/tag#003_focus.png"
  }
}
```

---

## License

This project is licensed under the [MIT License](LICENSE).
