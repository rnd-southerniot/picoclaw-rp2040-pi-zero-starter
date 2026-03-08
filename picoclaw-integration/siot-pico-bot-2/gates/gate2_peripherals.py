"""
Gate 2 — Onboard Peripherals (NeoPixel + Buzzer)
Checks: WS2812 RGB LEDs cycle colors, buzzer plays tones

Pass criteria:
  - NeoPixels cycle Red → Green → Blue (both LEDs)
  - Buzzer plays ascending C4-E4-G4-C5 scale
  - Ensure Robo Pico mute switch is OFF for buzzer test
"""

import machine
import neopixel
import time
import sys

sys.path.insert(0, "/lib")
sys.path.insert(0, ".")

from config import NEOPIXEL_PIN, NEOPIXEL_COUNT, BUZZER_PIN


def run():
    print("=" * 40)
    print("GATE 2: Onboard Peripherals")
    print("=" * 40)

    # --- NeoPixel Test ---
    print("  NeoPixel: cycling R → G → B → Off")
    np = neopixel.NeoPixel(machine.Pin(NEOPIXEL_PIN), NEOPIXEL_COUNT)

    colors = [
        ("Red",   (255, 0, 0)),
        ("Green", (0, 255, 0)),
        ("Blue",  (0, 0, 255)),
        ("Off",   (0, 0, 0)),
    ]

    for name, color in colors:
        for i in range(NEOPIXEL_COUNT):
            np[i] = color
        np.write()
        print(f"    {name}")
        time.sleep(0.8)

    print("  NeoPixel: complete (visual check)")

    # --- Buzzer Test ---
    print("  Buzzer: ascending C4-E4-G4-C5")
    print("  ⚠ Ensure mute switch is OFF!")
    buzzer = machine.PWM(machine.Pin(BUZZER_PIN))

    notes = [
        ("C4", 262),
        ("E4", 330),
        ("G4", 392),
        ("C5", 523),
    ]

    for name, freq in notes:
        buzzer.freq(freq)
        buzzer.duty_u16(8000)  # ~12% duty
        print(f"    {name} ({freq} Hz)")
        time.sleep(0.3)

    buzzer.duty_u16(0)  # silence
    buzzer.deinit()
    print("  Buzzer: complete (audio check)")

    print("-" * 40)
    print("GATE 2: PASSED ✓ (requires visual + audio confirmation)")
    print()
    return True


if __name__ == "__main__":
    run()
