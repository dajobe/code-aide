"""macOS application bundle installs (``install_type: "app_bundle"``).

A desktop app has no command on PATH, so these tools are located through
an activation symlink (``app_link``, e.g. ``~/Applications/Example.app``)
or the usual application folders. Each release is unpacked into its own
versioned directory and activated by repointing the symlink, so a switch is
atomic and the previous version stays available until cleaned.

Replacing a running app's bundle is unsafe, so installs, upgrades, and
removals first check for the running process and offer to quit it.
"""

import base64
import hashlib
import os
import platform
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from typing import Any, Dict, List, Optional

from code_aide import __version__
from code_aide.console import error, info, success, warning
from code_aide.detection_types import DetectedInstallInfo
from code_aide.install_types import InstallMethod, InstallType, parse_install_type

DOWNLOAD_TIMEOUT_SECONDS = 120
QUIT_TIMEOUT_SECONDS = 30
_HOMEBREW_PREFIXES = ("/opt/homebrew", "/usr/local", "/home/linuxbrew/.linuxbrew")
_MAC_ARCH = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "amd64": "x64"}


def is_app_bundle_tool(tool_config: Dict[str, Any]) -> bool:
    """Return True when the tool is installed as a macOS app bundle."""
    return parse_install_type(tool_config.get("install_type")) == (
        InstallType.APP_BUNDLE
    )


def app_dirs() -> tuple[str, str]:
    """Return the application folders Homebrew casks install into."""
    return ("/Applications", os.path.expanduser("~/Applications"))


def cask_app_dir() -> str:
    """Return the folder Homebrew installs cask apps into.

    That is /Applications unless ``HOMEBREW_CASK_OPTS`` sets ``--appdir``.
    """
    words = shlex.split(os.environ.get("HOMEBREW_CASK_OPTS", ""))
    for index, word in enumerate(words):
        if word.startswith("--appdir="):
            return os.path.expanduser(word.split("=", 1)[1]).rstrip("/")
        if word == "--appdir" and index + 1 < len(words):
            return os.path.expanduser(words[index + 1]).rstrip("/")
    return "/Applications"


def is_cask_app(
    app_bundle: str, cask: Optional[str], cask_bundle_name: Optional[str]
) -> bool:
    """Return True when the bundle is the app the installed cask puts down.

    The bundle must have the cask's bundle name and sit in the folder
    Homebrew installs casks into; another app in that folder (a nightly
    build, say) is not the cask's even when the cask is installed.
    """
    return bool(
        cask
        and cask_bundle_name
        and os.path.basename(app_bundle) == cask_bundle_name
        and os.path.dirname(app_bundle) == cask_app_dir()
        and is_brew_cask_installed(cask)
    )


def is_brew_cask_installed(cask: str) -> bool:
    """Return True when Homebrew has the named cask installed.

    Checks the Caskroom directory directly so status checks do not pay for
    a ``brew`` subprocess.
    """
    prefixes = [os.environ.get("HOMEBREW_PREFIX", ""), *_HOMEBREW_PREFIXES]
    return any(
        prefix and os.path.isdir(os.path.join(prefix, "Caskroom", cask))
        for prefix in prefixes
    )


def _candidates(tool_config: Dict[str, Any]) -> List[str]:
    paths = [os.path.expanduser(tool_config["app_link"])]
    for directory in (*app_dirs(), cask_app_dir()):
        paths.append(os.path.join(directory, tool_config["app_bundle_name"]))
    return list(dict.fromkeys(paths))


def tool_location(tool_config: Dict[str, Any]) -> Optional[str]:
    """Return where the tool is installed: its command path or app bundle."""
    if not is_app_bundle_tool(tool_config):
        return shutil.which(tool_config["command"])
    for path in _candidates(tool_config):
        if os.path.isdir(path):
            return path
    return None


