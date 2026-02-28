"""Upgrade and remove operations for managed tools."""

import glob as globmod
import os
import shutil
import subprocess
import sys
from typing import List

from code_aide.constants import TOOLS
from code_aide.detection import detect_install_method
from code_aide.install import install_direct_download, run_install_script
from code_aide.console import error, info, run_command, success, warning
from code_aide.prereqs import is_tool_installed


def upgrade_tool(tool_name: str) -> bool:
    """Upgrade a tool based on its configuration."""
    tool_config = TOOLS.get(tool_name)
    if not tool_config:
        error(f"Unknown tool: {tool_name}")
        return False

    if not is_tool_installed(tool_name):
        warning(f"{tool_config['name']} is not installed. Use 'install' command first.")
        return False

    install_info = detect_install_method(tool_name)
    method = install_info["method"]
    detail = install_info["detail"]

    info(f"Upgrading {tool_config['name']} (installed via {method})...")

    try:
        if method == "brew_formula":
            run_command(["brew", "upgrade", detail], check=True, capture=False)
            success(f"{tool_config['name']} upgraded successfully")

        elif method == "brew_cask":
            run_command(
                ["brew", "upgrade", "--cask", detail], check=True, capture=False
            )
            success(f"{tool_config['name']} upgraded successfully")

        elif method in ("npm", "brew_npm"):
            npm_package = detail or tool_config.get("npm_package")
            if not npm_package:
                error(f"No npm package configured for {tool_config['name']}")
                return False
            run_command(["npm", "install", "-g", f"{npm_package}@latest"], check=True)
            success(f"{tool_config['name']} upgraded successfully")

        elif method == "script":
            install_url = tool_config["install_url"]
            expected_sha256 = tool_config.get("install_sha256")
            if run_install_script(install_url, tool_config["name"], expected_sha256):
                success(f"{tool_config['name']} upgraded successfully")
            else:
                return False

        elif method == "direct_download":
            if not install_direct_download(tool_name, tool_config):
                return False

        elif method == "self_managed":
            upgrade_cmd = tool_config.get("upgrade_command")
            if not upgrade_cmd:
                error(f"No upgrade_command configured for {tool_config['name']}")
                return False
            run_command(upgrade_cmd, check=True, capture=False)
            success(f"{tool_config['name']} upgraded successfully")

        elif method == "system":
            error(
                f"{tool_config['name']} is managed by the system package manager. "
                "Use your package manager to upgrade it."
            )
            return False

        else:
            error(
                f"Don't know how to upgrade {tool_config['name']} "
                f"(install method: {method})"
            )
            return False

        return True

    except subprocess.CalledProcessError as exc:
        error(f"Failed to upgrade {tool_config['name']}: {exc.stderr}")
        return False
    except Exception as exc:
        error(f"Failed to upgrade {tool_config['name']}: {exc}")
        return False


