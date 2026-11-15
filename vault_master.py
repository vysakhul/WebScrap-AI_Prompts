import os
import csv
import json
import subprocess
import sys
from pathlib import Path
from PIL import Image
from typing import Dict

# --- Directories ---
BASE_DIR = Path(__file__).parent
MEIGEN_DIR = BASE_DIR / "Meigen"
BANANA_DIR = BASE_DIR / "BananaPrompts"
PERSONAL_DIR = BASE_DIR / "Personal"


def run_script(folder_path, script_name):
    script_path = folder_path / script_name
    if not script_path.exists():
        print(f"\n[!] Error: Cannot find {script_name} in {folder_path.name}/")
        return

    print(f"\n=== Launching {script_name} ===")
    subprocess.run(["python", script_name], cwd=folder_path)
    print(f"=== {script_name} Closed ===\n")


# ==========================================
# COMPRESSION / OPTIMIZATION ENGINE
# ==========================================
def optimize_storage():
    print("\n=== Storage Optimizer ===")
    print("Scanning Meigen and Banana image folders...")

    target_folders = [MEIGEN_DIR / "images", BANANA_DIR / "images"]
    size_threshold = 500 * 1024  # 500 KB
    max_width = 1024

    large_files = []
    initial_total_size = 0

    for folder in target_folders:
        if not folder.exists(): continue
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp"]:
            for file_path in folder.glob(ext):
                size = file_path.stat().st_size
                if size > size_threshold:
                    large_files.append(file_path)
                    initial_total_size += size

    if not large_files:
        print("All images are already optimized (under 500 KB).")
        return

    print(f"Found {len(large_files)} images larger than 500KB.")
    print(f"Initial size: {initial_total_size / (1024 * 1024):.2f} MB")

    choice = input("Compress them now? (y/n): ").strip().lower()
    if choice != 'y': return

    print("\nCompressing... (Please do not close the terminal)")
    final_total_size = 0
    errors = 0

    for i, file_path in enumerate(large_files, 1):
        sys.stdout.write(f"\r[{i}/{len(large_files)}] Processing: {file_path.name[:30]}...   ")
        sys.stdout.flush()

        temp_path = file_path.with_suffix('.tmp')
        ext = file_path.suffix.lower()

        try:
            with Image.open(file_path) as img:
                # 1. FIX: Safely convert Palette images to prevent transparency loss
                if img.mode == 'P' and 'transparency' in img.info:
                    img = img.convert('RGBA')

                # 2. Resize if necessary
                if img.width > max_width:
                    ratio = max_width / float(img.width)
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

                # 3. Save with the appropriate format
                if ext == '.png':
                    img.save(temp_path, "PNG", optimize=True)
                else:
                    # JPEGs cannot handle transparency, so we strip it safely to RGB
                    if img.mode in ("RGBA", "P", "LA"):
                        img = img.convert("RGB")
                    img.save(temp_path, "JPEG", optimize=True, quality=85)

            os.replace(temp_path, file_path)
            final_total_size += file_path.stat().st_size

        except Exception as e:
            errors += 1
            if temp_path.exists():
                temp_path.unlink()

    sys.stdout.write("\r" + " " * 80 + "\r")
    saved_mb = (initial_total_size - final_total_size) / (1024 * 1024)
    print("\n[SUCCESS] Optimization Complete!")
    print(f"Images Processed: {len(large_files)}")
    print(f"Errors Skipped: {errors}")
    print(f"Space Saved: {saved_mb:.2f} MB")


