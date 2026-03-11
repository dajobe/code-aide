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

    def test_packaged_newer_than_config_no_upstream_note(self):
        """When packaged version is newer than config latest, do not show upstream."""
        output = self._capture(
            "2.1.60 (Claude Code)",
            "2.1.52",
            {
                "package": "dev-util/claude-code",
                "installed_version": "2.1.60",
                "available_version": "2.1.60",
                "available_date": "2026-03-01",
            },
        )
        self.assertIn("up to date", output)
        self.assertIn("Packaged:     2.1.60", output)
        self.assertNotIn("upstream:", output)


class TestPrintBrewVersionStatus(unittest.TestCase):
    """Tests for print_brew_version_status."""

    def _capture(self, cli_version, latest_version, pkg_info):
        from io import StringIO
        import contextlib

        buf = StringIO()
        with contextlib.redirect_stdout(buf):
            cli_status.print_brew_version_status(cli_version, latest_version, pkg_info)
        return buf.getvalue()

    def test_packaged_newer_than_config_no_upstream_note(self):
        """When Homebrew packaged version is newer than config, do not show upstream."""
        output = self._capture(
            "codex-cli 0.114.0",
            "0.112.0",
            {
                "package": "codex",
                "installed_version": "0.114.0",
                "available_version": "0.114.0",
                "outdated": False,
            },
        )
        self.assertIn("up to date", output)
        self.assertIn("Packaged:     0.114.0 (codex)", output)
        self.assertNotIn("upstream:", output)
