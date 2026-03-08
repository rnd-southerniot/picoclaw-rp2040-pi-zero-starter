# safety/sandbox.py — exec() restricted environment

import time as _time

_ALLOWED_MODULES = {
    "time": _time,
}


def _safe_import(name, *args, **kwargs):
    """Custom __import__ for exec() sandbox. Only allows whitelisted modules."""
    if name in _ALLOWED_MODULES:
        return _ALLOWED_MODULES[name]
    raise ImportError("import '{}' is not allowed. Only: {}".format(
        name, ", ".join(_ALLOWED_MODULES.keys())))


_SAFE_BUILTINS = {
    "print":     print,
    "range":     range,
    "len":       len,
    "int":       int,
    "float":     float,
    "str":       str,
    "bool":      bool,
    "list":      list,
    "dict":      dict,
    "abs":       abs,
    "min":       min,
    "max":       max,
    "round":     round,
    "True":      True,
    "False":     False,
    "None":      None,
    "__import__": _safe_import,
}


def make_exec_globals(robot_instance):
    """Return a restricted globals dict for exec()."""
    return {
        "__builtins__": _SAFE_BUILTINS,
        "robot": robot_instance,
    }


def run_student_code(code, robot_instance):
    """
    Execute student code string in restricted sandbox.
    Returns {'ok': True} or {'ok': False, 'error': 'message'}.
    Never raises — all exceptions are caught and returned as JSON-serializable dicts.
    """
    result = {"ok": True, "error": None}
    try:
        globs = make_exec_globals(robot_instance)
        exec(code, globs)
    except ImportError as e:
        result["ok"] = False
        result["error"] = "Import blocked: " + str(e)
    except SyntaxError as e:
        result["ok"] = False
        result["error"] = "Syntax error: " + str(e)
    except Exception as e:
        result["ok"] = False
        result["error"] = str(e)
    return result
