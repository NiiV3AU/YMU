import copy
import json
import logging
import os
import re
import shutil
import threading
import time
from typing import TYPE_CHECKING

import requests
from PySide6.QtCore import QObject, Qt, Signal

from core.config import get_config
from core.paths import USER_AGENT, YMU_LANG_DIR, resource_path

if TYPE_CHECKING:
    from core.worker_manager import WorkerManager

logger = logging.getLogger(__name__)

PRIMARY_LANG_URL = "https://ymu.pages.dev/translations.json"
FALLBACK_LANG_URL = (
    "https://api.github.com/repos/NiiV3AU/YMU/contents/translations.json"
)

SUPPORTED_LOCALES: frozenset[str] = frozenset({
    "en_US",
    "de_DE",
    "nl_NL",
    "fr_FR",
    "es_ES",
    "pt_BR",
    "pl_PL",
    "ru_RU",
    "uk_UA",
    "tr_TR",
    "zh_Hans",
    "zh_Hant",
    "zh_TW",
    "ja_JP",
    "ko_KR",
    "ar_SA",
})

# A local translations.json may add new locales at runtime, using POSIX underscore
# format (language[_Script][_REGION]) with at least one subtag present.
# This project ships region-only codes (en_US, zh_TW) and script-only codes
# (zh_Hans, zh_Hant). The original ^[a-z]{2}_[A-Z]{2}$ pattern rejected the
# latter and silently quarantined a valid local file; "zh_Hans" carries no
# region at all, so the region subtag cannot be required either. A bare
# language code ("en") stays rejected - it is far more likely a stray key.
_LOCALES = re.compile(
    r"^[a-z]{2,3}(?:_[A-Z][a-z]{3})?_[A-Z]{2}$|^[a-z]{2,3}_[A-Z][a-z]{3}$"
)

LOCAL_FILE_PATH = os.path.join(YMU_LANG_DIR, "translations.json")
# Sidecar paths, spelled once so the quarantine target can never drift from
# the file it is derived from.
LOCAL_FILE_BAK_PATH = LOCAL_FILE_PATH + ".bak"
LOCAL_FILE_TMP_PATH = LOCAL_FILE_PATH + ".tmp"

