"""
mpu6050.py — MPU6050 IMU driver over I2C

Registers:
  WHO_AM_I  (0x75) → expect 0x68
  PWR_MGMT_1(0x6B) → write 0x00 to wake
  ACCEL_X_H (0x3B) → 14 bytes: accel(6) + temp(2) + gyro(6)
  GYRO_Z_H  (0x47) → 2 bytes for heading integration

Default ranges: accel ±2g (/16384), gyro ±250°/s (/131)

Usage:
  from mpu6050 import MPU6050
  imu = MPU6050(0, sda=0, scl=1)
  ax, ay, az = imu.accel()
  gx, gy, gz = imu.gyro()
  gz_cal = imu.calibrate_gyro_z(samples=200)
"""

import struct
import time
from machine import Pin, I2C


class MPU6050:
    """MPU6050 6-DOF IMU driver."""

    # Register addresses
    _WHO_AM_I   = 0x75
    _PWR_MGMT_1 = 0x6B
    _ACCEL_XOUT = 0x3B
    _GYRO_ZOUT  = 0x47

    # Scale factors (default config: ±2g, ±250°/s)
    _ACCEL_SCALE = 16384.0
    _GYRO_SCALE  = 131.0

    def __init__(self, i2c_id: int = 0, sda: int = 0, scl: int = 1,
                 freq: int = 400000, addr: int = 0x68):
        """
        Args:
            i2c_id: I2C bus number (0 or 1)
            sda:    SDA GPIO pin
            scl:    SCL GPIO pin
            freq:   I2C clock frequency
            addr:   MPU6050 address (0x68 default, 0x69 if AD0 high)
        """
        self._i2c = I2C(i2c_id, sda=Pin(sda), scl=Pin(scl), freq=freq)
        self._addr = addr
        self._gyro_z_offset = 0.0

        # Verify device
        who = self._read_byte(self._WHO_AM_I)
        if who != 0x68:
            raise RuntimeError(
                f"MPU6050 WHO_AM_I=0x{who:02X}, expected 0x68. "
                "Check wiring: SDA→GP{}, SCL→GP{}".format(sda, scl)
            )

        # Wake up (clear sleep bit)
        self._write_byte(self._PWR_MGMT_1, 0x00)
        time.sleep_ms(100)

    def _read_byte(self, reg: int) -> int:
        return self._i2c.readfrom_mem(self._addr, reg, 1)[0]

    def _write_byte(self, reg: int, val: int):
        self._i2c.writeto_mem(self._addr, reg, bytes([val]))

    def _read_raw(self) -> tuple:
        """Read all 14 bytes: accel(6) + temp(2) + gyro(6)."""
        buf = self._i2c.readfrom_mem(self._addr, self._ACCEL_XOUT, 14)
        vals = struct.unpack(">hhhhhhh", buf)
        # vals: ax, ay, az, temp_raw, gx, gy, gz
        return vals

    def accel(self) -> tuple:
        """
        Read accelerometer in g.

        Returns:
            (ax, ay, az) in g units.
            Flat surface: expect (0, 0, ~1.0).
        """
        vals = self._read_raw()
        return (
            vals[0] / self._ACCEL_SCALE,
            vals[1] / self._ACCEL_SCALE,
            vals[2] / self._ACCEL_SCALE,
        )

    def gyro(self) -> tuple:
        """
        Read gyroscope in °/s.

        Returns:
            (gx, gy, gz) in degrees per second.
        """
        vals = self._read_raw()
        return (
            vals[4] / self._GYRO_SCALE,
            vals[5] / self._GYRO_SCALE,
            vals[6] / self._GYRO_SCALE,
        )

    def gyro_z(self) -> float:
        """Read only gyro Z-axis in °/s (optimized for heading)."""
        buf = self._i2c.readfrom_mem(self._addr, self._GYRO_ZOUT, 2)
        raw = struct.unpack(">h", buf)[0]
        return raw / self._GYRO_SCALE

    def gyro_z_calibrated(self) -> float:
        """Read gyro Z with offset correction applied."""
        return self.gyro_z() - self._gyro_z_offset

    def temperature(self) -> float:
        """Read temperature in °C."""
        vals = self._read_raw()
        return vals[3] / 340.0 + 36.53

    def calibrate_gyro_z(self, samples: int = 200, delay_ms: int = 5) -> float:
        """
        Calibrate gyro Z offset. Robot must be stationary.

        Args:
            samples:  Number of samples to average
            delay_ms: Delay between samples in ms

        Returns:
            Computed offset (also stored internally).
        """
        total = 0.0
        for _ in range(samples):
            total += self.gyro_z()
            time.sleep_ms(delay_ms)
        self._gyro_z_offset = total / samples
        return self._gyro_z_offset

    def scan(self) -> list:
        """Return list of I2C addresses found on the bus."""
        return self._i2c.scan()