def bundle_version(bundle_path: str) -> Optional[str]:
    """Return an app bundle's CFBundleShortVersionString, if readable."""
    try:
        with open(os.path.join(bundle_path, "Contents", "Info.plist"), "rb") as f:
            version = plistlib.load(f).get("CFBundleShortVersionString")
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None
    return version if isinstance(version, str) else None


def versions_root(tool_config: Dict[str, Any]) -> str:
    """Return the directory holding the versioned install directories."""
    return os.path.dirname(os.path.expanduser(tool_config["install_dir"]))


def _version_bundle(tool_config: Dict[str, Any], version: str) -> str:
    install_dir = os.path.expanduser(tool_config["install_dir"].format(version=version))
    return os.path.join(install_dir, tool_config["app_bundle_name"])


def detect_app_install(tool_config: Dict[str, Any]) -> DetectedInstallInfo:
    """Detect how the app bundle was installed.

    A bundle inside ``versions_root`` is managed by code-aide. A bundle in an
    application folder owned by the configured Homebrew cask is the cask's;
    anything else is a user-managed desktop app.
    """
    path = tool_location(tool_config)
    if not path:
        return {"method": None, "detail": None}
    real_path = os.path.realpath(path)
    root = os.path.realpath(versions_root(tool_config))
    if real_path.startswith(root + os.sep):
        return {"method": InstallMethod.APP_BUNDLE, "detail": real_path}
    cask = tool_config.get("brew_cask")
    if cask and is_cask_app(path, cask, tool_config["app_bundle_name"]):
        return {"method": InstallMethod.BREW_CASK, "detail": cask}
    return {"method": InstallMethod.SYSTEM, "detail": real_path}


# --- running-app guard ------------------------------------------------------


