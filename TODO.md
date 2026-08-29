# TODO

Keep the project focused on managing AI coding CLI tools (install, upgrade,
remove, status, and version metadata).

## Summary

| #  | Item                                        | Risk     | Effort  | Notes                                                              |
|:---|:--------------------------------------------|:---------|:--------|:-------------------------------------------------------------------|
| 1  | ~~Handle missing `node` cleanly~~ (done)    | -        | -       | Fixed in `prereqs.py` `check_prerequisites()`                      |
| 2  | Read version from stdout+stderr             | Med      | Low     | Some tools write version to stderr; shown as not installed         |
| 3  | ~~Atomic version cache writes~~ (done)      | -        | -       | Fixed in `config.py` `save_versions_cache()`                       |
| 4  | ~~Warn on invalid cache JSON~~ (done)       | -        | -       | `config.py` `load_versions_cache()` logs a warning                 |
| 5  | ~~Use `os.pathsep` not `":"`~~ (done)       | -        | -       | Fixed in `prereqs.py` `check_path_directories()`                   |
| 6  | ~~Verify direct-download tarballs~~ (done)  | -        | -       | `download_sha256` recorded by update-versions, verified on install |
| 7  | ~~Tarball checksum metadata fields~~ (done) | -        | -       | `download_sha256` field in tools schema and versions cache         |
| 8  | `--json` output mode                        | Low      | Med     | Needed for CI/automation consumers                                 |
| 9  | `doctor` command                            | Low      | Med     | Health checks exist but are scattered                              |
| 10 | `install --force`                           | Low      | Trivial | Internal `force` param exists; not exposed in CLI                  |
| 11 | Cleanup stale direct-download versions      | Low      | Med     | Old version dirs accumulate on disk                                |
| 12 | Document default subcommand                 | Very Low | Trivial | One line in README                                                 |
| 13 | Document `install --dryrun`                 | Very Low | Trivial | One line in README                                                 |
| 14 | Document env vars and config paths          | Low      | Low     | `XDG_CONFIG_HOME` undocumented                                     |
| 15 | Cross-distro package detection              | Med      | High    | Only Gentoo supported; other Linux distros get nothing             |
| 16 | Split large modules                         | Low      | High    | Refactoring only; no behavior change                               |
| 17 | Tests for untested functions                | Med      | High    | `fetch_url`, `get_system_package_info`                             |
| 18 | Tests for edge cases                        | Med      | Med     | PATH oddities, more version parsing corners                        |

## Reliability and Correctness

- [x] Handle missing `node` cleanly during prerequisite checks (`OSError` path
  in Node version probing).
- [ ] Read tool version output from both stdout and stderr so status does not
  miss installed versions.
- [x] Make version cache writes atomic (temp file + rename) to avoid
  partial/corrupted `versions.json`.
- [x] Warn when `versions.json` cache contains invalid JSON instead of silently
  returning empty data.
- [x] Use `os.pathsep` instead of hardcoded `":"` in `prereqs.py`
  `check_path_directories()`.

## Security and Integrity

- [x] Verify direct-download tarballs against a checksum recorded by
  `update-versions` (warn when no checksum has been recorded yet).
- [x] Extend tool metadata with a `download_sha256` field for tarball checksums.
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
