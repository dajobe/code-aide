"""Tests for release-asset helpers used by direct-download tools."""

import hashlib
import io
import json
import os
import tarfile
import tempfile
import unittest
from unittest import mock

from code_aide import app_bundle, constants
from code_aide import detection as cli_detection
from code_aide import install as cli_install
from code_aide import release_assets
from code_aide import versions as cli_versions

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


class TestParseSha256sums(unittest.TestCase):
    """Tests for parse_sha256sums."""

    def test_text_and_binary_mode_lines(self):
        text = f"{DIGEST_A}  one.tar.gz\n{DIGEST_B} *two.tar.gz\n"
        self.assertEqual(release_assets.parse_sha256sums(text, "one.tar.gz"), DIGEST_A)
        self.assertEqual(release_assets.parse_sha256sums(text, "two.tar.gz"), DIGEST_B)

    def test_missing_file_and_malformed_lines(self):
        text = f"garbage\nshort  one.tar.gz\n{DIGEST_A}  other.tar.gz\n"
        self.assertIsNone(release_assets.parse_sha256sums(text, "one.tar.gz"))


class TestMarkersAndLaunchers(unittest.TestCase):
    """Tests for install markers, launcher records and platform checks."""

    def test_unsupported_platform_message(self):
        cfg = {"unsupported_platforms": {"darwin-x64": "no Intel build"}}
        self.assertEqual(
            release_assets.unsupported_platform_message(cfg, "darwin", "x64"),
            "no Intel build",
        )
        self.assertIsNone(
            release_assets.unsupported_platform_message(cfg, "darwin", "arm64")
        )
        self.assertIsNone(release_assets.unsupported_platform_message({}, "a", "b"))

    def test_marker_round_trip(self):
        cfg = {"install_complete_marker": ".install-complete"}
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(release_assets.install_marker_matches(cfg, td, "1.0"))
            release_assets.write_install_marker(cfg, td, "1.0")
            with open(os.path.join(td, ".install-complete"), encoding="utf-8") as f:
                self.assertEqual(f.read(), "1.0\n")
            self.assertTrue(release_assets.install_marker_matches(cfg, td, "1.0"))
            self.assertFalse(release_assets.install_marker_matches(cfg, td, "2.0"))
            self.assertFalse(release_assets.install_marker_matches({}, td, "1.0"))

    def test_record_launchers_appends_once(self):
        with tempfile.TemporaryDirectory() as td:
            td = os.path.realpath(td)
            record = os.path.join(td, "runtime", "launchers")
            cfg = {"launcher_record_file": record}
            link = os.path.join(td, "bin", "example")
            release_assets.record_launchers(cfg, [link])
            release_assets.record_launchers(cfg, [link])
            with open(record, encoding="utf-8") as f:
                lines = [line for line in f.read().splitlines() if line]
            self.assertEqual(lines, [link])


class TestCheckGithubReleaseTool(unittest.TestCase):
    """Tests for check_github_release_tool via check_script_tool."""

    CFG = {"install_type": "direct_download", "github_release_repo": "o/r"}

    def _release(self, tag="v0.1.7"):
        body = {"tag_name": tag, "published_at": "2026-11-04T06:39:38Z"}
        return (json.dumps(body).encode(), None)

    @mock.patch.object(cli_versions, "fetch_url")
    def test_new_version_is_changed(self, mock_fetch):
        mock_fetch.return_value = self._release()
        result = cli_versions.check_script_tool("example", dict(self.CFG))
        self.assertEqual(result["version"], "0.1.7")
        self.assertEqual(result["date"], "2026-11-04")
        self.assertEqual(result["status"], "changed")
        self.assertIsNone(result["update"])
        self.assertEqual(
            mock_fetch.call_args[0][0],
            "https://api.github.com/repos/o/r/releases/latest",
        )

    @mock.patch.object(cli_versions, "fetch_url")
    def test_cached_version_is_ok(self, mock_fetch):
        mock_fetch.return_value = self._release()
        cfg = dict(self.CFG, latest_version="0.1.7")
        self.assertEqual(cli_versions.check_script_tool("example", cfg)["status"], "ok")

    @mock.patch.object(cli_versions, "fetch_url", side_effect=OSError("down"))
    def test_fetch_error(self, mock_fetch):
        result = cli_versions.check_script_tool("example", dict(self.CFG))
        self.assertEqual(result["status"], "error")


