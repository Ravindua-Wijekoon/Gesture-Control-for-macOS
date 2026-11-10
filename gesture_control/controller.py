"""Turns engine actions into macOS input (pyautogui), or just prints in dry-run."""
from . import config


def frontmost_bundle_id():
    """Bundle id of the frontmost app, or None if it cannot be determined."""
    try:
        from AppKit import NSWorkspace

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return str(app.bundleIdentifier()) if app else None
    except Exception:
        return None


def keys_for(kind, default):
    """Per-app override for `kind` (next/prev/zoom_in/zoom_out), else `default`."""
    if config.APP_KEYS:
        override = config.APP_KEYS.get(frontmost_bundle_id() or "", {}).get(kind)
        if override:
            return tuple(override)
    return default


class Controller:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self._pg = None
        if not dry_run:
            import pyautogui

            pyautogui.FAILSAFE = True   # mouse into a screen corner aborts
            pyautogui.PAUSE = 0
            self._pg = pyautogui

    def perform(self, action):
        """Execute one Action; return a short label for the HUD."""
        if action.kind == "arm":
            label = "ARMED" if action.amount else "DISARMED"
            if self.dry_run:
                print(f"[dry-run] {label}")
            return label

        if action.kind == "scroll":
            label = f"SCROLL {'UP' if action.amount > 0 else 'DOWN'}"
            if self.dry_run:
                print(f"[dry-run] scroll {action.amount:+d}")
            else:
                self._pg.scroll(action.amount)
            return label

        if action.kind == "zoom":
            zoom_in = action.amount > 0
            keys = (keys_for("zoom_in", config.ZOOM_IN_KEY) if zoom_in
                    else keys_for("zoom_out", config.ZOOM_OUT_KEY))
            label = "ZOOM IN" if zoom_in else "ZOOM OUT"
        elif action.kind == "next":
            keys, label = keys_for("next", config.NEXT_KEY), "NEXT"
        else:
            keys, label = keys_for("prev", config.PREV_KEY), "PREVIOUS"
        if self.dry_run:
            print(f"[dry-run] {label} -> {'+'.join(keys)}")
        elif len(keys) == 1:
            self._pg.press(keys[0])
        else:
            self._pg.hotkey(*keys)
        return label
