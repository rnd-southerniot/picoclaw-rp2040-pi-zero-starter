from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from nl_parser import ParseError, parse_natural_language
from serial_bridge import SerialBridge
from telemetry_logger import TelemetryLogger


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def normalize_config_paths(cfg: Dict[str, Any], config_path: str) -> Dict[str, Any]:
    base = Path(config_path).resolve().parent

    logging_cfg = dict(cfg.get("logging", {}))
    for key in ("telemetry_log", "raw_log"):
        value = logging_cfg.get(key)
        if isinstance(value, str):
            p = Path(value)
            if not p.is_absolute():
                logging_cfg[key] = str(base / p)

    discovery_cfg = dict(cfg.get("discovery", {}))
    cache_file = discovery_cfg.get("cache_file")
    if isinstance(cache_file, str):
        p = Path(cache_file)
        if not p.is_absolute():
            discovery_cfg["cache_file"] = str(base / p)

    normalized = dict(cfg)
    normalized["logging"] = logging_cfg
    normalized["discovery"] = discovery_cfg
    return normalized


def build_bridge(cfg: Dict[str, Any], logger: TelemetryLogger) -> SerialBridge:
    transport_cfg = dict(cfg.get("transport", {}))
    if not transport_cfg and "serial" in cfg:
        transport_cfg = {"type": "serial", "serial": dict(cfg.get("serial", {}))}

    tcp_cfg = dict(transport_cfg.get("tcp", {}))
    serial_cfg = dict(transport_cfg.get("serial", cfg.get("serial", {})))
    discovery_cfg = dict(cfg.get("discovery", {}))

    return SerialBridge(
        logger=logger,
        dry_run=cfg.get("agent", {}).get("dry_run", False),
        required_telemetry_fields=cfg.get("agent", {}).get("required_telemetry_fields"),
        transport_type=str(transport_cfg.get("type", "tcp")).lower(),
        tcp_host=tcp_cfg.get("host", "auto"),
        tcp_port=tcp_cfg.get("port", 8765),
        tcp_connect_timeout=tcp_cfg.get("connect_timeout", 3.0),
        tcp_read_timeout=tcp_cfg.get("read_timeout", 1.0),
        serial_port=serial_cfg.get("port", "/dev/ttyACM0"),
        serial_baudrate=serial_cfg.get("baudrate", 115200),
        serial_timeout=serial_cfg.get("timeout", 1.0),
        discovery_enabled=bool(discovery_cfg.get("enabled", True)),
        discovery_candidates=list(discovery_cfg.get("candidates", [])),
        discovery_subnet_scan=bool(discovery_cfg.get("subnet_scan", True)),
        discovery_subnet_prefix=discovery_cfg.get("subnet_prefix"),
        discovery_cache_file=discovery_cfg.get("cache_file"),
    )


class BridgeManager:
    def __init__(
        self,
        bridge: SerialBridge,
        reconnect_delay_sec: float = 2.0,
        heartbeat_interval_sec: float = 1.0,
    ):
        self.bridge = bridge
        self.reconnect_delay_sec = reconnect_delay_sec
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self.connected = False
        self.last_error: Optional[str] = None
        self.last_telemetry: Optional[Dict[str, Any]] = None
        self.last_message: Optional[Dict[str, Any]] = None
        self._stop = threading.Event()
        self._send_lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.bridge.close()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.bridge.open()
                self.connected = True
                self.last_error = None
                next_heartbeat = time.monotonic()
                while not self._stop.is_set():
                    now = time.monotonic()
                    if now >= next_heartbeat:
                        with self._send_lock:
                            self.bridge.send({"cmd": "HEARTBEAT"})
                        next_heartbeat = now + self.heartbeat_interval_sec

                    msg = self.bridge.read_one()
                    if msg is None:
                        time.sleep(0.05)
                        continue
                    self.last_message = msg
                    msg_type = str(msg.get("type", "")).lower()
                    if msg_type in {"", "telemetry"}:
                        self.last_telemetry = msg
            except Exception as exc:
                self.connected = False
                self.last_error = str(exc)
                self.bridge.logger.log_warning(
                    f"Web bridge link error, retrying in {self.reconnect_delay_sec:.1f}s: {exc}"
                )
                time.sleep(self.reconnect_delay_sec)
            finally:
                self.connected = False
                self.bridge.close()

    def send(self, payload: Dict[str, Any]) -> None:
        if not self.connected:
            raise RuntimeError("bridge not connected")
        with self._send_lock:
            self.bridge.send(payload)


