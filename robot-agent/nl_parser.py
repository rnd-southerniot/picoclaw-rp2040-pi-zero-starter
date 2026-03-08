from __future__ import annotations

import re
from typing import Any, Dict, Tuple


class ParseError(ValueError):
    pass


TURN_RE = re.compile(r"(?:turn(?:\s+to)?|heading(?:\s+to)?|face)\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
DIST_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:m|meter|meters)\b", re.IGNORECASE)
SPEED_RE = re.compile(r"(?:speed\s*)?(-?\d+(?:\.\d+)?)\s*(?:m/s|mps)\b", re.IGNORECASE)


def parse_natural_language(text: str, default_drive_speed_mps: float = 0.2) -> Tuple[Dict[str, Any], bool]:
    t = (text or "").strip().lower()
    if not t:
        raise ParseError("empty command text")

    if "ping" in t:
        return {"cmd": "PING"}, False
    if "button" in t:
        return {"cmd": "GET_BUTTONS"}, False
    if "get state" in t or "state" in t or "status" in t or "telemetry" in t:
        return {"cmd": "GET_STATE"}, False
    if "stop" in t or "halt" in t or "brake" in t:
        return {"cmd": "STOP"}, False
    if "ding dong" in t or ("play" in t and "ding" in t):
        return {"cmd": "PLAY_SOUND", "name": "ding_dong"}, False
    if ("green light" in t or "green led" in t or "grren light" in t) and (
        "on" in t or "turn" in t or "set" in t
    ):
        return {"cmd": "SET_LED", "color": "green"}, False
    if "light off" in t or "led off" in t or "turn off light" in t:
        return {"cmd": "SET_LED", "color": "off"}, False

    m_turn = TURN_RE.search(t)
    if m_turn:
        return {"cmd": "TURN_TO", "heading": float(m_turn.group(1))}, True

    if "drive" in t or "forward" in t:
        meters = None
        speed = default_drive_speed_mps

        m_dist = DIST_RE.search(t)
        if m_dist:
            meters = float(m_dist.group(1))

        m_speed = SPEED_RE.search(t)
        if m_speed:
            speed = float(m_speed.group(1))

        if meters is None:
            raise ParseError("drive command needs distance like '0.5 meters'")

        return {"cmd": "DRIVE_DIST", "meters": meters, "speed": speed}, True

    raise ParseError("could not map text to supported command")
