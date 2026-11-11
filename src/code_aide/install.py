"""Install implementations for script, npm, and direct-download tools."""

import hashlib
import io
import os
import platform
import shutil
import subprocess

import tarfile
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, Optional

from code_aide.app_bundle import (
    install_app_bundle,
    is_app_bundle_tool,
    tool_location,
)
from code_aide.constants import TOOLS
from code_aide.console import (
    called_process_error_message,
    command_exists,
    error,
    info,
    run_command,
    success,
    warning,
)
from code_aide.npm_cache import npm_cache_environment, stop_process_group
from code_aide import macos_quarantine
from code_aide.install_types import InstallType, get_tool_install_type
from code_aide.release_assets import (
    install_marker_matches,
    parse_sha256sums,
    record_launchers,
    unsupported_platform_message,
    write_install_marker,
)
from code_aide.versions import check_script_tool, fetch_url

DOWNLOAD_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class InstallOutcome:
    """Result of an install, including directories that may need PATH setup."""

    succeeded: bool
    bin_dirs: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.succeeded


def get_npm_global_bin_dir() -> Optional[str]:
    """Return the directory where the active npm installs global executables."""
    try:
        prefix = run_command(["npm", "prefix", "--global"]).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None

    if not prefix:
        return None
    return os.path.join(prefix, "bin")


