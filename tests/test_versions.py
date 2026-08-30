"""Unit tests for CLI versioning and update-check helpers."""

import unittest
from unittest import mock

from code_aide import config as code_aide_config
from code_aide import versions as cli_versions


class TestNormalizeVersion(unittest.TestCase):
    """Tests for normalize_version."""

    def test_strips_v_prefix(self):
        self.assertEqual(cli_versions.normalize_version("v1.2.3"), "1.2.3")

    def test_strips_multiple_v(self):
        self.assertEqual(cli_versions.normalize_version("vvv1.0"), "1.0")

    def test_no_prefix(self):
        self.assertEqual(cli_versions.normalize_version("1.2.3"), "1.2.3")

    def test_uppercase_v(self):
        self.assertEqual(cli_versions.normalize_version("V1.2.3"), "V1.2.3")

    def test_empty_string(self):
        self.assertEqual(cli_versions.normalize_version(""), "")

    def test_date_hash_format(self):
        self.assertEqual(
            cli_versions.normalize_version("2026.02.13-41ac335"),
            "2026.02.13-41ac335",
        )


class TestStatusVersionMatchesLatest(unittest.TestCase):
    """Tests for status_version_matches_latest."""

    def test_exact_match(self):
        self.assertTrue(cli_versions.status_version_matches_latest("0.29.5", "0.29.5"))

    def test_v_prefix_match(self):
        self.assertTrue(cli_versions.status_version_matches_latest("v0.29.5", "0.29.5"))

    def test_embedded_version(self):
        self.assertTrue(
            cli_versions.status_version_matches_latest(
                "Claude Code 2.1.50 (abc123)", "2.1.50"
            )
        )

    def test_tool_name_prefix(self):
        self.assertTrue(
            cli_versions.status_version_matches_latest("gemini 0.29.5", "0.29.5")
        )

    def test_codex_prefix(self):
        self.assertTrue(
            cli_versions.status_version_matches_latest("codex-cli 0.104.0", "0.104.0")
        )

    def test_date_hash_format(self):
        self.assertTrue(
            cli_versions.status_version_matches_latest(
                "2026.02.13-41ac335", "2026.02.13-41ac335"
            )
        )

    def test_mismatch(self):
        self.assertFalse(cli_versions.status_version_matches_latest("0.29.6", "0.29.5"))

    def test_embedded_mismatch(self):
        self.assertFalse(
            cli_versions.status_version_matches_latest(
                "Claude Code 2.1.51 (abc)", "2.1.50"
            )
        )

    def test_empty_status(self):
        self.assertFalse(cli_versions.status_version_matches_latest("", "1.0.0"))

    def test_empty_latest(self):
        self.assertFalse(cli_versions.status_version_matches_latest("1.0.0", ""))

    def test_none_status(self):
        self.assertFalse(cli_versions.status_version_matches_latest(None, "1.0.0"))

    def test_none_latest(self):
        self.assertFalse(cli_versions.status_version_matches_latest("1.0.0", None))


class TestExtractVersionFromString(unittest.TestCase):
    """Tests for extract_version_from_string."""

    def test_bare_version(self):
        self.assertEqual(cli_versions.extract_version_from_string("0.29.6"), "0.29.6")

    def test_v_prefix(self):
        self.assertEqual(cli_versions.extract_version_from_string("v0.29.6"), "0.29.6")

    def test_tool_name_prefix(self):
        self.assertEqual(
            cli_versions.extract_version_from_string("gemini 0.29.5"),
            "0.29.5",
        )

    def test_claude_format(self):
        self.assertEqual(
            cli_versions.extract_version_from_string("Claude Code 2.1.50 (abc123)"),
            "2.1.50",
        )

    def test_codex_format(self):
        self.assertEqual(
            cli_versions.extract_version_from_string("codex-cli 0.104.0"),
            "0.104.0",
        )

    def test_date_hash_format(self):
        self.assertEqual(
            cli_versions.extract_version_from_string("2026.02.13-41ac335"),
            "2026.02.13-41ac335",
        )

    def test_empty_string(self):
        self.assertIsNone(cli_versions.extract_version_from_string(""))

    def test_none(self):
        self.assertIsNone(cli_versions.extract_version_from_string(None))

    def test_no_version(self):
        self.assertIsNone(cli_versions.extract_version_from_string("no version here"))

    def test_whitespace(self):
        self.assertEqual(
            cli_versions.extract_version_from_string("  1.2.3  "),
            "1.2.3",
        )

    def test_amp_version(self):
        self.assertEqual(
            cli_versions.extract_version_from_string(
                "0.0.1771863250-g045394 (released 2026-02-23)"
            ),
            "0.0.1771863250-g045394",
        )


