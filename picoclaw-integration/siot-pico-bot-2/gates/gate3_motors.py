"""
Gate 3 — Motor Driver Test
Checks: Both motor channels forward/backward, pivots

⚠ Elevate wheels off the ground before running!

Pass criteria:
  - All 8 movement patterns verified visually
  - If motor spins wrong direction, swap M+/M− at terminal

Tip: Use Robo Pico hardware test buttons (M1A/M1B/M2A/M2B) first.
"""

import time
import sys

sys.path.insert(0, "/lib")
sys.path.insert(0, ".")

from config import MOTOR_LEFT_A, MOTOR_LEFT_B, MOTOR_RIGHT_A, MOTOR_RIGHT_B
from motor import Motor


def run():
    print("=" * 40)
    print("GATE 3: Motor Driver Test")
    print("=" * 40)
    print("  ⚠ Wheels should be OFF the ground!")
    print()

    ml = Motor(MOTOR_LEFT_A, MOTOR_LEFT_B)
    mr = Motor(MOTOR_RIGHT_A, MOTOR_RIGHT_B)
    speed = 45  # % — moderate speed for testing
    duration = 1.5

    patterns = [
        ("Left FORWARD",   (speed, 0)),
        ("Left BACKWARD",  (-speed, 0)),
        ("Right FORWARD",  (0, speed)),
        ("Right BACKWARD", (0, -speed)),
        ("BOTH FORWARD",   (speed, speed)),
        ("BOTH BACKWARD",  (-speed, -speed)),
        ("PIVOT LEFT",     (-speed, speed)),
        ("PIVOT RIGHT",    (speed, -speed)),
    ]

    for i, (name, (ls, rs)) in enumerate(patterns, 1):
        print(f"  [{i}/8] {name}...", end=" ")
        ml.drive(ls)
        mr.drive(rs)
        time.sleep(duration)
        ml.brake()
        mr.brake()
        print("done")
        time.sleep(0.5)

    ml.deinit()
    mr.deinit()

    print("-" * 40)
    print("GATE 3: PASSED ✓ (requires visual confirmation of all 8 patterns)")
    print()
    print("  If a motor spins the wrong direction:")
    print("  → Swap M+/M− wires at the Robo Pico screw terminal")
    print()
    return True


if __name__ == "__main__":
    run()
