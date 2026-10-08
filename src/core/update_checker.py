import logging
import re
import threading
import time

from core import release_service
from core.paths import LOCAL_VERSION

logger = logging.getLogger(__name__)

REPO = "NiiV3AU/YMU"
# YMU updates passively: the version check below tells the user an update
# exists, and the UI opens this page so they can download the new build.
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"

_update_cache: dict[str, tuple[tuple[str, str], float]] = {}
_update_cache_lock = threading.Lock()
CACHE_DURATION_SECONDS = 300
ERROR_CACHE_DURATION_SECONDS = 60

# --- STATUS CONSTANTS ---
STATUS_ERROR = "ERROR"
STATUS_UPDATE_AVAILABLE = "UPDATE_AVAILABLE"
STATUS_UP_TO_DATE = "UP_TO_DATE"
STATUS_AHEAD = "AHEAD"


def _set_cached(result: tuple[str, str], ttl: float, current_time: float) -> None:
    with _update_cache_lock:
        _update_cache[REPO] = (result, current_time + ttl)


def parse_version_tuple(v: str) -> tuple[int, int, int]:
    """Parse a semantic or tagged version string like 'v1.2.3', 'release-1.2.0', or '1.0' into a 3-tuple (major, minor, patch)."""
    match = re.search(r"(\d+(?:\.\d+)*)", str(v).strip())
    if not match:
        return (0, 0, 0)
    nums = [int(n) for n in match.group(1).split(".")][:3]
    nums += [0] * max(0, 3 - len(nums))
    return (nums[0], nums[1], nums[2])


def check_for_updates():
    """
    Returns tuple: (STATUS_CODE, DATA)
    DATA is either the remote version string or the error message/object.
    """
    current_time = time.time()

    with _update_cache_lock:
        if REPO in _update_cache:
            cached_data, expire_at = _update_cache[REPO]
            if current_time < expire_at:
                return cached_data

    logger.info("Checking for YMU updates...")
    try:
        provider = release_service.GitHubAPIProvider(
            repository=REPO, asset_extension=""
        )
        latest_release = provider.get_latest_release()

        if not latest_release:
            err_res = (STATUS_ERROR, "Could not fetch release info")
            _set_cached(err_res, ERROR_CACHE_DURATION_SECONDS, current_time)
            return err_res

        remote_version = latest_release.version_tag

        local = parse_version_tuple(LOCAL_VERSION)
        remote = parse_version_tuple(remote_version)

        if remote == (0, 0, 0) and not re.search(r"\d+", remote_version):
            err_res = (STATUS_ERROR, f"Unrecognized version format: {remote_version}")
            _set_cached(err_res, ERROR_CACHE_DURATION_SECONDS, current_time)
            return err_res

        result = None
        if remote > local:
            result = (STATUS_UPDATE_AVAILABLE, remote_version)
        elif remote == local:
            result = (STATUS_UP_TO_DATE, remote_version)
        else:
            result = (STATUS_AHEAD, remote_version)

        _set_cached(result, CACHE_DURATION_SECONDS, current_time)
        return result

    except release_service.RateLimitException as e:
        logger.warning(f"Rate limit during YMU update check: {e}")
        wait_m = getattr(e, "wait_minutes", None)
        ttl = (
            min(3600, wait_m * 60)
            if wait_m is not None
            else ERROR_CACHE_DURATION_SECONDS
        )
        err_res = (STATUS_ERROR, str(e))
        _set_cached(err_res, ttl, current_time)
        return err_res
    except Exception as e:
        logger.exception("Update check failed")
        err_res = (STATUS_ERROR, str(e))
        _set_cached(err_res, ERROR_CACHE_DURATION_SECONDS, current_time)
        return err_res
