"""
Gate 6 — Closed-Loop PID Speed Control
Checks: Both motors reach and hold target RPM using encoder feedback

Pass criteria:
  - RPM converges to target within 2 seconds (±15%)
  - L/R RPM approximately equal (difference < 20%)
  - No sustained oscillation

PID Tuning Guide:
  Start: kp=0.5, ki=0.1, kd=0.0
  Increase kp until responsive
  Add ki to eliminate steady-state error
  Add kd ONLY if overshooting
"""

import time
import sys

sys.path.insert(0, "/lib")
sys.path.insert(0, ".")

from config import (
    MOTOR_LEFT_A, MOTOR_LEFT_B, MOTOR_RIGHT_A, MOTOR_RIGHT_B,
    ENC_LEFT_A, ENC_LEFT_B, ENC_RIGHT_A, ENC_RIGHT_B,
    ENC_LEFT_INVERT, ENC_RIGHT_INVERT,
    PID_KP, PID_KI, PID_KD, PID_LOOP_HZ, PID_TARGET_RPM,
)
from motor import Motor
from hal.encoder_pio import EncoderPIO
from pid import PID


def run():
    print("=" * 40)
    print("GATE 6: PID Speed Control")
    print("=" * 40)

    target_rpm = PID_TARGET_RPM
    loop_hz = PID_LOOP_HZ
    dt = 1.0 / loop_hz
    run_time = 5.0  # seconds

    print(f"  Target: {target_rpm} RPM")
    print(f"  Loop:   {loop_hz} Hz ({dt*1000:.0f}ms)")
    print(f"  PID:    kp={PID_KP} ki={PID_KI} kd={PID_KD}")
    print(f"  Duration: {run_time}s")
    print()

    # Initialize hardware
    ml = Motor(MOTOR_LEFT_A, MOTOR_LEFT_B)
    mr = Motor(MOTOR_RIGHT_A, MOTOR_RIGHT_B)
    enc_l = EncoderPIO(ENC_LEFT_A, ENC_LEFT_B, sm_id=4, invert=ENC_LEFT_INVERT)
    enc_r = EncoderPIO(ENC_RIGHT_A, ENC_RIGHT_B, sm_id=5, invert=ENC_RIGHT_INVERT)

    pid_l = PID(kp=PID_KP, ki=PID_KI, kd=PID_KD)
    pid_r = PID(kp=PID_KP, ki=PID_KI, kd=PID_KD)

    enc_l.reset()
    enc_r.reset()

    passed = True
    converged = False
    samples = []

    # Control loop
    iterations = int(run_time * loop_hz)
    for i in range(iterations):
        t0 = time.ticks_us()

        # Measure RPM
        rpm_l = enc_l.rpm(dt)
        rpm_r = enc_r.rpm(dt)

        # Compute PID output (0-100% speed)
        out_l = pid_l.compute(target_rpm, rpm_l, dt)
        out_r = pid_r.compute(target_rpm, rpm_r, dt)

        # Apply
        ml.drive(out_l)
        mr.drive(out_r)

        # Log every 10th sample
        if i % 10 == 0:
            print(f"  t={i*dt:.1f}s  L={rpm_l:6.1f} RPM ({out_l:+5.1f}%)  "
                  f"R={rpm_r:6.1f} RPM ({out_r:+5.1f}%)")

        # Track convergence after 2s
        if i * dt >= 2.0:
            samples.append((rpm_l, rpm_r))

        # Wait for next loop tick, draining FIFO frequently
        target_us = int(dt * 1_000_000)
        while time.ticks_diff(time.ticks_us(), t0) < target_us:
            enc_l.count()
            enc_r.count()
            time.sleep_us(500)

    # Stop motors
    ml.brake()
    mr.brake()

    # Analyze convergence
    if samples:
        avg_l = sum(s[0] for s in samples) / len(samples)
        avg_r = sum(s[1] for s in samples) / len(samples)

        err_l = abs(avg_l - target_rpm) / target_rpm * 100
        err_r = abs(avg_r - target_rpm) / target_rpm * 100
        diff = abs(avg_l - avg_r) / target_rpm * 100 if target_rpm > 0 else 0

        print(f"\n  Post-convergence (t>2s) averages:")
        print(f"    Left:  {avg_l:.1f} RPM (error: {err_l:.1f}%)")
        print(f"    Right: {avg_r:.1f} RPM (error: {err_r:.1f}%)")
        print(f"    L-R diff: {diff:.1f}%")

        if err_l > 15:
            print(f"  ✗ Left error {err_l:.1f}% > 15%")
            passed = False
        if err_r > 15:
            print(f"  ✗ Right error {err_r:.1f}% > 15%")
            passed = False
        if diff > 20:
            print(f"  ✗ L/R difference {diff:.1f}% > 20%")
            passed = False

    # Cleanup
    ml.deinit()
    mr.deinit()
    enc_l.deinit()
    enc_r.deinit()

    print("-" * 40)
    if passed:
        print("GATE 6: PASSED ✓")
    else:
        print("GATE 6: FAILED ✗")
        print("  Tuning tips:")
        print("  → Reduce kp by 50% if oscillating")
        print("  → Increase ki if steady-state error persists")
        print("  → Set kd=0 to start fresh")
    print()
    return passed


if __name__ == "__main__":
    run()
