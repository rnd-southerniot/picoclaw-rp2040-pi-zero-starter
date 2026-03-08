"""
Gate 9 — Autonomous Mission: Drive a 50cm Square
Full integration: encoders + IMU + PID + motor control

Mission profile:
  Repeat 4×: drive 500mm straight, turn 90° CW
  Robot should return near starting position.

Key parameters:
  Wheel diameter: 65mm → circumference ≈ 204mm
  252 ticks/rev → ~0.81 mm/tick
  500mm ≈ 617 encoder ticks per side

Pass criteria:
  - Total distance error < 20%
  - Total heading error < 30°
  - Returns approximately to start
"""

import time
import sys

sys.path.insert(0, "/lib")
sys.path.insert(0, ".")

from config import (
    MOTOR_LEFT_A, MOTOR_LEFT_B, MOTOR_RIGHT_A, MOTOR_RIGHT_B,
    ENC_LEFT_A, ENC_LEFT_B, ENC_RIGHT_A, ENC_RIGHT_B,
    ENC_LEFT_INVERT, ENC_RIGHT_INVERT,
    I2C_ID, I2C_SDA, I2C_SCL, I2C_FREQ,
    TICKS_PER_REV, MM_PER_TICK,
    MISSION_SIDE_MM, MISSION_TURN_DEG,
    MISSION_DRIVE_SPEED, MISSION_TURN_SPEED, MISSION_TURN_TOL,
)
from motor import Motor
from hal.encoder_pio import EncoderPIO
from mpu6050 import MPU6050


def drive_straight(ml, mr, enc_l, enc_r, distance_mm, speed=40, timeout_s=10.0):
    """
    Drive straight for a given distance using encoder feedback.
    Differential correction keeps L/R balanced.

    Returns:
        (actual_mm_l, actual_mm_r)
    """
    target_ticks = int(distance_mm / MM_PER_TICK)
    enc_l.reset()
    enc_r.reset()

    correction_gain = 0.5
    deadline = time.ticks_add(time.ticks_ms(), int(timeout_s * 1000))

    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        lt = abs(enc_l.count())
        rt = abs(enc_r.count())
        avg = (lt + rt) / 2

        if avg >= target_ticks:
            break

        # Differential correction: if left ahead, slow left / speed right
        diff = lt - rt
        adj = diff * correction_gain

        ml.drive(max(10, speed - adj))
        mr.drive(max(10, speed + adj))
        # Drain FIFO frequently to avoid overflow
        for _ in range(10):
            enc_l.count()
            enc_r.count()
            time.sleep_ms(1)

    ml.brake()
    mr.brake()
    time.sleep_ms(100)

    actual_l = abs(enc_l.count()) * MM_PER_TICK
    actual_r = abs(enc_r.count()) * MM_PER_TICK
    return actual_l, actual_r


def turn_angle(ml, mr, imu, angle_deg, speed=30, tolerance=3.0, timeout_s=5.0):
    """
    Turn robot by angle using gyro integration.
    Positive = CW, negative = CCW.

    Returns:
        Actual degrees turned.
    """
    heading = 0.0
    t_prev = time.ticks_us()
    deadline = time.ticks_add(time.ticks_ms(), int(timeout_s * 1000))

    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        t_now = time.ticks_us()
        dt = time.ticks_diff(t_now, t_prev) / 1_000_000.0
        t_prev = t_now

        gz = imu.gyro_z_calibrated()
        heading += gz * dt

        error = angle_deg - heading

        if abs(error) < tolerance:
            break

        pivot = max(20, min(speed, abs(error) * 1.0))
        if error > 0:
            ml.drive(pivot)
            mr.drive(-pivot)
        else:
            ml.drive(-pivot)
            mr.drive(pivot)

        time.sleep_ms(5)

    ml.brake()
    mr.brake()
    time.sleep_ms(200)
    return heading


def run():
    print("=" * 40)
    print("GATE 9: Autonomous Mission — Drive a Square")
    print("=" * 40)
    print(f"  Side length: {MISSION_SIDE_MM}mm")
    print(f"  Target ticks/side: {int(MISSION_SIDE_MM / MM_PER_TICK)}")
    print()

    # Initialize hardware
    ml = Motor(MOTOR_LEFT_A, MOTOR_LEFT_B)
    mr = Motor(MOTOR_RIGHT_A, MOTOR_RIGHT_B)
    enc_l = EncoderPIO(ENC_LEFT_A, ENC_LEFT_B, sm_id=4, invert=ENC_LEFT_INVERT)
    enc_r = EncoderPIO(ENC_RIGHT_A, ENC_RIGHT_B, sm_id=5, invert=ENC_RIGHT_INVERT)
    imu = MPU6050(I2C_ID, sda=I2C_SDA, scl=I2C_SCL, freq=I2C_FREQ)

    # Calibrate
    print("  Calibrating gyro (keep robot still)...")
    offset = imu.calibrate_gyro_z(samples=200, delay_ms=5)
    print(f"  Offset: {offset:.3f}°/s")
    print()

    total_distance = 0.0
    total_heading = 0.0

    # Mission: 4 sides of a square
    for side in range(1, 5):
        # Drive straight
        print(f"  Side {side}/4: driving {MISSION_SIDE_MM}mm...")
        dl, dr = drive_straight(
            ml, mr, enc_l, enc_r,
            MISSION_SIDE_MM,
            speed=MISSION_DRIVE_SPEED,
        )
        avg_mm = (dl + dr) / 2
        total_distance += avg_mm
        print(f"    Distance: L={dl:.0f}mm R={dr:.0f}mm avg={avg_mm:.0f}mm")

        # Turn 90°
        print(f"  Turn {side}/4: {MISSION_TURN_DEG}° CW...")
        actual_turn = turn_angle(
            ml, mr, imu,
            MISSION_TURN_DEG,
            speed=MISSION_TURN_SPEED,
            tolerance=MISSION_TURN_TOL,
        )
        total_heading += actual_turn
        print(f"    Turned: {actual_turn:.1f}° (cumulative: {total_heading:.1f}°)")
        print()

    # Results
    expected_distance = MISSION_SIDE_MM * 4
    expected_heading = MISSION_TURN_DEG * 4
    dist_error = abs(total_distance - expected_distance) / expected_distance * 100
    hdg_error = abs(total_heading - expected_heading)

    print("=" * 40)
    print("  MISSION RESULTS")
    print(f"  Total distance: {total_distance:.0f}mm (expected {expected_distance}mm, error {dist_error:.1f}%)")
    print(f"  Total heading:  {total_heading:.1f}° (expected {expected_heading}°, error {hdg_error:.1f}°)")

    passed = True
    if dist_error > 20:
        print(f"  ✗ Distance error {dist_error:.1f}% > 20%")
        passed = False
    else:
        print(f"  ✓ Distance error within 20%")

    if hdg_error > 30:
        print(f"  ✗ Heading error {hdg_error:.1f}° > 30°")
        passed = False
    else:
        print(f"  ✓ Heading error within 30°")

    # Cleanup
    ml.deinit()
    mr.deinit()
    enc_l.deinit()
    enc_r.deinit()

    print("-" * 40)
    if passed:
        print("GATE 9: PASSED ✓")
    else:
        print("GATE 9: FAILED ✗")
        print("  Calibration tips:")
        print("  → Measure actual wheel diameter with calipers")
        print("  → Verify encoder tick count per full revolution")
        print("  → Recalibrate gyro before each run")
        print("  → Run on flat, non-slip surface")
    print()
    return passed


if __name__ == "__main__":
    run()
