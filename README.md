# Gesture Control for macOS

Control your Mac with hand gestures through the built-in webcam. A small menu bar app that turns four kinds of hand movement into scrolling, page turning and zooming. It runs fully offline: camera frames never leave your machine, and every component is open source.

> Personal prototype for local use on one Mac. Not signed or notarized for distribution.

## Gestures

| Command | Gesture | Sent to macOS |
|---|---|---|
| Scroll up / down | Raise index + middle finger, hold still briefly, then move your hand up / down | Mouse-wheel scroll (speed grows with distance moved) |
| Previous / Next | Open palm, quick swipe left-to-right / right-to-left | Left / Right arrow key (configurable) |
| Zoom in / out | Index finger + thumb, spread apart / bring together | `Cmd +` / `Cmd -` (configurable) |
| Arm / disarm | Closed fist held for 2 seconds | Turns gesture control on or off |

Any other hand shape is ignored, so ordinary hand movement does not trigger anything. After a gesture pose appears there is a short (0.4 s) settling period before it takes effect, which prevents false triggers while your hand is still moving into position.

## How it works

```
Webcam ──frames──▶ Hand tracker ──21 landmarks──▶ Gesture engine ──actions──▶ Controller ──▶ macOS
(OpenCV)           (MediaPipe                      (pose + motion             (PyAutoGUI)
                    HandLandmarker)                 rules, pure Python)
```

- **Hand tracker:** MediaPipe's Tasks API `HandLandmarker` finds one hand and returns 21 landmarks per frame.
- **Gesture engine:** classifies the pose (palm, two fingers, pinch, fist), debounces it, smooths the hand position, and applies the motion rules. It has no camera or OS code inside, so it is unit-tested with synthetic hands.
  - *Scroll* uses a joystick model: the hand's distance from a start point sets the speed, with a dead zone to ignore jitter.
  - *Swipe* looks at the palm's travel over a ~0.35 s window, rejects diagonal motion, and applies a cooldown so one swipe sends one command.
  - *Zoom* is a ratchet: each fixed change in thumb-index gap (measured relative to hand size) fires one zoom step.
- **Controller:** sends the actions to macOS with PyAutoGUI, or only prints them in dry-run mode. It can use different keys per app.
- **Menu bar app:** runs the loop in the background with a menu for pause, arm, sensitivity presets and launch at login.

## Requirements

- macOS with a webcam
- Python 3.11 or 3.12 (MediaPipe wheels may not exist for newer versions)
- Camera permission and Accessibility permission (see below)

## Setup

