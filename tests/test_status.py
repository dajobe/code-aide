"""Unit tests for status-rendering helpers."""

import unittest

from code_aide import status as cli_status


class TestPrintSystemVersionStatus(unittest.TestCase):
    """Tests for print_system_version_status."""

    def _capture(self, cli_version, latest_version, pkg_info):
        from io import StringIO
        import contextlib

        buf = StringIO()
        with contextlib.redirect_stdout(buf):
            cli_status.print_system_version_status(
                cli_version, latest_version, pkg_info
            )
        return buf.getvalue()

    def test_installed_matches_package_shows_up_to_date(self):
        output = self._capture(
            "2.1.50 (Claude Code)",
            "2.1.52",
            {
                "package": "dev-util/claude-code",
                "installed_version": "2.1.50",
                "available_version": "2.1.50",
                "available_date": "2026-02-24",
            },
        )
        self.assertIn("up to date", output)
        self.assertNotIn("package has", output)
        self.assertIn("upstream: 2.1.52", output)

    def test_installed_behind_package_shows_package_version(self):
        output = self._capture(
            "2.1.49 (Claude Code)",
            "2.1.52",
            {
                "package": "dev-util/claude-code",
                "installed_version": "2.1.49",
                "available_version": "2.1.50",
                "available_date": "2026-02-24",
            },
        )
        self.assertIn("package has 2.1.50", output)

    def test_package_matches_upstream_no_upstream_note(self):
        output = self._capture(
            "2.1.52 (Claude Code)",
            "2.1.52",
            {
                "package": "dev-util/claude-code",
                "installed_version": "2.1.52",
                "available_version": "2.1.52",
                "available_date": "2026-02-25",
            },
        )
        self.assertIn("up to date", output)
        self.assertNotIn("upstream:", output)

    def test_no_package_info_falls_back(self):
        output = self._capture(
            "2.1.50 (Claude Code)",
            "2.1.52",
            {
                "package": None,
                "installed_version": None,
                "available_version": None,
                "available_date": None,
            },
        )
        self.assertIn("2.1.50", output)
        self.assertNotIn("Packaged:", output)
