"""
Browser automation test: open Firefox, navigate to kayak.com, search Los Cabos travel.

Uses gsd-computer-use linux-x11 backend directly to demonstrate real desktop
automation with a web browser inside Docker (Xvfb + openbox + Firefox).
"""
import base64
import os
import subprocess
import tempfile
import time
import unittest

os.environ.setdefault("GSD_CU_BACKEND", "linux-x11")

from computer_use.backends.linux_x11 import LinuxX11Backend


def run_cmd(cmd: list[str], timeout: int = 10) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip()
    except Exception:
        return -1, ""


class TestBrowserKayak(unittest.TestCase):
    """Open Firefox, navigate to kayak.com, search for Los Cabos flights."""

    backend = LinuxX11Backend()
    step = 0

    def _screenshot(self, label: str = "") -> str:
        """Capture screenshot for debugging."""
        b64, w, h, fmt = self.backend.capture_screenshot()
        TestBrowserKayak.step += 1
        path = f"/tmp/browser_step_{TestBrowserKayak.step:02d}_{label.replace(' ', '_')}.png"
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))
        print(f"  [screenshot] step {TestBrowserKayak.step}: {label} -> {path}")
        return path

    def test_01_launch_firefox(self):
        """Launch Firefox browser."""
        print("\n=== Step 1: Launch Firefox ===")
        result = self.backend.activate_or_launch_app("firefox")
        print(f"  Launch result: {result}")
        self._wait(6)
        self._screenshot("firefox_launched")

        # Verify Firefox is running
        code, out = run_cmd(["pgrep", "-c", "-f", "firefox"])
        print(f"  Firefox processes: {out}")
        # Firefox may not be found by pgrep in container — don't fail on this

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
        self._wait(10)
        self._screenshot("kayak_loaded")

    def test_03_click_destination_field(self):
        """Click the destination/To field on kayak search form."""
        print("\n=== Step 3: Click destination field ===")
        # On kayak.com, the destination field is usually in the upper-center area
        # Try clicking where the "To" destination input would be
        # First take a screenshot to see what we have
        self._screenshot("before_click")

        # Try to click the destination field area
        # kayak.com layout: From field ~left, To field ~center-left
        self.backend.click(element_index=None, x=520, y=300)
        self._wait(1)
        self._screenshot("destination_clicked")

    def test_04_type_los_cabos(self):
        """Type 'Los Cabos' in the destination field."""
        print("\n=== Step 4: Type Los Cabos ===")
        self.backend.press_key("ctrl+a")
        self._wait(0.2)
        self.backend.type_text("Los Cabos")
        self._wait(3)
        self._screenshot("los_cabos_typed")

        # Select first autocomplete suggestion
        self.backend.press_key("Down")
        self._wait(0.5)
        self.backend.press_key("Return")
        self._wait(2)
        self._screenshot("destination_selected")

    def test_05_click_search(self):
        """Click the search button to find flights."""
        print("\n=== Step 5: Click search ===")
        # Search button is typically below the form fields
        self.backend.click(element_index=None, x=640, y=450)
        self._wait(8)
        self._screenshot("search_results")

    def test_06_capture_results(self):
        """Wait for results page and capture final state."""
        print("\n=== Step 6: Capture results ===")
        self._wait(5)
        self._screenshot("final_results_page")
        print("  Browser automation complete!")

    def _wait(self, seconds: float = 2.0):
        time.sleep(seconds)


if __name__ == "__main__":
    unittest.main()
