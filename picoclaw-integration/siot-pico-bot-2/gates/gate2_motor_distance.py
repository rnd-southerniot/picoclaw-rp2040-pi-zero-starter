"""
gate2_motor_distance.py — On-device motor distance drive test (FW-02)

Run via: mpremote run gates/gate2_motor_distance.py

Verifies that the motor HAL + PIO encoder combination can drive a target
distance and stop within tolerance. Drives left motor at 40% speed until
the encoder reaches the target tick count, then brakes.

This is a blocking gate script (no async) — acceptable for on-device
verification use only. Production code uses the async motor PID task.

Target: 200mm
Tolerance: +/- 15mm

Requirements:
  - Pico W connected via USB
  - Left motor and left encoder both connected
  - Robot on a surface with room to drive forward ~20cm
  - Place robot at a measured start point for accuracy

PASS criteria:
  abs(actual_mm - target_mm) <= 15
"""

import utime
import math
import config
from hal.motors import MotorHAL
from hal.encoder_pio import EncoderPIO

# ── Target distance calculation ───────────────────────────────────────────
TARGET_MM = 200.0
DRIVE_SPEED = 0.4          # 40% speed (clamped by MotorHAL to 70% max anyway)
TOLERANCE_MM = 15.0

# Ticks required to travel TARGET_MM
# circumference = pi * diameter; ticks_per_mm = TICKS_PER_REV_QUAD / circumference
CIRCUMFERENCE_MM = math.pi * config.WHEEL_DIAMETER_MM
TICKS_PER_MM = config.TICKS_PER_REV_QUAD / CIRCUMFERENCE_MM
TARGET_TICKS = int(TARGET_MM * TICKS_PER_MM)

print("=" * 50)
print("Gate 2: Motor Distance Drive Test")
print("=" * 50)
print(f"Target distance:  {TARGET_MM:.1f} mm")
print(f"Tolerance:        +/- {TOLERANCE_MM:.1f} mm")
print(f"Target ticks:     {TARGET_TICKS}")
print(f"Wheel diameter:   {config.WHEEL_DIAMETER_MM:.1f} mm")
print(f"Ticks/rev (quad): {config.TICKS_PER_REV_QUAD}")
print(f"Drive speed:      {DRIVE_SPEED * 100:.0f}%")
print()

# ── Hardware init ─────────────────────────────────────────────────────────
motor = MotorHAL(config.MOTOR_LEFT_A, config.MOTOR_LEFT_B)
encoder = EncoderPIO(config.ENC_LEFT_A, config.ENC_LEFT_B, sm_id=4)
encoder.reset()

input("Place robot at start mark, then press ENTER to drive... ")

# ── Drive until target ticks reached ─────────────────────────────────────
print("Driving...")
start_time = utime.ticks_ms()
motor.drive(DRIVE_SPEED)

# Blocking poll loop — not async (gate script only)
TIMEOUT_MS = 5000    # 5 second safety timeout
while True:
    current_ticks = encoder.count()
    elapsed_ms = utime.ticks_diff(utime.ticks_ms(), start_time)

    if current_ticks >= TARGET_TICKS:
        break

    if elapsed_ms > TIMEOUT_MS:
        print(f"TIMEOUT after {elapsed_ms}ms — stopping motor")
        break

    utime.sleep_ms(2)   # 2ms poll interval (~500Hz)

motor.brake()
elapsed_ms = utime.ticks_diff(utime.ticks_ms(), start_time)

# ── Results ───────────────────────────────────────────────────────────────
final_ticks = encoder.count()
actual_mm = final_ticks / TICKS_PER_MM
error_mm = actual_mm - TARGET_MM
abs_error_mm = abs(error_mm)

print()
print("=" * 50)
print("RESULTS")
print("=" * 50)
print(f"  Target distance:  {TARGET_MM:.1f} mm  ({TARGET_TICKS} ticks)")
print(f"  Actual distance:  {actual_mm:.1f} mm  ({final_ticks} ticks)")
print(f"  Error:            {error_mm:+.1f} mm")
print(f"  Elapsed time:     {elapsed_ms} ms")
print()

if abs_error_mm <= TOLERANCE_MM:
    print(f"PASS: Motor drove {actual_mm:.1f}mm, within {TOLERANCE_MM}mm tolerance.")
else:
    print(f"FAIL: Error {abs_error_mm:.1f}mm exceeds tolerance {TOLERANCE_MM}mm.")
    print("Next steps:")
    print("  - Verify WHEEL_DIAMETER_MM matches actual wheel (measure with calipers)")
    print("  - Verify TICKS_PER_REV_QUAD = 1008 matches encoder hardware")
    print("  - Check motor encoder wiring (A/B channels not swapped)")
    print("  - Reduce DRIVE_SPEED if motor overshoots consistently")

# Cleanup
encoder.deinit()
motor.deinit()
