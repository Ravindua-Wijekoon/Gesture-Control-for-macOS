# Hand Gesture Control for macOS — System & Development Plan

## 1. Overview

A small macOS desktop app that uses the built-in webcam to watch the user's hand and turns four gestures into computer commands:

| Command | Gesture | Action sent to macOS |
|---|---|---|
| Scroll up | ✌️ Two fingers (index + middle up), move hand **up** from start point | Mouse-wheel scroll up |
| Scroll down | ✌️ Two fingers, move hand **down** from start point | Mouse-wheel scroll down |
| Next | 🖐 Open palm, quick swipe **right** | Right-arrow key (configurable) |
| Previous | 🖐 Open palm, quick swipe **left** | Left-arrow key (configurable) |

**Scope:** personal prototype, runs locally on one Mac, packaged as a `.dmg` for local install only. No App Store, no cloud, no paid services.

**Goals**
- Reliable recognition of the 4 commands in normal indoor lighting
- Very few false triggers from ordinary hand movement
- Responsive (gesture → action in under ~150 ms)
- Fully offline and free (all open-source components)

**Non-goals (for now)**
- Multi-hand or multi-user support
- Windows/Linux builds
- Signed/notarized distribution

---

## 2. System Architecture

```
┌──────────┐   frames   ┌────────────────┐  21 landmarks  ┌────────────────┐  commands  ┌──────────────┐
│  Webcam  │ ─────────▶ │ Hand Tracker   │ ─────────────▶ │ Gesture Engine │ ─────────▶ │  OS Control  │
│ (OpenCV) │            │ (MediaPipe     │                │ (pose + motion │            │ (pyautogui)  │
└──────────┘            │  HandLandmarker│                │  rules)        │            └──────────────┘
                        └────────────────┘                └────────────────┘
                                                                  │ state
                                                                  ▼
                                                          ┌────────────────┐
                                                          │ Preview / HUD  │
                                                          │ (OpenCV window)│
                                                          └────────────────┘
```

### 2.1 Components

**1. Camera capture (OpenCV)**
- Reads frames from the webcam at ~640×480, ~30 FPS.
- Mirrors the frame horizontally (`cv2.flip(frame, 1)`) so the user's right = screen right.

**2. Hand tracker (MediaPipe Tasks API — `HandLandmarker`)**
- Detects one hand and returns 21 landmarks (x, y normalized 0–1, plus z).
- Runs in `RunningMode.VIDEO` with strictly increasing millisecond timestamps.
- Model file: `hand_landmarker.task` (~8 MB, Apache 2.0), downloaded from Google's model storage.
- ⚠️ **Important:** use the **Tasks API** (`mediapipe.tasks.python.vision.HandLandmarker`). The legacy `mp.solutions.hands` API seen in most online tutorials **no longer exists** in current MediaPipe (0.10.3x).

**3. Gesture engine (pure Python, no camera/OS dependencies → unit-testable)**
- **Pose classifier** — decides the hand shape each frame:
  - Finger is "extended" if `dist(tip, wrist) > dist(pip_joint, wrist) × 1.05` (rotation-tolerant, unlike comparing y-coordinates).
  - `palm` = all four fingers extended
  - `two` = index + middle extended, ring + pinky folded
  - anything else = `none` (ignored — this is the "arming" mechanism that blocks accidental triggers)
- **Pose debouncing** — a pose must persist for N frames (default 3) before it becomes active.
- **Smoothing** — exponential moving average on the tracked point to remove jitter.
- **Scroll logic (joystick model)** — when `two` pose starts, record the hand's y position as an anchor. Offset from the anchor beyond a dead zone produces continuous scrolling; larger offset = faster scroll.
- **Swipe logic** — while in `palm` pose, keep a ~0.35 s history of palm-centre positions. If horizontal travel > threshold and vertical travel is small → `next` / `prev`. Then a cooldown (~0.8 s) so one swipe = one command.
- Any pose change or hand loss resets tracking state.

**4. OS control (pyautogui)**
- `scroll(n)` for scrolling, `press(key)` / `hotkey(...)` for next/previous.
- Fail-safe enabled: moving the mouse into a screen corner aborts.

**5. Preview / HUD (OpenCV window)**
- Draws landmarks and skeleton, current mode (SCROLL / SWIPE / –), FPS, last command flash, pause/dry-run status.
- Keys: `q`/Esc quit, `p` pause/resume.

### 2.2 Hand landmark reference (MediaPipe)

| Index | Point | Index | Point |
|---|---|---|---|
| 0 | Wrist | 12 | Middle tip |
| 5 / 6 / 8 | Index MCP / PIP / tip | 14 / 16 | Ring PIP / tip |
| 9 / 10 | Middle MCP / PIP | 17 / 18 / 20 | Pinky MCP / PIP / tip |

Palm centre = mean of points 0, 5, 9, 13, 17.

### 2.3 Tunable parameters (keep at top of file / in config)

