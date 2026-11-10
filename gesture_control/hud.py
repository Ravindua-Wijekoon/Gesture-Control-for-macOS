"""Preview overlay: skeleton, mode, FPS, last command, pause/dry-run status."""
import cv2
from mediapipe.tasks.python.vision import HandLandmarksConnections

_MODES = {"two": "SCROLL", "palm": "SWIPE", "pinch": "ZOOM", "fist": "ARM", "none": "-"}
_GREEN, _WHITE, _YELLOW, _RED = (0, 220, 0), (255, 255, 255), (0, 220, 255), (0, 0, 255)


def draw(frame, landmarks, pose, fps, last_label, paused, dry_run, armed=True):
    h, w = frame.shape[:2]
    if landmarks:
        pts = [(int(p.x * w), int(p.y * h)) for p in landmarks]
        for c in HandLandmarksConnections.HAND_CONNECTIONS:
            cv2.line(frame, pts[c.start], pts[c.end], _GREEN, 2)
        for pt in pts:
            cv2.circle(frame, pt, 3, _WHITE, -1)

    cv2.putText(frame, f"MODE: {_MODES.get(pose, '-')}", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, _WHITE, 2)
    cv2.putText(frame, f"FPS: {fps:.0f}", (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, _WHITE, 1)
    if last_label:
        cv2.putText(frame, last_label, (10, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, _YELLOW, 3)
    status = []
    if paused:
        status.append("PAUSED")
    if not armed:
        status.append("DISARMED")
    if dry_run:
        status.append("DRY-RUN")
    if status:
        cv2.putText(frame, " ".join(status), (w - 200, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, _RED, 2)
    return frame
