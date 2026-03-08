from __future__ import annotations

import unittest
from pathlib import Path
import sys

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nl_parser import ParseError, parse_natural_language


class NLParserTests(unittest.TestCase):
    def test_ping(self) -> None:
        payload, motion = parse_natural_language("please ping")
        self.assertEqual(payload["cmd"], "PING")
        self.assertFalse(motion)

    def test_get_state(self) -> None:
        payload, motion = parse_natural_language("get state")
        self.assertEqual(payload["cmd"], "GET_STATE")
        self.assertFalse(motion)

    def test_turn_to(self) -> None:
        payload, motion = parse_natural_language("turn to 90")
        self.assertEqual(payload["cmd"], "TURN_TO")
        self.assertEqual(payload["heading"], 90.0)
        self.assertTrue(motion)

    def test_drive_with_speed(self) -> None:
        payload, motion = parse_natural_language("drive 0.8 meters speed 0.25 mps")
        self.assertEqual(payload["cmd"], "DRIVE_DIST")
        self.assertAlmostEqual(payload["meters"], 0.8)
        self.assertAlmostEqual(payload["speed"], 0.25)
        self.assertTrue(motion)

    def test_drive_uses_default_speed(self) -> None:
        payload, _ = parse_natural_language("drive 1 meters", default_drive_speed_mps=0.3)
        self.assertAlmostEqual(payload["speed"], 0.3)

    def test_play_ding_dong(self) -> None:
        payload, motion = parse_natural_language("play ding dong")
        self.assertEqual(payload["cmd"], "PLAY_SOUND")
        self.assertEqual(payload["name"], "ding_dong")
        self.assertFalse(motion)

    def test_green_light_on(self) -> None:
        payload, motion = parse_natural_language("turn on green light")
        self.assertEqual(payload["cmd"], "SET_LED")
        self.assertEqual(payload["color"], "green")
        self.assertFalse(motion)

    def test_get_buttons(self) -> None:
        payload, motion = parse_natural_language("button state")
        self.assertEqual(payload["cmd"], "GET_BUTTONS")
        self.assertFalse(motion)

    def test_unrecognized(self) -> None:
        with self.assertRaises(ParseError):
            parse_natural_language("dance")


if __name__ == "__main__":
    unittest.main()
