# paths.py - Defines, creates, and manages all application file paths.
import os
import sys

LOCAL_VERSION = "v1.1.6"
APP_URL = "https://github.com/NiiV3AU/YMU"
USER_AGENT = f"YMU/{LOCAL_VERSION} (+{APP_URL})"


def get_required_env(env_var: str) -> str:
    """Gets an environment variable that is required for the app to run."""
    value = os.getenv(env_var)
    if value is None:
        raise EnvironmentError(f"Required environment variable '{env_var}' is not set.")
    return value


def _create_path(path: str):
    """Helper function to ensure a directory exists."""
    os.makedirs(path, exist_ok=True)
    return path


APPDATA_PATH = get_required_env("APPDATA")

YMU_APPDATA_DIR = _create_path(os.path.join(APPDATA_PATH, "YMU"))
YMU_DLL_DIR = _create_path(os.path.join(YMU_APPDATA_DIR, "dll"))
YMU_LOG_FILE_PATH = os.path.join(YMU_APPDATA_DIR, "ymu.log")
YMU_CONFIG_FILE_PATH = os.path.join(YMU_APPDATA_DIR, "config.json")

YIMMENU_APPDATA_DIR = _create_path(os.path.join(APPDATA_PATH, "YimMenu"))
YIMMENU_SCRIPTS_DIR = os.path.join(YIMMENU_APPDATA_DIR, "scripts")
YIMMENU_DISABLED_SCRIPTS_DIR = os.path.join(YIMMENU_SCRIPTS_DIR, "disabled")
YIMMENU_SETTINGS_FILE_PATH = os.path.join(YIMMENU_APPDATA_DIR, "settings.json")
YMU_LANG_DIR = _create_path(os.path.join(YMU_APPDATA_DIR, "lang"))


def resource_path(relative_path: str) -> str:
    """
    Gets the absolute path to a resource.
    Works for:
    1. PyInstaller (_MEIPASS)
    2. Nuitka (sys.argv[0] dir or __file__)
    3. Normal Python Script
    """
    if hasattr(sys, "_MEIPASS"):
        base_path = getattr(sys, "_MEIPASS")
    else:
        base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        possible_path = os.path.join(base_path, relative_path)
        if not os.path.exists(possible_path):
            base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)
