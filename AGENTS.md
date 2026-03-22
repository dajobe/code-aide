# AGENTS.md - AI Coding Agent Instructions

- Always use `uv run` to run python code and scripts.
- Run tests with `uv run pytest`.

## Key Design Decisions

- Runtime dependencies are stdlib only (`dependencies` in pyproject.toml).
  Dev tooling (pytest, black, ruff) lives in `dependency-groups` for tests
  and linting.
- Primary supported environments are macOS and Linux (see pyproject
  classifiers); avoid assuming Windows-specific behavior unless explicitly
  in scope.
- For planned behavior or refactors, read matching notes under `specs/`
  before inventing design.
- Two-layer version data: bundled definitions (with SHA256 checksums),
  user's local cache (~/.config/code-aide/versions.json)
- All tests should pass before committing
- pre-commit runs black and ruff on commit; run `black` to format and then
  `pre-commit run --all-files` to check before committing
- When changing pyproject.toml dependencies, run `uv lock` and commit
  uv.lock
- Write useful commit messages: start subjects with past-tense action verbs
  (`Added`, `Changed`, `Fixed`, `Removed`), keep them user-facing, and keep
  commits focused.
- Python 3.11+ compatible
- Keep files under 300 lines where practical
- Run `format-markdown` on markdown files before commits (if it is
  available)
- When pushing tags, always push them explicitly with `git push <remote>
  <tag>` rather than relying on `--follow-tags`, which silently skips tags
  when the branch commits are already on the remote