def _make_tarball():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        payload = b"#!/bin/sh\necho ok\n"
        member = tarfile.TarInfo("example-1.0.0-linux-x64/example")
        member.size = len(payload)
        member.mode = 0o755
        tf.addfile(member, io.BytesIO(payload))
    return buf.getvalue()


@mock.patch.object(cli_install, "detect_os_arch", return_value=("linux", "x64"))
class TestUpstreamChecksumInstall(unittest.TestCase):
    """Tests for install_direct_download with a publisher checksum file."""

    def _config(self, td):
        base = "https://example.com/v{version}"
        return {
            "name": "Example",
            "latest_version": "1.0.0",
            "download_url_template": base + "/example-{version}-{os}-{arch}.tar.gz",
            "checksums_url_template": base + "/SHA256SUMS",
            "install_dir": os.path.join(td, "versions", "{version}"),
            "install_complete_marker": ".install-complete",
            "launcher_record_file": os.path.join(td, "launchers"),
            "bin_dir": os.path.join(td, "bin"),
            "symlinks": {"example": "example"},
            # A stale recorded checksum must not override the publisher's.
            "download_sha256": "0" * 64,
        }

    def _fetch(self, tarball, sums):
        def fake_fetch(url, timeout=30):
            if url.endswith("SHA256SUMS"):
                return (sums.encode(), None)
            return (tarball, None)

        return fake_fetch

    def test_matching_upstream_checksum_installs(self, _os_arch):
        tarball = _make_tarball()
        sums = (
            f"{hashlib.sha256(tarball).hexdigest()}  example-1.0.0-linux-x64.tar.gz\n"
        )
        with tempfile.TemporaryDirectory() as td:
            cfg = self._config(td)
            with mock.patch.object(
                cli_install, "fetch_url", side_effect=self._fetch(tarball, sums)
            ):
                self.assertTrue(cli_install.install_direct_download("example", cfg))
            version_dir = os.path.join(td, "versions", "1.0.0")
            self.assertTrue(os.path.isfile(os.path.join(version_dir, "example")))
            with open(os.path.join(version_dir, ".install-complete")) as f:
                self.assertEqual(f.read(), "1.0.0\n")
            self.assertEqual(
                os.readlink(os.path.join(td, "bin", "example")),
                os.path.join(version_dir, "example"),
            )
            with open(os.path.join(td, "launchers")) as f:
                self.assertIn(
                    os.path.join(os.path.realpath(td), "bin", "example"), f.read()
                )

    def test_mismatched_upstream_checksum_fails(self, _os_arch):
        tarball = _make_tarball()
        sums = f"{DIGEST_A}  example-1.0.0-linux-x64.tar.gz\n"
        with tempfile.TemporaryDirectory() as td:
            cfg = self._config(td)
            with mock.patch.object(
                cli_install, "fetch_url", side_effect=self._fetch(tarball, sums)
            ):
                self.assertFalse(cli_install.install_direct_download("example", cfg))
            self.assertFalse(os.path.exists(os.path.join(td, "versions", "1.0.0")))

    def test_unlisted_asset_fails(self, _os_arch):
        with tempfile.TemporaryDirectory() as td:
            cfg = self._config(td)
            with mock.patch.object(
                cli_install,
                "fetch_url",
                side_effect=self._fetch(_make_tarball(), f"{DIGEST_A}  other\n"),
            ):
                self.assertFalse(cli_install.install_direct_download("example", cfg))

    def test_existing_marker_skips_download(self, _os_arch):
        with tempfile.TemporaryDirectory() as td:
            cfg = self._config(td)
            version_dir = os.path.join(td, "versions", "1.0.0")
            os.makedirs(version_dir)
            release_assets.write_install_marker(cfg, version_dir, "1.0.0")
            with (
                mock.patch.object(cli_install, "fetch_url") as mock_fetch,
                mock.patch.object(cli_install, "success") as mock_success,
            ):
                self.assertTrue(cli_install.install_direct_download("example", cfg))
                mock_fetch.assert_not_called()
            self.assertTrue(os.path.islink(os.path.join(td, "bin", "example")))
            # install_tool reports the overall success, not this helper.
            mock_success.assert_not_called()

    def test_fetch_download_checksum_reads_sums_file(self, _os_arch):
        with tempfile.TemporaryDirectory() as td:
            cfg = self._config(td)
            sums = f"{DIGEST_B}  example-1.0.0-linux-x64.tar.gz\n"
            with mock.patch.object(
                cli_install, "fetch_url", side_effect=self._fetch(b"", sums)
            ) as mock_fetch:
                self.assertEqual(cli_install.fetch_download_checksum(cfg), DIGEST_B)
            mock_fetch.assert_called_once()


