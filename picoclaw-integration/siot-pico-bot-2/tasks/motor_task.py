"""
motor_task.py — Async motor PID control coroutine (20Hz)

Runs as one of the three concurrent coroutines under uasyncio.
Uses PIO quadrature encoders (EncoderPIO) as the measured RPM for PID
feedback — closing the control loop with real encoder data (FW-02).

Exports:
  motor_pid_loop()      — coroutine, schedule with uasyncio.gather()
  get_target_rpm(side)  — returns current target RPM for 'left' or 'right'
  set_target_rpm(side, rpm) — sets target RPM
  set_watchdog(wdg)     — injects WatchdogKeeper after creation in main.py
"""

import uasyncio
import utime
from hal.motors import MotorHAL
from lib.pid import PID
from hal.encoder_pio import EncoderPIO
import config

# ── Module-level hardware instances ──────────────────────────────────────────
# MotorHAL wraps lib/motor.py with normalised -1.0..1.0 interface and 70% speed cap.
_left_motor  = MotorHAL(config.MOTOR_LEFT_A,  config.MOTOR_LEFT_B)
_right_motor = MotorHAL(config.MOTOR_RIGHT_A, config.MOTOR_RIGHT_B)

# PIO quadrature encoders — PIO block 1 (SM IDs 4 & 5) to avoid NeoPixel conflict.
# Pins must be consecutive: ENC_LEFT_A/B = GP6/GP7, ENC_RIGHT_A/B = GP26/GP27.
# SM IDs 4/5 = PIO block 1; NeoPixel on PIO block 0 SM 0 (no conflict).
_left_enc  = EncoderPIO(config.ENC_LEFT_A,  config.ENC_LEFT_B,  sm_id=4,
                        invert=getattr(config, "ENC_LEFT_INVERT", False))
_right_enc = EncoderPIO(config.ENC_RIGHT_A, config.ENC_RIGHT_B, sm_id=5,
                        invert=getattr(config, "ENC_RIGHT_INVERT", False))

# PID controllers — one per wheel
_left_pid  = PID(config.PID_KP, config.PID_KI, config.PID_KD)
_right_pid = PID(config.PID_KP, config.PID_KI, config.PID_KD)

# Shared target RPM state — written by external commands, read by PID loop
_target_rpm = {"left": 0.0, "right": 0.0}

# Measured RPM state — written by PID loop, read by status endpoint
_actual_rpm = {"left": 0.0, "right": 0.0}

# WatchdogKeeper — injected by main.py via set_watchdog() after WDT creation.
# None until set; check_motor_timeout / emergency_stop are no-ops when None.
_watchdog = None

# Tick tracking for actual dt measurement (Pitfall 4: use measured dt, not nominal)
_last_tick_ms = utime.ticks_ms()

# ── Public accessors ──────────────────────────────────────────────────────────

def get_target_rpm(side: str) -> float:
    """Return current target RPM for 'left' or 'right' motor."""
    return _target_rpm[side]


def get_actual_rpm(side: str) -> float:
    """Return measured RPM for 'left' or 'right' motor."""
    return _actual_rpm[side]


def set_target_rpm(side: str, rpm: float):
    """Set target RPM for 'left' or 'right' motor.

    Arms the software motor timeout when any wheel has a non-zero target,
    and disarms it when both wheels return to zero.
    """
    _target_rpm[side] = rpm
    if _watchdog is not None:
        if _target_rpm["left"] != 0.0 or _target_rpm["right"] != 0.0:
            _watchdog.arm_motor_timeout()
        else:
            _watchdog.disarm_motor_timeout()


def set_watchdog(wdg):
    """
    Inject the WatchdogKeeper instance created in main.py.

    Called once during boot after WatchdogKeeper construction and before
    the async event loop starts. Allows main.py to control WDT lifecycle
    (create after IMU calibration) while motor_task uses it for safety.

    Args:
        wdg: WatchdogKeeper instance, or None to clear.
    """
    global _watchdog
    _watchdog = wdg


# ── Coroutine ─────────────────────────────────────────────────────────────────

async def motor_pid_loop():
    """
    Motor PID loop coroutine — runs at 20Hz (every 50ms).

    Each iteration:
      1. Measures actual dt using utime.ticks_diff (Pitfall 4 avoidance —
         actual elapsed time, not nominal interval, avoids RPM overshoot).
      2. Reads actual RPM from PIO quadrature encoders (_left_enc, _right_enc).
      3. Computes PID correction using measured RPM as feedback (FW-02).
      4. Drives motors with PID output.
      5. Checks software motor timeout via WatchdogKeeper.

    Exception handling (Pitfall 2 avoidance): on any exception, brakes both
    motors and calls emergency_stop() before breaking the loop. gather() will
    propagate the exception; WDT will eventually reset if nothing else runs.
    """
    global _last_tick_ms

    interval_ms = 1000 // config.PID_LOOP_HZ  # 50 ms at 20Hz
    iteration   = 0
    _last_tick_ms = utime.ticks_ms()

    while True:
        try:
            # ── Step 1: Measure actual elapsed time ───────────────────────────
            now = utime.ticks_ms()
            dt  = utime.ticks_diff(now, _last_tick_ms) / 1000.0  # seconds
            _last_tick_ms = now

            iteration += 1
            if iteration % 5 == 0:
                print("motor tick", iteration)

            # ── Step 2: Read actual RPM from PIO encoders ─────────────────────
            # Use measured dt (not nominal) to avoid RPM calculation error
            # when the event loop runs late (Pitfall 4 from research).
            left_rpm_actual  = _left_enc.rpm(dt)  if dt > 0 else 0.0
            right_rpm_actual = _right_enc.rpm(dt) if dt > 0 else 0.0
            _actual_rpm["left"]  = left_rpm_actual
            _actual_rpm["right"] = right_rpm_actual

            # ── Step 3: Compute PID correction using real encoder feedback ─────
            left_out  = _left_pid.compute(_target_rpm["left"],  left_rpm_actual,  dt if dt > 0 else 0.05)
            right_out = _right_pid.compute(_target_rpm["right"], right_rpm_actual, dt if dt > 0 else 0.05)

            # ── Step 4: Drive motors with PID output ──────────────────────────
            _left_motor.drive(left_out)
            _right_motor.drive(right_out)

            # ── Step 5: Check software motor timeout ──────────────────────────
            if _watchdog is not None:
                stop_fn = lambda: (_left_motor.brake(), _right_motor.brake())
                _watchdog.check_motor_timeout(stop_fn)

        except Exception as e:
            # Brake both motors and call emergency_stop before propagating.
            # Never leave motors running when firmware has an error.
            stop_fn = lambda: (_left_motor.brake(), _right_motor.brake())
            _left_motor.brake()
            _right_motor.brake()
            if _watchdog is not None:
                _watchdog.emergency_stop(stop_fn)
            print("motor_task ERROR:", e)
            break  # Exit loop; gather() propagates exception; WDT resets if stuck

        await uasyncio.sleep_ms(interval_ms)
