"""All tunable parameters. Optional overrides load from a JSON file."""
import json
from pathlib import Path

APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "GestureControl"
OVERRIDES_FILE = APP_SUPPORT_DIR / "config.json"

# Camera
CAMERA_INDEX = 0            # use 1 if iPhone Continuity Camera takes index 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# Hand tracking
DETECTION_CONFIDENCE = 0.6
FINGER_EXTEND_RATIO = 1.05  # tip must be this much farther from wrist than the PIP joint

# Pose / smoothing
POSE_STABLE_FRAMES = 3      # higher = fewer flickers, slower response
SMOOTHING = 0.5             # higher = smoother, more lag

# Arm / disarm (hold a closed fist to toggle)
START_ARMED = True
ARM_HOLD_S = 2.0

# Scroll (joystick model)
SCROLL_DEADZONE = 0.06      # movement needed before scrolling starts
SCROLL_SETTLE_S = 0.4       # after a scroll/zoom pose appears, reference follows the hand, no action
SCROLL_GAIN = 20           # scroll speed
SCROLL_MAX_PER_FRAME = 6    # scroll speed cap
INVERT_SCROLL = False       # flip if direction feels wrong

# Zoom (pinch spread: thumb + index gap, relative to hand size)
ZOOM_STEP = 0.3             # gap change (in hand sizes) that fires one zoom step
ZOOM_MIN_INTERVAL_S = 0.25  # minimum time between zoom steps
INVERT_ZOOM = False         # flip if spread/close feels backwards

# Swipe
SWIPE_WINDOW_S = 0.35       # time window for a swipe
SWIPE_DISTANCE = 0.25       # fraction of frame width a swipe must cover
SWIPE_MAX_VERTICAL = 0.12   # rejects diagonal motion
COOLDOWN_S = 1.2            # gap after next/prev
SWAP_SWIPE_DIRECTION = True   # left-to-right = previous, right-to-left = next

# Keys sent for next / previous (pyautogui key names)
NEXT_KEY = ("right",)       # e.g. ("command", "]") for browser forward
PREV_KEY = ("left",)
ZOOM_IN_KEY = ("command", "=")   # Cmd + (the "+" key is "=" without shift)
ZOOM_OUT_KEY = ("command", "-")

# Per-app overrides, keyed by macOS bundle id. Any of: next, prev, zoom_in, zoom_out.
# Apps not listed (or keys not listed) use the global keys above. Example:
#   APP_KEYS = {
#       "com.apple.Safari":    {"next": ("command", "]"), "prev": ("command", "[")},
#       "com.google.Chrome":   {"next": ("command", "]"), "prev": ("command", "[")},
#       "com.apple.Preview":   {"next": ("pagedown",),    "prev": ("pageup",)},
#   }
# Find an app's bundle id with:  osascript -e 'id of app "Safari"'
APP_KEYS = {}


def _load_overrides():
    try:
        data = json.loads(OVERRIDES_FILE.read_text())
    except (OSError, ValueError):
        return
    for name, value in data.items():
        if name in globals() and name.isupper():
            globals()[name] = tuple(value) if isinstance(value, list) else value


def set_value(name, value):
    """Change a setting now and persist it to the overrides file."""
    if name not in globals() or not name.isupper():
        raise KeyError(name)
    globals()[name] = value
    try:
        data = json.loads(OVERRIDES_FILE.read_text())
    except (OSError, ValueError):
        data = {}
    data[name] = value
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    OVERRIDES_FILE.write_text(json.dumps(data, indent=2))


_load_overrides()
