"""Install implementations for script, npm, and direct-download tools."""

import hashlib
import io
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
from typing import Any, Dict, Optional

from code_aide.constants import TOOLS
from code_aide.console import command_exists, error, info, run_command, success, warning
from code_aide.versions import fetch_url


def run_install_script(
    install_url: str,
    tool_name: str,
    expected_sha256: Optional[str] = None,
    dryrun: bool = False,
) -> bool:
    """Download and run an installation script with SHA256 verification."""
    try:
        info(f"Downloading install script from: {install_url}")
        script_content, _ = fetch_url(install_url)

        if expected_sha256:
            info("Verifying script integrity with SHA256...")
            actual_sha256 = hashlib.sha256(script_content).hexdigest()

            if actual_sha256 != expected_sha256:
                error(f"SHA256 verification FAILED for {tool_name}!")
                error(f"Expected: {expected_sha256}")
                error(f"Actual:   {actual_sha256}")
                error("")
                error("The install script has changed and needs to be reviewed.")
                error("This could indicate a security issue or a legitimate update.")
                error(
                    "Please review the new script and update the SHA256 if it's safe."
                )
                return False

            success("SHA256 verification passed")
        else:
            warning(
                "No SHA256 checksum configured - script integrity cannot be verified!"
            )

        if dryrun:
            info(f"[DRYRUN] Would execute install script for {tool_name}")
            return True

        warning(f"About to execute install script for {tool_name}")
        warning("This will run with your user privileges. Press Ctrl+C to cancel.")

        bash_process = subprocess.Popen(
            ["bash"],
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _, stderr = bash_process.communicate(input=script_content)

        if bash_process.returncode == 0:
            return True

        stderr_text = stderr.decode("utf-8", errors="replace")
        error(f"Failed to install {tool_name}: {stderr_text}")
        return False
    except subprocess.CalledProcessError as exc:
        error(f"Failed to download install script for {tool_name}: {exc.stderr}")
        return False
    except Exception as exc:
        error(f"Failed to install {tool_name}: {exc}")
        return False


ARCH_MAP = {
    "x86_64": "x64",
    "amd64": "x64",
    "arm64": "arm64",
    "aarch64": "arm64",
}


def detect_os_arch() -> tuple:
    """Detect OS and architecture for direct download URLs."""
    os_name = platform.system().lower()
    if os_name not in ("linux", "darwin"):
        raise RuntimeError(f"Unsupported OS: {os_name}")

    machine = platform.machine()
    arch = ARCH_MAP.get(machine)
    if not arch:
        raise RuntimeError(f"Unsupported architecture: {machine}")

    return os_name, arch


def extract_tar_member(
    tar_file: tarfile.TarFile, member: tarfile.TarInfo, destination: str
) -> None:
    """Extract a tar member using the safest API available."""
    try:
        tar_file.extract(member, destination, filter="data")
    except TypeError:
        tar_file.extract(member, destination)


def install_direct_download(
    tool_name: str,
    tool_config: Dict[str, Any],
    dryrun: bool = False,
    install_dir_override: Optional[str] = None,
    bin_dir_override: Optional[str] = None,
) -> bool:
    """Download, extract, and install a tool via direct tarball download."""
    try:
        version = tool_config["latest_version"]
        install_url = tool_config["install_url"]
        expected_sha256 = tool_config.get("install_sha256")

        info(f"Verifying install script from: {install_url}")
        script_content, _ = fetch_url(install_url)

        if expected_sha256:
            actual_sha256 = hashlib.sha256(script_content).hexdigest()
            if actual_sha256 != expected_sha256:
                error(f"SHA256 verification FAILED for {tool_name} install script!")
                error(f"Expected: {expected_sha256}")
                error(f"Actual:   {actual_sha256}")
                error("")
                error("The install script has changed and needs to be reviewed.")
                return False
            success("Install script SHA256 verified")

        os_name, arch = detect_os_arch()
        info(f"Platform: {os_name}/{arch}")

        url_template = tool_config["download_url_template"]
        download_url = url_template.format(version=version, os=os_name, arch=arch)
        info(f"Download URL: {download_url}")

        install_dir_template = tool_config["install_dir"]
        install_dir = os.path.expanduser(install_dir_template.format(version=version))
        bin_dir = os.path.expanduser(tool_config["bin_dir"])

        if install_dir_override:
            install_dir = install_dir_override
        if bin_dir_override:
            bin_dir = bin_dir_override

        if dryrun:
            info(f"[DRYRUN] Would download: {download_url}")
            info(f"[DRYRUN] Would extract to: {install_dir}")
            info(f"[DRYRUN] Would create symlinks in: {bin_dir}")
            for link_name, target in tool_config.get("symlinks", {}).items():
                info(f"[DRYRUN]   {link_name} -> {install_dir}/{target}")
            return True

        info("Downloading package...")
        tarball_data, _ = fetch_url(download_url, timeout=120)
        success(f"Downloaded {len(tarball_data)} bytes")

        install_parent = os.path.dirname(install_dir) or "."
        os.makedirs(install_parent, exist_ok=True)
        temp_dir = tempfile.mkdtemp(
            prefix=os.path.basename(install_dir) + ".tmp-", dir=install_parent
        )

        try:
            with tarfile.open(fileobj=io.BytesIO(tarball_data), mode="r:gz") as tf:
                for member in tf.getmembers():
                    parts = member.name.split("/", 1)
                    if len(parts) <= 1 and not member.isdir():
                        continue
                    if len(parts) > 1:
                        member_name = parts[1]
                    else:
                        continue

                    normalized_name = os.path.normpath(member_name)
                    if normalized_name in ("", "."):
                        continue
                    if normalized_name.startswith("..") or os.path.isabs(
                        normalized_name
                    ):
                        continue

                    member.name = normalized_name
                    extract_tar_member(tf, member, temp_dir)

            if os.path.exists(install_dir):
                shutil.rmtree(install_dir)
            os.rename(temp_dir, install_dir)
            success(f"Extracted to {install_dir}")

        except Exception:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise

        os.makedirs(bin_dir, exist_ok=True)
        symlinks = tool_config.get("symlinks", {})
        for link_name, target_name in symlinks.items():
            link_path = os.path.join(bin_dir, link_name)
            target_path = os.path.join(install_dir, target_name)

            if os.path.lexists(link_path):
                os.remove(link_path)

            os.symlink(target_path, link_path)
            info(f"Symlink: {link_path} -> {target_path}")

        success(f"{tool_config['name']} installed successfully")
        return True

    except RuntimeError as exc:
        error(str(exc))
        return False
    except Exception as exc:
        error(f"Failed to install {tool_name}: {exc}")
        return False


def install_tool(tool_name: str, dryrun: bool = False) -> bool:
    """Install a tool based on its configuration."""
    tool_config = TOOLS.get(tool_name)
    if not tool_config:
        error(f"Unknown tool: {tool_name}")
        return False

    if dryrun:
        info(f"[DRYRUN] Checking {tool_config['name']}...")
    else:
        info(f"Installing {tool_config['name']}...")

    if command_exists(tool_config["command"]):
        tool_path = shutil.which(tool_config["command"])
        if dryrun:
            info(f"{tool_config['command']} already installed at {tool_path}")
        else:
            warning(f"{tool_config['command']} already installed at {tool_path}")
        return True

    try:
        install_type = tool_config["install_type"]

        if install_type == "npm":
            npm_package = tool_config["npm_package"]
            if dryrun:
                info(f"[DRYRUN] Would install npm package: {npm_package}")
            else:
                run_command(["npm", "install", "-g", npm_package], check=True)
                success(f"{tool_config['name']} installed successfully")
                info(tool_config["next_steps"])
                if "docs_url" in tool_config:
                    info(f"Documentation: {tool_config['docs_url']}")

        elif install_type == "script":
            install_url = tool_config["install_url"]
            expected_sha256 = tool_config.get("install_sha256")
            if run_install_script(
                install_url, tool_config["name"], expected_sha256, dryrun
            ):
                if dryrun:
                    success(f"{tool_config['name']} verification passed")
                else:
                    success(f"{tool_config['name']} installed successfully")
                    info(tool_config["next_steps"])
                    if "docs_url" in tool_config:
                        info(f"Documentation: {tool_config['docs_url']}")
            else:
                return False

        elif install_type == "direct_download":
            if install_direct_download(tool_name, tool_config, dryrun):
                if dryrun:
                    success(f"{tool_config['name']} verification passed")
                else:
                    success(f"{tool_config['name']} installed successfully")
                    info(tool_config["next_steps"])
                    if "docs_url" in tool_config:
                        info(f"Documentation: {tool_config['docs_url']}")
            else:
                return False

        return True

    except subprocess.CalledProcessError as exc:
        error(f"Failed to install {tool_config['name']}: {exc.stderr}")
        return False
    except Exception as exc:
        error(f"Failed to install {tool_config['name']}: {exc}")
        return False
