"""Gesture engine: pose classification + scroll/swipe logic. Pure logic, no I/O."""
import math
from collections import deque, namedtuple

from . import config

# kind: "scroll" | "next" | "prev"; amount: scroll clicks (+ up, - down), else 0
Action = namedtuple("Action", ["kind", "amount"])

WRIST = 0
PALM_POINTS = (0, 5, 9, 13, 17)
# (tip, pip) landmark indices
FINGERS = {"index": (8, 6), "middle": (12, 10), "ring": (16, 14), "pinky": (20, 18)}

POSE_NONE, POSE_PALM, POSE_TWO, POSE_PINCH, POSE_FIST = (
    "none", "palm", "two", "pinch", "fist")
THUMB_TIP, INDEX_TIP, MIDDLE_MCP = 4, 8, 9


def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def finger_extended(lm, name):
    """Rotation-tolerant: the tip is farther from the wrist than the PIP joint."""
    tip, pip = FINGERS[name]
    return _dist(lm[tip], lm[WRIST]) > _dist(lm[pip], lm[WRIST]) * config.FINGER_EXTEND_RATIO


def classify_pose(lm):
    ext = {name: finger_extended(lm, name) for name in FINGERS}
    if all(ext.values()):
        return POSE_PALM
    if ext["index"] and ext["middle"] and not ext["ring"] and not ext["pinky"]:
        return POSE_TWO
    # Thumb is ignored here: only the index is up; the thumb-index gap is the control.
    if ext["index"] and not ext["middle"] and not ext["ring"] and not ext["pinky"]:
        return POSE_PINCH
    if not any(ext.values()):
        return POSE_FIST
    return POSE_NONE


def pinch_gap(lm):
    """Thumb-tip to index-tip distance, normalized by hand size (wrist to middle MCP)."""
    size = _dist(lm[WRIST], lm[MIDDLE_MCP])
    return _dist(lm[THUMB_TIP], lm[INDEX_TIP]) / max(size, 1e-6)


def palm_center(lm):
    xs = [lm[i].x for i in PALM_POINTS]
    ys = [lm[i].y for i in PALM_POINTS]
    return sum(xs) / len(xs), sum(ys) / len(ys)


class GestureEngine:
    def __init__(self):
        self.pose = POSE_NONE      # debounced, active pose (for the HUD)
        self._candidate = POSE_NONE
        self._candidate_frames = 0
        self._cooldown_until = 0.0
        self._settle_until = 0.0   # scroll/zoom reference follows the hand until then
        self.armed = config.START_ARMED
        self._pose_since = 0.0
        self._fist_fired = False
        self._reset_tracking()

    def _reset_tracking(self):
        self._smoothed = None      # EMA of palm centre (x, y)
        self._anchor_y = None      # scroll anchor
        self._gap_s = None         # EMA of pinch gap
        self._gap_ref = None       # zoom reference gap
        self._last_zoom_t = -1e9
        self._history = deque()    # (t, x, y) for swipe detection

    def _reset_all(self):
        self.pose = POSE_NONE
        self._candidate = POSE_NONE
        self._candidate_frames = 0
        self._reset_tracking()

    def _debounce(self, raw):
        """Return True if the active pose changed this frame."""
        if raw == self._candidate:
            self._candidate_frames += 1
        else:
            self._candidate = raw
            self._candidate_frames = 1
        if (self._candidate != self.pose
                and self._candidate_frames >= config.POSE_STABLE_FRAMES):
            self.pose = self._candidate
            return True
        return False

    def update(self, landmarks, t):
        """Feed one frame (landmarks or None, timestamp in seconds) -> list[Action]."""
        if landmarks is None:
            self._reset_all()
            return []

        if self._debounce(classify_pose(landmarks)):
            self._reset_tracking()
            self._settle_until = t + config.SCROLL_SETTLE_S
            self._pose_since = t
            self._fist_fired = False

        if self.pose == POSE_FIST:
            # Hold a fist to toggle armed; fires once, must open the hand to re-toggle.
            if not self._fist_fired and t - self._pose_since >= config.ARM_HOLD_S:
                self._fist_fired = True
                self.armed = not self.armed
                return [Action("arm", int(self.armed))]
            return []
        if not self.armed:
            return []

        x, y = palm_center(landmarks)
        a = config.SMOOTHING
        if self._smoothed is None:
            self._smoothed = (x, y)
        else:
            sx, sy = self._smoothed
            self._smoothed = (a * sx + (1 - a) * x, a * sy + (1 - a) * y)

        if self.pose == POSE_TWO:
            return self._scroll(t)
        if self.pose == POSE_PINCH:
            return self._zoom(t, pinch_gap(landmarks))
        if self.pose == POSE_PALM:
            return self._swipe(t, x, y)
        return []

    def _scroll(self, t):
        _, sy = self._smoothed
        if self._anchor_y is None or t < self._settle_until:
            self._anchor_y = sy   # still settling: neutral point follows the hand
            return []
        offset = self._anchor_y - sy   # positive = hand moved up
        magnitude = abs(offset) - config.SCROLL_DEADZONE
        if magnitude <= 0:
            return []
        clicks = int(round(min(magnitude * config.SCROLL_GAIN, config.SCROLL_MAX_PER_FRAME)))
        if clicks == 0:
            return []
        if (offset < 0) != config.INVERT_SCROLL:
            clicks = -clicks
        return [Action("scroll", clicks)]

    def _zoom(self, t, gap):
        a = config.SMOOTHING
        self._gap_s = gap if self._gap_s is None else a * self._gap_s + (1 - a) * gap
        if self._gap_ref is None or t < self._settle_until:
            self._gap_ref = self._gap_s   # still settling: reference follows the hand
            return []
        change = self._gap_s - self._gap_ref
        if abs(change) < config.ZOOM_STEP or t - self._last_zoom_t < config.ZOOM_MIN_INTERVAL_S:
            return []
        self._gap_ref = self._gap_s       # ratchet: next step is measured from here
        self._last_zoom_t = t
        step = 1 if change > 0 else -1
        return [Action("zoom", -step if config.INVERT_ZOOM else step)]

    def _swipe(self, t, x, y):
        if t < self._cooldown_until or t < self._settle_until:
            self._history.clear()
            return []
        self._history.append((t, x, y))
        while self._history and t - self._history[0][0] > config.SWIPE_WINDOW_S:
            self._history.popleft()

        _, x0, y0 = self._history[0]
        dx, dy = x - x0, y - y0
        if abs(dx) < config.SWIPE_DISTANCE or abs(dy) > config.SWIPE_MAX_VERTICAL:
            return []

        self._cooldown_until = t + config.COOLDOWN_S
        self._history.clear()
        go_next = (dx > 0) != config.SWAP_SWIPE_DIRECTION
        return [Action("next" if go_next else "prev", 0)]
