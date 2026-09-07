import logging
import re
import time

from core import release_service
from core.paths import LOCAL_VERSION

logger = logging.getLogger(__name__)

REPO = "NiiV3AU/YMU"
# YMU updates passively: the version check below tells the user an update
# exists, and the UI opens this page so they can download the new build.
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"

_update_cache = {}
CACHE_DURATION_SECONDS = 300

# --- STATUS CONSTANTS ---
STATUS_ERROR = "ERROR"
STATUS_UPDATE_AVAILABLE = "UPDATE_AVAILABLE"
STATUS_UP_TO_DATE = "UP_TO_DATE"
STATUS_AHEAD = "AHEAD"


def parse_version_tuple(v: str) -> tuple[int, int, int]:
    """Parse a semantic or tagged version string like 'v1.2.3' into a 3-tuple (major, minor, patch)."""
    base = re.split(r"[-+]", str(v).strip())[0]
    cleaned = re.sub(r"^[^\d]*", "", base)
    nums = [int(n) for n in re.findall(r"\d+", cleaned)]
    nums += [0] * max(0, 3 - len(nums))
    return (nums[0], nums[1], nums[2])


def check_for_updates(*args, **kwargs):
    """
    Returns tuple: (STATUS_CODE, DATA)
    DATA is either the remote version string or the error message/object.
    """
    current_time = time.time()

    if REPO in _update_cache:
        cached_data, timestamp = _update_cache[REPO]
        if (current_time - timestamp) < CACHE_DURATION_SECONDS:
            return cached_data

    logger.info("Checking for YMU updates...")
    try:
        provider = release_service.GitHubAPIProvider(
            repository=REPO, asset_extension=""
        )
        latest_release = provider.get_latest_release()

        if not latest_release:
            return (STATUS_ERROR, "Could not fetch release info")

        remote_version = latest_release.version_tag

        local = parse_version_tuple(LOCAL_VERSION)
        remote = parse_version_tuple(remote_version)

        result = None
        if remote > local:
            result = (STATUS_UPDATE_AVAILABLE, remote_version)
        elif remote == local:
            result = (STATUS_UP_TO_DATE, remote_version)
        else:
            result = (STATUS_AHEAD, remote_version)

        _update_cache[REPO] = (result, current_time)
        return result

    except release_service.RateLimitException as e:
        logger.warning(f"Rate limit during YMU update check: {e}")
        return (STATUS_ERROR, str(e))
    except Exception as e:
        logger.exception("Update check failed")
        return (STATUS_ERROR, str(e))
