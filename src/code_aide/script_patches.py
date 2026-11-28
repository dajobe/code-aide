"""Text replacements applied to verified third-party install scripts."""

from typing import Any, Dict, List, Mapping, Optional, Sequence

ScriptReplacements = Sequence[Mapping[str, str]]


def get_install_script_replacements(
    tool_config: Dict[str, Any],
) -> Optional[List[Dict[str, str]]]:
    """Return a tool's configured install script replacements, if any."""
    replacements = tool_config.get("install_script_replacements")
    if not replacements:
        return None
    return [dict(item) for item in replacements]


def apply_script_replacements(
    script_content: bytes, replacements: Optional[ScriptReplacements]
) -> bytes:
    """Replace every occurrence of each ``old`` string with its ``new`` string.

    Replacements run after the script's SHA256 has been verified, so the
    pinned script is what is edited. A missing ``old`` string means the
    replacement no longer fits the script, and raises ValueError rather than
    silently running the unmodified script.
    """
    if not replacements:
        return script_content
    text = script_content.decode("utf-8")
    for replacement in replacements:
        old = replacement["old"]
        new = replacement["new"]
        if old not in text:
            raise ValueError(f"install script replacement not found: {old!r}")
        text = text.replace(old, new)
    return text.encode("utf-8")