def remove_tool(tool_name: str) -> bool:
    """Remove a tool based on its configuration."""
    tool_config = TOOLS.get(tool_name)
    if not tool_config:
        error(f"Unknown tool: {tool_name}")
        return False

    if not is_tool_installed(tool_name):
        warning(f"{tool_config['name']} is not installed.")
        return True

    install_info = detect_install_method(tool_name)
    method = install_info["method"]
    detail = install_info["detail"]

    info(f"Removing {tool_config['name']} (installed via {method})...")

    try:
        if method == "brew_formula":
            run_command(["brew", "uninstall", detail], check=True, capture=False)
            success(f"{tool_config['name']} removed successfully")

        elif method == "brew_cask":
            run_command(
                ["brew", "uninstall", "--cask", detail], check=True, capture=False
            )
            success(f"{tool_config['name']} removed successfully")

        elif method in ("npm", "brew_npm"):
            npm_package = detail or tool_config.get("npm_package")
            if not npm_package:
                error(f"No npm package configured for {tool_config['name']}")
                return False
            run_command(["npm", "uninstall", "-g", npm_package], check=True)
            success(f"{tool_config['name']} removed successfully")

        elif method == "script":
            command = tool_config["command"]
            command_path = shutil.which(command)

            if command_path:
                try:
                    os.remove(command_path)
                    success(f"{tool_config['name']} removed successfully")
                except PermissionError:
                    try:
                        run_command(
                            ["sudo", "rm", command_path], check=True, capture=False
                        )
                        success(f"{tool_config['name']} removed successfully")
                    except subprocess.CalledProcessError as exc:
                        error(
                            f"Failed to remove {tool_config['name']}: {exc.stderr}. "
                            f"Please remove manually: {command_path}"
                        )
                        return False
                except Exception as exc:
                    error(f"Failed to remove {tool_config['name']}: {exc}")
                    return False
            else:
                warning(f"Could not find {command} binary to remove")
                return True

        elif method == "direct_download":
            bin_dir = os.path.expanduser(tool_config.get("bin_dir", "~/.local/bin"))
            removed_links = set()
            for link_name in tool_config.get("symlinks", {}):
                link_path = os.path.join(bin_dir, link_name)
                if os.path.lexists(link_path):
                    os.remove(link_path)
                    info(f"Removed symlink: {link_path}")
                    removed_links.add(link_path)

            command_path = shutil.which(tool_config["command"])
            if (
                command_path
                and command_path not in removed_links
                and os.path.lexists(command_path)
            ):
                os.remove(command_path)
                info(f"Removed: {command_path}")

            install_dir_template = tool_config.get("install_dir")
            if install_dir_template:
                if "{version}" in install_dir_template:
                    install_pattern = os.path.expanduser(
                        install_dir_template.replace("{version}", "*")
                    )
                    for install_path in sorted(globmod.glob(install_pattern)):
                        if os.path.isdir(install_path):
                            shutil.rmtree(install_path)
                            info(f"Removed: {install_path}")
                        elif os.path.lexists(install_path):
                            os.remove(install_path)
                            info(f"Removed: {install_path}")
                else:
                    install_path = os.path.expanduser(install_dir_template)
                    if os.path.isdir(install_path):
                        shutil.rmtree(install_path)
                        info(f"Removed: {install_path}")
                    elif os.path.lexists(install_path):
                        os.remove(install_path)
                        info(f"Removed: {install_path}")

            success(f"{tool_config['name']} removed successfully")

        elif method == "self_managed":
            command = tool_config["command"]
            command_path = shutil.which(command)
            removed_any = False
            if command_path:
                real_path = os.path.realpath(command_path)
                remove_paths = [command_path]
                if real_path != command_path:
                    remove_paths.append(real_path)

                for path in remove_paths:
                    if not os.path.lexists(path):
                        continue
                    is_link = os.path.islink(path)
                    if os.path.isdir(path) and not is_link:
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    if is_link:
                        info(f"Removed symlink: {path}")
                    else:
                        info(f"Removed: {path}")
                    removed_any = True

            if removed_any:
                success(f"{tool_config['name']} removed successfully")
            else:
                warning(f"Could not find {command} binary to remove")

        elif method == "system":
            error(
                f"{tool_config['name']} is managed by the system package manager. "
                "Use your package manager to remove it."
            )
            return False

        else:
            error(
                f"Don't know how to remove {tool_config['name']} "
                f"(install method: {method})"
            )
            return False

        return True

    except subprocess.CalledProcessError as exc:
        error(f"Failed to remove {tool_config['name']}: {exc.stderr}")
        return False
    except Exception as exc:
        error(f"Failed to remove {tool_config['name']}: {exc}")
        return False


def validate_tools(tools: List[str]) -> None:
    """Validate that all tool names are valid."""
    invalid_tools = [tool for tool in tools if tool not in TOOLS]

    if invalid_tools:
        error(f"Invalid tool name(s): {', '.join(invalid_tools)}")
        available = ", ".join(TOOLS.keys())
        print(f"\nAvailable tools: {available}")
        sys.exit(1)
