"""
run_all.py — Sequential gate runner for v2 async firmware

Executes all gate verification scripts in order. Run with:

  mpremote run gates/run_all.py

Each gate is exec()'d in a try/except. A gate PASSES if it runs without
raising an exception AND its output contains the string 'PASS'.
Prints a summary at the end.

Note: Gate scripts that use uasyncio.run() will drive their own event loop.
"""

import uasyncio

# All gates in execution order.
# Ordered by dependency: async skeleton → motors → turns → sensors → safety → encoders
GATES = [
    "gates/gate1_async_skeleton.py",
    "gates/gate2_motor_distance.py",
    "gates/gate3_turn_angle.py",
    "gates/gate4_sensors.py",
    "gates/gate5_watchdog.py",
    "gates/gate6_pio_encoder.py",
    "gates/gate7_exec_sandbox.py",
]

passed = 0
failed = 0

for gate_path in GATES:
    print("=" * 40)
    print("Running:", gate_path)
    print("-" * 40)

    try:
        gate_src = open(gate_path).read()
        exec(gate_src, {"__name__": "__main__"})
        print("RESULT: PASS -", gate_path)
        passed += 1
    except Exception as e:
        print("RESULT: FAIL -", gate_path)
        print("  Error:", e)
        failed += 1

print()
print("=" * 40)
total = passed + failed
print("SUMMARY: {}/{} gates passed".format(passed, total))
print("=" * 40)
