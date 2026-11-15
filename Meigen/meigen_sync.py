import os
import csv
import time
import sys
import requests
from pathlib import Path

# --- Configuration ---
API_URL = "https://www.meigen.ai/api/images"
CATEGORIES = ["product", "logo", "3d", "design", "photograph", "wallpaper"]
LIMIT = 20

BASE_DIR = Path(__file__).parent
CSV_FILE = BASE_DIR / "meigen_data.csv"
IMAGE_DIR = BASE_DIR / "images"

CSV_FIELDS = [
    "id",
    "title",
    "prompt",
    "category_tag",
    "model",
    "image_url",
    "local_path",
    "author_name"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.meigen.ai/",
    "Accept": "application/json"
}


def load_local_database():
    if not CSV_FILE.exists():
        return []

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def save_local_database(data):
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(data)


def download_image(url, image_id):
    file_path = IMAGE_DIR / f"{image_id}.jpg"
    if file_path.exists():
        return f"images/{image_id}.jpg"

    try:
        response = requests.get(url, headers=HEADERS, stream=True, timeout=15)
        response.raise_for_status()
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return f"images/{image_id}.jpg"
    except Exception as e:
        print(f"\n  [!] Failed to download image {image_id}: {e}")
        return None


def sync_gallery():
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    local_data = load_local_database()
    known_ids = {item["id"] for item in local_data if "id" in item}

    pending_downloads = []

    print("=== PHASE 1: Scanning for updates ===")

    for category in CATEGORIES:
        print(f"\nScanning category: {category.upper()}")
        offset = 0
        reached_known_data = False
        category_new_count = 0

        while not reached_known_data:
            params = {
                "category": category,
                "offset": offset,
                "limit": LIMIT,
                "sort": "latest"
            }

            sys.stdout.write(f"\r  -> Checking offset {offset}... ")
            sys.stdout.flush()

            try:
                response = requests.get(API_URL, headers=HEADERS, params=params, timeout=10)

                if response.status_code == 429:
                    print("\n  [!] Rate limited. Pausing for 15s...")
                    time.sleep(15)
                    continue
                elif response.status_code != 200:
                    print(f"\n  [!] API Error: HTTP {response.status_code}. Halting scan for {category}.")
                    break

                data = response.json()

            except requests.exceptions.RequestException as e:
                print(f"\n  [!] Network error: {e}. Halting scan for {category}.")
                break
            except ValueError:
                print(f"\n  [!] Invalid JSON received. Halting scan for {category}.")
                break

            images = data.get("images", [])
            if not images:
                print("\n  -> Reached the end of the archive for this category.")
                break

            known_on_this_page = 0

            for item in images:
                item_id = item.get("id")
                if not item_id: continue

                if item_id in known_ids:
                    known_on_this_page += 1
                    continue

                # Flatten the JSON response into our standard CSV structure
                author_data = item.get("author", {})
                author_name = author_data.get("name", "") if isinstance(author_data, dict) else ""

                flat_item = {
                    "id": item_id,
                    "title": item.get("title", ""),
                    "prompt": item.get("prompt", ""),
                    "category_tag": category,
                    "model": item.get("model", ""),
                    "image_url": item.get("image", ""),
                    "local_path": "",  # Will be populated during download phase
                    "author_name": author_name
                }

                pending_downloads.append(flat_item)
                category_new_count += 1
                known_ids.add(item_id)

            if known_on_this_page == len(images):
                print(f"\n  -> Reached already-archived content. Moving to next category.")
                reached_known_data = True

            offset += LIMIT
            time.sleep(4)

        print(f"Found {category_new_count} new items in {category.upper()}.")

    # USER PROMPT PHASE
    if not pending_downloads:
        print("\nScan complete. Your vault is already up to date!")
        save_local_database(local_data)
        return

    print(f"\n=== SUMMARY ===")
    print(f"Total new images to download across all categories: {len(pending_downloads)}")

    choice = input("\nDo you want to proceed with the download now? (y/n): ").strip().lower()

    if choice != 'y':
        print("\nDownload aborted. No files were saved. Run the script again when you are ready.")
        return

    # DOWNLOAD PHASE
    print("\n=== PHASE 2: Downloading ===")
    new_entries = []
    total_downloads = len(pending_downloads)

    for index, item in enumerate(pending_downloads, 1):
        item_id = item["id"]

        sys.stdout.write(f"\r[{index} / {total_downloads}] Downloading {item_id} ({item['category_tag']})...")
        sys.stdout.flush()

        local_image_path = download_image(item.get("image_url"), item_id)

        if local_image_path:
            item["local_path"] = local_image_path
            new_entries.append(item)

        time.sleep(1)

    print(f"\n\nSync complete! Successfully archived {len(new_entries)} new items.")

    # Prepend new entries to existing data and save
    updated_data = new_entries + local_data
    save_local_database(updated_data)


if __name__ == "__main__":
    sync_gallery()