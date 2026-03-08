"""
sensors.py — Async-safe sensor drivers

All sensor read methods use await uasyncio.sleep_ms() — never blocking
time.sleep() or spin-wait loops — so they are safe to call from uasyncio
coroutines without stalling the event loop (Pitfall 6 avoidance).

Exports:
    IRLineSensor    — analog IR reflective sensors (multi-channel ADC)
    UltrasonicSensor — HC-SR04 style distance sensor (async echo timing)
    ColorSensor      — TCS34725 I2C color sensor or analog light fallback

Pin assignments are read from config.py:
    config.IR_PINS            — list of ADC-capable GPIO pin numbers
    config.ULTRASONIC_TRIG    — trigger output GPIO
    config.ULTRASONIC_ECHO    — echo input GPIO
    config.COLOR_ANALOG_PIN   — ADC GPIO for analog mode, or None for I2C

Usage:
    from hal.sensors import IRLineSensor, UltrasonicSensor, ColorSensor
    import config

    ir      = IRLineSensor(config.IR_PINS)
    us      = UltrasonicSensor(config.ULTRASONIC_TRIG, config.ULTRASONIC_ECHO)
    color   = ColorSensor(analog_pin=config.COLOR_ANALOG_PIN)  # analog fallback
    # or: color = ColorSensor(i2c=i2c)  # TCS34725 I2C mode

    # In async context:
    values   = await ir.read_all()       # list of 0–65535 per channel
    dist_cm  = await us.read_cm()        # distance in cm; -1.0 on timeout
    colours  = await color.read()        # {'r','g','b','c'} or {'lux':n}
"""

import uasyncio
import utime
from machine import Pin, ADC


class IRLineSensor:
    """
    Analog IR reflective line sensor — reads one or more ADC channels.

    Returns raw 16-bit ADC values (0–65535) per channel.  Higher values
    typically indicate a reflective (light) surface; lower values indicate
    an absorbing (dark) surface — confirm polarity for your sensor hardware.

    Pins must be ADC-capable GPIO.  On the Pico W: GP26, GP27, GP28 only.

    Requirement: FW-04
    """

    def __init__(self, pins: list):
        """
        Args:
            pins: List of ADC-capable GPIO pin numbers.
                  e.g. [28] for single channel, [26, 27, 28] for three channels
                  (verify no pin conflicts with encoders before using 26/27).
        """
        self._adcs = [ADC(Pin(p)) for p in pins]

    async def read_all(self) -> list:
        """
        Read all IR sensor channels.

        Returns:
            List of int 0–65535 per channel.
            Non-blocking: yields once to the event loop before reading.
        """
        await uasyncio.sleep_ms(0)  # yield to event loop before hardware read
        return [adc.read_u16() for adc in self._adcs]


class UltrasonicSensor:
    """
    HC-SR04 style ultrasonic distance sensor.

    Sends a 10us trigger pulse and times the echo return.  All waits use
    await uasyncio.sleep_ms(0) so the event loop is never blocked (Pitfall 6).
    Maximum poll rate: 10Hz (HC-SR04 needs ~60ms between triggers).

    Requirement: FW-05
    """

    TIMEOUT_US = 30000  # ~5m max range at 343m/s; 30ms echo timeout

    def __init__(self, trig_pin: int, echo_pin: int):
        """
        Args:
            trig_pin: GPIO number for trigger output (10us pulse)
            echo_pin: GPIO number for echo input (pulse width = flight time)
        """
        self._trig = Pin(trig_pin, Pin.OUT)
        self._echo = Pin(echo_pin, Pin.IN)
        self._trig.value(0)  # ensure trigger starts low

    async def read_cm(self) -> float:
        """
        Measure distance to nearest obstacle.

        Returns:
            Distance in cm as float.
            Returns -1.0 on echo timeout (out of range or no obstacle).
            Non-blocking: all waits use await, not spin-wait.
        """
        # Ensure trigger is low before pulse
        self._trig.value(0)
        await uasyncio.sleep_ms(2)      # 2ms settling time

        # Send 10us trigger pulse (MicroPython yields; actual pulse ~10-50us)
        self._trig.value(1)
        await uasyncio.sleep_ms(0)      # yield once — pulse width is ~10-50us
        self._trig.value(0)

        # Wait for echo to go high (sensor processing + transit)
        start = utime.ticks_us()
        while self._echo.value() == 0:
            await uasyncio.sleep_ms(0)  # yield on each iteration — non-blocking
            if utime.ticks_diff(utime.ticks_us(), start) > self.TIMEOUT_US:
                return -1.0  # timeout — no echo received

        # Time the echo pulse (high duration = 2× flight time)
        pulse_start = utime.ticks_us()
        while self._echo.value() == 1:
            await uasyncio.sleep_ms(0)  # yield on each iteration — non-blocking
            if utime.ticks_diff(utime.ticks_us(), pulse_start) > self.TIMEOUT_US:
                return -1.0  # timeout — echo too long (object too close or noise)

        duration_us = utime.ticks_diff(utime.ticks_us(), pulse_start)
        # Speed of sound = 343m/s; 1cm round trip = 58.3us
        return duration_us / 58.0


