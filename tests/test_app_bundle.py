"""Tests for macOS app bundle installs and tools that upgrade together."""

import base64
import contextlib
import hashlib
import io
import os
import plistlib
import tempfile
import unittest
from unittest import mock

from code_aide import app_bundle, commands_actions, config, constants
from code_aide import operations as cli_operations
from code_aide import tool_groups
from code_aide.operations import UpgradeResult

EXAMPLE_APP = {
    "name": "Example desktop app",
    "command": "example-app",
    "install_type": "app_bundle",
    "platforms": ["darwin"],
    "github_release_repo": "example/example",
    "download_url_template": (
        "https://example.com/v{version}/Example-{version}-{arch}.zip"
    ),
    "checksum_manifest_url_template": "https://example.com/v{version}/latest-mac.yml",
    "install_dir": "~/.local/opt/example-app/v{version}",
    "app_bundle_name": "Example.app",
    "app_link": "~/Applications/Example.app",
    "bundle_id": "com.example.app",
    "running_process_name": "Example",
    "brew_cask": "example",
}
# The real entry, used only by tests about T3 Code's own configuration.
T3_APP_CONFIG = config.load_bundled_tools()["tools"]["t3code-app"]
BUNDLE = EXAMPLE_APP["app_bundle_name"]


def _make_bundle(path: str, version: str) -> str:
    """Create a minimal app bundle with an Info.plist; return its path."""
    contents = os.path.join(path, "Contents")
    os.makedirs(contents)
    with open(os.path.join(contents, "Info.plist"), "wb") as handle:
        plistlib.dump({"CFBundleShortVersionString": version}, handle)
    return path


