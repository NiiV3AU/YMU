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

    def load_theme_preference(self) -> str:
        """Loads the theme preference from the config file."""
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
                return config.get("theme", "dark")
        except (FileNotFoundError, json.JSONDecodeError):
            return "dark"  # Default theme

    def save_theme_preference(self, theme: str):
        """Saves the theme preference to the config file."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        config = {"theme": theme}
        with open(self.config_path, "w") as f:
            json.dump(config, f)

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
