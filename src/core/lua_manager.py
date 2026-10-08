# lua_manager.py - Handles enabling and disabling of Lua scripts by moving files.
# All functions take explicit directories so the caller decides which edition
# (Legacy or Enhanced, see menu_modes.py) is being managed.
import logging
import os
import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.menu_modes import MenuMode

logger = logging.getLogger(__name__)


def _is_safe_filename(filename: str) -> bool:
    """Checks if the script filename is safe and contains no traversal attempts."""
    if not filename or not isinstance(filename, str):
        return False
    if os.path.basename(filename) != filename:
        return False
    return not any(sep in filename for sep in ("/", "\\", ".."))


def _get_lua_files(directory: str) -> list[str]:
    """Helper function to find all .lua files in a directory."""
    if not os.path.isdir(directory):
        return []

    try:
        entries = os.listdir(directory)
    except OSError as e:
        logger.warning("Could not list Lua script directory %s: %s", directory, e)
        return []

    return [
        f
        for f in entries
        if f.lower().endswith(".lua") and os.path.isfile(os.path.join(directory, f))
    ]


def scripts_available(appdata_dir: str) -> bool:
    """True if the edition's AppData directory exists (i.e. it is installed)."""
    return os.path.isdir(appdata_dir)


def get_scripts(scripts_dir: str, disabled_dir: str) -> dict[str, list[str]]:
    """
    Returns a dictionary with lists of enabled and disabled lua scripts,
    with the '.lua' suffix removed for display.
    """
    enabled_scripts_full = _get_lua_files(scripts_dir)
    disabled_scripts_full = _get_lua_files(disabled_dir)

    def _strip_lua_ext(name: str) -> str:
        return name[:-4] if name.lower().endswith(".lua") else name

    enabled_display = [_strip_lua_ext(s) for s in sorted(enabled_scripts_full)]
    disabled_display = [_strip_lua_ext(s) for s in sorted(disabled_scripts_full)]

    logger.debug(f"Found enabled scripts: {enabled_display}")
    logger.debug(f"Found disabled scripts: {disabled_display}")

    return {"enabled": enabled_display, "disabled": disabled_display}


def enable_script(scripts_dir: str, disabled_dir: str, filename: str) -> bool:
    """Moves a script from the 'disabled' folder to the 'scripts' folder."""
    if not _is_safe_filename(filename):
        logger.error(f"Cannot enable script with unsafe name: '{filename}'")
        return False

    actual_filename = f"{filename}.lua"

    src = os.path.join(disabled_dir, actual_filename)
    dest = os.path.join(scripts_dir, actual_filename)

    if not os.path.exists(src):
        logger.error(
            f"Cannot enable script '{actual_filename}', it does not exist in the disabled folder."
        )
        return False

    try:
        os.makedirs(scripts_dir, exist_ok=True)
        shutil.move(src, dest)
        logger.info(f"Enabled script: {actual_filename}")
        return True
    except OSError:
        logger.exception(f"Error enabling script {actual_filename}")
        return False


def disable_script(scripts_dir: str, disabled_dir: str, filename: str) -> bool:
    """Moves a script from the 'scripts' folder to the 'disabled' folder."""
    if not _is_safe_filename(filename):
        logger.error(f"Cannot disable script with unsafe name: '{filename}'")
        return False

    actual_filename = f"{filename}.lua"

    src = os.path.join(scripts_dir, actual_filename)
    dest = os.path.join(disabled_dir, actual_filename)

    if not os.path.exists(src):
        logger.error(
            f"Cannot disable script '{actual_filename}', it does not exist in the scripts folder."
        )
        return False

    try:
        os.makedirs(disabled_dir, exist_ok=True)
        shutil.move(src, dest)
        logger.info(f"Disabled script: {actual_filename}")
        return True
    except OSError:
        logger.exception(f"Error disabling script {actual_filename}")
        return False


def bulk_toggle_scripts(mode: "MenuMode", disable: bool) -> int:
    """Moves all Lua scripts to the disabled/ directory (disable=True) or back (disable=False).

    Returns:
        int: Number of script files moved.
    """
    src_dir = mode.scripts_dir if disable else mode.disabled_scripts_dir
    dst_dir = mode.disabled_scripts_dir if disable else mode.scripts_dir

    if not os.path.isdir(src_dir):
        return 0

    os.makedirs(dst_dir, exist_ok=True)
    moved_count = 0

    for item in os.listdir(src_dir):
        if item.lower().endswith(".lua"):
            src_file = os.path.join(src_dir, item)
            dst_file = os.path.join(dst_dir, item)
            if os.path.isfile(src_file):
                try:
                    shutil.move(src_file, dst_file)
                    moved_count += 1
                    logger.info(
                        "%s script: %s -> %s",
                        "Disabled" if disable else "Enabled",
                        src_file,
                        dst_file,
                    )
                except OSError as e:
                    logger.warning("Failed to move script %s: %s", src_file, e)

    return moved_count
