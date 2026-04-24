#!/usr/bin/env python3
"""
GSD Computer Use - optional legacy autonomous task runner.

This file is not used by the self-hosted Codex plugin. The local plugin entry
point is scripts/computer_use_mcp_server.py.

This older CLI can delegate screen understanding to a Z.AI vision model and
then execute actions at OS level via pyautogui/pynput.

Features:
- Full desktop screen capture (mss)
- OS-level mouse control (pyautogui)
- OS-level keyboard control (pyautogui + pynput)
- Window management (AppleScript on macOS)
- Human-like delays and movements
"""

import asyncio
import base64
import json
import math
import os
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

# Screen capture
try:
    import mss
    import mss.tools
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

# Mouse/keyboard control
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

# Additional input handling
try:
    from pynput import keyboard as pynput_keyboard
    from pynput import mouse as pynput_mouse
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

# Optional Z.AI API client for the legacy autonomous CLI.
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Pillow for image processing
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class ActionType(Enum):
    """Supported action types."""
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    MOVE = "move"
    TYPE = "type"
    KEY = "key"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    DONE = "done"
    ERROR = "error"


@dataclass
class Action:
    """Represents a computer use action."""
    type: ActionType
    x: Optional[int] = None
    y: Optional[int] = None
    text: Optional[str] = None
    key: Optional[str] = None
    seconds: Optional[float] = None
    result: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        d = {"type": self.type.value}
        if self.x is not None:
            d["x"] = self.x
        if self.y is not None:
            d["y"] = self.y
        if self.text is not None:
            d["text"] = self.text
        if self.key is not None:
            d["key"] = self.key
        if self.seconds is not None:
            d["seconds"] = self.seconds
        if self.result is not None:
            d["result"] = self.result
        if self.message is not None:
            d["message"] = self.message
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Action":
        """Create from dictionary."""
        action_type = d.get("type", "error")
        try:
            action_type = ActionType(action_type)
        except ValueError:
            action_type = ActionType.ERROR

        return cls(
            type=action_type,
            x=d.get("x"),
            y=d.get("y"),
            text=d.get("text"),
            key=d.get("key"),
            seconds=d.get("seconds"),
            result=d.get("result"),
            message=d.get("message")
        )


