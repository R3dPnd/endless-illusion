"""Process matching for the okay-dann launcher (okay_dann.py)."""

from pathlib import Path

import okay_dann as od

ROOT = Path("/repo")
PY = "/usr/bin/python3"


def test_script_args_requires_python_interpreter():
    assert od.script_args([PY, "/x/okay-dann", "web", "--open"], od.LAUNCHER_NAMES) == ["web", "--open"]
    assert od.script_args(["vim", "okay_dann.py"], od.LAUNCHER_NAMES) is None
    assert od.script_args([PY, "other.py", "okay_dann.py"], od.LAUNCHER_NAMES) is None


def test_classify_launchers_and_services():
    assert od.classify([PY, "/bin/okay-dann", "dev"], ROOT) == "launcher"
    assert od.classify([PY, "/repo/pnd.py", "--web"], ROOT) == "launcher"
    assert od.classify(["/repo/.venv/bin/python", "-m", "hub"], ROOT) == "service"
    assert od.classify(["/repo/.venv/bin/python", "-m", "hub.desktop"], ROOT) == "service"
    assert od.classify(["node", "/repo/ui/node_modules/.bin/vite"], ROOT) == "service"
    # macOS framework python: no repo path in argv, matched by cwd
    framework = "/opt/homebrew/Python.app/Contents/MacOS/Python"
    assert od.classify([framework, "-m", "hub"], ROOT, cwd="/repo") == "service"
    assert od.classify([framework, "-m", "hub"], ROOT, cwd="/elsewhere") is None


def test_classify_ignores_control_commands_and_strangers():
    for cmd in ("stop", "restart", "status"):
        assert od.classify([PY, "/bin/okay-dann", cmd], ROOT) is None
    assert od.classify(["node", "/elsewhere/vite"], ROOT) is None
    assert od.classify(["node", "/repo/ui/node_modules/.bin/vite", "build"], ROOT) is None


def test_restart_args():
    assert od.restart_args([(1, "launcher", [PY, "/bin/okay-dann", "web", "--open"])]) == ["web", "--open"]
    assert od.restart_args([(1, "launcher", [PY, "pnd.py", "--dev"])]) == ["dev"]
    assert od.restart_args([(1, "launcher", [PY, "pnd.py"])]) == ["app"]
    assert od.restart_args([(1, "launcher", [PY, "/bin/okay-dann", "test"])]) is None
    assert od.restart_args([(1, "service", ["/repo/.venv/bin/python", "-m", "hub"])]) is None
