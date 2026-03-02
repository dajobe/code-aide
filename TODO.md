# TODO

Keep the project focused on managing AI coding CLI tools (install, upgrade,
remove, status, and version metadata).

## Bugs

- [x] Standardize `--dryrun` flag: `update-versions` uses `--dry-run` but
  `install` uses `--dryrun`. Change `update-versions` to `--dryrun`.
- [x] Add missing `success()` message for direct-download installs in
  non-dryrun mode (`install.py`, `install_tool()`).
- [x] Replace PID-based temp directory naming with `tempfile.mkdtemp()` in
  `install.py` `install_direct_download()`.
- [x] Guard `package.split("/", 1)` in `detection.py`
  `get_system_package_info()` against missing `/` in subprocess output.

## Reliability and Correctness

- [ ] Handle missing `node` cleanly during prerequisite checks
  (`FileNotFoundError` path in Node version probing).
- [ ] Read tool version output from both stdout and stderr so status does
  not miss installed versions.
- [ ] Make version cache writes atomic (write temp file + rename) to avoid
  partial/corrupted `versions.json`.
- [ ] Warn when `versions.json` cache contains invalid JSON instead of
  silently returning empty data.
- [ ] Use `os.pathsep` instead of hardcoded `":"` in `prereqs.py`
  `check_path_directories()`.

## Security and Integrity

- [ ] Add integrity verification for direct-download tarballs (not only
  install script SHA256).
- [ ] Extend tool metadata to support tarball checksum/signature fields
  where applicable.

## CLI and Automation UX

- [ ] Add `--json` output mode for `list`, `status`, and `update-versions`.
- [ ] Add a focused `doctor` command for environment checks (PATH,
  prerequisites, command health).
- [ ] Consider `install --force` for reinstall/repair flows.
- [ ] Add cleanup support for stale direct-download versions no longer in
  use.
- [ ] Expand `upgrade` help text to mention the default "only out-of-date
  tools" behavior.

## Documentation

- [ ] Document that running `code-aide` with no subcommand defaults to
  `status`.
- [ ] Add `install --dryrun` to the README usage examples.
- [ ] Document environment variables and config file paths
  (`~/.config/code-aide/versions.json`).

## Platform and Package Detection

- [ ] Broaden system package metadata detection beyond Gentoo-specific
  tooling where practical.

## Maintainability and Tests

- [ ] Split larger modules into smaller focused files where practical
  (`commands_actions.py`, `versions.py`, `install.py`).
- [ ] Add tests for major untested functions:
  - `upgrade_tool()` (completely untested)
  - `cmd_remove()` (completely untested)
  - `fetch_url()` (completely untested)
  - `check_prerequisites()` / `install_nodejs_npm()` (completely untested)
  - `get_system_package_info()` (completely untested)
- [ ] Add tests for prerequisite edge cases and cache write behavior.
