"""System package manager definitions and helpers."""

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class PackageManager(Enum):
    """Known system package managers."""

    APT = "apt-get"
    DNF = "dnf"
    YUM = "yum"
    PACMAN = "pacman"
    ZYPPER = "zypper"
    EMERGE = "emerge"
    PKG = "pkg"
    HOMEBREW = "brew"


@dataclass(frozen=True)
class PackageManagerInfo:
    """Configuration for a system package manager."""

    manager: PackageManager
    description: str
    detect_command: str
    packages: List[str]
    install_command: List[str]
    pre_install: List[List[str]] = field(default_factory=list)
    query_owner_command: List[str] = field(default_factory=list)
    remove_command: List[str] = field(default_factory=list)


_MANAGERS: List[PackageManagerInfo] = [
    PackageManagerInfo(
        manager=PackageManager.APT,
        description="Debian/Ubuntu",
        detect_command="apt-get",
        packages=["nodejs", "npm"],
        pre_install=[["sudo", "apt-get", "update"]],
        install_command=["sudo", "apt-get", "install", "-y"],
        query_owner_command=["dpkg", "-S"],
        remove_command=["sudo", "apt-get", "remove"],
    ),
    PackageManagerInfo(
        manager=PackageManager.DNF,
        description="Fedora/RHEL 8+",
        detect_command="dnf",
        packages=["nodejs", "npm"],
        install_command=["sudo", "dnf", "install", "-y"],
        query_owner_command=["rpm", "-qf"],
        remove_command=["sudo", "dnf", "remove"],
    ),
    PackageManagerInfo(
        manager=PackageManager.YUM,
        description="RHEL/CentOS 7",
        detect_command="yum",
        packages=["nodejs", "npm"],
        install_command=["sudo", "yum", "install", "-y"],
        query_owner_command=["rpm", "-qf"],
        remove_command=["sudo", "yum", "remove"],
    ),
    PackageManagerInfo(
        manager=PackageManager.PACMAN,
        description="Arch Linux",
        detect_command="pacman",
        packages=["nodejs", "npm"],
        install_command=["sudo", "pacman", "-S", "--noconfirm"],
        query_owner_command=["pacman", "-Qo"],
        remove_command=["sudo", "pacman", "-R"],
    ),
    PackageManagerInfo(
        manager=PackageManager.ZYPPER,
        description="openSUSE",
        detect_command="zypper",
        packages=["nodejs", "npm"],
        install_command=["sudo", "zypper", "install", "-y"],
        query_owner_command=["rpm", "-qf"],
        remove_command=["sudo", "zypper", "remove"],
    ),
    PackageManagerInfo(
        manager=PackageManager.EMERGE,
        description="Gentoo",
        detect_command="emerge",
        packages=["net-libs/nodejs"],
        install_command=["sudo", "emerge", "--quiet-build"],
        query_owner_command=["qfile", "-qC"],
        remove_command=["sudo", "emerge", "--unmerge"],
    ),
    PackageManagerInfo(
        manager=PackageManager.PKG,
        description="FreeBSD",
        detect_command="pkg",
        packages=["node22", "npm-node22"],
        install_command=["sudo", "pkg", "install", "-y"],
        query_owner_command=["pkg", "which", "-q"],
        remove_command=["sudo", "pkg", "delete"],
    ),
    PackageManagerInfo(
        manager=PackageManager.HOMEBREW,
        description="macOS/Linux (Homebrew)",
        detect_command="brew",
        packages=["node"],
        install_command=["brew", "install"],
        query_owner_command=["brew", "which-formula"],
        remove_command=["brew", "uninstall"],
    ),
]

PACKAGE_MANAGER_BY_ENUM = {info.manager: info for info in _MANAGERS}


def detect_package_manager() -> Optional[PackageManagerInfo]:
    """Detect the system package manager, or None on unsupported platforms."""
    if platform.system() not in ("Linux", "FreeBSD", "Darwin"):
        return None

    for info in _MANAGERS:
        if shutil.which(info.detect_command):
            return info

    return None


def _parse_package_name(manager: PackageManager, query_output: str) -> Optional[str]:
    """Extract a package name from query-owner output."""
    line = query_output.strip().split("\n")[0]
    if not line:
        return None

    if manager == PackageManager.APT:
        # dpkg -S output: "package: /path/to/file"
        return line.split(":")[0].strip() or None
    if manager == PackageManager.PACMAN:
        # pacman -Qo output: "/path is owned by package version"
        parts = line.split("is owned by")
        if len(parts) > 1:
            return parts[1].strip().rsplit(" ", 1)[0] or None
        return None
    # rpm -qf (dnf/yum/zypper): "package-version-release.arch"
    # qfile -qC (emerge): "category/package"
    # pkg which -q (FreeBSD): "package-name"
    return line.strip() or None


def query_package_owner(
    binary_path: str,
) -> tuple:
    """Identify the system package that owns a binary path.

    Returns (package_name, remove_command_str) or (None, None).
    """
    mgr = detect_package_manager()
    if not mgr or not mgr.query_owner_command or not mgr.remove_command:
        return None, None

    # brew which-formula takes the command name, not the full path.
    query_arg = (
        os.path.basename(binary_path)
        if mgr.manager == PackageManager.HOMEBREW
        else binary_path
    )

    try:
        proc = subprocess.run(
            [*mgr.query_owner_command, query_arg],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None, None
    except Exception:
        return None, None

    package = _parse_package_name(mgr.manager, proc.stdout)
    if not package:
        return None, None

    remove_cmd = " ".join([*mgr.remove_command, package])
    return package, remove_cmd
