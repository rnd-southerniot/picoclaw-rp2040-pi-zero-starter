"""
Gate 7 — Heading Control (IMU Turn-to-Angle)
Checks: Gyro Z integration tracks heading, 90° turns are accurate

Algorithm:
  1. Calibrate gyro offset (robot stationary)
  2. Integrate (gz - offset) × dt per loop
  3. Proportional pivot speed to target angle
  4. Stop when |error| < tolerance

Pass criteria:
  - 90° turn accuracy: ±10°
  - Round-trip (90° CW → 90° CCW): net heading within ±15° of zero
"""

import time
import sys

sys.path.insert(0, "/lib")
sys.path.insert(0, ".")

from config import (
    MOTOR_LEFT_A, MOTOR_LEFT_B, MOTOR_RIGHT_A, MOTOR_RIGHT_B,
    I2C_ID, I2C_SDA, I2C_SCL, I2C_FREQ,
    MISSION_TURN_SPEED, MISSION_TURN_TOL,
)
from motor import Motor
from mpu6050 import MPU6050


def turn_to_angle(ml, mr, imu, target_deg, speed=30, tolerance=3.0, timeout_s=5.0):
    """
    Turn robot by target_deg degrees using gyro integration.

    Args:
        ml, mr:     Motor objects (left, right)
        imu:        MPU6050 object (calibrated)
        target_deg: Degrees to turn (positive = CW, negative = CCW)
        speed:      Max pivot speed (%)
        tolerance:  Acceptable error in degrees
        timeout_s:  Safety timeout

    Returns:
        Actual degrees turned.
    """
    heading = 0.0
    t_prev = time.ticks_us()
    deadline = time.ticks_add(time.ticks_ms(), int(timeout_s * 1000))

    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        # Time delta
        t_now = time.ticks_us()
        dt = time.ticks_diff(t_now, t_prev) / 1_000_000.0
        t_prev = t_now

        # Integrate gyro
        gz = imu.gyro_z_calibrated()
        heading += gz * dt

        error = target_deg - heading

        # Check convergence
        if abs(error) < tolerance:
            ml.brake()
            mr.brake()
            return heading

        # Proportional pivot speed (minimum 15% to overcome friction)
        pivot = max(20, min(speed, abs(error) * 1.0))

        if error > 0:  # CW: left forward, right backward
            ml.drive(pivot)
            mr.drive(-pivot)
        else:           # CCW: left backward, right forward
            ml.drive(-pivot)
            mr.drive(pivot)

        time.sleep_ms(5)  # ~200Hz loop

    # Timeout
    ml.brake()
    mr.brake()
    return heading


def run():
    print("=" * 40)
    print("GATE 7: Heading Control")
    print("=" * 40)
    print("  Robot should be on a FLAT, NON-SLIP surface.")
    print()

    passed = True

    # Initialize
    ml = Motor(MOTOR_LEFT_A, MOTOR_LEFT_B)
    mr = Motor(MOTOR_RIGHT_A, MOTOR_RIGHT_B)
    imu = MPU6050(I2C_ID, sda=I2C_SDA, scl=I2C_SCL, freq=I2C_FREQ)

    # Calibrate gyro
    print("  Calibrating gyro Z (keep robot still)...")
    offset = imu.calibrate_gyro_z(samples=200, delay_ms=5)
    print(f"  Gyro Z offset: {offset:.3f}°/s")

    speed = MISSION_TURN_SPEED
    tol = MISSION_TURN_TOL

    # --- Test 1: 90° CW ---
    print(f"\n  [1/2] Turning 90° CW...")
    heading_1 = turn_to_angle(ml, mr, imu, 90.0, speed=speed, tolerance=tol)
    err_1 = abs(heading_1 - 90.0)
    print(f"    Result: {heading_1:.1f}° (error: {err_1:.1f}°)")

    if err_1 > 10.0:
        print(f"    ✗ Error {err_1:.1f}° > 10° threshold")
        passed = False
    else:
        print(f"    ✓ Within ±10°")

    time.sleep(1.0)

    # --- Test 2: 90° CCW (return) ---
    print(f"\n  [2/2] Turning 90° CCW (return)...")
    heading_2 = turn_to_angle(ml, mr, imu, -90.0, speed=speed, tolerance=tol)
    net_heading = heading_1 + heading_2
    print(f"    Result: {heading_2:.1f}°")
    print(f"    Net heading: {net_heading:.1f}° (should be ~0°)")

    if abs(net_heading) > 15.0:
        print(f"    ✗ Net heading {net_heading:.1f}° > ±15°")
        passed = False
    else:
        print(f"    ✓ Round-trip within ±15°")

    # Cleanup
    ml.deinit()
    mr.deinit()

    print("-" * 40)
    if passed:
        print("GATE 7: PASSED ✓")
    else:
        print("GATE 7: FAILED ✗")
        print("  Tips:")
        print("  → Recalibrate gyro (keep robot perfectly still)")
        print("  → Reduce speed for better accuracy")
        print("  → Ensure surface has grip (no spinning wheels)")
    print()
    return passed


if __name__ == "__main__":
    run()
