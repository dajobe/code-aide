# AGENTS.md - AI Coding Agent Instructions

## Key Design Decisions

- No external dependencies - stdlib only
- Three-layer version data: bundled definitions, bundled baseline versions,
  user's local cache (~/.config/code-aide/versions.json)
- All tests should pass before committing
- Run `black` formatter on python before commits
- Python 3.11+ compatible
- Keep files under 300 lines where practical
- Run `format-markdown` on markdown files before commits (if it is available)
