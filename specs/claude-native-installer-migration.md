# Migrate Claude Code from npm to native installer in code-aide

## Context

Anthropic has deprecated npm installation of Claude Code in favor of a
native installer (`curl -fsSL https://claude.ai/install.sh | bash`). The
native binary lives at `~/.local/bin/claude` (symlink to
`~/.local/share/claude/versions/<version>`), auto-updates, and has no
Node.js dependency. code-aide currently treats Claude as `self_managed`
install type backed by npm, which is now outdated.

## Approach

Change Claude's install type from `self_managed` (npm-backed) to `script`
(install-script-backed). This reuses the existing `script` install type
already used by Amp, which downloads and verifies a shell script by SHA256
before executing it. Claude Code was the only tool using `self_managed`, so
that type becomes dead code and can be removed.

## Changes

### 1. `src/code_aide/data/tools.json` -- update claude config

- Change `install_type` from `self_managed` to `script`
- Add `install_url`: `https://claude.ai/install.sh`
- Add `install_sha256`:
  `431889ac7d056f636aaf5b71524666d04c89c45560f80329940846479d484778`
- Remove `npm_package` field
- Remove `upgrade_command` field (native binary auto-updates; `script`
  upgrade re-runs the install script which is idempotent)
- Change `prerequisites` from `["npm"]` to `[]`
- Update `docs_url` to `https://code.claude.com/docs/en/setup`

### 2. `src/code_aide/detection.py` -- detect native installer

Add a new detection case before the `node_modules` check:

```python
if "/.local/share/claude/versions/" in real_path:
    return {"method": "script", "detail": "native installer"}
```

This detects the native binary's real path pattern.

### 3. `src/code_aide/detection.py` -- format label

No change needed -- the existing `format_install_method("script")` returns
`"script"` which is accurate.

### 4. `src/code_aide/install.py` -- remove `self_managed` branch

Remove the `elif install_type == "self_managed"` block (lines 289-301). The
`script` handler (lines 261-275) will now handle Claude's installation.

### 5. `src/code_aide/operations.py` -- remove `self_managed` branches

- **upgrade_tool**: Remove `elif method == "self_managed"` block (lines
  65-71). The `script` branch (lines 53-59) handles re-running the install
  script, which for Claude is idempotent and installs the latest version.
- **remove_tool**: Remove `elif method == "self_managed"` block (lines
  203-230). The `script` branch (lines 133-158) removes the binary at its
  `which` path. For full cleanup, add removal of `~/.local/share/claude`
  directory in the script removal path when the tool is `claude`.

### 6. `src/code_aide/versions.py` -- remove `self_managed` branch

- `format_check_backend`: Remove the `self_managed` -> `npm-registry`
  mapping (line 276-277). Claude will now use `script-url` backend (SHA256
  check of install script + version extraction).
- `check_npm_tool` is no longer called for Claude; `check_script_tool`
  handles it instead via the `script` type path.

### 7. `src/code_aide/commands_actions.py` -- remove `self_managed` from update check

- Line 259: Change `if install_type in ("npm", "self_managed")` to `if
  install_type == "npm"`.

### 8. Tests -- update all `self_managed` references

- **`tests/test_constants.py`**: Change assertion from `self_managed` to
  `script`; remove npm prerequisite assertion
- **`tests/test_config.py`**: Change assertion from `self_managed` to
  `script`
- **`tests/test_detection.py`**:
  - Update `test_detects_brew_npm_wrapper` -- this test was for npm Claude
    installs; replace with test for native installer detection (realpath
    containing `/.local/share/claude/versions/`)
  - Update `test_detects_plain_npm_global` -- same, replace with a variant
  - Remove `TestFormatInstallMethodSelfManaged` class
  - Update `test_brew_npm_label` test -- change to use a different tool's
    npm package (or remove if no tools use brew_npm)
- **`tests/test_operations.py`**: Change `TestRemoveToolSelfManaged` to test
  script-based removal instead
- **`tests/test_versions.py`**: Remove `TestFormatCheckBackendSelfManaged`;
  optionally add a test that `script` maps to `script-url`

### 9. `README.md` -- update table

Change Claude's install type from `Self-managed (npm)` to `Script`.

## Verification

1. `uv run pytest tests/ -v` -- all tests pass
2. `uv run python -m code_aide status` -- Claude shows as installed, method
   shows `script`
3. `uv run python -m code_aide list` -- Claude listed with script install
   type
4. `uv run python -m code_aide update-versions -n` -- Claude checked via
   script-url backend, SHA256 verified
5. Manually verify detection: `claude` resolves to `~/.local/bin/claude`
   with realpath `~/.local/share/claude/versions/...`, detected as `script`
   method
