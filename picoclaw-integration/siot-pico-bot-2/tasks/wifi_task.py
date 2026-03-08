"""
wifi_task.py — WiFi AP + HTTP server coroutine

Starts WiFi Access Point with a MAC-derived unique SSID (RoboPico-XXXX)
and runs Microdot async HTTP server with robot API routes.

Phase 2: replaces the placeholder coroutine with a real HTTP server.

Exports:
  start_ap()           — sync function, call from main.py boot section
  wifi_server_task()   — coroutine, schedule with uasyncio.gather()
"""

import network
import ubinascii
import utime
import uasyncio
import config

from microdot import Microdot
from microdot.cors import CORS
from robot import RobotAPI
from safety.sandbox import run_student_code

# ── Microdot app + CORS ──────────────────────────────────────────────────────
app = Microdot()
CORS(app, allowed_origins='*')

# ── Robot API singleton ──────────────────────────────────────────────────────
_robot = RobotAPI()

# ── HTTP Routes ──────────────────────────────────────────────────────────────

@app.get('/status')
async def status(request):
    """Return current robot state as JSON."""
    return _robot.status()

@app.post('/exec')
async def exec_endpoint(request):
    """
    Execute a robot program.
    Request body: {"code": "robot.forward(60)\n..."}
    Response: {"ok": true} or {"ok": false, "error": "message"}
    """
    body = request.json
    if not body or "code" not in body:
        return {"ok": False, "error": "Missing 'code' field"}, 400

    result = run_student_code(body["code"], _robot)
    return result, (200 if result["ok"] else 400)

# ── WiFi AP Startup ──────────────────────────────────────────────────────────

def start_ap():
    """
    Start WiFi Access Point with MAC-derived unique SSID.

    Returns (ap, ssid) tuple.
    Blocks until AP is active (max 10s) — call from sync boot section only.

    SSID format: "RoboPico-XXXX" where XXXX = last 2 bytes of AP MAC in hex.
    Password from config.WIFI_AP_PASSWORD.

    IMPORTANT RP2040 gotcha: ap.config(ssid=...) MUST be called BEFORE ap.active(True).
    """
    ap = network.WLAN(network.AP_IF)
    mac = ap.config('mac')
    suffix = ubinascii.hexlify(mac[-2:]).decode().upper()
    ssid = "{}-{}".format(config.WIFI_AP_SSID_PREFIX, suffix)

    ap.config(ssid=ssid, password=config.WIFI_AP_PASSWORD)
    ap.active(True)

    deadline = utime.ticks_add(utime.ticks_ms(), 10000)
    while not ap.active():
        if utime.ticks_diff(deadline, utime.ticks_ms()) <= 0:
            raise RuntimeError("WiFi AP failed to activate after 10s")
        utime.sleep_ms(200)

    ip = ap.ifconfig()[0]
    print("AP active: SSID={} IP={} Password={}".format(ssid, ip, config.WIFI_AP_PASSWORD))
    return ap, ssid

# ── Server Coroutine ─────────────────────────────────────────────────────────

async def wifi_server_task():
    """
    HTTP server coroutine — runs Microdot on port 80.

    AP startup is done in main.py boot section (sync).
    This coroutine starts the HTTP server and runs forever.

    Exception handling: wrap in try/except to prevent gather() cascade.
    On server crash, log error — WDT will reset if nothing recovers.
    """
    try:
        print("Starting HTTP server on 0.0.0.0:{}".format(config.HTTP_PORT))
        await app.start_server(host='0.0.0.0', port=config.HTTP_PORT, debug=False)
    except Exception as e:
        print("wifi_task ERROR:", e)
        # Do NOT re-raise — prevent gather() from cancelling motor/sensor tasks
