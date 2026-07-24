import os
import json
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
GADGETS_FILE = os.path.join(DATA_DIR, "gadgets.json")
CATEGORIES_FILE = os.path.join(DATA_DIR, "categories.json")
THREAT_LEVELS_FILE = os.path.join(DATA_DIR, "threat_levels.json")
README_FILE = os.path.join(BASE_DIR, "README.md")


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


def generate_stats_markdown():
    if not os.path.exists(GADGETS_FILE):
        gadgets = []
    else:
        with open(GADGETS_FILE, "r", encoding="utf-8") as f:
            gadgets = json.load(f)

    gadgets.sort(key=gadget_sort_key)

    if not os.path.exists(CATEGORIES_FILE):
        categories = []
    else:
        with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
            categories = json.load(f).get("categories", [])

    if not os.path.exists(THREAT_LEVELS_FILE):
        threat_levels = []
    else:
        with open(THREAT_LEVELS_FILE, "r", encoding="utf-8") as f:
            threat_levels = json.load(f).get("threat_levels", [])

    cat_counts = {c["id"]: 0 for c in categories}
    threat_counts = {t["id"]: 0 for t in threat_levels}

    total_gadgets = len(gadgets)
    seasons = sorted(list(set(g.get("season") for g in gadgets if g.get("season") is not None)))

    # Calculate total episodes scanned: sum of maximum episode scanned in each season
    total_episodes_scanned = 0
    for s in seasons:
        eps = [g.get("episode", 0) for g in gadgets if g.get("season") == s and g.get("episode") is not None]
        if eps:
            total_episodes_scanned += max(eps)

    c137_count = 0

    for g in gadgets:
        if g.get("c137_confirmed"):
            c137_count += 1
        
        cid = g.get("category_id")
        if cid in cat_counts:
            cat_counts[cid] += 1
        else:
            cat_counts[cid] = 1

        tid = g.get("threat_level", 99)
        if tid in threat_counts:
            threat_counts[tid] += 1
        else:
            threat_counts[tid] = 1

    CAT_NAME_EN = {
        0: "Handheld Weapon / Device",
        1: "Cybernetic / Body Implant",
        2: "Vehicle / Adaptation",
        3: "Garage / Lab Equipment",
        4: "Wearable Equipment / Armor / Jetpack",
        5: "Biological / Genetic / Chemical Invention",
        6: "Other / Special Invention",
        7: "Unclassified / Unknown",
        8: "Ship-Mounted Device"
    }

    THREAT_NAME_EN = {
        0: "Harmless / Utility",
        1: "Indirect Hazard / Tactical",
        2: "Personal Lethality",
        3: "Area Destruction",
        4: "Planetary Threat",
        5: "Multiversal / Reality Bending",
        99: "Unclassified / Unknown"
    }

    c137_pct = f"{int((c137_count / total_gadgets) * 100)}%" if total_gadgets > 0 else "0%"

    seasons_str = f"**{len(seasons)}**" if seasons else "**0**"
    if len(seasons) == 1:
        seasons_str += f" (Season {next(iter(seasons)):02d})"
    elif len(seasons) > 1:
        seasons_str += f" (Season {min(seasons):02d} - {max(seasons):02d})"

    episodes_str = f"**{total_episodes_scanned}**"

    lines = [
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| Total Registered Inventions | **{total_gadgets}** |",
        f"| Seasons Analyzed | {seasons_str} |",
        f"| Episodes Analyzed | {episodes_str} |",
        f"| Confirmed C-137 Invention Ratio | **{c137_pct}** ({c137_count}/{total_gadgets}) |",
        "",
        "### Category Breakdown"
    ]

    for c in categories:
        cid = c["id"]
        cname = CAT_NAME_EN.get(cid, c["name"])
        count = cat_counts.get(cid, 0)
        lines.append(f"- **{cname}:** {count} items")

    lines.append("")
    lines.append("### Threat Level Breakdown")
    for t in threat_levels:
        tid = t["id"]
        tname = THREAT_NAME_EN.get(tid, t["name"])
        count = threat_counts.get(tid, 0)
        lines.append(f"- **[{tid}] {tname}:** {count} items")

    return "\n".join(lines)


def update_readme():
    if not os.path.exists(README_FILE):
        return

    with open(README_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    stats_md = generate_stats_markdown()
    pattern = r"<!-- STATS:START -->.*?<!-- STATS:END -->"
    replacement = f"<!-- STATS:START -->\n{stats_md}\n<!-- STATS:END -->"

    if re.search(pattern, content, flags=re.DOTALL):
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    else:
        new_content = content + f"\n\n<!-- STATS:START -->\n{stats_md}\n<!-- STATS:END -->"

    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)


if __name__ == "__main__":
    update_readme()
