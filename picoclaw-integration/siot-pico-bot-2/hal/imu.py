"""
imu.py — IMU HAL wrapper and heading tracker

Wraps v1 lib/mpu6050.py with a thin convenience layer and provides
an async heading integration loop at 100Hz.

Exports:
    IMUHAL          — thin wrapper around MPU6050 with calibrate() + gyro_z_dps()
    HeadingTracker  — integrates gyro Z into heading angle; run update_loop() as task

Usage:
    from hal.imu import IMUHAL, HeadingTracker
    from machine import I2C, Pin
    import config

    from lib.mpu6050 import MPU6050
    imu = MPU6050(config.I2C_ID, sda=config.I2C_SDA,
                  scl=config.I2C_SCL, freq=config.I2C_FREQ)
    imu_hal = IMUHAL(imu)
    imu_hal.calibrate()          # call at boot, BEFORE WDT starts
    tracker = HeadingTracker(imu_hal)
    # In async context:
    #   uasyncio.create_task(tracker.update_loop())
"""

import utime
import uasyncio
from lib.mpu6050 import MPU6050


class IMUHAL:
    """
    Thin HAL wrapper around v1 MPU6050 driver.

    Re-exposes the interface needed by HeadingTracker and the motor task.
    I2C reads are fast (<1ms at 400kHz) so these methods can be called
    directly from async tasks without await.
    """

    def __init__(self, mpu):
        """
        Args:
            mpu: Already-constructed MPU6050 instance (from lib/mpu6050.py)
        """
        self._imu = mpu

    def calibrate(self, samples: int = 200):
        """
        Calibrate gyro Z offset. Robot must be stationary.

        Call at boot BEFORE the WDT is armed — calibration takes ~1 second.
        """
        self._imu.calibrate_gyro_z(samples=samples)

    def gyro_z_dps(self) -> float:
        """
        Return calibrated gyro Z rate in degrees per second.

        Positive = clockwise rotation (robot turning right) on a flat surface
        with MPU6050 Z-axis pointing up.
        """
        return self._imu.gyro_z_calibrated()

    def accel(self) -> tuple:
        """Return (ax, ay, az) in g units."""
        return self._imu.accel()

    def gyro(self) -> tuple:
        """Return (gx, gy, gz) in degrees per second."""
        return self._imu.gyro()


class HeadingTracker:
    """
    Integrates gyro Z rate into a cumulative heading angle.

    Run update_loop() as an uasyncio task for 100Hz heading integration.
    The heading accumulates — positive values indicate clockwise rotation.

    Usage:
        tracker = HeadingTracker(imu_hal)
        uasyncio.create_task(tracker.update_loop())

        # Later:
        heading = tracker.get_heading()   # degrees since last reset()
        tracker.reset()                   # zero heading for a new manoeuvre
    """

    def __init__(self, imu_hal: IMUHAL):
        """
        Args:
            imu_hal: Initialised and calibrated IMUHAL instance
        """
        self._imu = imu_hal
        self._heading = 0.0
        self._last_t = utime.ticks_ms()

    async def update_loop(self):
        """
        100Hz heading integration coroutine. Schedule with uasyncio.create_task().

        Measures actual elapsed dt using utime.ticks_diff() to avoid dt drift
        when the event loop is busy (Pitfall 4 avoidance).
        """
        while True:
            now = utime.ticks_ms()
            dt = utime.ticks_diff(now, self._last_t) / 1000.0
            self._last_t = now
            if dt > 0:
                self._heading += self._imu.gyro_z_dps() * dt
            await uasyncio.sleep_ms(10)  # 100Hz update rate

    def get_heading(self) -> float:
        """Return accumulated heading in degrees since last reset()."""
        return self._heading

    def reset(self):
        """Zero the heading counter. Call before starting a new timed manoeuvre."""
        self._heading = 0.0
