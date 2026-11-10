"""MediaPipe HandLandmarker wrapper (Tasks API)."""
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    HandLandmarker,
    HandLandmarkerOptions,
    RunningMode,
)

from . import config

MODEL_NAME = "hand_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)


def resolve_model_path():
    """Bundle (PyInstaller) -> project dir -> App Support (downloaded on first run)."""
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / MODEL_NAME)
    candidates.append(Path(__file__).resolve().parent.parent / MODEL_NAME)
    candidates.append(config.APP_SUPPORT_DIR / MODEL_NAME)
    for path in candidates:
        if path.exists():
            return str(path)

    dest = config.APP_SUPPORT_DIR / MODEL_NAME
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(MODEL_URL, dest)
    return str(dest)


class HandTracker:
    def __init__(self):
        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=resolve_model_path()),
            running_mode=RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=config.DETECTION_CONFIDENCE,
            min_hand_presence_confidence=config.DETECTION_CONFIDENCE,
            min_tracking_confidence=config.DETECTION_CONFIDENCE,
        )
        self._landmarker = HandLandmarker.create_from_options(options)
        self._last_ts_ms = -1

    def detect(self, bgr_frame):
        """Return the 21 landmarks (each with .x .y .z, normalized) or None."""
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        # VIDEO mode requires strictly increasing timestamps.
        ts_ms = max(int(time.monotonic() * 1000), self._last_ts_ms + 1)
        self._last_ts_ms = ts_ms
        result = self._landmarker.detect_for_video(image, ts_ms)
        if not result.hand_landmarks:
            return None
        return result.hand_landmarks[0]

    def close(self):
        self._landmarker.close()
