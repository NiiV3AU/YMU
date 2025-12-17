import release_service
import subprocess
import logging
import sys
import os
from paths import YMU_APPDATA_DIR, LOCAL_VERSION

logger = logging.getLogger(__name__)

REPO = "NiiV3AU/YMU"
UPDATER_REPO = "xesdoog/YMU-Updater"
UPDATER_EXE_PATH = os.path.join(YMU_APPDATA_DIR, "ymu_self_updater.exe")

_update_cache = {}
CACHE_DURATION_SECONDS = 300

# --- STATUS CONSTANTS ---
STATUS_ERROR = "ERROR"
STATUS_UPDATE_AVAILABLE = "UPDATE_AVAILABLE"
STATUS_UP_TO_DATE = "UP_TO_DATE"
STATUS_AHEAD = "AHEAD"


def check_for_updates(*args, **kwargs):
    """
    Returns tuple: (STATUS_CODE, DATA)
    DATA is either the remote version string or the error message/object.
    """
    import time
    from packaging.version import parse

    current_time = time.time()

    if REPO in _update_cache:
        cached_data, timestamp = _update_cache[REPO]
        if (current_time - timestamp) < CACHE_DURATION_SECONDS:
            return cached_data

    logger.info("Checking for YMU updates...")
    try:
        provider = release_service.GitHubAPIProvider(
            repository=REPO, asset_extension=".exe"
        )
        latest_release = provider.get_latest_release()

        if not latest_release:
            return (STATUS_ERROR, "Could not fetch release info")

        remote_version = latest_release.version_tag

        local = parse(LOCAL_VERSION)
        remote = parse(remote_version)

        result = None
        if remote > local:
            result = (STATUS_UPDATE_AVAILABLE, remote_version)
        elif remote == local:
            result = (STATUS_UP_TO_DATE, remote_version)
        else:
            result = (STATUS_AHEAD, remote_version)

        _update_cache[REPO] = (result, current_time)
        return result

    except Exception as e:
        logger.exception(f"Update check failed: {e}")
        return (STATUS_ERROR, str(e))


def download_and_launch_updater(progress_signal=None, *args, **kwargs):
    """
    Downloads updater, passes sys.executable to it.
    """
    logger.info(f"Fetching latest updater from {UPDATER_REPO}")
    provider = release_service.GitHubAPIProvider(
        repository=UPDATER_REPO, asset_extension=".exe"
    )
    latest_release = provider.get_latest_release()

    if not latest_release:
        return (False, "Could not find the latest updater release.")

    success = release_service.download_and_verify_release(
        latest_release, progress_signal
    )

    if not success:
        return (False, "Failed to download the updater executable.")

    try:
        logger.info(f"Launching updater: {UPDATER_EXE_PATH}")
        current_exe = sys.executable
        cmd = [UPDATER_EXE_PATH, current_exe]

        if sys.platform == "win32":
            subprocess.Popen(
                cmd,
                creationflags=subprocess.DETACHED_PROCESS,
                close_fds=True,
            )
        else:
            subprocess.Popen(cmd)

        return (True, "Updater launched")
    except (IOError, OSError) as e:
        logger.exception(f"Failed to launch updater: {e}")
        return (False, str(e))
