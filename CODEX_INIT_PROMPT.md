You are Codex CLI working inside a fresh repository for a robotics gateway project.

Project name: picoclaw-rp2040-pi-zero-starter
Owner: Arif
Objective: build a Raspberry Pi Zero gateway that talks to an RP2040 robot controller over serial, translates high-level motion commands into a compact protocol, logs telemetry, and is safe by default.

## Hard requirements
- Keep RP2040 as the real-time control and safety authority.
- Raspberry Pi Zero runs Linux-side orchestration only.
- Use Python 3 for the first bridge implementation.
- Use JSON-lines over serial for the first version.
- Default serial port: /dev/ttyACM0
- Default baud: 115200
- Include unit-testable protocol parsing where practical.
- Prefer simple, deterministic modules over framework-heavy code.
- Do not add cloud dependencies to the first bring-up.
- Preserve a folder for future PicoClaw integration, but do not block execution on it.

## Safety rules
- Never issue motor movement automatically during tests.
- Require explicit command-line flags for any movement test.
- Enforce a deadman heartbeat timeout in firmware contract docs.
- Any invalid packet must fail closed.
- Any missing telemetry field must be logged as a warning.

## Deliverables to create or improve
1. A Python package in `robot-agent/` with:
   - `serial_bridge.py`
   - `protocol.py`
   - `cli.py`
   - `telemetry_logger.py`
   - `config.yaml`
2. A documented serial protocol in `firmware-rp2040/PROTOCOL.md`
3. A minimal firmware pseudocode scaffold in `firmware-rp2040/`
4. A `systemd` service for the Pi Zero
5. A host-side script for discovering and SSHing into the Pi Zero on the same LAN
6. A `README.md` that explains first boot, deployment, testing, and next steps

## Immediate tasks
- Inspect the repository structure first.
- Normalize filenames and imports.
- Implement a working CLI that can send:
  - PING
  - GET_STATE
  - STOP
  - TURN_TO --heading <deg>
  - DRIVE_DIST --meters <m> --speed <mps>
- Log all raw telemetry lines to a file.
- Add a dry-run mode for development without hardware.
- Keep code small and readable.

## Command style
When executing shell commands:
- explain briefly what you are about to do
- group related changes
- avoid destructive commands unless clearly necessary

## Success condition
At the end, I should be able to:
1. SSH into the Pi Zero on my LAN
2. deploy this repo to `/opt/picoclaw-rp2040`
3. run the bridge
4. send `PING` and `GET_STATE`
5. later extend it into a PicoClaw-backed mission agent