class TestVersionIsNewer(unittest.TestCase):
    """Tests for version_is_newer."""

    def test_patch_newer(self):
        self.assertTrue(cli_versions.version_is_newer("0.29.6", "0.29.5"))

    def test_patch_older(self):
        self.assertFalse(cli_versions.version_is_newer("0.29.5", "0.29.6"))

    def test_equal(self):
        self.assertFalse(cli_versions.version_is_newer("0.29.5", "0.29.5"))

    def test_minor_newer(self):
        self.assertTrue(cli_versions.version_is_newer("0.30.0", "0.29.5"))

    def test_major_newer(self):
        self.assertTrue(cli_versions.version_is_newer("1.0.0", "0.99.99"))

    def test_minor_older(self):
        self.assertFalse(cli_versions.version_is_newer("0.28.0", "0.29.5"))

    def test_two_component(self):
        self.assertTrue(cli_versions.version_is_newer("1.1", "1.0"))

    def test_four_component(self):
        self.assertTrue(cli_versions.version_is_newer("1.2.3.4", "1.2.3.3"))

    def test_large_numbers(self):
        self.assertTrue(
            cli_versions.version_is_newer("0.0.1771900501", "0.0.1771863250")
        )

    def test_date_versions(self):
        self.assertTrue(
            cli_versions.version_is_newer("2026.02.14-abc123", "2026.02.13-abc122")
        )


class TestFormatVersionManifestUrl(unittest.TestCase):
    """Tests for platform-specific release manifest URLs."""

    @mock.patch.object(cli_versions.platform, "machine", return_value="arm64")
    @mock.patch.object(cli_versions.platform, "system", return_value="Darwin")
    def test_formats_macos_arm64(self, _system, _machine):
        result = cli_versions.format_version_manifest_url(
            "https://example.com/manifests/{platform}.json"
        )
        self.assertEqual(result, "https://example.com/manifests/darwin_arm64.json")

    @mock.patch.object(cli_versions.platform, "machine", return_value="x86_64")
    @mock.patch.object(cli_versions.platform, "system", return_value="Linux")
    def test_formats_linux_amd64(self, _system, _machine):
        result = cli_versions.format_version_manifest_url(
            "https://example.com/manifests/{platform}.json"
        )
        self.assertEqual(result, "https://example.com/manifests/linux_amd64.json")

    @mock.patch.object(cli_versions.platform, "system", return_value="Windows")
    def test_rejects_unsupported_os(self, _system):
        with self.assertRaises(ValueError):
            cli_versions.format_version_manifest_url(
                "https://example.com/manifests/{platform}.json"
            )


class TestParseHttpDate(unittest.TestCase):
    """Tests for parse_http_date."""

    def test_valid_rfc2822(self):
        self.assertEqual(
            cli_versions.parse_http_date("Thu, 20 Feb 2026 12:00:00 GMT"),
            "2026-02-20",
        )

    def test_none(self):
        self.assertIsNone(cli_versions.parse_http_date(None))

    def test_empty(self):
        self.assertIsNone(cli_versions.parse_http_date(""))

    def test_invalid(self):
        self.assertIsNone(cli_versions.parse_http_date("not a date"))


class TestParseIsoDate(unittest.TestCase):
    """Tests for parse_iso_date."""

    def test_iso_with_z(self):
        self.assertEqual(
            cli_versions.parse_iso_date("2026-02-20T12:00:00Z"),
            "2026-02-20",
        )

    def test_iso_with_offset(self):
        self.assertEqual(
            cli_versions.parse_iso_date("2026-02-20T12:00:00+00:00"),
            "2026-02-20",
        )

    def test_none(self):
        self.assertIsNone(cli_versions.parse_iso_date(None))

    def test_empty(self):
        self.assertIsNone(cli_versions.parse_iso_date(""))

    def test_invalid(self):
        self.assertIsNone(cli_versions.parse_iso_date("not a date"))


