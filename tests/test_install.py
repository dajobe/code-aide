"""Unit tests for installer helpers."""

import io
import os
import tarfile
import tempfile
import unittest
from unittest import mock

from code_aide import install as cli_install


class TestDetectOsArch(unittest.TestCase):
    """Tests for detect_os_arch."""

    @mock.patch.object(cli_install.platform, "machine", return_value="x86_64")
    @mock.patch.object(cli_install.platform, "system", return_value="Linux")
    def test_linux_x86_64(self, mock_sys, mock_mach):
        self.assertEqual(cli_install.detect_os_arch(), ("linux", "x64"))

    @mock.patch.object(cli_install.platform, "machine", return_value="aarch64")
    @mock.patch.object(cli_install.platform, "system", return_value="Linux")
    def test_linux_aarch64(self, mock_sys, mock_mach):
        self.assertEqual(cli_install.detect_os_arch(), ("linux", "arm64"))

    @mock.patch.object(cli_install.platform, "machine", return_value="arm64")
    @mock.patch.object(cli_install.platform, "system", return_value="Darwin")
    def test_darwin_arm64(self, mock_sys, mock_mach):
        self.assertEqual(cli_install.detect_os_arch(), ("darwin", "arm64"))

    @mock.patch.object(cli_install.platform, "machine", return_value="amd64")
    @mock.patch.object(cli_install.platform, "system", return_value="Darwin")
    def test_darwin_amd64(self, mock_sys, mock_mach):
        self.assertEqual(cli_install.detect_os_arch(), ("darwin", "x64"))

    @mock.patch.object(cli_install.platform, "machine", return_value="x86_64")
    @mock.patch.object(cli_install.platform, "system", return_value="Windows")
    def test_unsupported_os(self, mock_sys, mock_mach):
        with self.assertRaises(RuntimeError):
            cli_install.detect_os_arch()

    @mock.patch.object(cli_install.platform, "machine", return_value="mips")
    @mock.patch.object(cli_install.platform, "system", return_value="Linux")
    def test_unsupported_arch(self, mock_sys, mock_mach):
        with self.assertRaises(RuntimeError):
            cli_install.detect_os_arch()

    @mock.patch.object(cli_install.platform, "machine", return_value="amd64")
    @mock.patch.object(cli_install.platform, "system", return_value="FreeBSD")
    def test_freebsd_amd64(self, mock_sys, mock_mach):
        self.assertEqual(cli_install.detect_os_arch(), ("freebsd", "x64"))

    @mock.patch.object(cli_install.platform, "machine", return_value="arm64")
    @mock.patch.object(cli_install.platform, "system", return_value="FreeBSD")
    def test_freebsd_arm64(self, mock_sys, mock_mach):
        self.assertEqual(cli_install.detect_os_arch(), ("freebsd", "arm64"))


class TestInstallToolFreeBSD(unittest.TestCase):
    """Tests for install_tool on FreeBSD."""

    def _make_tool_config(self, **overrides):
        base = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "npm",
            "npm_package": "test-tool",
            "next_steps": "Run test-tool",
            "docs_url": "https://example.com",
        }
        base.update(overrides)
        return base

    @mock.patch.object(cli_install.platform, "system", return_value="FreeBSD")
    @mock.patch.object(cli_install, "command_exists", return_value=False)
    def test_freebsd_no_port_returns_false(self, mock_cmd, mock_sys):
        tool_config = self._make_tool_config()
        with mock.patch.dict(cli_install.TOOLS, {"test": tool_config}, clear=True):
            result = cli_install.install_tool("test")
        self.assertFalse(result)

    @mock.patch.object(cli_install.platform, "system", return_value="FreeBSD")
    @mock.patch.object(cli_install, "command_exists", return_value=False)
    def test_freebsd_with_port_dryrun(self, mock_cmd, mock_sys):
        tool_config = self._make_tool_config(freebsd_port="test-tool-port")
        with mock.patch.dict(cli_install.TOOLS, {"test": tool_config}, clear=True):
            result = cli_install.install_tool("test", dryrun=True)
        self.assertTrue(result)

    @mock.patch.object(cli_install.platform, "system", return_value="FreeBSD")
    @mock.patch.object(cli_install, "command_exists", return_value=False)
    @mock.patch.object(cli_install, "run_command")
    def test_freebsd_with_port_installs_via_pkg(self, mock_run, mock_cmd, mock_sys):
        tool_config = self._make_tool_config(freebsd_port="test-tool-port")
        with mock.patch.dict(cli_install.TOOLS, {"test": tool_config}, clear=True):
            result = cli_install.install_tool("test")
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ["sudo", "pkg", "install", "-y", "test-tool-port"], check=True
        )

    @mock.patch.object(cli_install.platform, "system", return_value="FreeBSD")
    @mock.patch.object(cli_install, "command_exists", return_value=False)
    @mock.patch.object(cli_install, "run_command")
    def test_freebsd_with_repo_passes_r_flag(self, mock_run, mock_cmd, mock_sys):
        tool_config = self._make_tool_config(
            freebsd_port="test-tool-port",
            freebsd_pkg_repo="FreeBSD-latest",
        )
        with mock.patch.dict(cli_install.TOOLS, {"test": tool_config}, clear=True):
            result = cli_install.install_tool("test")
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ["sudo", "pkg", "install", "-y", "-r", "FreeBSD-latest", "test-tool-port"],
            check=True,
        )


