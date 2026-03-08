import math
import socket
import time

import network
from machine import Pin, PWM
import rp2

try:
    import ujson as json
except ImportError:  # pragma: no cover
    import json  # type: ignore

try:
    import neopixel
except ImportError:  # pragma: no cover
    neopixel = None

try:
    import wifi_config
except ImportError:
    wifi_config = None

# Safety and transport timing
DEADMAN_TIMEOUT_MS = 2000
TELEMETRY_PERIOD_MS = 250
CONTROL_PERIOD_MS = 50  # 20Hz
DEFAULT_TCP_PORT = 8765
MOTION_MODES = ("TURNING", "DRIVING")

# Pin map (aligned to firmware-rp2040/PINOUT.md, overrideable in wifi_config.py)
LEFT_MOTOR_A = int(getattr(wifi_config, "LEFT_MOTOR_A", 9)) if wifi_config else 9
LEFT_MOTOR_B = int(getattr(wifi_config, "LEFT_MOTOR_B", 8)) if wifi_config else 8
RIGHT_MOTOR_A = int(getattr(wifi_config, "RIGHT_MOTOR_A", 10)) if wifi_config else 10
RIGHT_MOTOR_B = int(getattr(wifi_config, "RIGHT_MOTOR_B", 11)) if wifi_config else 11
LEFT_ENC_A = int(getattr(wifi_config, "LEFT_ENC_A", 6)) if wifi_config else 6
LEFT_ENC_B = int(getattr(wifi_config, "LEFT_ENC_B", 7)) if wifi_config else 7
RIGHT_ENC_A = int(getattr(wifi_config, "RIGHT_ENC_A", 4)) if wifi_config else 4
RIGHT_ENC_B = int(getattr(wifi_config, "RIGHT_ENC_B", 5)) if wifi_config else 5
LEFT_ENC_INVERT = bool(getattr(wifi_config, "LEFT_ENC_INVERT", True)) if wifi_config else True
RIGHT_ENC_INVERT = bool(getattr(wifi_config, "RIGHT_ENC_INVERT", False)) if wifi_config else False

# Peripheral pins
NEOPIXEL_PIN = int(getattr(wifi_config, "NEOPIXEL_PIN", 18)) if wifi_config else 18
NEOPIXEL_COUNT = int(getattr(wifi_config, "NEOPIXEL_COUNT", 2)) if wifi_config else 2
BUZZER_PIN = int(getattr(wifi_config, "BUZZER_PIN", 22)) if wifi_config else 22
BUTTON_A_PIN = int(getattr(wifi_config, "BUTTON_A_PIN", 20)) if wifi_config else 20
BUTTON_B_PIN = int(getattr(wifi_config, "BUTTON_B_PIN", 21)) if wifi_config else 21

# Robot geometry / encoder constants
WHEEL_DIAMETER_MM = 65.0
TRACK_WIDTH_MM = 150.0
TICKS_PER_REV_QUAD = 1008.0
MM_PER_REV = math.pi * WHEEL_DIAMETER_MM
MM_PER_TICK = MM_PER_REV / TICKS_PER_REV_QUAD

# Motion control defaults
MOTOR_PWM_FREQ = 1000
MOTOR_MAX_SPEED_PCT = 70.0
MOTOR_MIN_EFFECTIVE_PCT = 22.0
TURN_TARGET_RPM = 45.0
TURN_DONE_TOL_DEG = 3.0
DRIVE_DONE_TOL_MM = 12.0

# Tested PID tuning from siot-pico-bot-2
PID_KP = 1.5
PID_KI = 0.8
PID_KD = 0.05

LED_COLORS = {
    "off": (0, 0, 0),
    "red": (32, 0, 0),
    "green": (0, 32, 0),
    "blue": (0, 0, 32),
    "yellow": (28, 20, 0),
    "cyan": (0, 24, 24),
    "magenta": (24, 0, 24),
    "white": (22, 22, 22),
}

SOUND_PATTERNS = {
    "ding_dong": ((880, 120), (0, 40), (660, 200), (0, 10)),
}

state = {
    "mode": "SAFE",
    "heading_deg": 0.0,
    "left_ticks": 0,
    "right_ticks": 0,
    "battery_v": 7.4,
    "fault_code": 0,
    "target_heading_deg": None,
    "target_meters": None,
    "target_speed_mps": None,
    "led_color": "off",
    "button_a_pressed": False,
    "button_b_pressed": False,
    "sound_active": False,
}