class TestFormatCheckBackend(unittest.TestCase):
    """Tests for format_check_backend."""

    def test_npm_backend_label(self):
        self.assertEqual(cli_versions.format_check_backend("npm"), "npm-registry")

    def test_script_backend_label(self):
        self.assertEqual(cli_versions.format_check_backend("script"), "script-url")

    def test_passthrough_unknown(self):
        self.assertEqual(cli_versions.format_check_backend("custom"), "custom")


class TestExtractScriptDate(unittest.TestCase):
    """Tests for extract_script_date."""

    def test_epoch_in_version(self):
        self.assertEqual(
            cli_versions.extract_script_date("v0.0.1772022876-ga1dd2c", None),
            "2026-02-25",
        )

    def test_epoch_preferred_over_http_header(self):
        self.assertEqual(
            cli_versions.extract_script_date(
                "v0.0.1772022876-ga1dd2c",
                "Mon, 24 Feb 2026 00:00:00 GMT",
            ),
            "2026-02-25",
        )

    def test_date_based_version(self):
        self.assertEqual(
            cli_versions.extract_script_date("2026.02.13-41ac335", None),
            "2026-02-13",
        )

    def test_falls_back_to_http_header(self):
        self.assertEqual(
            cli_versions.extract_script_date("v1.2.3", "Tue, 25 Feb 2026 12:34:56 GMT"),
            "2026-02-25",
        )

    def test_no_version_uses_http_header(self):
        self.assertEqual(
            cli_versions.extract_script_date(None, "Tue, 25 Feb 2026 12:34:56 GMT"),
            "2026-02-25",
        )

    def test_no_info_returns_none(self):
        self.assertIsNone(cli_versions.extract_script_date(None, None))

    def test_non_date_version_no_header_returns_none(self):
        self.assertIsNone(cli_versions.extract_script_date("v1.2.3", None))


