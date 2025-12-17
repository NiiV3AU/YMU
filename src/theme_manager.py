# theme_manager.py - Handles loading, applying, and saving UI themes.
import json
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal
from paths import YMU_CONFIG_FILE_PATH


class ThemeManager(QObject):
    themeChanged = Signal(str)

    def __init__(
        self,
        app: QApplication,
        dark_stylesheet: str,
        light_stylesheet: str,
        asset_path: str,
    ):
        super().__init__()
        self.app = app
        self.themes = {
            "dark": dark_stylesheet.replace("{ASSET_PATH}", asset_path),
            "light": light_stylesheet.replace("{ASSET_PATH}", asset_path),
        }
        self.config_path = YMU_CONFIG_FILE_PATH
        self.current_theme = self.load_theme_preference()

    def _get_current_config(self) -> dict:
        """Helper to read the full config without losing data."""
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def load_theme_preference(self) -> str:
        """Loads the theme preference from the config file."""
        config = self._get_current_config()
        return config.get("theme", "dark")

    def save_theme_preference(self, theme: str):
        """Saves the theme preference to the config file safely."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        config = self._get_current_config()
        config["theme"] = theme
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except OSError as e:
            print(f"Error saving theme preference: {e}")

    def apply_theme(self, theme: str):
        """Applies a theme and saves the selection."""
        if theme in self.themes:
            self.app.setStyleSheet(self.themes[theme])
            self.current_theme = theme
            self.save_theme_preference(theme)
            self.themeChanged.emit(theme)

    def apply_current_theme(self):
        """Applies the currently loaded theme."""
        self.apply_theme(self.current_theme)
