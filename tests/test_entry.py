"""Unit tests for the CLI argument parser and entrypoint."""

import logging
import unittest
from unittest import mock

from code_aide import entry as cli_entry


class TestArgumentParser(unittest.TestCase):
    """Cover individual subcommand parsing and the default behavior."""

    def _run_with_args(self, argv):
        with (
            mock.patch("sys.argv", ["code-aide"] + argv),
            mock.patch.object(cli_entry, "cmd_status") as mock_status,
            mock.patch.object(cli_entry, "cmd_list") as mock_list,
            mock.patch.object(cli_entry, "cmd_install") as mock_install,
            mock.patch.object(cli_entry, "cmd_upgrade") as mock_upgrade,
            mock.patch.object(cli_entry, "cmd_remove") as mock_remove,
            mock.patch.object(cli_entry, "cmd_update_versions") as mock_update,
        ):
            cli_entry.main()
            return {
                "status": mock_status,
                "list": mock_list,
                "install": mock_install,
                "upgrade": mock_upgrade,
                "remove": mock_remove,
                "update": mock_update,
            }

    def test_no_subcommand_runs_status(self):
        mocks = self._run_with_args([])
        mocks["status"].assert_called_once()

    def test_list_subcommand(self):
        mocks = self._run_with_args(["list"])
        mocks["list"].assert_called_once()
        mocks["status"].assert_not_called()

    def test_status_long_flag_recorded(self):
        mocks = self._run_with_args(["status", "--long"])
        ns = mocks["status"].call_args[0][0]
        self.assertTrue(ns.long)

    def test_install_passes_tools_and_flags(self):
        mocks = self._run_with_args(["install", "claude", "-p", "--dryrun"])
        ns = mocks["install"].call_args[0][0]
        self.assertEqual(ns.tools, ["claude"])
        self.assertTrue(ns.install_prerequisites)
        self.assertTrue(ns.dryrun)

    def test_upgrade_default_no_tools(self):
        mocks = self._run_with_args(["upgrade"])
        ns = mocks["upgrade"].call_args[0][0]
        self.assertEqual(ns.tools, [])

    def test_remove_with_tool(self):
        mocks = self._run_with_args(["remove", "amp"])
        ns = mocks["remove"].call_args[0][0]
        self.assertEqual(ns.tools, ["amp"])

    def test_update_versions_flags(self):
        mocks = self._run_with_args(
            ["update-versions", "--dryrun", "--yes", "--verbose"]
        )
        ns = mocks["update"].call_args[0][0]
        self.assertTrue(ns.dryrun)
        self.assertTrue(ns.yes)
        self.assertTrue(ns.verbose)

    def test_version_flag_exits_cleanly(self):
        with mock.patch("sys.argv", ["code-aide", "--version"]):
            with self.assertRaises(SystemExit) as cm:
                cli_entry.main()
            # argparse uses exit code 0 for --version
            self.assertEqual(cm.exception.code, 0)


class TestLoggingConfiguration(unittest.TestCase):
    """Verify the --debug flag wires up logging."""

    def setUp(self):
        # Save and restore root logger level/handlers so other tests are unaffected.
        root = logging.getLogger()
        self._saved_level = root.level
        self._saved_handlers = root.handlers[:]

    def tearDown(self):
        root = logging.getLogger()
        root.setLevel(self._saved_level)
        root.handlers[:] = self._saved_handlers

    def test_default_logging_is_warning(self):
        cli_entry._configure_logging(debug=False)
        self.assertEqual(logging.getLogger().level, logging.WARNING)

    def test_debug_flag_enables_debug_logging(self):
        cli_entry._configure_logging(debug=True)
        self.assertEqual(logging.getLogger().level, logging.DEBUG)


if __name__ == "__main__":
    unittest.main()
