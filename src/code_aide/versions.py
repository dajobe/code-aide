"""Version parsing and upstream update-check helpers."""

import email.utils
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from code_aide import __version__
from code_aide.constants import Colors


def fetch_url(url: str, timeout: int = 30) -> tuple:
    """Fetch content from a URL. Returns (bytes, last_modified_str)."""
    req = urllib.request.Request(
        url, headers={"User-Agent": f"code-aide/{__version__}"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        content = response.read()
        last_modified = response.headers.get("Last-Modified")
        return content, last_modified


def parse_http_date(date_str: Optional[str]) -> Optional[str]:
    """Parse an HTTP date header into YYYY-MM-DD format."""
    if not date_str:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(date_str)
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        return None


def parse_iso_date(date_str: Optional[str]) -> Optional[str]:
    """Parse an ISO 8601 date string into YYYY-MM-DD format."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def normalize_version(version: str) -> str:
    """Normalize a version string for storage and comparison."""
    return version.lstrip("v")


def status_version_matches_latest(status_version: str, latest_version: str) -> bool:
    """Return True when a tool-reported version string matches latest_version."""
    if not status_version or not latest_version:
        return False

    latest_norm = normalize_version(latest_version.strip())
    status_text = status_version.strip()

    if normalize_version(status_text) == latest_norm:
        return True

    patterns = [
        r"\d{4}\.\d{2}\.\d{2}-[0-9a-f]+",
        r"[vV]?\d+(?:\.\d+)+(?:[-+][0-9A-Za-z._-]+)?",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, status_text):
            if normalize_version(match.group(0)) == latest_norm:
                return True

    return False


def extract_version_from_string(version_string: str) -> Optional[str]:
    """Extract a normalized version number from a tool version output string."""
    if not version_string:
        return None

    text = version_string.strip()

    normalized = normalize_version(text)
    if re.match(r"^\d+(?:\.\d+)+$", normalized):
        return normalized

    patterns = [
        r"\d{4}\.\d{2}\.\d{2}-[0-9a-f]+",
        r"[vV]?\d+(?:\.\d+)+(?:[-+][0-9A-Za-z._-]+)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return normalize_version(match.group(0))

    return None


def version_is_newer(version_a: str, version_b: str) -> bool:
    """Return True if version_a is strictly newer than version_b."""

    def parse_components(version: str) -> list:
        parts = re.split(r"[.\-]", version)
        result = []
        for part in parts:
            try:
                result.append((0, int(part)))
            except ValueError:
                result.append((1, part))
        return result

    a_parts = parse_components(version_a)
    b_parts = parse_components(version_b)

    return a_parts > b_parts


def check_npm_tool(
    tool_name: str, tool_config: Dict[str, Any], verbose: bool = False
) -> Dict[str, Any]:
    """Check an npm tool for the latest version and publish date."""
    package = tool_config["npm_package"]
    result: Dict[str, Any] = {
        "tool": tool_name,
        "type": "npm",
        "version": "-",
        "date": "-",
        "status": "unknown",
        "update": None,
    }

    try:
        url = f"https://registry.npmjs.org/{package}"
        raw, _ = fetch_url(url)
        data = json.loads(raw)

        latest_version = data.get("dist-tags", {}).get("latest", "?")
        result["version"] = latest_version

        time_info = data.get("time", {})
        publish_date = time_info.get(latest_version)
        if publish_date:
            result["date"] = parse_iso_date(publish_date) or "-"

        result["status"] = "ok"
    except Exception as exc:
        result["status"] = "error"
        if verbose:
            result["version"] = f"error: {exc}"

    return result


def extract_script_date(
    version_info: Optional[str], last_modified: Optional[str]
) -> Optional[str]:
    """Extract a date from a script tool's version string or HTTP header."""
    if version_info:
        epoch_match = re.search(r"\.(\d{10,})", version_info)
        if epoch_match:
            try:
                dt = datetime.fromtimestamp(int(epoch_match.group(1)), tz=timezone.utc)
                return dt.strftime("%Y-%m-%d")
            except (ValueError, OSError):
                pass
        match = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", version_info)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return parse_http_date(last_modified)


def extract_script_version(
    tool_name: str,
    tool_config: Dict[str, Any],
    script_content: bytes,
) -> Optional[str]:
    """Try to extract a version string from script content or version URL."""
    version_url = tool_config.get("version_url")
    if version_url:
        try:
            version_data, _ = fetch_url(version_url)
            version_str = version_data.decode("utf-8").strip()
            if "<" not in version_str and len(version_str) < 50:
                if not version_str.startswith("v"):
                    version_str = f"v{version_str}"
                return version_str
        except Exception:
            pass

    text = script_content.decode("utf-8", errors="replace")

    if tool_name == "cursor":
        match = re.search(r"(\d{4}\.\d{2}\.\d{2}-[0-9a-f]+)", text)
        if match:
            return match.group(1)

    for pattern in [
        r'VERSION="([^"]+)"',
        r"VERSION='([^']+)'",
        r"VERSION=(\S+)",
    ]:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    return None


def check_script_tool(
    tool_name: str, tool_config: Dict[str, Any], verbose: bool = False
) -> Dict[str, Any]:
    """Check a script/direct_download tool for SHA256 changes, version, and date."""
    install_url = tool_config["install_url"]
    current_sha256 = tool_config.get("install_sha256", "")

    result: Dict[str, Any] = {
        "tool": tool_name,
        "type": tool_config.get("install_type", "script"),
        "version": "-",
        "date": "-",
        "sha256_current": current_sha256[:12] + "..." if current_sha256 else "none",
        "sha256_latest": "-",
        "status": "unknown",
        "update": None,
    }

    try:
        script_content, last_modified = fetch_url(install_url)
        actual_sha256 = hashlib.sha256(script_content).hexdigest()

        if verbose:
            result["sha256_current"] = current_sha256 or "none"
            result["sha256_latest"] = actual_sha256
        else:
            result["sha256_latest"] = actual_sha256[:12] + "..."

        version_info = extract_script_version(tool_name, tool_config, script_content)
        if version_info:
            result["version"] = version_info

        date_str = extract_script_date(version_info, last_modified)
        if date_str:
            result["date"] = date_str

        if actual_sha256 == current_sha256:
            result["status"] = "ok"
        else:
            result["status"] = "changed"
            result["update"] = {"install_sha256": actual_sha256}

    except Exception as exc:
        result["status"] = "error"
        if verbose:
            result["version"] = f"error: {exc}"

    return result


def format_check_status(status: str) -> str:
    """Format an update-check status string with color."""
    if status == "ok":
        return f"{Colors.GREEN}ok{Colors.NC}"
    if status == "changed":
        return f"{Colors.YELLOW}changed{Colors.NC}"
    if status == "error":
        return f"{Colors.RED}error{Colors.NC}"
    return status


def format_check_backend(check_type: str) -> str:
    """Format update-check backend labels for display."""
    if check_type == "npm":
        return "npm-registry"
    if check_type in ("script", "direct_download"):
        return "script-url"
    if check_type == "self_managed":
        return "npm-registry"
    return check_type


def print_check_results_table(
    results: List[Dict[str, Any]], verbose: bool = False
) -> None:
    """Print update-check results as a formatted table."""
    if verbose:
        headers = [
            "Tool",
            "Check",
            "Version",
            "Date",
            "Current SHA256",
            "Latest SHA256",
            "Status",
        ]
    else:
        headers = ["Tool", "Check", "Version", "Date", "Status"]

    rows = []
    for result in results:
        if verbose:
            rows.append(
                [
                    result["tool"],
                    format_check_backend(result["type"]),
                    result.get("version", "-"),
                    result.get("date", "-"),
                    result.get("sha256_current", "-"),
                    result.get("sha256_latest", "-"),
                    result["status"],
                ]
            )
        else:
            rows.append(
                [
                    result["tool"],
                    format_check_backend(result["type"]),
                    result.get("version", "-"),
                    result.get("date", "-"),
                    result["status"],
                ]
            )

    widths = [len(header) for header in headers]
    for row in rows:
        for i, cell in enumerate(row):
            plain = re.sub(r"\033\[[^m]*m", "", str(cell))
            widths[i] = max(widths[i], len(plain))

    header_line = "  ".join(header.ljust(widths[i]) for i, header in enumerate(headers))
    print(f"\n{Colors.BOLD}{header_line}{Colors.NC}")
    print("  ".join("-" * width for width in widths))

    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            if i == len(row) - 1:
                cells.append(format_check_status(cell))
            else:
                cells.append(str(cell).ljust(widths[i]))
        print("  ".join(cells))

    print()


def apply_sha256_updates(
    config: Dict[str, Any], results: List[Dict[str, Any]]
) -> List[str]:
    """Apply pending SHA256 updates to the config dict."""
    updated = []
    for result in results:
        if result["update"]:
            tool_name = result["tool"]
            for key, value in result["update"].items():
                config["tools"][tool_name][key] = value
            updated.append(tool_name)
    return updated