class ColorSensor:
    """
    Color / light sensor — supports TCS34725 over I2C or simple analog fallback.

    I2C mode (TCS34725):
        Returns {'c': clear, 'r': red, 'g': green, 'b': blue} (16-bit each)
        I2C address: 0x29 (fixed on TCS34725)
        Shares I2C0 bus with IMU (no address conflict)

    Analog mode (simple light sensor on ADC pin):
        Returns {'lux': reading} where reading is 0–65535

    Requirement: FW-06
    """

    # TCS34725 register addresses (with auto-increment bit 0x80 set)
    _TCS_ADDR  = 0x29
    _TCS_CDATAL = 0x14   # Clear data low byte
    _TCS_RDATAL = 0x16   # Red data low byte
    _TCS_GDATAL = 0x18   # Green data low byte
    _TCS_BDATAL = 0x1A   # Blue data low byte

    def __init__(self, i2c=None, analog_pin: int = None):
        """
        Args:
            i2c:        machine.I2C instance for TCS34725 mode (addr 0x29).
                        Set to None to use analog_pin mode.
            analog_pin: ADC-capable GPIO pin number for simple light sensor.
                        Set to None to use I2C mode.

        Exactly one of i2c or analog_pin should be provided.
        If both are None, read() returns {'lux': 0}.
        """
        self._i2c = i2c
        self._analog = ADC(Pin(analog_pin)) if analog_pin is not None else None

    async def read(self) -> dict:
        """
        Read sensor values.

        Returns:
            I2C mode:     {'c': int, 'r': int, 'g': int, 'b': int}
                          16-bit clear + RGB channels from TCS34725.
            Analog mode:  {'lux': int}
                          16-bit raw ADC reading (0–65535).
            No hardware:  {'lux': 0}

        Non-blocking: yields once to the event loop before reading.
        """
        await uasyncio.sleep_ms(0)  # yield to event loop

        if self._analog is not None:
            return {"lux": self._analog.read_u16()}

        if self._i2c is not None:
            try:
                def _read_word(reg: int) -> int:
                    """Read 2 bytes from TCS34725 register (little-endian)."""
                    self._i2c.writeto(self._TCS_ADDR, bytes([0x80 | reg]))
                    data = self._i2c.readfrom(self._TCS_ADDR, 2)
                    return data[0] | (data[1] << 8)

                return {
                    "c": _read_word(self._TCS_CDATAL),
                    "r": _read_word(self._TCS_RDATAL),
                    "g": _read_word(self._TCS_GDATAL),
                    "b": _read_word(self._TCS_BDATAL),
                }
            except Exception:
                # I2C error — return zeros rather than crashing the sensor loop
                return {"r": 0, "g": 0, "b": 0, "c": 0}

        # No sensor configured
        return {"lux": 0}
