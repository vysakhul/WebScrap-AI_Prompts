import csv
import os
import sys
import time
from pathlib import Path

import requests

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

BASE_URL = "https://www.bananaprompts.xyz"
API_URL = f"{BASE_URL}/api/prompts"
PAGE_SIZE = 100  # the API caps limit at 100

BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "banana_prompts_data.csv"
IMAGE_DIR = BASE_DIR / "images"

CSV_FIELDS = [
    "uuid",
    "title",
    "url",
    "prompt",
    "image_url",
    "access_level",
    "download_status",
]

SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".webp")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"{BASE_URL}/explore",
    "Accept": "application/json",
}

# ------------------------------------------------------------
# CSV HELPERS
# ------------------------------------------------------------

def load_existing_rows():
    if not CSV_PATH.exists():
        return []

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        for field in CSV_FIELDS:
            row.setdefault(field, "")
        if not row["download_status"]:
            row["download_status"] = "Pending"
    return rows


def write_csv(rows):
    # Write to a temp file first so an interrupted run can't corrupt the database
    tmp_path = CSV_PATH.with_suffix(".tmp")
    with open(tmp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp_path, CSV_PATH)

# ------------------------------------------------------------
# IMAGE HELPERS
# ------------------------------------------------------------

def local_image_ids():
    """UUIDs that already have an image file on disk."""
    if not IMAGE_DIR.exists():
        return set()
    return {
        name.rsplit(".", 1)[0]
        for name in os.listdir(IMAGE_DIR)
        if name.lower().endswith(SUPPORTED_EXTS)
    }


def download_image(uuid, img_src):
    ext = img_src.split("?")[0].rsplit(".", 1)[-1].lower()
    if f".{ext}" not in SUPPORTED_EXTS:
        ext = "jpg"
    img_path = IMAGE_DIR / f"{uuid}.{ext}"
    if img_path.exists():
        return True

    tmp_path = img_path.with_suffix(".part")
    try:
        r = requests.get(img_src, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=30)
        r.raise_for_status()
        with open(tmp_path, "wb") as f:
            f.write(r.content)
        os.replace(tmp_path, img_path)
        return True
    except Exception as e:
        print(f"\n  [WARN] Image download failed {uuid}: {e}")
        if tmp_path.exists():
            tmp_path.unlink()
        return False

# ------------------------------------------------------------
# API
# ------------------------------------------------------------

def fetch_all_prompts():
    """Read the full prompt list from the site's JSON feed (metadata only, no images).

    The feed's sort order is not strictly by date, so we scan every page rather
    than stopping at the first known item. That is ~50 small requests.
    """
    items = []
    offset = 0
    while True:
        sys.stdout.write(f"\r  -> Fetching offset {offset}... ")
        sys.stdout.flush()
        try:
            r = requests.get(
                API_URL,
                headers=HEADERS,
                params={"limit": PAGE_SIZE, "offset": offset, "sort": "newest"},
                timeout=30,
            )
            if r.status_code == 429:
                print("\n  [!] Rate limited. Pausing for 15s...")
                time.sleep(15)
                continue
            r.raise_for_status()
            data = r.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"\n  [!] Could not read the prompt feed: {e}")
            return None

        page = data.get("items", [])
        items.extend(page)
        if not data.get("hasMore") or not page:
            break
        offset = data.get("nextOffset") or offset + len(page)
        time.sleep(1)

    print(f"\r  -> Fetched {len(items)} prompts from the site.        ")
    return items


def item_to_row(item):
    uuid = item["id"]
    premium = bool(item.get("isPremium"))
    prompt = (item.get("prompt") or "").strip()
    if premium and not prompt:
        prompt = "Premium Content"
    return {
        "uuid": uuid,
        "title": (item.get("title") or "").strip(),
        "url": f"{BASE_URL}/prompts/{uuid}",
        "prompt": prompt,
        "image_url": item.get("image") or "",
        "access_level": "Premium" if premium else "Free",
        "download_status": "Pending",
    }

# ------------------------------------------------------------
# MAIN WORKFLOW
# ------------------------------------------------------------

def main():
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_existing_rows()
    by_uuid = {row["uuid"]: row for row in rows if row.get("uuid")}
    on_disk = local_image_ids()
    print(f"[INFO] Prompts in CSV: {len(by_uuid)} | Images on disk: {len(on_disk)}")

    # ======================================================
    # STAGE 1 — DISCOVERY (metadata only)
    # ======================================================
    print("\n[STAGE 1] Checking bananaprompts.xyz for new prompts")
    items = fetch_all_prompts()
    if items is None:
        print("[ABORT] Nothing was changed.")
        return
    if not items:
        print("[ABORT] The site returned no prompts. It may have changed again; nothing was changed.")
        return

    new_rows = []
    filled_prompts = 0
    for item in items:
        if not item.get("id"):
            continue
        fresh = item_to_row(item)
        existing = by_uuid.get(fresh["uuid"])
        if existing is None:
            new_rows.append(fresh)
            by_uuid[fresh["uuid"]] = fresh
            continue
        # Fill gaps in rows you already have without touching their images
        if fresh["prompt"] and existing["prompt"] in ("", "Premium Content") and fresh["prompt"] != "Premium Content":
            existing["prompt"] = fresh["prompt"]
            existing["access_level"] = "Free"
            filled_prompts += 1
        if not existing["image_url"] and fresh["image_url"]:
            existing["image_url"] = fresh["image_url"]

    # Newest first, so new prompts show at the top of the gallery
    created = {i["id"]: i.get("createdAt") or "" for i in items if i.get("id")}
    new_rows.sort(key=lambda r: created.get(r["uuid"], ""), reverse=True)
    rows = new_rows + rows

    # Only rows never downloaded are queued; rows already marked Complete are never re-fetched
    to_download = [
        r for r in rows
        if r["uuid"] not in on_disk and r["download_status"] != "Complete" and r["image_url"]
    ]

    print(f"\n=== SUMMARY ===")
    print(f"New prompts found:            {len(new_rows)}")
    print(f"  of which Premium:           {sum(r['access_level'] == 'Premium' for r in new_rows)}")
    print(f"Existing prompts text updated: {filled_prompts}")
    print(f"Images to download:           {len(to_download)}")

    if not new_rows and not filled_prompts and not to_download:
        print("\nYour vault is already up to date!")
        return

    # Save discovered metadata now so a skipped/interrupted download can resume next run
    write_csv(rows)
    print(f"\n[SAVED] {CSV_PATH.name} now has {len(rows)} prompts.")

    if not to_download:
        return

    proceed = input("\nDownload the missing images now? (y/n): ").strip().lower()
    if proceed != "y":
        print("Skipped. New prompts are saved as Pending; run again to download their images.")
        return

    # ======================================================
    # STAGE 2 — IMAGE DOWNLOAD
    # ======================================================
    print("\n[STAGE 2] Downloading images")
    ok = 0
    for idx, row in enumerate(to_download, 1):
        sys.stdout.write(f"\r[{idx}/{len(to_download)}] {row['uuid']}   ")
        sys.stdout.flush()
        if download_image(row["uuid"], row["image_url"]):
            row["download_status"] = "Complete"
            ok += 1
        if idx % 25 == 0:
            write_csv(rows)
        time.sleep(0.5)

    write_csv(rows)
    print(f"\n\n[DONE] Downloaded {ok}/{len(to_download)} images. Failed ones stay Pending for the next run.")


if __name__ == "__main__":
    main()