class TestExtractScriptVersion(unittest.TestCase):
    """Tests for extract_script_version (cursor version parsing)."""

    _CURSOR_CONFIG = {"version_extract_pattern": r"\d{4}\.\d{2}\.\d{2}(?:-[0-9a-f]+)+"}

    def test_cursor_legacy_date_hash_format(self):
        script = b'DOWNLOAD_URL="https://downloads.cursor.com/lab/2026.03.20-44cb435/${OS}/${ARCH}/agent-cli-package.tar.gz"'
        self.assertEqual(
            cli_versions.extract_script_version("cursor", self._CURSOR_CONFIG, script),
            "2026.03.20-44cb435",
        )

    def test_cursor_date_time_hash_format(self):
        # Cursor extended the version with a build time (HH-MM-SS). The whole
        # string must be captured or the download URL path 403s.
        script = b'DOWNLOAD_URL="https://downloads.cursor.com/lab/2026.06.12-19-59-36-f6aba9a/${OS}/${ARCH}/agent-cli-package.tar.gz"'
        self.assertEqual(
            cli_versions.extract_script_version("cursor", self._CURSOR_CONFIG, script),
            "2026.06.12-19-59-36-f6aba9a",
        )

    def test_cursor_no_version_returns_none(self):
        self.assertIsNone(
            cli_versions.extract_script_version(
                "cursor", self._CURSOR_CONFIG, b"echo hello"
            )
        )

    def test_bundled_cursor_pattern_comes_from_config(self):
        bundled = code_aide_config.load_bundled_tools()["tools"]["cursor"]
        script = b'VERSION="9.9.9"\nDOWNLOAD_URL="https://downloads.cursor.com/lab/2026.06.12-19-59-36-f6aba9a/x"'
        self.assertEqual(
            cli_versions.extract_script_version("cursor", bundled, script),
            "2026.06.12-19-59-36-f6aba9a",
        )

    def test_invalid_pattern_falls_back_to_generic_extraction(self):
        config = {"version_extract_pattern": "([unclosed"}
        script = b'VERSION="1.2.3"\n'
        self.assertEqual(
            cli_versions.extract_script_version("tool", config, script),
            "1.2.3",
        )

    def test_non_capturing_pattern_returns_whole_match(self):
        config = {"version_extract_pattern": r"\d+\.\d+\.\d+"}
        self.assertEqual(
            cli_versions.extract_script_version("tool", config, b"version 1.2.3 here"),
            "1.2.3",
        )

    def test_skips_shell_variable_placeholder(self):
        # The amp script declares AMP_VERSION="${AMP_VERSION:-}"; the literal
        # placeholder must not be returned as a version.
        script = b'AMP_VERSION="${AMP_VERSION:-}"\n'
        self.assertIsNone(cli_versions.extract_script_version("amp", {}, script))

    def test_returns_real_version_after_placeholder(self):
        script = b'AMP_VERSION="${AMP_VERSION:-}"\nVERSION="1.2.3"\n'
        self.assertEqual(
            cli_versions.extract_script_version("amp", {}, script),
            "1.2.3",
        )

    def test_plain_version_assignment(self):
        self.assertEqual(
            cli_versions.extract_script_version("amp", {}, b'VERSION="2.0.1"\n'),
            "2.0.1",
        )

    @mock.patch.object(
        cli_versions,
        "format_version_manifest_url",
        return_value="https://example.com/manifests/darwin_arm64.json",
    )
    @mock.patch.object(cli_versions, "fetch_url")
    def test_reads_version_from_json_manifest(self, mock_fetch, mock_format):
        mock_fetch.return_value = (b'{"version": "1.1.1"}', None)

        result = cli_versions.extract_script_version(
            "antigravity",
            {
                "version_manifest_url_template": (
                    "https://example.com/manifests/{platform}.json"
                )
            },
            b"#!/bin/bash\n",
        )

        self.assertEqual(result, "1.1.1")
        mock_format.assert_called_once()
        mock_fetch.assert_called_once_with(
            "https://example.com/manifests/darwin_arm64.json"
        )

    @mock.patch.object(cli_versions, "fetch_url")
    def test_invalid_manifest_falls_back_to_script(self, mock_fetch):
        mock_fetch.return_value = (b"not json", None)

        result = cli_versions.extract_script_version(
            "antigravity",
            {
                "version_manifest_url_template": (
                    "https://example.com/manifests/{platform}.json"
                )
            },
            b'VERSION="1.0.0"\n',
        )

        self.assertEqual(result, "1.0.0")


class TestFetchUrl(unittest.TestCase):
    """Tests for fetch_url network fetch behavior."""

    @staticmethod
    def _response(content=b"payload", last_modified="Tue, 25 Aug 2026 10:00:00 GMT"):
        response = mock.Mock()
        response.read.return_value = content
        response.headers = {"Last-Modified": last_modified}
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=False)
        return response

    def test_returns_content_and_last_modified(self):
        with mock.patch.object(
            cli_versions.urllib.request,
            "urlopen",
            return_value=self._response(content=b"abc"),
        ) as mock_urlopen:
            content, last_modified = cli_versions.fetch_url("https://example.com/x")
        self.assertEqual(content, b"abc")
        self.assertEqual(last_modified, "Tue, 25 Aug 2026 10:00:00 GMT")
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "https://example.com/x")
        self.assertEqual(mock_urlopen.call_args[1]["timeout"], 30)

    def test_sends_code_aide_user_agent(self):
        with mock.patch.object(
            cli_versions.urllib.request, "urlopen", return_value=self._response()
        ) as mock_urlopen:
            cli_versions.fetch_url("https://example.com/x")
        request = mock_urlopen.call_args[0][0]
        self.assertIn("code-aide/", request.headers.get("User-agent", ""))

    def test_last_modified_is_none_when_header_absent(self):
        with mock.patch.object(
            cli_versions.urllib.request,
            "urlopen",
            return_value=self._response(last_modified=None),
        ):
            content, last_modified = cli_versions.fetch_url("https://example.com/x")
        self.assertEqual(content, b"payload")
        self.assertIsNone(last_modified)

    def test_custom_timeout_is_passed(self):
        with mock.patch.object(
            cli_versions.urllib.request, "urlopen", return_value=self._response()
        ) as mock_urlopen:
            cli_versions.fetch_url("https://example.com/x", timeout=5)
        self.assertEqual(mock_urlopen.call_args[1]["timeout"], 5)