| Parameter | Default | Effect |
|---|---|---|
| `CAMERA_INDEX` | 0 | Use 1 if iPhone Continuity Camera takes index 0 |
| `POSE_STABLE_FRAMES` | 3 | Higher = fewer flickers, slower response |
| `SMOOTHING` | 0.5 | Higher = smoother, more lag |
| `SCROLL_DEADZONE` | 0.04 | Movement needed before scrolling starts |
| `SCROLL_GAIN` | 40 | Scroll speed |
| `SCROLL_MAX_PER_FRAME` | 6 | Scroll speed cap |
| `INVERT_SCROLL` | False | Flip if direction feels wrong |
| `SWIPE_WINDOW_S` | 0.35 | Time window for a swipe |
| `SWIPE_DISTANCE` | 0.18 | Fraction of frame width a swipe must cover |
| `SWIPE_MAX_VERTICAL` | 0.12 | Rejects diagonal motion |
| `COOLDOWN_S` | 0.8 | Gap after next/prev |
| `NEXT_KEY` / `PREV_KEY` | right / left | e.g. `("command","]")` for browser forward |

---

## 3. Technology Stack

| Layer | Choice | License / Cost |
|---|---|---|
| Language | Python 3.11 or 3.12 (safest for MediaPipe wheels on macOS) | Free |
| Camera | `opencv-python` | Apache 2.0 |
| Hand tracking | `mediapipe` ≥ 0.10.20, Tasks API `HandLandmarker` | Apache 2.0 |
| OS control | `pyautogui` (pulls in pyobjc on macOS) | BSD |
| Packaging | PyInstaller → `.app`, `hdiutil` → `.dmg` | Free |
| Signing | Ad-hoc (`codesign --sign -`) | Free |
| Tests | `pytest` | Free |

Everything runs offline after the first model download. Camera frames never leave the machine.

---

## 4. Proposed Project Structure

```
gesture-control/
├── plan.md
├── requirements.txt
├── gesture_control/
│   ├── __init__.py
│   ├── main.py          # entry point, main loop, CLI args (--dry-run, --camera)
│   ├── config.py        # all tunable parameters
│   ├── camera.py        # OpenCV capture + mirroring
│   ├── tracker.py       # MediaPipe HandLandmarker wrapper + model path resolution
│   ├── gestures.py      # pose classifier + GestureEngine (pure logic)
│   ├── controller.py    # pyautogui actions, dry-run mode
│   └── hud.py           # drawing landmarks + status overlay
├── tests/
│   └── test_gestures.py # synthetic-landmark tests for the engine
└── build_mac.sh         # PyInstaller + dmg build
```

---

## 5. Development Plan (Phases)

### Phase 0 — Environment setup
**Tasks**
- Install Python 3.12 (python.org or Homebrew), create a venv.
- `pip install mediapipe opencv-python pyautogui pytest`.
- Download `hand_landmarker.task` from
  `https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task`
- Grant **Camera** permission to Terminal (or VS Code).

**Done when:** `python -c "from mediapipe.tasks.python.vision import HandLandmarker"` succeeds.

---

### Phase 1 — Camera + hand tracking visualization
**Tasks**
- Open webcam, mirror frames, show them in a window.
- Run `HandLandmarker` in VIDEO mode on each frame.
- Draw 21 landmarks + connections (`HandLandmarksConnections.HAND_CONNECTIONS`).
- Show FPS. Quit on `q`.

**Done when:** skeleton follows the hand smoothly at ≥ 20 FPS.

---

### Phase 2 — Pose classification (detect only, no control)
**Tasks**
- Implement `finger_extended()` and `classify_pose()` → `palm` / `two` / `none`.
- Add pose debouncing (N stable frames).
- Display current pose on screen.

**Done when:** pose label is correct and stable while holding each pose, and doesn't flicker when the hand is still.

---

### Phase 3 — Gesture engine (scroll + swipe logic)
**Tasks**
- Build `GestureEngine.update(landmarks, timestamp) -> list[action]` with **no camera or OS code inside**.
- Add EMA smoothing, scroll joystick with dead zone, swipe detection with time window, vertical-rejection and cooldown.
- Reset state on pose change / hand loss.
- Write unit tests with synthetic hand landmarks covering:
  - still two-finger hand → no scroll
  - two fingers moved up → positive scroll; down → negative
  - fast palm swipe right → exactly one `next`; left → exactly one `prev`
  - slow palm drift → nothing
  - diagonal swipe → nothing
  - fist moving fast → nothing
  - swipe then quick return within cooldown → only one command
  - hand disappears mid-gesture → clean reset

**Done when:** all tests pass and `--dry-run` mode prints the right commands live.

---

### Phase 4 — OS control integration
**Tasks**
- Add `Controller` using pyautogui (`scroll`, `press`, `hotkey`), with `pyautogui.FAILSAFE = True` and `PAUSE = 0`.
- Keep `--dry-run` flag that disables real input.
- Add `p` to pause/resume.
- Grant **Accessibility** permission to Terminal/VS Code (System Settings → Privacy & Security → Accessibility).

**Done when:** scrolling a web page and changing slides/photos works by gesture.

**macOS behaviour to remember**
- Key presses go to the **frontmost app** — click the target app after launching, or arrows go to the preview window.
- Scroll events go to the window **under the mouse pointer**.
- Without Accessibility permission, pyautogui fails **silently**.

