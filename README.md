# picoclaw-rp2040-pi-zero-starter

Starter repository for a safe-by-default Raspberry Pi Zero gateway that communicates with an RP2040 motion controller over JSON-lines TCP.

## Architecture

- RP2040: real-time motor control + final safety authority
- Raspberry Pi Zero: Linux-side orchestration, CLI, telemetry logging
- Transport: JSON-lines over Wi-Fi TCP (`rp2040.local:8765` by default)

## Repository Layout

- `robot-agent/` Python bridge + protocol parser + CLI + logs config
- `robot-agent/web_app.py` web UI + natural-language command endpoint
- `firmware-rp2040/` protocol contract and firmware pseudocode scaffold
- `firmware-rp2040/micropython/` flashable Pico W TCP firmware with motor + LED + buzzer + button handlers
- `pi-zero/` first-boot and bootstrap scripts for the Pi
- `host-tools/` LAN discovery and SSH helpers
- `systemd/` service to run the bridge on boot
- `picoclaw-integration/` future integration area (includes vendored `siot-pico-bot-2` reference copy)

## First Boot (Pi Zero)

1. Flash Raspberry Pi OS Lite.
2. During imaging, set:
- hostname: `pi-zero`
- username: `arif`
- Wi-Fi credentials for your LAN
- SSH enabled
3. Boot the Pi and discover/connect from host:
```bash
./host-tools/find-pi-zero.sh
./host-tools/ssh-pi-zero.sh arif
```

If mDNS fails, use DHCP leases from your router and run:
```bash
./host-tools/ssh-pi-zero.sh arif <pi-ip>
```

## Deploy to `/opt/picoclaw-rp2040`

From inside the repo on the Pi:

```bash
cd /path/to/picoclaw-rp2040-pi-zero-starter
./pi-zero/bootstrap_pi_zero.sh
```

This script:
- installs Python deps
- copies repo to `/opt/picoclaw-rp2040`
- creates venv in `/opt/picoclaw-rp2040/.venv`
- installs/enables `robot-agent.service`

## Run Bridge Manually

```bash
cd /opt/picoclaw-rp2040/robot-agent
../.venv/bin/python cli.py MONITOR --config config.yaml
```

Set RP2040 TCP endpoint in `robot-agent/config.yaml`:
```yaml
transport:
  type: tcp
  tcp:
    host: rp2040.local
    port: 8765
```

## CLI Commands

Run from `/opt/picoclaw-rp2040/robot-agent`.

Non-motion commands:
```bash
../.venv/bin/python cli.py PING
../.venv/bin/python cli.py GET_STATE
../.venv/bin/python cli.py STOP
../.venv/bin/python cli.py SET_LED --color green
../.venv/bin/python cli.py PLAY_SOUND --name ding_dong
../.venv/bin/python cli.py GET_BUTTONS
```

Motion commands require explicit opt-in:
```bash
../.venv/bin/python cli.py --allow-motion TURN_TO --heading 90
../.venv/bin/python cli.py --allow-motion DRIVE_DIST --meters 0.5 --speed 0.15
```

## Web App (Natural Language Control)

Start manually:
```bash
cd /opt/picoclaw-rp2040/robot-agent
../.venv/bin/python web_app.py --config config.yaml
```

Open from LAN:
```text
http://<pi-ip>:8080
```

Example natural-language commands:
- `ping`
- `get state`
- `stop`
- `turn to 90`
- `drive 0.5 meters speed 0.2 mps`
- `play ding dong`
- `turn on green light`
- `light off`
- `button state`

Motion commands require `Allow motion commands` checked in the UI.

## Dry-Run Smoke (No Hardware)

No RP2040 connection is required:

```bash
cd /opt/picoclaw-rp2040/robot-agent
./smoke_test.sh
```

Notes:
- movement is never triggered unless `--allow-motion` is passed
- invalid packets are ignored (fail closed)
- TCP mode is default; serial remains available as optional fallback in config

## Telemetry and Logs

Configured in `robot-agent/config.yaml`:
- raw link lines: `robot-agent/logs/raw_link.log`
- parsed telemetry JSONL: `robot-agent/logs/telemetry.jsonl`

Missing required telemetry fields are logged as warnings.
Telemetry also includes peripheral state fields (`led_color`, `button_a_pressed`, `button_b_pressed`, `sound_active`) when provided by firmware.

## systemd Service

Service file: `systemd/robot-agent.service`

On Pi:
```bash
sudo systemctl start robot-agent.service
sudo systemctl status robot-agent.service
sudo journalctl -u robot-agent.service -f
```

This service runs the web app and keeps the bridge link active in the background.
RP2040 firmware supports multi-client TCP, so CLI and web app can run together.

## Firmware Contract

See `firmware-rp2040/PROTOCOL.md` for:
- command/telemetry schema
- deadman heartbeat timeout (`2.0 s` default)
- STOP preemption and fail-closed packet rules

See `firmware-rp2040/PINOUT.md` for RP2040 pin mapping, tested PID defaults, and override options in `firmware-rp2040/micropython/wifi_config.py`.

## Next Steps

1. Add more sound/LED patterns and expose named presets in `PLAY_SOUND` and `SET_LED`.
2. Add mission-level primitives while preserving RP2040 authority for any motion safety checks.
3. Implement adapters under `picoclaw-integration/` without coupling bring-up path to cloud services.
