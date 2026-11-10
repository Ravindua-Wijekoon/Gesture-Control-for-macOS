"""Webcam capture with horizontal mirroring."""
import time

import cv2

from . import config

FIRST_FRAME_TIMEOUT_S = 3.0


class CameraError(RuntimeError):
    """Camera cannot be used; the message is safe to show to the user."""


class Camera:
    def __init__(self, index=None):
        index = config.CAMERA_INDEX if index is None else index
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            self.cap.release()
            raise CameraError(
                f"Cannot open camera {index}. It may be in use by another app, "
                "unplugged, or the wrong index (try --camera 1)."
            )
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        self._wait_for_first_frame()

    def _wait_for_first_frame(self):
        # A camera blocked by macOS privacy settings often opens fine but gives no frames.
        deadline = time.monotonic() + FIRST_FRAME_TIMEOUT_S
        while time.monotonic() < deadline:
            ok, _ = self.cap.read()
            if ok:
                return
            time.sleep(0.05)
        self.cap.release()
        raise CameraError(
            "The camera gave no video. Allow camera access in System Settings > "
            "Privacy & Security > Camera, then restart."
        )

    def read(self):
        """Return a mirrored BGR frame, or None if the read failed."""
        ok, frame = self.cap.read()
        if not ok:
            return None
        return cv2.flip(frame, 1)

    def release(self):
        self.cap.release()
