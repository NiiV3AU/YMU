# theme_manager.py - Handles loading, applying, and saving UI themes.
import logging
import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from paths import resource_path
from ymu_config import get_config

logger = logging.getLogger(__name__)


def _load_qss(theme_name: str) -> str:
    """Finds and reads the QSS file for the specified theme."""
    candidates = [
        resource_path(os.path.join("ui", "styles", f"{theme_name}.qss")),
        resource_path(os.path.join("src", "ui", "styles", f"{theme_name}.qss")),
        os.path.join(os.path.dirname(__file__), "ui", "styles", f"{theme_name}.qss"),
        os.path.join(os.path.dirname(__file__), "styles", f"{theme_name}.qss"),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except OSError as e:
                logger.error(f"Failed to read stylesheet at {path}: {e}")
    logger.error(f"Stylesheet for theme '{theme_name}' could not be found.")
    return ""


class ThemeManager(QObject):
    themeChanged = Signal(str)

    def __init__(
        self,
        app: QApplication,
        asset_path: str = "",
        dark_stylesheet: str | None = None,
        light_stylesheet: str | None = None,
    ):
        super().__init__()
        self.app = app
        self.asset_path = asset_path or resource_path(
            os.path.join("assets", "icons")
        ).replace("\\", "/")

        dark_raw = dark_stylesheet if dark_stylesheet is not None else _load_qss("dark")
        light_raw = (
            light_stylesheet if light_stylesheet is not None else _load_qss("light")
        )

        # In-memory cached stylesheets with resolved asset paths
        self.themes: dict[str, str] = {
            "dark": dark_raw.replace("{ASSET_PATH}", self.asset_path),
            "light": light_raw.replace("{ASSET_PATH}", self.asset_path),
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
