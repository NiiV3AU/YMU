# menu_modes.py - Single source of truth for the two YimMenu editions.
# Lua scripts carry no version metadata; which edition a script belongs to is
# determined solely by the AppData directory it is read from. This module also
# knows how to locate and launch each edition (registry keys, Steam URIs).
import dataclasses
import logging
import os

from paths import (
    YIMMENU_APPDATA_DIR,
    YIMMENU_DISABLED_SCRIPTS_DIR,
    YIMMENU_SCRIPTS_DIR,
    YIMMENU_SETTINGS_FILE_PATH,
    YIMMENUV2_APPDATA_DIR,
    YIMMENUV2_DISABLED_SCRIPTS_DIR,
    YIMMENUV2_SCRIPTS_DIR,
    YIMMENUV2_SETTINGS_FILE_PATH,
)

logger = logging.getLogger(__name__)

# The Rockstar launcher is store-agnostic; the same Epic URI opens it and it
# then picks the edition itself. There is no separate Epic Enhanced URI.
EPIC_LAUNCH_URI = (
    "com.epicgames.launcher://apps/"
    "9d2d0eb64d5c44529cece33fe2a46482?action=launch&silent=true"
)


@dataclasses.dataclass(frozen=True)
class MenuMode:
    """Everything that differs between GTA V Legacy and Enhanced."""

    key: str
    display_name: str
    appdata_dir: str
    scripts_dir: str
    disabled_scripts_dir: str
    settings_file: str
    target_executables: tuple[str, ...]
    repo: str
    dll_name: str
    steam_uri: str
    registry_subkeys: tuple[str, ...]
    # Executables to launch from an install directory, in priority order.
    launch_executables: tuple[str, ...]


LEGACY = MenuMode(
    key="legacy",
    display_name="YimMenu (Legacy)",
    appdata_dir=YIMMENU_APPDATA_DIR,
    scripts_dir=YIMMENU_SCRIPTS_DIR,
    disabled_scripts_dir=YIMMENU_DISABLED_SCRIPTS_DIR,
    settings_file=YIMMENU_SETTINGS_FILE_PATH,
    target_executables=("gta5.exe",),
    repo="Mr-X-GTA/YimMenu",
    dll_name="YimMenu.dll",
    steam_uri="steam://run/271590",
    registry_subkeys=(
        r"SOFTWARE\Rockstar Games\Grand Theft Auto V",
        r"SOFTWARE\WOW6432Node\Rockstar Games\Grand Theft Auto V",
    ),
    launch_executables=("PlayGTAV.exe", "GTA5.exe"),
)

ENHANCED = MenuMode(
    key="enhanced",
    display_name="YimMenuV2 (Enhanced)",
    appdata_dir=YIMMENUV2_APPDATA_DIR,
    scripts_dir=YIMMENUV2_SCRIPTS_DIR,
    disabled_scripts_dir=YIMMENUV2_DISABLED_SCRIPTS_DIR,
    settings_file=YIMMENUV2_SETTINGS_FILE_PATH,
    target_executables=("gta5_enhanced.exe",),
    repo="YimMenu/YimMenuV2",
    dll_name="YimMenuV2.dll",
    steam_uri="steam://run/3240220",
    registry_subkeys=(
        r"SOFTWARE\Rockstar Games\GTAV Enhanced",
        r"SOFTWARE\WOW6432Node\Rockstar Games\GTAV Enhanced",
    ),
    launch_executables=("PlayGTAV.exe", "GTA5_Enhanced.exe"),
)

MODES: dict[str, MenuMode] = {LEGACY.key: LEGACY, ENHANCED.key: ENHANCED}


def get_mode(key: str) -> MenuMode:
    """Returns the mode for a config key, falling back to Legacy."""
    return MODES.get(key, LEGACY)


def get_install_dir(mode: MenuMode) -> str | None:
    """Returns the edition's install directory via the Rockstar registry keys,
    or None if it cannot be found (e.g. Steam/Epic installs that do not write
    these keys)."""
    try:
        import winreg
    except ImportError:
        return None

    for subkey in mode.registry_subkeys:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, subkey, 0, winreg.KEY_READ
            ) as regkey:
                path, _ = winreg.QueryValueEx(regkey, "InstallFolder")
            if path:
                path = path.strip('"').strip()
                if os.path.isdir(path):
                    logger.info(
                        f"Found {mode.display_name} install dir via registry: {path}"
                    )
                    return path
        except OSError:
            continue
    return None


def detect_installed_modes() -> list[str]:
    """Best-effort detection of which editions are installed, via the Rockstar
    registry keys. Returns a list of mode keys (possibly empty)."""
    return [m.key for m in MODES.values() if get_install_dir(m) is not None]
