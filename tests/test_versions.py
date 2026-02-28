"""Unit tests for CLI versioning and update-check helpers."""

import unittest

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


class TestFormatCheckBackendSelfManaged(unittest.TestCase):
    """Tests for format_check_backend with self_managed type."""

    def test_self_managed_uses_npm_registry(self):
        self.assertEqual(
            cli_versions.format_check_backend("self_managed"),
            "npm-registry",
        )


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
