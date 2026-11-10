"""Command-line entry point: runs the gesture loop with a preview window."""
import argparse
import sys
import time
from collections import Counter

from . import config
from .camera import CameraError
from .permissions import accessibility_granted, open_accessibility_settings
from .runner import GestureRunner


def main():
    parser = argparse.ArgumentParser(description="Hand gesture control for macOS")
    parser.add_argument("--dry-run", action="store_true", help="print commands, send nothing")
    parser.add_argument("--camera", type=int, default=config.CAMERA_INDEX)
    parser.add_argument("--stats", action="store_true",
                        help="count commands and print a summary on exit (acceptance tests)")
    # parse_known_args: macOS may pass extra args (e.g. -psn_...) to launched apps
    args, _ = parser.parse_known_args()

    if not args.dry_run and not accessibility_granted():
        print("Accessibility permission is missing, so gestures cannot control the Mac.\n"
              "Enable this app in System Settings > Privacy & Security > Accessibility,\n"
              "then run again. (Use --dry-run to test without it.)", file=sys.stderr)
        open_accessibility_settings()
        return 1

    counts = Counter()
    started = time.monotonic()
    runner = GestureRunner(
        args.camera, dry_run=args.dry_run, preview=True,
        on_event=(lambda label: counts.update([label])) if args.stats else None)
    try:
        runner.run()
    except CameraError as e:
        print(f"Camera problem: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    finally:
        if args.stats:
            minutes = (time.monotonic() - started) / 60
            print(f"\n--- session summary ({minutes:.1f} min) ---")
            if not counts:
                print("no commands fired")
            for label, n in sorted(counts.items()):
                print(f"{label}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