HTML_PAGE = """<!doctype html>
<html>
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
<title>RP2040 Control</title>
<style>
body{font-family:ui-sans-serif,system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;background:#f6f8fb;color:#132}
.card{background:#fff;border:1px solid #dde3ea;border-radius:10px;padding:14px;margin-bottom:12px}
input,button,textarea{font:inherit}
textarea{width:100%;min-height:70px}
.row{display:flex;gap:8px;flex-wrap:wrap}
button{border:1px solid #b9c5d3;background:#ecf2f8;padding:8px 12px;border-radius:8px;cursor:pointer}
button.primary{background:#1b8f5a;color:#fff;border-color:#1b8f5a}
pre{white-space:pre-wrap;background:#0f1720;color:#d6f1ff;padding:10px;border-radius:8px}
</style>
</head>
<body>
<h2>RP2040 Web Control (TCP)</h2>
<div class=\"card\">
<div id=\"status\">Loading...</div>
</div>
<div class=\"card\">
<label>Natural language command</label>
<textarea id=\"cmd\" placeholder=\"Examples: ping | get state | stop | turn to 90 | drive 0.5 meters speed 0.2 mps | play ding dong | turn on green light\"></textarea>
<div class=\"row\">
<label><input id=\"allowMotion\" type=\"checkbox\"> Allow motion commands</label>
<button class=\"primary\" onclick=\"sendNL()\">Send</button>
<button onclick=\"quick('PING')\">PING</button>
<button onclick=\"quick('GET_STATE')\">GET_STATE</button>
<button onclick=\"quick('STOP')\">STOP</button>
<button onclick=\"quick('SET_LED',{color:'green'})\">GREEN LIGHT</button>
<button onclick=\"quick('SET_LED',{color:'off'})\">LIGHT OFF</button>
<button onclick=\"quick('PLAY_SOUND',{name:'ding_dong'})\">DING DONG</button>
</div>
</div>
<div class=\"card\"><b>Last response</b><pre id=\"resp\">(none)</pre></div>
<div class=\"card\"><b>Last telemetry</b><pre id=\"tele\">(none)</pre></div>
<script>
async function j(url,opt){const r=await fetch(url,opt);const t=await r.text();try{return JSON.parse(t)}catch{return {ok:false,error:t}}}
async function refresh(){
  const s=await j('/api/state');
  document.getElementById('status').textContent = `connected=${s.connected} host=${s.current_host||'-'} error=${s.last_error||'-'}`;
  document.getElementById('tele').textContent = JSON.stringify(s.last_telemetry||{}, null, 2);
}
async function sendNL(){
  const text=document.getElementById('cmd').value;
  const allow_motion=document.getElementById('allowMotion').checked;
  const r=await j('/api/command',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text,allow_motion})});
  document.getElementById('resp').textContent = JSON.stringify(r, null, 2);
  refresh();
}
async function quick(cmd, extra={}){
  const allow_motion=document.getElementById('allowMotion').checked;
  const r=await j('/api/command',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(Object.assign({cmd,allow_motion}, extra))});
  document.getElementById('resp').textContent = JSON.stringify(r, null, 2);
  refresh();
}
setInterval(refresh, 1500); refresh();
</script>
</body>
</html>
"""


def make_handler(manager: BridgeManager, default_speed: float):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, code: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                body = HTML_PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/api/state":
                self._json(
                    200,
                    {
                        "connected": manager.connected,
                        "current_host": getattr(manager.bridge, "current_host", None),
                        "last_error": manager.last_error,
                        "last_message": manager.last_message,
                        "last_telemetry": manager.last_telemetry,
                    },
                )
                return
            self._json(404, {"ok": False, "error": "not found"})

        def do_POST(self):
            if self.path != "/api/command":
                self._json(404, {"ok": False, "error": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception:
                self._json(400, {"ok": False, "error": "invalid json body"})
                return

            allow_motion = bool(body.get("allow_motion", False))

            if "cmd" in body:
                payload = {"cmd": str(body["cmd"]).upper()}
                if payload["cmd"] == "TURN_TO":
                    payload["heading"] = float(body.get("heading"))
                if payload["cmd"] == "DRIVE_DIST":
                    payload["meters"] = float(body.get("meters"))
                    payload["speed"] = float(body.get("speed"))
                if payload["cmd"] == "SET_LED":
                    payload["color"] = str(body.get("color", "")).lower()
                if payload["cmd"] == "PLAY_SOUND":
                    payload["name"] = str(body.get("name", "")).lower()
            else:
                text = str(body.get("text", ""))
                try:
                    payload, motion = parse_natural_language(text, default_drive_speed_mps=default_speed)
                except ParseError as exc:
                    self._json(400, {"ok": False, "error": str(exc)})
                    return
                if motion and not allow_motion:
                    self._json(400, {"ok": False, "error": "motion command requires allow_motion=true"})
                    return

            if payload["cmd"] in {"TURN_TO", "DRIVE_DIST"} and not allow_motion:
                self._json(400, {"ok": False, "error": "motion command requires allow_motion=true"})
                return

            try:
                manager.send(payload)
            except Exception as exc:
                self._json(503, {"ok": False, "error": str(exc), "payload": payload})
                return

            self._json(200, {"ok": True, "payload": payload})

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="RP2040 web control app")
    parser.add_argument("--config", default=str(Path(__file__).resolve().with_name("config.yaml")))
    args = parser.parse_args()

    cfg = normalize_config_paths(load_config(args.config), args.config)
    logger = TelemetryLogger(cfg["logging"]["telemetry_log"], cfg["logging"]["raw_log"])

    bridge = build_bridge(cfg, logger)
    reconnect_delay = float(cfg.get("agent", {}).get("reconnect_delay_sec", 2.0))
    heartbeat_interval_sec = float(cfg.get("agent", {}).get("heartbeat_interval_sec", 1.0))
    manager = BridgeManager(
        bridge,
        reconnect_delay_sec=reconnect_delay,
        heartbeat_interval_sec=heartbeat_interval_sec,
    )
    manager.start()

    web_cfg = dict(cfg.get("web", {}))
    web_host = str(web_cfg.get("host", "0.0.0.0"))
    web_port = int(web_cfg.get("port", 8080))
    default_speed = float(cfg.get("agent", {}).get("default_drive_speed_mps", 0.2))

    handler = make_handler(manager, default_speed=default_speed)
    server = ThreadingHTTPServer((web_host, web_port), handler)
    print(f"Web UI listening on http://{web_host}:{web_port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        manager.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
