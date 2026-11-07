"""Per-method handlers for upgrade and remove operations.

Each handler is keyed by :class:`InstallMethod` and wraps the platform-specific
command for that method. Handlers return ``True`` on success and ``False`` on a
configuration error (e.g. missing npm package). Subprocess errors raised by the
handlers are caught by their callers in :mod:`code_aide.operations`.
"""

import glob as globmod
import os
import shutil
import subprocess
from typing import Callable, Dict, Optional

from code_aide.console import (
    called_process_error_message,
    error,
    info,
    run_command,
    success,
    warning,
)
from code_aide.install import (
    get_install_script_env,
    install_direct_download,
    run_install_script,
    run_pkg_command,
)
from code_aide.app_bundle import (
    ensure_app_stopped,
    install_app_bundle,
    remove_app_bundle,
)
from code_aide.constants import TOOLS
from code_aide.path_copies import npm_prefix_for
from code_aide.install_types import (
    InstallMethod,
    InstallType,
    get_tool_install_type,
)

_OperationHandler = Callable[[str, Dict, Optional[str]], bool]


def _npm_prefix_args(cfg: Dict) -> list:
    """Return npm --prefix arguments targeting the copy that runs from PATH.

    With several npm global prefixes (such as ~/.npm-packages and Homebrew's),
    the npm first on PATH may not own the active copy; naming its prefix
    upgrades or removes that copy rather than a different one.
    """
    command_path = shutil.which(cfg["command"])
    if not command_path:
        return []
    prefix = npm_prefix_for(os.path.realpath(command_path))
    return ["--prefix", prefix] if prefix else []


def _cask_app_stopped(cfg: Dict, cask: str, action: str) -> bool:
    """Return True unless the cask's desktop app is running and stays so.

    A cask may be reached through the app tool itself or through a command
    the app provides (such as an ``example`` shim), so look up the app tool that
    names this cask to find its process.
    """
    candidates = [cfg, *TOOLS.values()]
    for app_cfg in candidates:
        if app_cfg.get("brew_cask") == cask and app_cfg.get("running_process_name"):
            return ensure_app_stopped(app_cfg, action)
    return True


# --- upgrade handlers -------------------------------------------------------


def _upgrade_brew_formula(_name: str, cfg: Dict, detail: Optional[str]) -> bool:
    if not detail:
        error(f"No brew formula detected for {cfg['name']}")
        return False
    run_command(["brew", "upgrade", detail], check=True, capture=False)
    return True


def _upgrade_brew_cask(_name: str, cfg: Dict, detail: Optional[str]) -> bool:
    if not detail:
        error(f"No brew cask detected for {cfg['name']}")
        return False
    if not _cask_app_stopped(cfg, detail, "upgrade it"):
        return False
    run_command(["brew", "upgrade", "--cask", detail], check=True, capture=False)
    return True


def _upgrade_npm(_name: str, cfg: Dict, detail: Optional[str]) -> bool:
    npm_package = detail or cfg.get("npm_package")
    if not npm_package:
        error(f"No npm package configured for {cfg['name']}")
        return False
    run_command(
        ["npm", "install", "-g", *_npm_prefix_args(cfg), f"{npm_package}@latest"],
        check=True,
    )
    return True


def _upgrade_script(name: str, cfg: Dict, _detail: Optional[str]) -> bool:
    if get_tool_install_type(cfg) == InstallType.DIRECT_DOWNLOAD:
        return install_direct_download(name, cfg)
    return run_install_script(
        cfg["install_url"],
        cfg["name"],
        cfg.get("install_sha256"),
        env=get_install_script_env(cfg),
    )


def _upgrade_direct_download(name: str, cfg: Dict, _detail: Optional[str]) -> bool:
    return install_direct_download(name, cfg)


def _upgrade_pkg(_name: str, cfg: Dict, detail: Optional[str]) -> bool:
    pkg_name = detail or cfg.get("freebsd_port")
    if not pkg_name:
        error(f"No FreeBSD port configured for {cfg['name']}")
        return False
    run_pkg_command(
        ["sudo", "pkg", "install", "-y", "-f"],
        pkg_name,
        pkg_repo=cfg.get("freebsd_pkg_repo"),
        check=True,
        capture=False,
    )
    return True


def _upgrade_system(_name: str, cfg: Dict, detail: Optional[str]) -> bool:
    if detail and detail.endswith(".app"):
        error(
            f"{cfg['name']} is provided by the desktop app at {detail}, which updates itself."
        )
        return False
    error(
        f"{cfg['name']} is managed by the system package manager. "
        "Use your package manager to upgrade it."
    )
    return False


def _upgrade_app_bundle(name: str, cfg: Dict, _detail: Optional[str]) -> bool:
    return install_app_bundle(name, cfg)


UPGRADE_HANDLERS: Dict[InstallMethod, _OperationHandler] = {
    InstallMethod.APP_BUNDLE: _upgrade_app_bundle,
    InstallMethod.BREW_FORMULA: _upgrade_brew_formula,
    InstallMethod.BREW_CASK: _upgrade_brew_cask,
    InstallMethod.NPM: _upgrade_npm,
    InstallMethod.BREW_NPM: _upgrade_npm,
    InstallMethod.SCRIPT: _upgrade_script,
    InstallMethod.DIRECT_DOWNLOAD: _upgrade_direct_download,
    InstallMethod.PKG: _upgrade_pkg,
    InstallMethod.SYSTEM: _upgrade_system,
}


