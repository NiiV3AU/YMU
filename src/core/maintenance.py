import logging
import os
from enum import StrEnum

from core import lua_manager
from core.menu_modes import MenuMode

logger = logging.getLogger(__name__)


class FslStatus(StrEnum):
    """Presence of the FSL local-save proxy DLL in the GTA V directory.

    FSL is a save-file tool: it redirects GTA Online save reads and writes to
    %APPDATA%/FSL. It is not an anti-cheat bypass and has no relation to
    BattlEye detection - the file check below is purely about which proxy DLL
    happens to sit in the game folder.
    """

    MISSING = "missing"
    DETECTED = "detected"
    DEPRECATED = "deprecated"


def clear_menu_caches(mode: MenuMode) -> tuple[int, list[str]]:
    """Deletes cached binary pointer and pattern files for the active edition.

    - Legacy: Deletes all *.bin files in %APPDATA%/YimMenu/cache/
    - Enhanced: Deletes pattern_cache.bin, scr_pointers.bin, tunables.bin in %APPDATA%/YimMenuV2/

    User configuration (.json), hotkeys, and custom teleports are strictly preserved.
    Returns:
        tuple of (deleted_count, list of deleted file basenames).
    """
    deleted: list[str] = []

    if mode.key == "legacy":
        cache_dir = os.path.join(mode.appdata_dir, "cache")
        if os.path.isdir(cache_dir):
            try:
                filenames = os.listdir(cache_dir)
            except OSError as e:
                logger.warning("Could not list cache directory %s: %s", cache_dir, e)
                filenames = []
            for filename in filenames:
                if filename.lower().endswith(".bin"):
                    file_path = os.path.join(cache_dir, filename)
                    try:
                        os.remove(file_path)
                        deleted.append(filename)
                        logger.info("Cleared Legacy cache file: %s", file_path)
                    except OSError as e:
                        logger.warning(
                            "Failed to delete cache file %s: %s", file_path, e
                        )
    elif mode.key == "enhanced":
        # Enhanced stores cache files directly in %APPDATA%/YimMenuV2/
        target_files = ("pattern_cache.bin", "scr_pointers.bin", "tunables.bin")
        for filename in target_files:
            file_path = os.path.join(mode.appdata_dir, filename)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    deleted.append(filename)
                    logger.info("Cleared Enhanced cache file: %s", file_path)
                except OSError as e:
                    logger.warning("Failed to delete cache file %s: %s", file_path, e)
    else:
        logger.error("Unknown menu mode key '%s'; skipping cache clear.", mode.key)
        return 0, []

    return len(deleted), deleted


def get_fsl_status(gta_dir: str | None) -> FslStatus:
    """Checks the FSL installation status in the GTA V directory.

    Returns:
        FslStatus.DETECTED: Current WINMM.dll is present (and no deprecated version.dll).
        FslStatus.DEPRECATED: Legacy version.dll is present (causes game crashes).
        FslStatus.MISSING: Neither file was found, or the directory is invalid.
    """
    if not gta_dir or not os.path.isdir(gta_dir):
        return FslStatus.MISSING

    try:
        filenames = {f.lower() for f in os.listdir(gta_dir)}
    except OSError:
        return FslStatus.MISSING

    # If the legacy, crashing version.dll is present, always warn the user
    if "version.dll" in filenames:
        return FslStatus.DEPRECATED
    if "winmm.dll" in filenames:
        return FslStatus.DETECTED

    return FslStatus.MISSING


def bulk_toggle_scripts(mode: MenuMode, disable: bool) -> int:
    """Moves all Lua scripts to the disabled/ directory (disable=True) or back (disable=False).

    Delegates to lua_manager.bulk_toggle_scripts.

    Returns:
        int: Number of script files moved.
    """
    return lua_manager.bulk_toggle_scripts(mode, disable)
