# theme_manager.py - Handles loading, applying, and saving UI themes.
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from ymu_config import get_config


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
        self.config = get_config()
        self.current_theme = self.config.get("theme", "dark")

    def apply_theme(self, theme: str):
        """Applies a theme and saves the selection."""
        if theme in self.themes:
            self.app.setStyleSheet(self.themes[theme])
            self.current_theme = theme
            self.config.set("theme", theme)
            self.themeChanged.emit(theme)

    def apply_current_theme(self):
        """Applies the currently loaded theme."""
        self.apply_theme(self.current_theme)