def app_is_running(tool_config: Dict[str, Any]) -> Optional[bool]:
    """Return whether the app runs for this user; None when the check fails."""
    process_name = tool_config.get("running_process_name")
    if not process_name:
        return False
    try:
        result = subprocess.run(
            ["pgrep", "-x", "-U", str(os.getuid()), re.escape(process_name)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def quit_app(tool_config: Dict[str, Any]) -> bool:
    """Ask the app to quit and wait for it to exit."""
    bundle_id = tool_config["bundle_id"]
    try:
        subprocess.run(
            ["osascript", "-e", f'tell application id "{bundle_id}" to quit'],
            capture_output=True,
            text=True,
            timeout=QUIT_TIMEOUT_SECONDS,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    deadline = time.monotonic() + QUIT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if app_is_running(tool_config) is False:
            return True
        time.sleep(0.5)
    return False


def ensure_app_stopped(tool_config: Dict[str, Any], action: str) -> bool:
    """Return True once the app is not running, offering to quit it.

    Without a terminal to ask on, a running app is left alone and the
    action is skipped.
    """
    running = app_is_running(tool_config)
    if running is False:
        return True
    name = tool_config["name"]
    if running is None:
        error(f"Could not check whether {name} is running; not trying to {action}.")
        return False
    if not sys.stdin.isatty():
        warning(f"{name} is running. Quit it and rerun to {action}.")
        return False
    answer = input(
        f"{name} is running. Quit it to {action}? "
        "Quitting stops its agent turns. [y/N] "
    )
    if answer.strip().lower() not in ("y", "yes"):
        warning(f"Left {name} running; did not {action}.")
        return False
    info(f"Quitting {name}...")
    if quit_app(tool_config):
        success(f"{name} has quit")
        return True
    error(
        f"{name} did not quit within {QUIT_TIMEOUT_SECONDS}s; not trying to {action}."
    )
    return False


# --- download and verification ----------------------------------------------


def _download_to_file(url: str, destination: str) -> str:
    """Stream a URL to a file and return the SHA-512 digest as hex."""
    digest = hashlib.sha512()
    request = urllib.request.Request(
        url, headers={"User-Agent": f"code-aide/{__version__}"}
    )
    with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as resp:
        with open(destination, "wb") as handle:
            while chunk := resp.read(1 << 20):
                digest.update(chunk)
                handle.write(chunk)
    return digest.hexdigest()


def parse_sha512_manifest(text: str, filename: str) -> Optional[str]:
    """Return the hex SHA-512 for a file in an electron-builder manifest.

    The manifest (``latest-mac.yml``) lists ``- url: <file>`` entries each
    followed by a base64 ``sha512:`` line.
    """
    match = re.search(
        rf"-\s*url:\s*['\"]?{re.escape(filename)}['\"]?\s*\n\s*sha512:\s*(\S+)",
        text,
    )
    if not match:
        return None
    try:
        return base64.b64decode(match.group(1), validate=True).hex()
    except ValueError:
        return None


def _expected_sha512(tool_config: Dict[str, Any], version: str, url: str) -> str:
    from code_aide.versions import fetch_url

    manifest_url = tool_config["checksum_manifest_url_template"].format(version=version)
    data, _ = fetch_url(manifest_url)
    filename = url.rsplit("/", 1)[-1]
    digest = parse_sha512_manifest(data.decode("utf-8", errors="replace"), filename)
    if not digest:
        raise RuntimeError(f"{manifest_url} does not list a checksum for {filename}")
    return digest


def _resolve_version(tool_name: str, tool_config: Dict[str, Any]) -> Optional[str]:
    version = tool_config.get("latest_version")
    if version:
        return str(version)
    from code_aide.versions import check_script_tool

    info("No cached version found, fetching latest version...")
    version = check_script_tool(tool_name, tool_config).get("version")
    if not version or version == "-":
        error(
            f"Could not determine latest version for {tool_name}. "
            "Run 'code-aide update-versions -y' first."
        )
        return None
    return str(version)


def signature_ok(bundle: str) -> bool:
    """Return True when the bundle's code signature verifies."""
    result = subprocess.run(
        ["codesign", "--verify", "--strict", bundle],
        capture_output=True,
        check=False,
        stdin=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _stage(
    tool_config: Dict[str, Any],
    version: str,
    url: str,
    expected_sha512: str,
    staging: str,
) -> Optional[str]:
    """Download, verify and unpack a release into ``staging``.

    Returns the staged bundle path, or None when verification fails. Nothing
    outside ``staging`` is touched, so a running app is unaffected.
    """
    archive = os.path.join(staging, "download.zip")
    info(f"Downloading {url}...")
    actual = _download_to_file(url, archive)
    if actual != expected_sha512:
        error(f"SHA-512 verification FAILED for {url}")
        error(f"Expected: {expected_sha512}")
        error(f"Actual:   {actual}")
        return None
    success("Download SHA-512 verification passed")

    unpacked = os.path.join(staging, "unpacked")
    # ditto keeps the bundle's symlinks, permissions and extended
    # attributes, which zipfile does not.
    subprocess.run(["ditto", "-x", "-k", archive, unpacked], check=True)
    bundle = os.path.join(unpacked, tool_config["app_bundle_name"])
    found = bundle_version(bundle)
    if found != version:
        error(f"Unpacked bundle reports version {found!r}, expected {version}")
        return None
    if not signature_ok(bundle):
        error(f"Code signature verification FAILED for {bundle}")
        return None
    success("Code signature verified")
    return bundle


def _move_into_place(staged_bundle: str, bundle: str, staging: str) -> None:
    """Install a staged bundle as ``bundle``, keeping any old copy on failure."""
    install_dir = os.path.dirname(bundle)
    backup = os.path.join(staging, "previous")
    had_previous = os.path.lexists(install_dir)
    if had_previous:
        os.rename(install_dir, backup)
    try:
        os.makedirs(install_dir)
        os.rename(staged_bundle, bundle)
    except OSError:
        shutil.rmtree(install_dir, ignore_errors=True)
        if had_previous:
            os.rename(backup, install_dir)
        raise
    info(f"Unpacked to {install_dir}")


def _repoint_link(link: str, target: str) -> None:
    """Atomically point ``link`` at ``target``."""
    link_dir = os.path.dirname(link)
    os.makedirs(link_dir, exist_ok=True)
    # A unique name, so concurrent installs cannot swap each other's link.
    temp_dir = tempfile.mkdtemp(prefix=".code-aide-link.", dir=link_dir)
    temp_link = os.path.join(temp_dir, "link")
    try:
        os.symlink(target, temp_link)
        os.replace(temp_link, link)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def install_app_bundle(
    tool_name: str, tool_config: Dict[str, Any], dryrun: bool = False
) -> bool:
    """Install or upgrade the app bundle to the latest known version.

    The new release is downloaded and verified into a staging directory
    first. Only after the running app (if any) has quit is anything in the
    versions directory replaced and the link switched.
    """
    name = tool_config["name"]
    if platform.system() != "Darwin":
        error(f"{name} is only available on macOS")
        return False
    link = os.path.expanduser(tool_config["app_link"])
    if os.path.lexists(link) and not os.path.islink(link):
        error(f"Refusing to replace {link}: it is not a symlink managed by code-aide")
        return False

    version = _resolve_version(tool_name, tool_config)
    if not version:
        return False
    arch = _MAC_ARCH.get(platform.machine())
    if not arch:
        error(f"Unsupported architecture: {platform.machine()}")
        return False
    url = tool_config["download_url_template"].format(version=version, arch=arch)
    bundle = _version_bundle(tool_config, version)

    if (
        os.path.realpath(link) == os.path.realpath(bundle)
        and bundle_version(bundle) == version
        and (dryrun or signature_ok(bundle))
    ):
        info(f"{name} {version} is already active at {link}")
        return True

    if dryrun:
        info(f"[DRYRUN] Would download: {url}")
        info(f"[DRYRUN] Would unpack to: {os.path.dirname(bundle)}")
        info(f"[DRYRUN] Would point {link} -> {bundle}")
        return True

    root = versions_root(tool_config)
    staging: Optional[str] = None
    try:
        staged_bundle: Optional[str] = None
        if bundle_version(bundle) == version and signature_ok(bundle):
            info(f"Version {version} is already unpacked at {os.path.dirname(bundle)}")
        else:
            if bundle_version(bundle) == version:
                warning(f"{bundle} failed its signature check; downloading again")
            expected = _expected_sha512(tool_config, version, url)
            os.makedirs(root, exist_ok=True)
            staging = tempfile.mkdtemp(prefix=f".v{version}.", dir=root)
            staged_bundle = _stage(tool_config, version, url, expected, staging)
            if staged_bundle is None:
                return False

        # Checked after the download, which may have taken a while, and
        # before anything the running app could be using is replaced.
        if not ensure_app_stopped(tool_config, f"switch {name} to {version}"):
            return False
        if staged_bundle and staging:
            _move_into_place(staged_bundle, bundle, staging)
        _repoint_link(link, bundle)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        error(f"Failed to install {name}: {exc}")
        return False
    finally:
        if staging:
            shutil.rmtree(staging, ignore_errors=True)

    success(f"{name} {version} is active at {link}")
    return True


def remove_app_bundle(tool_config: Dict[str, Any]) -> bool:
    """Remove the activation symlink and every managed version."""
    name = tool_config["name"]
    if not ensure_app_stopped(tool_config, f"remove {name}"):
        return False
    link = os.path.expanduser(tool_config["app_link"])
    if os.path.islink(link):
        os.remove(link)
        info(f"Removed symlink: {link}")
    root = versions_root(tool_config)
    pattern = re.compile(
        "^"
        + re.escape(os.path.basename(tool_config["install_dir"])).replace(
            re.escape("{version}"), ".+"
        )
        + "$"
    )
    if os.path.isdir(root):
        for entry in sorted(os.listdir(root)):
            path = os.path.join(root, entry)
            if pattern.match(entry) and os.path.isdir(path):
                shutil.rmtree(path)
                info(f"Removed: {path}")
    success(f"{name} removed successfully")
    return True