# ==========================================
# HTML GENERATOR
# ==========================================
def generate_html():
    print("\nCompiling Vault Data...")
    all_data = []

    # 1. Parse Meigen
    meigen_csv = MEIGEN_DIR / "meigen_data.csv"
    meigen_count = 0
    if meigen_csv.exists():
        with open(meigen_csv, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                row_data = {k.strip().lower(): v for k, v in row.items() if k}
                img_name = os.path.basename(row_data.get("local_path", ""))
                all_data.append({
                    "id": row_data.get("id", ""),
                    "title": row_data.get("title", ""),
                    "prompt": row_data.get("prompt", ""),
                    "category_tag": row_data.get("category_tag", ""),
                    "model": row_data.get("model", ""),
                    "local_path": f"Meigen/images/{img_name}" if img_name else "",
                    "source": "meigen"
                })
                meigen_count += 1
    print(f" -> Found {meigen_count} Meigen Prompts")

    # 2. Parse Banana (Strictly looks for banana_prompts_data.csv)
    banana_csv = BANANA_DIR / "banana_prompts_data.csv"

    banana_count = 0
    if banana_csv.exists():
        with open(banana_csv, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                row_data = {k.strip().lower(): v for k, v in row.items() if k}
                uuid = row_data.get("uuid", "").strip()
                if not uuid: continue

                img_filename = None
                for ext in [".jpg", ".jpeg", ".png", ".webp"]:
                    if (BANANA_DIR / "images" / f"{uuid}{ext}").exists():
                        img_filename = f"{uuid}{ext}"
                        break

                if img_filename:
                    all_data.append({
                        "id": uuid,
                        "title": row_data.get("title", ""),
                        "prompt": row_data.get("prompt", ""),
                        "category_tag": row_data.get("access_level", "Unknown").strip(),
                        "model": "",
                        "local_path": f"BananaPrompts/images/{img_filename}",
                        "source": "banana"
                    })
                    banana_count += 1
        print(f" -> Found {banana_count} Banana Prompts in {banana_csv.name}")
    else:
        print(f" -> [!] Could not find {banana_csv.name} in {BANANA_DIR.name}/ folder.")

    # 3. Parse Personal
    personal_csv = PERSONAL_DIR / "personal_data.csv"
    personal_count = 0
    if personal_csv.exists():
        with open(personal_csv, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                row_data = {k.strip().lower(): v for k, v in row.items() if k}
                img_name = os.path.basename(row_data.get("local_path", ""))
                all_data.append({
                    "id": row_data.get("id", ""),
                    "title": row_data.get("title", ""),
                    "prompt": row_data.get("prompt", ""),
                    "category_tag": row_data.get("category_tag", ""),
                    "model": row_data.get("model", ""),
                    "local_path": f"Personal/images/{img_name}" if img_name else "",
                    "source": "personal"
                })
                personal_count += 1
    print(f" -> Found {personal_count} Personal Prompts")

    if all_data:
        json_str = json.dumps(all_data, ensure_ascii=False).replace("</", "<\\/")
        html_content = HTML_TEMPLATE.replace("__JSON_DATA__", json_str)

        output_file = BASE_DIR / "index.html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"\n[SUCCESS] Vault Compiled! Open {output_file.name} in your browser.")
    else:
        print("\n[!] Vault compilation failed. No data was found across all 3 folders.")


# ==========================================
# RAW HTML TEMPLATE
# ==========================================
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prompt Vault</title>
    <style>
        :root { --bg-color: #f8f9fa; --surface-color: #ffffff; --text-main: #202124; --text-muted: #5f6368; --border-color: #dadce0; --accent: #1a73e8; --tag-model-bg: #e8f0fe; --tag-model-text: #1967d2; }
        [data-theme="dark"] { --bg-color: #121212; --surface-color: #1e1e1e; --text-main: #e8eaed; --text-muted: #9aa0a6; --border-color: #3c4043; --accent: #8ab4f8; --tag-model-bg: #1e3a5f; --tag-model-text: #8ab4f8; }
        body { font-family: -apple-system, sans-serif; background-color: var(--bg-color); color: var(--text-main); margin: 0; padding: 20px; transition: 0.3s; }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding: 15px; background: var(--surface-color); border-radius: 12px; border: 1px solid var(--border-color); }
        .controls { display: flex; gap: 15px; flex-wrap: wrap; }
        input, select, button { padding: 10px 15px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--bg-color); color: var(--text-main); outline: none; font-size: 14px; }
        button { cursor: pointer; background: var(--surface-color); transition: 0.2s; font-weight: 600; }
        button:hover { background: var(--border-color); }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; }
        .tab-btn { padding: 10px 20px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--surface-color); color: var(--text-muted); cursor: pointer; font-weight: 600; }
        .tab-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
        .masonry-grid { column-count: 4; column-gap: 20px; }
        @media (max-width: 1200px) { .masonry-grid { column-count: 3; } }
        @media (max-width: 800px) { .masonry-grid { column-count: 2; } }
        @media (max-width: 500px) { .masonry-grid { column-count: 1; } }
        .card { break-inside: avoid; margin-bottom: 20px; background: var(--surface-color); border-radius: 12px; overflow: hidden; border: 1px solid var(--border-color); cursor: pointer; transition: transform 0.2s; }
        .card:hover { transform: translateY(-4px); }
        .card img { width: 100%; display: block; background-color: var(--border-color); min-height: 100px; }
        .card-info { padding: 12px; }
        .tag { display: inline-block; padding: 4px 8px; font-size: 11px; background: var(--border-color); border-radius: 4px; text-transform: uppercase; margin-right: 5px; margin-bottom: 5px;}
        .tag.model { background: var(--tag-model-bg); color: var(--tag-model-text); font-weight: bold; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); backdrop-filter: blur(5px); z-index: 1000; justify-content: center; align-items: center; }
        .modal-content { background: var(--surface-color); width: 90%; max-width: 1000px; max-height: 90vh; border-radius: 16px; display: flex; overflow: hidden; flex-direction: row; position: relative;}
        @media (max-width: 768px) { .modal-content { flex-direction: column; overflow-y: auto; } }
        .modal-image { flex: 1; background: var(--bg-color); display: flex; align-items: center; justify-content: center; padding: 20px;}
        .modal-image img { max-width: 100%; max-height: 90vh; object-fit: contain; }
        .modal-details { flex: 1; padding: 30px; overflow-y: auto; border-left: 1px solid var(--border-color); }
        pre { white-space: pre-wrap; background: var(--bg-color); padding: 15px; border-radius: 8px; font-size: 13px; border: 1px solid var(--border-color); line-height: 1.5; }
        .close-btn { position: absolute; top: 15px; right: 20px; font-size: 30px; cursor: pointer; color: var(--text-muted); z-index: 10;}
    </style>