class GSDComputerUse:
    """
    GSD Computer Use Agent.

    True OS-level desktop automation using Z.AI vision models.
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = "GLM-4.6V",
        base_url: str = "https://api.z.ai/api/coding/paas/v4",
        max_steps: int = 30,
        human_like: bool = True,
        platform: str = "darwin"
    ):
        """
        Initialize GSD Computer Use agent.

        Args:
            api_key: Z.AI API key (or set Z_AI_API_KEY env var)
            model: Vision model to use
            base_url: Z.AI API base URL
            max_steps: Maximum steps per task
            human_like: Use human-like delays/movements
            platform: "darwin" (macOS) or "linux"
        """
        self.api_key = api_key or os.getenv("Z_AI_API_KEY")
        self.model = model
        self.base_url = base_url
        self.max_steps = max_steps
        self.human_like = human_like
        self.platform = platform

        # Check availability
        self._check_dependencies()

        # Initialize client
        self.client = None
        if OPENAI_AVAILABLE and self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

        # Screen info
        self.screen_width = 0
        self.screen_height = 0
        self._update_screen_size()

    def _check_dependencies(self):
        """Check if required dependencies are available."""
        missing = []

        if not MSS_AVAILABLE:
            missing.append("mss")
        if not PYAUTOGUI_AVAILABLE:
            missing.append("pyautogui")
        if not OPENAI_AVAILABLE:
            missing.append("openai")

        if missing:
            print(f"Warning: Missing dependencies: {', '.join(missing)}")
            print(f"Install with: pip install {' '.join(missing)}")

        # pynput is optional but recommended
        if not PYNPUT_AVAILABLE:
            print("Note: pynput not available. Using pyautogui only.")

    def _update_screen_size(self):
        """Update screen dimensions."""
        if PYAUTOGUI_AVAILABLE:
            try:
                self.screen_width, self.screen_height = pyautogui.size()
            except Exception:
                self.screen_width, self.screen_height = 2560, 1440  # Default
        else:
            self.screen_width, self.screen_height = 2560, 1440

    def capture_screen(self) -> Tuple[str, int, int]:
        """
        Capture full desktop screenshot.

        Returns:
            Tuple of (base64 image, width, height)
        """
        if not MSS_AVAILABLE:
            raise RuntimeError("mss not installed. Run: pip install mss")

        with mss.mss() as sct:
            # Capture all monitors or primary
            monitor = sct.monitors[0]  # 0 = all monitors
            sct_img = sct.grab(monitor)

            # Convert to PNG base64
            img_bytes = mss.tools.to_png(sct_img.rgb, sct_img.size)
            img_b64 = base64.b64encode(img_bytes).decode()

            return img_b64, sct_img.width, sct_img.height

    def capture_region(self, x: int, y: int, width: int, height: int) -> str:
        """
        Capture a specific screen region.

        Args:
            x, y: Top-left corner
            width, height: Region dimensions

        Returns:
            Base64 encoded PNG
        """
        if not MSS_AVAILABLE:
            raise RuntimeError("mss not installed")

        with mss.mss() as sct:
            region = {
                "left": x,
                "top": y,
                "width": width,
                "height": height
            }
            sct_img = sct.grab(region)
            return base64.b64encode(mss.tools.to_png(sct_img.rgb, sct_img.size)).decode()

    # ==================== MOUSE CONTROL ====================

    def move_mouse(self, x: int, y: int, human: bool = True):
        """
        Move mouse to x, y coordinates.

        Args:
            x, y: Target coordinates
            human: Use human-like curved movement
        """
        if not PYAUTOGUI_AVAILABLE:
            raise RuntimeError("pyautogui not installed")

        if human and self.human_like:
            self._human_move_mouse(x, y)
        else:
            pyautogui.moveTo(x, y)

        self._delay(0.1, 0.2)

    def _human_move_mouse(self, x: int, y: int):
        """
        Move mouse with human-like bezier curve.

        This creates natural-looking mouse paths instead of instant teleportation.
        """
        if not PYAUTOGUI_AVAILABLE:
            return

        # Get current position
        try:
            current_x, current_y = pyautogui.position()
        except Exception:
            current_x, current_y = x, y  # Start at target

        # Calculate bezier control points
        distance = math.sqrt((x - current_x)**2 + (y - current_y)**2)

        if distance < 50:
            # Too close, just move
            pyautogui.moveTo(x, y)
            return

        # Add randomness to path
        mid_x = (current_x + x) // 2 + random.randint(-100, 100)
        mid_y = (current_y + y) // 2 + random.randint(-100, 100)

        # Bezier curve points
        steps = max(int(distance / 20), 10)

        for i in range(steps + 1):
            t = i / steps
            # Quadratic bezier: (1-t)^2 * P0 + 2(1-t)t * P1 + t^2 * P2
            px = (1-t)**2 * current_x + 2*(1-t)*t * mid_x + t**2 * x
            py = (1-t)**2 * current_y + 2*(1-t)*t * mid_y + t**2 * y

            pyautogui.moveTo(int(px), int(py))
            self._delay(0.01, 0.03)

    def click(self, x: int = None, y: int = None, button: str = "left"):
        """
        Click at coordinates.

        Args:
            x, y: Coordinates (None = current position)
            button: "left", "right", or "middle"
        """
        if not PYAUTOGUI_AVAILABLE:
            raise RuntimeError("pyautogui not installed")

        if x is not None and y is not None:
            self.move_mouse(x, y)

        pyautogui.click(button=button)
        self._delay(0.1, 0.3)

    def double_click(self, x: int = None, y: int = None):
        """Double click at coordinates."""
        if not PYAUTOGUI_AVAILABLE:
            raise RuntimeError("pyautogui not installed")

        if x is not None and y is not None:
            self.move_mouse(x, y)

        pyautogui.doubleClick()
        self._delay(0.1, 0.3)

    def right_click(self, x: int = None, y: int = None):
        """Right click at coordinates."""
        self.click(x, y, button="right")

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        """
        Drag from (x1, y1) to (x2, y2).

        Args:
            x1, y1: Start coordinates
            x2, y2: End coordinates
            duration: Drag duration in seconds
        """
        if not PYAUTOGUI_AVAILABLE:
            raise RuntimeError("pyautogui not installed")

        pyautogui.moveTo(x1, y1)
        self._delay(0.1, 0.2)
        pyautogui.mouseDown()
        self._delay(0.1, 0.2)

        # Move in steps for smooth drag
        steps = max(int(duration * 20), 5)
        for i in range(steps):
            t = (i + 1) / steps
            cx = x1 + (x2 - x1) * t
            cy = y1 + (y2 - y1) * t
            pyautogui.moveTo(int(cx), int(cy))
            self._delay(0.04, 0.06)

        pyautogui.mouseUp()
        self._delay(0.1, 0.2)

    # ==================== KEYBOARD CONTROL ====================

    def type_text(self, text: str, human: bool = True):
        """
        Type text string.

        Args:
            text: Text to type
            human: Use human-like typing speed
        """
        if not PYAUTOGUI_AVAILABLE:
            raise RuntimeError("pyautogui not installed")

        if human and self.human_like:
            self._human_type(text)
        else:
            pyautogui.write(text, interval=0.05)

    def _human_type(self, text: str):
        """
        Type with human-like variation.

        Uses random delays between keystrokes to appear more human.
        """
        if not PYAUTOGUI_AVAILABLE:
            return

        for char in text:
            pyautogui.press(char)
            # Variable delay per character
            delay = random.uniform(0.05, 0.15)
            self._delay(delay, delay)

    def press_key(self, key: str):
        """
        Press a keyboard key or key combination.

        Args:
            key: Key name (e.g., "enter", "cmd", "cmd+c", "ctrl+tab")
        """
        if not PYAUTOGUI_AVAILABLE:
            raise RuntimeError("pyautogui not installed")

        # Parse key combination
        key = key.lower().strip()

        if "+" in key:
            # Key combination like "cmd+c"
            parts = key.split("+")
            modifiers = []
            main_key = parts[-1]

            for mod in parts[:-1]:
                if mod in ["cmd", "command", "super"]:
                    modifiers.append("command")
                elif mod in ["ctrl", "control"]:
                    modifiers.append("ctrl")
                elif mod in ["alt", "option"]:
                    modifiers.append("alt")
                elif mod in ["shift"]:
                    modifiers.append("shift")

            pyautogui.hotkey(*modifiers, main_key)
        else:
            # Single key
            pyautogui.press(key)

        self._delay(0.1, 0.3)

    def hotkey(self, *keys):
        """Press key combination (e.g., "command", "c" for Cmd+C)."""
        if not PYAUTOGUI_AVAILABLE:
            raise RuntimeError("pyautogui not installed")

        pyautogui.hotkey(*keys)
        self._delay(0.1, 0.3)

    # ==================== WINDOW MANAGEMENT ====================

    def get_open_windows(self) -> List[Dict[str, str]]:
        """
        Get list of open windows.

        Returns:
            List of window info dicts
        """
        if self.platform == "darwin":
            return self._get_mac_windows()
        else:
            return self._get_linux_windows()

    def _get_mac_windows(self) -> List[Dict[str, str]]:
        """Get open windows on macOS using AppleScript."""
        try:
            script = '''tell application "System Events" to get name of every process whose background only is false'''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=2
            )

            windows = []
            # Parse output
            for line in result.stdout.strip().split("\n"):
                if line:
                    windows.append({"title": line.strip()})

            return windows
        except Exception as e:
            print(f"Error getting windows: {e}")
            return []

    def _get_linux_windows(self) -> List[Dict[str, str]]:
        """Get open windows on Linux."""
        # Use wmctrl or xdotool
        try:
            result = subprocess.run(
                ["wmctrl", "-l"],
                capture_output=True,
                text=True,
                timeout=5
            )

            windows = []
            for line in result.stdout.strip().split("\n"):
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    windows.append({
                        "title": parts[3],
                        "window": parts[0]
                    })

            return windows
        except Exception:
            return []

    def activate_window(self, app_name: str) -> bool:
        """
        Switch to/focus an application.

        Args:
            app_name: Application name (e.g., "Safari")

        Returns:
            True if successful
        """
        if self.platform == "darwin":
            try:
                script = 'tell application "System Events" to get name of every process whose name is "{}"'.format(
                    app_name.replace('"', '').replace('\\', '')
                )
                subprocess.run(
                    ["osascript", "-e", 'tell application "' + app_name.replace('"', '') + '" to activate'],
                    capture_output=True,
                    timeout=5
                )
                self._delay(0.5, 1.0)
                return True
            except Exception as e:
                print(f"Error activating window: {e}")
                return False
        else:
            # Linux - try wmctrl
            try:
                subprocess.run(
                    ["wmctrl", "-a", app_name],
                    capture_output=True,
                    timeout=5
                )
                return True
            except Exception:
                return False

    def launch_app(self, app_path: str, app_name: str = None):
        """
        Launch an application.

        Args:
            app_path: Path to app or app name
            app_name: Optional display name
        """
        if self.platform == "darwin":
            # Use open command
            subprocess.Popen(["open", "-a", app_path])
        else:
            subprocess.Popen([app_path])

        self._delay(1.0, 2.0)

    def minimize_window(self):
        """Minimize current window."""
        if self.platform == "darwin":
            self.press_key("cmd+m")
        else:
            self.press_key("super+down")

    def maximize_window(self):
        """Maximize current window."""
        if self.platform == "darwin":
            # Green button - need to click
            # Get window bounds first
            pass  # TODO

    # ==================== VISION ANALYSIS ====================

    def analyze_screen(self, task: str, screenshot_b64: str = None) -> Action:
        """
        Analyze screen with Z.AI vision model.

        Args:
            task: Task description
            screenshot_b64: Optional screenshot (if None, captures new)

        Returns:
            Action to execute
        """
        if not self.client:
            raise RuntimeError(
                "Z.AI client not initialized. "
                "Set Z_AI_API_KEY or pass api_key."
            )

        # Capture screenshot if not provided
        if not screenshot_b64:
            screenshot_b64, _, _ = self.capture_screen()

        # Get system context
        sys_info = self._get_system_context()

        # Build messages
        system_prompt = """You are a computer use agent. Analyze the desktop screenshot and return a JSON action.

