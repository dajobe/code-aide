"""Verify cleanup ordering across native install methods."""

import hashlib
import io
import plistlib
import tarfile
from unittest import mock

import pytest

from code_aide import app_bundle, constants, install, operation_handlers
from code_aide import macos_quarantine as quarantine


@pytest.fixture(autouse=True)
def darwin(monkeypatch):
    monkeypatch.setattr(quarantine.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(quarantine.platform, "machine", lambda: "arm64")


@pytest.mark.parametrize(
    "installer_ok,cleanup_ok", [(True, True), (True, False), (False, True)]
)
@pytest.mark.parametrize("upgrade", [True, False])
def test_script_install_and_upgrade(installer_ok, cleanup_ok, upgrade):
    cfg = {
        "name": "Tool",
        "command": "tool",
        "install_type": "script",
        "install_url": "https://example.com",
        "next_steps": "Run tool",
    }
    module = operation_handlers if upgrade else install
    with (
        mock.patch.dict(constants._TOOLS_DATA, {"tool": cfg}),
        mock.patch.object(install, "command_exists", return_value=False),
        mock.patch.object(module, "run_install_script", return_value=installer_ok),
        mock.patch.object(
            quarantine, "clear_script_quarantine", return_value=cleanup_ok
        ) as clean,
    ):
        result = (
            operation_handlers._upgrade_script("tool", cfg, None)
            if upgrade
            else install.install_tool("tool")
        )
    assert bool(result) is (installer_ok and cleanup_ok)
    assert clean.called is installer_ok


@pytest.mark.parametrize("cask", [True, False])
def test_brew_upgrade_propagates_cleanup_failure(cask):
    handler = (
        operation_handlers._upgrade_brew_cask
        if cask
        else operation_handlers._upgrade_brew_formula
    )
    with (
        mock.patch.object(operation_handlers, "run_command"),
        mock.patch.object(operation_handlers, "_cask_app_stopped", return_value=True),
        mock.patch.object(
            quarantine, "clear_brew_quarantine", return_value=False
        ) as clean,
    ):
        assert not handler("tool", {"name": "Tool"}, "package")
    clean.assert_called_once_with("package", cask=cask)


@pytest.mark.parametrize("valid_checksum", [True, False])
def test_direct_download_cleans_after_verification_before_link(
    tmp_path, valid_checksum
):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as archive:
        member = tarfile.TarInfo("package/helper")
        member.size = 4
        archive.addfile(member, io.BytesIO(b"test"))
    content = data.getvalue()
    destination = tmp_path / "versions/1"
    link = tmp_path / "bin/tool"
    cfg = {
        "name": "Tool",
        "latest_version": "1",
        "install_dir": str(destination),
        "bin_dir": str(link.parent),
        "symlinks": {"tool": "helper"},
        "download_url_template": "https://example.com/{version}/{os}/{arch}",
        "download_sha256": (
            hashlib.sha256(content).hexdigest() if valid_checksum else "wrong"
        ),
    }

    def clear(path):
        assert path == str(destination)
        assert (destination / "helper").read_bytes() == b"test"
        assert not link.exists()
        return True

    with (
        mock.patch.object(install, "fetch_url", return_value=(content, {})),
        mock.patch.object(quarantine, "clear_quarantine", side_effect=clear) as clean,
    ):
        assert install.install_direct_download("tool", cfg) is valid_checksum
    assert clean.called is valid_checksum
    assert link.exists() is valid_checksum


@pytest.mark.parametrize(
    "dryrun,cleanup_ok", [(False, True), (False, False), (True, True)]
)
def test_existing_verified_bundle_cleanup(tmp_path, dryrun, cleanup_ok):
    bundle = tmp_path / "v1/Tool.app"
    (bundle / "Contents").mkdir(parents=True)
    with (bundle / "Contents/Info.plist").open("wb") as handle:
        plistlib.dump({"CFBundleShortVersionString": "1"}, handle)
    link = tmp_path / "Tool.app"
    link.symlink_to(bundle)
    cfg = {
        "name": "Tool",
        "latest_version": "1",
        "install_dir": str(tmp_path / "v{version}"),
        "app_bundle_name": "Tool.app",
        "app_link": str(link),
        "download_url_template": "https://example.com/{version}/{arch}",
    }
    with (
        mock.patch.object(app_bundle, "signature_ok", return_value=True),
        mock.patch.object(
            quarantine, "clear_quarantine", return_value=cleanup_ok
        ) as clean,
    ):
        assert app_bundle.install_app_bundle("tool", cfg, dryrun=dryrun) is cleanup_ok
    assert clean.called is not dryrun
