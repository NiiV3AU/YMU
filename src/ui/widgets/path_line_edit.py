# path_line_edit.py - Specialized path line edit with single-click focus and streamlined context menu.
import logging
import os
import subprocess

from PySide6.QtCore import QSize, Qt, Slot
from PySide6.QtGui import (
    QColor,
    QFocusEvent,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QMouseEvent,
)
from PySide6.QtWidgets import QLineEdit, QMenu, QWidget

from core.paths import resource_path
from ui.utils import create_colored_pixmap

logger = logging.getLogger(__name__)


class PathLineEdit(QLineEdit):
    """Specialized QLineEdit for path inputs.

    - Single click on unfocused field immediately selects all text (matching Tab focus behavior).
    - Right-click displays a modern themed context menu populated with Lucide icons (Cut, Copy, Paste, Show in Explorer).
    """

    def __init__(
        self,
        theme_manager=None,
        loc_manager=None,
        browse_icon: str = "folder-search.svg",
        parent: QWidget | None = None,
        **_kwargs,
    ):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.loc_manager = loc_manager
        self.browse_icon = browse_icon
        self._focus_by_mouse = False

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and not self.hasFocus():
            self._focus_by_mouse = True
            self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        super().mouseReleaseEvent(event)
        if self._focus_by_mouse:
            self._focus_by_mouse = False
            if not self.hasSelectedText():
                self.selectAll()

    def focusInEvent(self, event: QFocusEvent):
        super().focusInEvent(event)
        if event.reason() in (
            Qt.FocusReason.TabFocusReason,
            Qt.FocusReason.BacktabFocusReason,
        ):
            self.selectAll()

    def contextMenuEvent(self, event):
        if not self.hasFocus():
            self.setFocus(Qt.FocusReason.MouseFocusReason)

        menu = self._create_context_menu()
        menu.exec(event.globalPos())
        menu.deleteLater()

    def _menu_icon(self, name: str, icon_color: QColor) -> QIcon:
        icon_path = resource_path(os.path.join("assets", "icons", name))
        if os.path.exists(icon_path):
            pm = create_colored_pixmap(icon_path, icon_color, QSize(16, 16))
            return QIcon(pm)
        return QIcon()

    def _tr(self, key: str, default: str) -> str:
        if self.loc_manager and hasattr(self.loc_manager, "tr"):
            return self.loc_manager.tr(key, default)
        return default

    def _create_context_menu(self) -> QMenu:
        menu = QMenu(self)
        if self.isRightToLeft():
            menu.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        else:
            menu.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        is_dark = (
            self.theme_manager.current_theme == "dark" if self.theme_manager else True
        )
        icon_color = QColor("#E0E0E0" if is_dark else "#1A1D21")

        has_selection = self.hasSelectedText()
        is_read_only = self.isReadOnly()
        clipboard = QGuiApplication.clipboard()
        has_clipboard = bool(clipboard.text()) if clipboard else False

        act_cut = menu.addAction(
            self._menu_icon("scissors.svg", icon_color),
            self._tr("Context.Cut", "Cut"),
        )
        act_cut.setShortcut(QKeySequence.StandardKey.Cut)
        act_cut.setEnabled(has_selection and not is_read_only)
        act_cut.triggered.connect(self.cut)

        act_copy = menu.addAction(
            self._menu_icon("copy.svg", icon_color),
            self._tr("Context.Copy", "Copy"),
        )
        act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        act_copy.setEnabled(has_selection)
        act_copy.triggered.connect(self.copy)

        act_paste = menu.addAction(
            self._menu_icon("clipboard-paste.svg", icon_color),
            self._tr("Context.Paste", "Paste"),
        )
        act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        act_paste.setEnabled(has_clipboard and not is_read_only)
        act_paste.triggered.connect(self.paste)

        menu.addSeparator()

        clean_path = self.text().strip().strip('"').strip("'")
        path_exists = bool(clean_path and os.path.exists(clean_path))
        act_explorer = menu.addAction(
            self._menu_icon("folder-open.svg", icon_color),
            self._tr("Context.OpenExplorer", "Show in Explorer"),
        )
        act_explorer.setEnabled(path_exists)
        act_explorer.triggered.connect(self._open_in_explorer)

        return menu

    @Slot()
    def _open_in_explorer(self):
        clean_path = self.text().strip().strip('"').strip("'")
        if not clean_path or not os.path.exists(clean_path):
            return

        if os.path.isfile(clean_path):
            try:
                subprocess.Popen(
                    ["explorer", f"/select,{os.path.normpath(clean_path)}"]
                )
                return
            except Exception as e:
                logger.warning(f"Could not select file in explorer: {e}")

        folder = (
            clean_path if os.path.isdir(clean_path) else os.path.dirname(clean_path)
        )
        if os.path.isdir(folder):
            try:
                os.startfile(folder)
            except Exception as e:
                logger.error(f"Could not open explorer at '{folder}': {e}")