class _AppDirMixin(unittest.TestCase):
    """Gives each test an app config rooted in a temporary directory."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(self._tmp.name)
        self.cfg = dict(
            EXAMPLE_APP,
            install_dir=os.path.join(self.root, "opt", "v{version}"),
            app_link=os.path.join(self.root, "Applications", "Example.app"),
        )
        self.link = self.cfg["app_link"]

    def _install_version(self, version: str, activate: bool = True) -> str:
        bundle = _make_bundle(
            os.path.join(self.root, "opt", f"v{version}", BUNDLE), version
        )
        if activate:
            os.makedirs(os.path.dirname(self.link), exist_ok=True)
            if os.path.lexists(self.link):
                os.remove(self.link)
            os.symlink(bundle, self.link)
        return bundle


class TestManifestAndVersion(unittest.TestCase):
    """Tests for the SHA-512 manifest parser and bundle version reader."""

    def test_parse_sha512_manifest(self):
        digest = hashlib.sha512(b"zip").digest()
        text = (
            "version: '1.0.0'\nfiles:\n"
            "  - url: Other-1.0.0-arm64.zip\n"
            f"    sha512: {base64.b64encode(b'x' * 64).decode()}\n"
            "  - url: App-1.0.0-arm64.zip\n"
            f"    sha512: {base64.b64encode(digest).decode()}\n"
            "    size: 3\n"
        )
        self.assertEqual(
            app_bundle.parse_sha512_manifest(text, "App-1.0.0-arm64.zip"),
            digest.hex(),
        )
        self.assertIsNone(app_bundle.parse_sha512_manifest(text, "Missing.zip"))

    def test_bundle_version(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = _make_bundle(os.path.join(td, "X.app"), "1.2.3")
            self.assertEqual(app_bundle.bundle_version(bundle), "1.2.3")
            self.assertIsNone(app_bundle.bundle_version(os.path.join(td, "nope")))


class TestDetectAppInstall(_AppDirMixin):
    """Tests for detect_app_install and tool_location."""

    def test_not_installed(self):
        with mock.patch.object(app_bundle, "app_dirs", return_value=()):
            self.assertIsNone(app_bundle.tool_location(self.cfg))
            self.assertEqual(
                app_bundle.detect_app_install(self.cfg),
                {"method": None, "detail": None},
            )

    def test_managed_version_is_app_bundle(self):
        bundle = self._install_version("1.0.0")
        self.assertEqual(app_bundle.tool_location(self.cfg), self.link)
        self.assertEqual(
            app_bundle.detect_app_install(self.cfg),
            {"method": "app_bundle", "detail": bundle},
        )

    def test_cask_app_in_app_dir(self):
        apps = os.path.join(self.root, "Apps")
        _make_bundle(os.path.join(apps, BUNDLE), "1.0.0")
        with (
            mock.patch.object(app_bundle, "app_dirs", return_value=(apps,)),
            mock.patch.object(app_bundle, "cask_app_dir", return_value=apps),
            mock.patch.object(app_bundle, "is_brew_cask_installed", return_value=True),
        ):
            self.assertEqual(
                app_bundle.detect_app_install(self.cfg),
                {"method": "brew_cask", "detail": "example"},
            )

    def test_found_in_custom_cask_appdir(self):
        apps = os.path.join(self.root, "CustomApps")
        bundle = _make_bundle(os.path.join(apps, BUNDLE), "1.0.0")
        with (
            mock.patch.object(app_bundle, "app_dirs", return_value=()),
            mock.patch.dict(os.environ, {"HOMEBREW_CASK_OPTS": f"--appdir={apps}"}),
            mock.patch.object(app_bundle, "is_brew_cask_installed", return_value=True),
        ):
            self.assertEqual(app_bundle.tool_location(self.cfg), bundle)
            self.assertEqual(
                app_bundle.detect_app_install(self.cfg),
                {"method": "brew_cask", "detail": "example"},
            )

    def test_hand_installed_app_is_user_managed(self):
        apps = os.path.join(self.root, "Apps")
        bundle = _make_bundle(os.path.join(apps, BUNDLE), "1.0.0")
        with (
            mock.patch.object(app_bundle, "app_dirs", return_value=(apps,)),
            mock.patch.object(app_bundle, "is_brew_cask_installed", return_value=False),
        ):
            self.assertEqual(
                app_bundle.detect_app_install(self.cfg),
                {"method": "system", "detail": bundle},
            )


class TestEnsureAppStopped(unittest.TestCase):
    """Tests for the running-app guard."""

    def _run(self, running, tty=True, answer="y", quits=True):
        stdin = mock.Mock()
        stdin.isatty.return_value = tty
        with (
            mock.patch.object(app_bundle, "app_is_running", return_value=running),
            mock.patch.object(app_bundle.sys, "stdin", stdin),
            mock.patch("builtins.input", return_value=answer) as mock_input,
            mock.patch.object(app_bundle, "quit_app", return_value=quits) as quit,
        ):
            result = app_bundle.ensure_app_stopped(EXAMPLE_APP, "upgrade")
        return result, mock_input, quit

    def test_not_running(self):
        result, mock_input, quit = self._run(False)
        self.assertTrue(result)
        mock_input.assert_not_called()
        quit.assert_not_called()

    def test_running_without_terminal_is_skipped(self):
        result, mock_input, quit = self._run(True, tty=False)
        self.assertFalse(result)
        mock_input.assert_not_called()
        quit.assert_not_called()

    def test_running_and_accepted_quits(self):
        result, _input, quit = self._run(True, answer="y")
        self.assertTrue(result)
        quit.assert_called_once()

    def test_running_and_declined(self):
        result, _input, quit = self._run(True, answer="")
        self.assertFalse(result)
        quit.assert_not_called()

    def test_quit_timeout(self):
        result, _input, _quit = self._run(True, answer="yes", quits=False)
        self.assertFalse(result)

    def test_check_failure_is_not_treated_as_stopped(self):
        result, _input, quit = self._run(None)
        self.assertFalse(result)
        quit.assert_not_called()


@mock.patch.object(app_bundle.platform, "system", return_value="Darwin")
@mock.patch.object(app_bundle.platform, "machine", return_value="arm64")
class TestInstallAppBundle(_AppDirMixin):
    """Tests for install_app_bundle activation rules."""

    def _cfg(self, version="2.0.0"):
        return dict(self.cfg, latest_version=version)

    def test_refuses_on_other_platforms(self, _machine, system):
        system.return_value = "Linux"
        self.assertFalse(app_bundle.install_app_bundle("example-app", self._cfg()))

    def test_refuses_unmanaged_link(self, _machine, _system):
        _make_bundle(self.link, "1.0.0")
        self.assertFalse(app_bundle.install_app_bundle("example-app", self._cfg()))

    def test_already_active_does_nothing(self, _machine, _system):
        self._install_version("2.0.0")
        with (
            mock.patch.object(app_bundle, "_stage") as unpack,
            mock.patch.object(app_bundle, "signature_ok", return_value=True),
            mock.patch.object(app_bundle, "ensure_app_stopped") as stopped,
        ):
            self.assertTrue(app_bundle.install_app_bundle("example-app", self._cfg()))
        unpack.assert_not_called()
        stopped.assert_not_called()

    def test_active_bundle_with_bad_signature_is_replaced(self, _machine, _system):
        self._install_version("2.0.0")
        with (
            mock.patch.object(app_bundle, "signature_ok", return_value=False),
            mock.patch.object(app_bundle, "_expected_sha512", return_value="ab" * 64),
            mock.patch.object(app_bundle, "_stage", return_value=None) as stage,
        ):
            self.assertFalse(app_bundle.install_app_bundle("example-app", self._cfg()))
        stage.assert_called_once()

    def test_switches_to_unpacked_version(self, _machine, _system):
        self._install_version("1.0.0")
        new_bundle = self._install_version("2.0.0", activate=False)
        with (
            mock.patch.object(app_bundle, "_stage") as unpack,
            mock.patch.object(app_bundle, "signature_ok", return_value=True),
            mock.patch.object(app_bundle, "ensure_app_stopped", return_value=True),
        ):
            self.assertTrue(app_bundle.install_app_bundle("example-app", self._cfg()))
        unpack.assert_not_called()
        self.assertEqual(os.readlink(self.link), new_bundle)

    def test_reused_bundle_with_bad_signature_is_downloaded_again(
        self, _machine, _system
    ):
        self._install_version("2.0.0", activate=False)
        with (
            mock.patch.object(app_bundle, "signature_ok", return_value=False),
            mock.patch.object(app_bundle, "_expected_sha512", return_value="ab" * 64),
            mock.patch.object(app_bundle, "_stage", return_value=None) as stage,
        ):
            self.assertFalse(app_bundle.install_app_bundle("example-app", self._cfg()))
        stage.assert_called_once()

    def test_declined_quit_leaves_updated_in_place_bundle_alone(
        self, _machine, _system
    ):
        # The app's own updater rewrote the active v2.0.0 directory to 3.0.0,
        # while code-aide still targets 2.0.0. Declining to quit must not
        # replace the directory the running app is using.
        active = self._install_version("2.0.0")
        with open(os.path.join(active, "Contents", "Info.plist"), "wb") as f:
            plistlib.dump({"CFBundleShortVersionString": "3.0.0"}, f)
        staged = _make_bundle(os.path.join(self.root, "staged", BUNDLE), "2.0.0")
        with (
            mock.patch.object(app_bundle, "_expected_sha512", return_value="ab" * 64),
            mock.patch.object(app_bundle, "_stage", return_value=staged),
            mock.patch.object(app_bundle, "ensure_app_stopped", return_value=False),
        ):
            self.assertFalse(app_bundle.install_app_bundle("example-app", self._cfg()))
        self.assertEqual(app_bundle.bundle_version(active), "3.0.0")
        self.assertEqual(os.readlink(self.link), active)

    def test_staged_bundle_replaces_version_dir_after_quit(self, _machine, _system):
        old = self._install_version("1.0.0")
        staged = _make_bundle(os.path.join(self.root, "staged", BUNDLE), "2.0.0")
        with (
            mock.patch.object(app_bundle, "_expected_sha512", return_value="ab" * 64),
            mock.patch.object(app_bundle, "_stage", return_value=staged),
            mock.patch.object(app_bundle, "ensure_app_stopped", return_value=True),
        ):
            self.assertTrue(app_bundle.install_app_bundle("example-app", self._cfg()))
        target = os.readlink(self.link)
        self.assertEqual(app_bundle.bundle_version(target), "2.0.0")
        self.assertNotEqual(target, old)
        self.assertEqual(
            [e for e in os.listdir(self.root + "/opt") if e.startswith(".")], []
        )
        self.assertEqual(
            [e for e in os.listdir(os.path.dirname(self.link)) if e.startswith(".")],
            [],
        )

    def test_running_app_blocks_switch(self, _machine, _system):
        old_bundle = self._install_version("1.0.0")
        self._install_version("2.0.0", activate=False)
        with mock.patch.object(app_bundle, "ensure_app_stopped", return_value=False):
            self.assertFalse(app_bundle.install_app_bundle("example-app", self._cfg()))
        self.assertEqual(os.readlink(self.link), old_bundle)

    def test_download_is_verified_before_unpacking(self, _machine, _system):
        with (
            mock.patch.object(app_bundle, "_expected_sha512", return_value="ab" * 64),
            mock.patch.object(app_bundle, "_stage", return_value=None) as unpack,
        ):
            self.assertFalse(app_bundle.install_app_bundle("example-app", self._cfg()))
        args = unpack.call_args[0]
        self.assertEqual(
            args[1:4],
            (
                "2.0.0",
                "https://example.com/v2.0.0/Example-2.0.0-arm64.zip",
                "ab" * 64,
            ),
        )


class TestRemoveAndClean(_AppDirMixin):
    """Tests for remove_app_bundle and clean_tool_versions on app bundles."""

    def test_remove_deletes_link_and_versions_only(self):
        self._install_version("1.0.0", activate=False)
        self._install_version("2.0.0")
        other = os.path.join(self.root, "opt", "keep-me")
        os.makedirs(other)
        with mock.patch.object(app_bundle, "ensure_app_stopped", return_value=True):
            self.assertTrue(app_bundle.remove_app_bundle(self.cfg))
        self.assertFalse(os.path.lexists(self.link))
        self.assertEqual(os.listdir(os.path.join(self.root, "opt")), ["keep-me"])

    def test_remove_refused_while_running(self):
        self._install_version("1.0.0")
        with mock.patch.object(app_bundle, "ensure_app_stopped", return_value=False):
            self.assertFalse(app_bundle.remove_app_bundle(self.cfg))
        self.assertTrue(os.path.islink(self.link))

    def test_clean_keeps_active_version(self):
        old = os.path.dirname(self._install_version("1.0.0", activate=False))
        self._install_version("2.0.0")
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"app": self.cfg}),
            mock.patch.object(cli_operations, "app_is_running", return_value=False),
        ):
            self.assertEqual(cli_operations.clean_tool_versions("app"), [old])
        self.assertFalse(os.path.exists(old))

    def test_clean_skipped_while_running(self):
        self._install_version("1.0.0", activate=False)
        self._install_version("2.0.0")
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"app": self.cfg}),
            mock.patch.object(cli_operations, "app_is_running", return_value=True),
        ):
            self.assertEqual(cli_operations.clean_tool_versions("app"), [])
        self.assertTrue(os.path.isdir(os.path.join(self.root, "opt", "v1.0.0")))

    def test_clean_skips_self_pruning_tool(self):
        cfg = {
            "name": "CLI",
            "install_dir": os.path.join(self.root, "v", "{version}"),
            "self_pruning_versions": True,
        }
        with mock.patch.dict(constants._TOOLS_DATA, {"cli": cfg}):
            self.assertIsNone(cli_operations.clean_tool_versions("cli"))


GROUP_TOOLS = {
    "cli": {"name": "CLI", "command": "cli", "upgrade_with": ["app"]},
    "app": {
        "name": "App",
        "command": "app",
        "install_type": "app_bundle",
        "upgrade_with": ["cli"],
    },
    "other": {"name": "Other", "command": "other"},
}


class TestUpgradeGroups(unittest.TestCase):
    """Tests for expanding and running linked upgrades."""

    def test_expand_adds_installed_partner_and_orders_app_first(self):
        with (
            mock.patch.dict(constants._TOOLS_DATA, GROUP_TOOLS, clear=True),
            mock.patch.object(tool_groups, "is_tool_installed", return_value=True),
        ):
            self.assertEqual(
                tool_groups.expand_upgrade_groups(["other", "cli"]),
                ["app", "other", "cli"],
            )

    def test_expand_skips_uninstalled_partner(self):
        with (
            mock.patch.dict(constants._TOOLS_DATA, GROUP_TOOLS, clear=True),
            mock.patch.object(tool_groups, "is_tool_installed", return_value=False),
        ):
            self.assertEqual(tool_groups.expand_upgrade_groups(["cli"]), ["cli"])

    def _upgrade(self, results, gap=None):
        args = type("Args", (), {"tools": ["cli"]})()
        with (
            mock.patch.object(
                commands_actions, "partner_version_gap", return_value=gap
            ),
            mock.patch.dict(constants._TOOLS_DATA, GROUP_TOOLS, clear=True),
            mock.patch.object(commands_actions, "validate_tools"),
            mock.patch.object(commands_actions, "is_tool_installed", return_value=True),
            mock.patch.object(tool_groups, "is_tool_installed", return_value=True),
            mock.patch.object(
                commands_actions, "upgrade_tool", side_effect=lambda t: results[t]
            ) as upgrade,
        ):
            buf = io.StringIO()
            code = None
            with contextlib.redirect_stdout(buf):
                try:
                    commands_actions.cmd_upgrade(args)
                except SystemExit as exc:
                    code = exc.code
        return [c.args[0] for c in upgrade.call_args_list], buf.getvalue(), code

    def test_failed_app_holds_back_cli(self):
        called, output, code = self._upgrade(
            {"app": UpgradeResult.FAILED, "cli": UpgradeResult.CHANGED}
        )
        self.assertEqual(called, ["app"])
        self.assertIn("Held back to stay in step: cli", output)
        self.assertEqual(code, 1)

    def test_lagging_app_holds_back_cli(self):
        called, output, code = self._upgrade(
            {"app": UpgradeResult.UNCHANGED, "cli": UpgradeResult.CHANGED},
            gap="app is at 1.0.0, not the 2.0.0 release cli would move to",
        )
        self.assertEqual(called, ["app"])
        self.assertIn("not the 2.0.0 release", output)
        self.assertEqual(code, 1)

    def test_partner_version_gap(self):
        tools = dict(GROUP_TOOLS, cli=dict(GROUP_TOOLS["cli"], latest_version="2.0.0"))
        with (
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(tool_groups, "installed_version", return_value="1.0.0"),
        ):
            self.assertIn("1.0.0", tool_groups.partner_version_gap("app", "cli"))
        with (
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(tool_groups, "installed_version", return_value="2.0.0"),
        ):
            self.assertIsNone(tool_groups.partner_version_gap("app", "cli"))

    def test_uncached_partner_target_is_resolved_and_recorded(self):
        tools = {k: dict(v) for k, v in GROUP_TOOLS.items()}
        with (
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(
                tool_groups,
                "check_script_tool",
                return_value={"status": "changed", "version": "2.0.0"},
            ),
            mock.patch.object(tool_groups, "installed_version", return_value="1.0.0"),
        ):
            gap = tool_groups.partner_version_gap("app", "cli")
            self.assertEqual(constants.TOOLS["cli"]["latest_version"], "2.0.0")
        self.assertIn("not the 2.0.0 release", gap)

    def test_unknown_versions_hold_partner(self):
        tools = {k: dict(v) for k, v in GROUP_TOOLS.items()}
        with (
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(
                tool_groups, "check_script_tool", return_value={"status": "error"}
            ),
        ):
            self.assertIn(
                "could not determine", tool_groups.partner_version_gap("app", "cli")
            )
        tools["cli"]["latest_version"] = "2.0.0"
        with (
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(tool_groups, "installed_version", return_value=None),
        ):
            self.assertIn(
                "could not read", tool_groups.partner_version_gap("app", "cli")
            )

    def test_both_upgrade_in_order(self):
        called, output, code = self._upgrade(
            {"app": UpgradeResult.CHANGED, "cli": UpgradeResult.CHANGED}
        )
        self.assertEqual(called, ["app", "cli"])
        self.assertIsNone(code)

    def test_version_mismatch_reported(self):
        versions = {"cli": "cli v1.0.0", "app": "2.0.0"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, GROUP_TOOLS, clear=True),
            mock.patch.object(tool_groups, "is_tool_installed", return_value=True),
            mock.patch.object(
                tool_groups,
                "get_tool_status",
                side_effect=lambda name, _cfg: {"version": versions[name]},
            ),
        ):
            messages = tool_groups.linked_version_mismatches()
        self.assertEqual(len(messages), 1)
        self.assertIn("app 2.0.0 and cli 1.0.0 differ", messages[0])


class TestServiceHintAndPlatforms(unittest.TestCase):
    """Tests for the service restart hint and platform filtering."""

    def test_service_hint_only_when_service_file_exists(self):
        with tempfile.TemporaryDirectory() as td:
            service = os.path.join(td, "svc.plist")
            cfg = {"service_files": [service], "service_restart_hint": "restart it"}
            with mock.patch.object(cli_operations, "warning") as warn:
                cli_operations.warn_service_restart(cfg)
                warn.assert_not_called()
                open(service, "w").close()
                cli_operations.warn_service_restart(cfg)
                warn.assert_called_once_with("restart it")

    def test_t3code_app_entry(self):
        # T3 Code's real entry: macOS only, linked to the CLI, and pointing
        # at the release asset names upstream publishes.
        self.assertEqual(T3_APP_CONFIG["platforms"], ["darwin"])
        self.assertEqual(T3_APP_CONFIG["upgrade_with"], ["t3code"])
        self.assertEqual(
            T3_APP_CONFIG["download_url_template"].format(
                version="0.1.7", arch="arm64"
            ),
            "https://github.com/pingdotgg/t3code/releases/download/v0.1.7/"
            "T3-Code-0.1.7-arm64.zip",
        )

    def test_platform_filter(self):
        with mock.patch.object(config.platform, "system", return_value="Linux"):
            self.assertFalse(config.is_supported_platform(EXAMPLE_APP))
            self.assertTrue(config.is_supported_platform({"name": "x"}))
        with mock.patch.object(config.platform, "system", return_value="Darwin"):
            self.assertTrue(config.is_supported_platform(EXAMPLE_APP))


class TestCaskGuardAndCache(unittest.TestCase):
    """Tests for the cask running-app guard, cask appdir, and cache checks."""

    def test_cask_upgrade_and_remove_respect_running_app(self):
        from code_aide import operation_handlers as handlers

        cli = {"name": "CLI", "command": "example"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"app": EXAMPLE_APP}, clear=True),
            mock.patch.object(handlers, "ensure_app_stopped", return_value=False),
            mock.patch.object(handlers, "run_command") as run,
        ):
            self.assertFalse(handlers._upgrade_brew_cask("example", cli, "example"))
            self.assertFalse(handlers._remove_brew_cask("example", cli, "example"))
        run.assert_not_called()

    def test_other_casks_are_not_guarded(self):
        from code_aide import operation_handlers as handlers

        with (
            mock.patch.dict(constants._TOOLS_DATA, {"app": EXAMPLE_APP}, clear=True),
            mock.patch.object(handlers, "ensure_app_stopped") as stopped,
            mock.patch.object(handlers, "run_command") as run,
        ):
            self.assertTrue(handlers._upgrade_brew_cask("codex", {}, "codex"))
        stopped.assert_not_called()
        run.assert_called_once()

    def test_cask_app_dir(self):
        cases = {
            "": "/Applications",
            "--appdir=~/Applications": os.path.expanduser("~/Applications"),
            "--no-quarantine --appdir /opt/apps/": "/opt/apps",
        }
        for opts, expected in cases.items():
            with mock.patch.dict(os.environ, {"HOMEBREW_CASK_OPTS": opts}):
                self.assertEqual(app_bundle.cask_app_dir(), expected, opts)

    def test_cache_freshness_requires_github_release_versions(self):
        tools = {
            "app": dict(EXAMPLE_APP),
            "cli": {"install_type": "direct_download", "github_release_repo": "o/r"},
        }
        with (
            mock.patch.object(config.os.path, "getmtime", return_value=1e12),
            mock.patch.object(config.time, "time", return_value=1e12),
        ):
            self.assertFalse(config.versions_cache_is_fresh(tools))
            for tool in tools.values():
                tool["latest_version"] = "1.0.0"
            self.assertTrue(config.versions_cache_is_fresh(tools))


if __name__ == "__main__":
    unittest.main()
