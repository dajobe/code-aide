"""Shared constants and mutable tool configuration for CLI modules."""

from typing import Any, Dict

from code_aide.config import load_tools_config


class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    BOLD = "\033[1m"
    NC = "\033[0m"


PACKAGE_MANAGERS: Dict[str, Dict[str, Any]] = {
    "apt-get": {
        "detect_command": "apt-get",
        "packages": ["nodejs", "npm"],
        "pre_install": [["sudo", "apt-get", "update"]],
        "install_command": ["sudo", "apt-get", "install", "-y"],
        "description": "Debian/Ubuntu",
    },
    "dnf": {
        "detect_command": "dnf",
        "packages": ["nodejs", "npm"],
        "pre_install": [],
        "install_command": ["sudo", "dnf", "install", "-y"],
        "description": "Fedora/RHEL 8+",
    },
    "yum": {
        "detect_command": "yum",
        "packages": ["nodejs", "npm"],
        "pre_install": [],
        "install_command": ["sudo", "yum", "install", "-y"],
        "description": "RHEL/CentOS 7",
    },
    "pacman": {
        "detect_command": "pacman",
        "packages": ["nodejs", "npm"],
        "pre_install": [],
        "install_command": ["sudo", "pacman", "-S", "--noconfirm"],
        "description": "Arch Linux",
    },
    "zypper": {
        "detect_command": "zypper",
        "packages": ["nodejs", "npm"],
        "pre_install": [],
        "install_command": ["sudo", "zypper", "install", "-y"],
        "description": "openSUSE",
    },
    "emerge": {
        "detect_command": "emerge",
        "packages": ["net-libs/nodejs"],
        "pre_install": [],
        "install_command": ["sudo", "emerge", "--quiet-build"],
        "description": "Gentoo",
    },
    "pkg": {
        "detect_command": "pkg",
        "packages": ["node22", "npm-node22"],
        "pre_install": [],
        "install_command": ["sudo", "pkg", "install", "-y"],
        "description": "FreeBSD",
    },
}


TOOLS: Dict[str, Dict[str, Any]] = load_tools_config()
