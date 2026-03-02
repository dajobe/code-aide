# Auto-migrate deprecated install methods

## Context

Claude Code switched from npm to a native installer. Users who installed
Claude via npm are stuck: `code-aide upgrade` runs `npm install -g @latest`
(the detected method) instead of the native script installer (the configured
method). `code-aide install` exits early because the command already exists.
There is no migration path. code-aide should detect this and fix it
automatically.

This is a general pattern -- any tool could change install methods in the
future. The solution should not be Claude-specific.

## Approach

A detected install method is "deprecated" when:

- Detected method is `npm` or `brew_npm` AND config `install_type` is
  `script` or `direct_download`

Methods that are never considered deprecated (user-managed choices):

- `brew_formula`, `brew_cask` -- user explicitly chose Homebrew
- `system` -- managed by system package manager

Migration flow: remove old (npm), install new (configured method), with
clear messaging. If the new install fails after removal, provide recovery
instructions.

## Changes

### 1. `src/code_aide/data/tools.json` -- add deprecated_npm_package

Add a `deprecated_npm_package` field to Claude's entry:

```json
"claude": {
  "name": "Claude CLI (Claude Code)",
  "install_type": "script",
  "deprecated_npm_package": "@anthropic-ai/claude-code",
  ...
}
```

This records the old npm package name explicitly so the migration removal
step does not rely solely on extracting the package name from the binary
path.

### 2. `src/code_aide/detection.py` -- add deprecation detection

Add two functions:

- `is_deprecated_install(tool_name)` -- returns True when the detected
  install method is `npm` or `brew_npm` but the configured `install_type` is
  something else (script, direct_download). Also returns True when
  `deprecated_npm_package` is set and the detected method is npm. Brew
  formula/cask and system installs are never deprecated (user-managed).
- `format_migration_warning(tool_name)` -- returns a human-readable warning
  string, or None if not deprecated. Uses existing `format_install_method()`
  for labels.

### 3. `src/code_aide/operations.py` -- auto-migrate in upgrade

Add `_migrate_install_method()` private function that:

1. Warns about the deprecated method
2. Calls `remove_tool()` to remove the old npm install
3. Calls `install_tool()` to install via the configured method
4. If install fails after remove, prints recovery instructions (`code-aide
   install <tool>` and manual curl command for script types)

Modify `upgrade_tool()`: after `detect_install_method()`, check
`is_deprecated_install()`. If True, call `_migrate_install_method()` instead
of the normal upgrade branch.

Modify `remove_tool()` npm branch: fall back to
`tool_config.get("deprecated_npm_package")` when looking up the npm package
name. Current code: `npm_package = detail or
tool_config.get("npm_package")`. Change to also check
`deprecated_npm_package`.

New imports needed: `is_deprecated_install`, `format_install_method` from
detection, `install_tool` from install.

Note: after `remove_tool()` succeeds, `command_exists()` returns False so
`install_tool()` proceeds normally with the configured `install_type`.

### 4. `src/code_aide/commands_actions.py` -- include deprecated in auto-upgrade

Modify `cmd_upgrade()` no-args path: after building the version-outdated
list, also add any installed tools with deprecated install methods. Without
this, a tool whose version is current but install method is deprecated would
be silently skipped by `code-aide upgrade`.

New import: `is_deprecated_install` from detection.

### 5. `src/code_aide/commands_tools.py` -- show warnings in status/list

In both `cmd_list()` and `cmd_status()`, after displaying "Installed via:",
call `format_migration_warning()` and display the warning if present.

At the end of `cmd_status()`, add a summary line counting tools that need
migration.

New imports: `format_migration_warning`, `is_deprecated_install` from
detection.

### 6. Tests

- `tests/test_detection.py`: Tests for `is_deprecated_install()` covering
  npm to script (deprecated), npm to npm (not deprecated), brew_formula
  (never deprecated), system (never deprecated), not installed, unknown
  tool, npm to direct_download. Tests for `format_migration_warning()`.
- `tests/test_operations.py`: Tests for migration in `upgrade_tool()`:
  triggers migration, normal upgrade when not deprecated, migration fails on
  remove, migration fails on install with recovery message.
- `tests/test_commands_tools.py`: Test that status/list show migration
  warnings for deprecated installs.

## Verification

1. `pre-commit run --all-files` -- formatting passes
2. `uv run pytest tests/ -v` -- all tests pass
3. `uv run python -m code_aide status` -- shows migration warning for
   npm-installed Claude (if applicable)
4. `uv run python -m code_aide upgrade claude` -- performs migration (remove
   npm, install via script)
