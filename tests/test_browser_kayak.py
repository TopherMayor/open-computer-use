"""
Browser automation test: open Chromium, navigate to kayak.com, search Los Cabos.

Uses open-computer-use linux-x11 backend directly to drive a real browser
inside Docker (Xvfb + openbox + Chromium). Records the session via ffmpeg.
"""
import base64
import os
import subprocess
import time
import unittest

os.environ.setdefault("OPEN_CU_BACKEND", "linux-x11")

from open_computer_use.backends.linux_x11 import LinuxX11Backend

SCREENSHOTS_DIR = "/home/testuser/repo/test-recordings/browser_debug"
# Chromium binary name (Debian: 'chromium', Ubuntu: 'chromium-browser')
BROWSER = "chromium"


def run_cmd(cmd: list[str], timeout: int = 10) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip()
    except Exception:
        return -1, ""


class TestBrowserKayak(unittest.TestCase):
    """Open Chromium, navigate to kayak.com, search for Los Cabos flights."""

    backend = LinuxX11Backend()
    step = 0

    @classmethod
    def setUpClass(cls):
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    def _screenshot(self, label: str = "") -> str:
        """Capture screenshot to mounted volume for debugging."""
        b64, w, h, fmt = self.backend.capture_screenshot()
        TestBrowserKayak.step += 1
        fname = f"step_{TestBrowserKayak.step:02d}_{label.replace(' ', '_')}.png"
        path = f"{SCREENSHOTS_DIR}/{fname}"
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))
        print(f"  [screenshot] step {TestBrowserKayak.step}: {label} ({w}x{h})")
        return path

    def test_01_launch_chromium(self):
        """Launch Chromium browser."""
        print("\n=== Step 1: Launch Chromium ===")

        env = os.environ.copy()
        env["DISPLAY"] = ":99"
        env["HOME"] = "/home/testuser"

        proc = subprocess.Popen(
            [BROWSER,
             "--no-sandbox",
             "--disable-gpu",
             "--disable-software-rasterizer",
             "--no-first-run",
             "--disable-default-apps",
             "--window-size=1280,800",
             "--homepage=about:blank",
             "about:blank"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"  Chromium PID: {proc.pid}")
        self._wait(5)

        # Verify it's running
        code, out = run_cmd(["pgrep", "-f", "chrom"])
        print(f"  Chromium processes found: {out}")
        self._screenshot("01_chromium_launched")

    def test_02_navigate_to_kayak(self):
        """Navigate to kayak.com by typing URL in address bar."""
        print("\n=== Step 2: Navigate to kayak.com ===")
        # Focus address bar
        self.backend.press_key("ctrl+l")
        self._wait(0.5)
        # Clear and type URL
        self.backend.press_key("ctrl+a")
        self._wait(0.2)
        self.backend.type_text("https://www.kayak.com")
        self._wait(0.3)
        self.backend.press_key("Return")
        print("  Navigating to kayak.com...")
        self._wait(12)
        self._screenshot("02_kayak_loaded")

    def test_03_click_destination_field(self):
        """Click the destination/To field on kayak search form."""
        print("\n=== Step 3: Click destination field ===")
        self._screenshot("03_before_click")

        # Click where the destination input would be on kayak.com
        self.backend.click(element_index=None, x=520, y=280)
        self._wait(1)
        self._screenshot("03_destination_clicked")

    def test_04_type_los_cabos(self):
        """Type 'Los Cabos' in the destination field."""
        print("\n=== Step 4: Type Los Cabos ===")
        self.backend.press_key("ctrl+a")
        self._wait(0.2)
        self.backend.type_text("Los Cabos")
        self._wait(3)
        self._screenshot("04_los_cabos_typed")

        # Select first autocomplete suggestion
        self.backend.press_key("Down")
        self._wait(0.5)
        self.backend.press_key("Return")
        self._wait(2)
        self._screenshot("04b_destination_selected")

    def test_05_click_search(self):
        """Click the search button."""
        print("\n=== Step 5: Click search ===")
        self.backend.click(element_index=None, x=640, y=450)
        self._wait(10)
        self._screenshot("05_search_results")

    def test_06_capture_results(self):
        """Wait for results and capture final state."""
        print("\n=== Step 6: Capture results ===")
        self._wait(5)
        self._screenshot("06_final_results")
        print("  Browser automation complete!")

    def _wait(self, seconds: float = 2.0):
        time.sleep(seconds)


if __name__ == "__main__":
    unittest.main()
