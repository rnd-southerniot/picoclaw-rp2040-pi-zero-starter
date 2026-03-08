"""
Gate 5 — IMU Test (MPU6050)
Checks: I2C scan, WHO_AM_I, accel/gyro readings

Pass criteria:
  - I2C finds device at 0x68
  - Az ≈ 1.0g on flat surface (0.8–1.2 range)
  - Gyro readings near 0 when stationary (±5°/s)
"""

import time
import sys

sys.path.insert(0, "/lib")
sys.path.insert(0, ".")

from config import I2C_ID, I2C_SDA, I2C_SCL, I2C_FREQ, MPU6050_ADDR
from mpu6050 import MPU6050


def run():
    print("=" * 40)
    print("GATE 5: IMU Test (MPU6050)")
    print("=" * 40)
    print("  Robot should be STATIONARY on a FLAT surface.")
    print()

    passed = True

    # --- I2C Scan ---
    from machine import Pin, I2C
    i2c = I2C(I2C_ID, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=I2C_FREQ)
    devices = i2c.scan()
    print(f"  I2C scan: {['0x{:02X}'.format(d) for d in devices]}")

    if MPU6050_ADDR not in devices:
        print(f"  ✗ MPU6050 (0x{MPU6050_ADDR:02X}) NOT found!")
        print(f"  → Check wiring: SDA=GP{I2C_SDA}, SCL=GP{I2C_SCL}")
        print(f"  → Verify 3V3 power to MPU6050")
        print("GATE 5: FAILED ✗")
        return False

    print(f"  ✓ MPU6050 found at 0x{MPU6050_ADDR:02X}")

    # --- Initialize ---
    try:
        imu = MPU6050(I2C_ID, sda=I2C_SDA, scl=I2C_SCL, freq=I2C_FREQ)
        print("  ✓ WHO_AM_I verified, device awake")
    except RuntimeError as e:
        print(f"  ✗ {e}")
        print("GATE 5: FAILED ✗")
        return False

    # --- Accelerometer ---
    print("\n  Accelerometer (5 samples):")
    for i in range(5):
        ax, ay, az = imu.accel()
        print(f"    [{i+1}] ax={ax:+.3f}g  ay={ay:+.3f}g  az={az:+.3f}g")
        time.sleep_ms(100)

    ax, ay, az = imu.accel()
    if 0.8 <= abs(az) <= 1.3:
        print(f"  ✓ Az={az:.3f}g (expected ~1.0g on flat surface)")
    else:
        print(f"  ✗ Az={az:.3f}g — out of range (0.8–1.3)")
        passed = False

    # --- Gyroscope ---
    print("\n  Gyroscope (5 samples, should be near 0):")
    for i in range(5):
        gx, gy, gz = imu.gyro()
        print(f"    [{i+1}] gx={gx:+.2f}°/s  gy={gy:+.2f}°/s  gz={gz:+.2f}°/s")
        time.sleep_ms(100)

    gx, gy, gz = imu.gyro()
    max_gyro = max(abs(gx), abs(gy), abs(gz))
    if max_gyro < 5.0:
        print(f"  ✓ Gyro drift < 5°/s when stationary")
    else:
        print(f"  ✗ Gyro drift = {max_gyro:.2f}°/s — too high (is robot still?)")
        passed = False

    # --- Temperature ---
    temp = imu.temperature()
    print(f"\n  Temperature: {temp:.1f}°C")

    print("-" * 40)
    if passed:
        print("GATE 5: PASSED ✓")
    else:
        print("GATE 5: FAILED ✗")
    print()
    return passed


if __name__ == "__main__":
    run()
