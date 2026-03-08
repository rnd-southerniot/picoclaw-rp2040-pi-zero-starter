"""
siot-pico-bot — Main Entry Point (v2 async architecture)

Boot sequence (safe WDT order per Pitfall 1 from research):
  1. Initialize I2C and MPU6050
  2. Calibrate gyro Z (blocks ~1s — WDT must NOT be running yet)
  3. Wrap IMU in IMUHAL, create HeadingTracker, wire into sensor_task
  4. Create WatchdogKeeper AFTER calibration (starts hardware WDT)
  5. Inject watchdog into motor_task via set_watchdog()
  6. Set green LED to signal boot complete
  7. Launch uasyncio event loop with all coroutines gathered

Usage:
  Flash to Pico W as main.py (via Thonny or mpremote).
  The rover will calibrate the IMU on boot (keep still for ~1 second),
  then start the async event loop running motor PID, sensor polling,
  heading integration, WiFi placeholder, and WDT feed loop concurrently.
"""

import machine
from machine import I2C, Pin
import uasyncio
import config
from lib.mpu6050 import MPU6050

# ── Boot Banner ───────────────────────────────────────────────────────────────

print()
print("=========================================")
print("  siot-pico-bot Learning Kit  v2.0")
print("  Async firmware -- uasyncio architecture")
print("=========================================")
print()

# ── Step 1: Hardware Init (NO WDT yet — Pitfall 1) ───────────────────────────

print("Initializing I2C and IMU...")
imu = MPU6050(
    i2c_id=config.I2C_ID,
    sda=config.I2C_SDA,
    scl=config.I2C_SCL,
    freq=config.I2C_FREQ,
    addr=config.MPU6050_ADDR,
)

# ── Step 2: IMU Calibration (blocking — WDT must NOT be running) ──────────────

print("Calibrating IMU -- keep robot still...")
imu.calibrate_gyro_z(samples=200)
print("Calibration done")

# ── Step 3: Wrap IMU in HAL + HeadingTracker ──────────────────────────────────
# IMUHAL wraps the already-calibrated MPU6050. HeadingTracker integrates gyro Z
# at 100Hz — its update_loop() coroutine is added to the gather() below.
# sensor_task reads heading via the injected tracker.

from hal.imu import IMUHAL, HeadingTracker
import tasks.sensor_task as sensor_task

imu_hal = IMUHAL(imu)
heading_tracker = HeadingTracker(imu_hal)
sensor_task.set_heading_tracker(heading_tracker)
sensor_task.set_i2c(imu._i2c)              # share I2C bus — avoids dual I2C(0)
print("HeadingTracker and shared I2C wired into sensor_task")

# ── Step 4: Start WDT AFTER calibration via WatchdogKeeper ───────────────────
# WatchdogKeeper wraps machine.WDT and provides the feed_loop coroutine plus
# the software motor timeout layer. Creating it here (after calibration) ensures
# the blocking calibration call cannot trigger a premature WDT reset.

from safety.watchdog import WatchdogKeeper
import tasks.motor_task as motor_task

watchdog = WatchdogKeeper(timeout_ms=8000)
print("Watchdog armed (8s timeout, fed every 4s in feed_loop coroutine)")

# ── Step 5: Inject watchdog into motor task ───────────────────────────────────
# motor_task needs the watchdog for check_motor_timeout() and emergency_stop().
# Injected here so motor_task module-level init (encoders, motors) can run
# at import time without needing the watchdog yet.

motor_task.set_watchdog(watchdog)

# ── Step 6: Signal boot complete (green LED = ready) ─────────────────────────

try:
    from hal.leds import StatusLED
    leds = StatusLED(config.NEOPIXEL_PIN, config.NEOPIXEL_COUNT)
    leds.set_ready()
    print("Status LED: green (ready)")
except Exception as e:
    # LED failure is non-fatal — firmware continues without visual indicator
    print("LED init skipped:", e)

# ── Step 7: Start WiFi AP (blocking — sync, before event loop) ──────────────
# AP startup can take 1-2s. Done here (sync) to avoid blocking the event loop.
# WDT is already armed but has 8s timeout — 10s AP deadline will trip WDT first
# only if AP truly hangs, which is acceptable (device resets and retries on boot).

from tasks.wifi_task import start_ap
ap, ssid = start_ap()


# ── Async main: gather all coroutines ────────────────────────────────────────

async def main_async():
    """
    Start all task coroutines and the WDT feed loop concurrently.

    Coroutines:
      motor_pid_loop()              — 20Hz motor PID with real encoder feedback
      sensor_poll_loop()            — 10Hz sensor reads (IR, ultrasonic, color)
      heading_tracker.update_loop() — 100Hz gyro-Z heading integration
      wifi_server_task()            — Microdot HTTP server on port 80 (AP already up)
      watchdog.feed_loop()          — feeds hardware WDT every 4s (MUST keep running)
    """
    from tasks.motor_task import motor_pid_loop
    from tasks.sensor_task import sensor_poll_loop
    from tasks.wifi_task import wifi_server_task

    print("Starting event loop: motor | sensor | heading | wifi/http | watchdog")
    await uasyncio.gather(
        motor_pid_loop(),
        sensor_poll_loop(),
        heading_tracker.update_loop(),
        wifi_server_task(),          # HTTP server — AP started in Step 7 above
        watchdog.feed_loop(),
    )


# ── Entry point ───────────────────────────────────────────────────────────────

uasyncio.run(main_async())
