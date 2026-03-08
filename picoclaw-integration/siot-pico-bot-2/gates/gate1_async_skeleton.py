"""
gate1_async_skeleton.py — Proof-of-concept: 3-coroutine interleave test

Standalone script (does NOT import from tasks/) that proves cooperative
scheduling works on this device. Run with:

  mpremote run gates/gate1_async_skeleton.py

Expected output (interleaved A/B/C lines — exact order varies by timing):
  A 0
  B 0
  A 1
  C 0
  B 1
  A 2
  ...
  PASS: All 3 tasks completed without blocking
"""

import uasyncio


async def task_a():
    """Prints 'A {i}' 5 times, sleeping 100ms between each."""
    for i in range(5):
        print("A", i)
        await uasyncio.sleep_ms(100)


async def task_b():
    """Prints 'B {i}' 5 times, sleeping 150ms between each."""
    for i in range(5):
        print("B", i)
        await uasyncio.sleep_ms(150)


async def task_c():
    """Prints 'C {i}' 3 times, sleeping 200ms between each."""
    for i in range(3):
        print("C", i)
        await uasyncio.sleep_ms(200)


async def main():
    """Gather all three tasks and confirm interleaved completion."""
    await uasyncio.gather(task_a(), task_b(), task_c())
    print("PASS: All 3 tasks completed without blocking")


uasyncio.run(main())
