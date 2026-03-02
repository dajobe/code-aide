# AGENTS.md - AI Coding Agent Instructions

## Key Design Decisions

- No external dependencies - stdlib only
- Three-layer version data: bundled definitions, bundled baseline versions,
  user's local cache (~/.config/code-aide/versions.json)
- All tests should pass before committing
- pre-commit runs black and ruff on commit; run `pre-commit run --all-files` to
  check before committing
- When changing pyproject.toml dependencies, run `uv lock` and commit uv.lock
- Write useful commit messages: start subjects with past-tense action verbs
  (`Added`, `Changed`, `Fixed`, `Removed`), keep them user-facing, and keep
  commits focused.
- Python 3.11+ compatible
- Keep files under 300 lines where practical
- Run `format-markdown` on markdown files before commits (if it is available)
