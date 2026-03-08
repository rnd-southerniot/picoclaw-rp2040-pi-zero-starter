"""
gate4_sensors.py — All sensor reads gate test

Verifies that all three sensor classes return readings without crashing.
No motor movement required — bench test only.

On-device test (requires Pico W connected via USB with sensors wired):
    mpremote run gates/gate4_sensors.py

Expected result:
    IR channel values: list of integers (0–65535 per channel)
    Distance: float in cm (or -1.0 if no object in range — acceptable)
    Color: dict with expected keys ('r','g','b','c' for I2C or 'lux' for analog)
    "PASS: All sensors returned readings"

Note: PASS is based on data type correctness, not sensor values. A distance
of -1.0 (timeout) is PASS because the driver ran without crashing.
"""

import uasyncio
from machine import I2C, Pin
import config
from hal.sensors import IRLineSensor, UltrasonicSensor, ColorSensor


async def main():
    print("gate4_sensors: All sensor reads test")
    print()

    all_pass = True

    # ── IR Line Sensor ────────────────────────────────────────────────────────
    print("--- IR Line Sensor ---")
    print("  Pins:", config.IR_PINS)
    try:
        ir = IRLineSensor(config.IR_PINS)
        values = await ir.read_all()
        print("  Values:", values)

        # PASS if all values are integers in 0–65535
        if isinstance(values, list) and all(isinstance(v, int) for v in values):
            print("  PASS: IR returned", len(values), "integer channel(s)")
        else:
            print("  FAIL: IR values are not a list of integers:", type(values))
            all_pass = False
    except Exception as e:
        print("  FAIL: IR sensor error:", e)
        all_pass = False

    print()

    # ── Ultrasonic Sensor ─────────────────────────────────────────────────────
    print("--- Ultrasonic Sensor ---")
    print("  TRIG:", config.ULTRASONIC_TRIG, "  ECHO:", config.ULTRASONIC_ECHO)
    try:
        us = UltrasonicSensor(config.ULTRASONIC_TRIG, config.ULTRASONIC_ECHO)
        dist = await us.read_cm()
        print("  Distance:", dist, "cm")

        # PASS if result is a float (including -1.0 timeout — driver ran OK)
        if isinstance(dist, float):
            if dist < 0:
                print("  PASS: Ultrasonic returned -1.0 (timeout/out of range — driver ran OK)")
            else:
                print("  PASS: Ultrasonic returned", round(dist, 1), "cm")
        else:
            print("  FAIL: Distance is not a float:", type(dist))
            all_pass = False
    except Exception as e:
        print("  FAIL: Ultrasonic sensor error:", e)
        all_pass = False

    print()

    # ── Color Sensor ──────────────────────────────────────────────────────────
    print("--- Color Sensor ---")
    if config.COLOR_ANALOG_PIN is not None:
        print("  Mode: analog, pin:", config.COLOR_ANALOG_PIN)
        color = ColorSensor(analog_pin=config.COLOR_ANALOG_PIN)
        expected_keys = {"lux"}
    else:
        print("  Mode: I2C TCS34725, addr 0x29")
        i2c = I2C(
            config.I2C_ID,
            sda=Pin(config.I2C_SDA),
            scl=Pin(config.I2C_SCL),
            freq=config.I2C_FREQ,
        )
        color = ColorSensor(i2c=i2c)
        expected_keys = {"r", "g", "b", "c"}

    try:
        reading = await color.read()
        print("  Reading:", reading)

        # PASS if dict has at least one expected key
        if isinstance(reading, dict) and expected_keys.intersection(reading.keys()):
            print("  PASS: Color returned dict with keys:", list(reading.keys()))
        else:
            print("  FAIL: Color dict missing expected keys. Got:", list(reading.keys()))
            print("        Expected at least one of:", expected_keys)
            all_pass = False
    except Exception as e:
        print("  FAIL: Color sensor error:", e)
        all_pass = False

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    if all_pass:
        print("PASS: All sensors returned readings")
    else:
        print("FAIL: One or more sensors did not return valid readings")
        print("  Check wiring, pin assignments in config.py, and sensor power.")


uasyncio.run(main())
