# paths.py - Defines, creates, and manages all application file paths.
import logging
import os
import sys
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

LOCAL_VERSION = "v1.2.0"
APP_URL = "https://github.com/NiiV3AU/YMU"
USER_AGENT = f"YMU/{LOCAL_VERSION} (+{APP_URL})"
WINDOW_TITLE = "YimMenuUpdater | NV3"


def _resolve_base_dirs() -> tuple[str, str]:
    home = Path.home()
    appdata = os.getenv("APPDATA")
    if not appdata:
        appdata = str(home / "AppData" / "Roaming")

    localappdata = os.getenv("LOCALAPPDATA")
    if not localappdata:
        userprofile = os.getenv("USERPROFILE")
        if userprofile:
            localappdata = os.path.join(userprofile, "AppData", "Local")
        else:
            localappdata = str(home / "AppData" / "Local")

    return (os.path.abspath(appdata), os.path.abspath(localappdata))


def _create_path(path: str) -> str:
    """Helper function to ensure a directory exists safely."""
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        logger.error("Failed to create directory '%s': %s", path, e)
    return path


APPDATA_PATH, LOCALAPPDATA_PATH = _resolve_base_dirs()

# --- YMU Application Directories and Files ---
YMU_APPDATA_DIR = _create_path(
    os.getenv("YMU_APPDATA_DIR") or os.path.join(APPDATA_PATH, "YMU")
)
YMU_LOCAL_DIR = _create_path(
    os.getenv("YMU_LOCAL_DIR") or os.path.join(LOCALAPPDATA_PATH, "YMU")
)
YMU_DLL_DIR = _create_path(os.path.join(YMU_LOCAL_DIR, "dll"))
YMU_LANG_DIR = _create_path(os.path.join(YMU_APPDATA_DIR, "lang"))
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


def is_compiled() -> bool:
    """Detects whether YMU is running as a compiled standalone executable (Nuitka, PyInstaller, etc.)."""
    import builtins

    return (
        "__compiled__" in globals()
        or hasattr(builtins, "__compiled__")
        or getattr(sys, "frozen", False)
        or (
            bool(sys.argv)
            and sys.argv[0].lower().endswith(".exe")
            and not os.path.basename(sys.argv[0])
            .lower()
            .startswith(("python", "pytest"))
        )
    )


def cleanup_old_runtime_dirs() -> None:
    """Removes old Nuitka onefile runtime cache directories.

    When YMU updates (e.g. from v1.1.11 to v1.2.0), prior runtime directories
    are left behind in %LOCALAPPDATA%/YMU/YMU/<version> or
    %LOCALAPPDATA%/Nuitka/Nuitka/Cache/YMU/YMU/<version> and consume ~30-50 MB each.
    This safely purges old version folders while strictly protecting the active version
    and never deleting the parent runtime directory itself.
    """
    import re
    import shutil

    candidates = [
        os.path.join(YMU_LOCAL_DIR, "YMU"),
        os.path.join(LOCALAPPDATA_PATH, "Nuitka", "Nuitka", "Cache", "YMU", "YMU"),
    ]

    current_version = LOCAL_VERSION.removeprefix("v")
    protected_names = {LOCAL_VERSION, current_version, f"v{current_version}"}
    version_pattern = re.compile(r"^v?\d+(\.\d+)*$")

    for base_dir in candidates:
        if not os.path.isdir(base_dir):
            continue

        try:
            for entry in os.listdir(base_dir):
                entry_path = os.path.join(base_dir, entry)
                if not os.path.isdir(entry_path):
                    continue

                if entry in protected_names:
                    continue

                # Only target subdirectories matching a version schema
                if not version_pattern.match(entry):
                    continue

                logger.info("Purging old runtime cache directory: %s", entry_path)
                try:
                    shutil.rmtree(entry_path)
                    logger.info("Successfully removed old runtime cache: %s", entry)
                except OSError as e:
                    logger.warning(
                        "Could not remove old runtime cache '%s': %s", entry_path, e
                    )
        except OSError as e:
            logger.warning(
                "Error scanning runtime cache directory '%s': %s",
                base_dir,
                e,
            )


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


@lru_cache(maxsize=128)
def resource_path(relative_path: str) -> str:
    """Gets the absolute path to a resource.

    Resolution hierarchy:
    1. PyInstaller extracted bundle (_MEIPASS)
    2. src/ directory (src/core/paths.py -> src/)
    3. Repository root directory (parent of src/, for dev root assets like translations.json)
    4. Compiled standalone executable directory (sys.argv[0] or sys.executable when is_compiled())
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)

    # 1. Try relative to src/ directory (since paths.py is located in src/core/)
    src_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(src_base, relative_path)
    if os.path.exists(candidate):
        return candidate

    # 2. Try relative to project / repository root (parent of src/)
    project_root = os.path.dirname(src_base)
    candidate = os.path.join(project_root, relative_path)
    if os.path.exists(candidate):
        return candidate

    # 3. If running a compiled executable (standalone/frozen), check next to executable binary.
    # NOTE: unittest/__main__.py sets sys.argv[0] to '<exe> -m unittest', which
    # causes dirname(abspath(argv[0])) to resolve to the CWD when not compiled.
    # Therefore, sys.argv[0] is only consulted if is_compiled() is True.
    if is_compiled():
        argv_target = sys.argv[0] if (sys.argv and sys.argv[0]) else sys.executable
        if argv_target:
            argv_base = os.path.dirname(os.path.abspath(argv_target))
            candidate = os.path.join(argv_base, relative_path)
            if os.path.exists(candidate):
                return candidate

    return os.path.join(src_base, relative_path)


def icon(name: str) -> str:
    """Return the absolute path to an icon asset in assets/icons."""
    return resource_path(os.path.join("assets", "icons", name))
