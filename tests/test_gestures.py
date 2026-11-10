"""Engine tests using synthetic landmarks (no camera needed)."""
from collections import namedtuple

from gesture_control.gestures import GestureEngine

P = namedtuple("P", ["x", "y", "z"])
DT = 1 / 30

# finger name -> (x offset, MCP idx, PIP idx, tip idx)
_FINGERS = {
    "index": (-0.03, 5, 6, 8),
    "middle": (-0.01, 9, 10, 12),
    "ring": (0.01, 13, 14, 16),
    "pinky": (0.03, 17, 18, 20),
}


def make_hand(cx, cy, extended, thumb_gap=0.0):
    """21 landmarks; `extended` is the set of finger names that are up.

    thumb_gap: horizontal distance of the thumb tip from the index tip.
    """
    pts = [P(cx, cy + 0.10, 0)] * 21  # everything defaults to the wrist
    pts = list(pts)
    for name, (dx, mcp, pip, tip) in _FINGERS.items():
        pts[mcp] = P(cx + dx, cy + 0.02, 0)
        pts[pip] = P(cx + dx, cy - 0.02, 0)
        tip_y = cy - 0.10 if name in extended else cy + 0.0
        pts[tip] = P(cx + dx, tip_y, 0)
    pts[4] = P(cx - 0.03 + thumb_gap, cy - 0.10, 0)  # thumb tip, level with index tip
    return pts


PALM = {"index", "middle", "ring", "pinky"}
TWO = {"index", "middle"}
PINCH = {"index"}
FIST = set()


class Runner:
    """Feeds frames to an engine with a running clock and collects actions."""

    def __init__(self):
        self.engine = GestureEngine()
        self.t = 0.0
        self.actions = []

    def feed(self, cx, cy, fingers, thumb_gap=0.0):
        self.t += DT
        self.actions += self.engine.update(make_hand(cx, cy, fingers, thumb_gap), self.t)

    def spread(self, start, end, frames):
        """Pinch pose with the thumb gap moving linearly from start to end."""
        for i in range(1, frames + 1):
            self.feed(0.5, 0.5, PINCH, start + (end - start) * i / frames)

    def lose_hand(self):
        self.t += DT
        self.actions += self.engine.update(None, self.t)

    def hold(self, cx, cy, fingers, frames):
        for _ in range(frames):
            self.feed(cx, cy, fingers)

    def move(self, start, step, fingers, frames):
        x, y = start
        for _ in range(frames):
            x += step[0]
            y += step[1]
            self.feed(x, y, fingers)
        return x, y

    def kinds(self):
        return [a.kind for a in self.actions]


def test_still_two_fingers_no_scroll():
    r = Runner()
    r.hold(0.5, 0.5, TWO, 30)
    assert r.actions == []


def test_moving_into_position_does_not_scroll():
    r = Runner()
    # Hand drifts downward while the pose is forming/settling (first ~0.4 s).
    r.move((0.5, 0.3), (0, 0.01), TWO, 10)
    assert r.actions == []
    # After settling, holding still at the new spot must not scroll either.
    r.hold(0.5, 0.4, TWO, 20)
    assert r.actions == []


def test_two_fingers_up_scrolls_positive():
    r = Runner()
    r.hold(0.5, 0.5, TWO, 20)
    r.move((0.5, 0.5), (0, -0.01), TWO, 15)
    scrolls = [a.amount for a in r.actions if a.kind == "scroll"]
    assert scrolls and all(n > 0 for n in scrolls)


def test_two_fingers_down_scrolls_negative():
    r = Runner()
    r.hold(0.5, 0.5, TWO, 20)
    r.move((0.5, 0.5), (0, 0.01), TWO, 15)
    scrolls = [a.amount for a in r.actions if a.kind == "scroll"]
    assert scrolls and all(n < 0 for n in scrolls)


def test_fast_swipe_right_fires_one_prev():
    r = Runner()
    r.hold(0.3, 0.5, PALM, 20)
    r.move((0.3, 0.5), (0.05, 0), PALM, 6)
    r.hold(0.6, 0.5, PALM, 5)
    assert r.kinds() == ["prev"]


def test_fast_swipe_left_fires_one_next():
    r = Runner()
    r.hold(0.7, 0.5, PALM, 20)
    r.move((0.7, 0.5), (-0.05, 0), PALM, 6)
    r.hold(0.4, 0.5, PALM, 5)
    assert r.kinds() == ["next"]


