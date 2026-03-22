"""Typed install type and method helpers."""

from enum import Enum
from typing import Mapping, Optional, TypeAlias


class _ValueEnum(str, Enum):
    """Enum that stringifies to its value."""

    def __str__(self) -> str:
        return self.value


class InstallType(_ValueEnum):
    """Configured install types from tool definitions."""

    NPM = "npm"
    SCRIPT = "script"
    DIRECT_DOWNLOAD = "direct_download"


class InstallMethod(_ValueEnum):
    """Detected local install methods."""

    NPM = "npm"
    BREW_NPM = "brew_npm"
    BREW_FORMULA = "brew_formula"
    BREW_CASK = "brew_cask"
    SYSTEM = "system"
    SCRIPT = "script"
    DIRECT_DOWNLOAD = "direct_download"


InstallTypeInput: TypeAlias = InstallType | str
InstallMethodInput: TypeAlias = InstallMethod | InstallType | str | None
ToolConfigLike: TypeAlias = Mapping[str, object]


_INSTALL_METHOD_BY_TYPE = {
    InstallType.NPM: InstallMethod.NPM,
    InstallType.SCRIPT: InstallMethod.SCRIPT,
    InstallType.DIRECT_DOWNLOAD: InstallMethod.DIRECT_DOWNLOAD,
}


def parse_install_type(value: object) -> Optional[InstallType]:
    """Return a typed install type when the input is recognized."""
    if isinstance(value, InstallType):
        return value
    if isinstance(value, str):
        try:
            return InstallType(value)
        except ValueError:
            return None
    return None


def require_install_type(value: object) -> InstallType:
    """Return a typed install type or raise for unknown input."""
    install_type = parse_install_type(value)
    if install_type is None:
        raise ValueError(f"Unknown install type: {value!r}")
    return install_type


def install_method_from_type(value: InstallTypeInput) -> InstallMethod:
    """Map a configured install type to its matching managed method."""
    return _INSTALL_METHOD_BY_TYPE[require_install_type(value)]


def parse_install_method(value: InstallMethodInput) -> Optional[InstallMethod]:
    """Return a typed detected method when the input is recognized."""
    if isinstance(value, InstallMethod):
        return value
    if isinstance(value, InstallType):
        return install_method_from_type(value)
    if isinstance(value, str):
        install_type = parse_install_type(value)
        if install_type is not None:
            return install_method_from_type(install_type)
        try:
            return InstallMethod(value)
        except ValueError:
            return None
    return None


def get_tool_install_type(tool_config: ToolConfigLike) -> InstallType:
    """Return the typed configured install type for a tool config."""
    return require_install_type(tool_config["install_type"])
