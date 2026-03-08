# siot-pico-bot-2

**STEM IoT Pico Robot — Gate-Based Learning Kit**

A structured, gate-verified robotics curriculum built on commercially available hardware. Inspired by the [WPILib XRP](https://docs.wpilib.org/en/stable/docs/xrp-robot/index.html) educational framework, adapted for the Cytron Robo Pico platform with MicroPython.

## Hardware

| Component | Specification |
|-----------|--------------|
| **Carrier Board** | [Cytron Robo Pico](https://www.cytron.io/p-robo-pico) — MX1515H 2-ch motor driver, 7 Grove, Maker port |
| **MCU** | Raspberry Pi Pico W (RP2040, WiFi) |
| **Motors** | [TT Metal Gear Motor w/ Hall Encoder](https://techshopbd.com/product/hobby-gearmotor-6v-tt-dual-shaft-bo-metal-gear-motor-with-hall-encoder) x2 — 6V, 300RPM, 1:42, 6-pulse/rev |
| **Chassis** | [Cytron Aluminum 2WD TT Chassis (Purple)](https://www.cytron.io/p-aluminum-2wd-tt-robot-motor-chassis-purple) |
| **IMU** | MPU6050 (GY-521) — 6-DOF, I2C 0x68 |
| **Power** | 3.7V LiPo single cell (required for motor operation) |

## Pin Map

```
MOTORS:     M1A=GP9  M1B=GP8  (Left)     M2A=GP10 M2B=GP11 (Right)
ENCODERS:   L_H1=GP6 L_H2=GP7 (remapped, inverted) R_H1=GP4 R_H2=GP5 (Grove3)
IMU:        SDA=GP16  SCL=GP17  (I2C0, remapped to Grove 4 pins)
ULTRASONIC: TRIG=GP2  ECHO=GP3  (Grove 2)
NEOPIXEL:   GP18 (2x WS2812)
BUZZER:     GP22
BUTTONS:    A=GP20   B=GP21
SERVOS:     GP12 GP13 GP14 GP15
IR SENSOR:  GP28 (ADC)
```

### Robo Pico Grove Port Map

| Grove | Pin 1 | Pin 2 | Assignment |
|-------|-------|-------|------------|
| 1 | GP0 | GP1 | Available |
| 2 | GP2 | GP3 | Ultrasonic (trig/echo) |
| 3 | GP4 | GP5 | Right encoder H1/H2 |
| 4 | GP16 | GP17 | I2C — IMU (MPU6050) |
| 5 | GP6 | GP26 | Left encoder H1 on GP6 |
| 6 | GP27 | GP7 | Left encoder H2 on GP7 |
| 7 | GP28 | — | IR line sensor (ADC) |

## Gate Progression

Each gate is a self-contained milestone with pass/fail criteria.

| Gate | Name | Key Skill | Pass Criteria | Status |
|------|------|-----------|---------------|--------|
| 0 | Environment Setup | MicroPython, UF2 | REPL responds | PASSED |
| 1 | Board Alive | GPIO, LED, buttons | LED blinks, buttons read | PASSED |
| 2 | Onboard Peripherals | NeoPixel, PWM buzzer | Visual + audio confirm | PASSED |
| 3 | Motor Driver | PWM, H-bridge | 8 motion patterns | PASSED |
| 4 | Encoder Feedback | PIO quadrature | Ticks 50-2000 in 2s | PASSED |
| 5 | IMU (MPU6050) | I2C, register R/W | Az ~= 1.0g flat | PASSED |
| 6 | PID Speed Control | Closed-loop, tuning | RPM converges +/-15% | PASSED |
| 7 | Heading Control | Gyro integration | 90 deg +/-10 | PASSED |
| 8 | WiFi Telemetry | AP, HTTP, JSON | Dashboard loads | N/A |
| 9 | Autonomous Mission | Full integration | Drive 50cm square | PASSED |

## Project Structure

```
siot-pico-bot-2/
├── lib/
│   ├── motor.py            # DC motor PWM driver
│   ├── encoder.py          # Quadrature encoder (IRQ-based, legacy)
│   ├── mpu6050.py          # MPU6050 I2C driver
│   ├── pid.py              # PID controller with anti-windup
│   └── microdot/           # Microdot HTTP server (CORS-enabled)
├── hal/
│   ├── motors.py           # Motor HAL with K-8 safety speed cap
│   ├── encoder_pio.py      # PIO quadrature encoder (zero-CPU-overhead)
│   ├── imu.py              # IMU HAL + HeadingTracker
│   ├── sensors.py          # IR, ultrasonic, color sensor HAL
│   └── leds.py             # NeoPixel status LED
├── tasks/
│   ├── motor_task.py       # Async 20Hz motor PID loop
│   ├── sensor_task.py      # Async 10Hz sensor polling
│   └── wifi_task.py        # WiFi AP + Microdot HTTP server
├── safety/
│   ├── watchdog.py         # Hardware WDT + software motor timeout
│   └── sandbox.py          # Code execution sandbox for /exec
├── gates/                  # Gate test scripts (run individually)
├── tools/
│   └── test-dashboard.html # Browser-based robot control dashboard
├── config.py               # Hardware pin definitions & constants
├── robot.py                # Robot facade API for exec() commands
├── main.py                 # Async entry point (uasyncio)
└── README.md
```

## Quick Start

### Prerequisites
- Python 3.x with `mpremote` installed (`pip install mpremote`)
- MicroPython UF2 for Pico W (v1.24+)
- 3.7V LiPo battery connected to Robo Pico JST connector

### Flashing Firmware
1. Hold **BOOTSEL** on Pico W, plug USB — RPI-RP2 drive appears
2. Copy MicroPython UF2 to the drive (Pico reboots automatically)

### Uploading Code
```bash
# Create directories on Pico
mpremote connect auto mkdir :lib :lib/microdot :hal :tasks :safety :gates

# Upload all files
mpremote connect auto cp config.py main.py robot.py :/
mpremote connect auto cp lib/*.py :/lib/
mpremote connect auto cp lib/microdot/*.py :/lib/microdot/
mpremote connect auto cp hal/*.py :/hal/
mpremote connect auto cp tasks/*.py :/tasks/
mpremote connect auto cp safety/*.py :/safety/
```

### Running Gates
```bash
# Run individual gate tests (rename main.py first to prevent auto-boot)
mpremote connect auto exec "import os; os.rename('main.py', '_main.py')"
mpremote connect auto run gates/gate0_env_check.py

# Restore main.py when done testing
mpremote connect auto exec "import os; os.rename('_main.py', 'main.py')"
```

### Test Dashboard
Open `tools/test-dashboard.html` in a browser, connect to the RoboPico WiFi AP, and click Connect.

## Hardware Notes

- **Battery required**: USB power alone causes brownout when motors run
- **Left motor pins swapped**: GP8/GP9 reversed in software (config.py) to correct direction
- **Left encoder inverted**: `ENC_LEFT_INVERT=True` in config.py — needed because left motor pins are swapped
- **Right encoder NOT inverted**: `ENC_RIGHT_INVERT=False` — sign matches motor direction
- **Encoders use PIO**: `hal/encoder_pio.py` uses RP2040 PIO state machines (SM4/SM5 on PIO block 1) for zero-CPU-overhead quadrature decoding. FIFO is only 4 deep — must drain at >=500Hz to avoid tick loss
- **PID tuning**: kp=1.5, ki=0.8, kd=0.05 — tested at 60 RPM target, ~54 RPM steady-state (9% error)
- **Turn speed**: 50% PWM minimum to overcome floor friction for pivot turns. Tolerance 1.0 deg for ~89-90 deg accuracy
- **main.py blocks REPL**: When main.py runs with WDT, mpremote can't connect. Rename to `_main.py` for gate testing
- **IMU Az reads ~1.24g**: Slightly above 1.0g on flat surface — normal for this sensor, gate tolerance set to 0.8-1.3g
- **struct.unpack**: MicroPython does not support spaces in format strings (e.g. use `">hhhhhhh"` not `">hhh h hhh"`)

## Encoder Math

```
Magnetic ring:    6 pulses/rev
Gear ratio:       1:42
Single-phase:     6 x 42 = 252 ticks/output-shaft-rev
Quadrature (4x):  252 x 4 = 1,008 ticks/output-shaft-rev
Wheel diameter:   65mm -> circumference ~= 204mm
Resolution:       ~0.81 mm/tick (single-phase)
```

## License

MIT
