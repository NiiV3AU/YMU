# ymu_config.py - YMU's own settings store (%APPDATA%/YMU/config.json).
# Strictly separate from YimMenu's settings.json (see settings_manager.py).
import copy
import json
import logging
import os
import shutil
import threading
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal

from paths import YMU_CONFIG_FILE_PATH

logger = logging.getLogger(__name__)

CONFIG_VERSION = 2

DEFAULTS = {
    "config_version": CONFIG_VERSION,
    "theme": "dark",
    "locale": "en_US",
    "mode": "legacy",
    # True once the user has picked an edition via the sidebar toggle. Until
    # then, YMU may auto-select the edition based on what is installed.
    "mode_user_set": False,
    "paths": {
        "gta_dir": None,
        "custom_dll": None,
    },
}


class YmuConfig(QObject):
    """Thread-safe, atomic JSON config store for all YMU-own settings."""

    changed = Signal(str, object)  # (dot-key, new value)

    def __init__(self, config_path: str = YMU_CONFIG_FILE_PATH):
        super().__init__()
        self._path = config_path
        self._lock = threading.RLock()
        self._data = self._load()

    # --- loading / migration ---

    def _load(self) -> dict:
        data = None
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("config root is not a JSON object")
            except (OSError, json.JSONDecodeError, ValueError) as e:
                logger.error(f"Config file unreadable ({e}). Backing up and resetting.")
                self._backup_corrupt_file()
                data = None

        if data is None:
            data = copy.deepcopy(DEFAULTS)
            self._write_locked(data)
            return data

        if self._migrate(data):
            self._write_locked(data)
        return data

    def _backup_corrupt_file(self):
        try:
            shutil.copyfile(self._path, self._path + ".bak")
            logger.info(f"Corrupt config backed up to {self._path}.bak")
        except OSError as e:
            logger.error(f"Could not back up corrupt config: {e}")

    def _migrate(self, data: dict) -> bool:
        """Fills in missing defaults (covers flat v1.1.6 configs with only
        'theme'/'locale'). Existing values always win. Returns True if changed."""

        def merge_defaults(target: dict, defaults: dict) -> bool:
            changed = False
            for key, default_value in defaults.items():
                if key not in target:
                    target[key] = copy.deepcopy(default_value)
                    changed = True
                elif isinstance(default_value, dict) and isinstance(target[key], dict):
                    changed = merge_defaults(target[key], default_value) or changed
            return changed

        changed = merge_defaults(data, DEFAULTS)
        if data.get("config_version") != CONFIG_VERSION:
            data["config_version"] = CONFIG_VERSION
            changed = True
        if changed:
            logger.info(f"Config migrated to version {CONFIG_VERSION}.")
        return changed

    # --- persistence ---

    def _write_locked(self, data: dict) -> bool:
        """Atomic write. Caller must hold the lock (or be in __init__)."""
        tmp_path = self._path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            os.replace(tmp_path, self._path)
            return True
        except OSError as e:
            logger.error(f"Failed to write YMU config: {e}")
            return False

    # --- public API ---

    def get(self, key_path: str, default: Any = None) -> Any:
        """Reads a (nested) setting via dot notation, e.g. 'paths.gta_dir'."""
        with self._lock:
            value: Any = self._data
            try:
                for key in key_path.split("."):
                    value = value[key]
            except (KeyError, TypeError):
                return default
            return copy.deepcopy(value) if isinstance(value, (dict, list)) else value

    def set(self, key_path: str, value: Any) -> bool:
        """Writes a (nested) setting and persists atomically."""
        with self._lock:
            keys = key_path.split(".")
            d = self._data
            for key in keys[:-1]:
                if key not in d or not isinstance(d[key], dict):
                    d[key] = {}
                d = d[key]
            d[keys[-1]] = value
            success = self._write_locked(self._data)
        if success:
            logger.info(f"YMU config: set '{key_path}' = '{value}'")
            self.changed.emit(key_path, value)
        return success

    def get_all(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._data)


_config: Optional[YmuConfig] = None
_config_lock = threading.Lock()


def get_config() -> YmuConfig:
    """Returns the process-wide YmuConfig singleton."""
    global _config
    with _config_lock:
        if _config is None:
            _config = YmuConfig()
        return _config
