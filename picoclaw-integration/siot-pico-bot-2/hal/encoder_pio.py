"""
encoder_pio.py — PIO quadrature encoder for RP2040

Replaces v1 lib/encoder.py ISR-based counting with zero-CPU-overhead
PIO state machines. Same public interface as v1 Encoder class.

BENCH TEST REQUIRED: Verify NeoPixel and both encoder SMs run
simultaneously before assuming SM ID assignments are conflict-free
(see research Pitfall 3). NeoPixel typically claims PIO0/SM0.
Using SM IDs 4-7 (PIO block 1) avoids conflict.

Hardware:
  - TT Motor Hall Encoders (6 pulses/motor-rev x 42:1 = 252 ticks/output-rev)
  - Quadrature (4x): 1008 ticks/output-shaft-rev

SM ID assignment:
  Left encoder:  sm_id=4  (PIO block 1, SM 0)
  Right encoder: sm_id=5  (PIO block 1, SM 1)
  If sm_id 4-7 unavailable in your MicroPython build, fall back to
  sm_id=2 and sm_id=3 — but verify no NeoPixel SM conflict on the bench.
"""

import rp2
from machine import Pin
import utime


@rp2.asm_pio(in_shiftdir=rp2.PIO.SHIFT_LEFT)
def _quadrature_state_push():
    """
    Push 2-bit AB state to RX FIFO on every state change.

    Uses X as previous state. On change: push new state, update X.
    On no change: tight poll loop via wrap.
    in_base must be pin_a; pin_b must be pin_a + 1.
    """
    # Init: set X to impossible sentinel so first read always triggers "changed"
    set(x, 0b11)

    label("poll")
    wrap_target()
    mov(osr, null)           # clear OSR
    mov(isr, null)           # clear ISR so in_ starts fresh
    in_(pins, 2)             # read 2 bits (A,B) into ISR
    mov(y, isr)              # Y = current AB state (lower 2 bits)
    jmp(x_not_y, "changed")  # if X != Y, state changed
    jmp("poll")              # no change — loop back

    label("changed")
    push(noblock)            # push Y to RX FIFO (also clears ISR)
    mov(x, y)                # update previous state
    wrap()


# Quadrature decode table indexed by (prev_ab << 2) | curr_ab.
# Encodes the direction for all 16 possible (prev, curr) combinations.
# Gray code CW sequence: 0b00 -> 0b01 -> 0b11 -> 0b10 -> 0b00 (+1 each)
# Gray code CCW sequence: 0b00 -> 0b10 -> 0b11 -> 0b01 -> 0b00 (-1 each)
# Invalid transitions (2-bit change, e.g. 0b00->0b11) return 0.
_QUAD_TABLE = [
    #        curr_ab:  00   01   10   11
     0,  +1,  -1,  0,   # prev_ab=00
    -1,   0,   0, +1,   # prev_ab=01
    +1,   0,   0, -1,   # prev_ab=10
     0,  -1,  +1,  0,   # prev_ab=11
]


class EncoderPIO:
    """
    PIO quadrature encoder replacing v1 lib/encoder.py.

    Uses an RP2040 PIO state machine to detect encoder transitions in
    hardware, pushing raw AB state to the FIFO. Python drains the FIFO
    on count() calls and uses a lookup table to accumulate signed ticks.

    Zero CPU overhead during counting: the PIO runs independently.
    The only CPU work is draining the FIFO when count() is called.

    Public interface is identical to v1 Encoder:
      count(), reset(), delta(), rpm(), deinit()

    Default SM IDs use PIO block 1 to avoid conflict with MicroPython's
    neopixel module (which claims PIO block 0 SM 0).
    """

    def __init__(self, pin_a: int, pin_b: int, sm_id: int = 4, invert: bool = False):
        """
        Args:
            pin_a:  GPIO pin number for encoder channel A (H1).
            pin_b:  GPIO pin number for encoder channel B (H2).
                    Must be pin_a + 1 for PIO in_(pins, 2) to read both.
            sm_id:  PIO state machine ID (0-7). Defaults to 4 (PIO block 1).
            invert: If True, negate the count direction.
        """
        self._pin_a = Pin(pin_a, Pin.IN, Pin.PULL_UP)
        self._pin_b = Pin(pin_b, Pin.IN, Pin.PULL_UP)
        self._sm = rp2.StateMachine(
            sm_id,
            _quadrature_state_push,
            freq=1_000_000,
            in_base=self._pin_a,
        )
        self._sm.active(1)

        self._count = 0
        self._last_count = 0
        self._last_time = utime.ticks_ms()
        self._sign = -1 if invert else 1
        # Set initial previous-state baseline from current pin values.
        # Matches the PIO's X initialisation (sentinel 0b11 forces first
        # push, so we rely on the initial pin read here, not 0b11).
        self._prev_ab = (self._pin_a.value() << 1) | self._pin_b.value()

    def count(self) -> int:
        """
        Return the current accumulated tick count.

        Drains the PIO RX FIFO and updates the running total using the
        quadrature lookup table. The PIO pushes one FIFO entry per state
        change; the FIFO is 4 entries deep. Call count() often enough
        that the FIFO does not overflow (any rate above ~1kHz is safe
        at typical robot speeds).

        Returns:
            Signed tick count (positive = CW, negative = CCW).
        """
        while self._sm.rx_fifo():
            raw = self._sm.get()
            curr_ab = raw & 0b11        # lower 2 bits = AB state
            idx = (self._prev_ab << 2) | curr_ab
            self._count += _QUAD_TABLE[idx] * self._sign
            self._prev_ab = curr_ab
        return self._count

    def reset(self):
        """
        Reset the accumulated tick count and delta baseline to zero.

        Drains the FIFO before resetting so stale transitions do not
        affect the next count() call.
        """
        while self._sm.rx_fifo():
            self._sm.get()
        self._count = 0
        self._last_count = 0
        self._prev_ab = (self._pin_a.value() << 1) | self._pin_b.value()

    def delta(self) -> int:
        """
        Return ticks since the last delta() call.

        Designed for use inside a periodic control loop (e.g., the 20Hz
        PID task). Returns the incremental movement between loop iterations.
        Not accumulated — each call returns only the change since the
        previous call.

        Returns:
            Signed tick delta (positive = CW, negative = CCW).
        """
        current = self.count()
        d = current - self._last_count
        self._last_count = current
        return d

    def rpm(self, dt: float) -> float:
        """
        Compute revolutions per minute.

        Args:
            dt: Actual elapsed time in seconds since last call.
                Use measured dt from utime.ticks_diff(), NOT the nominal
                loop interval. The async event loop may run late (Pitfall 4
                from research: rpm() with wrong dt causes PID overshoot).

        Returns:
            RPM. Positive = CW, negative = CCW.
        """
        if dt <= 0:
            return 0.0
        import config
        ticks = self.delta()
        revs_per_sec = ticks / config.TICKS_PER_REV_QUAD / dt
        return revs_per_sec * 60.0

    def deinit(self):
        """Stop the PIO state machine and release its resources."""
        self._sm.active(0)
