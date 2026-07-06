# lua_manager.py - Handles enabling and disabling of Lua scripts by moving files.
# All functions take explicit directories so the caller decides which edition
# (Legacy or Enhanced, see menu_modes.py) is being managed.
import logging
import os
import shutil
from typing import Dict, List

logger = logging.getLogger(__name__)


def _get_lua_files(directory: str) -> List[str]:
    """Helper function to find all .lua files in a directory."""
    if not os.path.isdir(directory):
        return []

    return [
        f
        for f in os.listdir(directory)
        if f.endswith(".lua") and os.path.isfile(os.path.join(directory, f))
    ]


def scripts_available(appdata_dir: str) -> bool:
    """True if the edition's AppData directory exists (i.e. it is installed)."""
    return os.path.isdir(appdata_dir)


def get_scripts(scripts_dir: str, disabled_dir: str) -> Dict[str, List[str]]:
    """
    Returns a dictionary with lists of enabled and disabled lua scripts,
    with the '.lua' suffix removed for display.
    """
    # Only create the 'disabled' subfolder if the scripts folder itself exists;
    # otherwise a missing edition directory would be silently created and the
    # "not installed" hint in the UI could never appear.
    if os.path.isdir(scripts_dir):
        os.makedirs(disabled_dir, exist_ok=True)

    enabled_scripts_full = _get_lua_files(scripts_dir)

    disabled_scripts_full = _get_lua_files(disabled_dir)

    enabled_display = [s.removesuffix(".lua") for s in sorted(enabled_scripts_full)]
    disabled_display = [s.removesuffix(".lua") for s in sorted(disabled_scripts_full)]

    logger.debug(f"Found enabled scripts: {enabled_display}")
    logger.debug(f"Found disabled scripts: {disabled_display}")

    return {"enabled": enabled_display, "disabled": disabled_display}


def enable_script(scripts_dir: str, disabled_dir: str, filename: str) -> bool:
    """Moves a script from the 'disabled' folder to the 'scripts' folder."""
    actual_filename = f"{filename}.lua"

    src = os.path.join(disabled_dir, actual_filename)
    dest = os.path.join(scripts_dir, actual_filename)

    if not os.path.exists(src):
        logger.error(
            f"Cannot enable script '{actual_filename}', it does not exist in the disabled folder."
        )
        return False

    try:
        shutil.move(src, dest)
        logger.info(f"Enabled script: {actual_filename}")
        return True
    except (IOError, OSError) as e:
        logger.exception(f"Error enabling script {actual_filename}: {e}")
        return False


def disable_script(scripts_dir: str, disabled_dir: str, filename: str) -> bool:
    """Moves a script from the 'scripts' folder to the 'disabled' folder."""
    actual_filename = f"{filename}.lua"

    src = os.path.join(scripts_dir, actual_filename)
    dest = os.path.join(disabled_dir, actual_filename)

    if not os.path.exists(src):
        logger.error(
            f"Cannot disable script '{actual_filename}', it does not exist in the scripts folder."
        )
        return False

    try:
        shutil.move(src, dest)
        logger.info(f"Disabled script: {actual_filename}")
        return True
    except (IOError, OSError) as e:
        logger.exception(f"Error disabling script {actual_filename}: {e}")
        return False
