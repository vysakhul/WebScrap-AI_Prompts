import asyncio
import csv
import os
import requests
from playwright.async_api import async_playwright

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

BASE_URL = "https://www.bananaprompts.xyz"
EXPLORE_URL = f"{BASE_URL}/explore"
CSV_PATH = "banana_prompts_data.csv"
IMAGE_DIR = "images"

CSV_FIELDS = [
    "uuid",
    "title",
    "url",
    "prompt",
    "image_url",
    "access_level",
    "download_status",
]

os.makedirs(IMAGE_DIR, exist_ok=True)

# ------------------------------------------------------------
# CSV HELPERS (BACKWARD COMPATIBLE)
# ------------------------------------------------------------

def load_existing_rows():
    if not os.path.exists(CSV_PATH):
        return [], set()

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Schema upgrade
    for row in rows:
        row.setdefault("prompt", "")
        row.setdefault("image_url", "")
        row.setdefault("access_level", "")
        row.setdefault("download_status", "Pending")

    existing_uuids = {row["uuid"] for row in rows}
    return rows, existing_uuids


def write_csv(rows):
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

# ------------------------------------------------------------
# IMAGE UTIL
# ------------------------------------------------------------

def image_exists(uuid):
    for f in os.listdir(IMAGE_DIR):
        if f.startswith(uuid + "."):
            return True
    return False


def download_image(uuid, img_src):
    clean_url = img_src.split("?")[0]
    ext = clean_url.split(".")[-1]
    img_path = os.path.join(IMAGE_DIR, f"{uuid}.{ext}")

    if os.path.exists(img_path):
        return True

    try:
        r = requests.get(img_src, timeout=30)
        r.raise_for_status()
        with open(img_path, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"[WARN] Image download failed {uuid}: {e}")
        return False

# ------------------------------------------------------------
# MAIN WORKFLOW
# ------------------------------------------------------------

async def main():
    rows, existing_uuids = load_existing_rows()
    print(f"[INFO] Existing UUIDs in CSV: {len(existing_uuids)}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # ======================================================
        # STAGE 1 — DISCOVERY
        # ======================================================

        print("[STAGE 1] Loading explore page")
        await page.goto(EXPLORE_URL, timeout=60000)

        scroll_pass = 0
        while True:
            end_marker = await page.query_selector(
                "span:text('You reached the end')"
            )
            if end_marker:
                print("[STAGE 1] End of page detected")
                break

            scroll_pass += 1
            print(f"[SCROLL] Pass {scroll_pass}")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)

        cards = await page.eval_on_selector_all(
            "a[href^='/prompts/'][aria-label]",
            """els => els.map(el => ({
                href: el.getAttribute('href'),
                aria: el.getAttribute('aria-label')
            }))"""
        )

        new_count = 0
        for item in cards:
            uuid = item["href"].rstrip("/").split("/")[-1]
            if uuid in existing_uuids:
                continue

            title = item["aria"].replace("View details for", "").strip()

            rows.append({
                "uuid": uuid,
                "title": title,
                "url": f"{BASE_URL}{item['href']}",
                "prompt": "",
                "image_url": "",
                "access_level": "",
                "download_status": "Pending",
            })

            existing_uuids.add(uuid)
            new_count += 1

        write_csv(rows)
        print(f"[STAGE 1] New UUIDs added: {new_count}")
        print(f"[STAGE 1] Total UUIDs: {len(rows)}")

        proceed = input(
            "\nProceed to prompt extraction and image download? (y/n): "
        ).strip().lower()

        if proceed != "y":
            await browser.close()
            return

        # ======================================================
        # STAGE 2 — PROMPT + IMAGE EXTRACTION
        # ======================================================

        print("\n[STAGE 2] Extracting prompts and downloading images")

        for idx, row in enumerate(rows, start=1):
            uuid = row["uuid"]

            needs_prompt = row["prompt"] == ""
            needs_image = row["download_status"] != "Complete"

            if not needs_prompt and not needs_image:
                continue

            print(f"[{idx}/{len(rows)}] Processing {uuid}")

            try:
                await page.goto(row["url"], timeout=60000)
                await page.wait_for_load_state("domcontentloaded")

                # ---------- PROMPT ----------
                if needs_prompt:
                    prompt_el = await page.query_selector("p.whitespace-pre-wrap")
                    if prompt_el:
                        row["prompt"] = (await prompt_el.text_content()).strip()
                        row["access_level"] = "Free"
                    else:
                        premium_el = await page.query_selector(
                            "h3:text('Premium Content')"
                        )
                        if premium_el:
                            row["prompt"] = "Premium Content"
                            row["access_level"] = "Premium"
                        else:
                            row["prompt"] = ""
                            row["access_level"] = "Unknown"

                # ---------- IMAGE ----------
                img_el = await page.query_selector("img[src]")
                if img_el:
                    img_src = await img_el.get_attribute("src")
                    row["image_url"] = img_src or ""

                    if img_src:
                        success = download_image(uuid, img_src)
                        row["download_status"] = "Complete" if success else "Pending"

                write_csv(rows)

            except Exception as e:
                print(f"[WARN] Failed {uuid}: {e}")

        await browser.close()

    # ======================================================
    # FINAL DOWNLOAD STATUS CHECK
    # ======================================================

    print("\n[FINAL] Verifying image download status")

    for row in rows:
        if image_exists(row["uuid"]):
            row["download_status"] = "Complete"
        else:
            row["download_status"] = "Pending"

    write_csv(rows)
    print("[DONE] CSV and image verification complete")

# ------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())
