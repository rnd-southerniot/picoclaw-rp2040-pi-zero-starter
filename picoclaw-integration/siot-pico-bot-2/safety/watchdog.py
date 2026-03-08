"""
watchdog.py — Two-layer safety system for siot-pico-bot

Layer 1: Hardware WDT (machine.WDT)
    Resets the entire device if feed_loop stops running for more than 8 seconds.
    Catches full event-loop hangs — runaway student code that blocks cooperative
    scheduling entirely so no coroutine can yield.

Layer 2: Software motor timeout
    Stops both motors after MOTOR_TIMEOUT_S seconds of continuous running.
    Catches student programs that run too long without explicitly stopping motors.
    This fires BEFORE the WDT would trigger a full device reset, giving a
    graceful motor-brake instead of a hard reset.

IMPORTANT: Create WatchdogKeeper AFTER IMU calibration completes.
    IMU gyro calibration blocks for ~1 second. If the WDT is armed before
    calibration, the blocking call will trigger a WDT reset. Always follow
    the boot order in main.py: hardware init → calibration → WDT → async loop.

Exports:
    WatchdogKeeper
"""

from machine import WDT
import uasyncio
import utime


class WatchdogKeeper:
    """
    Two-layer safety system: hardware WDT + software motor timeout.

    Create once in main.py after IMU calibration, then:
      1. Call set_watchdog() on motor_task to inject this keeper.
      2. Add feed_loop() to the uasyncio.gather() call.

    The feed_loop coroutine feeds the hardware WDT every 4 seconds.
    If the event loop hangs (student code blocks cooperative scheduling),
    feed_loop stops executing and the WDT fires after 8 seconds, resetting
    the device.

    The motor timeout is checked each PID iteration via check_motor_timeout().
    If motors have run longer than MOTOR_TIMEOUT_S seconds, both motors are
    braked immediately and the timeout is disarmed.
    """

    MOTOR_TIMEOUT_S = 30   # Stop motors after 30 seconds — configurable per-unit

    def __init__(self, timeout_ms: int = 8000):
        """
        Create the hardware WDT and feed it immediately.

        Args:
            timeout_ms: WDT timeout in milliseconds. RP2040 supports 1000–8388 ms.
                        Default 8000 ms gives a 4-second margin with the 4-second
                        feed interval in feed_loop().

        IMPORTANT: Call this AFTER IMU calibration — the WDT starts counting
        immediately on construction. Any blocking call longer than timeout_ms
        after construction will trigger a reset.
        """
        self._wdt = WDT(timeout=timeout_ms)
        self._wdt.feed()  # Feed immediately after creation to start fresh
        self._motor_start_time = None
        self._motors_running = False

    async def feed_loop(self):
        """
        Feed the hardware WDT every 4 seconds.

        This coroutine MUST be included in the uasyncio.gather() call and
        MUST keep running. If the event loop hangs, this coroutine stops
        executing and the WDT fires after 8 seconds, resetting the device.

        The 4-second feed interval gives a generous 4-second margin before
        the 8-second WDT fires — enough for slow but non-hung operations.
        """
        while True:
            self._wdt.feed()
            await uasyncio.sleep_ms(4000)

    def arm_motor_timeout(self):
        """
        Arm the software motor timeout.

        Call this when student program starts motor movement. The timeout
        begins counting from this moment. If check_motor_timeout() is called
        more than MOTOR_TIMEOUT_S seconds after arm_motor_timeout(), both
        motors will be stopped.
        """
        self._motor_start_time = utime.time()
        self._motors_running = True

    def disarm_motor_timeout(self):
        """
        Disarm the software motor timeout.

        Call this when student program explicitly stops motors. Prevents
        the timeout from firing when motors are legitimately stopped.
        Also called internally by check_motor_timeout() and emergency_stop()
        after triggering.
        """
        self._motor_start_time = None
        self._motors_running = False

    def check_motor_timeout(self, stop_fn) -> bool:
        """
        Check if the software motor timeout has elapsed.

        Call from motor_pid_loop() on every iteration. If motors have been
        running for longer than MOTOR_TIMEOUT_S seconds, calls stop_fn() to
        brake both motors and disarms the timeout.

        Args:
            stop_fn: Callable that brakes both motors immediately.
                     Example: lambda: (_left_motor.brake(), _right_motor.brake())
                     Must be safe to call from the async PID loop context.

        Returns:
            True if the timeout fired and motors were stopped.
            False if timeout has not elapsed or motors are not running.
        """
        if not self._motors_running or self._motor_start_time is None:
            return False
        elapsed = utime.time() - self._motor_start_time
        if elapsed > self.MOTOR_TIMEOUT_S:
            stop_fn()
            self.disarm_motor_timeout()
            print("[SAFETY] Motor timeout after {}s -- motors stopped".format(elapsed))
            return True
        return False

    def emergency_stop(self, stop_fn):
        """
        Immediately brake both motors and disarm the motor timeout.

        Call from exception handlers anywhere in firmware. Disarms the
        timeout so it does not double-fire after an emergency stop.

        Args:
            stop_fn: Callable that brakes both motors immediately.
                     Same signature as check_motor_timeout's stop_fn.
        """
        stop_fn()
        self.disarm_motor_timeout()
        print("[SAFETY] Emergency stop triggered")