class TestUnsupportedPlatformInstall(unittest.TestCase):
    """install_direct_download refuses configured unsupported platforms."""

    @mock.patch.object(cli_install, "fetch_url")
    @mock.patch.object(cli_install, "detect_os_arch", return_value=("darwin", "x64"))
    def test_refuses_without_download(self, _os_arch, mock_fetch):
        cfg = dict(constants.TOOLS["t3code"], latest_version="0.1.7")
        self.assertFalse(cli_install.install_direct_download("t3code", cfg))
        mock_fetch.assert_not_called()
        self.assertIsNone(cli_install.fetch_download_checksum(cfg))


class TestDesktopCliDetection(unittest.TestCase):
    """Tests for detecting a command provided by a desktop app's shim."""

    def _detect(self, td, app_line, cask_installed, cask_opts=""):
        shim = os.path.join(td, "example")
        with open(shim, "w", encoding="utf-8") as f:
            f.write(f'#!/bin/sh\n{app_line}\nexec "$app" "$@"\n')
        tools = {
            "example": {
                "name": "Example",
                "command": "example",
                "install_type": "direct_download",
                "brew_cask": "example",
                "desktop_cli_shim": shim,
            },
            # The app tool names the bundle the cask installs.
            "example-app": {
                "name": "Example app",
                "command": "example-app",
                "install_type": "app_bundle",
                "brew_cask": "example",
                "app_bundle_name": "Example.app",
            },
        }
        with (
            mock.patch.object(cli_detection, "TOOLS", tools),
            mock.patch.object(cli_detection.shutil, "which", return_value=shim),
            mock.patch.object(
                app_bundle, "is_brew_cask_installed", return_value=cask_installed
            ),
            mock.patch.dict(os.environ, {"HOMEBREW_CASK_OPTS": cask_opts}),
        ):
            return cli_detection.detect_install_method("example")

    def test_cask_app_detected_as_brew_cask(self):
        app = "app='/Applications/Example.app/Contents/MacOS/Example'"
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                self._detect(td, app, True),
                {"method": "brew_cask", "detail": "example"},
            )

    def test_user_appdir_cask_detected_as_brew_cask(self):
        bundle = os.path.expanduser("~/Applications/Example.app")
        app = f"app='{bundle}/Contents/MacOS/Example'"
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                self._detect(td, app, True, "--appdir=~/Applications"),
                {"method": "brew_cask", "detail": "example"},
            )

    def test_other_bundle_in_cask_appdir_is_desktop_app(self):
        # A nightly build next to the cask's app is not the cask's.
        bundle = "/Applications/Example Nightly.app"
        app = f"app='{bundle}/Contents/MacOS/Example'"
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                self._detect(td, app, True),
                {"method": "system", "detail": bundle},
            )

    def test_copy_outside_cask_appdir_is_desktop_app(self):
        # The cask installs into /Applications; a manual copy in
        # ~/Applications is not the cask's even though the cask exists.
        bundle = os.path.expanduser("~/Applications/Example.app")
        app = f"app='{bundle}/Contents/MacOS/Example'"
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                self._detect(td, app, True),
                {"method": "system", "detail": bundle},
            )

    def test_app_dir_without_cask_is_desktop_app(self):
        app = "app='/Applications/Example.app/Contents/MacOS/Example'"
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                self._detect(td, app, False)["method"],
                "system",
            )

    def test_non_cask_app_detected_as_desktop_app(self):
        bundle = "/Users/x/opt/Example.app"
        app = f"app='{bundle}/Contents/MacOS/Example'"
        with tempfile.TemporaryDirectory() as td:
            info = self._detect(td, app, True)
            self.assertEqual(info, {"method": "system", "detail": bundle})
            self.assertEqual(
                cli_detection.format_install_method(info["method"], info["detail"]),
                f"desktop app ({bundle})",
            )

    def test_is_brew_cask_installed_checks_caskroom(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "Caskroom", "example"))
            with mock.patch.dict(os.environ, {"HOMEBREW_PREFIX": td}):
                self.assertTrue(cli_detection.is_brew_cask_installed("example"))
                self.assertFalse(cli_detection.is_brew_cask_installed("nope-zzz"))


if __name__ == "__main__":
    unittest.main()
