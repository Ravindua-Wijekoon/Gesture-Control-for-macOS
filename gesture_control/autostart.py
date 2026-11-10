"""Launch at login via a per-user LaunchAgent (only meaningful for the packaged .app)."""
import plistlib
import sys
from pathlib import Path

LABEL = "local.gesturecontrol"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def available():
    """True when running as the packaged .app (a script run has no bundle to launch)."""
    return bool(getattr(sys, "frozen", False))


def _bundle_path():
    # .../Gesture Control.app/Contents/MacOS/Gesture Control -> .../Gesture Control.app
    return Path(sys.executable).resolve().parents[2]


def is_enabled():
    return PLIST_PATH.exists()


def enable():
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PLIST_PATH.open("wb") as f:
        plistlib.dump(
            {
                "Label": LABEL,
                "ProgramArguments": ["/usr/bin/open", "-a", str(_bundle_path())],
                "RunAtLoad": True,
            },
            f,
        )


def disable():
    PLIST_PATH.unlink(missing_ok=True)
