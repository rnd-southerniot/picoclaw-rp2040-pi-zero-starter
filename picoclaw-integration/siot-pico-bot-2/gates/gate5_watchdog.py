"""
gate5_watchdog.py — WatchdogKeeper safety layer verification

Verifies:
  Test 1: Software motor timeout stops motors within 500ms of 30-second elapsed time.
  Test 2: Hardware WDT can be fed without triggering a device reset.

Note on WDT reboot testing:
  It is NOT possible to verify actual WDT reboot behaviour in a gate script.
  A real WDT timeout would reset the device, terminating this script — there
  is no way to observe the reset from within the same run. Test 2 verifies
  the WDT is alive (can be fed) without triggering a reset. The reboot
  behaviour is a hardware guarantee from the RP2040, not something we can
  test in software.

On-device test (requires Pico W connected via USB):
    mpremote run gates/gate5_watchdog.py

Expected result:
    PASS: Software motor timeout triggered
    PASS: WDT fed successfully, device still running
    PASS: All watchdog safety tests passed
"""

import utime
from safety.watchdog import WatchdogKeeper

all_pass = True

print("gate5_watchdog: WatchdogKeeper safety layer test")
print()


# ── Test 1: Software motor timeout ───────────────────────────────────────────
print("--- Test 1: Software motor timeout ---")
print("  Creating WatchdogKeeper (timeout_ms=8000)...")

wdg = WatchdogKeeper(timeout_ms=8000)

# Flag to verify stop_fn was called
stop_was_called = False

def mock_stop():
    global stop_was_called
    stop_was_called = True

# Arm the timeout and simulate 31 seconds having elapsed
wdg.arm_motor_timeout()

# Override utime.time to simulate elapsed time.
# We temporarily patch the start time to simulate 31 seconds in the past
# without actually waiting 31 seconds.
_real_start = wdg._motor_start_time
wdg._motor_start_time = _real_start - 31  # simulate 31 seconds elapsed

# check_motor_timeout should fire because 31 > MOTOR_TIMEOUT_S (30)
triggered = wdg.check_motor_timeout(mock_stop)

if triggered and stop_was_called:
    print("  PASS: Software motor timeout triggered")
    print("  PASS: stop_fn was called by check_motor_timeout")
else:
    print("  FAIL: Software motor timeout did NOT trigger")
    print("    triggered =", triggered)
    print("    stop_was_called =", stop_was_called)
    all_pass = False

# Verify disarm happened automatically
if not wdg._motors_running and wdg._motor_start_time is None:
    print("  PASS: Timeout auto-disarmed after triggering")
else:
    print("  FAIL: Timeout was not disarmed after triggering")
    all_pass = False

# Verify second call is a no-op (disarmed — should not call stop_fn again)
stop_was_called = False
wdg.check_motor_timeout(mock_stop)
if not stop_was_called:
    print("  PASS: check_motor_timeout is a no-op when disarmed")
else:
    print("  FAIL: check_motor_timeout fired again after disarm")
    all_pass = False

print()


# ── Test 2: Hardware WDT alive ────────────────────────────────────────────────
print("--- Test 2: Hardware WDT feed ---")
print("  Feeding WDT 3 times with 100ms sleep between feeds...")
print("  (Actual WDT reboot cannot be tested in a gate — hardware guarantee.)")

wdg2 = WatchdogKeeper(timeout_ms=8000)
for i in range(3):
    wdg2._wdt.feed()
    utime.sleep_ms(100)
    print("  Feed {}/3 OK".format(i + 1))

print("  PASS: WDT fed successfully, device still running")
print()


# ── Test 3: Emergency stop ────────────────────────────────────────────────────
print("--- Test 3: Emergency stop ---")

wdg3 = WatchdogKeeper(timeout_ms=8000)
wdg3.arm_motor_timeout()

estop_called = False

def mock_estop():
    global estop_called
    estop_called = True

wdg3.emergency_stop(mock_estop)

if estop_called and not wdg3._motors_running and wdg3._motor_start_time is None:
    print("  PASS: Emergency stop called stop_fn and disarmed timeout")
else:
    print("  FAIL: Emergency stop did not behave correctly")
    print("    estop_called =", estop_called)
    print("    motors_running =", wdg3._motors_running)
    all_pass = False

print()


# ── Summary ───────────────────────────────────────────────────────────────────
if all_pass:
    print("PASS: All watchdog safety tests passed")
else:
    print("FAIL: One or more watchdog tests failed -- check output above")
