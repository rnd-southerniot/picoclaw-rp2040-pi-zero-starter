# robot.py — facade API (robot-as-object pattern)
import tasks.motor_task as _motor_task
import tasks.sensor_task as _sensor_task


class RobotAPI:
    """
    Stable robot facade API.
    This is the contract between firmware and all browser-generated code.
    All public methods here are the complete API surface for exec() commands.
    Never expose HAL or task internals below this layer.
    """

    def forward(self, rpm=60.0):
        """Drive both wheels forward at rpm."""
        _motor_task.set_target_rpm("left", rpm)
        _motor_task.set_target_rpm("right", rpm)

    def backward(self, rpm=60.0):
        """Drive both wheels backward at rpm."""
        _motor_task.set_target_rpm("left", -rpm)
        _motor_task.set_target_rpm("right", -rpm)

    def turn_left(self, rpm=40.0):
        """Pivot left: right wheel forward, left wheel backward."""
        _motor_task.set_target_rpm("left", -rpm)
        _motor_task.set_target_rpm("right", rpm)

    def turn_right(self, rpm=40.0):
        """Pivot right: left wheel forward, right wheel backward."""
        _motor_task.set_target_rpm("left", rpm)
        _motor_task.set_target_rpm("right", -rpm)

    def stop(self):
        """Stop both wheels."""
        _motor_task.set_target_rpm("left", 0.0)
        _motor_task.set_target_rpm("right", 0.0)

    def status(self):
        """Return current robot state as JSON-serializable dict."""
        state = _sensor_task.get_sensor_state()
        return {
            "rpm_left":    _motor_task.get_actual_rpm("left"),
            "rpm_right":   _motor_task.get_actual_rpm("right"),
            "ir":          state["ir"],
            "distance_cm": state["distance_cm"],
            "color":       state["color"],
            "heading":     state["heading"],
            "tick":        state["tick"],
        }
