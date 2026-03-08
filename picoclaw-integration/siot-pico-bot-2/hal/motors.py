"""
motors.py — Motor HAL wrapper with K-8 safety speed cap

Wraps v1 lib/motor.py (Motor class) with:
  - Normalised speed interface: -1.0 to +1.0 (not -100 to 100)
  - K-8 safety cap applied at the HAL boundary (Pitfall 5 from research)
  - Cap cannot be bypassed by higher layers (robot.py, task layer, etc.)

The cap is read from config.MOTOR_MAX_SPEED_PCT (default 70).
To adjust: change MOTOR_MAX_SPEED_PCT in config.py only.

Usage:
    from hal.motors import MotorHAL
    import config
    m = MotorHAL(config.MOTOR_LEFT_A, config.MOTOR_LEFT_B)
    m.drive(1.0)   # actual drive = 0.70 (70% of full speed)
    m.drive(0.5)   # actual drive = 0.50 (under the cap)
    m.brake()
    m.deinit()
"""

from lib.motor import Motor
import config

# K-8 safety: cap applied at HAL boundary — cannot be bypassed by higher layers.
# Read once at module load. Default to 70 if key is absent (belt-and-suspenders).
_MAX_SPEED = getattr(config, "MOTOR_MAX_SPEED_PCT", 70) / 100.0


class MotorHAL:
    """
    Thin HAL wrapper around v1 Motor class.

    Speed interface: -1.0 (full reverse) to +1.0 (full forward).
    All drive() calls are clamped to +/-MOTOR_MAX_SPEED_PCT before
    being forwarded to the underlying Motor driver.

    lib/motor.py accepts -100.0 to 100.0; MotorHAL scales accordingly.
    """

    def __init__(self, pin_a: int, pin_b: int):
        """
        Args:
            pin_a: GPIO for forward direction (e.g. MOTOR_LEFT_A)
            pin_b: GPIO for backward direction (e.g. MOTOR_LEFT_B)
        """
        self._motor = Motor(pin_a, pin_b)

    def drive(self, speed: float):
        """
        Drive motor at normalised speed.

        Args:
            speed: -1.0 (full reverse) to +1.0 (full forward).
                   Values outside this range are clamped to ±1.0 first,
                   then the K-8 cap is applied: effective max is
                   ±MOTOR_MAX_SPEED_PCT / 100.

        The cap is enforced here at the HAL boundary regardless of the
        caller. Phase 2+ code cannot exceed the cap.
        """
        # Clamp to normalised range then apply safety cap
        clamped = max(-_MAX_SPEED, min(_MAX_SPEED, speed))
        # lib/motor.py expects -100.0 to 100.0 — scale up
        self._motor.drive(clamped * 100.0)

    def brake(self):
        """Active brake — both motor outputs LOW (MX1515H brake mode)."""
        self._motor.brake()

    def coast(self):
        """Coast — both motor outputs HIGH (MX1515H Hi-Z mode)."""
        self._motor.coast()

    def deinit(self):
        """Release PWM resources."""
        self._motor.deinit()