def run_pkg_command(
    base_cmd: list,
    pkg_name: str,
    pkg_repo: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """Run a FreeBSD pkg command, falling back without -r if the repo is unavailable."""
    if pkg_repo:
        cmd = base_cmd + ["-r", pkg_repo, pkg_name]
        try:
            run_command(cmd, **kwargs)
            return
        except subprocess.CalledProcessError:
            warning(f"Repository '{pkg_repo}' is not available. To enable it:")
            warning("  See https://wiki.freebsd.org/Ports/Quarterly for instructions")
            warning("  Then run: sudo pkg update")
            info("Falling back to default repository...")

    cmd = base_cmd + [pkg_name]
    run_command(cmd, **kwargs)


def run_install_script(
    install_url: str,
    tool_name: str,
    expected_sha256: Optional[str] = None,
    dryrun: bool = False,
    env: Optional[Dict[str, str]] = None,
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

        # Scripts may invoke npm themselves; inherit the same bounded cache.
        with npm_cache_environment(env) as script_env:
            bash_process = subprocess.Popen(
                ["bash"],
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=script_env,
                start_new_session=True,
            )
            try:
                _, stderr = bash_process.communicate(input=script_content)
            except BaseException:
                stop_process_group(bash_process)
                raise

        if bash_process.returncode == 0:
            return True

        stderr_text = stderr.decode("utf-8", errors="replace")
        error(f"Failed to install {tool_name}: {stderr_text}")
        return False
    except Exception as exc:
        error(f"Failed to install {tool_name}: {exc}")
        return False


def get_install_script_env(tool_config: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Return environment overrides for running a tool's install script."""
    path_prepend = tool_config.get("install_script_path_prepend", [])
    if not path_prepend:
        return None

    env = os.environ.copy()
    expanded_paths = [os.path.expanduser(path) for path in path_prepend]
    current_path = env.get("PATH", "")
    path_parts = [*expanded_paths]
    if current_path:
        path_parts.append(current_path)
    env["PATH"] = os.pathsep.join(path_parts)
    return env


ARCH_MAP = {
    "x86_64": "x64",
    "amd64": "x64",
    "arm64": "arm64",
    "aarch64": "arm64",
}


def detect_os_arch() -> tuple:
    """Detect OS and architecture for direct download URLs."""
    os_name = platform.system().lower()
    if os_name not in ("linux", "darwin", "freebsd"):
        raise RuntimeError(f"Unsupported OS: {os_name}")

    machine = platform.machine()
    arch = ARCH_MAP.get(machine)
    if not arch:
        raise RuntimeError(f"Unsupported architecture: {machine}")

    return os_name, arch


def fetch_upstream_sha256(
    tool_config: Dict[str, Any],
    version: str,
    os_name: str,
    arch: str,
    download_url: str,
) -> str:
    """Return the publisher's SHA256 for the download from its checksum file.

    Raises RuntimeError when the checksum file does not list the download.
    """
    sums_url = tool_config["checksums_url_template"].format(
        version=version, os=os_name, arch=arch
    )
    sums_data, _ = fetch_url(sums_url)
    filename = download_url.rsplit("/", 1)[-1]
    digest = parse_sha256sums(sums_data.decode("utf-8", errors="replace"), filename)
    if not digest:
        raise RuntimeError(f"{sums_url} does not list a checksum for {filename}")
    return digest


def fetch_download_checksum(tool_config: Dict[str, Any]) -> Optional[str]:
    """Download a direct-download tarball and return its SHA256 hex digest.

    Resolves the download URL with the cached latest_version. Returns
    None when the checksum cannot be computed (missing version, network
    failure, or unsupported platform).
    """
    version = tool_config.get("latest_version")
    if not version:
        warning("No cached latest_version; cannot compute download SHA256")
        return None
    try:
        os_name, arch = detect_os_arch()
        if unsupported_platform_message(tool_config, os_name, arch):
            return None
        url = tool_config["download_url_template"].format(
            version=version, os=os_name, arch=arch
        )
        if tool_config.get("checksums_url_template"):
            return fetch_upstream_sha256(tool_config, version, os_name, arch, url)
        info(f"Downloading {url} to compute SHA256...")
        data, _ = fetch_url(url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    except Exception as exc:
        warning(f"Could not compute download SHA256: {exc}")
        return None
    return hashlib.sha256(data).hexdigest()


def extract_tar_member(
    tar_file: tarfile.TarFile, member: tarfile.TarInfo, destination: str
) -> None:
    """Extract a tar member using the safest API available."""
    try:
        tar_file.extract(member, destination, filter="data")
    except TypeError:
        tar_file.extract(member, destination)


def _download_verified(
    tool_name: str,
    cfg: Dict[str, Any],
    version: str,
    os_name: str,
    arch: str,
    download_url: str,
) -> Optional[bytes]:
    """Download a tarball and check its SHA256; return None on mismatch.

    A publisher checksum file (``checksums_url_template``) takes precedence
    over the checksum recorded by 'code-aide update-versions'.
    """
    if cfg.get("checksums_url_template"):
        expected_sha256: Optional[str] = fetch_upstream_sha256(
            cfg, version, os_name, arch, download_url
        )
        source = "the publisher's checksum file"
    else:
        expected_sha256 = cfg.get("download_sha256")
        source = "the checksum recorded by 'code-aide update-versions'"

    info("Downloading package...")
    tarball_data, _ = fetch_url(download_url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    success(f"Downloaded {len(tarball_data)} bytes")

    if not expected_sha256:
        warning("No download SHA256 recorded - tarball integrity cannot be verified!")
        warning("Run 'code-aide update-versions -y' to record checksums.")
        return tarball_data

    actual_sha256 = hashlib.sha256(tarball_data).hexdigest()
    if actual_sha256 != expected_sha256:
        error(f"SHA256 verification FAILED for {tool_name} download!")
        error(f"Expected: {expected_sha256}")
        error(f"Actual:   {actual_sha256}")
        error(f"The downloaded tarball does not match {source}.")
        error(
            "It may be corrupted or tampered with. After reviewing, "
            "re-run 'code-aide update-versions -y' to record the new "
            "checksum."
        )
        return None
    success("Download SHA256 verification passed")
    return tarball_data


def _extract_tarball(
    tarball_data: bytes, install_dir: str, cfg: Dict[str, Any], version: str
) -> None:
    """Extract a tarball, dropping its top-level directory, into install_dir.

    Extraction goes to a sibling temporary directory that replaces
    install_dir only once it is complete.
    """
    install_parent = os.path.dirname(install_dir) or "."
    os.makedirs(install_parent, exist_ok=True)
    temp_dir = tempfile.mkdtemp(
        prefix=os.path.basename(install_dir) + ".tmp-", dir=install_parent
    )

    try:
        with tarfile.open(fileobj=io.BytesIO(tarball_data), mode="r:gz") as tf:
            for member in tf.getmembers():
                parts = member.name.split("/", 1)
                if len(parts) <= 1:
                    continue

                normalized_name = os.path.normpath(parts[1])
                if normalized_name in ("", "."):
                    continue
                if normalized_name.startswith("..") or os.path.isabs(normalized_name):
                    continue

                member.name = normalized_name
                extract_tar_member(tf, member, temp_dir)

        write_install_marker(cfg, temp_dir, version)
        if os.path.exists(install_dir):
            shutil.rmtree(install_dir)
        os.rename(temp_dir, install_dir)
        success(f"Extracted to {install_dir}")

    except Exception:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise


def install_direct_download(
    tool_name: str,
    tool_config: Dict[str, Any],
    dryrun: bool = False,
    install_dir_override: Optional[str] = None,
    bin_dir_override: Optional[str] = None,
) -> bool:
    """Download, extract, and install a tool via direct tarball download."""
    # Tarball path never runs install_url; drop any cached script checksum so a
    # stale value cannot trigger script verification in this flow.
    cfg = dict(tool_config)
    cfg.pop("install_sha256", None)

    try:
        version = cfg.get("latest_version")
        if not version:
            info("No cached version found, fetching latest version...")
            result = check_script_tool(tool_name, cfg)
            version = result.get("version")
            if not version or version == "-":
                error(
                    f"Could not determine latest version for {tool_name}. "
                    "Run 'code-aide update-versions -y' first."
                )
                return False
        os_name, arch = detect_os_arch()
        info(f"Platform: {os_name}/{arch}")
        unsupported = unsupported_platform_message(cfg, os_name, arch)
        if unsupported:
            error(f"{cfg['name']} has no download for {os_name}/{arch}: {unsupported}")
            return False

        url_template = cfg["download_url_template"]
        download_url = url_template.format(version=version, os=os_name, arch=arch)
        info(f"Download URL: {download_url}")

        install_dir_template = cfg["install_dir"]
        install_dir = os.path.expanduser(install_dir_template.format(version=version))
        bin_dir = os.path.expanduser(cfg["bin_dir"])

        if install_dir_override:
            install_dir = install_dir_override
        if bin_dir_override:
            bin_dir = bin_dir_override

        if dryrun:
            info(f"[DRYRUN] Would download: {download_url}")
            info(f"[DRYRUN] Would extract to: {install_dir}")
            info(f"[DRYRUN] Would create symlinks in: {bin_dir}")
            for link_name, target in cfg.get("symlinks", {}).items():
                info(f"[DRYRUN]   {link_name} -> {install_dir}/{target}")
            return True

        if install_marker_matches(cfg, install_dir, version):
            info(f"Version {version} is already present in {install_dir}")
        else:
            tarball_data = _download_verified(
                tool_name, cfg, version, os_name, arch, download_url
            )
            if tarball_data is None:
                return False
            _extract_tarball(tarball_data, install_dir, cfg, version)

        if not macos_quarantine.clear_quarantine(install_dir):
            return False

        os.makedirs(bin_dir, exist_ok=True)
        symlinks = cfg.get("symlinks", {})
        link_paths = []
        for link_name, target_name in symlinks.items():
            link_path = os.path.join(bin_dir, link_name)
            target_path = os.path.join(install_dir, target_name)

            if os.path.lexists(link_path):
                os.remove(link_path)

            os.symlink(target_path, link_path)
            link_paths.append(link_path)
            info(f"Symlink: {link_path} -> {target_path}")
        record_launchers(cfg, link_paths)

        # Callers report success: install_tool once per install, and
        # upgrade_tool once it has compared the versions.
        return True

    except RuntimeError as exc:
        error(str(exc))
        return False
    except Exception as exc:
        error(f"Failed to install {tool_name}: {exc}")
        return False


def install_tool(
    tool_name: str,
    dryrun: bool = False,
    force: bool = False,
    report_existing: bool = True,
) -> InstallOutcome:
    """Install a tool based on its configuration.

    With force, an existing copy of the command is reinstalled over. A
    migration passes report_existing=False: it has already removed the old
    install, so any copy still on PATH is a separate one, which the
    migration reports itself afterwards.
    """
    tool_config = TOOLS.get(tool_name)
    if not tool_config:
        error(f"Unknown tool: {tool_name}")
        return InstallOutcome(False)

    if dryrun:
        info(f"[DRYRUN] Checking {tool_config['name']}...")
    else:
        info(f"Installing {tool_config['name']}...")

    if is_app_bundle_tool(tool_config):
        existing_path = tool_location(tool_config)
    elif command_exists(tool_config["command"]):
        existing_path = shutil.which(tool_config["command"])
    else:
        existing_path = None
    if existing_path and not force:
        tool_path = existing_path
        if dryrun:
            info(f"{tool_config['command']} already installed at {tool_path}")
        else:
            warning(f"{tool_config['command']} already installed at {tool_path}")
        return InstallOutcome(True)
    if existing_path and force and report_existing:
        tool_path = existing_path
        if dryrun:
            info(
                f"[DRYRUN] Would reinstall {tool_config['command']} despite existing "
                f"binary at {tool_path}"
            )
        else:
            info(
                f"Reinstalling {tool_config['command']} despite existing binary at "
                f"{tool_path}"
            )

    if platform.system() == "FreeBSD":
        freebsd_port = tool_config.get("freebsd_port")
        if not freebsd_port:
            error(f"{tool_config['name']} is not available on FreeBSD (no port exists)")
            return InstallOutcome(False)
        pkg_repo = tool_config.get("freebsd_pkg_repo")
        if dryrun:
            repo_flag = f" -r {pkg_repo}" if pkg_repo else ""
            info(
                f"[DRYRUN] Would install FreeBSD port: "
                f"pkg install{repo_flag} {freebsd_port}"
            )
            return InstallOutcome(True)
        try:
            run_pkg_command(
                ["sudo", "pkg", "install", "-y"],
                freebsd_port,
                pkg_repo=pkg_repo,
                check=True,
            )
            success(f"{tool_config['name']} installed successfully via FreeBSD pkg")
            info(tool_config["next_steps"])
            if "docs_url" in tool_config:
                info(f"Documentation: {tool_config['docs_url']}")
            return InstallOutcome(True)
        except subprocess.CalledProcessError as exc:
            error(
                f"Failed to install {tool_config['name']}: "
                f"{called_process_error_message(exc)}"
            )
            return InstallOutcome(False)
        except Exception as exc:
            error(f"Failed to install {tool_config['name']}: {exc}")
            return InstallOutcome(False)

    try:
        install_type = get_tool_install_type(tool_config)

        if install_type == InstallType.APP_BUNDLE:
            if not install_app_bundle(tool_name, tool_config, dryrun):
                return InstallOutcome(False)
            if not dryrun:
                info(tool_config["next_steps"])
            return InstallOutcome(True)

        if install_type == InstallType.NPM:
            npm_package = tool_config["npm_package"]
            bin_dirs: tuple[str, ...] = ()
            if dryrun:
                info(f"[DRYRUN] Would install npm package: {npm_package}")
            else:
                run_command(["npm", "install", "-g", npm_package], check=True)
                if not macos_quarantine.clear_npm_quarantine(npm_package):
                    return InstallOutcome(False)
                npm_bin_dir = get_npm_global_bin_dir()
                if npm_bin_dir:
                    bin_dirs = (npm_bin_dir,)
                success(f"{tool_config['name']} installed successfully")
                info(tool_config["next_steps"])
                if "docs_url" in tool_config:
                    info(f"Documentation: {tool_config['docs_url']}")
            return InstallOutcome(True, bin_dirs)

        elif install_type == InstallType.SCRIPT:
            install_url = tool_config["install_url"]
            expected_sha256 = tool_config.get("install_sha256")
            if run_install_script(
                install_url,
                tool_config["name"],
                expected_sha256,
                dryrun,
                env=get_install_script_env(tool_config),
            ):
                if dryrun:
                    success(f"{tool_config['name']} verification passed")
                else:
                    if not macos_quarantine.clear_script_quarantine(tool_config):
                        return InstallOutcome(False)
                    success(f"{tool_config['name']} installed successfully")
                    info(tool_config["next_steps"])
                    if "docs_url" in tool_config:
                        info(f"Documentation: {tool_config['docs_url']}")
            else:
                return InstallOutcome(False)

        elif install_type == InstallType.DIRECT_DOWNLOAD:
            if install_direct_download(tool_name, tool_config, dryrun):
                if dryrun:
                    success(f"{tool_config['name']} verification passed")
                else:
                    success(f"{tool_config['name']} installed successfully")
                    info(tool_config["next_steps"])
                    if "docs_url" in tool_config:
                        info(f"Documentation: {tool_config['docs_url']}")
            else:
                return InstallOutcome(False)

            if not dryrun and tool_config.get("bin_dir"):
                return InstallOutcome(
                    True, (os.path.expanduser(tool_config["bin_dir"]),)
                )

        return InstallOutcome(True)

    except subprocess.CalledProcessError as exc:
        error(
            f"Failed to install {tool_config['name']}: "
            f"{called_process_error_message(exc)}"
        )
        return InstallOutcome(False)
    except Exception as exc:
        error(f"Failed to install {tool_config['name']}: {exc}")
        return InstallOutcome(False)
