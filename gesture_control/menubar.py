"""Menu bar app: runs the gesture loop in the background, no preview window."""
import threading
import traceback

import rumps

from . import autostart, config
from .camera import CameraError
from .permissions import accessibility_granted, open_accessibility_settings
from .runner import GestureRunner

SCROLL_PRESETS = {"Slow": 12, "Normal": 20, "Fast": 32}    # SCROLL_GAIN
ZOOM_PRESETS = {"Low": 0.45, "Normal": 0.3, "High": 0.2}   # ZOOM_STEP (lower = more sensitive)

ICON_ON, ICON_PAUSED, ICON_DISARMED = "✋", "⏸", "🔒"


class GestureMenuApp(rumps.App):
    def __init__(self):
        super().__init__("Gesture Control", title=ICON_ON, quit_button=None)
        self.runner = GestureRunner(preview=False, on_event=self._on_event)
        self._error = None
        self._last_event = ""
        self._was_armed = self.runner.engine.armed

        self.status_item = rumps.MenuItem("Starting...")   # no callback = greyed out
        self.pause_item = rumps.MenuItem("Pause", callback=self._toggle_pause)
        self.armed_item = rumps.MenuItem("Armed (hold a fist 2 s to toggle)",
                                         callback=self._toggle_armed)
        self.scroll_menu = self._preset_menu("Scroll speed", SCROLL_PRESETS, self._set_scroll)
        self.zoom_menu = self._preset_menu("Zoom sensitivity", ZOOM_PRESETS, self._set_zoom)
        self.invert_item = rumps.MenuItem("Invert scroll", callback=self._toggle_invert)
        self.swap_item = rumps.MenuItem("Swap swipe direction", callback=self._toggle_swap)
        self.login_item = rumps.MenuItem("Launch at login", callback=self._toggle_login)

        self.menu = [
            self.status_item, None,
            self.pause_item, self.armed_item, None,
            self.scroll_menu, self.zoom_menu, self.invert_item, self.swap_item, None,
            self.login_item,
            rumps.MenuItem("Open Accessibility settings...",
                           callback=lambda _: open_accessibility_settings()),
            rumps.MenuItem("Quit", callback=self._quit),
        ]
        self._sync_menu()

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._timer = rumps.Timer(self._tick, 0.4)
        self._timer.start()

    # --- background loop -------------------------------------------------
    def _run_loop(self):
        try:
            self.runner.run()
        except CameraError as e:
            self._error = ("Camera problem", str(e))
        except Exception as e:  # keep the menu bar alive long enough to report it
            traceback.print_exc()
            self._error = ("Unexpected error", repr(e))

    def _on_event(self, label):
        self._last_event = label

    # --- UI refresh (main thread, via timer) ---------------------------------
    def _tick(self, _):
        if self._error:
            title, message = self._error
            self._error = None
            self._timer.stop()
            rumps.alert(title, message)
            self._quit(None)
            return
        self._sync_menu()

    def _notify_if_arm_changed(self):
        armed = self.runner.engine.armed
        if armed == self._was_armed:
            return
        self._was_armed = armed
        try:
            rumps.notification("Gesture Control", "Armed" if armed else "Disarmed",
                               "Gestures are on." if armed else
                               "Gestures are off. Hold a fist for 2 s or use the menu to arm.")
        except Exception:
            pass  # notifications can be unavailable (e.g. running from source)

    def _sync_menu(self):
        self._notify_if_arm_changed()
        engine = self.runner.engine
        if self.runner.paused:
            self.title, status = ICON_PAUSED, "Paused"
        elif not engine.armed:
            self.title, status = ICON_DISARMED, "Disarmed (hold a fist 2 s to arm)"
        else:
            self.title, status = ICON_ON, "Running"
        if not accessibility_granted():
            status = "Accessibility permission needed"
        if self._last_event:
            status += f" - last: {self._last_event}"
        self.status_item.title = status

        self.pause_item.title = "Resume" if self.runner.paused else "Pause"
        self.armed_item.state = int(engine.armed)
        self.invert_item.state = int(config.INVERT_SCROLL)
        self.swap_item.state = int(config.SWAP_SWIPE_DIRECTION)
        self.login_item.state = int(autostart.is_enabled())
        self._mark_presets(self.scroll_menu, SCROLL_PRESETS, config.SCROLL_GAIN)
        self._mark_presets(self.zoom_menu, ZOOM_PRESETS, config.ZOOM_STEP)

    # --- menu helpers --------------------------------------------------------
    @staticmethod
    def _preset_menu(title, presets, callback):
        parent = rumps.MenuItem(title)
        for name in presets:
            parent.add(rumps.MenuItem(name, callback=callback))
        return parent

    @staticmethod
    def _mark_presets(parent, presets, current):
        for name, value in presets.items():
            parent[name].state = int(abs(value - current) < 1e-9)

    # --- callbacks -------------------------------------------------------------
    def _toggle_pause(self, _):
        self.runner.paused = not self.runner.paused
        self._sync_menu()

    def _toggle_armed(self, _):
        self.runner.engine.armed = not self.runner.engine.armed
        self._sync_menu()

    def _set_scroll(self, sender):
        config.set_value("SCROLL_GAIN", SCROLL_PRESETS[sender.title])
        self._sync_menu()

    def _set_zoom(self, sender):
        config.set_value("ZOOM_STEP", ZOOM_PRESETS[sender.title])
        self._sync_menu()

    def _toggle_invert(self, _):
        config.set_value("INVERT_SCROLL", not config.INVERT_SCROLL)
        self._sync_menu()

    def _toggle_swap(self, _):
        config.set_value("SWAP_SWIPE_DIRECTION", not config.SWAP_SWIPE_DIRECTION)
        self._sync_menu()

    def _toggle_login(self, _):
        if not autostart.available():
            rumps.alert("Launch at login",
                        "This only works in the packaged Gesture Control app, "
                        "not when running from source.")
            return
        autostart.disable() if autostart.is_enabled() else autostart.enable()
        self._sync_menu()

    def _quit(self, _):
        self.runner.stop()
        self._thread.join(timeout=2)
        rumps.quit_application()


def main():
    if not accessibility_granted():
        if rumps.alert("Accessibility permission needed",
                       "Gesture Control needs Accessibility access to scroll and press keys.",
                       ok="Open Settings", cancel="Later"):
            open_accessibility_settings()
    GestureMenuApp().run()


if __name__ == "__main__":
    main()