---

### Phase 5 — Tuning & usability
**Tasks**
- Move all parameters into `config.py` (optionally load overrides from a JSON file in `~/Library/Application Support/GestureControl/`).
- Test in different lighting, distances (0.5–1.5 m), and backgrounds; tune thresholds.
- Improve HUD: mode indicator, scroll direction arrow, "NEXT / PREVIOUS" flash.
- Measure false triggers during 5 minutes of normal desk activity (typing, drinking, scratching face) — target: 0–1.

**Done when:** ≥ 95 % of intentional gestures recognised in a 20-try test per gesture, and false triggers near zero.

---

### Phase 6 — Package as `.app` and `.dmg` (local use)
**Tasks**
- Model path resolution order: inside bundle (`sys._MEIPASS`) → next to script → `~/Library/Application Support/GestureControl/` (download on first run).
- Use `parse_known_args()` so extra args macOS passes to apps don't crash argparse.
- Build:
  ```bash
  pyinstaller --noconfirm --windowed --name "Gesture Control" \
    --osx-bundle-identifier local.gesturecontrol \
    --collect-all mediapipe \
    --add-data "hand_landmarker.task:." \
    gesture_control/main.py
  ```
- Add `NSCameraUsageDescription` to `Info.plist` (**required** — without it macOS denies the camera or kills the app):
  ```bash
  /usr/libexec/PlistBuddy -c "Add :NSCameraUsageDescription string 'Uses the camera to see hand gestures.'" "dist/Gesture Control.app/Contents/Info.plist"
  ```
- Re-sign ad-hoc after editing the plist: `codesign --force --deep --sign - "dist/Gesture Control.app"`
- Create dmg (with an Applications shortcut for drag-install):
  ```bash
  hdiutil create -volname "Gesture Control" -srcfolder <staging_dir> -ov -format UDZO "Gesture Control.dmg"
  ```
- Wrap all of this in `build_mac.sh`.

**Done when:** app installs from the dmg, launches from Applications, asks for camera access, and controls the Mac after Accessibility is enabled for **Gesture Control**.

**Notes**
- No paid Apple Developer account needed for local use.
- After each rebuild, macOS may treat the app as new → toggle its Accessibility permission off/on.
- If Gatekeeper blocks it: right-click → **Open**.

---

### Phase 7 — Optional enhancements (later)
- **Menu-bar app** (e.g. `rumps`) with Start/Pause/Quit, hide preview window by default.
- **Launch at login**.
- **Per-app key mappings** (e.g. Keynote vs browser vs Photos).
- **More gestures** (fist = play/pause, pinch = click, thumbs-up = volume).
- **ML classifier**: record own landmark data → train small model (scikit-learn / TensorFlow) to replace hand-written rules; or try MediaPipe's built-in `GestureRecognizer` (open palm, fist, victory, pointing up, thumbs up/down…).
- **Dynamic gestures** (circles, waves) with sequence models (LSTM).
- **Native rewrite** in Swift using Apple Vision (`VNDetectHumanHandPoseRequest`) + `CGEvent` for lower CPU usage and a fully native app.

---

## 6. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| False triggers from normal movement | Arming poses (only `two`/`palm` act), pose debouncing, vertical-rejection on swipes |
| One swipe fires many commands | Cooldown after each discrete command, clear history after firing |
| Jittery landmarks | EMA smoothing, dead zone on scroll |
| Poor lighting / busy background | Confidence thresholds (0.6), test & tune in Phase 5, advise good front lighting |
| Old tutorials using `mp.solutions` | Use Tasks API only |
| MediaPipe wheel not available for newest Python | Use Python 3.11/3.12 |
| Input silently blocked | Accessibility permission checklist; show a hint in HUD if no effect |
| Camera blocked in packaged app | `NSCameraUsageDescription` in Info.plist + re-sign |
| Wrong camera opened (iPhone Continuity Camera) | `--camera` argument / `CAMERA_INDEX` setting |
| Swipe/scroll direction feels inverted | `SWAP_SWIPE_DIRECTION`, `INVERT_SCROLL` settings |

---

## 7. Testing Strategy

- **Unit tests** (Phase 3+): `GestureEngine` fed with synthetic landmark sequences — no camera needed, runs in CI or anywhere.
- **Dry-run testing**: `--dry-run` shows/prints detected commands without controlling the Mac.
- **Manual acceptance tests**: 20 attempts per gesture, record hit rate; 5 min false-trigger test during normal activity.
- **Packaged app test**: fresh install from dmg on the same Mac, verify both permission prompts and all 4 commands.

---

## 8. Milestone Summary

| Phase | Outcome |
|---|---|
| 0 | Environment ready |
| 1 | Live hand skeleton on screen |
| 2 | Correct pose labels |
| 3 | Gesture engine + passing unit tests, dry-run works |
| 4 | Mac actually scrolls / changes pages |
| 5 | Tuned, reliable, few false triggers |
| 6 | `Gesture Control.dmg` installs and works locally |
| 7 | Optional extras |