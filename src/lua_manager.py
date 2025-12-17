# lua_manager.py - Handles enabling and disabling of Lua scripts by moving files.
import os
import shutil
import logging
from typing import Dict, List
from paths import YIMMENU_APPDATA_DIR, YIMMENU_SCRIPTS_DIR, YIMMENU_DISABLED_SCRIPTS_DIR

logger = logging.getLogger(__name__)

YIM_FOLDER_PATH = YIMMENU_APPDATA_DIR
SCRIPTS_PATH = YIMMENU_SCRIPTS_DIR
DISABLED_SCRIPTS_PATH = YIMMENU_DISABLED_SCRIPTS_DIR


def _get_lua_files(directory: str) -> List[str]:
    """Helper function to find all .lua files in a directory."""
    if not os.path.isdir(directory):
        return []

    return [
        f
        for f in os.listdir(directory)
        if f.endswith(".lua") and os.path.isfile(os.path.join(directory, f))
    ]


def get_scripts() -> Dict[str, List[str]]:
    """
    Returns a dictionary with lists of enabled and disabled lua scripts,
    with the '.lua' suffix removed for display.
    """
    os.makedirs(DISABLED_SCRIPTS_PATH, exist_ok=True)

    enabled_scripts_full = _get_lua_files(SCRIPTS_PATH)

    disabled_scripts_full = _get_lua_files(DISABLED_SCRIPTS_PATH)

    enabled_display = [s.removesuffix(".lua") for s in sorted(enabled_scripts_full)]
    disabled_display = [s.removesuffix(".lua") for s in sorted(disabled_scripts_full)]

    logger.debug(f"Found enabled scripts: {enabled_display}")
    logger.debug(f"Found disabled scripts: {disabled_display}")

    return {"enabled": enabled_display, "disabled": disabled_display}


def enable_script(filename: str) -> bool:
    """Moves a script from the 'disabled' folder to the 'scripts' folder."""
    actual_filename = f"{filename}.lua"

    src = os.path.join(DISABLED_SCRIPTS_PATH, actual_filename)
    dest = os.path.join(SCRIPTS_PATH, actual_filename)

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


def disable_script(filename: str) -> bool:
    """Moves a script from the 'scripts' folder to the 'disabled' folder."""
    actual_filename = f"{filename}.lua"

    src = os.path.join(SCRIPTS_PATH, actual_filename)
    dest = os.path.join(DISABLED_SCRIPTS_PATH, actual_filename)

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
