# settings_manager.py - Manages reading and writing to YimMenu's settings.json.
# This module only ever touches YimMenu's own settings files; YMU's own
# settings live in ymu_config.py.
import json
import logging
import os
import shutil
import threading

from paths import YIMMENU_SETTINGS_FILE_PATH

logger = logging.getLogger(__name__)

SETTINGS_FILE_PATH = YIMMENU_SETTINGS_FILE_PATH

# Serializes the read-modify-write in set_setting so parallel writers cannot
# lose each other's changes or collide on the shared .tmp file.
_write_lock = threading.Lock()

# In-memory cache keyed by settings_file path: (mtime, data_dict)
_cache: dict[str, tuple[float, dict]] = {}


def _read_json_safely(settings_file: str) -> dict | None:
    """Reads the JSON file with in-memory caching based on file mtime.

    Returns {} if missing, dict if valid, or None if malformed/unreadable.
    Reads as utf-8-sig so a stray UTF-8 BOM (e.g. from a hand edit in some
    editors) is tolerated rather than treated as corruption; writes stay plain
    utf-8 so YMU never introduces a BOM of its own."""
    if not os.path.exists(settings_file):
        _cache.pop(settings_file, None)
        return {}

    try:
        mtime = os.path.getmtime(settings_file)
        if settings_file in _cache:
            cached_mtime, cached_data = _cache[settings_file]
            if cached_mtime == mtime:
                return cached_data

        with open(settings_file, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise TypeError("settings root is not a JSON object")

        _cache[settings_file] = (mtime, data)
        return data
    except (json.JSONDecodeError, TypeError, OSError) as e:
        logger.warning(f"Failed to read {settings_file}: {e}")
        return None


def get_setting(key_path: str, default=None, settings_file: str = SETTINGS_FILE_PATH):
    """
    Reads a nested setting.
    Example: get_setting("lua.enable_auto_reload_changed_scripts")
    """
    data = _read_json_safely(settings_file)
    if data is None:
        return default

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
        if data is None:
            # File exists but is corrupt. Create a .bak before proceeding.
            try:
                shutil.copyfile(settings_file, settings_file + ".bak")
                logger.info(f"Corrupt settings backed up to {settings_file}.bak")
            except OSError as e:
                logger.error(f"Could not back up corrupt settings: {e}")
            data = {}

        keys = key_path.split(".")
        d = data
        try:
            for key in keys[:-1]:
                if key not in d or not isinstance(d[key], dict):
                    d[key] = {}
                d = d[key]

            d[keys[-1]] = value
        except (TypeError, KeyError, IndexError) as e:
            logger.error(f"Error traversing settings dict: {e}")
            return False

        temp_file = settings_file + ".tmp"
        try:
            os.makedirs(os.path.dirname(settings_file), exist_ok=True)
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            os.replace(temp_file, settings_file)
            _cache[settings_file] = (os.path.getmtime(settings_file), data)
            logger.info(
                f"Successfully set '{key_path}' to '{value}' in {settings_file}"
            )
            return True
        except OSError as e:
            logger.error(f"Failed to write settings file: {e}")
            return False
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
