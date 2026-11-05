from . import __version__
"""
OpenATS Automatic Update Checker.
Checks for official security patches and new releases from https://github.com/3447nazmul/openats.
Runs non-blockingly with zero external dependencies and a 1-hour in-process cache.
"""
import time
import urllib.request
import json
import re
from typing import Dict, Any, Tuple

REPO_OWNER = "3447nazmul"
REPO_NAME = "openats"
API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

# In-process cache: { current_version: (timestamp, response_dict) }
_UPDATE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
CACHE_TTL_SECONDS: int = 3600  # 1 hour


def clear_update_cache() -> None:
    """Clear the in-process update check cache (useful for testing)."""
    _UPDATE_CACHE.clear()


def parse_semver(v: str):
    """Extracts (major, minor, patch) integers from a semver string like 'v1.2.3'."""
    clean = re.sub(r'^[vV]', '', v.strip())
    parts = clean.split('.')
    nums = []
    for p in parts:
        m = re.match(r'\d+', p)
        nums.append(int(m.group(0)) if m else 0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


def check_for_updates(
    current_version: str = __version__,
    timeout: float = 2.0,
    use_cache: bool = True,
) -> dict:
    """
    Checks if a newer release is published on GitHub.
    Caches the result in-process for 1 hour (3600s) when use_cache=True.
    Returns:
        dict: {
            "update_available": bool,
            "current_version": str,
            "latest_version": str,
            "release_url": str,
            "notes": str
        }
    """
    now = time.time()
    if use_cache and current_version in _UPDATE_CACHE:
        cached_time, cached_res = _UPDATE_CACHE[current_version]
        if (now - cached_time) < CACHE_TTL_SECONDS:
            return dict(cached_res)

    result = {
        "update_available": False,
        "current_version": current_version,
        "latest_version": current_version,
        "release_url": f"https://github.com/{REPO_OWNER}/{REPO_NAME}",
        "notes": ""
    }
    try:
        req = urllib.request.Request(
            API_URL,
            headers={
                "User-Agent": f"OpenATS-Client/{current_version}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                latest_tag = data.get("tag_name", current_version)
                latest_sem = parse_semver(latest_tag)
                curr_sem = parse_semver(current_version)

                if latest_sem > curr_sem:
                    result = {
                        "update_available": True,
                        "current_version": current_version,
                        "latest_version": latest_tag,
                        "release_url": data.get("html_url", result["release_url"]),
                        "notes": data.get("body", "").strip()[:300]
                    }
    except Exception:
        # Gracefully suppress any network or offline issues
        pass

    if use_cache:
        _UPDATE_CACHE[current_version] = (now, dict(result))

    return result
