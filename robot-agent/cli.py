from __future__ import annotations
import argparse
import time
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML is required. Install dependencies first, for example:\n"
        "  pip install pyyaml"
    ) from exc

from serial_bridge import SerialBridge
from telemetry_logger import TelemetryLogger
from protocol import MOTION_COMMANDS


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def normalize_config_paths(cfg: Dict[str, Any], config_path: str) -> Dict[str, Any]:
    base = Path(config_path).resolve().parent
    logging_cfg = dict(cfg.get("logging", {}))
    for key in ("telemetry_log", "raw_log"):
        value = logging_cfg.get(key)
        if isinstance(value, str):
            candidate = Path(value)
            if not candidate.is_absolute():
                logging_cfg[key] = str(base / candidate)
    normalized = dict(cfg)
    normalized["logging"] = logging_cfg
    return normalized


def build_bridge_kwargs(cfg: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    transport_cfg = dict(cfg.get("transport", {}))
    # Backward compatibility for old config files that had only `serial`.
    if not transport_cfg and "serial" in cfg:
        transport_cfg = {"type": "serial", "serial": dict(cfg.get("serial", {}))}

    transport_type = str(transport_cfg.get("type", "tcp")).lower()
    tcp_cfg = dict(transport_cfg.get("tcp", {}))
    serial_cfg = dict(transport_cfg.get("serial", cfg.get("serial", {})))

    return {
        "logger": TelemetryLogger(cfg["logging"]["telemetry_log"], cfg["logging"]["raw_log"]),
        "dry_run": dry_run,
        "required_telemetry_fields": cfg.get("agent", {}).get("required_telemetry_fields"),
        "transport_type": transport_type,
        "tcp_host": tcp_cfg.get("host", "rp2040.local"),
        "tcp_port": tcp_cfg.get("port", 8765),
        "tcp_connect_timeout": tcp_cfg.get("connect_timeout", 3.0),
        "tcp_read_timeout": tcp_cfg.get("read_timeout", 1.0),
        "serial_port": serial_cfg.get("port", "/dev/ttyACM0"),
        "serial_baudrate": serial_cfg.get("baudrate", 115200),
        "serial_timeout": serial_cfg.get("timeout", 1.0),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RP2040 robot bridge CLI")
    default_config = str(Path(__file__).resolve().with_name("config.yaml"))
    parser.add_argument("--config", default=default_config)
    parser.add_argument("--dry-run", action="store_true", help="Run without network/serial hardware")
    parser.add_argument(
        "--allow-motion",
        action="store_true",
        help="Required flag for TURN_TO and DRIVE_DIST",
    )
    parser.add_argument(
        "--response-timeout",
        type=float,
        default=2.0,
        help="Seconds to wait for a response after sending one command",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("PING", aliases=["ping"])
    subparsers.add_parser("GET_STATE", aliases=["get_state"])
    subparsers.add_parser("STOP", aliases=["stop"])

    p_turn = subparsers.add_parser("TURN_TO", aliases=["turn_to"])
    p_turn.add_argument("--heading", type=float, required=True)

    p_drive = subparsers.add_parser("DRIVE_DIST", aliases=["drive_dist"])
    p_drive.add_argument("--meters", type=float, required=True)
    p_drive.add_argument("--speed", type=float, required=True)

    subparsers.add_parser("MONITOR", aliases=["monitor"])
    return parser


def command_payload(args: argparse.Namespace) -> Dict[str, Any]:
    if args.command == "PING":
        return {"cmd": "PING"}
    if args.command == "GET_STATE":
        return {"cmd": "GET_STATE"}
    if args.command == "STOP":
        return {"cmd": "STOP"}
    if args.command == "TURN_TO":
        return {"cmd": "TURN_TO", "heading": args.heading}
    if args.command == "DRIVE_DIST":
        return {"cmd": "DRIVE_DIST", "meters": args.meters, "speed": args.speed}
    raise ValueError(f"unsupported command: {args.command}")


def ensure_motion_allowed(args: argparse.Namespace) -> None:
    if args.command in MOTION_COMMANDS and not args.allow_motion:
        raise SystemExit(
            "Refusing motion command without --allow-motion. "
            "This prevents accidental movement during tests."
        )


def wait_for_message(bridge: SerialBridge, timeout_sec: float) -> int:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        msg = bridge.read_one()
        if msg is not None:
            print(msg)
            return 0
        time.sleep(0.05)
    return 1


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.command = str(args.command).upper()

    cfg = normalize_config_paths(load_config(args.config), args.config)
    bridge = SerialBridge(
        **build_bridge_kwargs(
            cfg,
            dry_run=args.dry_run or cfg.get("agent", {}).get("dry_run", False),
        )
    )
    reconnect_delay_sec = float(cfg.get("agent", {}).get("reconnect_delay_sec", 2.0))

    ensure_motion_allowed(args)

    if args.command == "MONITOR":
        while True:
            try:
                bridge.open()
                while True:
                    msg = bridge.read_one()
                    if msg is not None:
                        print(msg)
                    time.sleep(0.05)
            except Exception as exc:
                bridge.logger.log_warning(f"Bridge link error, retrying in {reconnect_delay_sec:.1f}s: {exc}")
                time.sleep(reconnect_delay_sec)
            finally:
                bridge.close()
    else:
        bridge.open()
        try:
            payload = command_payload(args)
            bridge.send(payload)
            msg = bridge.read_one()
            if msg is not None:
                print(msg)
                return 0
            return wait_for_message(bridge, timeout_sec=args.response_timeout)
        finally:
            bridge.close()


if __name__ == "__main__":
    raise SystemExit(main())
