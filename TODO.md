# TODO

Keep the project focused on managing AI coding CLI tools (install, upgrade,
remove, status, and version metadata).

## Reliability and Correctness

- [ ] Handle missing `node` cleanly during prerequisite checks
  (`FileNotFoundError` path in Node version probing).
- [ ] Read tool version output from both stdout and stderr so status does not
  miss installed versions.
- [ ] Make version cache writes atomic (write temp file + rename) to avoid
  partial/corrupted `versions.json`.

## Security and Integrity

- [ ] Add integrity verification for direct-download tarballs (not only install
  script SHA256).
- [ ] Extend tool metadata to support tarball checksum/signature fields where
  applicable.

## CLI and Automation UX

- [ ] Add `--json` output mode for `list`, `status`, and `update-versions`.
- [ ] Add a focused `doctor` command for environment checks (PATH,
  prerequisites, command health).
- [ ] Consider `install --force` for reinstall/repair flows.
- [ ] Add cleanup support for stale direct-download versions no longer in use.

## Platform and Package Detection

- [ ] Broaden system package metadata detection beyond Gentoo-specific tooling
  where practical.

## Maintainability and Tests

- [ ] Split larger modules into smaller focused files where practical
  (`commands_actions.py`, `versions.py`, `install.py`).
- [ ] Add tests for prerequisite edge cases and cache write behavior.
