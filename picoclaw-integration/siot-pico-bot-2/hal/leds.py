"""
leds.py — NeoPixel status LED controller and buzzer

Controls the 2× WS2812 RGB NeoPixels on the Cytron Robo Pico (GP18)
with named state colours and an async pulsing animation.

Exports:
    StatusLED — NeoPixel state machine (ready/running/error/off + pulse)

Pin note: NeoPixel uses PIO internally. The Cytron Robo Pico places the
NeoPixels on GP18. Encoders must use PIO block 1 (SM IDs 4-5) to avoid
conflict with the neopixel PIO on block 0 (Pitfall 3 avoidance).

Buzzer (GP22) is supported via buzzer_beep() which uses a brief blocking
PWM tone — acceptable at boot-time only. Do NOT call in async hot paths.

Usage:
    from hal.leds import StatusLED
    import config

    led = StatusLED()
    led.set_ready()     # both pixels green
    led.set_running()   # both pixels blue
    led.set_error()     # both pixels red
    led.set_off()       # pixels off

    # Async pulsing animation (for "connecting" state):
    uasyncio.create_task(led.pulse_loop((0, 0, 50)))  # blue pulse
"""

import uasyncio
import neopixel
from machine import Pin, PWM
import config


class StatusLED:
    """
    NeoPixel state indicator for the Cytron Robo Pico.

    Controls 2× WS2812 LEDs on config.NEOPIXEL_PIN with colour-coded states.
    Brightness is kept low (0-50/255) to avoid washing out in classroom lighting.

    State colours:
        ready    — green  (0, 50, 0)
        running  — blue   (0, 0, 50)
        error    — red    (50, 0, 0)
        off      — all off (0, 0, 0)
    """

    # State colours (R, G, B) — kept dim for classroom use
    COLOUR_READY   = (0, 50, 0)
    COLOUR_RUNNING = (0, 0, 50)
    COLOUR_ERROR   = (50, 0, 0)
    COLOUR_OFF     = (0, 0, 0)

    def __init__(self):
        """
        Initialise NeoPixel on config.NEOPIXEL_PIN with config.NEOPIXEL_COUNT pixels.

        NeoPixel uses PIO block 0 internally. Encoders must be on PIO block 1
        (SM IDs 4-5) to avoid SM conflict (Pitfall 3 avoidance).
        """
        self._np = neopixel.NeoPixel(
            Pin(config.NEOPIXEL_PIN), config.NEOPIXEL_COUNT
        )
        self._set_all(self.COLOUR_OFF)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _set_all(self, colour: tuple):
        """Set all pixels to the same colour and write."""
        for i in range(config.NEOPIXEL_COUNT):
            self._np[i] = colour
        self._np.write()

    # ── State methods ─────────────────────────────────────────────────────────

    def set_ready(self):
        """Green — firmware ready, waiting for commands."""
        self._set_all(self.COLOUR_READY)

    def set_running(self):
        """Blue — student program executing."""
        self._set_all(self.COLOUR_RUNNING)

    def set_error(self):
        """Red — error or exception state."""
        self._set_all(self.COLOUR_ERROR)

    def set_off(self):
        """All pixels off."""
        self._set_all(self.COLOUR_OFF)

    # ── Async animation ───────────────────────────────────────────────────────

    async def pulse_loop(self, colour: tuple = (0, 0, 50)):
        """
        Infinite async pulse animation — fades brightness 0 → 50 → 0.

        Intended for "connecting to WiFi" state. Run as an uasyncio task;
        cancel the task to stop pulsing and resume static colour.

        Args:
            colour: (R, G, B) base colour; brightness scaled 0-100%.
        """
        r, g, b = colour
        step = 5  # brightness step size

        while True:
            # Fade up
            for brightness in range(0, 51, step):
                scale = brightness / 50.0
                self._set_all((
                    int(r * scale),
                    int(g * scale),
                    int(b * scale),
                ))
                await uasyncio.sleep_ms(30)
            # Fade down
            for brightness in range(50, -1, -step):
                scale = brightness / 50.0
                self._set_all((
                    int(r * scale),
                    int(g * scale),
                    int(b * scale),
                ))
                await uasyncio.sleep_ms(30)

    # ── Buzzer ────────────────────────────────────────────────────────────────

    def buzzer_beep(self, freq_hz: int = 440, duration_ms: int = 200):
        """
        Brief blocking PWM tone on config.BUZZER_PIN.

        BLOCKING — only call at boot time (chime, ready signal), not in
        async hot paths. Check the Robo Pico mute switch if no sound heard.

        Args:
            freq_hz:     Tone frequency in Hz (default 440 = concert A)
            duration_ms: Duration in milliseconds
        """
        import utime
        buzzer = PWM(Pin(config.BUZZER_PIN))
        try:
            buzzer.freq(freq_hz)
            buzzer.duty_u16(32768)  # 50% duty cycle
            utime.sleep_ms(duration_ms)
        finally:
            buzzer.duty_u16(0)
            buzzer.deinit()