</head>
<body data-theme="dark">

    <header>
        <h2>Prompt Vault</h2>
        <div class="controls">
            <input type="text" id="searchInput" placeholder="Search prompts..." onkeyup="filterGallery()">
            <select id="categoryFilter" onchange="filterGallery()"><option value="all">All Categories</option></select>
            <select id="modelFilter" onchange="filterGallery()"><option value="all">All Models</option></select>
            <button onclick="document.body.setAttribute('data-theme', document.body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark')">🌓 Theme</button>
        </div>
    </header>

    <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('meigen')">Meigen.ai</button>
        <button class="tab-btn" onclick="switchTab('banana')">Banana Prompts</button>
        <button class="tab-btn" onclick="switchTab('personal')">Personal Vault</button>
    </div>

    <div class="masonry-grid" id="gallery"></div>

    <div id="viewModal" class="modal" onclick="if(event.target.classList.contains('modal')) this.style.display='none'">
        <div class="modal-content">
            <span class="close-btn" onclick="document.getElementById('viewModal').style.display='none'">&times;</span>
            <div class="modal-image"><img id="vImg" src=""></div>
            <div class="modal-details">
                <span class="tag" id="vCat"></span>
                <span class="tag model" id="vModel"></span>
                <h3 id="vTitle" style="margin-top: 15px;"></h3>
                <pre id="vPrompt"></pre>
            </div>
        </div>
    </div>

    <script>
        const allData = __JSON_DATA__;
        let currentSource = 'meigen';

        function switchTab(source) {
            currentSource = source;
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            updateDropdowns();
            filterGallery();
        }

        function updateDropdowns() {
            const currentData = allData.filter(item => item.source === currentSource);

            const categories = [...new Set(currentData.map(item => item.category_tag).filter(Boolean))];
            const catSelect = document.getElementById('categoryFilter');
            catSelect.innerHTML = '<option value="all">All Categories</option>';
            categories.sort().forEach(cat => { catSelect.innerHTML += `<option value="${cat}">${cat}</option>`; });

            const models = [...new Set(currentData.map(item => item.model).filter(Boolean))];
            const modelSelect = document.getElementById('modelFilter');
            modelSelect.innerHTML = '<option value="all">All Models</option>';
            models.sort().forEach(mod => { modelSelect.innerHTML += `<option value="${mod}">${mod}</option>`; });
            modelSelect.style.display = models.length > 0 ? 'inline-block' : 'none';
        }

        function filterGallery() {
            const query = document.getElementById('searchInput').value.toLowerCase();
            const category = document.getElementById('categoryFilter').value;
            const model = document.getElementById('modelFilter').value;
            const gallery = document.getElementById('gallery');
            gallery.innerHTML = '';

            const filtered = allData.filter(item => {
                if (item.source !== currentSource) return false;
                const matchesSearch = (item.prompt || "").toLowerCase().includes(query) || (item.title || "").toLowerCase().includes(query);
                const matchesCat = category === 'all' || item.category_tag === category;
                const matchesModel = model === 'all' || item.model === model;
                return matchesSearch && matchesCat && matchesModel;
            });

            filtered.forEach(item => {
                const card = document.createElement('div');
                card.className = 'card';
                card.onclick = () => openViewModal(item);
                const title = item.title ? `<strong>${item.title}</strong><br>` : "";

                card.innerHTML = `
                    <img src="${item.local_path}" loading="lazy" onerror="this.style.display='none'">
                    <div class="card-info">
                        <span class="tag">${item.category_tag || 'Misc'}</span>
                        ${item.model ? `<span class="tag model">${item.model}</span>` : ''}
                        <p style="font-size: 12px; margin-top: 8px; color: var(--text-muted);">${title} ${ (item.prompt || "No prompt").substring(0, 60) }...</p>
                    </div>
                `;
                gallery.appendChild(card);
            });
        }

        function openViewModal(item) {
            document.getElementById('viewModal').style.display = 'flex';
            document.getElementById('vImg').src = item.local_path;
            document.getElementById('vCat').innerText = item.category_tag || 'Misc';
            document.getElementById('vModel').innerText = item.model || '';
            document.getElementById('vModel').style.display = item.model ? 'inline-block' : 'none';
            document.getElementById('vTitle').innerText = item.title || '';
            document.getElementById('vPrompt').innerText = item.prompt || 'No prompt available.';
        }

        document.addEventListener('keydown', e => { if (e.key === 'Escape') document.getElementById('viewModal').style.display = 'none'; });

        // Init
        updateDropdowns();
        filterGallery();
    </script>
</body>
</html>"""


# ==========================================
# MAIN MENU
# ==========================================
def main_menu():
    while True:
        print("\n==================================")
        print("      PROMPT VAULT MANAGER        ")
        print("==================================")
        print("1. Update Meigen.ai")
        print("2. Update Banana Prompts")
        print("3. Add Personal Prompt (GUI)")
        print("4. Generate & View HTML Vault")
        print("5. Run Storage Optimizer")
        print("6. Exit")

        choice = input("\nSelect an option (1-6): ").strip()

        if choice == '1':
            run_script(MEIGEN_DIR, "meigen_sync.py")
        elif choice == '2':
            run_script(BANANA_DIR, "banana_prompts_sync.py")
        elif choice == '3':
            run_script(PERSONAL_DIR, "add_prompt_gui.py")
        elif choice == '4':
            generate_html()
        elif choice == '5':
            optimize_storage()
        elif choice == '6':
            print("Exiting...")
            break
        else:
            print("[!] Invalid option. Please try again.")


if __name__ == "__main__":
    main_menu()