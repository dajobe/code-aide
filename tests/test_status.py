"""Unit tests for status-rendering helpers."""

import unittest
from unittest import mock

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


class TestToolUpgradeEvaluator(unittest.TestCase):
    """Tests for enum-backed tool upgrade evaluation."""

    def _evaluate(
        self,
        tool_config,
        *,
        status,
        install_info,
        package_info=None,
        tool_path=None,
    ):
        return cli_status.ToolUpgradeEvaluator(
            "test",
            tool_config,
            status=status,
            install_info=install_info,
            package_info=package_info,
            tool_path=tool_path,
        ).evaluate()

    def test_catalog_match_is_current(self):
        assessment = self._evaluate(
            {
                "name": "Test Tool",
                "command": "test-tool",
                "install_type": "script",
                "latest_version": "1.0.0",
            },
            status={"installed": True, "version": "1.0.0", "errors": []},
            install_info={"method": "script", "detail": None},
        )
        self.assertEqual(assessment.decision, cli_status.UpgradeDecision.CURRENT)
        self.assertEqual(
            assessment.version_state, cli_status.VersionDisplayState.UP_TO_DATE
        )
        self.assertFalse(assessment.actionable_by_upgrade)

    def test_installed_newer_than_catalog_is_current(self):
        assessment = self._evaluate(
            {
                "name": "Test Tool",
                "command": "test-tool",
                "install_type": "script",
                "latest_version": "1.0.0",
            },
            status={"installed": True, "version": "2.0.0", "errors": []},
            install_info={"method": "script", "detail": None},
        )
        self.assertEqual(assessment.decision, cli_status.UpgradeDecision.CURRENT)
        self.assertEqual(
            assessment.version_state, cli_status.VersionDisplayState.UP_TO_DATE
        )

    def test_catalog_older_is_upgrade(self):
        assessment = self._evaluate(
            {
                "name": "Test Tool",
                "command": "test-tool",
                "install_type": "script",
                "latest_version": "2.0.0",
            },
            status={"installed": True, "version": "1.0.0", "errors": []},
            install_info={"method": "script", "detail": None},
        )
        self.assertEqual(assessment.decision, cli_status.UpgradeDecision.UPGRADE)
        self.assertEqual(
            assessment.version_state, cli_status.VersionDisplayState.OUTDATED
        )
        self.assertTrue(assessment.actionable_by_upgrade)

    def test_brew_outdated_is_upgrade(self):
        assessment = self._evaluate(
            {
                "name": "Brew Tool",
                "command": "brewtool",
                "install_type": "script",
                "latest_version": "9.9.9",
            },
            status={"installed": True, "version": "1.0.0", "errors": []},
            install_info={"method": "brew_formula", "detail": "brewtool"},
            package_info={
                "package": "brewtool",
                "installed_version": "1.0.0",
                "available_version": "2.0.0",
                "outdated": True,
            },
        )
        self.assertEqual(assessment.decision, cli_status.UpgradeDecision.UPGRADE)
        self.assertEqual(
            assessment.version_state, cli_status.VersionDisplayState.OUTDATED
        )

    def test_brew_current_is_current(self):
        assessment = self._evaluate(
            {
                "name": "Brew Tool",
                "command": "brewtool",
                "install_type": "script",
                "latest_version": "9.9.9",
            },
            status={"installed": True, "version": "1.0.0", "errors": []},
            install_info={"method": "brew_formula", "detail": "brewtool"},
            package_info={
                "package": "brewtool",
                "installed_version": "1.0.0",
                "available_version": "1.0.0",
                "outdated": False,
            },
        )
        self.assertEqual(assessment.decision, cli_status.UpgradeDecision.CURRENT)
        self.assertEqual(
            assessment.version_state, cli_status.VersionDisplayState.UP_TO_DATE
        )
        self.assertFalse(assessment.actionable_by_upgrade)

    def test_system_install_is_package_managed(self):
        assessment = self._evaluate(
            {
                "name": "System Tool",
                "command": "sys-tool",
                "install_type": "script",
                "latest_version": "3.0.0",
            },
            status={"installed": True, "version": "2.0.0", "errors": []},
            install_info={"method": "system", "detail": "/usr/bin/sys-tool"},
            package_info={
                "package": "dev-util/sys-tool",
                "installed_version": "2.0.0",
                "available_version": "2.0.0",
                "available_date": "2026-03-01",
            },
        )
        self.assertEqual(
            assessment.decision, cli_status.UpgradeDecision.PACKAGE_MANAGED
        )
        self.assertEqual(
            assessment.version_state, cli_status.VersionDisplayState.UP_TO_DATE
        )
        self.assertFalse(assessment.actionable_by_upgrade)

    def test_deprecated_install_is_migration(self):
        assessment = self._evaluate(
            {
                "name": "Test Tool",
                "command": "test-tool",
                "install_type": "script",
                "latest_version": "1.0.0",
            },
            status={"installed": True, "version": "1.0.0", "errors": []},
            install_info={"method": "npm", "detail": "test-tool"},
        )
        self.assertEqual(assessment.decision, cli_status.UpgradeDecision.MIGRATION)
        self.assertEqual(
            assessment.version_state, cli_status.VersionDisplayState.UP_TO_DATE
        )
        self.assertTrue(assessment.actionable_by_upgrade)

    def test_missing_cli_version_is_unknown(self):
        assessment = self._evaluate(
            {
                "name": "Test Tool",
                "command": "test-tool",
                "install_type": "script",
                "latest_version": "1.0.0",
            },
            status={"installed": True, "version": None, "errors": []},
            install_info={"method": "script", "detail": None},
        )
        self.assertEqual(assessment.decision, cli_status.UpgradeDecision.UNKNOWN)
        self.assertEqual(
            assessment.version_state, cli_status.VersionDisplayState.UNAVAILABLE
        )
        self.assertFalse(assessment.actionable_by_upgrade)

    def test_missing_latest_version_is_unknown(self):
        assessment = self._evaluate(
            {
                "name": "Test Tool",
                "command": "test-tool",
                "install_type": "script",
            },
            status={"installed": True, "version": "1.0.0", "errors": []},
            install_info={"method": "script", "detail": None},
        )
        self.assertEqual(assessment.decision, cli_status.UpgradeDecision.UNKNOWN)
        self.assertEqual(
            assessment.version_state, cli_status.VersionDisplayState.UNAVAILABLE
        )