last_heartbeat_ms = time.ticks_ms()
start_ms = time.ticks_ms()

# Runtime control variables
_drive_start_avg_ticks = None
_last_control_ms = time.ticks_ms()
_prev_left_ticks = 0
_prev_right_ticks = 0

# Peripheral runtime
pixels = None
buzzer = None
button_a = None
button_b = None
_active_sound_steps = None
_active_sound_index = 0
_active_sound_deadline_ms = time.ticks_ms()


class Motor:
    def __init__(self, pin_a, pin_b, freq=MOTOR_PWM_FREQ):
        self._pwm_a = PWM(Pin(pin_a))
        self._pwm_b = PWM(Pin(pin_b))
        self._pwm_a.freq(freq)
        self._pwm_b.freq(freq)
        self.brake()

    def drive_pct(self, pct):
        pct = max(-100.0, min(100.0, float(pct)))
        duty = int(abs(pct) / 100.0 * 65535)
        if pct > 0:
            self._pwm_a.duty_u16(duty)
            self._pwm_b.duty_u16(0)
        elif pct < 0:
            self._pwm_a.duty_u16(0)
            self._pwm_b.duty_u16(duty)
        else:
            self.brake()

    def brake(self):
        self._pwm_a.duty_u16(0)
        self._pwm_b.duty_u16(0)


class Encoder:
    def __init__(self, pin_a, pin_b):
        self._count = 0
        self._pin_a = Pin(pin_a, Pin.IN, Pin.PULL_UP)
        self._pin_b = Pin(pin_b, Pin.IN, Pin.PULL_UP)
        self._pin_a.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self._isr_a)
        self._pin_b.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self._isr_b)

    def _isr_a(self, _pin):
        if self._pin_a.value() == self._pin_b.value():
            self._count += 1
        else:
            self._count -= 1

    def _isr_b(self, _pin):
        if self._pin_a.value() != self._pin_b.value():
            self._count += 1
        else:
            self._count -= 1

    def count(self):
        return self._count


