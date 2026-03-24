"""Prerequisite and environment checks for tool installation."""

import os
import platform
import subprocess
import sys
from typing import List, Optional

from code_aide.constants import PACKAGE_MANAGERS, TOOLS
from code_aide.console import (
    command_exists,
    error,
    info,
    run_command,
    success,
    warning,
)


def detect_package_manager() -> Optional[str]:
    """Detect the Linux distribution and return package manager name."""
    if platform.system() not in ("Linux", "FreeBSD"):
        return None

    for pkg_mgr_name, config in PACKAGE_MANAGERS.items():
        if command_exists(config["detect_command"]):
            return pkg_mgr_name

    return None


def install_nodejs_npm() -> bool:
    """Install Node.js and npm using the system package manager."""
    pkg_mgr_name = detect_package_manager()

    if not pkg_mgr_name:
        error("Could not detect package manager. Please install Node.js manually:")
        for manager_name, config in PACKAGE_MANAGERS.items():
            install_cmd = " ".join(config["install_command"] + config["packages"])
            print(f"  {config['description']}: {install_cmd}")
        print("  Or visit: https://nodejs.org/")
        return False

    config = PACKAGE_MANAGERS[pkg_mgr_name]
    info(f"Detected package manager: {pkg_mgr_name} ({config['description']})")
    info("Installing Node.js and npm...")

    try:
        for pre_cmd in config["pre_install"]:
            info(f"Running: {' '.join(pre_cmd)}")
            run_command(pre_cmd, check=True, capture=False)

        install_cmd = config["install_command"] + config["packages"]
        run_command(install_cmd, check=True, capture=False)

        if not command_exists("npm"):
            error("npm installation completed but npm command not found in PATH")
            error("You may need to restart your shell or add npm to your PATH")
            return False

        success("Node.js and npm installed successfully")
        return True
    except subprocess.CalledProcessError as exc:
        stderr_msg = (
            getattr(exc, "stderr", None) or getattr(exc, "stdout", None) or str(exc)
        )
        error(f"Failed to install Node.js and npm: {stderr_msg}")
        return False
    except Exception as exc:
        error(f"Failed to install Node.js and npm: {exc}")
        return False


def check_prerequisites(
    tools_to_install: List[str], install_prereqs: bool = False
) -> None:
    """Check if prerequisites are met, optionally installing them."""
    needed_prereqs = set()
    tools_needing_node = []

    on_freebsd = platform.system() == "FreeBSD"

    for tool_name in tools_to_install:
        tool_config = TOOLS.get(tool_name)
        if not tool_config:
            continue

        # FreeBSD pkg handles all dependencies for ported tools
        if on_freebsd and tool_config.get("freebsd_port"):
            continue

        needed_prereqs.update(tool_config.get("prerequisites", []))
        if tool_config.get("min_node_version"):
            tools_needing_node.append((tool_name, tool_config["min_node_version"]))

    if "npm" in needed_prereqs:
        if not command_exists("npm"):
            if install_prereqs:
                info("npm not found, attempting to install prerequisites...")
                if not install_nodejs_npm():
                    sys.exit(1)
            else:
                error("npm is required but not installed.")
                error("Please install Node.js and npm first:")
                for manager_name, config in PACKAGE_MANAGERS.items():
                    install_cmd = " ".join(
                        config["install_command"] + config["packages"]
                    )
                    print(f"  {config['description']}: {install_cmd}")
                print("  Or visit: https://nodejs.org/")
                print("\nOr use -p/--install-prerequisites to install automatically")
                sys.exit(1)

        try:
            npm_version = run_command(["npm", "--version"]).stdout.strip()
            info(f"Prerequisites check passed (npm found: {npm_version})")
        except subprocess.CalledProcessError:
            error("Failed to check npm version")
            sys.exit(1)

    for tool_name, min_version in tools_needing_node:
        try:
            node_version_output = run_command(["node", "--version"]).stdout.strip()
            version_str = node_version_output.lstrip("v")
            version_parts = version_str.replace("-", ".").split(".")
            if not version_parts or not version_parts[0].isdigit():
                raise ValueError(f"Invalid version format: {node_version_output}")
            node_major_version = int(version_parts[0])
            if node_major_version < min_version:
                if install_prereqs:
                    warning(
                        f"Node.js version {node_version_output} is below v{min_version} "
                        f"required for {TOOLS[tool_name]['name']}"
                    )
                    warning(
                        "You may need to upgrade Node.js manually or use a Node "
                        "version manager"
                    )
                    warning("See: https://nodejs.org/ or https://github.com/nvm-sh/nvm")
                else:
                    error(
                        f"{TOOLS[tool_name]['name']} requires Node.js version "
                        f"{min_version} or higher."
                    )
                    error(f"Current version: {node_version_output}")
                    error("Please upgrade Node.js: https://nodejs.org/")
                    sys.exit(1)
        except (subprocess.CalledProcessError, ValueError, IndexError) as exc:
            error(f"Failed to check Node.js version: {exc}")
            sys.exit(1)


def is_tool_installed(tool_name: str) -> bool:
    """Check if a tool is installed."""
    tool_config = TOOLS.get(tool_name)
    if not tool_config:
        return False
    return command_exists(tool_config["command"])


def check_path_directories(tools_installed: Optional[List[str]] = None) -> None:
    """Check if binary installation directories are in PATH and warn if not.

    When *tools_installed* is given, only directories relevant to those
    tools are checked.  Otherwise a small set of common directories is used.
    """
    current_path = os.environ.get("PATH", "")
    path_entries = current_path.split(":")

    if tools_installed:
        seen: set = set()
        dirs_to_check: List[str] = []
        for tool_name in tools_installed:
            tool_config = TOOLS.get(tool_name)
            if not tool_config:
                continue
            bin_dir = tool_config.get("bin_dir")
            if bin_dir:
                expanded = os.path.expanduser(bin_dir)
                if expanded not in seen:
                    seen.add(expanded)
                    dirs_to_check.append(expanded)
    else:
        dirs_to_check = [
            os.path.expanduser("~/.local/bin"),
            os.path.expanduser("~/.npm-packages/bin"),
            os.path.expanduser("~/.amp/bin"),
        ]

    missing_dirs = []
    for dir_path in dirs_to_check:
        if dir_path not in path_entries and os.path.isdir(dir_path):
            missing_dirs.append(dir_path)

    if missing_dirs:
        warning("The following directories exist but are not in your PATH:")
        for dir_path in missing_dirs:
            print(f"  {dir_path}")
        print()
        print("To use installed tools, add to ~/.bashrc or ~/.zshrc:")
        for dir_path in missing_dirs:
            print(f'    export PATH="{dir_path}:$PATH"')
        print()