{sys_info}

Available actions (respond ONLY with JSON):
- {{"type": "click", "x": 100, "y": 200}} - MUST click before typing!
- {{"type": "double_click", "x": 100, "y": 200}}
- {{"type": "right_click", "x": 100, "y": 200}}
- {{"type": "type", "text": "hello world"}}
- {{"type": "key", "key": "enter"}} or {{"type": "key", "key": "cmd+c"}}
- {{"type": "move", "x": 500, "y": 300}}
- {{"type": "wait", "seconds": 2}}
- {{"type": "done", "result": "task completed"}}

For "done", include a brief result description.
Always provide exact x,y coordinates for clicks.
Think about what the user wants and plan the next action.""".format(sys_info=sys_info)

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{screenshot_b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": f"Task: {task}\n\nWhat action should I take? Return JSON."
                    }
                ]
            }
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1024,
                temperature=0.1
            )

            content = response.choices[0].message.content

            # Parse JSON from response
            action_dict = self._parse_json_action(content)
            return Action.from_dict(action_dict)

        except Exception as e:
            print(f"Analysis error: {e}")
            return Action(
                type=ActionType.ERROR,
                message=str(e)
            )

    def _parse_json_action(self, content: str) -> dict:
        """Parse JSON action from model response."""
        # Try direct parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from text
        patterns = [
            r'\{[^{}]*\}',  # Simple objects
            r'\{[\s\S]*?\}',  # Multi-line
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue

        # Default error action
        return {"type": "error", "message": "Could not parse action"}

    # ==================== ACTION EXECUTION ====================

    def execute_action(self, action: Action) -> dict:
        """
        Execute an action.

        Args:
            action: Action to execute

        Returns:
            Result dict
        """
        action_type = action.type

        try:
            if action_type == ActionType.CLICK:
                x, y = action.x or 0, action.y or 0
                self.click(x, y)
                return {"success": True, "action": f"clicked at ({x}, {y})"}

            elif action_type == ActionType.DOUBLE_CLICK:
                x, y = action.x or 0, action.y or 0
                self.double_click(x, y)
                return {"success": True, "action": f"double-clicked at ({x}, {y})"}

            elif action_type == ActionType.RIGHT_CLICK:
                x, y = action.x or 0, action.y or 0
                self.right_click(x, y)
                return {"success": True, "action": f"right-clicked at ({x}, {y})"}

            elif action_type == ActionType.MOVE:
                x, y = action.x or 0, action.y or 0
                self.move_mouse(x, y)
                return {"success": True, "action": f"moved to ({x}, {y})"}

            elif action_type == ActionType.TYPE:
                text = action.text or ""
                self.type_text(text)
                return {"success": True, "action": f"typed {len(text)} chars"}

            elif action_type == ActionType.KEY:
                key = action.key or ""
                self.press_key(key)
                return {"success": True, "action": f"pressed {key}"}

            elif action_type == ActionType.WAIT:
                seconds = action.seconds or 1.0
                self._delay(seconds, seconds)
                return {"success": True, "action": f"waited {seconds}s"}

            elif action_type == ActionType.DONE:
                return {
                    "success": True,
                    "done": True,
                    "result": action.result or "Task completed"
                }

            elif action_type == ActionType.ERROR:
                return {
                    "success": False,
                    "error": action.message or "Unknown error"
                }

            else:
                return {
                    "success": False,
                    "error": f"Unknown action type: {action_type}"
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== TASK LOOP ====================

    async def run_task(self, task: str) -> dict:
        """
        Run a computer use task.

        This is the main loop:
        1. Capture screenshot
        2. Analyze with vision model
        3. Execute action
        4. Repeat until done

        Args:
            task: Task description

        Returns:
            Result dict with success, result, steps
        """
        print(f"Starting task: {task}")
        print(f"Screen size: {self.screen_width}x{self.screen_height}")

        for step in range(self.max_steps):
            print(f"\n--- Step {step + 1}/{self.max_steps} ---")

            # Capture screen
            try:
                screenshot, width, height = self.capture_screen()
                print(f"Screenshot: {width}x{height}")
            except Exception as e:
                return {"success": False, "error": f"Screenshot failed: {e}"}

            # Analyze with vision model
            try:
                action = self.analyze_screen(task, screenshot)
                print(f"Action: {action.to_dict()}")
            except Exception as e:
                return {"success": False, "error": f"Analysis failed: {e}"}

            # Execute action
            result = self.execute_action(action)

            # Check for completion
            if action.type == ActionType.DONE:
                return {
                    "success": True,
                    "result": action.result,
                    "steps": step + 1
                }

            # Check for error
            if not result.get("success"):
                return {
                    "success": False,
                    "error": result.get("error"),
                    "steps": step + 1
                }

            # Print action result
            print(f"Result: {result.get('action', 'OK')}")

        return {
            "success": False,
            "error": "Max steps reached",
            "steps": self.max_steps
        }

    def run_task_sync(self, task: str) -> dict:
        """Synchronous wrapper for run_task."""
        try:
            import nest_asyncio
            nest_asyncio.apply()
        except Exception:
            pass

        return asyncio.run(self.run_task(task))

    # ==================== UTILITIES ====================

    def _delay(self, min_sec: float, max_sec: float):
        """Add random delay (for human-like behavior)."""
        if self.human_like:
            time.sleep(random.uniform(min_sec, max_sec))
        else:
            time.sleep(min_sec)

    def get_screen_size(self) -> Tuple[int, int]:
        """Get screen dimensions."""
        return (self.screen_width, self.screen_height)

    def get_mouse_position(self) -> Tuple[int, int]:
        """Get current mouse position."""
        if PYAUTOGUI_AVAILABLE:
            return pyautogui.position()
        return (0, 0)

    def _get_system_context(self) -> str:
        """Get system state for LLM context."""
        sw, sh = self.screen_width, self.screen_height
        mx, my = self.get_mouse_position()
        windows = self.get_open_windows()

        win_list = ", ".join([f'"{w.get("title", "")}"' for w in windows[:10]]) if windows else "None"

        return f"""Current state:
- Screen size: {sw}x{sh}
- Mouse position: ({mx}, {my})
- Open windows: {win_list}

IMPORTANT for typing: You MUST click in the text field BEFORE typing. Use click action first."""


async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="GSD Computer Use - True OS-level Desktop Automation"
    )
    parser.add_argument(
        "--task", "-t",
        type=str,
        required=True,
        help="Task to accomplish"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="Z.AI API Key (or set Z_AI_API_KEY)"
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="GLM-4.6V",
        help="Vision model"
    )
    parser.add_argument(
        "--steps", "-s",
        type=int,
        default=30,
        help="Max steps"
    )
    parser.add_argument(
        "--no-human",
        action="store_true",
        help="Disable human-like behavior"
    )
    parser.add_argument(
        "--platform",
        type=str,
        default="darwin",
        choices=["darwin", "linux"],
        help="Platform"
    )

    args = parser.parse_args()

    agent = GSDComputerUse(
        api_key=args.api_key,
        model=args.model,
        max_steps=args.steps,
        human_like=not args.no_human,
        platform=args.platform
    )

    try:
        result = await agent.run_task(args.task)
        print("\n" + "=" * 50)
        print("RESULT:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
