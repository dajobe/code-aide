"""Quarantine cleanup boundaries and installer integration."""

import platform
import subprocess
from unittest import mock

import pytest

from code_aide import constants, install, operation_handlers
from code_aide import macos_quarantine as quarantine


@pytest.fixture
def darwin(monkeypatch):
    monkeypatch.setattr(quarantine.platform, "system", lambda: "Darwin")


@pytest.mark.parametrize("system", ["Linux", "FreeBSD"])
def test_other_platforms_do_not_probe_or_modify(system, monkeypatch):
    monkeypatch.setattr(quarantine.platform, "system", lambda: system)
    with mock.patch.object(quarantine, "run_command") as run:
        assert quarantine.clear_quarantine("/missing")
        assert quarantine.clear_npm_quarantine("@openai/codex")
        assert quarantine.clear_script_quarantine({"command": "codex"})
        assert quarantine.clear_brew_quarantine("codex", cask=True)
    run.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [
        PermissionError("denied"),
        subprocess.CalledProcessError(1, "xattr", stderr="denied"),
        subprocess.TimeoutExpired("xattr", 60),
    ],
)
def test_cleanup_failure_is_reported(darwin, capsys, failure):
    with mock.patch.object(quarantine, "run_command", side_effect=failure) as run:
        assert not quarantine.clear_quarantine("/package with spaces")
    run.assert_called_once_with(
        [
            "/usr/bin/xattr",
            "-r",
            "-d",
            "-s",
            quarantine.QUARANTINE,
            "/package with spaces",
        ],
        timeout=60,
    )
    assert "Could not clear macOS quarantine" in capsys.readouterr().out


def test_npm_uses_selected_prefix(tmp_path, darwin):
    root = tmp_path / "prefix with spaces/lib/node_modules"
    prefix_args = ["--prefix", str(tmp_path / "prefix with spaces")]
    with (
        mock.patch.object(
            quarantine, "run_command", return_value=mock.Mock(stdout=str(root))
        ) as run,
        mock.patch.object(quarantine, "clear_quarantine", return_value=True) as clean,
    ):
        assert quarantine.clear_npm_quarantine("@openai/codex", prefix_args)
    run.assert_called_once_with(["npm", "root", "-g", *prefix_args], timeout=30)
    clean.assert_called_once_with(str(root / "@openai/codex"))


@pytest.mark.parametrize(
    "package", ["../other", "@../other", "@openai", "/tmp/tool", "tool@latest"]
)
def test_npm_refuses_non_package_paths(package, darwin):
    with mock.patch.object(quarantine, "run_command") as run:
        assert not quarantine.clear_npm_quarantine(package)
    run.assert_not_called()


def test_npm_refuses_linked_package(tmp_path, darwin):
    root = tmp_path / "node_modules"
    root.mkdir()
    (root / "tool").symlink_to(tmp_path / "unrelated")
    with mock.patch.object(
        quarantine, "run_command", return_value=mock.Mock(stdout=str(root))
    ):
        assert not quarantine.clear_npm_quarantine("tool")


def test_npm_probe_timeout_reports_failure(darwin):
    with mock.patch.object(
        quarantine, "run_command", side_effect=subprocess.TimeoutExpired("npm", 30)
    ):
        assert not quarantine.clear_npm_quarantine("tool")


def test_script_resolves_only_executable_not_shared_bin(tmp_path, darwin):
    binary = tmp_path / "versions/1.0/tool"
    binary.parent.mkdir(parents=True)
    binary.touch()
    link = tmp_path / "bin/tool"
    link.parent.mkdir()
    link.symlink_to(binary)
    with (
        mock.patch.object(quarantine.shutil, "which", return_value=None),
        mock.patch.object(quarantine, "clear_quarantine", return_value=True) as clean,
    ):
        assert quarantine.clear_script_quarantine(
            {"command": "tool", "macos_quarantine_paths": [str(link)]}
        )
    clean.assert_called_once_with(str(binary.resolve()))


