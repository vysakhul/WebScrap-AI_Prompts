import csv
from pathlib import Path

CSV_PATH = "banana_prompts_data.csv"
IMAGE_DIR = "images"
OUTPUT_HTML = "index.html"

SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def find_image(uuid):
    for ext in SUPPORTED_EXTS:
        p = Path(IMAGE_DIR) / f"{uuid}{ext}"
        if p.exists():
            return p.as_posix()
    return None


def escape_html(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("`", "&#96;")
    )


def main():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    cards_html = []
    data_js = []

    for idx, row in enumerate(rows):
        img = find_image(row["uuid"])
        if not img:
            continue

        title = escape_html(row.get("title", ""))
        prompt = escape_html(row.get("prompt", "No prompt available"))
        access = row.get("access_level", "Unknown")

        cards_html.append(f"""
        <div class="card"
             data-title="{title.lower()}"
             data-prompt="{prompt.lower()}"
             data-access="{access}"
             onclick="openModal({idx})">
            <img src="{img}" loading="lazy">
            <div class="title-pill">{title}</div>
            {"<div class='premium-pill'>★ PREMIUM</div>" if access == "Premium" else ""}
        </div>
        """)

        data_js.append({
            "img": img,
            "title": title,
            "prompt": prompt
        })

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Offline Prompt Gallery</title>
<meta name="viewport" content="width=device-width, initial-scale=1">

<style>
:root {{
    --bg: #f4f6f8;
    --fg: #000;
    --card: #fff;
    --border: #ddd;
}}
.dark {{
    --bg: #242424;
    --fg: #e5e7eb;
    --card: #242424;
    --border: #334155;
}}

body {{
    margin: 0;
    background: var(--bg);
    color: var(--fg);
    font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
}}

.header {{
    display: flex;
    gap: 12px;
    align-items: center;
    padding: 16px 20px;
}}

input, select, button {{
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--card);
    color: var(--fg);
}}

button {{
    cursor: pointer;
}}

.grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 22px;
    padding: 24px;
}}

.card {{
    position: relative;
    border-radius: 22px;
    overflow: hidden;
    cursor: pointer;
    background: var(--card);
    box-shadow: 0 8px 20px rgba(0,0,0,.12);
    transition: transform .25s ease;
}}
.card:hover {{ transform: translateY(-6px); }}

.card img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
}}

.title-pill {{
    position: absolute;
    top: 12px;
    left: 12px;
    background: rgba(0,0,0,.65);
    color: #fff;
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 12px;
    max-width: 80%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}

.premium-pill {{
    position: absolute;
    bottom: 12px;
    left: 12px;
    background: #f59e0b;
    color: #000;
    padding: 5px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
}}

.modal {{
    position: fixed;
    inset: 0;
    display: none;
    background: rgba(0,0,0,.7);
    justify-content: center;
    align-items: center;
    z-index: 999;
}}

.modal-content {{
    background: var(--card);
    width: 92%;
    max-width: 1100px;
    height: 90%;
    border-radius: 22px;
    display: flex;
    overflow: hidden;
    position: relative;
}}

.modal img {{
    width: 55%;
    object-fit: cover;
}}

.modal-right {{
    width: 45%;
    display: flex;
    flex-direction: column;
}}

.modal-header {{
    padding: 20px 56px 12px 24px;
    font-size: 18px;
    font-weight: 600;
    border-bottom: 1px solid var(--border);
}}

.prompt-text {{
    padding: 20px 24px;
    overflow-y: auto;
    overflow-x: hidden;
    white-space: pre-wrap;
    line-height: 1.6;
    font-size: 14px;
    flex: 1;
}}

.modal-close {{
    position: absolute;
    top: 14px;
    right: 18px;
    font-size: 28px;
    cursor: pointer;
    color: var(--fg);
}}
</style>
</head>

<body>

<div class="header">
    <input id="search" placeholder="Search prompts or titles…">
    <select id="filter">
        <option value="All">All</option>
        <option value="Free">Free</option>
        <option value="Premium">Premium</option>
    </select>
    <button onclick="toggleDark()">🌙</button>
</div>

<div class="grid" id="grid">
{''.join(cards_html)}
</div>

<div class="modal" id="modal" onclick="overlayClose(event)">
    <div class="modal-content">
        <div class="modal-close" onclick="closeModal()">×</div>
        <img id="modalImg">
        <div class="modal-right">
            <div class="modal-header" id="modalTitle"></div>
            <div class="prompt-text" id="modalPrompt"></div>
        </div>
    </div>
</div>

<script>
const cards = document.querySelectorAll(".card");
const data = {data_js};
let current = 0;

function openModal(i) {{
    current = i;
    document.getElementById("modal").style.display = "flex";
    render();
}}

function render() {{
    document.getElementById("modalImg").src = data[current].img;
    document.getElementById("modalTitle").textContent = data[current].title;
    document.getElementById("modalPrompt").textContent = data[current].prompt;
}}

function closeModal() {{
    document.getElementById("modal").style.display = "none";
}}

function overlayClose(e) {{
    if (e.target.id === "modal") closeModal();
}}

document.addEventListener("keydown", e => {{
    if (e.key === "Escape") closeModal();
}});

// ---------------- SEARCH + FILTER ----------------

document.getElementById("search").addEventListener("input", applyFilters);
document.getElementById("filter").addEventListener("change", applyFilters);

function applyFilters() {{
    const q = document.getElementById("search").value.toLowerCase();
    const f = document.getElementById("filter").value;

    cards.forEach(c => {{
        const textMatch =
            c.dataset.title.includes(q) ||
            c.dataset.prompt.includes(q);

        const accessMatch =
            f === "All" || c.dataset.access === f;

        c.style.display = (textMatch && accessMatch) ? "block" : "none";
    }});
}}

// ---------------- DARK MODE ----------------

function toggleDark() {{
    document.body.classList.toggle("dark");
    localStorage.dark = document.body.classList.contains("dark");
}}

if (localStorage.dark === "true") {{
    document.body.classList.add("dark");
}}
</script>

</body>
</html>
"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print("[DONE] index.html generated with search, filter, and dark mode")


if __name__ == "__main__":
    main()
