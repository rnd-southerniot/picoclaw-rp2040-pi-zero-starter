from __future__ import annotations

import socket
import time
from typing import Any, Dict, List, Optional

try:
    import serial  # type: ignore
except Exception:  # pragma: no cover
    serial = None

from protocol import REQUIRED_TELEMETRY_FIELDS, decode_line, encode_command, telemetry_missing_fields
from telemetry_logger import TelemetryLogger
from discovery import discover_tcp_host


class SerialBridge:
    """
    Backward-compatible bridge class name.

    Supports two link types:
    - tcp: JSON-lines over Wi-Fi TCP socket (default)
    - serial: JSON-lines over UART/USB serial (fallback)
    """

    def __init__(
        self,
        logger: TelemetryLogger,
        dry_run: bool = False,
        required_telemetry_fields: Optional[List[str]] = None,
        transport_type: str = "tcp",
        tcp_host: str = "rp2040.local",
        tcp_port: int = 8765,
        tcp_connect_timeout: float = 3.0,
        tcp_read_timeout: float = 1.0,
        serial_port: str = "/dev/ttyACM0",
        serial_baudrate: int = 115200,
        serial_timeout: float = 1.0,
        discovery_enabled: bool = False,
        discovery_candidates: Optional[List[str]] = None,
        discovery_subnet_scan: bool = False,
        discovery_subnet_prefix: Optional[str] = None,
        discovery_cache_file: Optional[str] = None,
    ):
        self.logger = logger
        self.dry_run = dry_run
        self.required_telemetry_fields = required_telemetry_fields or list(REQUIRED_TELEMETRY_FIELDS)

        self.transport_type = transport_type.lower()

        self.tcp_host = tcp_host
        self.tcp_port = int(tcp_port)
        self.tcp_connect_timeout = float(tcp_connect_timeout)
        self.tcp_read_timeout = float(tcp_read_timeout)

        self.serial_port = serial_port
        self.serial_baudrate = int(serial_baudrate)
        self.serial_timeout = float(serial_timeout)
        self.discovery_enabled = discovery_enabled
        self.discovery_candidates = discovery_candidates or []
        self.discovery_subnet_scan = discovery_subnet_scan
        self.discovery_subnet_prefix = discovery_subnet_prefix
        self.discovery_cache_file = discovery_cache_file
        self.current_host = self.tcp_host

        self.ser = None
        self.sock = None
        self._tcp_rx_buffer = b""

    def open(self) -> None:
        if self.dry_run:
            return
        if self.transport_type == "tcp":
            resolved_host = discover_tcp_host(
                configured_host=self.tcp_host,
                port=self.tcp_port,
                connect_timeout=self.tcp_connect_timeout,
                enabled=self.discovery_enabled or self.tcp_host.lower() == "auto",
                candidates=self.discovery_candidates,
                subnet_scan=self.discovery_subnet_scan,
                subnet_prefix=self.discovery_subnet_prefix,
                cache_file=self.discovery_cache_file,
            )
            self.current_host = resolved_host
            self.sock = socket.create_connection(
                (resolved_host, self.tcp_port), timeout=self.tcp_connect_timeout
            )
            self.sock.settimeout(self.tcp_read_timeout)
            return
        if self.transport_type == "serial":
            if serial is None:
                raise RuntimeError("pyserial is not installed")
            self.ser = serial.Serial(self.serial_port, self.serial_baudrate, timeout=self.serial_timeout)
            time.sleep(1.5)
            return
        raise RuntimeError(f"unsupported transport_type: {self.transport_type}")

    def send(self, payload: Dict[str, Any]) -> None:
        encoded = encode_command(payload)
        if self.dry_run:
            self.logger.log_raw("DRYRUN SEND " + encoded.decode("utf-8").rstrip("\n"))
            return

        if self.transport_type == "tcp":
            if self.sock is None:
                raise RuntimeError("tcp socket not open")
            self.sock.sendall(encoded)
            return

        if self.transport_type == "serial":
            if self.ser is None:
                raise RuntimeError("serial port not open")
            self.ser.write(encoded)
            return

        raise RuntimeError(f"unsupported transport_type: {self.transport_type}")

    def _read_tcp_line(self) -> Optional[str]:
        if self.sock is None:
            raise RuntimeError("tcp socket not open")

        while b"\n" not in self._tcp_rx_buffer:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                return None
            if not chunk:
                raise RuntimeError("tcp connection closed by peer")
            self._tcp_rx_buffer += chunk

        raw_line, _, remainder = self._tcp_rx_buffer.partition(b"\n")
        self._tcp_rx_buffer = remainder
        return raw_line.decode("utf-8", errors="replace") + "\n"

    def _read_serial_line(self) -> Optional[str]:
        if self.ser is None:
            raise RuntimeError("serial port not open")
        line = self.ser.readline().decode("utf-8", errors="replace")
        if not line:
            return None
        return line

    def _parse_and_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        self.logger.log_raw(line)
        try:
            payload = decode_line(line)
        except ValueError as exc:
            self.logger.log_warning(f"Invalid JSON packet ignored: {exc}")
            return None

        payload_type = str(payload.get("type", "")).lower()
        if payload_type in {"", "telemetry"}:
            missing_fields = telemetry_missing_fields(payload, required_fields=self.required_telemetry_fields)
            for field in missing_fields:
                self.logger.log_warning(f"Telemetry missing required field: {field}")

        self.logger.log_telemetry(payload)
        return payload

    def read_one(self) -> Optional[Dict[str, Any]]:
        if self.dry_run:
            sample = {
                "time_ms": int(time.monotonic() * 1000),
                "mode": "DRY_RUN",
                "heading_deg": 0.0,
                "left_ticks": 0,
                "right_ticks": 0,
                "battery_v": 7.4,
                "fault_code": 0,
            }
            self.logger.log_raw("DRYRUN RECV " + str(sample))
            self.logger.log_telemetry(sample)
            return sample

        if self.transport_type == "tcp":
            line = self._read_tcp_line()
        elif self.transport_type == "serial":
            line = self._read_serial_line()
        else:
            raise RuntimeError(f"unsupported transport_type: {self.transport_type}")

        if line is None:
            return None
        return self._parse_and_log_line(line)

    def close(self) -> None:
        if self.ser is not None:
            self.ser.close()
            self.ser = None
        if self.sock is not None:
            self.sock.close()
            self.sock = None
            self._tcp_rx_buffer = b""