class PID:
    def __init__(self, kp, ki, kd, out_min=-100.0, out_max=100.0, integral_limit=80.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.out_min = out_min
        self.out_max = out_max
        self.integral_limit = integral_limit
        self._integral = 0.0
        self._prev_error = 0.0
        self._first = True

    def reset(self):
        self._integral = 0.0
        self._prev_error = 0.0
        self._first = True

    def compute(self, setpoint, measured, dt):
        if dt <= 0:
            return 0.0
        error = setpoint - measured
        p_term = self.kp * error

        self._integral += error * dt
        self._integral = max(-self.integral_limit, min(self.integral_limit, self._integral))
        i_term = self.ki * self._integral

        if self._first:
            d_term = 0.0
            self._first = False
        else:
            d_term = self.kd * (error - self._prev_error) / dt

        self._prev_error = error
        out = p_term + i_term + d_term
        return max(self.out_min, min(self.out_max, out))


left_motor = None
right_motor = None
left_encoder = None
right_encoder = None
pid_left = PID(PID_KP, PID_KI, PID_KD)
pid_right = PID(PID_KP, PID_KI, PID_KD)

try:
    left_motor = Motor(LEFT_MOTOR_A, LEFT_MOTOR_B)
    right_motor = Motor(RIGHT_MOTOR_A, RIGHT_MOTOR_B)
    left_encoder = Encoder(LEFT_ENC_A, LEFT_ENC_B)
    right_encoder = Encoder(RIGHT_ENC_A, RIGHT_ENC_B)
except Exception as exc:
    state["fault_code"] = 2001
    print("Motion HW init failed:", exc)


def init_peripherals():
    global pixels, buzzer, button_a, button_b

    try:
        if neopixel is not None and NEOPIXEL_COUNT > 0:
            pixels = neopixel.NeoPixel(Pin(NEOPIXEL_PIN), NEOPIXEL_COUNT)
            set_led_color("off")
    except Exception as exc:
        pixels = None
        print("NeoPixel init warning:", exc)

    try:
        buzzer = PWM(Pin(BUZZER_PIN))
        buzzer.freq(1000)
        buzzer.duty_u16(0)
    except Exception as exc:
        buzzer = None
        print("Buzzer init warning:", exc)

    try:
        button_a = Pin(BUTTON_A_PIN, Pin.IN, Pin.PULL_UP)
    except Exception as exc:
        button_a = None
        print("Button A init warning:", exc)

    try:
        button_b = Pin(BUTTON_B_PIN, Pin.IN, Pin.PULL_UP)
    except Exception as exc:
        button_b = None
        print("Button B init warning:", exc)


def now_ms():
    return time.ticks_diff(time.ticks_ms(), start_ms)


def normalize_heading_deg(angle):
    while angle > 180.0:
        angle -= 360.0
    while angle <= -180.0:
        angle += 360.0
    return angle


def heading_error_deg(target, current):
    return normalize_heading_deg(target - current)


def emit_json(conn, payload):
    conn.send((json.dumps(payload) + "\n").encode("utf-8"))


def try_emit_json(conn, payload):
    try:
        emit_json(conn, payload)
        return True
    except Exception:
        return False


def read_buttons_state():
    if button_a is not None:
        state["button_a_pressed"] = button_a.value() == 0
    if button_b is not None:
        state["button_b_pressed"] = button_b.value() == 0


def set_led_color(color_name):
    color = str(color_name).lower()
    if color not in LED_COLORS:
        return False, "invalid_color"
    if pixels is None:
        return False, "led_unavailable"

    rgb = LED_COLORS[color]
    for i in range(NEOPIXEL_COUNT):
        pixels[i] = rgb
    try:
        pixels.write()
    except Exception:
        return False, "led_write_failed"

    state["led_color"] = color
    return True, None


def _sound_off():
    state["sound_active"] = False
    if buzzer is not None:
        buzzer.duty_u16(0)


def _sound_on(freq_hz):
    if buzzer is None:
        return
    try:
        buzzer.freq(max(1, int(freq_hz)))
        buzzer.duty_u16(22000)
        state["sound_active"] = True
    except Exception:
        _sound_off()


def stop_sound():
    global _active_sound_steps, _active_sound_index
    _active_sound_steps = None
    _active_sound_index = 0
    _sound_off()


def start_sound(name):
    global _active_sound_steps, _active_sound_index, _active_sound_deadline_ms

    key = str(name).lower()
    steps = SOUND_PATTERNS.get(key)
    if steps is None:
        return False, "unsupported_sound"
    if buzzer is None:
        return False, "buzzer_unavailable"

    _active_sound_steps = steps
    _active_sound_index = 0
    _active_sound_deadline_ms = time.ticks_ms()
    return True, None


def update_sound():
    global _active_sound_index, _active_sound_deadline_ms

    if _active_sound_steps is None:
        return

    now = time.ticks_ms()
    if time.ticks_diff(now, _active_sound_deadline_ms) < 0:
        return

    while _active_sound_steps is not None:
        if _active_sound_index >= len(_active_sound_steps):
            stop_sound()
            return

        freq, duration_ms = _active_sound_steps[_active_sound_index]
        _active_sound_index += 1

        if int(freq) <= 0:
            _sound_off()
        else:
            _sound_on(int(freq))

        hold_ms = max(1, int(duration_ms))
        _active_sound_deadline_ms = time.ticks_add(time.ticks_ms(), hold_ms)
        return


def telemetry_packet():
    read_buttons_state()
    return {
        "type": "telemetry",
        "time_ms": now_ms(),
        "mode": state["mode"],
        "heading_deg": state["heading_deg"],
        "left_ticks": state["left_ticks"],
        "right_ticks": state["right_ticks"],
        "battery_v": state["battery_v"],
        "fault_code": state["fault_code"],
        "target_heading_deg": state["target_heading_deg"],
        "target_meters": state["target_meters"],
        "target_speed_mps": state["target_speed_mps"],
        "led_color": state["led_color"],
        "button_a_pressed": state["button_a_pressed"],
        "button_b_pressed": state["button_b_pressed"],
        "sound_active": state["sound_active"],
    }


def parse_line(raw):
    line = raw.decode("utf-8").strip()
    if not line:
        raise ValueError("empty packet")
    payload = json.loads(line)
    if not isinstance(payload, dict):
        raise ValueError("packet must be object")
    return payload


def motion_hw_ready():
    return left_motor is not None and right_motor is not None and left_encoder is not None and right_encoder is not None


def _apply_motor_with_limits(motor, cmd_pct):
    if motor is None:
        return
    pct = max(-MOTOR_MAX_SPEED_PCT, min(MOTOR_MAX_SPEED_PCT, float(cmd_pct)))
    if pct != 0.0 and abs(pct) < MOTOR_MIN_EFFECTIVE_PCT:
        pct = MOTOR_MIN_EFFECTIVE_PCT if pct > 0 else -MOTOR_MIN_EFFECTIVE_PCT
    motor.drive_pct(pct)


def _drive_outputs(left_pct, right_pct):
    _apply_motor_with_limits(left_motor, left_pct)
    _apply_motor_with_limits(right_motor, right_pct)


def _brake_all():
    if left_motor is not None:
        left_motor.brake()
    if right_motor is not None:
        right_motor.brake()


def _stop_motion(mode="SAFE"):
    global _drive_start_avg_ticks
    _brake_all()
    pid_left.reset()
    pid_right.reset()
    _drive_start_avg_ticks = None
    state["mode"] = mode
    state["target_heading_deg"] = None
    state["target_meters"] = None
    state["target_speed_mps"] = None


def handle_command(payload):
    global last_heartbeat_ms, _drive_start_avg_ticks

    cmd = str(payload.get("cmd", "")).upper()
    if not cmd:
        return {"type": "err", "ok": False, "reason": "missing_cmd"}

    if cmd == "PING":
        return {"type": "ack", "cmd": "PING", "ok": True}

    if cmd == "GET_STATE":
        return telemetry_packet()

    if cmd == "GET_BUTTONS":
        read_buttons_state()
        return {
            "type": "ack",
            "cmd": "GET_BUTTONS",
            "ok": True,
            "button_a_pressed": state["button_a_pressed"],
            "button_b_pressed": state["button_b_pressed"],
        }

    if cmd == "SET_LED":
        color = payload.get("color")
        if color is None:
            return {"type": "err", "cmd": "SET_LED", "ok": False, "reason": "missing_color"}
        ok, reason = set_led_color(color)
        if not ok:
            return {"type": "err", "cmd": "SET_LED", "ok": False, "reason": reason}
        return {"type": "ack", "cmd": "SET_LED", "ok": True, "color": state["led_color"]}

    if cmd == "PLAY_SOUND":
        name = payload.get("name")
        if name is None:
            return {"type": "err", "cmd": "PLAY_SOUND", "ok": False, "reason": "missing_name"}
        ok, reason = start_sound(name)
        if not ok:
            return {"type": "err", "cmd": "PLAY_SOUND", "ok": False, "reason": reason}
        return {"type": "ack", "cmd": "PLAY_SOUND", "ok": True, "name": str(name).lower()}

    if cmd == "STOP":
        _stop_motion(mode="SAFE")
        stop_sound()
        return {"type": "ack", "cmd": "STOP", "ok": True}

    if cmd == "HEARTBEAT":
        last_heartbeat_ms = time.ticks_ms()
        return {"type": "ack", "cmd": "HEARTBEAT", "ok": True}

    if cmd == "TURN_TO":
        if "heading" not in payload:
            return {"type": "err", "cmd": "TURN_TO", "ok": False, "reason": "missing_heading"}
        if not motion_hw_ready():
            return {"type": "err", "cmd": "TURN_TO", "ok": False, "reason": "motion_hw_unavailable"}
        try:
            heading = float(payload["heading"])
        except Exception:
            return {"type": "err", "cmd": "TURN_TO", "ok": False, "reason": "bad_heading"}
        state["target_heading_deg"] = normalize_heading_deg(heading)
        state["target_meters"] = None
        state["target_speed_mps"] = None
        state["mode"] = "TURNING"
        state["fault_code"] = 0
        last_heartbeat_ms = time.ticks_ms()
        return {"type": "ack", "cmd": "TURN_TO", "ok": True}

    if cmd == "DRIVE_DIST":
        if "meters" not in payload or "speed" not in payload:
            return {"type": "err", "cmd": "DRIVE_DIST", "ok": False, "reason": "missing_drive_fields"}
        if not motion_hw_ready():
            return {"type": "err", "cmd": "DRIVE_DIST", "ok": False, "reason": "motion_hw_unavailable"}
        try:
            meters = float(payload["meters"])
            speed = abs(float(payload["speed"]))
        except Exception:
            return {"type": "err", "cmd": "DRIVE_DIST", "ok": False, "reason": "bad_drive_fields"}
        if meters == 0.0:
            _stop_motion(mode="LINKED")
            return {"type": "ack", "cmd": "DRIVE_DIST", "ok": True}
        if speed <= 0.0:
            return {"type": "err", "cmd": "DRIVE_DIST", "ok": False, "reason": "bad_speed"}
        state["target_meters"] = meters
        state["target_speed_mps"] = speed
        state["target_heading_deg"] = None
        state["mode"] = "DRIVING"
        state["fault_code"] = 0
        _drive_start_avg_ticks = None
        last_heartbeat_ms = time.ticks_ms()
        return {"type": "ack", "cmd": "DRIVE_DIST", "ok": True}

    return {"type": "err", "cmd": cmd, "ok": False, "reason": "unsupported_cmd"}


def enforce_deadman():
    if state["mode"] in MOTION_MODES:
        age = time.ticks_diff(time.ticks_ms(), last_heartbeat_ms)
        if age > DEADMAN_TIMEOUT_MS:
            state["fault_code"] = 1001
            _stop_motion(mode="SAFE")


def update_motion_control():
    global _last_control_ms, _prev_left_ticks, _prev_right_ticks, _drive_start_avg_ticks

    now = time.ticks_ms()
    if time.ticks_diff(now, _last_control_ms) < CONTROL_PERIOD_MS:
        return

    dt = time.ticks_diff(now, _last_control_ms) / 1000.0
    _last_control_ms = now

    if not motion_hw_ready():
        return

    left_ticks_raw = left_encoder.count()
    right_ticks_raw = right_encoder.count()
    left_ticks = -left_ticks_raw if LEFT_ENC_INVERT else left_ticks_raw
    right_ticks = -right_ticks_raw if RIGHT_ENC_INVERT else right_ticks_raw

    state["left_ticks"] = left_ticks
    state["right_ticks"] = right_ticks

    dl_ticks = left_ticks - _prev_left_ticks
    dr_ticks = right_ticks - _prev_right_ticks
    _prev_left_ticks = left_ticks
    _prev_right_ticks = right_ticks

    dl_mm = dl_ticks * MM_PER_TICK
    dr_mm = dr_ticks * MM_PER_TICK
    dtheta_deg = (dr_mm - dl_mm) / TRACK_WIDTH_MM * 57.2957795
    state["heading_deg"] = normalize_heading_deg(state["heading_deg"] + dtheta_deg)

    if dt <= 0:
        return

    left_rpm = (dl_ticks / TICKS_PER_REV_QUAD) * (60.0 / dt)
    right_rpm = (dr_ticks / TICKS_PER_REV_QUAD) * (60.0 / dt)

    if state["mode"] == "DRIVING":
        target_meters = float(state["target_meters"] or 0.0)
        target_speed_mps = float(state["target_speed_mps"] or 0.0)

        if target_meters == 0.0 or target_speed_mps <= 0.0:
            _stop_motion(mode="LINKED")
            return

        avg_ticks = (left_ticks + right_ticks) / 2.0
        if _drive_start_avg_ticks is None:
            _drive_start_avg_ticks = avg_ticks

        target_ticks = abs((target_meters * 1000.0) / MM_PER_TICK)
        traveled_ticks = abs(avg_ticks - _drive_start_avg_ticks)
        remaining_mm = max(0.0, (target_ticks - traveled_ticks) * MM_PER_TICK)
        if remaining_mm <= DRIVE_DONE_TOL_MM:
            _stop_motion(mode="LINKED")
            return

        target_rpm_mag = (target_speed_mps * 1000.0 / MM_PER_REV) * 60.0
        direction = 1.0 if target_meters > 0 else -1.0
        target_left_rpm = direction * target_rpm_mag
        target_right_rpm = direction * target_rpm_mag

        left_pct = pid_left.compute(target_left_rpm, left_rpm, dt)
        right_pct = pid_right.compute(target_right_rpm, right_rpm, dt)
        _drive_outputs(left_pct, right_pct)
        return

    if state["mode"] == "TURNING":
        target_heading = state["target_heading_deg"]
        if target_heading is None:
            _stop_motion(mode="LINKED")
            return

        err = heading_error_deg(float(target_heading), state["heading_deg"])
        if abs(err) <= TURN_DONE_TOL_DEG:
            _stop_motion(mode="LINKED")
            return

        direction = 1.0 if err > 0 else -1.0
        target_left_rpm = -direction * TURN_TARGET_RPM
        target_right_rpm = direction * TURN_TARGET_RPM

        left_pct = pid_left.compute(target_left_rpm, left_rpm, dt)
        right_pct = pid_right.compute(target_right_rpm, right_rpm, dt)
        _drive_outputs(left_pct, right_pct)
        return

    _brake_all()


def update_peripherals():
    read_buttons_state()
    update_sound()


def wifi_connect():
    country = getattr(wifi_config, "COUNTRY", "BD") if wifi_config else "BD"
    try:
        rp2.country(country)
    except Exception as exc:
        print("country set warning:", exc)

    sta_ssid = getattr(wifi_config, "WIFI_SSID", "") if wifi_config else ""
    sta_password = getattr(wifi_config, "WIFI_PASSWORD", "") if wifi_config else ""
    ap_ssid = getattr(wifi_config, "AP_SSID", "rp2040-bridge") if wifi_config else "rp2040-bridge"
    ap_password = getattr(wifi_config, "AP_PASSWORD", "rp2040bridge") if wifi_config else "rp2040bridge"

    sta = network.WLAN(network.STA_IF)
    ap = network.WLAN(network.AP_IF)
    ap.active(False)

    if sta_ssid:
        sta.active(True)
        if sta.isconnected():
            print("Wi-Fi STA already connected:", sta.ifconfig())
            return

        print("Wi-Fi STA connecting:", sta_ssid)
        sta.connect(sta_ssid, sta_password)
        for _ in range(150):
            if sta.isconnected():
                print("Wi-Fi STA connected:", sta.ifconfig())
                return
            time.sleep_ms(100)
        print("Wi-Fi STA connect timeout; fallback to AP mode")

    sta.active(False)
    ap.active(True)
    if ap_password and len(ap_password) >= 8:
        ap.config(essid=ap_ssid, password=ap_password)
    else:
        ap.config(essid=ap_ssid)
    print("Wi-Fi AP active:", ap.ifconfig())


def tcp_server():
    tcp_port = int(getattr(wifi_config, "TCP_PORT", DEFAULT_TCP_PORT)) if wifi_config else DEFAULT_TCP_PORT
    addr = socket.getaddrinfo("0.0.0.0", tcp_port)[0][-1]
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(addr)
    server.listen(4)
    server.settimeout(0.1)
    print("TCP server listening on port", tcp_port)

    clients = []
    last_tx_ms = time.ticks_ms()

    def drop_client(index, reason):
        client = clients[index]
        try:
            client["sock"].close()
        except Exception:
            pass
        print("TCP client disconnected:", client["addr"], reason)
        del clients[index]

    while True:
        try:
            conn, client_addr = server.accept()
        except OSError:
            conn = None

        if conn is not None:
            print("TCP client connected:", client_addr)
            conn.settimeout(0.0)
            clients.append({"sock": conn, "addr": client_addr, "buf": b""})
            if state["mode"] == "SAFE":
                state["mode"] = "LINKED"
                state["fault_code"] = 0

        enforce_deadman()
        update_motion_control()
        update_peripherals()

        now = time.ticks_ms()
        if clients and time.ticks_diff(now, last_tx_ms) >= TELEMETRY_PERIOD_MS:
            packet = telemetry_packet()
            for i in range(len(clients) - 1, -1, -1):
                if not try_emit_json(clients[i]["sock"], packet):
                    drop_client(i, "tx_error")
            last_tx_ms = now

        for i in range(len(clients) - 1, -1, -1):
            client = clients[i]
            sock = client["sock"]
            try:
                chunk = sock.recv(512)
            except OSError:
                chunk = None
            except Exception:
                drop_client(i, "rx_error")
                continue

            if chunk == b"":
                drop_client(i, "peer_closed")
                continue

            if not chunk:
                continue

            client["buf"] += chunk
            while b"\n" in client["buf"]:
                raw, _, client["buf"] = client["buf"].partition(b"\n")
                try:
                    payload = parse_line(raw)
                except Exception as exc:
                    ok = try_emit_json(
                        sock,
                        {"type": "err", "ok": False, "reason": "invalid_json", "detail": str(exc)},
                    )
                    if not ok:
                        drop_client(i, "tx_error")
                        break
                    continue

                response = handle_command(payload)
                if not try_emit_json(sock, response):
                    drop_client(i, "tx_error")
                    break

        if not clients and state["mode"] == "LINKED":
            _stop_motion(mode="SAFE")

        time.sleep_ms(10)


def main():
    try:
        led = Pin("LED", Pin.OUT)
        led.value(1)
    except Exception:
        led = None

    init_peripherals()
    wifi_connect()
    tcp_server()

    if led is not None:
        led.value(0)


main()
