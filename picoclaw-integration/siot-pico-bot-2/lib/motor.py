"""
motor.py — DC Motor driver for Cytron Robo Pico (MX1515H)

MX1515H Truth Table:
  A=HIGH, B=LOW  → Forward
  A=LOW,  B=HIGH → Backward
  A=LOW,  B=LOW  → Brake
  A=HIGH, B=HIGH → Coast (Hi-Z)

Usage:
  from motor import Motor
  m = Motor(8, 9)       # GP8=M1A, GP9=M1B
  m.drive(50)           # 50% forward
  m.drive(-30)          # 30% backward
  m.brake()
"""

from machine import Pin, PWM


class Motor:
    """Single DC motor channel on the MX1515H H-bridge."""

    def __init__(self, pin_a: int, pin_b: int, freq: int = 1000):
        """
        Args:
            pin_a: GPIO for forward (e.g. GP8 for M1A)
            pin_b: GPIO for backward (e.g. GP9 for M1B)
            freq:  PWM frequency in Hz (default 1000)
        """
        self._pwm_a = PWM(Pin(pin_a))
        self._pwm_b = PWM(Pin(pin_b))
        self._pwm_a.freq(freq)
        self._pwm_b.freq(freq)
        self.brake()

    def drive(self, speed: float):
        """
        Drive motor at given speed.

        Args:
            speed: -100.0 to +100.0 (negative = backward)
        """
        speed = max(-100.0, min(100.0, speed))
        duty = int(abs(speed) / 100.0 * 65535)

        if speed > 0:
            self._pwm_a.duty_u16(duty)
            self._pwm_b.duty_u16(0)
        elif speed < 0:
            self._pwm_a.duty_u16(0)
            self._pwm_b.duty_u16(duty)
        else:
            self.brake()

    def brake(self):
        """Active brake — both outputs LOW."""
        self._pwm_a.duty_u16(0)
        self._pwm_b.duty_u16(0)

    def coast(self):
        """Coast — both outputs HIGH (Hi-Z on MX1515H)."""
        self._pwm_a.duty_u16(65535)
        self._pwm_b.duty_u16(65535)

    def deinit(self):
        """Release PWM resources."""
        self._pwm_a.deinit()
        self._pwm_b.deinit()
