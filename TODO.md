# TODO

Keep the project focused on managing AI coding CLI tools (install, upgrade,
remove, status, and version metadata).

## Summary

| #  | Item                                   | Risk     | Effort  | Notes                                                      |
|:---|:---------------------------------------|:---------|:--------|:-----------------------------------------------------------|
| 1  | Handle missing `node` cleanly          | Med      | Low     | Unhandled `FileNotFoundError` crashes prereq checks        |
| 2  | Read version from stdout+stderr        | Med      | Low     | Some tools write version to stderr; shown as not installed |
| 3  | Atomic version cache writes            | Med-High | Low     | Process crash can corrupt `versions.json`                  |
| 4  | Warn on invalid cache JSON             | Low      | Low     | Silent data loss; user sees empty versions                 |
| 5  | Use `os.pathsep` not `":"`             | High     | Trivial | Breaks PATH checks on Windows entirely                     |
| 6  | Verify direct-download tarballs        | High     | Med     | No integrity check before extracting; MITM risk            |
| 7  | Tarball checksum metadata fields       | High     | Low     | Prerequisite for item 6                                    |
| 8  | `--json` output mode                   | Low      | Med     | Needed for CI/automation consumers                         |
| 9  | `doctor` command                       | Low      | Med     | Health checks exist but are scattered                      |
| 10 | `install --force`                      | Low      | Trivial | Internal `force` param exists; not exposed in CLI          |
| 11 | Cleanup stale direct-download versions | Low      | Med     | Old version dirs accumulate on disk                        |
| 12 | Document default subcommand            | Very Low | Trivial | One line in README                                         |
| 13 | Document `install --dryrun`            | Very Low | Trivial | One line in README                                         |
| 14 | Document env vars and config paths     | Low      | Low     | `XDG_CONFIG_HOME` undocumented                             |
| 15 | Cross-distro package detection         | Med      | High    | Only Gentoo supported; other Linux distros get nothing     |
| 16 | Split large modules                    | Low      | High    | Refactoring only; no behavior change                       |
| 17 | Tests for untested functions           | Med      | High    | `cmd_remove`, `fetch_url`, prereqs, detection              |
| 18 | Tests for edge cases                   | Med      | Med     | Cache corruption, PATH oddities, version parsing           |

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
  - `cmd_remove()` (completely untested)
  - `fetch_url()` (completely untested)
  - `check_prerequisites()` / `install_nodejs_npm()` (completely untested)
  - `get_system_package_info()` (completely untested)
- [ ] Add tests for prerequisite edge cases and cache write behavior.