class TestExtractTarMember(unittest.TestCase):
    """Tests for extract_tar_member."""

    def test_falls_back_when_filter_keyword_not_supported(self):
        tarball_data = io.BytesIO()
        with tarfile.open(fileobj=tarball_data, mode="w:gz") as tf:
            file_data = b"hello world"
            info = tarfile.TarInfo("payload/file.txt")
            info.size = len(file_data)
            tf.addfile(info, io.BytesIO(file_data))

        tarball_data.seek(0)

        with tempfile.TemporaryDirectory() as td:
            with tarfile.open(fileobj=tarball_data, mode="r:gz") as tf:
                member = tf.getmembers()[0]
                original_extract = tf.extract

                def _extract_with_legacy_signature(*args, **kwargs):
                    if "filter" in kwargs:
                        raise TypeError("unexpected keyword argument 'filter'")
                    return original_extract(*args, **kwargs)

                with mock.patch.object(
                    tf, "extract", side_effect=_extract_with_legacy_signature
                ):
                    cli_install.extract_tar_member(tf, member, td)

            extracted = os.path.join(td, "payload", "file.txt")
            self.assertTrue(os.path.exists(extracted))


class TestInstallDirectDownloadDryrun(unittest.TestCase):
    """Tests for install_direct_download in dryrun mode."""

    @mock.patch.object(cli_install, "detect_os_arch", return_value=("linux", "x64"))
    @mock.patch.object(cli_install, "fetch_url")
    def test_dryrun_succeeds(self, mock_fetch, mock_os_arch):
        mock_fetch.return_value = (b"script content", None)

        tool_config = {
            "name": "Test Tool",
            "install_url": "https://example.com/install",
            "download_url_template": "https://example.com/{version}/{os}/{arch}/pkg.tar.gz",
            "install_dir": "/tmp/test-{version}",
            "bin_dir": "/tmp/test-bin",
            "symlinks": {"test": "test-bin"},
            "latest_version": "1.0.0",
        }

        result = cli_install.install_direct_download("test", tool_config, dryrun=True)
        self.assertTrue(result)


class TestInstallDirectDownload(unittest.TestCase):
    """Tests for install_direct_download in non-dryrun mode."""

    @mock.patch.object(cli_install, "detect_os_arch", return_value=("linux", "x64"))
    @mock.patch.object(cli_install, "fetch_url")
    def test_creates_missing_install_parent_directory(self, mock_fetch, mock_os_arch):
        tarball_data = io.BytesIO()
        with tarfile.open(fileobj=tarball_data, mode="w:gz") as tf:
            payload = b"#!/bin/sh\necho ok\n"
            info = tarfile.TarInfo("package/test-bin")
            info.mode = 0o755
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
        tarball_bytes = tarball_data.getvalue()

        mock_fetch.return_value = (tarball_bytes, None)

        tool_config = {
            "name": "Test Tool",
            "install_url": "https://example.com/install",
            "download_url_template": "https://example.com/{version}/{os}/{arch}/pkg.tar.gz",
            "install_dir": "/tmp/test-{version}",
            "bin_dir": "/tmp/test-bin",
            "symlinks": {"test": "test-bin"},
            "latest_version": "1.0.0",
        }

        with tempfile.TemporaryDirectory() as td:
            install_dir = os.path.join(td, "missing", "versions", "1.0.0")
            bin_dir = os.path.join(td, "bin")

            result = cli_install.install_direct_download(
                "test",
                tool_config,
                dryrun=False,
                install_dir_override=install_dir,
                bin_dir_override=bin_dir,
            )

            self.assertTrue(result)
            self.assertTrue(os.path.isdir(os.path.dirname(install_dir)))
            self.assertTrue(os.path.exists(os.path.join(install_dir, "test-bin")))
            self.assertTrue(os.path.islink(os.path.join(bin_dir, "test")))


class TestInstallTool(unittest.TestCase):
    """Tests for install_tool behavior."""

    def test_force_reinstalls_even_when_binary_exists(self):
        tool_config = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "npm",
            "npm_package": "test-tool",
            "next_steps": "Run test-tool",
        }

        with (
            mock.patch.dict(cli_install.TOOLS, {"test": tool_config}, clear=True),
            mock.patch.object(cli_install, "command_exists", return_value=True),
            mock.patch.object(
                cli_install.shutil, "which", return_value="/usr/local/bin/test-tool"
            ),
            mock.patch.object(cli_install, "run_command") as mock_run,
        ):
            result = cli_install.install_tool("test", force=True)

        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ["npm", "install", "-g", "test-tool"], check=True
        )

    def test_force_dryrun_reports_reinstall_when_binary_exists(self):
        tool_config = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "npm",
            "npm_package": "test-tool",
            "next_steps": "Run test-tool",
        }

        with (
            mock.patch.dict(cli_install.TOOLS, {"test": tool_config}, clear=True),
            mock.patch.object(cli_install, "command_exists", return_value=True),
            mock.patch.object(
                cli_install.shutil, "which", return_value="/usr/local/bin/test-tool"
            ),
            mock.patch.object(cli_install, "info") as mock_info,
            mock.patch.object(cli_install, "run_command") as mock_run,
        ):
            result = cli_install.install_tool("test", dryrun=True, force=True)

        self.assertTrue(result)
        mock_run.assert_not_called()
        mock_info.assert_any_call("[DRYRUN] Checking Test Tool...")
        mock_info.assert_any_call(
            "[DRYRUN] Would reinstall test-tool despite existing binary at "
            "/usr/local/bin/test-tool"
        )
        mock_info.assert_any_call("[DRYRUN] Would install npm package: test-tool")
