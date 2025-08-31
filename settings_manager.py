# settings_manager.py - Manages reading and writing to YimMenu's settings.json.
import os
import json
import logging
import shutil
from paths import YIMMENU_APPDATA_DIR, YIMMENU_SETTINGS_FILE_PATH

logger = logging.getLogger(__name__)

YIM_FOLDER_PATH = YIMMENU_APPDATA_DIR
SETTINGS_FILE_PATH = YIMMENU_SETTINGS_FILE_PATH


def get_setting(key_path: str, default=None):
    """
    Reads a nested setting from settings.json using a dot-separated path.
    Example: get_setting("lua.enable_auto_reload_changed_scripts")
    """
    if not os.path.exists(SETTINGS_FILE_PATH):
        logger.debug(
            f"Settings file not found at '{SETTINGS_FILE_PATH}'. Returning default value."
        )
        return default

    try:
        with open(SETTINGS_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        keys = key_path.split(".")
        value = data
        for key in keys:
            value = value[key]
        return value
    except (IOError, KeyError, json.JSONDecodeError) as e:
        logger.warning(
            f"Could not read setting '{key_path}'. Error: {e}. Returning default value."
        )
        return default


def set_setting(key_path: str, value) -> bool:
    """
    Writes a nested setting to settings.json using a dot-separated path.
    This function performs an atomic write to prevent data corruption.
    """
    os.makedirs(YIM_FOLDER_PATH, exist_ok=True)

    data = {}
    if os.path.exists(SETTINGS_FILE_PATH):
        try:
            with open(SETTINGS_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            corrupted_path = SETTINGS_FILE_PATH + ".corrupted"
            logger.error(
                f"Could not read settings file, it might be corrupted. Backing it up to '{corrupted_path}' and starting fresh. Error: {e}"
            )
            try:
                shutil.copy(SETTINGS_FILE_PATH, corrupted_path)
            except IOError:
                pass
            data = {}  # Start with fresh data if file is corrupted

    try:
        keys = key_path.split(".")
        d = data
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value

        temp_file_path = SETTINGS_FILE_PATH + ".tmp"
        with open(temp_file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        # Replace the original file with the temporary file
        shutil.move(temp_file_path, SETTINGS_FILE_PATH)

        logger.info(f"Successfully set '{key_path}' to '{value}'.")
        return True

    except (
        IOError,
        TypeError,
    ) as e:
        logger.exception(f"Failed to write setting '{key_path}'. Error: {e}")
        return False
