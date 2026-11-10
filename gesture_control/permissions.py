"""macOS permission helpers."""
import ctypes
import ctypes.util
import subprocess

_ACCESSIBILITY_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
_CAMERA_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera"


def accessibility_granted():
    """True if this process may send input events. Unknown -> True (don't block)."""
    try:
        lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices"))
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(lib.AXIsProcessTrusted())
    except (OSError, AttributeError, TypeError):
        return True


def open_accessibility_settings():
    subprocess.run(["open", _ACCESSIBILITY_URL], check=False)


def open_camera_settings():
    subprocess.run(["open", _CAMERA_URL], check=False)
