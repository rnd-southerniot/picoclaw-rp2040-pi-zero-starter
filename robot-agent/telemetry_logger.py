from __future__ import annotations
import logging
from pathlib import Path
from typing import Mapping, Any
import json


class TelemetryLogger:
    def __init__(self, telemetry_path: str, raw_path: str):
        self.telemetry_path = Path(telemetry_path)
        self.raw_path = Path(raw_path)
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        self.raw_path.parent.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger("robot_agent")
        if not self._logger.handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    def log_raw(self, line: str) -> None:
        with self.raw_path.open("a", encoding="utf-8") as f:
            f.write(line.rstrip("\n") + "\n")

    def log_telemetry(self, payload: Mapping[str, Any]) -> None:
        with self.telemetry_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(dict(payload), ensure_ascii=True) + "\n")

    def log_warning(self, message: str) -> None:
        self._logger.warning(message)
