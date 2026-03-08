from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional

SUPPORTED_COMMANDS = {
    "PING",
    "GET_STATE",
    "STOP",
    "HEARTBEAT",
    "TURN_TO",
    "DRIVE_DIST",
    "SET_LED",
    "PLAY_SOUND",
    "GET_BUTTONS",
}
MOTION_COMMANDS = {"TURN_TO", "DRIVE_DIST"}
REQUIRED_TELEMETRY_FIELDS = (
    "time_ms",
    "mode",
    "heading_deg",
    "left_ticks",
    "right_ticks",
    "battery_v",
    "fault_code",
)


def _to_object(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(payload)


def validate_command_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    obj = _to_object(payload)
    cmd = str(obj.get("cmd", "")).upper()
    if cmd not in SUPPORTED_COMMANDS:
        raise ValueError(f"unsupported cmd: {obj.get('cmd')!r}")
    validated: Dict[str, Any] = {"cmd": cmd}

    if cmd == "TURN_TO":
        if "heading" not in obj:
            raise ValueError("TURN_TO requires 'heading'")
        validated["heading"] = float(obj["heading"])
    elif cmd == "DRIVE_DIST":
        if "meters" not in obj or "speed" not in obj:
            raise ValueError("DRIVE_DIST requires 'meters' and 'speed'")
        validated["meters"] = float(obj["meters"])
        validated["speed"] = float(obj["speed"])
    elif cmd == "SET_LED":
        if "color" not in obj:
            raise ValueError("SET_LED requires 'color'")
        validated["color"] = str(obj["color"]).lower()
    elif cmd == "PLAY_SOUND":
        if "name" not in obj:
            raise ValueError("PLAY_SOUND requires 'name'")
        validated["name"] = str(obj["name"]).lower()

    return validated


def encode_command(payload: Mapping[str, Any]) -> bytes:
    validated = validate_command_payload(payload)
    return (json.dumps(validated, separators=(",", ":")) + "\n").encode("utf-8")


def decode_line(line: str) -> Dict[str, Any]:
    candidate = line.strip()
    if not candidate:
        raise ValueError("empty line")
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object")
    return payload


def telemetry_missing_fields(payload: Mapping[str, Any], required_fields: Optional[List[str]] = None) -> List[str]:
    required = required_fields or list(REQUIRED_TELEMETRY_FIELDS)
    return [field for field in required if field not in payload]
