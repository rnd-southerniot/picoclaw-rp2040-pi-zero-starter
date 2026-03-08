"""
sensor_task.py — Async sensor poll coroutine (10Hz)

Runs as one of the concurrent coroutines under uasyncio.
Polls all sensors at 10Hz and stores results in the shared _sensor_state dict
so other tasks (motor PID, WiFi/HTTP) can read values without touching hardware.

Sensor pin assignments are read from config.py:
    config.IR_PINS            — ADC-capable GPIO pins for IR line sensors
    config.ULTRASONIC_TRIG    — HC-SR04 trigger output GPIO
    config.ULTRASONIC_ECHO    — HC-SR04 echo input GPIO
    config.COLOR_ANALOG_PIN   — ADC GPIO for analog color; None = I2C TCS34725

NOTE: Update config.py with actual hardware pins before deploying.
The pin defaults in config.py are placeholders — verify against your wiring.

Exports:
    set_i2c(i2c)        — inject shared I2C bus from main.py (call before event loop)
    set_heading_tracker(tracker) — inject HeadingTracker from main.py (call before event loop)
    sensor_poll_loop()  — coroutine, schedule with uasyncio.gather()
    get_sensor_state()  — returns a reference to the shared state dict

Shared state keys:
    "ir"          — list of int 0–65535 per IR channel
    "distance_cm" — float cm from ultrasonic; -1.0 on timeout
    "color"       — dict {'r','g','b','c'} (I2C) or {'lux': n} (analog)
    "heading"     — float degrees from HeadingTracker (if IMU task running)
    "tick"        — int iteration counter (monotonically increases)
"""

import uasyncio

import config
from hal.sensors import IRLineSensor, UltrasonicSensor, ColorSensor
from hal.imu import IMUHAL, HeadingTracker

# ── Shared sensor state ───────────────────────────────────────────────────────
# Written by this task, read by motor / wifi tasks.
_sensor_state = {
    "ir":          [],
    "distance_cm": -1.0,
    "color":       {},
    "heading":     0.0,
    "tick":        0,
}

# ── Module-level sensor instances ─────────────────────────────────────────────
# Instantiated once here; sensor_poll_loop() uses these throughout its lifetime.
# If a sensor is not physically connected, the driver will either return -1.0
# (ultrasonic timeout) or zeros — the loop will continue safely.

_ir_sensor = IRLineSensor(config.IR_PINS)
_us_sensor = UltrasonicSensor(config.ULTRASONIC_TRIG, config.ULTRASONIC_ECHO)

# Color sensor: use analog pin if configured, otherwise I2C TCS34725
if config.COLOR_ANALOG_PIN is not None:
    _color_sensor = ColorSensor(analog_pin=config.COLOR_ANALOG_PIN)
else:
    # I2C mode: ColorSensor initialized in set_i2c() — called from main.py
    _color_sensor = None

# HeadingTracker is managed externally (main.py passes an IMUHAL to it);
# sensor_task exposes a setter so main.py can wire them together after boot.
_heading_tracker = None

# I2C bus shared with IMU — injected from main.py via set_i2c()
_shared_i2c = None


def set_i2c(i2c):
    """
    Wire in the shared I2C bus from main.py after IMU init.

    Call this from main.py after MPU6050 init and before starting
    the event loop. sensor_poll_loop() will then use the shared bus
    for ColorSensor reads — avoiding a second I2C(0) instantiation.
    """
    global _shared_i2c, _color_sensor
    _shared_i2c = i2c
    _color_sensor = ColorSensor(i2c=_shared_i2c)


def set_heading_tracker(tracker: HeadingTracker):
    """
    Wire in the HeadingTracker from main.py after IMU calibration.

    Call this from main.py after calibration completes and before starting
    the event loop. sensor_poll_loop() will then read heading from it.
    """
    global _heading_tracker
    _heading_tracker = tracker


# ── Public accessor ───────────────────────────────────────────────────────────

def get_sensor_state() -> dict:
    """Return a reference to the shared sensor state dict."""
    return _sensor_state


# ── Coroutine ─────────────────────────────────────────────────────────────────

async def sensor_poll_loop():
    """
    Sensor poll coroutine — runs at 10Hz (every 100ms).

    Reads IR line sensors, ultrasonic distance, color, and heading on each
    iteration and stores results in _sensor_state. All reads are async-safe
    (no blocking spin-waits). See hal/sensors.py for implementation details.

    Exception handling: sensor failures must NOT propagate to gather()
    and kill the motor task (Pitfall 2 avoidance). Errors are logged and
    the loop continues — a failed sensor returns stale values until it recovers.
    """
    iteration = 0

    while True:
        try:
            iteration += 1
            _sensor_state["tick"] = iteration

            # IR line sensors — list of ADC readings (0–65535 per channel)
            _sensor_state["ir"] = await _ir_sensor.read_all()

            # Ultrasonic distance — cm; -1.0 on timeout
            _sensor_state["distance_cm"] = await _us_sensor.read_cm()

            # Color / light — dict with RGBC or lux key
            if _color_sensor is not None:
                _sensor_state["color"] = await _color_sensor.read()

            # Heading — degrees from HeadingTracker update_loop (100Hz separate task)
            if _heading_tracker is not None:
                _sensor_state["heading"] = _heading_tracker.get_heading()

        except Exception as e:
            # Log but continue — sensor failure must not cancel motor task
            print("sensor_task ERROR (continuing):", e)

        await uasyncio.sleep_ms(100)  # 10Hz poll rate
