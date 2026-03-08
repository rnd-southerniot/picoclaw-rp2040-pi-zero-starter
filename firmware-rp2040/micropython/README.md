# MicroPython TCP Firmware

This folder contains RP2040 (Pico W) firmware for the JSON-lines TCP bridge.

The TCP server supports multiple concurrent clients, so the Pi web app can
stream telemetry while CLI clients send commands.

## Files

- `main.py` - TCP server, command parser, telemetry publisher, deadman handling, motor/encoder control, and peripheral control (`SET_LED`, `PLAY_SOUND`, `GET_BUTTONS`).
- `wifi_config.py` - Wi-Fi and TCP endpoint settings.

## Flash / Update from macOS

1. Confirm device:
```bash
ls /dev/cu.usbmodem*
```

2. Copy firmware files:
```bash
mpremote connect /dev/cu.usbmodemXXXX fs cp firmware-rp2040/micropython/main.py :main.py
mpremote connect /dev/cu.usbmodemXXXX fs cp firmware-rp2040/micropython/wifi_config.py :wifi_config.py
```

3. Edit Wi-Fi credentials on device (or pre-edit local `wifi_config.py`):
```python
WIFI_SSID = "your-ssid"
WIFI_PASSWORD = "your-password"
```

4. Soft reset:
```bash
mpremote connect /dev/cu.usbmodemXXXX soft-reset
```

## Safety Behavior

- Invalid JSON packets are rejected (`type=err`, `reason=invalid_json`).
- Unsupported commands are rejected.
- `STOP` always preempts motion intent.
- Deadman timeout (`2s`) forces mode back to `SAFE`.
- Motion commands drive motors from RP2040 firmware control loop (host stays orchestration-only).
- If motion hardware init fails, movement commands return `motion_hw_unavailable`.
- LED/Buzzer/Button failures return command errors (`led_unavailable`, `buzzer_unavailable`) without affecting motion safety logic.