@pytest.mark.parametrize("cask", [True, False])
def test_brew_cleans_package_directory(tmp_path, darwin, cask):
    root = tmp_path / "codex"
    with (
        mock.patch.object(
            quarantine, "run_command", return_value=mock.Mock(stdout=str(root))
        ) as run,
        mock.patch.object(quarantine, "clear_quarantine", return_value=True) as clean,
    ):
        assert quarantine.clear_brew_quarantine("codex", cask=cask)
    run.assert_called_once_with(
        ["brew", "--caskroom" if cask else "--prefix", "codex"], timeout=30
    )
    clean.assert_called_once_with(str(root.resolve()))


@pytest.mark.parametrize("succeeded", [True, False])
def test_npm_install_cleans_before_reporting_success(darwin, succeeded):
    cfg = {
        "command": "tool",
        "name": "Tool",
        "install_type": "npm",
        "npm_package": "tool",
        "next_steps": "Run tool",
    }
    with (
        mock.patch.dict(constants._TOOLS_DATA, {"tool": cfg}),
        mock.patch.object(install, "command_exists", return_value=False),
        mock.patch.object(install, "run_command"),
        mock.patch.object(
            install, "get_npm_global_bin_dir", return_value="/prefix/bin"
        ),
        mock.patch.object(
            quarantine, "clear_npm_quarantine", return_value=succeeded
        ) as clean,
        mock.patch.object(install, "success") as success,
    ):
        assert bool(install.install_tool("tool")) is succeeded
    clean.assert_called_once_with("tool")
    assert success.called is succeeded


def test_failed_install_and_dryrun_never_clean(darwin):
    cfg = {
        "command": "tool",
        "name": "Tool",
        "install_type": "npm",
        "npm_package": "tool",
    }
    with (
        mock.patch.dict(constants._TOOLS_DATA, {"tool": cfg}),
        mock.patch.object(install, "command_exists", return_value=False),
        mock.patch.object(
            install, "run_command", side_effect=subprocess.CalledProcessError(1, "npm")
        ),
        mock.patch.object(quarantine, "clear_npm_quarantine") as clean,
    ):
        assert not install.install_tool("tool")
        assert install.install_tool("tool", dryrun=True)
    clean.assert_not_called()


def test_npm_upgrade_preserves_prefix(darwin):
    with (
        mock.patch.object(
            operation_handlers, "_npm_prefix_args", return_value=["--prefix", "/chosen"]
        ),
        mock.patch.object(operation_handlers, "run_command"),
        mock.patch.object(
            quarantine, "clear_npm_quarantine", return_value=False
        ) as clean,
    ):
        assert not operation_handlers._upgrade_npm("tool", {"name": "Tool"}, "package")
    clean.assert_called_once_with("package", ["--prefix", "/chosen"])


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS extended attributes")
def test_real_macos_nested_helpers_preserve_other_attributes_and_external_links(
    tmp_path,
):
    package = tmp_path / "package with spaces"
    helper = package / "node_modules/native/bin/codex-code-mode-host"
    helper.parent.mkdir(parents=True)
    helper.touch()
    outside = tmp_path / "other-tool"
    outside.mkdir()
    unrelated = outside / "binary"
    unrelated.touch()
    (package / "linked-directory").symlink_to(outside, target_is_directory=True)
    (package / "linked-binary").symlink_to(unrelated)

    def xattr(*args):
        return subprocess.run(
            ["/usr/bin/xattr", *map(str, args)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    for path in (package, helper, unrelated):
        xattr("-w", quarantine.QUARANTINE, "0081;00000000;code-aide-test;", path)
        xattr("-w", "com.code-aide.test", "preserved", path)
    assert quarantine.clear_quarantine(str(package))
    assert quarantine.QUARANTINE not in xattr(helper)
    assert quarantine.QUARANTINE not in xattr(package)
    assert xattr("-p", "com.code-aide.test", helper).strip() == "preserved"
    assert quarantine.QUARANTINE in xattr(unrelated)
    assert quarantine.clear_quarantine(str(package))  # Missing attributes are harmless.
