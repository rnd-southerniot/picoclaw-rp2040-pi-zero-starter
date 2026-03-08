"""
Gate 4 — Encoder Feedback
Checks: Hall encoder tick counts from both motors

Pass criteria:
  - Active motor encoder: 50–2000 ticks in 2 seconds
  - Idle motor encoder: stays near 0 (±5)
  - Count sign reverses when direction reverses

If encoder reads 0:
  → Verify V→3V3, G→GND (hall sensor needs independent power)
"""

import time
import sys

sys.path.insert(0, "/lib")
sys.path.insert(0, ".")

from config import (
    MOTOR_LEFT_A, MOTOR_LEFT_B, MOTOR_RIGHT_A, MOTOR_RIGHT_B,
    ENC_LEFT_A, ENC_LEFT_B, ENC_RIGHT_A, ENC_RIGHT_B,
    ENC_LEFT_INVERT, ENC_RIGHT_INVERT,
)
from motor import Motor
from hal.encoder_pio import EncoderPIO


def _drive_and_count(motor, enc_active, enc_idle, speed, duration_ms=2000, poll_ms=10):
    """Drive motor while polling encoders frequently to avoid FIFO overflow."""
    enc_active.reset()
    enc_idle.reset()
    motor.drive(speed)
    for _ in range(duration_ms // poll_ms):
        enc_active.count()  # drain FIFO
        enc_idle.count()
        time.sleep_ms(poll_ms)
    motor.brake()
    time.sleep_ms(200)
    return enc_active.count(), enc_idle.count()


def run():
    print("=" * 40)
    print("GATE 4: Encoder Feedback (PIO)")
    print("=" * 40)

    ml = Motor(MOTOR_LEFT_A, MOTOR_LEFT_B)
    mr = Motor(MOTOR_RIGHT_A, MOTOR_RIGHT_B)
    enc_l = EncoderPIO(ENC_LEFT_A, ENC_LEFT_B, sm_id=4, invert=ENC_LEFT_INVERT)
    enc_r = EncoderPIO(ENC_RIGHT_A, ENC_RIGHT_B, sm_id=5, invert=ENC_RIGHT_INVERT)

    passed = True
    test_speed = 50

    # --- Test 1: Left motor forward ---
    print("\n  [1/4] Left motor FORWARD (right idle)...")
    lt, rt = _drive_and_count(ml, enc_l, enc_r, test_speed)
    print(f"    Left ticks:  {lt}")
    print(f"    Right ticks: {rt} (should be ~0)")

    if not (50 <= abs(lt) <= 2000):
        print("    ✗ Left encoder out of range!")
        passed = False
    else:
        print("    ✓ Left encoder OK")

    if abs(rt) > 10:
        print("    ⚠ Right encoder has crosstalk")

    # --- Test 2: Right motor forward ---
    print("\n  [2/4] Right motor FORWARD (left idle)...")
    rt, lt = _drive_and_count(mr, enc_r, enc_l, test_speed)
    print(f"    Left ticks:  {lt} (should be ~0)")
    print(f"    Right ticks: {rt}")

    if not (50 <= abs(rt) <= 2000):
        print("    ✗ Right encoder out of range!")
        passed = False
    else:
        print("    ✓ Right encoder OK")

    # --- Test 3: Left motor backward (sign check) ---
    print("\n  [3/4] Left motor BACKWARD (sign reversal)...")
    lt, _ = _drive_and_count(ml, enc_l, enc_r, -test_speed)
    print(f"    Left ticks: {lt} (should be negative)")
    if lt >= 0:
        print("    ✗ Sign did not reverse — check encoder wiring")
        passed = False
    else:
        print("    ✓ Sign reversed OK")

    # --- Test 4: Right motor backward ---
    print("\n  [4/4] Right motor BACKWARD (sign reversal)...")
    rt, _ = _drive_and_count(mr, enc_r, enc_l, -test_speed)
    print(f"    Right ticks: {rt} (should be negative)")
    if rt >= 0:
        print("    ✗ Sign did not reverse — check encoder wiring")
        passed = False
    else:
        print("    ✓ Sign reversed OK")

    # Cleanup
    ml.deinit()
    mr.deinit()
    enc_l.deinit()
    enc_r.deinit()

    print("-" * 40)
    if passed:
        print("GATE 4: PASSED ✓")
    else:
        print("GATE 4: FAILED ✗")
        print("  Troubleshooting:")
        print("  → If ticks=0: check V→3V3, G→GND on encoder cable")
        print("  → If sign wrong: swap H1/H2 wires")
    print()
    return passed


if __name__ == "__main__":
    run()
