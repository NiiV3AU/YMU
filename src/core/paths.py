# paths.py - Defines, creates, and manages all application file paths.
import os
import sys

LOCAL_VERSION = "v1.1.9"
APP_URL = "https://github.com/NiiV3AU/YMU"
USER_AGENT = f"YMU/{LOCAL_VERSION} (+{APP_URL})"


def get_required_env(env_var: str) -> str:
    """Gets an environment variable that is required for the app to run."""
    value = os.getenv(env_var)
    if value is None:
        raise OSError(f"Required environment variable '{env_var}' is not set.")
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
YMU_CACHE_FILE_PATH = os.path.join(YMU_APPDATA_DIR, "cache.json")

# YimMenu directories are intentionally NOT created here: their absence is
# how YMU detects that an edition is not installed yet.
YIMMENU_APPDATA_DIR = os.path.join(APPDATA_PATH, "YimMenu")
YIMMENU_SCRIPTS_DIR = os.path.join(YIMMENU_APPDATA_DIR, "scripts")
YIMMENU_DISABLED_SCRIPTS_DIR = os.path.join(YIMMENU_SCRIPTS_DIR, "disabled")
YIMMENU_SETTINGS_FILE_PATH = os.path.join(YIMMENU_APPDATA_DIR, "settings.json")

YIMMENUV2_APPDATA_DIR = os.path.join(APPDATA_PATH, "YimMenuV2")
YIMMENUV2_SCRIPTS_DIR = os.path.join(YIMMENUV2_APPDATA_DIR, "scripts")
YIMMENUV2_DISABLED_SCRIPTS_DIR = os.path.join(YIMMENUV2_SCRIPTS_DIR, "disabled")
YIMMENUV2_SETTINGS_FILE_PATH = os.path.join(YIMMENUV2_APPDATA_DIR, "settings.json")
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
        return os.path.join(sys._MEIPASS, relative_path)

    # 1. Try relative to sys.argv[0] directory
    argv_base = os.path.dirname(os.path.abspath(sys.argv[0]))
    candidate = os.path.join(argv_base, relative_path)
    if os.path.exists(candidate):
        return candidate

    # 2. Try relative to src/ directory (since paths.py is located in src/core/)
    src_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(src_base, relative_path)
    if os.path.exists(candidate):
        return candidate

    return candidate
