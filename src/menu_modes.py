# menu_modes.py - Single source of truth for the two YimMenu editions.
# Lua scripts carry no version metadata; which edition a script belongs to is
# determined solely by the AppData directory it is read from.
import dataclasses

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
)

MODES: dict[str, MenuMode] = {LEGACY.key: LEGACY, ENHANCED.key: ENHANCED}


def get_mode(key: str) -> MenuMode:
    """Returns the mode for a config key, falling back to Legacy."""
    return MODES.get(key, LEGACY)
