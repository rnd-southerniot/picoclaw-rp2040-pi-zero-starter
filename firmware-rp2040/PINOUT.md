# RP2040 Pin Mapping (Robo Pico aligned)

This mapping is aligned to the tested `siot-pico-bot-2` layout with TCP transport.
The running firmware supports pin overrides via `firmware-rp2040/micropython/wifi_config.py`.

Assumptions:
- RP2040 controls motors/encoders/IMU directly.
- Pi Zero is orchestration only.
- Primary Pi<->RP2040 link is Wi-Fi TCP (`<rp2040-ip>:8765`).

## Pi Zero <-> RP2040 Link

### Primary (recommended)
- Wi-Fi TCP (`rp2040.local:8765` or discovered IP)
- Same JSON-lines payload on both sides

### Optional UART fallback
- Pi GPIO14 (TXD) -> RP2040 GP1 (UART0 RX)
- Pi GPIO15 (RXD) <- RP2040 GP0 (UART0 TX)
- Pi GND <-> RP2040 GND

## RP2040 Peripheral Mapping

### Motors (MX1515H / Robo Pico style)
- `GP9`  : LEFT_MOTOR_A
- `GP8`  : LEFT_MOTOR_B
- `GP10` : RIGHT_MOTOR_A
- `GP11` : RIGHT_MOTOR_B

### Encoders
- Default firmware:
  - `GP6`  : LEFT_ENC_A
  - `GP7`  : LEFT_ENC_B
  - `GP4`  : RIGHT_ENC_A
  - `GP5`  : RIGHT_ENC_B
- Current tested deployment:
  - `GP16` : LEFT_ENC_A
  - `GP17` : LEFT_ENC_B
  - `GP4`  : RIGHT_ENC_A
  - `GP5`  : RIGHT_ENC_B

### IMU (MPU6050 on I2C0)
- `GP0` : I2C0 SDA
- `GP1` : I2C0 SCL

### Other onboard / common peripherals
- `GP18` : NeoPixel data
- `GP22` : Buzzer
- `GP20` : Button A
- `GP21` : Button B
- `GP12`, `GP13`, `GP14`, `GP15` : Servo outputs
- `GP2` / `GP3` : Ultrasonic trig/echo
- `GP28` : IR analog sensor (ADC)

## Tested PID Defaults (from siot-pico-bot-2)

- `kp = 1.5`
- `ki = 0.8`
- `kd = 0.05`
- `loop_hz = 20`
- `target_rpm = 60`

## Power / Safety Notes

- Keep a common ground between Pi, RP2040, and motor driver.
- Do not power motors from RP2040 3V3 rail.
- Keep STOP command and deadman timeout in firmware as final authority.
- Invalid command packets must be rejected fail-closed.
- For any non-default wiring, set pin overrides in `micropython/wifi_config.py` instead of editing control logic.
