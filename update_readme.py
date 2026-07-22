import os
import json
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
GADGETS_FILE = os.path.join(DATA_DIR, "gadgets.json")
CATEGORIES_FILE = os.path.join(DATA_DIR, "categories.json")
README_FILE = os.path.join(BASE_DIR, "README.md")


def generate_stats_markdown():
    if not os.path.exists(GADGETS_FILE):
        gadgets = []
    else:
        with open(GADGETS_FILE, "r", encoding="utf-8") as f:
            gadgets = json.load(f)

    if not os.path.exists(CATEGORIES_FILE):
        categories = []
    else:
        with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
            categories = json.load(f).get("categories", [])

    cat_counts = {c["id"]: 0 for c in categories}

    total_gadgets = len(gadgets)
    seasons = set()
    episodes = set()
    c137_count = 0

    for g in gadgets:
        s = g.get("season")
        e = g.get("episode")
        if s is not None:
            seasons.add(s)
        if s is not None and e is not None:
            episodes.add((s, e))
        if g.get("c137_confirmed"):
            c137_count += 1
        cid = g.get("category_id")
        if cid in cat_counts:
            cat_counts[cid] += 1
        else:
            cat_counts[cid] = 1

    c137_pct = f"%{int((c137_count / total_gadgets) * 100)}" if total_gadgets > 0 else "%0"

    seasons_str = f"**{len(seasons)}**" if seasons else "**0**"
    if len(seasons) == 1:
        seasons_str += f" (Sezon {next(iter(seasons)):02d})"
    elif len(seasons) > 1:
        seasons_str += f" (Sezon {min(seasons):02d} - {max(seasons):02d})"

    episodes_str = f"**{len(episodes)}**"

    lines = [
        "| Metrik | Deger |",
        "| :--- | :--- |",
        f"| Toplam Kayitli Icat / Silah | **{total_gadgets}** |",
        f"| Taranan Sezon Sayisi | {seasons_str} |",
        f"| Taranan Bölüm Sayisi | {episodes_str} |",
        f"| C-137 Onayli Icat Orani | **{c137_pct}** ({c137_count}/{total_gadgets}) |",
        "",
        "### Kategori Dagilimi"
    ]

    for c in categories:
        cid = c["id"]
        cname = c["name"]
        count = cat_counts.get(cid, 0)
        lines.append(f"- **{cname}:** {count} adet")

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
