# RP2040 <-> Pi Zero TCP Protocol (v0 JSONL)

This document defines the first bring-up contract between the Linux gateway (Pi Zero) and the RP2040 controller.

## Transport

- Primary link: Wi-Fi TCP socket (RP2040 runs TCP server, Pi Zero is TCP client)
- Default endpoint: `rp2040.local:8765` (configurable)
- Framing: UTF-8 JSON object per line (`\n` terminated)
- Direction:
  - Pi Zero -> RP2040: commands + heartbeat
  - RP2040 -> Pi Zero: telemetry + command acknowledgements/errors
- Optional fallback: USB/UART serial with the same JSON-lines payloads

## Core Safety Contract

- RP2040 is the final safety authority.
- Invalid packet handling is fail-closed:
  - Malformed JSON: reject packet, do not execute motion.
  - Unknown `cmd`: reject packet, do not execute motion.
  - Missing required command fields: reject packet, do not execute motion.
- `STOP` must preempt all motion immediately.
- Deadman heartbeat is required for motion modes:
  - Pi sends `HEARTBEAT` at `1 Hz` (or faster).
  - RP2040 deadman timeout default: `2.0 s`.
  - If timeout expires while moving, RP2040 must transition to safe stop.
- RP2040 enforces motor and heading limits regardless of host intent.

## Commands (Pi -> RP2040)

### `PING`
```json
{"cmd":"PING"}
```

### `GET_STATE`
```json
{"cmd":"GET_STATE"}
```

### `STOP`
```json
{"cmd":"STOP"}
```

### `HEARTBEAT`
```json
{"cmd":"HEARTBEAT"}
```

### `TURN_TO`
```json
{"cmd":"TURN_TO","heading":90.0}
```

Required fields:
- `heading` (float, degrees)

### `DRIVE_DIST`
```json
{"cmd":"DRIVE_DIST","meters":1.0,"speed":0.20}
```

Required fields:
- `meters` (float)
- `speed` (float, m/s)

### `SET_LED`
```json
{"cmd":"SET_LED","color":"green"}
```

Required fields:
- `color` (string): `off|red|green|blue|yellow|cyan|magenta|white`

### `PLAY_SOUND`
```json
{"cmd":"PLAY_SOUND","name":"ding_dong"}
```

Required fields:
- `name` (string): currently supports `ding_dong`

### `GET_BUTTONS`
```json
{"cmd":"GET_BUTTONS"}
```

## RP2040 Responses / Telemetry (RP2040 -> Pi)

### Acknowledgement / status examples
```json
{"type":"ack","cmd":"PING","ok":true}
{"type":"ack","cmd":"STOP","ok":true}
{"type":"err","cmd":"TURN_TO","ok":false,"reason":"missing_heading"}
{"type":"ack","cmd":"SET_LED","ok":true,"color":"green"}
{"type":"ack","cmd":"PLAY_SOUND","ok":true,"name":"ding_dong"}
{"type":"ack","cmd":"GET_BUTTONS","ok":true,"button_a_pressed":false,"button_b_pressed":true}
```

### Telemetry example
```json
{
  "time_ms": 12400,
  "mode": "AUTO",
  "heading_deg": 87.2,
  "target_heading_deg": 90.0,
  "heading_error_deg": 2.8,
  "left_ticks": 1031,
  "right_ticks": 1032,
  "battery_v": 7.5,
  "fault_code": 0,
  "led_color": "green",
  "button_a_pressed": false,
  "button_b_pressed": false,
  "sound_active": false
}
```

Host-side required telemetry fields:
- `time_ms`
- `mode`
- `heading_deg`
- `left_ticks`
- `right_ticks`
- `battery_v`
- `fault_code`

If any required field is missing, the host logs a warning and keeps processing.

## Versioning / Compatibility

- Backward-compatible additions may introduce optional fields.
- Breaking command/field changes should bump protocol version and be reflected in both firmware and host bridge.
