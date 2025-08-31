# update_checker.py - Manages the self-updating logic for YMU.
import release_service
import subprocess
import logging
from typing import Callable, Optional
import sys
import os
from paths import YMU_APPDATA_DIR, resource_path

logger = logging.getLogger(__name__)

LOCAL_VERSION = "v1.1.5"
REPO = "NiiV3AU/YMU"
UPDATER_REPO = "xesdoog/YMU-Updater"
UPDATER_EXE_PATH = os.path.join(YMU_APPDATA_DIR, "ymu_self_updater.exe")
_update_cache = {}
CACHE_DURATION_SECONDS = 300


def check_for_updates(*args, **kwargs):
    """
    Checks for YMU updates using the GitHub API, with caching.
    Returns a tuple: (status, message)
    """
    import time

    current_time = time.time()

    if REPO in _update_cache:
        cached_data, timestamp = _update_cache[REPO]
        if (current_time - timestamp) < CACHE_DURATION_SECONDS:
            logger.info(f"Using cached update check result for {REPO}.")
            return cached_data

    logger.info("Checking for YMU updates...")
    provider = release_service.GitHubAPIProvider(
        repository=REPO, asset_extension=".exe"
    )
    latest_release = provider.get_latest_release()

    if not latest_release:
        logger.error("Could not fetch latest release info for YMU.")
        raise RuntimeError("Could not fetch latest release info.")

    remote_version = latest_release.version_tag
    logger.info(f"Local version: {LOCAL_VERSION}, Remote version: {remote_version}")

    result = None
    try:
        from packaging.version import parse
    except ImportError:
        logger.warning(
            "'packaging' module not found. Using simple tuple comparison for version check."
        )
        try:
            local_tuple = tuple(map(int, LOCAL_VERSION.lstrip("v").split(".")))
            remote_tuple = tuple(map(int, remote_version.lstrip("v").split(".")))

            if remote_tuple > local_tuple:
                result = ("UPDATE_AVAILABLE", f"Update {remote_version} is available!")
            elif remote_tuple == local_tuple:
                result = ("UP_TO_DATE", "YMU is up-to-date.")
            else:
                result = (
                    "AHEAD",
                    "You are running a newer version than the latest release.",
                )
        except ValueError:
            logger.error("Could not parse version strings for comparison.")
            raise RuntimeError("Could not parse version strings.")
    else:
        local = parse(LOCAL_VERSION)
        remote = parse(remote_version)
        if remote > local:
            result = ("UPDATE_AVAILABLE", f"Update {remote_version} is available!")
        elif remote == local:
            result = ("UP_TO_DATE", "YMU is up-to-date.")
        else:
            result = (
                "AHEAD",
                "You are running a newer version than the latest release.",
            )

    if result:
        _update_cache[REPO] = (result, current_time)

    return result


def download_and_launch_updater(
    progress_callback: Optional[Callable[[int], None]] = None, *args, **kwargs
):
    """
    Downloads the latest ymu_self_updater.exe, launches it, and prepares the main app to exit.
    """
    logger.info(f"Fetching latest updater from {UPDATER_REPO}")
    provider = release_service.GitHubAPIProvider(
        repository=UPDATER_REPO, asset_extension=".exe"
    )
    latest_release = provider.get_latest_release()

    if not latest_release:
        logger.error("Could not find the latest updater release.")
        return (False, "Could not find the latest updater release.")

    success = release_service.download_and_verify_release(
        latest_release, progress_callback
    )

    if not success:
        logger.error("Failed to download the updater executable.")
        return (False, "Failed to download the updater executable.")

    try:
        logger.info(f"Launching updater: {UPDATER_EXE_PATH}")
        if sys.platform == "win32":
            subprocess.Popen(
                [UPDATER_EXE_PATH],
                creationflags=subprocess.DETACHED_PROCESS,
                close_fds=True,
            )
        else:
            subprocess.Popen([UPDATER_EXE_PATH])

        return (True, "Updater launched. YMU will now exit.")
    except (IOError, OSError) as e:
        logger.exception(f"Failed to launch updater: {e}")
        return (False, f"Failed to launch updater: {e}")
