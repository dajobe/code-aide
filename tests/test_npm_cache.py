"""Cache lifetime regressions through standalone operation dispatch."""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import threading

import pytest

from code_aide import console, constants, install, operations
from code_aide.npm_cache import npm_cache_environment


@pytest.fixture
def cache_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize("route", ["install", "upgrade", "remove"])
@pytest.mark.parametrize("fail", [False, True])
def test_operation_downloads_removed(cache_home, monkeypatch, route, fail):
    user_cache = cache_home / "existing-cache"
    user_cache.mkdir()
    marker = user_cache / "keep"
    marker.write_text("existing")
    monkeypatch.setenv("NPM_CONFIG_CACHE", str(user_cache))
    monkeypatch.setenv("npm_config_prefix", "/example/prefix")
    monkeypatch.setenv("NPM_TOKEN", "fake-token")
    original = os.environ.copy()
    seen = []

    def run(cmd, **kwargs):
        env = kwargs["env"]
        cache = Path(env["npm_config_cache"])
        assert cache.stat().st_mode & 0o777 == 0o700
        assert "NPM_CONFIG_CACHE" not in env
        assert env["npm_config_prefix"] == "/example/prefix"
        assert env["NPM_TOKEN"] == "fake-token"
        (cache / "download").write_bytes(b"synthetic tarball")
        seen.append(cache)
        if fail:
            raise subprocess.CalledProcessError(1, cmd, stderr="fake failure")
        return subprocess.CompletedProcess(cmd, 0, stdout="/example/prefix")

    cfg = dict(
        name="Fake Tool",
        command="fake-tool",
        install_type="npm",
        npm_package="fake-tool",
        next_steps="Run fake-tool",
    )
    monkeypatch.setitem(constants._TOOLS_DATA, "fake", cfg)
    monkeypatch.setattr(console, "run_npm_process", run)
    monkeypatch.setattr(install, "command_exists", lambda _: False)
    monkeypatch.setattr(install.platform, "system", lambda: "Linux")
    monkeypatch.setattr(operations, "is_tool_installed", lambda _: True)
    monkeypatch.setattr(operations, "is_deprecated_install", lambda _: False)
    monkeypatch.setattr(
        operations,
        "detect_install_method",
        lambda _: {"method": "npm", "detail": "fake-tool"},
    )
    monkeypatch.setattr(operations, "_get_upgrade_snapshot", lambda *a: {})
    monkeypatch.setattr(
        operations,
        "_upgrade_result_from_snapshots",
        lambda *a: operations.UpgradeResult.CHANGED,
    )
    if route == "install":
        assert bool(install.install_tool("fake")) is not fail
    elif route == "upgrade":
        result = operations.upgrade_tool("fake")
        assert (result == operations.UpgradeResult.FAILED) is fail
    else:
        assert operations.remove_tool("fake") is not fail
    assert seen and all(not p.exists() for p in seen)
    assert marker.read_text() == "existing"
    assert os.environ == original


def test_concurrent_operations_keep_each_others_downloads(cache_home):
    barrier = threading.Barrier(2)

    def operation(_):
        with npm_cache_environment() as env:
            path = Path(env["npm_config_cache"])
            (path / "download").write_text("data")
            barrier.wait(timeout=5)
            assert len(list(path.parent.iterdir())) == 2
            barrier.wait(timeout=5)
            return path

    with ThreadPoolExecutor(max_workers=2) as pool:
        paths = list(pool.map(operation, range(2)))
    assert paths[0] != paths[1]
    assert all(not path.exists() for path in paths)


@pytest.mark.parametrize("exception", [KeyboardInterrupt, subprocess.TimeoutExpired])
def test_exception_cleanup(cache_home, monkeypatch, exception):
    seen = []

    def run(cmd, **kwargs):
        seen.append(Path(kwargs["env"]["npm_config_cache"]))
        if exception is subprocess.TimeoutExpired:
            raise exception(cmd, 0.01)
        raise exception()

    monkeypatch.setattr(console, "run_npm_process", run)
    with pytest.raises(exception):
        console.run_command(["npm", "install", "fake"], timeout=0.01)
    assert not seen[0].exists()


def test_non_npm_and_dryrun_do_not_create_cache(cache_home, monkeypatch):
    monkeypatch.setattr(
        console.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0)
    )
    console.run_command(["example", "install"])
    monkeypatch.setattr(install, "command_exists", lambda _: False)
    monkeypatch.setattr(install.platform, "system", lambda: "Linux")
    assert install.install_tool("codex", dryrun=True)
    assert not (cache_home / ".cache").exists()


@pytest.mark.parametrize("returncode", [0, 1])
def test_script_downloads_removed(cache_home, monkeypatch, returncode):
    # Real bash exercises an installer subprocess rather than mocking its env.
    fake_bin = cache_home / "bin"
    fake_bin.mkdir()
    fake_npm = fake_bin / "npm"
    fake_npm.write_text(
        "#!/bin/sh\n"
        'mkdir -p "$npm_config_cache/nested"\n'
        'printf download > "$npm_config_cache/nested/archive"\n'
        'printf "%s" "$npm_config_cache" > "$HOME/observed-cache"\n'
        f"exit {returncode}\n"
    )
    fake_npm.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ["PATH"])
    script = b"npm install -g fake-tool\n"
    monkeypatch.setattr(install, "fetch_url", lambda _: (script, None))
    assert install.run_install_script("https://example.invalid", "Fake") is (
        returncode == 0
    )
    observed = Path((cache_home / "observed-cache").read_text())
    assert not observed.exists()


def test_explicit_cache_override_rejected_before_cache_creation(cache_home):
    with pytest.raises(ValueError, match="cache overrides"):
        console.run_command(["npm", "install", "--cache=/example"])
    assert not (cache_home / ".cache").exists()


def test_symlink_cache_parent_rejected(cache_home, tmp_path):
    target = tmp_path / "outside"
    target.mkdir(mode=0o755)
    (cache_home / ".cache").symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        with npm_cache_environment():
            pytest.fail("must reject symlink")
    assert not list(target.iterdir())
    assert target.stat().st_mode & 0o777 == 0o755


def test_real_timeout_stops_descendant_before_cleanup(cache_home, monkeypatch):
    import sys
    import time

    fake_bin = cache_home / "bin"
    fake_bin.mkdir()
    cache_record = cache_home / "cache-path"
    ready = cache_home / "ready"
    child = cache_home / "writer.py"
    child.write_text(
        "import os, pathlib, time\n"
        "p = pathlib.Path(os.environ['npm_config_cache'])\n"
        "pathlib.Path(os.environ['HOME'], 'ready').write_text('ready')\n"
        "while True:\n"
        " p.mkdir(parents=True, exist_ok=True)\n"
        " (p / 'download').write_text('data')\n"
        " time.sleep(0.01)\n"
    )
    fake_npm = fake_bin / "npm"
    fake_npm.write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, subprocess, sys, time\n"
        "pathlib.Path(os.environ['HOME'], 'cache-path').write_text(os.environ['npm_config_cache'])\n"
        f"subprocess.Popen([sys.executable, {str(child)!r}])\n"
        "time.sleep(30)\n"
    )
    fake_npm.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ["PATH"])
    with pytest.raises(subprocess.TimeoutExpired):
        console.run_command(["npm", "install", "fake"], timeout=0.5)
    assert ready.exists()
    cache = Path(cache_record.read_text())
    assert not cache.exists()
    # The descendant would recreate its directory within 10ms if still alive.
    time.sleep(0.1)
    assert not cache.exists()
