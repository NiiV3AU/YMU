import copy
import json
import logging
import os
import threading

import requests
from PySide6.QtCore import QObject, Signal

from core.config import get_config
from core.paths import USER_AGENT, YMU_LANG_DIR

logger = logging.getLogger(__name__)

REMOTE_LANG_URL = "https://raw.githubusercontent.com/NiiV3AU/YMU/main/translations.json"
LOCAL_FILE_PATH = os.path.join(YMU_LANG_DIR, "translations.json")

FALLBACK_DATA = {
    "en_US": {
        "meta": {"name": "English (US)"},
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
            "Cancel": "Cancel",
            "RestartAdmin": "Restart as Admin",
        },
        "Risk": {
            "Title": "ATTENTION",
            "Info": "Always use YMU and YimMenu with BattlEye DISABLED.\nUsing mods online carries a risk of being banned.",
            "Btn": {
                "YimOfficial": "Official YimMenu GitHub Repo",
                "YimLegacy": "YimMenu (legacy) GitHub Repo",
                "YimV2": "YimMenuV2 (enhanced) GitHub Repo",
                "FSL": "FSL's UC-Thread",
            },
            "Tooltip": {
                "YimOfficial": "Open the official YimMenu GitHub repository",
                "YimLegacy": "Open the YimMenu (legacy) GitHub repository",
                "YimV2": "Open the YimMenuV2 (enhanced) GitHub repository",
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
                "SuccessUnverified": "Download successful (unverified)!",
                "Failed": "Download failed. Check logs.",
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
                "SuccessMsgUnverified": "DLL downloaded successfully, but could not be verified (no remote checksum).",
                "FailedTitle": "Download Failed",
                "FailedMsg": "Verification failed. Please check the logs.",
                "UpdateTitle": "{0} Update",
            },
            "Dialog": {
                "UnverifiedTitle": "Unverified DLL Download",
                "UnverifiedPrompt": "No SHA256 checksum was provided with this release.\n\nYMU cannot verify the integrity or authenticity of the file.\n\nDo you want to download it anyway?",
                "DownloadAnyway": "Download anyway",
            },
            "Error": {
                "RateLimited": "GitHub API rate limit reached. Please try again in {0} minutes.",
            },
            "Help": {
                "Title": "DLL & FSL Info",
                "DllSteps": "1. Click on (Download)\n2. Wait for the download to finish\n3. The file is in the 'YMU/dll' folder\n\nIf the file gets deleted, add an exception\nin your antivirus or disable it temporarily.",
                "FslSteps": "1. Download FSL (Link provided in the Risks Page)\n2. Open your GTAV Directory\n3. Drop the WINMM.dll in the folder\n   (filename MUST be exactly 'WINMM.dll')\n4. Disable BattlEye in Rockstar's Game Launcher\n5. Done! ✅",
            },
            "Tooltip": {
                "Help": "Show help for DLL and FSL installation",
                "Channel": "Select the YimMenu version to download",
                "ActiveChannel": "Active edition — change it with the Legacy/Enhanced switch in the sidebar",
            },
        },
        "Inject": {
            "Launcher": {"Select": "Select Launcher", "CustomPath": "Custom Path"},
            "Btn": {
                "StartGta": "Start GTA 5",
                "InjectBase": "Inject YimMenu",
                "NoDll": "No DLL found",
                "InjectFile": "Inject {0}",
            },
            "Label": {"Custom": "custom"},
            "Notify": {
                "AlreadyRunning": "GTA 5 is already running!",
                "SelectLauncher": "Please select a launcher first.",
                "SuccessTitle": "Injection Successful",
                "SuccessMsg": "Successfully injected DLL!",
                "CustomDllMissing": "The configured custom DLL no longer exists:\n{0}",
                "LaunchTimeout": "GTA V didn't start (or was closed before it loaded).\nYou can try launching again.",
            },
            "BattlEye": {
                "Title": "BattlEye Is Running",
                "Warn": "BattlEye is active. Injecting while it runs can get your account banned and will often fail outright.\n\nThis is entirely your decision and at your own risk — disabling BattlEye in your launcher first is strongly recommended.",
                "Proceed": "Inject anyway",
                "Learn": "How to disable",
            },
            "Help": {
                "Title": "Injection Info",
                "StartGtaSteps": "1. Select your launcher\n2. Press 'Start GTA 5'\n3. Read the next step ↗",
                "TabInject": "Inject DLL",
                "InjectSteps": "1. Start GTA 5 (↖ Previous Step)\n2. Wait for the game's start screen/menu\n3. Click on 'Inject YimMenu'\n4. Wait for YimMenu to finish loading\n5. Done! ✅",
            },
            "Tooltip": {
                "Help": "Show help for the injection process",
                "Launcher": "Select the launcher you use to start GTA V",
                "Dll": "Select the DLL to inject",
                "NoDll": "Download the {0} DLL on the Download page first.",
            },
            "Error": {
                "NoDllSelected": "Error: No DLL selected or found for injection.",
                "ProcessLost": "GTA 5 process disappeared before injection.",
                "InjectionFailed": "Injection failed. See logs for details.",
                "NoRockstarPath": "Could not find Rockstar Games installation path.",
                "CustomPathInvalid": "The custom GTA V path is not set or no longer exists.\nSet it again on the Settings page.",
                "NoExeFound": "Executable not found at '{0}'",
                "LaunchFailed": "Error launching game. See logs for details.",
                "AccessDenied": "Missing permissions to inject into GTA V.\nTry restarting YMU as Administrator.",
                "AccessDeniedAdmin": "Injection was denied even with Administrator rights.\nThis is usually caused by BattlEye or a wrong game edition.\nDisable BattlEye in your launcher (see Risks page) and make\nsure the Legacy/Enhanced switch matches your game.",
                "RedownloadAction": "Re-download DLL",
            },
        },
        "Settings": {
            "Header": {
                "Appearance": "Appearance",
                "Lua": "Lua Settings",
                "Paths": "Custom Paths",
                "Other": "Other",
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
            },
            "Label": {"Language": "Language"},
            "Theme": {"Dark": "Dark", "Light": "Light"},
            "Lua": {
                "AutoReload": "Auto-reload changed scripts",
                "ListDisabled": "Disabled",
                "ListEnabled": "Enabled",
                "NoScriptsDir": "No {0} folder found yet.\nInject and run it once to create it.",
                "Tooltip": {
                    "AutoReload": "Automatically re-apply changes when Lua script files are saved",
                    "Enable": "Enable selected script(s)",
                    "Disable": "Disable selected script(s)",
                    "Refresh": "Refresh script lists",
                },
            },
            "Other": {
                "DebugConsole": "Enable External Debug Console",
                "Tooltip": {
                    "Debug": "Show YimMenu's external console window for detailed logs and debugging"
                },
            },
            "Btn": {
                "OpenScripts": "Open Scripts Folder",
                "DiscoverLua": "Discover Luas",
                "OpenYimFolder": "Open YimMenu Folder",
                "OpenYmuFolder": "Open YMU Folder",
                "ReportBug": "Report a Bug",
                "RequestFeature": "Request a Feature",
                "CheckUpdates": "Check for YMU Updates",
                "UpToDate": "YMU is up-to-date",
            },
            "Tooltip": {
                "OpenScripts": "Open the folder where your Lua scripts are located",
                "DiscoverLua": "Open the official YimMenu-Lua GitHub organization to find new scripts",
                "OpenYimFolder": "Open YimMenu folder (%APPDATA%/YimMenu)",
                "OpenYmuFolder": "Open YMU folder (%APPDATA%/YMU)",
                "ReportBug": "Open the bug report page on GitHub in your browser",
                "RequestFeature": "Open the feature request page on GitHub in your browser",
                "Language": "Select application language (requires restart)",
                "UpdateLang": "Check for translation updates",
            },
            "Update": {
                "Title": "YMU Updater",
                "UpToDate": "Your YMU is already up-to-date.",
                "AvailableTitle": "Update Available",
                "AvailableMsg": "Update {0} is available!",
                "Prompt": "Do you want to open the download page in your browser?",
                "CheckTitle": "YMU Update Check",
                "ErrorTitle": "Update Error",
                "Ahead": "You are running a newer version than the latest release.",
            },
            "Notify": {
                "RestartRequired": "Please restart YMU to apply the new language.",
                "LangUpdated": "Translations were successfully downloaded.\nRestart YMU to see the updated Language List in Settings.",
                "LangTitle": "Language Changed",
                "LangUpToDate": "Translations are already up-to-date.",
                "V2FileMissing": "YimMenuV2 has no settings.json yet.\nInject and run it once, then try again.",
                "FolderMissing": "Folder does not exist yet:\n{0}",
            },
        },
    }
}


