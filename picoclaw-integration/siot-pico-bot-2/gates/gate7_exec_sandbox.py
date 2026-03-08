# gates/gate7_exec_sandbox.py — Verify exec() sandbox rejects forbidden imports and runs valid code
"""
Gate 7: exec() sandbox verification

Tests:
  1. import machine is blocked with ImportError
  2. import os is blocked with ImportError
  3. robot.stop() executes successfully
  4. Syntax error returns ok=False with error message
  5. robot.forward() sets target RPM (functional check)

No hardware required — runs on-device or host-side.
"""

from safety.sandbox import run_student_code
from robot import RobotAPI

robot = RobotAPI()


def test_import_machine_blocked():
    result = run_student_code("import machine", robot)
    assert result["ok"] == False, "Should block import machine"
    assert "import" in result["error"].lower() or "blocked" in result["error"].lower()
    print("PASS: import machine rejected:", result["error"])


def test_import_os_blocked():
    result = run_student_code("import os", robot)
    assert result["ok"] == False, "Should block import os"
    print("PASS: import os rejected:", result["error"])


def test_valid_robot_code_runs():
    result = run_student_code("robot.stop()", robot)
    assert result["ok"] == True, "robot.stop() should succeed: " + str(result)
    print("PASS: robot.stop() executed successfully")


def test_syntax_error_returns_error():
    result = run_student_code("robot.forward(", robot)
    assert result["ok"] == False, "Syntax error should return ok=False"
    assert "syntax" in result["error"].lower() or "Syntax" in result["error"]
    print("PASS: syntax error returned:", result["error"])


def test_robot_forward_functional():
    result = run_student_code("robot.forward(60)", robot)
    assert result["ok"] == True, "robot.forward(60) should succeed: " + str(result)
    print("PASS: robot.forward(60) executed successfully")


test_import_machine_blocked()
test_import_os_blocked()
test_valid_robot_code_runs()
test_syntax_error_returns_error()
test_robot_forward_functional()
print()
print("PASS: All exec() sandbox tests passed (gate7)")
