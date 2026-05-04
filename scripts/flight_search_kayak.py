"""
Search kayak.com for flights LAX -> SJD (Los Cabos) for Feb 3-7, 2027.
Uses open-computer-use linux-x11 backend to drive Chromium in Docker.
Saves screenshots of results and extracts flight text via OCR.
"""
import base64
import json
import os
import subprocess
import sys
import time

os.environ.setdefault("OPEN_CU_BACKEND", "linux-x11")

from open_open_computer_use.backends.linux_x11 import LinuxX11Backend
from open_open_computer_use.vision import ocr_extract

OUTPUT_DIR = "/home/testuser/repo/test-recordings/flight_search"
BROWSER = "chromium"


def wait(seconds: float = 2.0):
    time.sleep(seconds)


def screenshot(backend, label: str) -> str:
    b64, w, h, fmt = backend.capture_screenshot()
    fname = f"{label}.png"
    path = f"{OUTPUT_DIR}/{fname}"
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))
    print(f"  [screenshot] {label} ({w}x{h}) -> {path}")
    return path


def extract_text(path: str) -> str:
    """OCR a screenshot and return the text."""
    try:
        with open(path, "rb") as f:
            results = ocr_extract(f.read())
        # ocr_extract returns list of dicts with 'text' key
        lines = [r.get("text", "") for r in results if r.get("text", "").strip()]
        return "\n".join(lines)
    except Exception as e:
        print(f"  [OCR error] {e}")
        return ""


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    backend = LinuxX11Backend()

    # Step 1: Launch Chromium
    print("\n=== Step 1: Launch Chromium ===")
    env = os.environ.copy()
    env["DISPLAY"] = ":99"
    env["HOME"] = "/home/testuser"

    # Use a clean profile to avoid cookie banners, set user-agent to look like a real browser
    proc = subprocess.Popen(
        [BROWSER,
         "--no-sandbox",
         "--disable-gpu",
         "--disable-software-rasterizer",
         "--no-first-run",
         "--disable-default-apps",
         "--window-size=1280,800",
         "--disable-infobars",
         "--disable-notifications",
         "--lang=en-US",
         "about:blank"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"  Chromium PID: {proc.pid}")
    wait(5)
    screenshot(backend, "01_chromium_launched")

    # Step 2: Navigate to kayak.com flights
    print("\n=== Step 2: Navigate to kayak.com ===")
    backend.press_key("ctrl+l")
    wait(0.5)
    backend.press_key("ctrl+a")
    wait(0.2)
    # Go directly to flights search page
    backend.type_text("https://www.kayak.com/flights")
    wait(0.3)
    backend.press_key("Return")
    print("  Loading kayak.com/flights...")
    wait(12)
    screenshot(backend, "02_kayak_flights_page")

    # Dismiss cookie banner if present - press Escape or click reject
    backend.press_key("Escape")
    wait(1)

    # Step 3: Click on origin field and set to LAX
    print("\n=== Step 3: Set origin to LAX ===")
    # The origin field is near the top-left of the search form
    # Try clicking on it - coordinates approximate for kayak.com flight search
    backend.click(element_index=None, x=320, y=230)
    wait(1)
    screenshot(backend, "03a_origin_clicked")

    # Clear and type LAX
    backend.press_key("ctrl+a")
    wait(0.3)
    backend.press_key("BackSpace")
    wait(0.3)
    backend.type_text("LAX")
    wait(3)
    screenshot(backend, "03b_lax_typed")

    # Select first autocomplete (LAX airport)
    backend.press_key("Down")
    wait(0.5)
    backend.press_key("Return")
    wait(2)
    screenshot(backend, "03c_lax_selected")

    # Step 4: Set destination to San Jose del Cabo (SJD)
    print("\n=== Step 4: Set destination to SJD ===")
    backend.click(element_index=None, x=600, y=230)
    wait(1)
    screenshot(backend, "04a_dest_clicked")

    backend.press_key("ctrl+a")
    wait(0.3)
    backend.press_key("BackSpace")
    wait(0.3)
    backend.type_text("SJD")
    wait(3)
    screenshot(backend, "04b_sjd_typed")

    backend.press_key("Down")
    wait(0.5)
    backend.press_key("Return")
    wait(2)
    screenshot(backend, "04c_sjd_selected")

    # Step 5: Set departure date to Feb 3, 2027
    print("\n=== Step 5: Set dates Feb 3-7, 2027 ===")
    # Click on the departure date field
    backend.click(element_index=None, x=400, y=280)
    wait(2)
    screenshot(backend, "05a_date_picker")

    # We need to navigate to February 2027
    # Kayak shows a month calendar, need to advance months
    # Current month is May 2025, need to get to Feb 2027 = ~21 months forward
    # Click "next" arrow ~21 times (or look for month arrows)
    # Actually, kayak often has month navigation. Let's try typing the date directly
    # First try: Tab to get to date field and type
    backend.press_key("Escape")
    wait(0.5)

    # Alternative: use kayak URL with pre-filled params
    # This is more reliable than clicking through date pickers
    print("  Switching to direct URL approach with pre-filled params...")
    backend.press_key("ctrl+l")
    wait(0.5)
    backend.press_key("ctrl+a")
    wait(0.2)
    backend.type_text("https://www.kayak.com/flights/LAX-SJD/2027-02-03/2027-02-07?sort=bestflight_a")
    wait(0.3)
    backend.press_key("Return")
    print("  Navigating to kayak.com with LAX-SJD Feb 3-7 search...")
    wait(15)
    screenshot(backend, "05b_search_loading")

    # Step 6: Wait for results to fully load
    print("\n=== Step 6: Wait for results ===")
    wait(10)
    screenshot(backend, "06a_results_partial")
    wait(10)
    screenshot(backend, "06b_results_loaded")
    wait(5)
    screenshot(backend, "06c_results_final")

    # Step 7: Scroll down to see more results
    print("\n=== Step 7: Scroll for more results ===")
    # Use xdotool scroll directly since we don't have an element_index
    subprocess.run(["xdotool", "mousemove", "640", "400"], check=False)
    subprocess.run(["xdotool", "click", "--repeat", "3", "--delay", "100", "5"], check=False)
    wait(3)
    screenshot(backend, "07a_results_scrolled")
    subprocess.run(["xdotool", "click", "--repeat", "3", "--delay", "100", "5"], check=False)
    wait(3)
    screenshot(backend, "07b_results_more")
    subprocess.run(["xdotool", "click", "--repeat", "3", "--delay", "100", "5"], check=False)
    wait(3)
    screenshot(backend, "07c_results_bottom")

    # Step 8: OCR the result screenshots to extract flight data
    print("\n=== Step 8: Extract flight data via OCR ===")
    results = {}
    for img in sorted(os.listdir(OUTPUT_DIR)):
        if img.startswith("06") or img.startswith("07"):
            path = f"{OUTPUT_DIR}/{img}"
            text = extract_text(path)
            if text:
                results[img] = text
                print(f"  --- {img} ---")
                print(text[:1000])

    # Save OCR results
    ocr_path = f"{OUTPUT_DIR}/ocr_results.json"
    with open(ocr_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  OCR results saved to {ocr_path}")

    print("\n=== Flight search complete! ===")
    print(f"  Screenshots: {OUTPUT_DIR}/")
    print(f"  OCR data: {ocr_path}")


if __name__ == "__main__":
    main()
