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


def test_litestream_process_is_a_service_only_for_this_repo():
    assert od.classify(["litestream", "replicate", "-config", "/repo/litestream.yml"], ROOT) == "service"
    assert od.classify(["/x/litestream", "replicate", "-once", "-config", "/repo/litestream.yml"], ROOT) is None
    assert od.classify(["litestream", "replicate", "-config", "/other/litestream.yml"], ROOT) is None
    assert od.classify([PY, "/bin/okay-dann", "backup", "status"], ROOT) is None


def test_replica_url_for_r2_and_override():
    url = od.replica_url({"R2_ACCOUNT_ID": "abc123", "R2_BUCKET": "ei-backups"})
    assert url == "s3://ei-backups/endless-illusion?endpoint=https://abc123.r2.cloudflarestorage.com&region=auto"
    assert od.replica_url({"EI_REPLICA_URL": "file:///tmp/r", "R2_BUCKET": "x"}) == "file:///tmp/r"
    assert od.replica_url({"R2_BUCKET": "x"}) is None


def test_litestream_env_requires_keys_for_r2():
    r2 = {"R2_ACCOUNT_ID": "a", "R2_BUCKET": "b"}
    assert od.litestream_env(r2, base={}) is None
    env = od.litestream_env({**r2, "LITESTREAM_ACCESS_KEY_ID": "k", "LITESTREAM_SECRET_ACCESS_KEY": "s"}, base={})
    assert env["EI_DB_PATH"] == str(od.DB_PATH) and env["EI_REPLICA_URL"].startswith("s3://b/")
    # shell variables override the file; a file:// replica needs no keys
    env = od.litestream_env(r2, base={"EI_REPLICA_URL": "file:///tmp/r"})
    assert env["EI_REPLICA_URL"] == "file:///tmp/r"


def test_read_env_file(tmp_path):
    f = tmp_path / "x.env"
    f.write_text("# comment\n\nR2_BUCKET='b'\nLITESTREAM_ACCESS_KEY_ID = \"k\"\nnoequals\n")
    assert od.read_env_file(f) == {"R2_BUCKET": "b", "LITESTREAM_ACCESS_KEY_ID": "k"}
    assert od.read_env_file(tmp_path / "missing.env") == {}


def test_lab_release_asset_name():
    # Real naming on juice-shop/juice-shop releases (v20.4.0): zip on macOS, tgz on Linux.
    assert od.lab_release_asset("20.4.0", 26, "arm64", "darwin") == "juice-shop-20.4.0_node26_darwin_arm64.zip"
    assert od.lab_release_asset("20.4.0", 22, "x86_64", "linux") == "juice-shop-20.4.0_node22_linux_x64.tgz"


def test_lab_pick_node_major():
    assets = ["juice-shop-20.4.0_node22_darwin_arm64.zip", "juice-shop-20.4.0_node24_darwin_arm64.zip"]
    assert od.lab_pick_node_major(assets, 24, "arm64", "darwin") == 24
    assert od.lab_pick_node_major(assets, 26, "arm64", "darwin") == 24  # highest published <= local
    assert od.lab_pick_node_major(assets, 20, "arm64", "darwin") is None


def test_lab_process_classified_as_service():
    lab = od.LAB_DIR / "20.4.0" / "juice-shop_20.4.0" / "build" / "app.js"
    assert od.classify(["node", str(lab)], ROOT) == "service"
    assert od.classify(["/opt/homebrew/bin/node", str(lab)], ROOT) == "service"
    assert od.classify(["node", "/elsewhere/build/app.js"], ROOT) is None
    assert od.classify(["vim", str(lab)], ROOT) is None


def test_lab_valid_tag():
    for ok in ("v20.4.0", "20.4.0", "v21"):
        assert od.lab_valid_tag(ok)
    for bad in ("../x", "v1/../2", "v1.2.3-rc1", "", None, "v1.2.\n"):
        assert not od.lab_valid_tag(bad)


def test_lab_digest_requires_published_sha256(tmp_path):
    import hashlib

    f = tmp_path / "a.zip"
    f.write_bytes(b"data")
    good = "sha256:" + hashlib.sha256(b"data").hexdigest()
    assert od.lab_digest_ok(f, {"name": "a.zip", "digest": good})
    assert not od.lab_digest_ok(f, {"name": "a.zip"})  # no checksum published: refuse
    assert not od.lab_digest_ok(f, {"name": "a.zip", "digest": None})
    assert not od.lab_digest_ok(f, {"name": "a.zip", "digest": "sha256:" + "0" * 64})


def _fake_lsof(monkeypatch, stdout="", returncode=0, missing=False):
    import subprocess

    def run(cmd, **kw):
        if missing:
            raise FileNotFoundError("lsof")
        return subprocess.CompletedProcess(cmd, returncode, stdout, "")

    monkeypatch.setattr(od.subprocess, "run", run)


def test_lab_bind_ok_fails_closed(monkeypatch):
    good = "p42\nf22\nn127.0.0.1:3000\n"
    _fake_lsof(monkeypatch, good)
    assert od.lab_bind_ok(42, wait=0) == (True, "")
    for kwargs, word in (
        ({"missing": True}, "lsof"),
        ({"returncode": 1, "stdout": good}, "exit"),
        ({"stdout": ""}, "no listening"),
        ({"stdout": "p42\nf22\nn*:3000\n"}, "*:3000"),
        ({"stdout": good + "f23\nn[::1]:3000\n"}, "[::1]:3000"),
    ):
        _fake_lsof(monkeypatch, **kwargs)
        ok, reason = od.lab_bind_ok(42, wait=0)
        assert not ok and word in reason, (kwargs, reason)


def test_bind_shim_forces_loopback(tmp_path):
    import json
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    shim = tmp_path / "shim.cjs"
    shim.write_text(od.BIND_SHIM)
    probe = Path(__file__).parent / "bind_shim_probe.js"
    out = subprocess.run([node, "--require", str(shim), str(probe)], capture_output=True, text=True, timeout=30)
    assert json.loads(out.stdout) == ["127.0.0.1"] * 5, out.stderr