```bash
git clone https://github.com/Ravindua-Wijekoon/hg_control.git
cd hg_control
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The hand tracking model `hand_landmarker.task` is included in the repository.

## Usage

**Menu bar app** (the everyday way to run it):

```bash
.venv/bin/python launch_menubar.py
```

A ✋ icon appears in the menu bar: ✋ running, ⏸ paused, 🔒 disarmed. The menu has Pause, Armed, Scroll speed, Zoom sensitivity, Invert scroll, Swap swipe direction, Launch at login (packaged app only), and Quit. Settings you change are saved to `~/Library/Application Support/GestureControl/config.json`.

**Command line with a preview window** (best for testing and tuning):

```bash
.venv/bin/python -m gesture_control.main --dry-run   # print commands, send nothing
.venv/bin/python -m gesture_control.main             # real control
```

| Option | Meaning |
|---|---|
| `--dry-run` | Print what would happen without controlling the Mac. Start here. |
| `--camera N` | Camera index (use `1` if an iPhone Continuity Camera takes index 0) |
| `--stats` | Count commands and print a summary on exit, for measuring hit rate and false triggers |

In the preview window: `q` or Esc quits, `p` pauses. Moving the mouse into a screen corner aborts control (PyAutoGUI fail-safe).

## macOS permissions and behaviour

- **Camera:** allowed on first launch.
- **Accessibility:** enable your terminal, VS Code, or the packaged app in System Settings → Privacy & Security → Accessibility. Without it, PyAutoGUI fails silently. The app warns you when it is missing.
- Scroll events go to the window **under the mouse pointer**. Key presses go to the **frontmost app**, so click your browser or PDF window first.

## Configuration

All tunable values live in [`gesture_control/config.py`](gesture_control/config.py). You can override any of them in `~/Library/Application Support/GestureControl/config.json`. Useful ones:

| Setting | Effect |
|---|---|
| `SCROLL_GAIN`, `SCROLL_DEADZONE`, `SCROLL_MAX_PER_FRAME` | Scroll speed and sensitivity |
| `SWIPE_DISTANCE`, `COOLDOWN_S` | How big a swipe must be, and the gap between commands |
| `ZOOM_STEP` | Finger-gap change per zoom step (lower = more sensitive) |
| `NEXT_KEY`, `PREV_KEY`, `ZOOM_IN_KEY`, `ZOOM_OUT_KEY` | Keys sent for each command |
| `APP_KEYS` | Per-app key overrides by bundle id, e.g. browser back / forward |
| `INVERT_SCROLL`, `SWAP_SWIPE_DIRECTION`, `INVERT_ZOOM` | Flip directions that feel wrong |
| `ARM_HOLD_S`, `START_ARMED` | Fist hold time for arm / disarm, and the starting state |

## Tests

```bash
.venv/bin/python -m pytest tests/
```

21 unit tests drive the gesture engine with synthetic hand landmarks (no camera needed). They cover scrolling in both directions, swipes in both directions, slow drift, diagonal motion, a moving fist, the swipe cooldown, hand loss mid-gesture, the settling period, pinch zoom, and arm / disarm.

## Build the app and installer

```bash
./build_mac.sh
```

Produces `dist/Gesture Control.app` and `Gesture Control.dmg` (PyInstaller, a camera usage description in `Info.plist`, menu-bar-only mode, ad-hoc code signing, and a drag-to-Applications disk image). After installing:

1. Launch the app. If macOS blocks it, right-click → **Open**.
2. Allow Camera, then enable **Gesture Control** under Accessibility.
3. After every rebuild macOS may treat the app as new, so switch its Accessibility permission off and on again.

## Project structure

```
gesture_control/
├── config.py       tunable settings and saved overrides
├── camera.py       webcam capture, mirroring, camera error handling
├── tracker.py      MediaPipe HandLandmarker wrapper and model lookup
├── gestures.py     pose classifier + gesture engine (pure logic)
├── controller.py   PyAutoGUI actions, dry-run, per-app keys
├── runner.py       camera → tracker → engine → controller loop
├── hud.py          preview overlay
├── main.py         command-line entry point
├── menubar.py      menu bar app
├── autostart.py    launch at login (LaunchAgent)
└── permissions.py  Accessibility check and settings shortcuts
tests/test_gestures.py   engine unit tests
launch_menubar.py        entry point for the packaged app
build_mac.sh             builds the .app and .dmg
plan.md                  original design and development plan
```

## Tech stack

Python · MediaPipe (Tasks API) · OpenCV · PyAutoGUI · rumps · PyInstaller · pytest

## Limitations

- One hand at a time, macOS only.
- Gesture thresholds are tuned by hand and not yet validated with a formal accuracy test. Use `--stats` to measure hit rate and false triggers on your own setup.
- A relaxed, curled hand can look like a fist. Holding it for 2 seconds disarms the app, which is shown by the 🔒 icon and a notification.
- Ad-hoc signed only; other Macs will show Gatekeeper warnings.

## Ideas for later

Optional extras from the original plan: more gestures (play / pause, click), a trained classifier instead of hand-written rules, dynamic gestures, and a native Swift rewrite using Apple Vision.

## Acknowledgements

Hand tracking by [MediaPipe](https://github.com/google-ai-edge/mediapipe) (Apache 2.0).