class TestToolUpgradeEvaluatorDiscovery(unittest.TestCase):
    """Tests for evaluator runtime discovery behavior."""

    def test_evaluator_fetches_system_package_info_from_tool_path(self):
        tool_config = {
            "name": "System Tool",
            "command": "sys-tool",
            "install_type": "script",
            "latest_version": "2.0.0",
        }
        with (
            mock.patch.object(
                cli_status,
                "get_tool_status",
                return_value={"installed": True, "version": "1.0.0", "errors": []},
            ),
            mock.patch.object(
                cli_status,
                "detect_install_method",
                return_value={"method": "system", "detail": "/usr/bin/sys-tool"},
            ),
            mock.patch.object(
                cli_status.shutil, "which", return_value="/usr/bin/sys-tool"
            ),
            mock.patch.object(
                cli_status,
                "get_system_package_info",
                return_value={
                    "package": "dev-util/sys-tool",
                    "installed_version": "1.0.0",
                    "available_version": "1.0.0",
                },
            ) as mock_pkg,
        ):
            assessment = cli_status.ToolUpgradeEvaluator("test", tool_config).evaluate()

        self.assertEqual(
            assessment.decision, cli_status.UpgradeDecision.PACKAGE_MANAGED
        )
        mock_pkg.assert_called_once_with("/usr/bin/sys-tool")
