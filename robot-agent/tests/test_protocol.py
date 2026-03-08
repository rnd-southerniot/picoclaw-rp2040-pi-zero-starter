from __future__ import annotations

import unittest
from pathlib import Path
import sys

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from protocol import decode_line, encode_command, telemetry_missing_fields, validate_command_payload


class ProtocolTests(unittest.TestCase):
    def test_encode_command_newline(self) -> None:
        data = encode_command({"cmd": "PING"})
        self.assertTrue(data.endswith(b"\n"))

    def test_validate_turn_to_requires_heading(self) -> None:
        with self.assertRaises(ValueError):
            validate_command_payload({"cmd": "TURN_TO"})

    def test_validate_drive_dist_requires_fields(self) -> None:
        with self.assertRaises(ValueError):
            validate_command_payload({"cmd": "DRIVE_DIST", "meters": 1.0})

    def test_validate_set_led_requires_color(self) -> None:
        with self.assertRaises(ValueError):
            validate_command_payload({"cmd": "SET_LED"})

    def test_validate_play_sound_requires_name(self) -> None:
        with self.assertRaises(ValueError):
            validate_command_payload({"cmd": "PLAY_SOUND"})

    def test_validate_set_led_normalizes_color(self) -> None:
        payload = validate_command_payload({"cmd": "SET_LED", "color": "GREEN"})
        self.assertEqual(payload["color"], "green")

    def test_validate_play_sound_normalizes_name(self) -> None:
        payload = validate_command_payload({"cmd": "PLAY_SOUND", "name": "DING_DONG"})
        self.assertEqual(payload["name"], "ding_dong")

    def test_decode_line_rejects_non_object(self) -> None:
        with self.assertRaises(ValueError):
            decode_line("[1,2,3]")

    def test_decode_line_rejects_invalid_json(self) -> None:
        with self.assertRaises(ValueError):
            decode_line("{bad json}")

    def test_missing_telemetry_fields(self) -> None:
        missing = telemetry_missing_fields({"time_ms": 1, "mode": "IDLE"})
        self.assertIn("heading_deg", missing)
        self.assertIn("fault_code", missing)


if __name__ == "__main__":
    unittest.main()
