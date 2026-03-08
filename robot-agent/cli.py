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

    discovery_cfg = dict(cfg.get("discovery", {}))
    cache_file = discovery_cfg.get("cache_file")
    if isinstance(cache_file, str):
        candidate = Path(cache_file)
        if not candidate.is_absolute():
            discovery_cfg["cache_file"] = str(base / candidate)

    normalized = dict(cfg)
    normalized["logging"] = logging_cfg
    normalized["discovery"] = discovery_cfg
    return normalized


def build_bridge_kwargs(cfg: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    transport_cfg = dict(cfg.get("transport", {}))
    # Backward compatibility for old config files that had only `serial`.
    if not transport_cfg and "serial" in cfg:
        transport_cfg = {"type": "serial", "serial": dict(cfg.get("serial", {}))}

    transport_type = str(transport_cfg.get("type", "tcp")).lower()
    tcp_cfg = dict(transport_cfg.get("tcp", {}))
    serial_cfg = dict(transport_cfg.get("serial", cfg.get("serial", {})))
    discovery_cfg = dict(cfg.get("discovery", {}))

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
        "discovery_enabled": bool(discovery_cfg.get("enabled", True)),
        "discovery_candidates": list(discovery_cfg.get("candidates", [])),
        "discovery_subnet_scan": bool(discovery_cfg.get("subnet_scan", True)),
        "discovery_subnet_prefix": discovery_cfg.get("subnet_prefix"),
        "discovery_cache_file": discovery_cfg.get("cache_file"),
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

    p_led = subparsers.add_parser("SET_LED", aliases=["set_led"])
    p_led.add_argument(
        "--color",
        type=str,
        required=True,
        choices=["off", "red", "green", "blue", "yellow", "cyan", "magenta", "white"],
    )

    p_sound = subparsers.add_parser("PLAY_SOUND", aliases=["play_sound"])
    p_sound.add_argument("--name", type=str, required=True, choices=["ding_dong"])

    subparsers.add_parser("GET_BUTTONS", aliases=["get_buttons"])
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
    if args.command == "SET_LED":
        return {"cmd": "SET_LED", "color": args.color}
    if args.command == "PLAY_SOUND":
        return {"cmd": "PLAY_SOUND", "name": args.name}
    if args.command == "GET_BUTTONS":
        return {"cmd": "GET_BUTTONS"}
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


def wait_for_command_reply(bridge: SerialBridge, sent_cmd: str, timeout_sec: float) -> int:
    if bridge.dry_run:
        print({"ok": True, "type": "ack", "cmd": sent_cmd, "dry_run": True})
        return 0

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        msg = bridge.read_one()
        if msg is None:
            time.sleep(0.05)
            continue

        msg_type = str(msg.get("type", "")).lower()
        msg_cmd = str(msg.get("cmd", "")).upper()
        if msg_type in {"ack", "err"} and msg_cmd == sent_cmd:
            print(msg)
            return 0

        if sent_cmd == "GET_STATE" and msg_type in {"", "telemetry"}:
            print(msg)
            return 0

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
            sent_cmd = str(payload["cmd"]).upper()
            return wait_for_command_reply(bridge, sent_cmd=sent_cmd, timeout_sec=args.response_timeout)
        finally:
            bridge.close()


if __name__ == "__main__":
    raise SystemExit(main())