class LocalizationManager(QObject):
    update_finished = Signal(bool, str, bool)

    def __init__(self):
        super().__init__()
        self.config = get_config()
        self.active_locale = self.config.get("locale", "en_US")
        self._lock = threading.Lock()
        self._is_updating = False

        self.data: dict = copy.deepcopy(FALLBACK_DATA)
        self.load_local_file()

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

    def set_locale(self, locale: str):
        """Saves the language in YMU's config."""
        with self._lock:
            has_locale = locale in self.data
        if has_locale:
            self.active_locale = locale
            if self.config.set("locale", locale):
                logger.info(f"Locale switched and saved to YMU config: {locale}")

    def fetch_updates(self):
        """Start the update check manually (by clicking the button)."""
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
            return self.data.get(locale_code, {}).get("meta", {}).get("name", locale_code)

    def load_local_file(self):
        if not os.path.exists(LOCAL_FILE_PATH):
            return
        try:
            with open(LOCAL_FILE_PATH, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
                if isinstance(loaded_data, dict):
                    self.data = self._deep_merge(FALLBACK_DATA, loaded_data)
                    logger.info("Local translations.json loaded.")
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load translations.json: {e}")

    def _read_local_raw_data(self) -> dict | None:
        if not os.path.exists(LOCAL_FILE_PATH):
            return None
        try:
            with open(LOCAL_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _update_from_remote_thread(self):
        """Internal method, runs in thread."""
        logger.info(f"Checking for translation updates from: {REMOTE_LANG_URL}")
        tmp_path = LOCAL_FILE_PATH + ".tmp"
        try:
            headers = {"User-Agent": USER_AGENT}
            response = requests.get(REMOTE_LANG_URL, headers=headers, timeout=10)
            if response.status_code == 200:
                remote_data = response.json()
                if isinstance(remote_data, dict):
                    local_raw = self._read_local_raw_data()
                    if local_raw is not None and local_raw == remote_data:
                        logger.info("Local translations are already up-to-date.")
                        msg = self.tr(
                            "Settings.Notify.LangUpToDate",
                            "Translations are already up-to-date.",
                        )
                        self.update_finished.emit(True, msg, False)
                    else:
                        logger.info("New translations detected. Updating local file...")
                        os.makedirs(os.path.dirname(LOCAL_FILE_PATH), exist_ok=True)
                        with open(tmp_path, "w", encoding="utf-8") as f:
                            json.dump(remote_data, f, indent=4, ensure_ascii=False)
                        os.replace(tmp_path, LOCAL_FILE_PATH)
                        with self._lock:
                            self.data = self._deep_merge(FALLBACK_DATA, remote_data)
                        msg = self.tr(
                            "Settings.Notify.LangUpdated",
                            "Translations updated successfully!",
                        )
                        self.update_finished.emit(True, msg, True)
                else:
                    logger.warning("Remote JSON is valid but not a dictionary.")
                    self.update_finished.emit(
                        False, "Invalid data format received.", False
                    )
            else:
                logger.warning(
                    f"Remote translations not found. Status Code: {response.status_code}"
                )
                self.update_finished.emit(
                    False, f"HTTP Error: {response.status_code}", False
                )

        except (requests.RequestException, OSError, ValueError) as e:
            logger.warning(f"Could not check for translation updates: {e}")
            self.update_finished.emit(False, str(e), False)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            with self._lock:
                self._is_updating = False

    def tr(self, key_path: str, default: str | None = None, *args, **kwargs) -> str:
        # This intentionally shadows QObject.tr with a dictionary-based lookup.
        # *args/**kwargs keep the override signature-compatible with the base
        # method so static type checkers don't flag an LSP violation.
        keys = key_path.split(".")
        with self._lock:
            value = self.data.get(self.active_locale, {})
        try:
            for k in keys:
                value = value[k]
            if isinstance(value, str):
                return value
        except (KeyError, TypeError):
            pass

        if self.active_locale != "en_US":
            with self._lock:
                fallback = self.data.get("en_US", {})
            try:
                for k in keys:
                    fallback = fallback[k]
                if isinstance(fallback, str):
                    return fallback
            except (KeyError, TypeError):
                pass

        return default if default else f"[{key_path}]"
