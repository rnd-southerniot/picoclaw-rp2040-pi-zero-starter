"""
Gate 1 — Board Alive Test
Checks: Pico W LED blinks, buttons GP20/GP21 respond

Note: Pico W LED is controlled via CYW43 WiFi chip, accessed as Pin("LED").

Pass criteria:
  - LED blinks 5× visible
  - Button A (GP20) reads LOW when pressed
  - Button B (GP21) reads LOW when pressed
"""

import machine
import time

# Pico W requires network import for LED access via CYW43
try:
    import network
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
except Exception:
    pass

import sys
sys.path.insert(0, "/lib")
sys.path.insert(0, ".")

from config import BUTTON_A_PIN, BUTTON_B_PIN


def run():
    print("=" * 40)
    print("GATE 1: Board Alive Test")
    print("=" * 40)

    passed = True

    # --- LED Blink ---
    led = machine.Pin("LED", machine.Pin.OUT)
    print("  Blinking LED 5 times...")
    for i in range(5):
        led.on()
        time.sleep(0.3)
        led.off()
        time.sleep(0.3)
    print("  LED blink complete. Did you see it? (visual check)")

    # --- Button A ---
    btn_a = machine.Pin(BUTTON_A_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    print(f"  Press Button A (GP{BUTTON_A_PIN}) within 5 seconds...")
    a_pressed = _wait_press(btn_a, timeout_s=5)
    if a_pressed:
        print("  Button A: DETECTED ✓")
    else:
        print("  Button A: NOT DETECTED ✗")
        passed = False

    # --- Button B ---
    btn_b = machine.Pin(BUTTON_B_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    print(f"  Press Button B (GP{BUTTON_B_PIN}) within 5 seconds...")
    b_pressed = _wait_press(btn_b, timeout_s=5)
    if b_pressed:
        print("  Button B: DETECTED ✓")
    else:
        print("  Button B: NOT DETECTED ✗")
        passed = False

    print("-" * 40)
    if passed:
        print("GATE 1: PASSED ✓")
    else:
        print("GATE 1: FAILED ✗")
    print()
    return passed


def _wait_press(pin, timeout_s=5):
    """Wait for a button press (active LOW). Returns True if pressed."""
    deadline = time.ticks_add(time.ticks_ms(), timeout_s * 1000)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if pin.value() == 0:
            time.sleep_ms(50)  # debounce
            if pin.value() == 0:
                return True
        time.sleep_ms(20)
    return False


if __name__ == "__main__":
    run()
