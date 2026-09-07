# paths.py - Defines, creates, and manages all application file paths.
import logging
import os
import sys

logger = logging.getLogger(__name__)

LOCAL_VERSION = "v1.1.11"
APP_URL = "https://github.com/NiiV3AU/YMU"
USER_AGENT = f"YMU/{LOCAL_VERSION} (+{APP_URL})"


def get_required_env(env_var: str) -> str:
    """Gets an environment variable that is required for the app to run."""
    value = os.getenv(env_var)
    if value is None:
        raise OSError(f"Required environment variable '{env_var}' is not set.")
    return value


def _create_path(path: str):
    """Helper function to ensure a directory exists."""
    os.makedirs(path, exist_ok=True)
    return path


APPDATA_PATH = get_required_env("APPDATA")
LOCALAPPDATA_PATH = os.environ.get("LOCALAPPDATA") or os.path.join(
    os.environ.get("USERPROFILE", ""), "AppData", "Local"
)

YMU_APPDATA_DIR = _create_path(os.path.join(APPDATA_PATH, "YMU"))
YMU_LOCAL_DIR = _create_path(os.path.join(LOCALAPPDATA_PATH, "YMU"))
YMU_DLL_DIR = _create_path(os.path.join(YMU_LOCAL_DIR, "dll"))
YMU_LOG_FILE_PATH = os.path.join(YMU_APPDATA_DIR, "ymu.log")
YMU_CONFIG_FILE_PATH = os.path.join(YMU_APPDATA_DIR, "config.json")
YMU_CACHE_FILE_PATH = os.path.join(YMU_APPDATA_DIR, "cache.json")


def migrate_legacy_dll_dir() -> None:
    """Migrates legacy DLLs from %APPDATA%/YMU/dll to %LOCALAPPDATA%/YMU/dll."""
    import shutil

    legacy_dir = os.path.join(YMU_APPDATA_DIR, "dll")
    if not os.path.isdir(legacy_dir):
        return

    logger.info("Migrating legacy DLL directory: %s -> %s", legacy_dir, YMU_DLL_DIR)
    try:
        for item in os.listdir(legacy_dir):
            src = os.path.join(legacy_dir, item)
            dst = os.path.join(YMU_DLL_DIR, item)
            if not os.path.isfile(src):
                continue
            if os.path.exists(dst):
                logger.warning(
                    "Legacy DLL migration: destination file '%s' already exists; removing duplicate source '%s'",
                    dst,
                    src,
                )
                try:
                    os.remove(src)
                except OSError as e:
                    logger.warning(
                        "Could not remove duplicate source DLL '%s': %s", src, e
                    )
            else:
                logger.info("Migrating legacy DLL: %s -> %s", src, dst)
                shutil.move(src, dst)

        remaining = os.listdir(legacy_dir)
        if not remaining:
            os.rmdir(legacy_dir)
            logger.info("Removed empty legacy DLL directory: %s", legacy_dir)
        else:
            logger.warning(
                "Legacy DLL directory '%s' not empty after migration: %s",
                legacy_dir,
                remaining,
            )
    except OSError as e:
        logger.warning("Error during legacy DLL migration: %s", e)


_migrate_legacy_dll_dir = migrate_legacy_dll_dir

# YimMenu directories are intentionally NOT created here: their absence is
# how YMU detects that an edition is not installed yet.
YIMMENU_APPDATA_DIR = os.path.join(APPDATA_PATH, "YimMenu")
YIMMENU_SCRIPTS_DIR = os.path.join(YIMMENU_APPDATA_DIR, "scripts")
YIMMENU_DISABLED_SCRIPTS_DIR = os.path.join(YIMMENU_SCRIPTS_DIR, "disabled")
YIMMENU_SETTINGS_FILE_PATH = os.path.join(YIMMENU_APPDATA_DIR, "settings.json")

YIMMENUV2_APPDATA_DIR = os.path.join(APPDATA_PATH, "YimMenuV2")
YIMMENUV2_SCRIPTS_DIR = os.path.join(YIMMENUV2_APPDATA_DIR, "scripts")
YIMMENUV2_DISABLED_SCRIPTS_DIR = os.path.join(YIMMENUV2_SCRIPTS_DIR, "disabled")
YIMMENUV2_SETTINGS_FILE_PATH = os.path.join(YIMMENUV2_APPDATA_DIR, "settings.json")
YMU_LANG_DIR = _create_path(os.path.join(YMU_APPDATA_DIR, "lang"))


def resource_path(relative_path: str) -> str:
    """
    Gets the absolute path to a resource.
    Works for:
    1. PyInstaller (_MEIPASS)
    2. Nuitka (sys.argv[0] dir or __file__)
    3. Normal Python Script
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)

    # 1. Try relative to sys.argv[0] directory
    argv_base = os.path.dirname(os.path.abspath(sys.argv[0]))
    candidate = os.path.join(argv_base, relative_path)
    if os.path.exists(candidate):
        return candidate

    # 2. Try relative to src/ directory (since paths.py is located in src/core/)
    src_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(src_base, relative_path)
    if os.path.exists(candidate):
        return candidate

    return candidate
