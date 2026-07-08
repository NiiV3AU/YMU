# settings_manager.py - Manages reading and writing to YimMenu's settings.json.
# This module only ever touches YimMenu's own settings files; YMU's own
# settings live in ymu_config.py.
import json
import logging
import os
import threading

from paths import YIMMENU_SETTINGS_FILE_PATH

logger = logging.getLogger(__name__)

SETTINGS_FILE_PATH = YIMMENU_SETTINGS_FILE_PATH

# Serializes the read-modify-write in set_setting so parallel writers cannot
# lose each other's changes or collide on the shared .tmp file.
_write_lock = threading.Lock()


def _read_json_safely(settings_file: str):
    """Reads the JSON file, returning {} if it is missing, unreadable, or malformed.

    Reads as utf-8-sig so a stray UTF-8 BOM (e.g. from a hand edit in some
    editors) is tolerated rather than treated as corruption; writes stay plain
    utf-8 so YMU never introduces a BOM of its own."""
    if not os.path.exists(settings_file):
        return {}
    try:
        with open(settings_file, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read {settings_file}: {e}")
        return {}


def get_setting(key_path: str, default=None, settings_file: str = SETTINGS_FILE_PATH):
    """
    Reads a nested setting.
    Example: get_setting("lua.enable_auto_reload_changed_scripts")
    """
    data = _read_json_safely(settings_file)

    keys = key_path.split(".")
    value = data
    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default


def set_setting(
    key_path: str,
    value,
    settings_file: str = SETTINGS_FILE_PATH,
    create_if_missing: bool = True,
) -> bool:
    """
    Writes a nested setting. Ensures parent keys exist.
    With create_if_missing=False the file is never created from scratch —
    used for YimMenuV2, whose settings schema YMU does not own.
    """
    with _write_lock:
        if not create_if_missing and not os.path.exists(settings_file):
            logger.warning(
                f"Refusing to create '{settings_file}' — it does not exist yet."
            )
            return False

        data = _read_json_safely(settings_file)

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

        temp_file = settings_file + ".tmp"
        try:
            os.makedirs(os.path.dirname(settings_file), exist_ok=True)
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            os.replace(temp_file, settings_file)
            logger.info(
                f"Successfully set '{key_path}' to '{value}' in {settings_file}"
            )
            return True
        except OSError as e:
            logger.error(f"Failed to write settings file: {e}")
            return False
