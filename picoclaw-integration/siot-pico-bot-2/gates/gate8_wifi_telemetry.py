"""
Gate 8 — WiFi Telemetry
Checks: Pico W creates AP, serves IMU telemetry via HTTP

Architecture:
  AP mode → "RoboPico-Lab" (password: robopico1)
  HTTP server on port 80:
    GET /     → Auto-refresh HTML dashboard
    GET /data → JSON: {"accel":{"x","y","z"}, "gyro":{"x","y","z"}}

Pass criteria:
  - AP visible on phone/laptop
  - http://192.168.4.1/ renders dashboard
  - Data updates on tilt
"""

import network
import socket
import json
import time
import sys

sys.path.insert(0, "/lib")
sys.path.insert(0, ".")

from config import (
    I2C_ID, I2C_SDA, I2C_SCL, I2C_FREQ,
    WIFI_AP_SSID_PREFIX, WIFI_AP_PASSWORD, WIFI_AP_IP, HTTP_PORT,
)
# Standalone gate uses a fixed test SSID (run only one rover at a time)
WIFI_AP_SSID = WIFI_AP_SSID_PREFIX + "-TEST"
from mpu6050 import MPU6050


# ── HTML Dashboard (auto-refresh every 1s) ──
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="1">
  <title>RoboPico Telemetry</title>
  <style>
    body { font-family: monospace; background: #1a1a2e; color: #e0e0e0;
           max-width: 600px; margin: 20px auto; padding: 10px; }
    h1 { color: #e94560; text-align: center; }
    .card { background: #16213e; border-radius: 8px; padding: 15px;
            margin: 10px 0; border-left: 4px solid #0f3460; }
    .card h2 { color: #0f3460; margin: 0 0 10px 0; }
    table { width: 100%%; border-collapse: collapse; }
    td { padding: 6px 10px; }
    td:first-child { color: #888; width: 40px; }
    td:last-child { text-align: right; font-size: 1.2em; color: #53d8fb; }
    .footer { text-align: center; color: #555; font-size: 0.8em; margin-top: 20px; }
  </style>
</head>
<body>
  <h1>🤖 RoboPico Telemetry</h1>
  <div class="card">
    <h2>Accelerometer (g)</h2>
    <table>
      <tr><td>X</td><td>%AX%</td></tr>
      <tr><td>Y</td><td>%AY%</td></tr>
      <tr><td>Z</td><td>%AZ%</td></tr>
    </table>
  </div>
  <div class="card">
    <h2>Gyroscope (°/s)</h2>
    <table>
      <tr><td>X</td><td>%GX%</td></tr>
      <tr><td>Y</td><td>%GY%</td></tr>
      <tr><td>Z</td><td>%GZ%</td></tr>
    </table>
  </div>
  <div class="card">
    <h2>Temperature</h2>
    <table>
      <tr><td></td><td>%TEMP% °C</td></tr>
    </table>
  </div>
  <div class="footer">Gate 8 — siot-pico-bot | Auto-refresh 1s</div>
</body>
</html>"""


def start_ap():
    """Create WiFi Access Point."""
    ap = network.WLAN(network.AP_IF)
    ap.config(essid=WIFI_AP_SSID, password=WIFI_AP_PASSWORD)
    ap.active(True)

    # Wait for AP to activate
    for _ in range(20):
        if ap.active():
            break
        time.sleep(0.5)

    if not ap.active():
        raise RuntimeError("Failed to activate AP")

    config = ap.ifconfig()
    print(f"  AP SSID:    {WIFI_AP_SSID}")
    print(f"  AP IP:      {config[0]}")
    print(f"  AP Password: {WIFI_AP_PASSWORD}")
    return ap


def serve(imu):
    """Run HTTP server loop."""
    addr = socket.getaddrinfo("0.0.0.0", HTTP_PORT)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(2)
    print(f"\n  HTTP server listening on port {HTTP_PORT}")
    print(f"  Dashboard: http://{WIFI_AP_IP}/")
    print(f"  JSON API:  http://{WIFI_AP_IP}/data")
    print(f"\n  Press Ctrl+C to stop.\n")

    while True:
        try:
            cl, remote = s.accept()
            request = cl.recv(1024).decode("utf-8")

            # Parse request path
            path = "/"
            if request:
                first_line = request.split("\r\n")[0]
                parts = first_line.split(" ")
                if len(parts) >= 2:
                    path = parts[1]

            # Read IMU
            ax, ay, az = imu.accel()
            gx, gy, gz = imu.gyro()
            temp = imu.temperature()

            if path == "/data":
                # JSON response
                data = {
                    "accel": {"x": round(ax, 3), "y": round(ay, 3), "z": round(az, 3)},
                    "gyro": {"x": round(gx, 2), "y": round(gy, 2), "z": round(gz, 2)},
                    "temp": round(temp, 1),
                }
                body = json.dumps(data)
                cl.send("HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n")
                cl.send(body)
            else:
                # HTML dashboard
                html = HTML_TEMPLATE
                html = html.replace("%AX%", f"{ax:+.3f}")
                html = html.replace("%AY%", f"{ay:+.3f}")
                html = html.replace("%AZ%", f"{az:+.3f}")
                html = html.replace("%GX%", f"{gx:+.2f}")
                html = html.replace("%GY%", f"{gy:+.2f}")
                html = html.replace("%GZ%", f"{gz:+.2f}")
                html = html.replace("%TEMP%", f"{temp:.1f}")
                cl.send("HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n")
                cl.send(html)

            cl.close()

        except OSError:
            pass
        except KeyboardInterrupt:
            break

    s.close()
    print("  Server stopped.")


def run():
    print("=" * 40)
    print("GATE 8: WiFi Telemetry")
    print("=" * 40)
    print()

    # Initialize IMU
    imu = MPU6050(I2C_ID, sda=I2C_SDA, scl=I2C_SCL, freq=I2C_FREQ)
    print("  ✓ MPU6050 initialized")

    # Start AP
    ap = start_ap()
    print("  ✓ AP active")

    # Serve
    try:
        serve(imu)
    finally:
        ap.active(False)
        print("  AP deactivated.")

    print("-" * 40)
    print("GATE 8: PASSED ✓ (if dashboard loaded with live data)")
    print()
    return True


if __name__ == "__main__":
    run()