FALLBACK_DATA = {
    "en_US": {
        "meta": {
            "name": "English (US)",
            "direction": "ltr",
        },
        "Sidebar": {
            "Risks": "Risks",
            "Download": "Download",
            "Inject": "Inject",
            "Settings": "Settings",
            "Tooltip": {
                "Risks": "Show important warnings and information",
                "ProjectPage": "Open the YMU project page in your browser",
            },
            "Mode": {
                "Legacy": "Legacy",
                "Enhanced": "E&E",
                "Tooltip": "Switch between YimMenu (Legacy) and YimMenuV2 (Enhanced)",
                "AutoDetected": "Detected {0} — selected it automatically.\nUse the sidebar switch to change it.",
            },
        },
        "Common": {
            "Error": "Error",
            "Info": "Information",
            "UnexpectedError": "An unexpected error occurred",
            "Restart": "Restart Now",
            "Yes": "Yes",
            "No": "No",
            "RestartAdmin": "Restart as Admin",
            "Cancel": "Cancel",
            "Notify": {
                "ConfigSaveFailed": "Failed to save setting to disk.",
                "RestartFailedTitle": "Restart Failed",
                "RestartFailedMsg": "Failed to restart application:\n{0}",
            },
        },
        "Risk": {
            "Title": "ATTENTION",
            "Info": "Always use YMU and YimMenu with BattlEye DISABLED.\nUsing mods online carries a risk of being banned.",
            "Btn": {
                "YimOfficial": "Official YimMenu GitHub Repo",
                "YimLegacy": "YimMenu (Legacy) GitHub Repo",
                "YimV2": "YimMenuV2 (Enhanced) GitHub Repo",
                "FSL": "FSL's UnknownCheats Thread",
            },
            "Tooltip": {
                "YimOfficial": "Open the official YimMenu GitHub repository",
                "YimLegacy": "Open the YimMenu (Legacy) GitHub repository",
                "YimV2": "Open the YimMenuV2 (Enhanced) GitHub repository",
                "FSL": "Open the FSL thread on UnknownCheats for download & support",
            },
        },
        "Download": {
            "Status": {
                "Initial": "Select a channel to check for updates.",
                "Checking": "Checking for updates...",
                "UpToDate": "YimMenu is up-to-date.",
                "NewVersion": "A new version is available!",
                "Error": "An error occurred. Please try again.",
                "Downloading": "Downloading",
                "Success": "Download successful and verified!",
                "Failed": "Download failed. Check logs.",
                "SuccessUnverified": "Download successful (unverified)!",
            },
            "Btn": {
                "Check": "Check for Updates",
                "Checking": "Checking...",
                "UpToDate": "Up-to-date",
                "Update": "Update",
                "Download": "Download",
                "Retry": "Retry Check",
                "Downloading": "Downloading...",
            },
            "Notify": {
                "NewVersion": "A new version is ready to be downloaded.",
                "CheckFailed": "Failed to check for updates",
                "SuccessTitle": "Download Complete",
                "SuccessMsg": "DLL successfully downloaded and verified!",
                "FailedTitle": "Download Failed",
                "FailedMsg": "Verification failed. Please check the logs.",
                "UpdateTitle": "{0} Update",
                "SuccessMsgUnverified": "DLL downloaded successfully, but could not be verified (no remote checksum).",
            },
            "Help": {
                "Title": "DLL & FSL Info",
                "DllSteps": "1. Click on [Download]\n2. Wait for the download to finish\n3. The file is in the '%LOCALAPPDATA%/YMU/dll' folder\n\nIf the file gets deleted, add an exception\nin your antivirus or disable it temporarily.",
                "FslSteps": "1. Download FSL (link provided in the Risks tab)\n2. Open your GTA V directory\n3. Drop the WINMM.dll in the folder\n   (filename MUST be exactly 'WINMM.dll')\n4. Disable BattlEye in the Rockstar Games Launcher\n5. Done!",
            },
            "Tooltip": {
                "Help": "Show help for DLL and FSL installation",
                "Channel": "Select the YimMenu version to download",
                "ActiveChannel": "Active edition — change it with the Legacy/Enhanced switch in the sidebar",
            },
            "Dialog": {
                "UnverifiedTitle": "Unverified DLL Download",
                "UnverifiedPrompt": "No SHA256 checksum was provided with this release.\n\nYMU cannot verify the integrity or authenticity of the file.\n\nDo you want to download it anyway?",
                "DownloadAnyway": "Download anyway",
            },
            "Error": {
                "RateLimited": "GitHub API rate limit reached. Please try again in {0} minutes.",
                "FileLocked": "YimMenu.dll is currently in use by GTA V or another process. Please close GTA V and try again.",
            },
        },
        "Inject": {
            "Launcher": {
                "Select": "Select Launcher",
                "CustomPath": "Custom Path",
            },
            "Btn": {
                "StartGta": "Start GTA V",
                "InjectBase": "Inject YimMenu",
                "NoDll": "No DLL found",
                "InjectFile": "Inject {0}",
            },
            "Notify": {
                "AlreadyRunning": "GTA V is already running!",
                "SelectLauncher": "Please select a launcher first.",
                "SuccessTitle": "Injection Successful",
                "SuccessMsg": "Successfully injected DLL!",
                "CustomDllMissing": "The configured custom DLL no longer exists:\n{0}",
                "LaunchTimeout": "GTA V didn't start (or was closed before it loaded).\nYou can try launching again.",
            },
            "Help": {
                "Title": "Injection Info",
                "StartGtaSteps": "1. Select your launcher\n2. Press [Start GTA V]\n3. Read the next step",
                "TabInject": "Inject DLL",
                "InjectSteps": "1. Start GTA V (Previous Step)\n2. Wait for the game's start screen/menu\n3. Click on [Inject YimMenu]\n4. Wait for YimMenu to finish loading\n5. Done!",
            },
            "Tooltip": {
                "Help": "Show help for the injection process",
                "Launcher": "Select the launcher you use to start GTA V",
                "Dll": "Select the DLL to inject",
                "NoDll": "Download the {0} DLL on the Download tab first.",
            },
            "Error": {
                "NoDllSelected": "Error: No DLL selected or found for injection.",
                "ProcessLost": "GTA V process disappeared before injection.",
                "InjectionFailed": "Injection failed. See logs for details.",
                "NoRockstarPath": "Could not find Rockstar Games installation path.",
                "CustomPathInvalid": "The custom GTA V path is not set or no longer exists.\nSet it again on the Settings tab.",
                "NoExeFound": "Executable not found at '{0}'",
                "LaunchFailed": "Error launching game. See logs for details.",
                "AccessDenied": "Missing permissions to inject into GTA V.\nTry restarting YMU as Administrator.",
                "AccessDeniedAdmin": "Injection was denied even with Administrator rights.\nThis is usually caused by BattlEye or a wrong game edition.\nDisable BattlEye in your launcher (see Risks tab) and make\nsure the Legacy/Enhanced switch matches your game.",
                "VerificationFailedTitle": "Injection Unconfirmed",
                "VerificationFailed": "The DLL injection was triggered, but the module could not be verified in GTA V's memory.\n\nThis usually happens when BattlEye is active, an antivirus blocked it, or the game crashed.",
                "RedownloadAction": "Re-download DLL",
                "ModuleNotFoundTitle": "Injection Failed",
                "ModuleNotFound": "GTA V could not load the YimMenu DLL — it may be incomplete or missing a dependency.\nRe-download it on the Download page. If it keeps failing, install the latest Microsoft Visual C++ Redistributable (x64).",
                "DllMissingTitle": "DLL Not Found",
                "DllMissing": "The menu DLL wasn't found on disk.\nYour antivirus may have quarantined it — YimMenu is often flagged. Add an exclusion, then re-download it on the Download page.",
                "NotADllTitle": "Not a Valid DLL",
                "NotADll": "The selected file isn't a valid Windows DLL.\nPick the correct YimMenu DLL, or use YMU's built-in download to get the right one.",
                "BadArchTitle": "Incompatible DLL",
                "BadArch": "GTA V needs a 64-bit YimMenu DLL, but the selected DLL isn't compatible.\nUse the official DLL for your edition — both Legacy and Enhanced are 64-bit.",
                "ProcessGoneTitle": "Game Closed",
                "ProcessGone": "GTA V closed before injection finished.\nStart the game, wait for it to finish loading, then try again.",
                "Unknown": "Injection failed for an unexpected reason.\nSee ymu.log for the full error.\n\nDetails: {0}",
            },
            "Label": {
                "Custom": "custom",
            },
            "BattlEye": {
                "Title": "BattlEye Is Running",
                "Warn": "BattlEye is active. Injecting while it runs can get your account banned and will often fail outright.\n\nThis is entirely your decision and at your own risk — disabling BattlEye in your launcher first is strongly recommended.",
                "Proceed": "Inject anyway",
                "Learn": "How to disable",
            },
        },
        "Settings": {
            "Header": {
                "Appearance": "Appearance",
                "Injection": "Injection",
                "Lua": "Lua Settings",
                "Maintenance": "Maintenance",
                "Other": "Other",
                "Paths": "Custom Paths",
            },
            "Inject": {
                "AutoClose": "Auto-Close after Injection",
                "SoundFeedback": "Sound Feedback on Success",
                "Tooltip": {
                    "AutoClose": "Automatically close YMU once the DLL has been injected into the game",
                    "SoundFeedback": "Play an audible confirmation chime when injection or download completes successfully",
                },
            },
            "Label": {
                "Language": "Language",
            },
            "Theme": {
                "Dark": "Dark",
                "Light": "Light",
            },
            "Lua": {
                "AutoReload": "Auto-reload changed scripts",
                "ListDisabled": "Disabled",
                "ListEnabled": "Enabled",
                "Btn": {
                    "DisableAll": "Disable All",
                    "EnableAll": "Enable All",
                },
                "Tooltip": {
                    "AutoReload": "Automatically re-apply changes when Lua script files are saved",
                    "Enable": "Enable selected script(s)",
                    "Disable": "Disable selected script(s)",
                    "Refresh": "Refresh script lists",
                    "DisableAll": "Disable all scripts at once (Safe Mode)",
                    "EnableAll": "Re-enable all disabled scripts",
                },
                "NoScriptsDir": "The {0} folder hasn't been created yet.\nInject and run YimMenu once to generate it.",
            },
            "Other": {
                "DebugConsole": "Enable External Debug Console",
                "Tooltip": {
                    "Debug": "Show YimMenu's external console window for detailed logs and debugging",
                },
            },
            "Btn": {
                "OpenScripts": "Open Scripts Folder",
                "DiscoverLua": "Discover Lua Scripts",
                "OpenYimFolder": "Open YimMenu Folder",
                "OpenYimV2Folder": "Open YimMenuV2 Folder",
                "OpenYmuFolder": "Open YMU Folder",
                "OpenLog": "Open YimMenu Log",
                "OpenV2Log": "Open YimMenuV2 Log",
                "ResetCaches": "Clear Pointer Caches",
                "ReportBug": "Report a Bug",
                "RequestFeature": "Request a Feature",
                "CheckUpdates": "Check for YMU Updates",
                "UpToDate": "YMU is up-to-date",
            },
            "Tooltip": {
                "OpenScripts": "Open the folder where your Lua scripts are located",
                "DiscoverLua": "Open the official YimMenu-Lua GitHub organization to find new scripts",
                "OpenYimFolder": "Open YimMenu folder (%APPDATA%/YimMenu)",
                "OpenYimV2Folder": "Open YimMenuV2 folder (%APPDATA%/YimMenuV2)",
                "OpenYmuFolder": "Open YMU folder (%APPDATA%/YMU)",
                "OpenLog": "Open the active edition's cout.log in your text editor",
                "ResetCaches": "Deletes cached binary offsets. Recommended after game updates if the menu crashes on launch.",
                "ReportBug": "Open the bug report page on GitHub in your browser",
                "RequestFeature": "Open the feature request page on GitHub in your browser",
                "Language": "Select application language (requires restart)",
                "UpdateLang": "Check for translation updates",
            },
            "Update": {
                "Title": "YMU Updates",
                "UpToDate": "Your YMU is already up-to-date.",
                "AvailableTitle": "Update Available",
                "AvailableMsg": "Update {0} is available!",
                "Prompt": "Do you want to open the download page in your browser?",
                "CheckTitle": "Check for YMU Updates",
                "ErrorTitle": "Update Error",
                "Ahead": "You are running a newer version than the latest release.",
            },
            "Notify": {
                "RestartRequired": "Please restart YMU to apply the new language.",
                "LangUpdated": "Translations were successfully downloaded.\nRestart YMU to see the updated Language List in Settings.",
                "LangTitle": "Language Changed",
                "LangUpToDate": "Translations are already up-to-date.",
                "V2FileMissing": "YimMenuV2 has no settings.json yet.\nInject and run it once, then try again.",
                "SettingWriteFailed": "Failed to save setting to settings.json.",
                "FolderMissing": "Folder does not exist yet:\n{0}",
                "FileMissing": "File does not exist yet:\n{0}",
                "OpenFolderFailed": "Could not open folder:\n{0}",
                "NoGtaDirFound": "Could not find your GTA V directory. Please browse and select your GTA V install folder first.",
                "BattlEyeDisabledTitle": "BattlEye Disabled",
                "BattlEyeDisabledMsg": "Added -nobattleye to commandline.txt in your GTA V directory.",
                "BattlEyeRestoredTitle": "BattlEye Restored",
                "BattlEyeRestoredMsg": "Removed -nobattleye from commandline.txt.",
                "CachesClearedTitle": "Caches Cleared",
                "CachesClearedMsg": "{0} cache file(s) cleared successfully.",
                "NoCachesMsg": "No cache files found to clear.",
                "LuaSafeModeEnabled": "{0} script(s) moved to disabled (Safe Mode).",
                "LuaSafeModeDisabled": "{0} script(s) re-enabled.",
            },
            "Notice": {
                "LegacyOnly": "Only available in YimMenu Legacy",
            },
            "Paths": {
                "GtaDir": "GTA V install folder",
                "CustomDll": "Custom menu DLL",
                "Browse": "Browse",
                "Clear": "Clear",
                "AutoDetect": "Auto-detected",
                "DefaultDll": "Use downloaded DLL",
                "ErrorNotFound": "Path does not exist.",
                "ErrorNoGta": "No GTA V executable found in this folder.",
                "ErrorNotDll": "Please select a .dll file.",
                "ErrorWriteCommandline": "Could not modify commandline.txt. Please check file permissions.",
                "OpenLogFailed": "Could not open log file:\n{0}",
                "ErrorAccess": "Cannot access folder: {0}",
                "NoBattlEye": "Disable BattlEye (commandline.txt)",
                "FslDetected": "FSL (WINMM.dll): Detected",
                "FslDeprecated": "FSL (version.dll): Outdated (Crash risk)",
                "FslMissing": "FSL (WINMM.dll): Not found (optional: local save data)",
                "FslHelp": "FSL Info",
                "Tooltip": {
                    "NoBattlEye": "Adds or removes -nobattleye in commandline.txt in your GTA V directory to run without BattlEye",
                    "Fsl": "View important FSL information and download link on the Risks page",
                    "FslDeprecated": "Outdated version.dll found! This legacy file causes game crashes. Please delete it and install WINMM.dll from the FSL thread.",
                },
            },
            "Badge": {
                "LegacyOnly": "Legacy only",
            },
        },
        "About": {
            "Title": "About YMU",
            "Subtitle": "The smart launcher for YimMenu: Always updated, always ready.",
            "Description": "The smart launcher, updater, and injector for YimMenu and YimMenuV2.",
            "TabGeneral": "General",
            "TabLicenses": "Licenses",
            "TabCredits": "Credits",
            "BtnWebsite": "Website",
            "BtnGitHub": "GitHub",
            "BtnClose": "Close",
            "BtnOpenOnline": "Open Online",
            "BtnLabel": "About YMU",
            "Tooltip": "View project information, dependencies, and open-source licenses",
            "Features": "Key Features",
            "Environment": "Environment",
            "ShieldNotice": "Free for non-commercial and permitted use under PolyForm Shield License 1.0.0.",
            "FeatureDualEdition": "<b>Dual-Edition Support:</b> Seamless switching between GTA V Legacy (YimMenu) and Enhanced (YimMenuV2) with independent settings.",
            "FeatureAutoUpdates": "<b>Automated DLL Management:</b> Automatic update checks on startup, one-click downloads, and SHA-256 integrity verification.",
            "FeatureSafeInjection": "<b>Native Injection Engine:</b> Safe Win32 DLL injection with BattlEye detection and in-memory verification.",
            "FeatureLuaManagement": "<b>Lua Script Manager:</b> Direct script discovery, safe-mode bulk actions, and instant folder access.",
            "FeatureAccessibility": "<b>Modern UI/UX:</b> Adaptive Dark/Light themes, full RTL layout support, and {0} localizations.",
            "LicensesNotice": "YimMenuUpdater is source-available software built upon free and open-source libraries. We gratefully acknowledge the following projects:",
            "CreditsLeadTitle": "Lead Developer & Architecture",
            "CreditsLeadDesc": "Creator and maintainer of YimMenuUpdater (YMU).",
            "CreditsModTitle": "Mod Menu Development",
            "CreditsModDesc": "Development and maintenance of the open-source YimMenu (Legacy) and YimMenuV2 (Enhanced Edition) mod menus.",
            "CreditsSaveTitle": "Local Saves",
            "CreditsSaveDesc": "UnknownCheats community contributors for the local GTA Online save redirection tool.",
            "CreditsTestTitle": "Community & Beta Testers",
            "CreditsTestDesc": "Special thanks to all community members and beta testers who tested pre-release builds, verified bug fixes, and suggested improvements across game updates.",
        },
        "Context": {
            "Undo": "Undo",
            "Redo": "Redo",
            "Cut": "Cut",
            "Copy": "Copy",
            "Paste": "Paste",
            "Delete": "Delete",
            "SelectAll": "Select All",
            "Browse": "Browse...",
            "OpenExplorer": "Show in Explorer",
            "Clear": "Clear",
        },
    }
}


