"""
encoder.py — Quadrature encoder driver for TT Hall Encoder motors

Hardware: 6-pulse/rev magnetic ring, 1:42 gear ratio
  Single-phase: 252 ticks/output-shaft-rev
  Quadrature:   1008 ticks/output-shaft-rev

Wiring (PH2.0-6PIN): V→3V3, G→GND, H1→Ch_A, H2→Ch_B

Usage:
  from encoder import Encoder
  enc = Encoder(6, 7)       # Left: H1=GP6, H2=GP7
  enc.reset()
  ticks = enc.count()
  rpm   = enc.rpm(dt=0.05)  # over 50ms loop
"""

from machine import Pin


class Encoder:
    """Quadrature encoder with IRQ-based tick counting."""

    def __init__(self, pin_a: int, pin_b: int):
        """
        Args:
            pin_a: GPIO for Hall channel A (H1)
            pin_b: GPIO for Hall channel B (H2)
        """
        self._count = 0
        self._prev_count = 0

        self._pin_a = Pin(pin_a, Pin.IN, Pin.PULL_UP)
        self._pin_b = Pin(pin_b, Pin.IN, Pin.PULL_UP)

        # Attach ISR on both edges of channel A for quadrature decoding
        self._pin_a.irq(
            trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,
            handler=self._isr_a,
        )
        # Optional: attach channel B for full 4× resolution
        self._pin_b.irq(
            trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,
            handler=self._isr_b,
        )

    def _isr_a(self, pin):
        """ISR for channel A edges."""
        if self._pin_a.value() == self._pin_b.value():
            self._count += 1
        else:
            self._count -= 1

    def _isr_b(self, pin):
        """ISR for channel B edges."""
        if self._pin_a.value() != self._pin_b.value():
            self._count += 1
        else:
            self._count -= 1

    def count(self) -> int:
        """Return current accumulated tick count."""
        return self._count

    def reset(self):
        """Reset tick count to zero."""
        self._count = 0
        self._prev_count = 0

    def delta(self) -> int:
        """Return ticks since last delta() call."""
        current = self._count
        d = current - self._prev_count
        self._prev_count = current
        return d

    def rpm(self, dt: float, ticks_per_rev: int = 252) -> float:
        """
        Compute RPM from tick delta.

        Args:
            dt: time interval in seconds since last call
            ticks_per_rev: encoder ticks per output shaft revolution
                           (252 for single-phase, 1008 for quad)
        Returns:
            Revolutions per minute.
        """
        d = self.delta()
        if dt <= 0:
            return 0.0
        revs = d / ticks_per_rev
        return revs * 60.0 / dt

    def deinit(self):
        """Disable IRQs."""
        self._pin_a.irq(handler=None)
        self._pin_b.irq(handler=None)