def test_slow_palm_drift_does_nothing():
    r = Runner()
    r.hold(0.2, 0.5, PALM, 20)
    r.move((0.2, 0.5), (0.005, 0), PALM, 60)
    assert r.actions == []


def test_diagonal_swipe_does_nothing():
    r = Runner()
    r.hold(0.3, 0.3, PALM, 20)
    r.move((0.3, 0.3), (0.05, 0.04), PALM, 6)
    assert r.actions == []


def test_fast_fist_does_nothing():
    r = Runner()
    r.hold(0.3, 0.5, FIST, 6)
    r.move((0.3, 0.5), (0.05, 0), FIST, 6)
    assert r.actions == []


def test_quick_return_within_cooldown_gives_one_command():
    r = Runner()
    r.hold(0.3, 0.5, PALM, 20)
    x, y = r.move((0.3, 0.5), (0.05, 0), PALM, 6)
    r.move((x, y), (-0.05, 0), PALM, 6)  # return swipe, well inside 0.8 s
    assert r.kinds() == ["prev"]


def test_still_pinch_no_zoom():
    r = Runner()
    r.hold(0.5, 0.5, PINCH, 30)
    assert r.actions == []


def test_pinch_spread_zooms_in():
    r = Runner()
    for _ in range(20):
        r.feed(0.5, 0.5, PINCH, 0.02)
    r.spread(0.02, 0.12, 15)
    zooms = [a.amount for a in r.actions if a.kind == "zoom"]
    assert zooms and all(n > 0 for n in zooms)


def test_pinch_close_zooms_out():
    r = Runner()
    for _ in range(20):
        r.feed(0.5, 0.5, PINCH, 0.12)
    r.spread(0.12, 0.02, 15)
    zooms = [a.amount for a in r.actions if a.kind == "zoom"]
    assert zooms and all(n < 0 for n in zooms)


def test_changing_gap_while_settling_does_not_zoom():
    r = Runner()
    r.spread(0.02, 0.12, 10)  # gap changing during the first ~0.33 s
    assert r.actions == []


def test_pinch_never_scrolls_or_swipes():
    r = Runner()
    for _ in range(20):
        r.feed(0.5, 0.5, PINCH, 0.02)
    r.spread(0.02, 0.12, 15)
    assert {a.kind for a in r.actions} <= {"zoom"}


def test_swipe_right_as_hand_enters_is_ignored():
    r = Runner()
    r.hold(0.3, 0.5, PALM, 6)             # pose just became active (still settling)
    r.move((0.3, 0.5), (0.05, 0), PALM, 6)
    assert r.actions == []


def test_fist_hold_disarms_then_rearms():
    r = Runner()
    r.hold(0.5, 0.5, FIST, 70)             # > 2 s
    assert [(a.kind, a.amount) for a in r.actions] == [("arm", 0)]
    assert not r.engine.armed
    r.hold(0.5, 0.5, PALM, 5)              # open the hand, then fist again
    r.hold(0.5, 0.5, FIST, 70)
    assert [(a.kind, a.amount) for a in r.actions] == [("arm", 0), ("arm", 1)]
    assert r.engine.armed


def test_long_fist_toggles_only_once():
    r = Runner()
    r.hold(0.5, 0.5, FIST, 120)            # 4 s
    assert r.kinds() == ["arm"]


def test_short_fist_does_not_toggle():
    r = Runner()
    r.hold(0.5, 0.5, FIST, 50)             # 1.67 s < 2 s
    assert r.actions == []
    assert r.engine.armed


def test_disarmed_ignores_gestures():
    r = Runner()
    r.hold(0.5, 0.5, FIST, 70)             # disarm
    r.actions.clear()
    r.hold(0.3, 0.5, PALM, 20)
    r.move((0.3, 0.5), (0.05, 0), PALM, 6)  # would be a swipe if armed
    assert r.actions == []


def test_hand_loss_resets_state():
    r = Runner()
    r.hold(0.5, 0.5, TWO, 6)
    r.lose_hand()
    assert r.engine.pose == "none"
    # Hand reappears far from the old anchor: must not scroll immediately.
    r.hold(0.5, 0.8, TWO, 10)
    assert r.actions == []