class LocalizationManager(QObject):
    update_finished = Signal(bool, str, bool)
    layout_direction_changed = Signal(Qt.LayoutDirection)
    locale_changed = Signal(str)

    def __init__(self, worker_manager: "WorkerManager | None" = None):
        super().__init__()
        global _instance
        _instance = self
        self.worker_manager = worker_manager
        self.config = get_config()
        self.active_locale = self.config.get("locale", "en_US")
        self._lock = threading.RLock()
        self._is_updating = False

        self.data: dict = copy.deepcopy(FALLBACK_DATA)
        self.load_local_file()

    @classmethod
    def _validate_translation_payload(cls, payload: object) -> bool:
        """Validates that a translation payload is a dict where every top-level key
        matches a POSIX locale pattern and is in SUPPORTED_LOCALES, with valid metadata
        (name: str, direction: 'ltr' | 'rtl') and recursive string leaves."""
        if not isinstance(payload, dict):
            logger.warning("Translation payload rejected: root is not a dictionary.")
            return False

        def _has_only_string_leaves(node: object) -> bool:
            if isinstance(node, dict):
                if not node:
                    return False
                return all(
                    isinstance(k, str) and _has_only_string_leaves(v)
                    for k, v in node.items()
                )
            return isinstance(node, str)

        for locale_code, content in payload.items():
            if not isinstance(locale_code, str) or not _LOCALES.match(locale_code):
                logger.warning(
                    "Translation payload rejected: invalid locale tag '%s'.",
                    locale_code,
                )
                return False
            if locale_code not in SUPPORTED_LOCALES:
                logger.warning(
                    "Translation payload rejected: unsupported locale code '%s'.",
                    locale_code,
                )
                return False
            if not isinstance(content, dict):
                logger.warning(
                    "Translation payload rejected: content for '%s' is not a dictionary.",
                    locale_code,
                )
                return False
            meta = content.get("meta")
            if not isinstance(meta, dict):
                logger.warning(
                    "Translation payload rejected: missing meta section for '%s'.",
                    locale_code,
                )
                return False
            if not isinstance(meta.get("name"), str):
                logger.warning(
                    "Translation payload rejected: meta.name for '%s' is not a string.",
                    locale_code,
                )
                return False
            direction = meta.get("direction")
            if direction not in ("ltr", "rtl"):
                logger.warning(
                    "Translation payload rejected: meta.direction for '%s' must be 'ltr' or 'rtl' (got '%s').",
                    locale_code,
                    direction,
                )
                return False
            if not _has_only_string_leaves(content):
                logger.warning(
                    "Translation payload rejected: locale '%s' contains non-string leaves or empty dicts.",
                    locale_code,
                )
                return False
        return True

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        result = copy.deepcopy(base)
        for key, val in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(val, dict)
            ):
                result[key] = LocalizationManager._deep_merge(result[key], val)
            else:
                result[key] = copy.deepcopy(val)
        return result

    def is_rtl(self, locale_code: str | None = None) -> bool:
        """Returns True if the specified or active locale is a Right-to-Left (RTL) language."""
        with self._lock:
            code = locale_code if locale_code is not None else self.active_locale
            locale_node = self.data.get(code)
            if not isinstance(locale_node, dict):
                return False
            meta = locale_node.get("meta")
            if not isinstance(meta, dict):
                return False
            direction = meta.get("direction", "ltr")
            return str(direction).strip().lower() == "rtl"

    def get_layout_direction(
        self, locale_code: str | None = None
    ) -> Qt.LayoutDirection:
        """Returns Qt.LayoutDirection.RightToLeft if the locale is RTL, otherwise LeftToRight."""
        return (
            Qt.LayoutDirection.RightToLeft
            if self.is_rtl(locale_code)
            else Qt.LayoutDirection.LeftToRight
        )

    def set_locale(self, locale: str):
        """Saves the language in YMU's config and signals layout direction changes.

        INVARIANT: self._lock must NOT be held across self.config.set() or signal emits,
        as config.set emits changed() which may trigger callbacks re-entering LocalizationManager.
        """
        old_direction = self.get_layout_direction()
        with self._lock:
            has_locale = locale in self.data
            if not has_locale:
                logger.warning(
                    f"Attempted to switch to unknown locale '{locale}'; ignoring."
                )
                return
            self.active_locale = locale

        new_direction = self.get_layout_direction(locale)
        if self.config.set("locale", locale):
            logger.info(f"Locale switched and saved to YMU config: {locale}")
        self.locale_changed.emit(locale)
        if new_direction != old_direction:
            self.layout_direction_changed.emit(new_direction)

    def fetch_updates(self):
        """Start the update check manually (by clicking the button)."""
        if self.worker_manager is not None:
            started = self.worker_manager.run_exclusive(
                "lang_sync",
                self._update_from_remote_worker,
                on_finished=self._on_remote_update_finished,
                on_error=self._on_remote_update_error,
            )
            if not started:
                logger.info("Translation update already in progress.")
            return

        with self._lock:
            if self._is_updating:
                logger.info("Translation update already in progress.")
                return
            self._is_updating = True

        update_thread = threading.Thread(
            target=self._update_from_remote_thread, daemon=True
        )
        update_thread.start()

    def get_available_locales(self) -> list[str]:
        with self._lock:
            return list(self.data.keys())

    def get_language_name(self, locale_code: str) -> str:
        with self._lock:
            locale_node = self.data.get(locale_code)
            if not isinstance(locale_node, dict):
                return locale_code
            meta = locale_node.get("meta")
            if not isinstance(meta, dict):
                return locale_code
            return meta.get("name", locale_code)

    @staticmethod
    def _quarantine_local_file(src_path: str = LOCAL_FILE_PATH) -> None:
        """Quarantines an invalid or unreadable local translation file to .bak with timestamp rotation."""
        if not os.path.exists(src_path):
            return
        if os.path.exists(LOCAL_FILE_BAK_PATH):
            ts = int(time.time())
            ts_bak = f"{LOCAL_FILE_BAK_PATH}-{ts}"
            try:
                shutil.move(LOCAL_FILE_BAK_PATH, ts_bak)
                logger.info("Rotated existing translation backup to %s", ts_bak)
            except OSError as err:
                logger.warning(
                    "Failed to rotate existing backup %s: %s",
                    LOCAL_FILE_BAK_PATH,
                    err,
                )
        try:
            shutil.move(src_path, LOCAL_FILE_BAK_PATH)
            logger.info("Quarantined %s to %s", src_path, LOCAL_FILE_BAK_PATH)
        except OSError as err:
            logger.error(
                "Failed to quarantine %s to %s: %s",
                src_path,
                LOCAL_FILE_BAK_PATH,
                err,
            )

    def load_local_file(self):
        bundled_path = resource_path("translations.json")
        if os.path.exists(bundled_path):
            try:
                with open(bundled_path, encoding="utf-8-sig") as f:
                    loaded_data = json.load(f)
                    if isinstance(
                        loaded_data, dict
                    ) and self._validate_translation_payload(loaded_data):
                        self.data = self._deep_merge(self.data, loaded_data)
                        logger.info("Bundled translations.json loaded.")
                    elif isinstance(loaded_data, dict):
                        logger.warning(
                            "Bundled translations.json failed schema validation; skipping."
                        )
            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.error(f"Failed to load bundled translations.json: {e}")

        if not os.path.exists(LOCAL_FILE_PATH):
            return
        try:
            with open(LOCAL_FILE_PATH, encoding="utf-8-sig") as f:
                loaded_data = json.load(f)
            if not self._validate_translation_payload(loaded_data):
                logger.error(
                    "Local translations.json failed schema validation. Quarantining to .bak."
                )
                self._quarantine_local_file(LOCAL_FILE_PATH)
                return
            self.data = self._deep_merge(self.data, loaded_data)
            logger.info("Local translations.json loaded.")
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(
                f"Failed to load translations.json: {e}. Quarantining to .bak."
            )
            self._quarantine_local_file(LOCAL_FILE_PATH)

    def _read_local_raw_data(self) -> dict | None:
        if not os.path.exists(LOCAL_FILE_PATH):
            return None
        try:
            with open(LOCAL_FILE_PATH, encoding="utf-8-sig") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _update_from_remote_worker(self) -> tuple[bool, str, bool]:
        """Worker task executed via WorkerManager or thread."""
        tmp_path = LOCAL_FILE_TMP_PATH
        try:
            urls = [PRIMARY_LANG_URL, FALLBACK_LANG_URL]
            response = None
            last_error: Exception | None = None
            headers = {"User-Agent": USER_AGENT}

            for url in urls:
                try:
                    logger.info(f"Checking for translation updates from: {url}")
                    req_headers = dict(headers)
                    if "api.github.com" in url:
                        req_headers["Accept"] = "application/vnd.github.raw+json"
                    with requests.get(url, headers=req_headers, timeout=10) as resp:
                        if resp.status_code == 200:
                            response = resp
                            break
                        logger.warning(
                            f"Translation fetch from {url} returned HTTP {resp.status_code}"
                        )
                except (requests.RequestException, OSError) as e:
                    logger.warning(f"Failed to fetch translations from {url}: {e}")
                    last_error = e

            if response is None or response.status_code != 200:
                err_msg = (
                    str(last_error)
                    if last_error
                    else f"HTTP Error: {response.status_code if response else 'Unavailable'}"
                )
                logger.warning(f"Remote translations unavailable: {err_msg}")
                return (False, err_msg, False)

            remote_data = response.json()
            if isinstance(remote_data, dict) and self._validate_translation_payload(
                remote_data
            ):
                local_raw = self._read_local_raw_data()
                if local_raw is not None and local_raw == remote_data:
                    logger.info("Local translations are already up-to-date.")
                    msg = self.tr(
                        "Settings.Notify.LangUpToDate",
                        "Translations are already up-to-date.",
                    )
                    return (True, msg, False)
                else:
                    logger.info("New translations detected. Updating local file...")
                    os.makedirs(os.path.dirname(LOCAL_FILE_PATH), exist_ok=True)
                    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
                        json.dump(remote_data, f, indent=4, ensure_ascii=False)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(tmp_path, LOCAL_FILE_PATH)
                    with self._lock:
                        self.data = self._deep_merge(self.data, remote_data)
                    msg = self.tr(
                        "Settings.Notify.LangUpdated",
                        "Translations updated successfully!",
                    )
                    return (True, msg, True)
            else:
                logger.warning(
                    "Remote translation payload failed schema validation or is not a dictionary."
                )
                return (False, "Invalid translation schema received.", False)

        except (requests.RequestException, OSError, ValueError) as e:
            logger.warning(f"Could not check for translation updates: {e}")
            return (False, str(e), False)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _on_remote_update_finished(self, result: tuple[bool, str, bool]):
        success, msg, updated = result
        self.update_finished.emit(success, msg, updated)

    def _on_remote_update_error(self, error: Exception):
        logger.warning(f"Could not check for translation updates: {error}")
        self.update_finished.emit(False, str(error), False)

    def _update_from_remote_thread(self):
        """Internal method, runs in thread if WorkerManager not used."""
        try:
            result = self._update_from_remote_worker()
            self._on_remote_update_finished(result)
        except Exception as e:
            self._on_remote_update_error(e)
        finally:
            with self._lock:
                self._is_updating = False

    def tr(self, key_path: str, default: str | None = None, *args, **kwargs) -> str:
        # This intentionally shadows QObject.tr with a dictionary-based lookup.
        # *args/**kwargs keep the override signature-compatible with the base
        # method so static type checkers don't flag an LSP violation.
        if key_path == "Common.Error.ConfigSaveFailed":
            key_path = "Common.Notify.ConfigSaveFailed"
        keys = key_path.split(".")
        with self._lock:
            try:
                value = self.data.get(self.active_locale, {})
                for k in keys:
                    value = value[k]
                if isinstance(value, str):
                    return value
            except (KeyError, TypeError):
                pass

            if self.active_locale != "en_US":
                try:
                    fallback = self.data.get("en_US", {})
                    for k in keys:
                        fallback = fallback[k]
                    if isinstance(fallback, str):
                        return fallback
                except (KeyError, TypeError):
                    pass

        return default if default else f"[{key_path}]"


_instance: LocalizationManager | None = None


def get_localization_manager() -> LocalizationManager:
    global _instance
    if _instance is None:
        _instance = LocalizationManager()
    return _instance
