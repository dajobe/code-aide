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
    def test_dryrun_verifies_sha256(self, mock_fetch, mock_os_arch):
        script_content = (
            b"DOWNLOAD_URL=https://example.com/2026.01.01-abc123/pkg.tar.gz"
        )
        expected_sha256 = cli_install.hashlib.sha256(script_content).hexdigest()

        mock_fetch.return_value = (script_content, None)

        tool_config = {
            "name": "Test Tool",
            "install_url": "https://example.com/install",
            "install_sha256": expected_sha256,
            "download_url_template": "https://example.com/{version}/{os}/{arch}/pkg.tar.gz",
            "install_dir": "/tmp/test-{version}",
            "bin_dir": "/tmp/test-bin",
            "symlinks": {"test": "test-bin"},
            "latest_version": "1.0.0",
        }

        result = cli_install.install_direct_download("test", tool_config, dryrun=True)
        self.assertTrue(result)

    @mock.patch.object(cli_install, "fetch_url")
    def test_dryrun_fails_on_bad_sha256(self, mock_fetch):
        mock_fetch.return_value = (b"tampered script", None)

        tool_config = {
            "name": "Test Tool",
            "install_url": "https://example.com/install",
            "install_sha256": "0" * 64,
            "download_url_template": "https://example.com/{version}/{os}/{arch}/pkg.tar.gz",
            "install_dir": "/tmp/test-{version}",
            "bin_dir": "/tmp/test-bin",
            "symlinks": {"test": "test-bin"},
            "latest_version": "1.0.0",
        }

        result = cli_install.install_direct_download("test", tool_config, dryrun=True)
        self.assertFalse(result)


class TestInstallDirectDownload(unittest.TestCase):
    """Tests for install_direct_download in non-dryrun mode."""

    @mock.patch.object(cli_install, "detect_os_arch", return_value=("linux", "x64"))
    @mock.patch.object(cli_install, "fetch_url")
    def test_creates_missing_install_parent_directory(self, mock_fetch, mock_os_arch):
        script_content = b"echo install"
        expected_sha256 = cli_install.hashlib.sha256(script_content).hexdigest()

        tarball_data = io.BytesIO()
        with tarfile.open(fileobj=tarball_data, mode="w:gz") as tf:
            payload = b"#!/bin/sh\necho ok\n"
            info = tarfile.TarInfo("package/test-bin")
            info.mode = 0o755
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
        tarball_bytes = tarball_data.getvalue()

        def _fake_fetch(url, timeout=30):
            if url.endswith("/install"):
                return script_content, None
            return tarball_bytes, None

        mock_fetch.side_effect = _fake_fetch

        tool_config = {
            "name": "Test Tool",
            "install_url": "https://example.com/install",
            "install_sha256": expected_sha256,
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
