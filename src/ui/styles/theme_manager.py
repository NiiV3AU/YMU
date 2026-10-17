# theme_manager.py - Handles loading, applying, and saving UI themes.
import logging
import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from core.config import get_config
from core.paths import resource_path

logger = logging.getLogger(__name__)


def _load_qss(theme_name: str) -> str:
    """Finds and reads the QSS file for the specified theme."""
    candidates = [
        os.path.join(os.path.dirname(__file__), f"{theme_name}.qss"),
        resource_path(os.path.join("ui", "styles", f"{theme_name}.qss")),
        resource_path(os.path.join("src", "ui", "styles", f"{theme_name}.qss")),
        os.path.join(os.path.dirname(__file__), "ui", "styles", f"{theme_name}.qss"),
        os.path.join(os.path.dirname(__file__), "styles", f"{theme_name}.qss"),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
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
        rtl_stylesheet: str | None = None,
        is_rtl: bool = False,
    ):
        super().__init__()
        self.app = app
        self.asset_path = asset_path or resource_path(
            os.path.join("assets", "icons")
        ).replace("\\", "/")
        self.is_rtl = is_rtl

        dark_raw = dark_stylesheet if dark_stylesheet is not None else _load_qss("dark")
        light_raw = (
            light_stylesheet if light_stylesheet is not None else _load_qss("light")
        )
        self.rtl_raw = (
            rtl_stylesheet if rtl_stylesheet is not None else _load_qss("rtl")
        )

        # In-memory cached stylesheets with resolved asset paths
        self.themes: dict[str, str] = {
            "dark": dark_raw.replace("{ASSET_PATH}", self.asset_path),
            "light": light_raw.replace("{ASSET_PATH}", self.asset_path),
        }
        self.config = get_config()
        theme_val = str(self.config.get("theme", "dark")).lower()
        if theme_val not in self.themes:
            logger.warning(
                f"Unknown theme '{theme_val}' in config; falling back to 'dark'."
            )
            theme_val = "dark"
            self.config.set("theme", "dark")
        self.current_theme = theme_val

    def _get_border_color(self, theme: str) -> str:
        return "#333333" if theme == "dark" else "#E3E6EA"

    def get_stylesheet(self, theme: str) -> str:
        """Returns the full stylesheet for the given theme, appending RTL overrides if active."""
        base_style = self.themes.get(theme, "")
        if not self.is_rtl or not self.rtl_raw:
            return base_style

        border_color = self._get_border_color(theme)
        rtl_overrides = self.rtl_raw.replace("{ASSET_PATH}", self.asset_path).replace(
            "{BORDER_COLOR}", border_color
        )
        return f"{base_style}\n\n/* --- RTL Overrides --- */\n{rtl_overrides}"

    def set_rtl(self, is_rtl: bool):
        """Sets the RTL state and updates the active stylesheet if changed."""
        if self.is_rtl != is_rtl:
            self.is_rtl = is_rtl
            if self.current_theme in self.themes:
                self.app.setStyleSheet(self.get_stylesheet(self.current_theme))

    def apply_theme(self, theme: str):
        """Applies a theme and saves the selection."""
        normalized = theme.lower()
        if normalized not in self.themes:
            logger.warning(
                f"Attempted to apply unknown theme '{theme}'; falling back to 'dark'."
            )
            normalized = "dark"
        self.app.setStyleSheet(self.get_stylesheet(normalized))
        is_dark = normalized == "dark"
        link_qcolor = QColor("#28A745" if is_dark else "#1A7F37")
        app_pal = self.app.palette()
        app_pal.setColor(QPalette.ColorRole.Link, link_qcolor)
        app_pal.setColor(QPalette.ColorRole.LinkVisited, link_qcolor)
        self.app.setPalette(app_pal)
        self.current_theme = normalized
        self.config.set("theme", normalized)
        self.themeChanged.emit(normalized)

    def apply_current_theme(self):
        """Applies the currently loaded theme."""
        self.apply_theme(self.current_theme)
