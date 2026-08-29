# TODO

Keep the project focused on managing AI coding CLI tools (install, upgrade,
remove, status, and version metadata).

## Summary

| #  | Item                                   | Risk     | Effort  | Notes                                                      |
|:---|:---------------------------------------|:---------|:--------|:-----------------------------------------------------------|
| 1  | Read version from stdout+stderr        | Med      | Low     | Some tools write version to stderr; shown as not installed |
| 2  | `--json` output mode                   | Low      | Med     | Needed for CI/automation consumers                         |
| 3  | `doctor` command                       | Low      | Med     | Health checks exist but are scattered                      |
| 4  | `install --force`                      | Low      | Trivial | Internal `force` param exists; not exposed in CLI          |
| 5  | Cleanup stale direct-download versions | Low      | Med     | Old version dirs accumulate on disk                        |
| 6  | Document default subcommand            | Very Low | Trivial | One line in README                                         |
| 7  | Document `install --dryrun`            | Very Low | Trivial | One line in README                                         |
| 8  | Document env vars and config paths     | Low      | Low     | `XDG_CONFIG_HOME` undocumented                             |
| 9  | Cross-distro package detection         | Med      | High    | Only Gentoo supported; other Linux distros get nothing     |
| 10 | Split large modules                    | Low      | High    | Refactoring only; no behavior change                       |
| 11 | Tests for untested functions           | Med      | High    | `fetch_url`, `get_system_package_info`                     |
| 12 | Tests for edge cases                   | Med      | Med     | PATH oddities, more version parsing corners                |

## Reliability and Correctness

- [ ] Read tool version output from both stdout and stderr so status does not
  miss installed versions.

## Security and Integrity

- [ ] Consider signature verification (beyond SHA256) for downloads where
  upstream publishes signatures.

## CLI and Automation UX

- [ ] Add `--json` output mode for `list`, `status`, and `update-versions`.
- [ ] Add a focused `doctor` command for environment checks (PATH,
  prerequisites, command health).
- [ ] Consider `install --force` for reinstall/repair flows.
- [ ] Add cleanup support for stale direct-download versions no longer in use.

## Documentation

- [ ] Document that running `code-aide` with no subcommand defaults to `status`.
- [ ] Add `install --dryrun` to the README usage examples.
- [ ] Document environment variables and config file paths
  (`~/.config/code-aide/versions.json`).

## Platform and Package Detection

- [ ] Broaden system package metadata detection beyond Gentoo-specific tooling
  where practical.

## Maintainability and Tests

- [ ] Split larger modules into smaller focused files where practical
  (`commands_actions.py`, `versions.py`, `install.py`).
- [ ] Add tests for remaining untested functions:
  - `fetch_url()` (network; needs mocking)
  - `get_system_package_info()` (Gentoo tooling)
- [ ] Add tests for more prerequisite edge cases and PATH oddities.
