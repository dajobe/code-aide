"""Tools that must upgrade together.

A tool lists its partners in ``upgrade_with`` (for example an ``example``
CLI and its ``example-app`` desktop app, which talk to each other and must
run the same release).
Upgrading any member also upgrades the installed partners. App bundles go
first: they are the member most likely to be blocked (by the running app),
and when one is not upgraded its partners are held back.
"""

from typing import List, Optional

from code_aide.app_bundle import is_app_bundle_tool
from code_aide.constants import TOOLS
from code_aide.prereqs import is_tool_installed
from code_aide.status import get_tool_status
from code_aide.install_types import InstallType, parse_install_type
from code_aide.versions import (
    check_npm_tool,
    check_script_tool,
    extract_version_from_string,
    normalize_version,
)


def linked_tools(tool_name: str) -> List[str]:
    """Return the configured partners of a tool that this platform has."""
    tool_config = TOOLS.get(tool_name, {})
    return [name for name in tool_config.get("upgrade_with", []) if name in TOOLS]


def expand_upgrade_groups(tool_names: List[str]) -> List[str]:
    """Add installed partners to an upgrade list and order app bundles first."""
    expanded: List[str] = []
    for name in tool_names:
        for member in [name, *linked_tools(name)]:
            if member in expanded:
                continue
            if member != name and not is_tool_installed(member):
                continue
            expanded.append(member)
    # Stable sort keeps the requested order within each kind.
    return sorted(expanded, key=lambda name: not is_app_bundle_tool(TOOLS[name]))


def installed_version(tool_name: str) -> Optional[str]:
    """Return the tool's installed version number, if it can be read."""
    raw = get_tool_status(tool_name, TOOLS[tool_name]).get("version") or ""
    return extract_version_from_string(raw) or raw or None


def resolve_target_version(tool_name: str) -> Optional[str]:
    """Return the release an upgrade of the tool would install.

    Uses the cached ``latest_version``, fetching and recording it when
    missing so the later upgrade installs exactly the release checked here.
    """
    tool_config = TOOLS[tool_name]
    target = tool_config.get("latest_version")
    if target:
        return str(target)
    if parse_install_type(tool_config.get("install_type")) == InstallType.NPM:
        result = check_npm_tool(tool_name, tool_config)
    else:
        result = check_script_tool(tool_name, tool_config)
    version = result.get("version")
    if result.get("status") == "error" or not version or version == "-":
        return None
    target = normalize_version(str(version))
    tool_config["latest_version"] = target
    return target


def partner_version_gap(tool_name: str, partner: str) -> Optional[str]:
    """Explain why a partner must not upgrade past this tool, or return None.

    The partner would move to its own ``latest_version``; if this tool did
    not end up on that same release (an older cached target, or a package
    manager that lags upstream), upgrading the partner would split them.
    When either version cannot be determined the partner is held back too,
    since alignment cannot be confirmed.
    """
    target = resolve_target_version(partner)
    if not target:
        return f"could not determine the release {partner} would move to"
    current = installed_version(tool_name)
    if not current:
        return f"could not read the installed version of {tool_name}"
    if normalize_version(current) == normalize_version(str(target)):
        return None
    return (
        f"{tool_name} is at {current}, not the {target} release {partner} would move to"
    )


def linked_version_mismatches() -> List[str]:
    """Describe installed partner tools that run different versions."""
    messages = []
    checked = set()
    for name in TOOLS:
        for partner in linked_tools(name):
            pair = tuple(sorted((name, partner)))
            if pair in checked:
                continue
            checked.add(pair)
            if not (is_tool_installed(name) and is_tool_installed(partner)):
                continue
            versions = {member: installed_version(member) or "" for member in pair}
            if (
                versions[pair[0]]
                and versions[pair[1]]
                and (versions[pair[0]] != versions[pair[1]])
            ):
                messages.append(
                    f"{pair[0]} {versions[pair[0]]} and {pair[1]} "
                    f"{versions[pair[1]]} differ; run 'code-aide upgrade "
                    f"{pair[0]}' to bring both to the latest release."
                )
    return messages
