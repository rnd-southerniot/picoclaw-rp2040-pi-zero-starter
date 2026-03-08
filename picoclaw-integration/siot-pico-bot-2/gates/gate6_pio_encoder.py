"""
gate6_pio_encoder.py — On-device PIO encoder tick count validation (FW-08)

Run via: mpremote run gates/gate6_pio_encoder.py

Verifies that the PIO quadrature encoder correctly counts ticks when
the wheel is rotated by hand. Expected tick count for 2 full revolutions
is 2 * TICKS_PER_REV_QUAD = 2016, with tolerance ±50 for manual rotation.

Requirements:
  - Pico W connected via USB
  - Both encoder connectors plugged in (PH2.0-6PIN)
  - Robot placed on a surface where wheels can spin freely

PASS criteria:
  - Left encoder:  abs(actual - 2016) <= 50
  - Right encoder: abs(actual - 2016) <= 50
"""

import config
from hal.encoder_pio import EncoderPIO

TURNS = 2
EXPECTED_TICKS = TURNS * config.TICKS_PER_REV_QUAD  # 2 * 1008 = 2016
TOLERANCE = 50

print("=" * 50)
print("Gate 6: PIO Encoder Tick Count Validation")
print("=" * 50)
print(f"Expected: {EXPECTED_TICKS} ticks for {TURNS} full wheel turns")
print(f"Tolerance: +/- {TOLERANCE} ticks")
print()

results = []

# ── Left Encoder ──────────────────────────────────────────────────────────
print("--- LEFT ENCODER ---")
print(f"Pins: A=GP{config.ENC_LEFT_A}, B=GP{config.ENC_LEFT_B}, SM=4")
enc_left = EncoderPIO(config.ENC_LEFT_A, config.ENC_LEFT_B, sm_id=4)
enc_left.reset()

input(f"Hand-rotate LEFT wheel {TURNS} full turns CW, then press ENTER... ")
actual_left = enc_left.count()
diff_left = abs(actual_left - EXPECTED_TICKS)

print(f"  Actual ticks:   {actual_left}")
print(f"  Expected ticks: {EXPECTED_TICKS}")
print(f"  Difference:     {diff_left}")

if diff_left <= TOLERANCE:
    print("  LEFT: PASS")
    results.append(("LEFT", True, actual_left, diff_left))
else:
    print(f"  LEFT: FAIL (difference {diff_left} > tolerance {TOLERANCE})")
    print("  Possible causes: wrong SM ID, wrong pin assignment,")
    print("  NeoPixel SM conflict, or wheel did not rotate exactly 2 turns.")
    results.append(("LEFT", False, actual_left, diff_left))

enc_left.deinit()
print()

# ── Right Encoder ─────────────────────────────────────────────────────────
print("--- RIGHT ENCODER ---")
print(f"Pins: A=GP{config.ENC_RIGHT_A}, B=GP{config.ENC_RIGHT_B}, SM=5")
enc_right = EncoderPIO(config.ENC_RIGHT_A, config.ENC_RIGHT_B, sm_id=5)
enc_right.reset()

input(f"Hand-rotate RIGHT wheel {TURNS} full turns CW, then press ENTER... ")
actual_right = enc_right.count()
diff_right = abs(actual_right - EXPECTED_TICKS)

print(f"  Actual ticks:   {actual_right}")
print(f"  Expected ticks: {EXPECTED_TICKS}")
print(f"  Difference:     {diff_right}")

if diff_right <= TOLERANCE:
    print("  RIGHT: PASS")
    results.append(("RIGHT", True, actual_right, diff_right))
else:
    print(f"  RIGHT: FAIL (difference {diff_right} > tolerance {TOLERANCE})")
    print("  Possible causes: wrong SM ID, wrong pin assignment,")
    print("  NeoPixel SM conflict, or wheel did not rotate exactly 2 turns.")
    results.append(("RIGHT", False, actual_right, diff_right))

enc_right.deinit()
print()

# ── Summary ───────────────────────────────────────────────────────────────
print("=" * 50)
print("SUMMARY")
print("=" * 50)
all_pass = all(ok for _, ok, _, _ in results)
for name, ok, actual, diff in results:
    status = "PASS" if ok else "FAIL"
    print(f"  {name:6s}: {status}  (actual={actual}, diff={diff})")

print()
if all_pass:
    print("PASS: Both PIO encoders counting correctly.")
else:
    print("FAIL: One or more encoders failed. See notes above.")
    print("Next steps:")
    print("  1. Verify ENC_* pin assignments in config.py match wiring")
    print("  2. Run neopixel + encoder simultaneously to check SM conflicts")
    print("  3. If SM conflict suspected, try sm_id=2/3 as fallback")
