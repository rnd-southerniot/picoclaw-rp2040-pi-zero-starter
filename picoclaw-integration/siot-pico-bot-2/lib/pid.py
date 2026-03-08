"""
pid.py — PID controller with anti-windup clamping

Usage:
  from pid import PID
  ctrl = PID(kp=0.8, ki=0.3, kd=0.05, out_min=-100, out_max=100)
  output = ctrl.compute(setpoint=60.0, measured=rpm, dt=0.05)
  ctrl.reset()
"""


class PID:
    """Discrete PID controller with integral anti-windup."""

    def __init__(self, kp: float = 0.8, ki: float = 0.3, kd: float = 0.05,
                 out_min: float = -100.0, out_max: float = 100.0,
                 integral_limit: float = 50.0):
        """
        Args:
            kp: Proportional gain
            ki: Integral gain
            kd: Derivative gain
            out_min: Minimum output (clamp)
            out_max: Maximum output (clamp)
            integral_limit: Anti-windup clamp on integral term
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.out_min = out_min
        self.out_max = out_max
        self.integral_limit = integral_limit

        self._integral = 0.0
        self._prev_error = 0.0
        self._first = True

    def compute(self, setpoint: float, measured: float, dt: float) -> float:
        """
        Compute PID output.

        Args:
            setpoint: Desired value (e.g., target RPM)
            measured: Current measured value
            dt:       Time step in seconds

        Returns:
            Control output (clamped to out_min..out_max)
        """
        if dt <= 0:
            return 0.0

        error = setpoint - measured

        # Proportional
        p_term = self.kp * error

        # Integral with anti-windup
        self._integral += error * dt
        self._integral = self._clamp(
            self._integral, -self.integral_limit, self.integral_limit
        )
        i_term = self.ki * self._integral

        # Derivative (skip on first call to avoid spike)
        if self._first:
            d_term = 0.0
            self._first = False
        else:
            d_term = self.kd * (error - self._prev_error) / dt

        self._prev_error = error

        # Sum and clamp output
        output = p_term + i_term + d_term
        return self._clamp(output, self.out_min, self.out_max)

    def reset(self):
        """Reset internal state."""
        self._integral = 0.0
        self._prev_error = 0.0
        self._first = True

    def set_gains(self, kp: float, ki: float, kd: float):
        """Update PID gains at runtime."""
        self.kp = kp
        self.ki = ki
        self.kd = kd

    @staticmethod
    def _clamp(val: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, val))
