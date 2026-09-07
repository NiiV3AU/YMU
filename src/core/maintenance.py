# maintenance.py - Cache clearing, FSL environment checks, and script recovery tools.
import logging
import os

from core import lua_manager
from core.menu_modes import MenuMode

logger = logging.getLogger(__name__)


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
            for filename in os.listdir(cache_dir):
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
    else:
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

    return len(deleted), deleted


def get_fsl_status(gta_dir: str | None) -> bool:
    """Checks if FSL (WINMM.dll or fallback version.dll) is present in the GTA V directory."""
    if not gta_dir or not os.path.isdir(gta_dir):
        return False

    candidate_names = ("winmm.dll", "version.dll")
    try:
        return any(
            os.path.isfile(os.path.join(gta_dir, name)) for name in candidate_names
        )
    except OSError:
        return False


def bulk_toggle_scripts(mode: MenuMode, disable: bool) -> int:
    """Moves all Lua scripts to the disabled/ directory (disable=True) or back (disable=False).

    Delegates to lua_manager.bulk_toggle_scripts.

    Returns:
        int: Number of script files moved.
    """
    return lua_manager.bulk_toggle_scripts(mode, disable)
