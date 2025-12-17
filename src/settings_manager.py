# settings_manager.py - Manages reading and writing to YimMenu's settings.json.
import os
import json
import logging
import shutil
from paths import YIMMENU_SETTINGS_FILE_PATH

logger = logging.getLogger(__name__)

SETTINGS_FILE_PATH = YIMMENU_SETTINGS_FILE_PATH


def _read_json_safely():
    """Reads the JSON file and handles BOM or corruption."""
    if not os.path.exists(SETTINGS_FILE_PATH):
        return {}
    try:
        with open(SETTINGS_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read settings.json: {e}")
        return {}


def get_setting(key_path: str, default=None):
    """
    Reads a nested setting.
    Example: get_setting("lua.enable_auto_reload_changed_scripts")
    """
    data = _read_json_safely()

    keys = key_path.split(".")
    value = data
    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default


def set_setting(key_path: str, value) -> bool:
    """
    Writes a nested setting. Ensures parent keys exist.
    """
    data = _read_json_safely()

    keys = key_path.split(".")
    d = data
    try:
        for i, key in enumerate(keys[:-1]):
            if key not in d or not isinstance(d[key], dict):
                d[key] = {}
            d = d[key]

        d[keys[-1]] = value
    except Exception as e:
        logger.error(f"Error traversing settings dict: {e}")
        return False

    temp_file = SETTINGS_FILE_PATH + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        shutil.move(temp_file, SETTINGS_FILE_PATH)
        logger.info(f"Successfully set '{key_path}' to '{value}'")
        return True
    except OSError as e:
        logger.error(f"Failed to write settings file: {e}")
        return False
