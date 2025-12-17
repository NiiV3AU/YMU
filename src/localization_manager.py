# localization_manager.py - downloads and manages translations
import os
import json
import logging
import requests
import threading
from typing import Dict, Optional, List
from PySide6.QtCore import QObject, Signal
from paths import YMU_LANG_DIR, YMU_CONFIG_FILE_PATH, USER_AGENT

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
        },
        "Common": {
            "Error": "Error",
            "Info": "Information",
            "UnexpectedError": "An unexpected error occurred",
            "Restart": "Restart Now",
            "Yes": "Yes",
            "No": "No",
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
                "FailedTitle": "Download Failed",
                "FailedMsg": "Verification failed. Please check the logs.",
                "UpdateTitle": "{0} Update",
            },
            "Help": {
                "Title": "DLL & FSL Info",
                "DllSteps": "1. Click on (Download)\n2. Wait for the download to finish\n3. The file is in the 'YMU/dll' folder\n\nIf the file gets deleted, add an exception\nin your antivirus or disable it temporarily.",
                "FslSteps": "1. Download FSL (Link provided in the Risks Page)\n2. Open your GTAV Directory\n3. Drop the WINMM.dll in the folder\n   (filename MUST be exactly 'WINMM.dll')\n4. Disable BattlEye in Rockstar's Game Launcher\n5. Done! ✅",
            },
            "Tooltip": {
                "Help": "Show help for DLL and FSL installation",
                "Channel": "Select the YimMenu version to download",
            },
        },
        "Inject": {
            "Launcher": {"Select": "Select Launcher"},
            "Btn": {
                "StartGta": "Start GTA 5",
                "InjectBase": "Inject YimMenu",
                "NoDll": "No DLL found",
                "InjectFile": "Inject {0}",
            },
            "Notify": {
                "AlreadyRunning": "GTA 5 is already running!",
                "SelectLauncher": "Please select a launcher first.",
                "SuccessTitle": "Injection Successful",
                "SuccessMsg": "Successfully injected DLL!",
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
            },
            "Error": {
                "NoDllSelected": "Error: No DLL selected or found for injection.",
                "ProcessLost": "GTA 5 process disappeared before injection.",
                "InjectionFailed": "Injection failed. See logs for details.",
                "NoRockstarPath": "Could not find Rockstar Games installation path.",
                "NoExeFound": "Executable not found at '{0}'",
                "LaunchFailed": "Error launching game. See logs for details.",
                "AccessDenied": "Missing permissions to inject into GTA V.\nTry restarting YMU as Administrator.",
            },
        },
        "Settings": {
            "Header": {
                "Appearance": "Appearance",
                "Lua": "Lua Settings",
                "Other": "Other",
            },
            "Label": {"Language": "Language"},
            "Theme": {"Dark": "Dark", "Light": "Light"},
            "Lua": {
                "AutoReload": "Auto-reload changed scripts",
                "ListDisabled": "Disabled",
                "ListEnabled": "Enabled",
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
                "Downloading": "Downloading Updater...",
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
                "Prompt": "Do you want to download and install it now?",
                "CheckTitle": "YMU Update Check",
                "ErrorTitle": "Update Error",
                "Ahead": "You are running a newer version than the latest release.",
            },
            "Notify": {
                "RestartRequired": "Please restart YMU to apply the new language.",
                "LangUpdated": "Translations were successfully downloaded.\nRestart YMU to see the updated Language List in Settings.",
                "LangTitle": "Language Changed",
                "LangUpToDate": "Translations are already up-to-date.",
            },
        },
    }
}


class LocalizationManager(QObject):
    update_finished = Signal(bool, str, bool)

    def __init__(self):
        super().__init__()
        self.config_path = YMU_CONFIG_FILE_PATH
        saved_locale = self._load_locale_preference()
        self.active_locale = saved_locale

        self.data: Dict = FALLBACK_DATA.copy()
        self.load_local_file()

    def _get_current_config(self) -> dict:
        """Helper to read the config safely."""
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _load_locale_preference(self) -> str:
        """Reads the language from YMU/config.json."""
        config = self._get_current_config()
        return config.get("locale", "en_US")

    def set_locale(self, locale: str):
        """Saves the language in YMU/config.json."""
        if locale in self.data:
            self.active_locale = locale
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            config = self._get_current_config()
            config["locale"] = locale

            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4)
                logger.info(f"Locale switched and saved to YMU config: {locale}")
            except OSError as e:
                logger.error(f"Failed to save locale: {e}")

    def fetch_updates(self):
        """Start the update check manually (by clicking the button)."""
        update_thread = threading.Thread(
            target=self._update_from_remote_thread, daemon=True
        )
        update_thread.start()

    def get_available_locales(self) -> List[str]:
        return list(self.data.keys())

    def get_language_name(self, locale_code: str) -> str:
        return self.data.get(locale_code, {}).get("meta", {}).get("name", locale_code)

    def load_local_file(self):
        if not os.path.exists(LOCAL_FILE_PATH):
            return
        try:
            with open(LOCAL_FILE_PATH, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
                if isinstance(loaded_data, dict):
                    self.data = loaded_data
                    logger.info("Local translations.json loaded.")
        except Exception as e:
            logger.error(f"Failed to load translations.json: {e}")

    def _update_from_remote_thread(self):
        """Internal method, runs in thread."""
        logger.info(f"Checking for translation updates from: {REMOTE_LANG_URL}")
        try:
            headers = {"User-Agent": USER_AGENT}
            response = requests.get(REMOTE_LANG_URL, headers=headers, timeout=10)
            if response.status_code == 200:
                remote_data = response.json()
                if isinstance(remote_data, dict):
                    if remote_data != self.data:
                        logger.info("New translations detected. Updating local file...")
                        os.makedirs(os.path.dirname(LOCAL_FILE_PATH), exist_ok=True)
                        with open(LOCAL_FILE_PATH, "w", encoding="utf-8") as f:
                            json.dump(remote_data, f, indent=4, ensure_ascii=False)
                        self.data = remote_data
                        msg = self.tr(
                            "Settings.Notify.LangUpdated",
                            "Translations updated successfully!",
                        )
                        self.update_finished.emit(True, msg, True)
                    else:
                        logger.info("Local translations are already up-to-date.")
                        msg = self.tr(
                            "Settings.Notify.LangUpToDate",
                            "Translations are already up-to-date.",
                        )
                        self.update_finished.emit(True, msg, False)
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

        except Exception as e:
            logger.warning(f"Could not check for translation updates: {e}")
            self.update_finished.emit(False, str(e), False)

    def tr(self, key_path: str, default: Optional[str] = None) -> str:
        keys = key_path.split(".")
        value = self.data.get(self.active_locale, {})
        try:
            for k in keys:
                value = value[k]
            if isinstance(value, str):
                return value
        except (KeyError, TypeError):
            pass

        if self.active_locale != "en_US":
            fallback = self.data.get("en_US", {})
            try:
                for k in keys:
                    fallback = fallback[k]
                if isinstance(fallback, str):
                    return fallback
            except:
                pass

        return default if default else f"[{key_path}]"
