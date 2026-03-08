"""
gate3_turn_angle.py — IMU heading accuracy gate test

Verifies that the HeadingTracker correctly integrates gyro Z into heading
and that a timed 90-degree turn produces a heading within ±5 degrees.

On-device test (requires Pico W connected via USB with motors + IMU):
    mpremote run gates/gate3_turn_angle.py

Expected result:
    Rover rotates approximately 90 degrees (left turn: left motor forward,
    right motor backward), then stops.
    Final heading printed.
    PASS if 85 ≤ heading ≤ 95 degrees.

Tuning: adjust TURN_DURATION_MS if heading is consistently over/under 90.
The turn duration is empirical — it depends on motor speed and turn radius.
"""

import uasyncio
import utime
from machine import I2C, Pin
import config
from lib.mpu6050 import MPU6050
from hal.imu import IMUHAL, HeadingTracker
from hal.motors import MotorHAL

# ── Turn parameters (tune for your hardware) ──────────────────────────────────
TURN_SPEED      = 0.3      # Motor speed (normalised -1.0 to 1.0); 30% after cap
TURN_DURATION_MS = 1500    # Duration in ms for ~90-degree turn; tune empirically
HEADING_TARGET  = 90.0     # Expected heading in degrees
HEADING_TOL     = 5.0      # Pass/fail tolerance in degrees


async def main():
    print("gate3_turn_angle: IMU heading accuracy test")
    print("  Turn speed:", TURN_SPEED, "  Duration:", TURN_DURATION_MS, "ms")

    # ── Hardware init ─────────────────────────────────────────────────────────
    i2c = I2C(
        config.I2C_ID,
        sda=Pin(config.I2C_SDA),
        scl=Pin(config.I2C_SCL),
        freq=config.I2C_FREQ,
    )
    imu_hal = IMUHAL(i2c)

    print("Calibrating IMU — keep robot still...")
    imu_hal.calibrate(samples=200)
    print("Calibration done.")

    tracker = HeadingTracker(imu_hal)
    tracker.reset()

    left_motor  = MotorHAL(config.MOTOR_LEFT_A,  config.MOTOR_LEFT_B)
    right_motor = MotorHAL(config.MOTOR_RIGHT_A, config.MOTOR_RIGHT_B)

    # ── Run heading update loop as a background task ──────────────────────────
    heading_task = uasyncio.create_task(tracker.update_loop())

    # ── Execute 90-degree left turn ───────────────────────────────────────────
    # Left turn: left motor forward, right motor backward
    print("Executing turn...")
    left_motor.drive(TURN_SPEED)
    right_motor.drive(-TURN_SPEED)

    await uasyncio.sleep_ms(TURN_DURATION_MS)

    left_motor.brake()
    right_motor.brake()

    # Brief settle to read final heading
    await uasyncio.sleep_ms(100)

    # ── Read and evaluate heading ─────────────────────────────────────────────
    heading_task.cancel()

    final_heading = tracker.get_heading()
    print("Final heading:", final_heading, "degrees (target: 90)")

    if HEADING_TARGET - HEADING_TOL <= abs(final_heading) <= HEADING_TARGET + HEADING_TOL:
        print("PASS: Heading", round(final_heading, 1), "within ±", HEADING_TOL, "of 90 degrees")
    else:
        print("FAIL: Heading", round(final_heading, 1), "outside ±", HEADING_TOL, "of 90 degrees")
        print("  Hint: adjust TURN_DURATION_MS to tune. Current value:", TURN_DURATION_MS)

    # ── Cleanup ───────────────────────────────────────────────────────────────
    left_motor.brake()
    right_motor.brake()
    left_motor.deinit()
    right_motor.deinit()


uasyncio.run(main())
