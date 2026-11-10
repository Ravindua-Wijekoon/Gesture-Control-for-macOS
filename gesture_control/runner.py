"""The camera -> tracker -> engine -> controller loop, usable with or without a preview."""
import threading
import time

import cv2

from .camera import Camera, CameraError
from .controller import Controller
from .gestures import GestureEngine
from .hud import draw
from .tracker import HandTracker

FLASH_S = 0.6           # how long the last command stays on the preview
MAX_MISSED_FRAMES = 90  # ~3 s of no video before giving up


class GestureRunner:
    def __init__(self, camera_index=None, dry_run=False, preview=True, on_event=None):
        self.camera_index = camera_index
        self.dry_run = dry_run
        self.preview = preview
        self.on_event = on_event      # called with a label string after every action
        self.engine = GestureEngine()
        self.paused = False
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        """Run until stop() or `q`. Raises CameraError if the camera fails."""
        camera = Camera(self.camera_index)
        try:
            tracker = HandTracker()
            try:
                self._loop(camera, tracker, Controller(dry_run=self.dry_run))
            finally:
                tracker.close()
        finally:
            camera.release()
            if self.preview:
                cv2.destroyAllWindows()

    def _loop(self, camera, tracker, controller):
        last_label, last_label_t = "", 0.0
        prev_t = time.monotonic()
        fps = 0.0
        missed = 0

        while not self._stop.is_set():
            frame = camera.read()
            if frame is None:
                missed += 1
                if missed > MAX_MISSED_FRAMES:
                    raise CameraError("The camera stopped delivering video.")
                time.sleep(0.03)
                continue
            missed = 0

            now = time.monotonic()
            fps = 0.9 * fps + 0.1 / max(now - prev_t, 1e-6)
            prev_t = now

            landmarks = tracker.detect(frame)
            if self.paused:
                self.engine.update(None, now)  # keep the engine reset while paused
            else:
                for action in self.engine.update(landmarks, now):
                    last_label, last_label_t = controller.perform(action), now
                    if self.on_event:
                        self.on_event(last_label)

            if self.preview:
                shown = last_label if now - last_label_t < FLASH_S else ""
                draw(frame, landmarks, self.engine.pose, fps, shown, self.paused,
                     self.dry_run, self.engine.armed)
                cv2.imshow("Gesture Control", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord("p"):
                    self.paused = not self.paused