# --- remove handlers --------------------------------------------------------


def _remove_brew_formula(_name: str, cfg: Dict, detail: Optional[str]) -> bool:
    if not detail:
        error(f"No brew formula detected for {cfg['name']}")
        return False
    run_command(["brew", "uninstall", detail], check=True, capture=False)
    success(f"{cfg['name']} removed successfully")
    return True


def _remove_brew_cask(_name: str, cfg: Dict, detail: Optional[str]) -> bool:
    if not detail:
        error(f"No brew cask detected for {cfg['name']}")
        return False
    if not _cask_app_stopped(cfg, detail, "remove it"):
        return False
    run_command(["brew", "uninstall", "--cask", detail], check=True, capture=False)
    success(f"{cfg['name']} removed successfully")
    return True


def _remove_npm(_name: str, cfg: Dict, detail: Optional[str]) -> bool:
    npm_package = detail or cfg.get("npm_package")
    if not npm_package:
        error(f"No npm package configured for {cfg['name']}")
        return False
    run_command(
        ["npm", "uninstall", "-g", *_npm_prefix_args(cfg), npm_package], check=True
    )
    success(f"{cfg['name']} removed successfully")
    return True


def _remove_script(name: str, cfg: Dict, _detail: Optional[str]) -> bool:
    command = cfg["command"]
    command_path = shutil.which(command)

    if not command_path:
        warning(f"Could not find {command} binary to remove")
        return True

    try:
        os.remove(command_path)
        success(f"{cfg['name']} removed successfully")
    except PermissionError:
        try:
            run_command(["sudo", "rm", command_path], check=True, capture=False)
            success(f"{cfg['name']} removed successfully")
        except subprocess.CalledProcessError as exc:
            error(
                f"Failed to remove {cfg['name']}: "
                f"{called_process_error_message(exc)}. "
                f"Please remove manually: {command_path}"
            )
            return False
    except Exception as exc:
        error(f"Failed to remove {cfg['name']}: {exc}")
        return False

    if name == "claude":
        claude_data = os.path.expanduser("~/.local/share/claude")
        if os.path.isdir(claude_data):
            shutil.rmtree(claude_data)
            info(f"Removed data directory: {claude_data}")
    return True


def _remove_direct_download(_name: str, cfg: Dict, _detail: Optional[str]) -> bool:
    bin_dir = os.path.expanduser(cfg.get("bin_dir", "~/.local/bin"))
    removed_links = set()
    for link_name in cfg.get("symlinks", {}):
        link_path = os.path.join(bin_dir, link_name)
        if os.path.lexists(link_path):
            os.remove(link_path)
            info(f"Removed symlink: {link_path}")
            removed_links.add(link_path)

    command_path = shutil.which(cfg["command"])
    if (
        command_path
        and command_path not in removed_links
        and os.path.lexists(command_path)
    ):
        os.remove(command_path)
        info(f"Removed: {command_path}")

    install_dir_template = cfg.get("install_dir")
    if install_dir_template:
        if "{version}" in install_dir_template:
            install_pattern = os.path.expanduser(
                install_dir_template.replace("{version}", "*")
            )
            paths_to_remove = sorted(globmod.glob(install_pattern))
        else:
            paths_to_remove = [os.path.expanduser(install_dir_template)]
        for install_path in paths_to_remove:
            if os.path.isdir(install_path):
                shutil.rmtree(install_path)
                info(f"Removed: {install_path}")
            elif os.path.lexists(install_path):
                os.remove(install_path)
                info(f"Removed: {install_path}")

    success(f"{cfg['name']} removed successfully")
    return True


def _remove_pkg(_name: str, cfg: Dict, detail: Optional[str]) -> bool:
    pkg_name = detail or cfg.get("freebsd_port")
    if not pkg_name:
        error(f"No FreeBSD port configured for {cfg['name']}")
        return False
    run_command(["sudo", "pkg", "delete", "-y", pkg_name], check=True, capture=False)
    success(f"{cfg['name']} removed successfully")
    return True


def _remove_system(_name: str, cfg: Dict, detail: Optional[str]) -> bool:
    if detail and detail.endswith(".app"):
        error(
            f"{cfg['name']} is provided by the desktop app at {detail}. Remove the app to remove it."
        )
        return False
    error(
        f"{cfg['name']} is managed by the system package manager. "
        "Use your package manager to remove it."
    )
    return False


def _remove_app_bundle(_name: str, cfg: Dict, _detail: Optional[str]) -> bool:
    return remove_app_bundle(cfg)


REMOVE_HANDLERS: Dict[InstallMethod, _OperationHandler] = {
    InstallMethod.APP_BUNDLE: _remove_app_bundle,
    InstallMethod.BREW_FORMULA: _remove_brew_formula,
    InstallMethod.BREW_CASK: _remove_brew_cask,
    InstallMethod.NPM: _remove_npm,
    InstallMethod.BREW_NPM: _remove_npm,
    InstallMethod.SCRIPT: _remove_script,
    InstallMethod.DIRECT_DOWNLOAD: _remove_direct_download,
    InstallMethod.PKG: _remove_pkg,
    InstallMethod.SYSTEM: _remove_system,
}
