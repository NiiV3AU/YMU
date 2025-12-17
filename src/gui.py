# gui.py - Contains all the UI code for the application using PySide6.

import sys
import os
import logging
from logging.handlers import RotatingFileHandler

try:
    import winreg
    import win32gui

    IS_WINDOWS = True

except (ImportError, AttributeError):
    IS_WINDOWS = False


# check if an instance is already running -> yes? -> gets focused
if IS_WINDOWS:
    WINDOW_TITLE = "YimMenuUpdater | NV3"
    try:
        hwnd = win32gui.FindWindow(None, WINDOW_TITLE)
        if hwnd != 0:
            win32gui.SetForegroundWindow(hwnd)
            sys.exit(0)
    except Exception as e:
        logging.getLogger(__name__).error(f"Error during instance check: {e}")

import webbrowser
import time
import platform
from typing import Optional, cast

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QHBoxLayout,
    QStackedWidget,
    QDialog,
    QTabBar,
    QButtonGroup,
    QMessageBox,
    QFrame,
    QScrollArea,
    QListWidget,
    QAbstractItemView,
    QGridLayout,
    QComboBox,
    QLayout,
)
from PySide6.QtCore import (
    QSize,
    Qt,
    QObject,
    Signal,
    QThread,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    QRectF,
    Property,
    QParallelAnimationGroup,
    QEvent,
    QPoint,
)
from PySide6.QtGui import (
    QFontDatabase,
    QIcon,
    QColor,
    QPainter,
    QPainterPath,
    QPixmap,
    QLinearGradient,
    QEnterEvent,
)
from PySide6.QtSvg import QSvgRenderer


# import modules
from paths import (
    YMU_LOG_FILE_PATH,
    resource_path,
    YMU_DLL_DIR,
    YIMMENU_APPDATA_DIR,
    YMU_APPDATA_DIR,
    YIMMENU_SCRIPTS_DIR,
    LOCAL_VERSION,
)
from worker_manager import WorkerManager
from theme_manager import ThemeManager
from localization_manager import LocalizationManager
import release_service
import process_manager
import settings_manager
import lua_manager
import update_checker


log_formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)-8s] [%(name)-18s] %(message)s", datefmt="%H:%M:%S"
)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)

file_handler = RotatingFileHandler(
    filename=YMU_LOG_FILE_PATH, maxBytes=1024 * 1024, backupCount=5, encoding="utf-8"
)
file_handler.setFormatter(log_formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(stream_handler)
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)

try:
    ymu_version = LOCAL_VERSION
except Exception:
    ymu_version = "unknown"  # Fallback

system_info = {
    "YMU Version": ymu_version,
    "Operating System": f"{platform.system()} {platform.release()}",
    "Architecture": platform.architecture()[0],
    "Working Directory": os.getcwd(),
}

logger.info("--- Initializing YMU ---")
for key, value in system_info.items():
    logger.info(f"{key}: {value}")
logger.info("--------------------------")

ICON_LIGHT_PATH = resource_path(os.path.join("assets", "icons", "logo_light.ico"))
ICON_DARK_PATH = resource_path(os.path.join("assets", "icons", "logo_dark.ico"))


def update_app_icon(app, window):
    """Checks the system theme and sets the appropriate application icon."""
    color_scheme = app.styleHints().colorScheme()

    if color_scheme == Qt.ColorScheme.Dark:
        logger.info("Dark Mode detected. Applying dark theme icon.")
        if os.path.exists(ICON_DARK_PATH):
            window.setWindowIcon(QIcon(ICON_DARK_PATH))
    else:
        logger.info("Light Mode detected. Applying light theme icon.")
        if os.path.exists(ICON_LIGHT_PATH):
            window.setWindowIcon(QIcon(ICON_LIGHT_PATH))


def create_colored_icon(icon_path: str, color: QColor) -> QIcon:
    """Loads an SVG file, recolors it, and returns it as a QIcon."""
    renderer = QSvgRenderer(icon_path)
    if not renderer.isValid():
        return QIcon()

    size = renderer.defaultSize()
    pixmap = QPixmap(size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)

    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()

    return QIcon(pixmap)


def restart_application():
    """
    Restarts the application.
    FIXED for Nuitka Onefile: Uses sys.argv[0] to find the real EXE,
    not the temporary python interpreter in sys.executable.
    """
    import subprocess

    logger.info("Restart requested via UI. Relaunching...")

    QApplication.quit()

    if "__compiled__" in globals():
        executable = sys.argv[0]
    elif getattr(sys, "frozen", False):
        executable = sys.executable
    else:
        subprocess.Popen([sys.executable] + sys.argv)
        sys.exit(0)
    if IS_WINDOWS:
        try:
            logger.info(f"Restarting executable at: {executable}")
            os.startfile(executable)
        except Exception as e:
            logger.error(f"Failed to restart via os.startfile: {e}")
            subprocess.Popen([executable])
    else:
        subprocess.Popen([executable])
    sys.exit(0)


class FocusStealingFilter(QObject):
    """
    An event filter that clears focus on mouse clicks, but ignores clicks
    on an AnimatedButton that is currently animating to prevent race conditions.
    """

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            if isinstance(watched, AnimatedButton) and watched._is_animating:
                pass
            else:
                focused_widget = QApplication.focusWidget()
                if focused_widget:
                    focused_widget.clearFocus()

        return super().eventFilter(watched, event)


STYLESHEET = """
    /***************************************************************************
     * *
     * YMU DESIGN SYSTEM                                                       *
     * *
     ***************************************************************************/

    /* --- BASE COLORS ---
     * @background:  The darkest color, for the window itself.
     * @surface:     A layer above, for container backgrounds like the sidebar.
     * @panel:       The lightest background color, for interactive panels.
     *
     * --- ACCENT COLOR ---
     * @primary:     The main accent color (a calmer green).
     * @primary-text: Text color for elements with a @primary background.
     *
     * --- TEXT COLORS ---
     * @text-primary:   Default text color.
     * @text-secondary: For less important text.
     * @text-disabled:  Text on disabled elements.
     * --- OTHER ---
     * @border-color: Color for subtle borders.
     * @radius:       Universal corner radius.
     */

    /* --- GLOBAL STYLES --- */
    QWidget {
        color: #E0E0E0; /* @text-primary */
        font-family: "Manrope", "Segoe UI", "Meiryo", "Microsoft YaHei", sans-serif;
        font-size: 14px;
    }

    QMainWindow {
        background-color: #121212; /* @background */
    }

    /* --- SIDEBAR --- */
    QWidget#Sidebar {
        background-color: #1E1E1E; /* @surface */
        border-right: 1px solid #333333; /* @border-color */
    }

    QPushButton#SidebarButton {
        background-color: transparent;
        color: #8B8B8B; /* @text-secondary */
        border: none;
        padding: 12px;
        font-size: 15px;
        text-align: left;
        border-radius: 10px; /* @radius */
        margin: 4px 8px;
        spacing: 10px;
    }

    QPushButton#SidebarButton:hover {
        background-color: #2C2C2C; /* @panel */
        color: #E0E0E0; /* @text-primary */
    }

    QPushButton#SidebarButton:checked {
    background-color: #333333;
    color: #E0E0E0;
    font-weight: bold;
    }

    /* --- PRIMARY BUTTONS --- */
    QPushButton {
        background-color: #28A745; /* @primary */
        color: #FFFFFF; /* @primary-text */
        border: none;
        padding: 10px 18px;
        font-weight: bold;
        font-size: 14px;
        border-radius: 10px; /* @radius */
    }

    QPushButton:hover {
        background-color: #2ebf4f;
    }

    QPushButton:disabled {
        background-color: #333333; /* @border-color */
        color: #8B8B8B; /* @text-disabled */
    }
    
    /* --- OTHER WIDGETS --- */
    QLabel {
        background-color: transparent;
    }
    /* --- Info Dialog Styling --- */
    QDialog#InfoDialog {
        background-color: #1E1E1E; /* @surface */
    }

    /* Style for the '?' button */
    QPushButton#InfoButton {
        background-color: transparent;
        color: #8B8B8B;
        border: 1px solid #333333;
        border-radius: 6px;
        padding: 0px;
        min-width: 30px;
        max-width: 30px;
        min-height: 30px;
        max-height: 30px;
    }

    QPushButton#InfoButton:hover {
        background-color: #333333;
        border-color: #555555;
        color: #E0E0E0;
    }

    /* Styling for the tabs inside the dialog */
    QDialog#InfoDialog QTabBar::tab {
        qproperty-alignment: 'AlignCenter';
        background-color: transparent;
        color: #8B8B8B;
        padding: 8px 15px;
        border: none;
        border-bottom: 2px solid transparent; 
    }

    QDialog#InfoDialog QTabBar::tab:hover {
        qproperty-alignment: 'AlignCenter';
        color: #E0E0E0;
    }

    QDialog#InfoDialog QTabBar::tab:selected {
        qproperty-alignment: 'AlignCenter';
        color: #FFFFFF;
        font-weight: bold;
        border-bottom: 2px solid #28A745; /* @primary */
    }
    
    QDialog#InfoDialog QStackedWidget {
        background-color: #2C2C2C; /* @panel */
        border: 1px solid #333333;   /* @border-color */
        border-radius: 5px;         /* @radius */
    }
    
    /* --- Styled Frame (Card) --- */
    QFrame#CardFrame {
        background-color: #1E1E1E; /* @surface */
        border: 1px solid #333333; /* @border-color */
        border-radius: 10px; /* @radius */
        padding: 15px;
    }

    /* --- ComboBox Styling --- */
    QComboBox {
        background-color: #2C2C2C; /* @panel */
        border: 1px solid #333333;
        border-radius: 8px;
        padding: 8px 12px;
    }

    QComboBox:hover {
        border-color: #555555;
    }

    QComboBox::drop-down {
        border: none;
        width: 20px;
    }

    QComboBox::down-arrow {
        image: url({ASSET_PATH}/chevron-down.svg);
        width: 20px;
        height: 20px;
        padding-right: 10px;
    }

    /* Das Popup-Panel */
    QComboBox QAbstractItemView {
        background-color: #1E1E1E; /* Etwas dunkler als der Trigger für Kontrast */
        border: 1px solid #333333;
        border-radius: 6px; 
        padding: 2px; /* Minimaler Abstand zum Rand */
        outline: 0px;
    }

    /* Die Items: Schlank und Dezent */
    QComboBox QAbstractItemView::item {
        padding: 2px 8px;   /* HIER: Das macht es dünn! */
        border-radius: 4px;
        min-height: 18px;   /* Kompakte Höhe */
        margin: 0px;
    }

    /* Hover: Grau statt Grün! */
    QComboBox QAbstractItemView::item:selected, 
    QComboBox QAbstractItemView::item:hover {
        background-color: #333333; /* Dezent, nicht aggressiv */
        color: #FFFFFF;
    }
    
    QLabel#SettingsTitle {
        font-size: 16px;
        font-weight: bold;
        margin-bottom: 10px;
    }
    /* --- Theme-Buttons --- */
    QPushButton#ThemeButton {
        background-color: #333333;
        color: #8B8B8B;
        border: 1px solid #555555;
        padding: 8px 16px;
    }

    QPushButton#ThemeButton:hover {
        background-color: #444444;
        color:#CCCCCC;
    }

    QPushButton#ThemeButton:checked {
        background-color: #E0E0E0;
        color: #121212;
        border-color: #E0E0E0;
    }

    /* --- Link-Buttons --- */
    QPushButton#LinkButton {
        background-color: transparent;
        color: #8B8B8B; /* @text-secondary */
        border: 1px solid #333333; /* @border-color */
        border-radius: 6px;
        text-align: left;
        padding: 8px 12px;
        spacing: 8px;
    }

    QPushButton#LinkButton:hover {
        background-color: #333333;
        color: #E0E0E0; /* @text-primary */
        text-decoration: none;
    }

    /* --- ScrollBar Styling --- */
    QScrollArea {
        border: none;
        background: transparent;
    }

    QScrollBar:vertical {
        border: none;
        background: #2C2C2C;
        width: 10px;
        margin: 0;
    }

    /* The handle that you drag */
    QScrollBar::handle:vertical {
        background: #555555;
        min-height: 30px;
        border-radius: 5px;
    }

    QScrollBar::handle:vertical:hover {
        background: #6E6E6E;
    }

    /* The track above and below the handle */
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }

    /* The top and bottom arrow buttons (hidden) */
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        background: none;
        border: none;
        height: 0px;
    }
    
    QWidget#ScrollContainer {
        background-color: #121212; /* @background */
    }
    
    QLabel#ListHeaderLabel {
        font-size: 11px;
        font-weight: bold;
        color: #8B8B8B; /* @text-secondary */
        margin-left: 5px;
        margin-bottom: 5px;
    }
    QLabel#DisabledListHeader {
    color: #e84555;
    }

    QLabel#EnabledListHeader {
        color: #28A745;
    }

    /* --- Lua Manager Control Buttons --- */
    QPushButton#EnableButton,
    QPushButton#RefreshButton,
    QPushButton#DisableButton {
        padding: 0px;
        border: 1px solid #333333;
        background-color: #333333;
        border-radius: 8px;
    }

    QPushButton#EnableButton:hover {
        background-color: #28A745;
        border-color: #28A745;
    }

    QPushButton#RefreshButton:hover {
        background-color: #444444;
        border-color: #555555;
    }

    QPushButton#DisableButton:hover {
        background-color: #e84555;
        border-color: #e84555;
    }
    QFrame#CardFrame QListWidget {
        font-family: "JetBrains Mono";
        font-size: 10px;
        background-color: #2C2C2C;
        border-radius: 5px;
        border: 1px solid #333333;
    }
    
    /* --- Sidebar Footer --- */
    QPushButton#SidebarFooter {
        background-color: transparent;
        border: none;
        color: #666666;
        font-size: 11px;
        text-align: center;
        padding: 10px;
    }

    QPushButton#SidebarFooter:hover {
        color: #8B8B8B; /* @text-secondary */
    }
    /* --- Risk Page Styles --- */
    QLabel#RiskTitleLabel {
        color: #e84555;
        font-size: 16px;
        font-weight: bold;
        qproperty-alignment: 'AlignCenter';
    }

    QLabel#RiskInfoLabel {
        qproperty-alignment: 'AlignCenter';
        font-size: 12px;
    }
    
    /* --- KEYBOARD FOCUS STYLES --- */
    *:focus {
        outline: 0;
    }

    QPushButton#SidebarButton:focus {
        background-color: #2C2C2C; /* @panel */
        color: #E0E0E0; /* @text-primary */
    }

    QPushButton:focus {
        background-color: #2ebf4f;
    }

    QPushButton#InfoButton:focus {
        background-color: #333333;
        border-color: #555555;
        color: #E0E0E0;
    }

    QPushButton#ThemeButton:focus {
        background-color: #444444;
        color: #CCCCCC;
    }

    QPushButton#LinkButton:focus {
        background-color: #333333;
        color: #E0E0E0;
    }

    QComboBox:focus, QListWidget:focus {
        border: 1px solid #555555;
    }

    /* Lua Manager Buttons */
    QPushButton#EnableButton:focus {
        background-color: #28A745;
        border-color: #28A745;
    }

    QPushButton#RefreshButton:focus {
        background-color: #444444;
        border-color: #555555;
    }

    QPushButton#DisableButton:focus {
        background-color: #e84555;
        border-color: #e84555;
    }
    /* --- Notification System --- */
    QFrame#NotificationCard {
        background-color: #1E1E1E; /* @surface */
        border: 1px solid #333333; /* @border-color */
        border-radius: 10px; /* @radius */
    }
    #NotificationCard QLabel#NotificationTitle {
        font-size: 14px;
        font-weight: bold;
        color: #E0E0E0; /* @text-primary */
    }
    #NotificationCard QLabel#NotificationMessage {
        font-size: 13px;
        color: #8B8B8B; /* @text-secondary */
    }
    #NotificationCard QPushButton#NotificationCloseButton {
    background-color: transparent;
    border: none;
    border-radius: 12px;
    }
    #NotificationCard QPushButton#NotificationCloseButton:hover {
        background-color: #333333;
    }
"""

STYLESHEET_LIGHT = """
    /***************************************************************************
     * YMU DESIGN SYSTEM (Light Theme)                                         *
     ***************************************************************************/

    /* --- GLOBAL STYLES --- */
    QWidget { color: #121212; font-family: "Manrope", "Segoe UI", "Meiryo", "Microsoft YaHei", sans-serif; font-size: 14px;}
    QMainWindow { background-color: #F5F5F5; }
    QWidget#MainContentWidget { background-color: rgba(245, 245, 245, 0.85); }

    /* --- SIDEBAR --- */
    QWidget#Sidebar { background-color: #EEEEEE; border-right: 1px solid #DCDCDC; }
    QPushButton#SidebarButton { background-color: transparent; color: #555555; border: none; padding: 12px; font-size: 15px; text-align: left; border-radius: 10px; margin: 4px 8px; spacing: 10px; }
    QPushButton#SidebarButton:hover { background-color: #E0E0E0; color: #121212; }
    QPushButton#SidebarButton:checked { background-color: #DCDCDC; color: #121212; font-weight: bold; }

    /* --- PRIMARY BUTTONS --- */
    QPushButton { background-color: #28A745; color: #FFFFFF; border: none; padding: 10px 18px; font-weight: bold; font-size: 14px; border-radius: 10px; }
    QPushButton:hover { background-color: #2ebf4f; }
    QPushButton:disabled { background-color: #E0E0E0; color: #AAAAAA; }
    
    /* --- DIALOGS (InfoDialog & QMessageBox) --- */
    QDialog#InfoDialog, QMessageBox { background-color: #FFFFFF; }
    QMessageBox QLabel { color: #121212; }
    
    QPushButton#InfoButton { background-color: transparent; color: #777777; border: 1px solid #DCDCDC; border-radius: 6px; padding: 0px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; }
    QPushButton#InfoButton:hover { background-color: #E0E0E0; border-color: #CCCCCC; color: #121212; }
    
    QDialog#InfoDialog QTabBar::tab { color: #555555; background-color: transparent; padding: 8px 15px; border: none; border-bottom: 2px solid transparent; }
    QDialog#InfoDialog QTabBar::tab:hover { color: #121212; }
    QDialog#InfoDialog QTabBar::tab:selected { property-alignment: 'AlignCenter'; color: #121212; font-weight: bold; border-bottom: 2px solid #28A745; }
    QDialog#InfoDialog QStackedWidget { background-color: #F5F5F5; border: 1px solid #E0E0E0; border-radius: 5px; }

    /* --- CONTAINERS & CARDS --- */
    QFrame#CardFrame { background-color: #FFFFFF; border: 1px solid #E0E0E0; border-radius: 10px; padding: 15px; }
    QWidget#ScrollContainer { background-color: #F5F5F5; }

    /* --- ComboBox Styling --- */
    QComboBox {
        background-color: #E0E0E0;
        border: 1px solid #DCDCDC;
        border-radius: 8px;
        padding: 8px 12px;
        color: #121212;
    }


    QComboBox:hover {
        border-color: #BDBDBD;
    }

    QComboBox::drop-down {
        border: none;
        width: 20px;
    }

    QComboBox::down-arrow {
        image: url({ASSET_PATH}/chevron-down.svg);
        width: 20px;
        height: 20px;
        padding-right: 10px;
    }

    QComboBox QAbstractItemView {
        background-color: #FFFFFF;
        border: 1px solid #CCCCCC;
        border-radius: 6px;
        padding: 2px;
        outline: 0px;
        color: #121212;
    }

    QComboBox QAbstractItemView::item {
        padding: 2px 8px;
        border-radius: 4px;
        min-height: 18px;
    }

    /* Hover: Hellgrau statt Grün */
    QComboBox QAbstractItemView::item:selected,
    QComboBox QAbstractItemView::item:hover {
        background-color: #E0E0E0; 
        color: #121212;
    }
    
    /* --- TEXT & TITLES --- */
    QLabel#SettingsTitle { font-size: 16px; font-weight: bold; margin-bottom: 10px; }
    QLabel#ListHeaderLabel { font-size: 11px; font-weight: bold; color: #555555; margin-left: 5px; margin-bottom: 5px; }
    QLabel#DisabledListHeader { color: #e84555; }
    QLabel#EnabledListHeader { color: #28A745; }

    /* --- THEME & LINK BUTTONS --- */
    QPushButton#ThemeButton { background-color: #E0E0E0; color: #555555; border: 1px solid #DCDCDC; padding: 8px 16px; }
    QPushButton#ThemeButton:hover { background-color: #DCDCDC; color: #121212; }
    QPushButton#ThemeButton:checked { background-color: #121212; color: #FFFFFF; border-color: #121212; }

    QPushButton#LinkButton { background-color: transparent; color: #555555; border: 1px solid #DCDCDC; border-radius: 6px; text-align: left; padding: 8px 12px; spacing: 8px; }
    QPushButton#LinkButton:hover { background-color: #E0E0E0; color: #121212; }

    /* --- SCROLLBAR --- */
    QScrollBar:vertical { border: none; background: #F5F5F5; width: 10px; margin: 0; }
    QScrollBar::handle:vertical { background: #CCCCCC; min-height: 30px; border-radius: 5px; }
    QScrollBar::handle:vertical:hover { background: #BDBDBD; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: none; border: none; height: 0px; }

    /* --- LUA MANAGER --- */
    QPushButton#EnableButton, QPushButton#RefreshButton, QPushButton#DisableButton { padding: 0px; border: 1px solid #DCDCDC; background-color: #E0E0E0; border-radius: 8px; }
    QPushButton#EnableButton:hover { background-color: #28A745; border-color: #28A745; }
    QPushButton#RefreshButton:hover { background-color: #DCDCDC; border-color: #BDBDBD; }
    QPushButton#DisableButton:hover { background-color: #e84555; border-color: #e84555; }
    QFrame#CardFrame QListWidget { font-family: "JetBrains Mono"; font-size: 10px; background-color: #F5F5F5; border-radius: 5px; border: 1px solid #E0E0E0; }

    /* --- FOOTER --- */
    QPushButton#SidebarFooter { background-color: transparent; border: none; color: #AAAAAA; font-size: 11px; text-align: center; padding: 10px; }
    QPushButton#SidebarFooter:hover { color: #777777; }
    /* --- Risk Page Styles --- */
    QLabel#RiskTitleLabel {
        color: #d32f2f;
        font-size: 16px;
        font-weight: bold;
        qproperty-alignment: 'AlignCenter';
    }

    QLabel#RiskInfoLabel {
        qproperty-alignment: 'AlignCenter';
        font-size: 12px;
    }
    /* --- KEYBOARD FOCUS STYLES --- */

    *:focus {
        outline: 0;
    }

    QPushButton#SidebarButton:focus {
        background-color: #E0E0E0;
        color: #121212;
    }

    QPushButton:focus {
        background-color: #2ebf4f;
    }

    QPushButton#InfoButton:focus {
        background-color: #E0E0E0;
        border-color: #CCCCCC;
        color: #121212;
    }

    QPushButton#ThemeButton:focus {
        background-color: #DCDCDC;
        color: #121212;
    }

    QPushButton#LinkButton:focus {
        background-color: #E0E0E0;
        color: #121212;
    }

    QComboBox:focus, QListWidget:focus {
        border: 1px solid #BDBDBD;
    }

    /* Lua Manager Buttons */
    QPushButton#EnableButton:focus {
        background-color: #28A745;
        border-color: #28A745;
    }

    QPushButton#RefreshButton:focus {
        background-color: #DCDCDC;
        border-color: #BDBDBD;
    }

    QPushButton#DisableButton:focus {
        background-color: #e84555;
        border-color: #e84555;
    }
    /* --- Notification System --- */
    QFrame#NotificationCard {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 10px;
    }
    #NotificationCard QLabel#NotificationTitle {
        font-size: 14px;
        font-weight: bold;
        color: #121212;
    }
    #NotificationCard QLabel#NotificationMessage {
        font-size: 13px;
        color: #555555;
    }
    #NotificationCard QPushButton#NotificationCloseButton {
    background-color: transparent;
    border: none;
    border-radius: 12px;
    }
    #NotificationCard QPushButton#NotificationCloseButton:hover {
        background-color: #E0E0E0;
    }
"""


class NotificationWidget(QFrame):
    """A single, animated notification widget in the style of a 'card'."""

    closed = Signal()

    def __init__(
        self,
        title,
        message,
        icon_type="info",
        theme_manager=None,
        parent=None,
        action_text=None,
        action_callback=None,
    ):
        super().__init__(parent)
        self.setObjectName("NotificationCard")
        self.theme_manager = theme_manager

        self.title = title
        self.message = message

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 12, 15, 12)
        main_layout.setSpacing(15)
        main_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32, 32)
        main_layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        self._set_icon(icon_type)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("NotificationTitle")

        message_label = QLabel(message)
        message_label.setObjectName("NotificationMessage")
        message_label.setWordWrap(True)

        text_layout.addWidget(title_label)
        text_layout.addWidget(message_label)

        if action_text and action_callback:
            self.action_btn = QPushButton(action_text)
            self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.action_btn.setMinimumWidth(100)
            self.action_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #333333;
                    color: #FFFFFF;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 4px 12px; 
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #28A745;
                    border-color: #28A745;
                }
            """
            )
            self.action_btn.clicked.connect(action_callback)
            self.action_btn.clicked.connect(self.close_animation)
            text_layout.addSpacing(5)
            text_layout.addWidget(self.action_btn, 0, Qt.AlignmentFlag.AlignLeft)

        main_layout.addLayout(text_layout)

        top_right_layout = QVBoxLayout()
        self.close_button = StatefulButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "x.svg")),
            color_normal=("#8B8B8B", "#AAAAAA"),
            color_hover=("#E0E0E0", "#121212"),
        )
        self.close_button.setObjectName("NotificationCloseButton")
        self.close_button.setFixedSize(24, 24)
        self.close_button.setIconSize(QSize(20, 20))
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self.close_animation)

        top_right_layout.addWidget(
            self.close_button,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )
        top_right_layout.addStretch()
        main_layout.addLayout(top_right_layout)

        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self.current_animation = None

    def _set_icon(self, icon_type: str):
        icons = {
            "success": os.path.join("assets", "icons", "check-circle.svg"),
            "error": os.path.join("assets", "icons", "alert-triangle.svg"),
            "info": os.path.join("assets", "icons", "info.svg"),
        }
        icon_path = resource_path(icons.get(icon_type, icons["info"]))
        is_light = self.theme_manager and self.theme_manager.current_theme == "light"
        color_map = {
            "success": QColor("#28A745"),
            "error": QColor("#e84555"),
            "info": QColor("#555555") if is_light else QColor("#8B8B8B"),
        }
        icon = create_colored_icon(
            icon_path, color_map.get(icon_type, color_map["info"])
        )
        self.icon_label.setPixmap(icon.pixmap(32, 32))

    def enterEvent(self, event):
        self._close_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._close_timer.interval() > 0:
            self._close_timer.start()
        super().leaveEvent(event)

    def start_fly_in(self, target_pos: QPoint, duration: int):
        parent = self.parentWidget()
        if not parent:
            return

        start_pos = QPoint(parent.width(), target_pos.y())
        self.move(start_pos)
        self.animate_to(target_pos)

        if duration > 0:
            self._close_timer.setInterval(duration)
            self._close_timer.timeout.connect(self.close_animation)
            self._close_timer.start()

    def close_animation(self):
        self._close_timer.stop()
        parent = self.parentWidget()
        if not parent:
            self._on_animation_finished()
            return

        end_pos = QPoint(self.pos().x(), parent.height())
        self.animate_to(end_pos, finished_slot=self._on_animation_finished)

    def animate_to(self, target_pos: QPoint, finished_slot=None):
        """A generic animation method to move the widget."""
        self.current_animation = QPropertyAnimation(self, b"pos")
        self.current_animation.setDuration(350)
        self.current_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.current_animation.setEndValue(target_pos)
        if finished_slot:
            self.current_animation.finished.connect(finished_slot)
        self.current_animation.start()

    def _on_animation_finished(self):
        self.closed.emit()
        self.deleteLater()


class NotificationManager(QObject):
    """Manages the creation, positioning, and lifecycle of notifications."""

    def __init__(self, parent: QWidget, theme_manager: "ThemeManager"):
        super().__init__(parent)
        self.parent_widget = parent
        self.theme_manager = theme_manager
        self.notifications = []
        self.padding = 15

    def show(
        self,
        title,
        message,
        icon_type="info",
        duration=6000,
        action_text=None,
        action_callback=None,
    ):
        for n in self.notifications:
            if n.title == title and n.message == message:
                logger.info(f"Suppressed duplicate notification: '{title}'")
                return

        notification = NotificationWidget(
            title,
            message,
            icon_type,
            self.theme_manager,
            self.parent_widget,
            action_text=action_text,
            action_callback=action_callback,
        )
        notification.show()
        notification.closed.connect(lambda: self._remove_notification(notification))

        self.notifications.append(notification)
        self._reposition_notifications(is_new=True, new_duration=duration)

    def _reposition_notifications(self, is_new=False, new_duration=0):
        """Calculates positions for all notifications and triggers their animations."""
        parent_rect = self.parent_widget.rect()
        current_y = parent_rect.bottom() - self.padding

        for i, notification in enumerate(reversed(self.notifications)):
            notification.adjustSize()
            h = notification.height()
            current_y -= h + self.padding / 2
            pos_x = parent_rect.right() - notification.width() - self.padding
            target_pos = QPoint(pos_x, current_y)
            is_the_very_newest = is_new and notification is self.notifications[-1]
            if is_the_very_newest:
                notification.start_fly_in(target_pos, new_duration)
            elif notification.pos() != target_pos:
                notification.animate_to(target_pos)

    def _remove_notification(self, notification):
        if notification in self.notifications:
            self.notifications.remove(notification)
        self._reposition_notifications()


class InfoDialog(QDialog):
    """A reusable, modal dialog for showing information in tabs with dynamic resizing."""

    def __init__(self, title: str, content: dict, theme_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("InfoDialog")
        self.setModal(True)

        self.tab_bar = QTabBar()
        self.tab_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.content_stack = QStackedWidget()

        self.tab_bar.setExpanding(False)
        self.tab_bar.setUsesScrollButtons(False)

        centering_layout = QHBoxLayout()
        centering_layout.addStretch()
        centering_layout.addWidget(self.tab_bar)
        centering_layout.addStretch()
        is_dark = theme_manager.current_theme == "dark"
        text_color = "#E0E0E0" if is_dark else "#121212"
        font_family = "Manrope, Segoe UI, Meiryo, Microsoft YaHei, sans-serif"

        for tab_title, tab_content in content.items():
            self.tab_bar.addTab(tab_title)
            formatted_content = tab_content.replace("\n", "<br>")
            html_text = (
                f"<html><body>"
                f"<div align='center' style='font-family:{font_family}; font-size:14px; color:{text_color};'>"
                f"{formatted_content}"
                f"</div></body></html>"
            )

            content_label = QLabel(html_text)
            content_label.setTextFormat(Qt.TextFormat.RichText)
            content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            content_label.setWordWrap(True)
            content_label.setOpenExternalLinks(True)
            content_label.setContentsMargins(10, 20, 10, 20)

            self.content_stack.addWidget(content_label)

        self.tab_bar.currentChanged.connect(self._on_tab_changed)

        main_layout = QVBoxLayout(self)
        main_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        main_layout.addLayout(centering_layout)
        main_layout.addWidget(self.content_stack)

        if self.tab_bar.count() > 0:
            self.content_stack.setCurrentIndex(0)

    def showEvent(self, event):
        super().showEvent(event)
        self.adjustSize()

    def _on_tab_changed(self, index):
        self.content_stack.setCurrentIndex(index)
        QApplication.processEvents()
        self.adjustSize()


class StatefulButton(QPushButton):
    """A button that receives its icon colors as tuples (dark, light) and reacts to a signal from the ThemeManager."""

    def __init__(
        self,
        *args,
        theme_manager,
        icon_path=None,
        color_normal: Optional[tuple] = None,
        color_hover: Optional[tuple] = None,
        color_checked: Optional[tuple] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.theme_manager = theme_manager
        self.icon_path = icon_path

        self.color_tuples = {
            "normal": color_normal,
            "hover": color_hover,
            "checked": color_checked,
        }

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_manager.themeChanged.connect(self.updateThemeColors)
        self.updateThemeColors(self.theme_manager.current_theme)

    def updateThemeColors(self, theme: str):
        """Selects the correct colors from the tuples and recreates the icons."""
        if not self.icon_path:
            return

        idx = 1 if theme == "light" else 0

        c_normal = (
            self.color_tuples["normal"][idx] if self.color_tuples["normal"] else None
        )
        c_hover = (
            self.color_tuples["hover"][idx] if self.color_tuples["hover"] else c_normal
        )
        c_checked = (
            self.color_tuples["checked"][idx]
            if self.color_tuples["checked"]
            else c_hover
        )

        if not c_normal:
            return

        self._icon_normal = create_colored_icon(self.icon_path, QColor(c_normal))
        self._icon_hover = create_colored_icon(self.icon_path, QColor(c_hover))
        self._icon_checked = create_colored_icon(self.icon_path, QColor(c_checked))

        self.updateIcon()

    def updateIcon(self):
        if not hasattr(self, "_icon_normal"):
            return
        if self.isChecked():
            self.setIcon(self._icon_checked)
        elif self.underMouse():
            self.setIcon(self._icon_hover)
        else:
            self.setIcon(self._icon_normal)

    def enterEvent(self, event: QEnterEvent):
        super().enterEvent(event)
        self.updateIcon()

    def leaveEvent(self, event: QEvent):
        super().leaveEvent(event)
        self.updateIcon()

    def setChecked(self, checked):
        super().setChecked(checked)
        self.updateIcon()


class AnimatedButton(StatefulButton):
    """A QPushButton that can play a 'shimmer' animation over itself."""

    _offset_changed = Signal()
    _progress_changed = Signal(float)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._progress = 0.0
        self._offset = -0.5
        self._is_animating = False
        self._shimmer_base_color = QColor(255, 255, 255)
        self.current_animation = None

        self.progress_animation = QPropertyAnimation(self, b"progress")
        self.progress_animation.setDuration(200)
        self.progress_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def updateThemeColors(self, theme: str):
        """Sets the appropriate shimmer color based on the current theme."""
        if theme == "light":
            self._shimmer_base_color = QColor(0, 0, 0)
        else:
            self._shimmer_base_color = QColor(255, 255, 255)

        super().updateThemeColors(theme)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        radius = 8 if not self.text() else 10
        path.addRoundedRect(self.rect(), radius, radius)
        painter.setClipPath(path)

        if self._progress > 0:
            fill_color = QColor("#28A745")
            fill_color.setAlphaF(0.3)
            fill_width = self.width() * self._progress
            fill_rect = QRectF(0, 0, fill_width, self.height())
            painter.setBrush(fill_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(fill_rect)

        if self._is_animating:
            painter.save()
            shimmer_width = self.width()
            x_pos = self.width() * self._offset - (shimmer_width / 2)
            shimmer_rect = QRectF(x_pos, 0, shimmer_width, self.height())
            gradient = QLinearGradient(shimmer_rect.topLeft(), shimmer_rect.topRight())
            base_color = self._shimmer_base_color
            c_transparent = QColor(base_color)
            c_transparent.setAlpha(0)
            c_edge_glow = QColor(base_color)
            c_edge_glow.setAlpha(
                30 if self.theme_manager.current_theme == "light" else 25
            )
            c_center_glow = QColor(base_color)
            c_center_glow.setAlpha(
                60 if self.theme_manager.current_theme == "light" else 50
            )
            gradient.setColorAt(0.0, c_transparent)
            gradient.setColorAt(0.33, c_edge_glow)
            gradient.setColorAt(0.5, c_center_glow)
            gradient.setColorAt(0.66, c_edge_glow)
            gradient.setColorAt(1.0, c_transparent)
            painter.shear(-0.2, 0)
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(shimmer_rect)
            painter.restore()

    def _get_progress(self) -> float:
        return self._progress

    def _set_progress(self, value: float):
        self._progress = value
        self._progress_changed.emit(value)
        self.update()

    progress = Property(float, _get_progress, _set_progress, notify=_progress_changed)  # type: ignore

    def set_progress(self, value: float):
        """Animates the progress bar to the target value."""
        if self.progress_animation.state() == QPropertyAnimation.State.Running:
            self.progress_animation.stop()

        self.progress_animation.setStartValue(self.progress)
        self.progress_animation.setEndValue(value)
        self.progress_animation.start()

    def reset_progress(self):
        """Resets the progress bar instantly to 0."""
        if self.progress_animation.state() == QPropertyAnimation.State.Running:
            self.progress_animation.stop()
        self.progress = 0.0

    def _get_offset(self):
        return self._offset

    def _set_offset(self, value):
        self._offset = value
        self._offset_changed.emit()
        self.update()

    offset = Property(float, _get_offset, _set_offset, notify=_offset_changed)  # type: ignore

    def start_animation(self, duration: Optional[int] = None):
        if (
            self.current_animation
            and self.current_animation.state() == QPropertyAnimation.State.Running
        ):
            self.current_animation.stop()

        anim = QPropertyAnimation(self, b"offset")

        if duration:
            anim.setDuration(duration)
            anim.setLoopCount(1)
            anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            anim.finished.connect(self.stop_animation)
        else:
            anim.setDuration(1200)
            anim.setLoopCount(-1)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        anim.setStartValue(-1)
        anim.setEndValue(2)
        self._is_animating = True
        anim.start()

        self.current_animation = anim

    def stop_animation(self):
        self._is_animating = False
        if self.current_animation:
            self.current_animation.stop()
        self.update()


class ToggleSwitch(QWidget):
    """A custom, modern, animated toggle switch widget."""

    toggled = Signal(bool)
    focusChanged = Signal(bool)

    _track_color_changed = Signal()
    _knob_position_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ToggleSwitch")
        self.setFixedSize(52, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._checked = False

        self._track_color_off = QColor("#8B8B8B")
        self._track_color_on = QColor("#28A745")
        self._knob_color = QColor("#FFFFFF")

        self._current_track_color = self._track_color_off
        self._knob_position = 3  # Start position (left)

        self.animation_group = QParallelAnimationGroup()

        self.color_animation = QPropertyAnimation(self, b"track_color")
        self.color_animation.setDuration(200)
        self.animation_group.addAnimation(self.color_animation)

        self.knob_animation = QPropertyAnimation(self, b"knob_position")
        self.knob_animation.setDuration(200)
        self.knob_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation_group.addAnimation(self.knob_animation)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked == checked:
            return
        self._checked = checked

        if checked:
            self.color_animation.setEndValue(self._track_color_on)
            self.knob_animation.setEndValue(self.width() - self.height() + 3)
        else:
            self.color_animation.setEndValue(self._track_color_off)
            self.knob_animation.setEndValue(3)

        self.animation_group.start()
        self.toggled.emit(self._checked)

    def focusInEvent(self, event):
        """Called when the widget gains focus."""
        super().focusInEvent(event)
        self.focusChanged.emit(True)

    def focusOutEvent(self, event):
        """Called when the widget loses focus."""
        super().focusOutEvent(event)
        self.focusChanged.emit(False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(self._current_track_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(track_rect, 13, 13)

        knob_y = (self.height() - 22) / 2
        knob_rect = QRectF(self._knob_position, knob_y, 22, 22)
        painter.setBrush(self._knob_color)
        painter.drawEllipse(knob_rect)

    def mousePressEvent(self, event):
        self.setChecked(not self.isChecked())

    def keyPressEvent(self, event):
        """Handles key presses when the widget has focus."""
        if event.key() == Qt.Key.Key_Space or Qt.Key.Key_Enter:
            self.setChecked(not self.isChecked())
        else:
            super().keyPressEvent(event)

    def _get_track_color(self):
        return self._current_track_color

    def _set_track_color(self, color):
        self._current_track_color = color
        self._track_color_changed.emit()
        self.update()

    def _get_knob_position(self):
        return self._knob_position

    def _set_knob_position(self, pos):
        self._knob_position = pos
        self._knob_position_changed.emit()
        self.update()

    track_color = Property(
        QColor, _get_track_color, _set_track_color, notify=_track_color_changed  # type: ignore
    )
    knob_position = Property(
        float, _get_knob_position, _set_knob_position, notify=_knob_position_changed  # type: ignore
    )


class MainWindow(QMainWindow):
    def __init__(
        self,
        theme_manager: "ThemeManager",
        worker_manager: "WorkerManager",
        loc_manager: "LocalizationManager",
    ):
        super().__init__()
        self._is_ready_to_show = False
        self.setWindowOpacity(0.0)
        self.theme_manager = theme_manager
        self.worker_manager = worker_manager
        self.loc_manager = loc_manager
        self.notification_manager = NotificationManager(self, self.theme_manager)

        self.setWindowTitle("YimMenuUpdater | NV3")
        self.setFixedSize(QSize(780, 520))

        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar_widget = QWidget()
        sidebar_widget.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_widget.setFixedWidth(200)

        self.content_stack = QStackedWidget()

        main_layout.addWidget(sidebar_widget)
        main_layout.addWidget(self.content_stack, stretch=1)
        self.setCentralWidget(main_widget)

        self.risk_page = RiskPage(
            theme_manager=self.theme_manager, loc_manager=self.loc_manager
        )
        self.download_page = DownloadPage(
            theme_manager=self.theme_manager,
            worker_manager=self.worker_manager,
            loc_manager=self.loc_manager,
        )
        self.inject_page = InjectPage(
            theme_manager=self.theme_manager,
            worker_manager=self.worker_manager,
            loc_manager=self.loc_manager,
        )
        self.settings_page = SettingsPage(
            theme_manager=self.theme_manager,
            worker_manager=self.worker_manager,
            loc_manager=self.loc_manager,
        )

        self.content_stack.addWidget(self.risk_page)
        self.content_stack.addWidget(self.download_page)
        self.content_stack.addWidget(self.inject_page)
        self.content_stack.addWidget(self.settings_page)

        self.setup_sidebar(sidebar_layout)
        self._trigger_initial_dll_checks()

    def _on_translation_update_finished(self, update_occurred: bool):
        """Slot: Called when the LocalizationManager has finished checking."""
        if update_occurred:
            title = self.loc_manager.tr("Common.Info", "Info")
            msg = self.loc_manager.tr(
                "Settings.Notify.LangUpdated",
                "Translations were successfully downloaded.\nRestart YMU to see the updated Language List in Settings.",
            )
            self.notification_manager.show(title, msg, icon_type="info", duration=7000)

    def show_when_ready(self):
        """Signals that the app is initialized and triggers the first paint."""
        self._is_ready_to_show = True
        self.update()

    def paintEvent(self, event):
        """Called every time the window needs to be repainted."""
        super().paintEvent(event)

        if self._is_ready_to_show and self.windowOpacity() == 0.0:
            self.setWindowOpacity(1.0)

    def setup_sidebar(self, layout: QVBoxLayout):
        self.button_group = QButtonGroup()
        self.button_group.setExclusive(True)
        self.button_group.buttonClicked.connect(
            lambda: QTimer.singleShot(
                0,
                lambda: [
                    b.updateIcon()
                    for b in self.button_group.buttons()
                    if isinstance(b, StatefulButton)
                ],
            )
        )

        sidebar_colors = {
            "color_normal": ("#8B8B8B", "#555555"),
            "color_hover": ("#E0E0E0", "#121212"),
            "color_checked": ("#E0E0E0", "#121212"),
        }

        btn_risks = StatefulButton(
            f"  {self.loc_manager.tr('Sidebar.Risks')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "alert-triangle.svg")
            ),
            **sidebar_colors,
        )
        btn_risks.setCheckable(True)
        btn_risks.setObjectName("SidebarButton")
        btn_risks.setToolTip(
            self.loc_manager.tr(
                "Sidebar.Tooltip.Risks", "Show important warnings and information"
            )
        )

        btn_download = StatefulButton(
            f"  {self.loc_manager.tr('Sidebar.Download')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "download.svg")),
            **sidebar_colors,
        )
        btn_download.setCheckable(True)
        btn_download.setObjectName("SidebarButton")

        btn_inject = StatefulButton(
            f"  {self.loc_manager.tr('Sidebar.Inject')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "crosshair.svg")),
            **sidebar_colors,
        )
        btn_inject.setCheckable(True)
        btn_inject.setObjectName("SidebarButton")

        btn_settings = StatefulButton(
            f"  {self.loc_manager.tr('Sidebar.Settings')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "settings.svg")),
            **sidebar_colors,
        )
        btn_settings.setCheckable(True)
        btn_settings.setObjectName("SidebarButton")

        layout.addWidget(btn_risks)
        self.button_group.addButton(btn_risks)
        layout.addWidget(btn_download)
        self.button_group.addButton(btn_download)
        layout.addWidget(btn_inject)
        self.button_group.addButton(btn_inject)
        layout.addWidget(btn_settings)
        self.button_group.addButton(btn_settings)
        layout.addStretch()

        footer_button = StatefulButton(
            f"YMU {update_checker.LOCAL_VERSION}\n© NiiV3AU",
            theme_manager=self.theme_manager,
        )
        footer_button.setObjectName("SidebarFooter")
        footer_button.clicked.connect(lambda: webbrowser.open("https://ymu.pages.dev/"))
        footer_button.setToolTip(
            self.loc_manager.tr(
                "Sidebar.Tooltip.ProjectPage",
                "Open the YMU project page in your browser",
            )
        )

        layout.addWidget(footer_button)

        btn_risks.setChecked(True)

        btn_risks.clicked.connect(
            lambda: self.content_stack.setCurrentWidget(self.risk_page)
        )
        btn_download.clicked.connect(
            lambda: self.content_stack.setCurrentWidget(self.download_page)
        )
        btn_inject.clicked.connect(
            lambda: self.content_stack.setCurrentWidget(self.inject_page)
        )
        btn_settings.clicked.connect(
            lambda: self.content_stack.setCurrentWidget(self.settings_page)
        )

    def _trigger_initial_dll_checks(self):
        """
        Triggers a background update check for all DLL channels upon startup
        to populate the cache.
        """
        logger.info("Triggering initial DLL checks in the background...")
        all_channels = list(self.download_page.RELEASE_CHANNELS.keys())

        for i, channel_name in enumerate(all_channels):
            QTimer.singleShot(
                i * 200, lambda name=channel_name: self._check_channel(name)
            )

    def _check_channel(self, channel_name: str):
        """Helper function to check a single channel."""
        logger.info(f"Running startup check for: {channel_name}")
        index = self.download_page.channel_select.findText(channel_name)
        if index != -1:
            self.download_page.channel_select.setCurrentIndex(index)


class RiskPage(QWidget):
    """A page which shows risks and warnings as well as links to repos and FSL."""

    def __init__(self, theme_manager, loc_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.loc_manager = loc_manager

        title_text = self.loc_manager.tr("Risk.Title", "ATTENTION")
        title_label = QLabel(title_text)
        title_label.setObjectName("RiskTitleLabel")

        info_text = self.loc_manager.tr(
            "Risk.Info",
            "Always use YMU and YimMenu with BattlEye DISABLED.\nUsing mods online carries a risk of being banned.",
        )
        info_label = QLabel(info_text)
        info_label.setObjectName("RiskInfoLabel")
        info_label.setWordWrap(True)

        link_button_colors = {
            "color_normal": ("#8B8B8B", "#555555"),
            "color_hover": ("#E0E0E0", "#121212"),
        }

        yim_official_repo_button = StatefulButton(
            f"  {self.loc_manager.tr('Risk.Btn.YimOfficial', 'Official YimMenu GitHub Repo')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        yim_official_repo_button.setObjectName("LinkButton")
        yim_official_repo_button.setToolTip(
            self.loc_manager.tr(
                "Risk.Tooltip.YimOfficial",
                "Open the official YimMenu GitHub repository",
            )
        )
        yim_official_repo_button.clicked.connect(
            lambda: webbrowser.open("https://github.com/YimMenu/YimMenu")
        )

        yim_repo_button = StatefulButton(
            f"  {self.loc_manager.tr('Risk.Btn.YimLegacy', 'YimMenu (legacy) GitHub Repo')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        yim_repo_button.setObjectName("LinkButton")
        yim_repo_button.setToolTip(
            self.loc_manager.tr(
                "Risk.Tooltip.YimLegacy", "Open the YimMenu (legacy) GitHub repository"
            )
        )
        yim_repo_button.clicked.connect(
            lambda: webbrowser.open("https://github.com/Mr-X-GTA/YimMenu")
        )

        yimv2_repo_button = StatefulButton(
            f"  {self.loc_manager.tr('Risk.Btn.YimV2', 'YimMenuV2 (enhanced) GitHub Repo')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        yimv2_repo_button.setObjectName("LinkButton")
        yimv2_repo_button.setToolTip(
            self.loc_manager.tr(
                "Risk.Tooltip.YimV2", "Open the YimMenuV2 (enhanced) GitHub repository"
            )
        )
        yimv2_repo_button.clicked.connect(
            lambda: webbrowser.open("https://github.com/YimMenu/YimMenuV2")
        )

        fsl_thread_button = StatefulButton(
            f"  {self.loc_manager.tr('Risk.Btn.FSL', "FSL's UC-Thread")}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        fsl_thread_button.setObjectName("LinkButton")
        fsl_thread_button.setToolTip(
            self.loc_manager.tr(
                "Risk.Tooltip.FSL",
                "Open the FSL thread on UnknownCheats for download & support",
            )
        )
        fsl_thread_button.clicked.connect(
            lambda: webbrowser.open(
                "https://www.unknowncheats.me/forum/grand-theft-auto-v/616977-fsl-local-gtao-saves.html"
            )
        )

        card_frame = QFrame()
        card_frame.setObjectName("CardFrame")

        card_layout = QVBoxLayout(card_frame)
        card_layout.setSpacing(15)
        card_layout.addWidget(title_label)
        card_layout.addWidget(info_label)
        card_layout.addSpacing(10)
        card_layout.addWidget(yim_official_repo_button)
        card_layout.addWidget(yim_repo_button)
        card_layout.addWidget(yimv2_repo_button)
        card_layout.addWidget(fsl_thread_button)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(60, 0, 60, 0)
        main_layout.addStretch()
        main_layout.addWidget(card_frame)
        main_layout.addStretch()


class DownloadPage(QWidget):
    STATUS_UPTODATE = "STATUS_UPTODATE"
    STATUS_DOWNLOAD = "STATUS_DOWNLOAD"
    STATUS_UPDATE = "STATUS_UPDATE"
    RELEASE_CHANNELS = {
        "YimMenu (Legacy)": {"repo": "Mr-X-GTA/YimMenu", "dll_name": "YimMenu.dll"},
        "YimMenuV2 (Enhanced)": {
            "repo": "YimMenu/YimMenuV2",
            "dll_name": "YimMenuV2.dll",
        },
    }

    def __init__(self, theme_manager, worker_manager, loc_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.worker_manager = worker_manager
        self.loc_manager = loc_manager

        self.latest_release_data = None
        self.release_provider = None
        self._release_cache = {}
        self.CACHE_DURATION_SECONDS = 300

        self.is_download_ready = False

        info_button = StatefulButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "help-circle.svg")),
            color_normal=("#8B8B8B", "#777777"),
            color_hover=("#E0E0E0", "#121212"),
        )
        info_button.setObjectName("InfoButton")
        info_button.setToolTip(
            self.loc_manager.tr(
                "Download.Tooltip.Help", "Show help for DLL and FSL installation"
            )
        )
        info_button.setIconSize(QSize(20, 20))

        self.channel_select = QComboBox()
        self.channel_select.addItems(list(self.RELEASE_CHANNELS.keys()))
        self.channel_select.setToolTip(
            self.loc_manager.tr(
                "Download.Tooltip.Channel", "Select the YimMenu version to download"
            )
        )
        self.channel_select.setCursor(Qt.CursorShape.PointingHandCursor)
        self.status_label = QLabel(
            self.loc_manager.tr(
                "Download.Status.Initial", "Select a channel to check for updates."
            )
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.download_button = AnimatedButton(
            self.loc_manager.tr("Download.Btn.Check", "Check for Updates"),
            theme_manager=self.theme_manager,
        )
        self.download_button.setMinimumWidth(140)
        self.download_button.setFixedHeight(40)
        self.download_button.setEnabled(True)

        header_layout = QHBoxLayout()
        header_layout.addStretch()
        header_layout.addWidget(info_button)

        card_frame = QFrame()
        card_frame.setObjectName("CardFrame")
        card_layout = QVBoxLayout(card_frame)
        card_layout.setSpacing(15)
        card_layout.addWidget(self.channel_select)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(
            self.download_button, alignment=Qt.AlignmentFlag.AlignCenter
        )

        centering_layout = QHBoxLayout()
        centering_layout.addStretch()
        centering_layout.addWidget(card_frame)
        centering_layout.addStretch()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addLayout(header_layout)
        main_layout.addStretch()
        main_layout.addLayout(centering_layout)
        main_layout.addStretch()

        info_button.clicked.connect(self.show_download_info_dialog)
        self.download_button.clicked.connect(self._on_download_button_clicked)
        self.channel_select.currentIndexChanged.connect(self.trigger_update_check)

        self.trigger_update_check()

    def _on_download_button_clicked(self):
        """This handler decides what happens when you click."""
        if self.is_download_ready:
            self.start_download()
        else:
            self.trigger_update_check()

    def trigger_update_check(self):
        """Starts the update check for the currently selected channel."""
        self.is_download_ready = False

        self.status_label.setText(
            self.loc_manager.tr("Download.Status.Checking", "Checking for updates...")
        )
        self.download_button.setEnabled(False)
        self.download_button.setText(
            self.loc_manager.tr("Download.Btn.Checking", "Checking...")
        )

        selected_channel_name = self.channel_select.currentText()
        channel_info = self.RELEASE_CHANNELS[selected_channel_name]
        repo_path = channel_info["repo"]
        dll_name = channel_info["dll_name"]

        self.release_provider = release_service.GitHubAPIProvider(repository=repo_path)
        self.local_dll_path = os.path.join(YMU_DLL_DIR, dll_name)

        self.worker_manager.run_task(
            target=self._update_check_logic,
            on_finished=self._handle_update_check_result,
            on_error=self._handle_worker_error,
        )

    def update_download_progress(self, percentage: int):
        self.download_button.set_progress(percentage / 100.0)

    def show_download_info_dialog(self):
        """Creates and displays the info dialog for the download page."""

        dll_info_default = (
            "1. Click on (Download)\n"
            "2. Wait for the download to finish\n"
            "3. The file is in the 'YMU/dll' folder\n\n"
            "If the file gets deleted, add an exception\n"
            "in your antivirus or disable it temporarily."
        )
        dll_info_text = self.loc_manager.tr("Download.Help.DllSteps", dll_info_default)

        fsl_info_default = (
            "1. Download FSL (Link provided in the Risks Page)\n"
            "2. Open your GTAV Directory\n"
            "3. Drop the WINMM.dll in the folder\n"
            "   (filename MUST be exactly 'WINMM.dll')\n"
            "4. Disable BattlEye in Rockstar's Game Launcher\n"
            "5. Done! ✅"
        )
        fsl_info_text = self.loc_manager.tr("Download.Help.FslSteps", fsl_info_default)

        content = {"DLL": dll_info_text, "FSL": fsl_info_text}

        dialog = InfoDialog(
            title=self.loc_manager.tr("Download.Help.Title", "DLL & FSL Info"),
            content=content,
            theme_manager=self.theme_manager,
            parent=self,
        )
        dialog.exec()

    def _update_check_logic(self, progress_signal=None):
        """
        Fetches the latest release data.
        RETURNS CONSTANTS instead of display strings.
        """
        if self.release_provider is None:
            raise RuntimeError("Release provider has not been initialized.")

        selected_channel_name = self.channel_select.currentText()
        repo_path = self.RELEASE_CHANNELS[selected_channel_name]["repo"]
        current_time = time.time()

        if repo_path in self._release_cache:
            cached_data, timestamp = self._release_cache[repo_path]
            if (current_time - timestamp) < self.CACHE_DURATION_SECONDS:
                logger.info(f"Using cached release data for {repo_path}.")
                self.latest_release_data = cached_data
                return self._compare_checksums()

        logger.info(f"Fetching fresh release data for {repo_path}.")
        self.latest_release_data = self.release_provider.get_latest_release()

        if not self.latest_release_data:
            raise RuntimeError("Failed to fetch release data from GitHub.")

        self._release_cache[repo_path] = (self.latest_release_data, current_time)
        return self._compare_checksums()

    def _compare_checksums(self):
        """Helper to determine status based on checksums."""
        assert self.latest_release_data is not None
        local_checksum = release_service.get_local_sha256(self.local_dll_path)

        if local_checksum == self.latest_release_data.checksum:
            return self.STATUS_UPTODATE
        elif local_checksum is None:
            return self.STATUS_DOWNLOAD
        else:
            return self.STATUS_UPDATE

    def _handle_update_check_result(self, status: str):
        if status == self.STATUS_UPTODATE:
            self.is_download_ready = False
            self.status_label.setText(
                self.loc_manager.tr(
                    "Download.Status.UpToDate", "YimMenu is up-to-date."
                )
            )
            self.download_button.setText(
                self.loc_manager.tr("Download.Btn.UpToDate", "Up-to-date")
            )
            self.download_button.setEnabled(False)

        elif status in [self.STATUS_DOWNLOAD, self.STATUS_UPDATE]:
            self.is_download_ready = True
            self.status_label.setText(
                self.loc_manager.tr(
                    "Download.Status.NewVersion", "A new version is available!"
                )
            )

            btn_key = (
                "Download.Btn.Update"
                if status == self.STATUS_UPDATE
                else "Download.Btn.Download"
            )
            self.download_button.setText(self.loc_manager.tr(btn_key))
            self.download_button.setEnabled(True)

            title_fmt = self.loc_manager.tr("Download.Notify.UpdateTitle", "{0} Update")
            cast(MainWindow, self.window()).notification_manager.show(
                title_fmt.format(self.channel_select.currentText()),
                self.loc_manager.tr(
                    "Download.Notify.NewVersion", "A new version is ready."
                ),
                icon_type="info",
            )

    def _handle_worker_error(self, error: Exception):
        """Callback for any error originating from the worker."""
        self.is_download_ready = False
        self.status_label.setText(
            self.loc_manager.tr(
                "Download.Status.Error", "An error occurred. Please try again."
            )
        )
        self.download_button.setText(
            self.loc_manager.tr("Download.Btn.Retry", "Retry Check")
        )
        self.download_button.setEnabled(True)

        cast(MainWindow, self.window()).notification_manager.show(
            self.loc_manager.tr("Common.Error", "Error"),
            f"{self.loc_manager.tr('Download.Notify.CheckFailed', 'Failed to check for updates')}: {error}",
            icon_type="error",
        )

    def start_download(self):
        """Starts the download process."""
        if not self.latest_release_data:
            self._handle_worker_error(
                RuntimeError("No release information to start download.")
            )
            return

        self.status_label.setText(
            f"{self.loc_manager.tr('Download.Status.Downloading', 'Downloading')} {self.latest_release_data.asset_name}..."
        )
        self.download_button.setEnabled(False)
        self.download_button.setText(
            self.loc_manager.tr("Download.Btn.Downloading", "Downloading...")
        )
        self.download_button.stop_animation()
        QApplication.processEvents()

        self.worker_manager.run_task(
            target=self._download_logic,
            on_finished=self._handle_download_result,
            on_error=self._handle_worker_error,
            on_progress=self.update_download_progress,
        )

    def _download_logic(self, progress_signal=None):
        """Runs in the background and executes the download."""
        assert self.latest_release_data is not None

        def progress_callback(percentage):
            if progress_signal:
                progress_signal.emit(percentage)

        success = release_service.download_and_verify_release(
            self.latest_release_data, progress_callback
        )
        return success

    def _handle_download_result(self, success: bool):
        if success:
            self.download_button.set_progress(1.0)
            self.status_label.setText(
                self.loc_manager.tr(
                    "Download.Status.Success", "Download successful and verified!"
                )
            )

            cast(MainWindow, self.window()).notification_manager.show(
                self.loc_manager.tr(
                    "Download.Notify.SuccessTitle", "Download Complete"
                ),
                self.loc_manager.tr(
                    "Download.Notify.SuccessMsg",
                    "DLL successfully downloaded and verified!",
                ),
                icon_type="success",
            )

            QTimer.singleShot(400, self._set_to_uptodate_state)
        else:
            self.download_button.reset_progress()
            cast(MainWindow, self.window()).notification_manager.show(
                self.loc_manager.tr("Download.Notify.FailedTitle", "Download Failed"),
                self.loc_manager.tr(
                    "Download.Notify.FailedMsg",
                    "Verification failed. Please check the logs.",
                ),
                icon_type="error",
            )
            self.status_label.setText(
                self.loc_manager.tr(
                    "Download.Status.Failed", "Download failed. Check logs."
                )
            )
            self.download_button.setEnabled(True)
            self.download_button.setText(
                self.loc_manager.tr("Download.Btn.Update", "Update")
            )
            self.is_download_ready = True

    def _set_to_uptodate_state(self):
        """Helper method to set the final UI state."""
        self.download_button.reset_progress()
        self.download_button.setText(
            self.loc_manager.tr("Download.Btn.UpToDate", "Up-to-date")
        )
        self.download_button.setEnabled(False)
        self.is_download_ready = False


class InjectPage(QWidget):
    STATE_IDLE = "IDLE"
    STATE_LAUNCHING = "LAUNCHING"
    STATE_APP_RUNNING = "APP_RUNNING"
    STATE_INJECTING = "INJECTING"
    STATE_INJECTED = "INJECTED"

    def __init__(self, theme_manager, worker_manager, loc_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.worker_manager = worker_manager
        self.loc_manager = loc_manager

        self.gta_pid = None
        self._state = self.STATE_IDLE
        self.dll_to_inject = None

        info_button = StatefulButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "help-circle.svg")),
            color_normal=("#8B8B8B", "#777777"),
            color_hover=("#E0E0E0", "#121212"),
        )
        info_button.setObjectName("InfoButton")

        info_button.setToolTip(
            self.loc_manager.tr(
                "Inject.Tooltip.Help", "Show help for the injection process"
            )
        )
        info_button.setIconSize(QSize(20, 20))

        self.launcher_select = QComboBox()
        select_txt = self.loc_manager.tr("Inject.Launcher.Select", "Select Launcher")
        self.launcher_select.addItems(
            [select_txt, "Steam", "Epic Games", "Rockstar Games"]
        )
        self.launcher_select.setFixedWidth(175)
        self.launcher_select.setToolTip(
            self.loc_manager.tr(
                "Inject.Tooltip.Launcher", "Select the launcher you use to start GTA V"
            )
        )
        self.launcher_select.setCursor(Qt.CursorShape.PointingHandCursor)

        self.dll_select = QComboBox()
        self.dll_select.setToolTip(
            self.loc_manager.tr("Inject.Tooltip.Dll", "Select the DLL to inject")
        )
        self.dll_select.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dll_select.setVisible(False)

        self.start_gta_button = AnimatedButton(
            self.loc_manager.tr("Inject.Btn.StartGta", "Start GTA 5"),
            theme_manager=self.theme_manager,
        )
        self.start_gta_button.setEnabled(False)

        self.inject_button = AnimatedButton(
            self.loc_manager.tr("Inject.Btn.InjectBase", "Inject YimMenu"),
            theme_manager=self.theme_manager,
        )
        self.inject_button.setEnabled(False)

        header_layout = QHBoxLayout()
        header_layout.addStretch()
        header_layout.addWidget(info_button)

        controls_frame = QFrame()
        controls_frame.setObjectName("CardFrame")
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setSpacing(15)
        controls_layout.addWidget(
            self.launcher_select, alignment=Qt.AlignmentFlag.AlignCenter
        )
        controls_layout.addWidget(
            self.dll_select, alignment=Qt.AlignmentFlag.AlignCenter
        )
        controls_layout.addWidget(
            self.start_gta_button, alignment=Qt.AlignmentFlag.AlignCenter
        )
        controls_layout.addWidget(
            self.inject_button, alignment=Qt.AlignmentFlag.AlignCenter
        )

        centering_controls_layout = QHBoxLayout()
        centering_controls_layout.addStretch()
        centering_controls_layout.addWidget(controls_frame)
        centering_controls_layout.addStretch()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addLayout(header_layout)
        main_layout.addStretch()
        main_layout.addLayout(centering_controls_layout)
        main_layout.addStretch()

        info_button.clicked.connect(self.show_inject_info_dialog)
        self.start_gta_button.clicked.connect(self.handle_start_gta_click)
        self.inject_button.clicked.connect(self.handle_inject_click)
        self.launcher_select.currentIndexChanged.connect(
            self._on_launcher_selection_changed
        )
        self.dll_select.currentIndexChanged.connect(self._on_dll_selection_changed)

        self.process_checker_timer = QTimer(self)
        self.process_checker_timer.setInterval(3000)
        self.process_checker_timer.timeout.connect(self._run_process_check)

    def showEvent(self, event):
        """Called every time the page becomes visible."""
        super().showEvent(event)
        self._update_dll_selector()
        self.process_checker_timer.start()
        logger.debug("InjectPage shown, started process checker timer.")

    def hideEvent(self, event):
        """Called every time the page is hidden."""
        super().hideEvent(event)
        self.process_checker_timer.stop()
        logger.debug("InjectPage hidden, stopped process checker timer.")

    def _set_state(self, new_state):
        """The only function that should ever change the state."""
        logger.debug(f"State changed: {self._state} -> {new_state}")
        self._state = new_state
        self._update_ui_for_state()

    def _update_ui_for_state(self):
        """Updates the entire UI based on the current state."""
        is_launcher_selected = self.launcher_select.currentIndex() > 0
        has_dll = self.dll_to_inject is not None

        if self._state == self.STATE_IDLE:
            self.start_gta_button.setEnabled(is_launcher_selected)
            self.inject_button.setEnabled(False)
            self.start_gta_button.stop_animation()

        elif self._state == self.STATE_LAUNCHING:
            self.start_gta_button.setEnabled(False)
            self.inject_button.setEnabled(False)
            self.start_gta_button.start_animation()

        elif self._state == self.STATE_APP_RUNNING:
            self.start_gta_button.setEnabled(False)
            self.inject_button.setEnabled(has_dll)
            self.start_gta_button.stop_animation()

        elif self._state == self.STATE_INJECTING:
            self.start_gta_button.setEnabled(False)
            self.inject_button.setEnabled(False)
            self.inject_button.start_animation(duration=500)

        elif self._state == self.STATE_INJECTED:
            self.start_gta_button.setEnabled(False)
            self.inject_button.setEnabled(False)
            self.inject_button.stop_animation()

    def _update_dll_selector(self):
        """Scans the DLL folder and dynamically adjusts the UI."""
        dll_dir = YMU_DLL_DIR
        os.makedirs(dll_dir, exist_ok=True)

        found_dlls = [f for f in os.listdir(dll_dir) if f.lower().endswith(".dll")]
        cleaned_names = [name.removesuffix(".dll") for name in found_dlls]

        self.dll_select.clear()

        if len(found_dlls) == 0:
            self.dll_select.setVisible(False)
            self.dll_to_inject = None
            self.inject_button.setText(
                self.loc_manager.tr("Inject.Btn.NoDll", "No DLL found")
            )
            self.inject_button.setEnabled(False)

        elif len(found_dlls) == 1:
            self.dll_select.setVisible(False)
            self.dll_to_inject = found_dlls[0]
            fmt = self.loc_manager.tr("Inject.Btn.InjectFile", "Inject {0}")
            self.inject_button.setText(fmt.format(cleaned_names[0]))

        else:
            self.dll_select.addItems(cleaned_names)
            self.dll_select.setVisible(True)
            current_cleaned_name = self.dll_select.currentText()
            self.dll_to_inject = f"{current_cleaned_name}.dll"
            fmt = self.loc_manager.tr("Inject.Btn.InjectFile", "Inject {0}")
            self.inject_button.setText(fmt.format(current_cleaned_name))

        self._update_ui_for_state()

    def _on_dll_selection_changed(self, index):
        """Updates the DLL to be injected when the user makes a selection."""
        if index > -1:
            cleaned_name = self.dll_select.currentText()
            fmt = self.loc_manager.tr("Inject.Btn.InjectFile", "Inject {0}")
            self.inject_button.setText(fmt.format(cleaned_name))

            self.dll_to_inject = f"{cleaned_name}.dll"
        self._update_ui_for_state()

    def _on_launcher_selection_changed(self):
        """Enables or disables the start button based on the dropdown selection."""
        self._update_ui_for_state()

    def show_inject_info_dialog(self):
        start_gta_default = (
            "1. Select your launcher\n"
            "2. Press 'Start GTA 5'\n"
            "3. Read the next step ↗"
        )
        start_gta_text = self.loc_manager.tr(
            "Inject.Help.StartGtaSteps", start_gta_default
        )

        inject_default = (
            "1. Start GTA 5 (↖ Previous Step)\n"
            "2. Wait for the game's start screen/menu\n"
            "3. Click on 'Inject YimMenu'\n"
            "4. Wait for YimMenu to finish loading\n"
            "5. Done! ✅"
        )
        inject_text = self.loc_manager.tr("Inject.Help.InjectSteps", inject_default)

        content = {
            self.loc_manager.tr("Inject.Btn.StartGta", "Start GTA 5"): start_gta_text,
            self.loc_manager.tr("Inject.Help.TabInject", "Inject DLL"): inject_text,
        }

        dialog = InfoDialog(
            title=self.loc_manager.tr("Inject.Help.Title", "Injection Info"),
            content=content,
            theme_manager=self.theme_manager,
            parent=self,
        )
        dialog.exec()

    def handle_start_gta_click(self):
        if self._state != self.STATE_IDLE:
            return
        if process_manager.find_gta_pid() is not None:
            cast(MainWindow, self.window()).notification_manager.show(
                self.loc_manager.tr("Common.Info", "Information"),
                self.loc_manager.tr(
                    "Inject.Notify.AlreadyRunning", "GTA 5 is already running!"
                ),
                icon_type="info",
            )
            return
        if self.launcher_select.currentIndex() == 0:
            cast(MainWindow, self.window()).notification_manager.show(
                self.loc_manager.tr("Common.Error", "Error"),
                self.loc_manager.tr(
                    "Inject.Notify.SelectLauncher", "Please select a launcher first."
                ),
                icon_type="error",
            )
            return

        self._set_state(self.STATE_LAUNCHING)
        self.worker_manager.run_task(
            target=self._launch_game_logic,
            on_finished=self.on_launch_attempt_finished,
            on_error=self.on_task_error,
        )

    def _get_rockstar_path(self) -> str | None:
        """Finds the GTA V install path via Registry (Standard & Enhanced)."""
        if not IS_WINDOWS:
            return None
        possible_subkeys = [
            r"SOFTWARE\Rockstar Games\Grand Theft Auto V",
            r"SOFTWARE\WOW6432Node\Rockstar Games\Grand Theft Auto V",
            r"SOFTWARE\Rockstar Games\GTAV Enhanced",
            r"SOFTWARE\WOW6432Node\Rockstar Games\GTAV Enhanced",
        ]

        for subkey in possible_subkeys:
            try:
                regkey = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, subkey, 0, winreg.KEY_READ
                )
                path, _ = winreg.QueryValueEx(regkey, "InstallFolder")
                winreg.CloseKey(regkey)
                if path:
                    path = path.strip('"').strip()
                    if os.path.exists(path):
                        logger.info(f"Found GTA V path via registry at: {path}")
                        return path
            except OSError:
                continue

        logger.error("Could not find Rockstar Games installation path in registry.")
        return None

    def _launch_game_logic(self, progress_signal=None):
        """Contains the actual logic for launching the game."""
        launcher = self.launcher_select.currentText()
        logger.info(f"Attempting to launch GTA 5 via {launcher} launcher.")
        launch_uris = {
            "Steam": "steam://run/271590",
            "Epic Games": "com.epicgames.launcher://apps/9d2d0eb64d5c44529cece33fe2a46482?action=launch&silent=true",
        }

        uri = launch_uris.get(launcher)
        if uri:
            try:
                webbrowser.open(uri)
                logger.info(f"Successfully sent launch command to {launcher}.")
                return f"Launch command sent to {launcher}."
            except Exception as e:
                logger.exception(f"Failed to open URI for {launcher}: {e}")
                raise RuntimeError(f"Could not send command to {launcher}.") from e

        elif launcher == "Rockstar Games":
            path = self._get_rockstar_path()
            if not path:
                msg = self.loc_manager.tr(
                    "Inject.Error.NoRockstarPath",
                    "Could not find Rockstar Games installation path.",
                )
                logger.error(msg)
                raise FileNotFoundError(msg)

            executable_path = os.path.join(path, "PlayGTAV.exe")
            if not os.path.exists(executable_path):
                msg = self.loc_manager.tr(
                    "Inject.Error.NoExeFound", "Executable not found at '{0}'"
                ).format(executable_path)
                logger.error(msg)
                raise FileNotFoundError(msg)

            try:
                os.startfile(executable_path)
                return "Success"
            except OSError as e:
                logger.exception(f"Failed to start PlayGTAV.exe: {e}")
                msg = self.loc_manager.tr(
                    "Inject.Error.LaunchFailed",
                    "Error launching game. See logs for details.",
                )
                raise RuntimeError(msg) from e
        else:
            logger.error(
                f"Logic Error: Attempted to launch with unhandled launcher: {launcher}"
            )
            raise ValueError(f"Internal Error: Unhandled launcher {launcher}")

    def on_launch_attempt_finished(self, result: str):
        """Callback for when the game launch task finishes."""
        logger.info(f"Launch attempt finished with result: {result}")

    def _run_process_check(self):
        if self._state in [self.STATE_INJECTING]:
            return
        self.worker_manager.run_task(
            target=process_manager.find_gta_pid,
            on_finished=self.update_inject_button_status,
        )

    def update_inject_button_status(self, pid: int | None):
        self.gta_pid = pid

        if self.gta_pid is not None:
            if self._state != self.STATE_INJECTED:
                self._set_state(self.STATE_APP_RUNNING)
        else:
            if self._state != self.STATE_LAUNCHING:
                self._set_state(self.STATE_IDLE)

    def handle_inject_click(self):
        if self._state != self.STATE_APP_RUNNING:
            return

        self._set_state(self.STATE_INJECTING)
        self.worker_manager.run_task(
            target=self._inject_logic,
            on_finished=self.on_injection_complete,
            on_error=self.on_task_error,
        )

    def _inject_logic(self, progress_signal=None):
        """Contains the actual logic for injecting the DLL."""
        assert self.gta_pid is not None

        if not self.dll_to_inject:
            msg = self.loc_manager.tr(
                "Inject.Error.NoDllSelected",
                "Error: No DLL selected or found for injection.",
            )
            raise ValueError(msg)

        if not process_manager.is_process_running(self.gta_pid):
            msg = self.loc_manager.tr(
                "Inject.Error.ProcessLost",
                "GTA 5 process disappeared before injection.",
            )
            raise RuntimeError(msg)

        success = process_manager.inject_dll(self.gta_pid, self.dll_to_inject)

        if success:
            return "Success"
        else:
            msg = self.loc_manager.tr(
                "Inject.Error.InjectionFailed",
                "Injection failed. See logs for details.",
            )
            raise RuntimeError(msg)

    def on_injection_complete(self, result: str):
        """Callback for when the injection task finishes."""
        self._set_state(self.STATE_INJECTED)
        logger.info(f"Injection finished with result: {result}")

        cast(MainWindow, self.window()).notification_manager.show(
            self.loc_manager.tr("Inject.Notify.SuccessTitle", "Injection Successful"),
            self.loc_manager.tr(
                "Inject.Notify.SuccessMsg", "Successfully injected DLL!"
            ),
            icon_type="success",
        )

    def on_task_error(self, error: Exception):
        logger.error(f"A task failed in the background: {error}")
        cast(MainWindow, self.window()).notification_manager.show(
            self.loc_manager.tr("Common.Error", "An Error Occurred"),
            str(error),
            icon_type="error",
        )
        if self.gta_pid:
            self._set_state(self.STATE_APP_RUNNING)
        else:
            self._set_state(self.STATE_IDLE)


class SettingsPage(QWidget):
    def __init__(self, theme_manager, worker_manager, loc_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.worker_manager = worker_manager
        self.loc_manager = loc_manager
        self._is_task_running = False

        scroll_content_widget = QWidget()
        scroll_content_widget.setObjectName("ScrollContainer")
        content_layout = QVBoxLayout(scroll_content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        appearance_frame = QFrame()
        appearance_frame.setObjectName("CardFrame")
        appearance_layout = QVBoxLayout(appearance_frame)

        appearance_title = QLabel(
            self.loc_manager.tr("Settings.Header.Appearance", "Appearance")
        )
        appearance_title.setObjectName("SettingsTitle")

        theme_button_layout = QHBoxLayout()
        self.theme_group = QButtonGroup()
        self.theme_group.setExclusive(True)

        btn_dark_theme = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Theme.Dark', 'Dark')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "moon.svg")),
            color_normal=("#8B8B8B", "#555555"),
            color_hover=("#CCCCCC", "#121212"),
            color_checked=("#121212", "#FFFFFF"),
        )
        btn_dark_theme.setObjectName("ThemeButton")
        btn_dark_theme.setCheckable(True)

        btn_light_theme = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Theme.Light', 'Light')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "sun.svg")),
            color_normal=("#8B8B8B", "#555555"),
            color_hover=("#CCCCCC", "#121212"),
            color_checked=("#121212", "#FFFFFF"),
        )
        btn_light_theme.setObjectName("ThemeButton")
        btn_light_theme.setCheckable(True)

        self.theme_group.addButton(btn_dark_theme)
        self.theme_group.addButton(btn_light_theme)

        if self.theme_manager.current_theme == "light":
            btn_light_theme.setChecked(True)
        else:
            btn_dark_theme.setChecked(True)

        self.theme_group.buttonClicked.connect(
            lambda: QTimer.singleShot(
                0,
                lambda: [
                    b.updateIcon()
                    for b in self.theme_group.buttons()
                    if isinstance(b, StatefulButton)
                ],
            )
        )
        btn_dark_theme.clicked.connect(lambda: self.theme_manager.apply_theme("dark"))
        btn_light_theme.clicked.connect(lambda: self.theme_manager.apply_theme("light"))

        theme_button_layout.addWidget(btn_dark_theme)
        theme_button_layout.addWidget(btn_light_theme)

        lang_layout = QHBoxLayout()
        lang_label = QLabel(self.loc_manager.tr("Settings.Label.Language", "Language"))

        self.lang_combo = QComboBox()
        self.lang_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lang_combo.setFixedWidth(150)
        self.lang_combo.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.Language",
                "Select application language (requires restart)",
            )
        )

        available_locales = self.loc_manager.get_available_locales()

        for code in available_locales:
            display_name = self.loc_manager.get_language_name(code)
            self.lang_combo.addItem(display_name, code)

            if code == self.loc_manager.active_locale:
                self.lang_combo.setCurrentIndex(self.lang_combo.count() - 1)

        self._lang_debounce_timer = QTimer()
        self._lang_debounce_timer.setSingleShot(True)
        self._lang_debounce_timer.setInterval(250)
        self._lang_debounce_timer.timeout.connect(self._commit_language_change)

        self.btn_update_lang = AnimatedButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "download-cloud.svg")
            ),
            color_normal=("#8B8B8B", "#555555"),
            color_hover=("#E0E0E0", "#121212"),
        )
        self.btn_update_lang.setObjectName("RefreshButton")
        self.btn_update_lang.setFixedSize(32, 32)
        self.btn_update_lang.setIconSize(QSize(20, 20))
        self.btn_update_lang.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.UpdateLang", "Check for translation updates"
            )
        )

        self.btn_update_lang.clicked.connect(self._on_fetch_lang_clicked)
        self.loc_manager.update_finished.connect(self._on_lang_fetch_finished)
        self.lang_combo.currentIndexChanged.connect(
            lambda: self._lang_debounce_timer.start()
        )
        lang_layout.addWidget(lang_label)
        lang_layout.addStretch()
        lang_layout.addWidget(self.btn_update_lang)
        lang_layout.addSpacing(10)
        lang_layout.addWidget(self.lang_combo)

        appearance_layout.addWidget(appearance_title)
        appearance_layout.addLayout(theme_button_layout)
        appearance_layout.addSpacing(10)
        appearance_layout.addLayout(lang_layout)

        color_normal_lua = ("#8B8B8B", "#555555")
        color_hover_lua = ("#E0E0E0", "#121212")
        lua_frame = QFrame()
        lua_frame.setObjectName("CardFrame")
        lua_layout = QVBoxLayout(lua_frame)

        lua_title = QLabel(self.loc_manager.tr("Settings.Header.Lua", "Lua Settings"))
        lua_title.setObjectName("SettingsTitle")

        auto_reload_layout = QHBoxLayout()
        self.auto_reload_label = QLabel(
            self.loc_manager.tr(
                "Settings.Lua.AutoReload", "Auto-reload changed scripts"
            )
        )
        self.auto_reload_toggle = ToggleSwitch()
        self.auto_reload_toggle.setToolTip(
            self.loc_manager.tr(
                "Settings.Lua.Tooltip.AutoReload",
                "Automatically re-apply changes when Lua script files are saved",
            )
        )

        auto_reload_layout.addWidget(self.auto_reload_label)
        auto_reload_layout.addStretch()
        auto_reload_layout.addWidget(self.auto_reload_toggle)

        lua_layout.addWidget(lua_title)
        lua_layout.addLayout(auto_reload_layout)

        manager_grid_layout = QGridLayout()

        disabled_label = QLabel(
            self.loc_manager.tr("Settings.Lua.ListDisabled", "Disabled")
        )
        disabled_label.setObjectName("DisabledListHeader")
        enabled_label = QLabel(
            self.loc_manager.tr("Settings.Lua.ListEnabled", "Enabled")
        )
        enabled_label.setObjectName("EnabledListHeader")

        manager_grid_layout.addWidget(disabled_label, 0, 0)
        manager_grid_layout.addWidget(enabled_label, 0, 2)

        self.disabled_scripts_list = QListWidget()
        self.disabled_scripts_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )

        self.enabled_scripts_list = QListWidget()
        self.enabled_scripts_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )

        manager_grid_layout.addWidget(self.disabled_scripts_list, 1, 0)
        manager_grid_layout.addWidget(self.enabled_scripts_list, 1, 2)

        buttons_layout = QVBoxLayout()
        buttons_layout.addStretch()

        btn_enable_script = StatefulButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "chevron-right.svg")
            ),
            color_normal=color_normal_lua,
            color_hover=("#FFFFFF", "#FFFFFF"),
        )
        btn_enable_script.setObjectName("EnableButton")
        btn_enable_script.setIconSize(QSize(20, 20))
        btn_enable_script.setFixedSize(36, 36)
        btn_enable_script.setToolTip(
            self.loc_manager.tr(
                "Settings.Lua.Tooltip.Enable", "Enable selected script(s)"
            )
        )

        self.btn_refresh_luas = AnimatedButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "refresh-cw.svg")),
            color_normal=color_normal_lua,
            color_hover=color_hover_lua,
        )
        self.btn_refresh_luas.setObjectName("RefreshButton")
        self.btn_refresh_luas.setIconSize(QSize(20, 20))
        self.btn_refresh_luas.setFixedSize(36, 36)
        self.btn_refresh_luas.setToolTip(
            self.loc_manager.tr("Settings.Lua.Tooltip.Refresh", "Refresh script lists")
        )

        btn_disable_script = StatefulButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "chevron-left.svg")
            ),
            color_normal=color_normal_lua,
            color_hover=("#FFFFFF", "#FFFFFF"),
        )
        btn_disable_script.setObjectName("DisableButton")
        btn_disable_script.setIconSize(QSize(20, 20))
        btn_disable_script.setFixedSize(36, 36)
        btn_disable_script.setToolTip(
            self.loc_manager.tr(
                "Settings.Lua.Tooltip.Disable", "Disable selected script(s)"
            )
        )

        buttons_layout.addWidget(btn_enable_script)
        buttons_layout.addSpacing(10)
        buttons_layout.addWidget(self.btn_refresh_luas)
        buttons_layout.addSpacing(10)
        buttons_layout.addWidget(btn_disable_script)
        buttons_layout.addStretch()

        manager_grid_layout.addLayout(buttons_layout, 1, 1)
        manager_grid_layout.setColumnStretch(0, 4)
        manager_grid_layout.setColumnStretch(1, 1)
        manager_grid_layout.setColumnStretch(2, 4)

        link_button_colors = {
            "color_normal": ("#8B8B8B", "#555555"),
            "color_hover": ("#E0E0E0", "#121212"),
        }
        footer_layout = QHBoxLayout()
        btn_open_scripts_folder = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.OpenScripts', 'Open Scripts Folder')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "folder.svg")),
            **link_button_colors,
        )
        btn_open_scripts_folder.setObjectName("LinkButton")
        btn_open_scripts_folder.setIconSize(QSize(20, 20))
        btn_open_scripts_folder.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.OpenScripts",
                "Open the folder where your Lua scripts are located",
            )
        )

        btn_discover_luas = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.DiscoverLua', 'Discover Luas')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "compass.svg")),
            **link_button_colors,
        )
        btn_discover_luas.setObjectName("LinkButton")
        btn_discover_luas.setIconSize(QSize(20, 20))
        btn_discover_luas.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.DiscoverLua",
                "Open the official YimMenu-Lua GitHub organization to find new scripts",
            )
        )

        footer_layout.addWidget(btn_open_scripts_folder)
        footer_layout.addStretch()
        footer_layout.addWidget(btn_discover_luas)

        lua_layout.addSpacing(15)
        lua_layout.addLayout(manager_grid_layout)
        lua_layout.addSpacing(10)
        lua_layout.addLayout(footer_layout)

        other_frame = QFrame()
        other_frame.setObjectName("CardFrame")
        other_layout = QVBoxLayout(other_frame)

        other_title = QLabel(self.loc_manager.tr("Settings.Header.Other", "Other"))
        other_title.setObjectName("SettingsTitle")

        debug_console_layout = QHBoxLayout()
        self.debug_console_label = QLabel(
            self.loc_manager.tr(
                "Settings.Other.DebugConsole", "Enable External Debug Console"
            )
        )
        self.debug_console_toggle = ToggleSwitch()
        self.debug_console_toggle.setToolTip(
            self.loc_manager.tr(
                "Settings.Other.Tooltip.Debug",
                "Show YimMenu's external console window for detailed logs and debugging",
            )
        )
        debug_console_layout.addWidget(self.debug_console_label)
        debug_console_layout.addStretch()
        debug_console_layout.addWidget(self.debug_console_toggle)

        btn_open_folder = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.OpenYimFolder', 'Open YimMenu Folder')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "folder.svg")),
            **link_button_colors,
        )
        btn_open_folder.setObjectName("LinkButton")
        btn_open_folder.setIconSize(QSize(20, 20))
        btn_open_folder.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.OpenYimFolder",
                "Open YimMenu folder (%APPDATA%/YimMenu)",
            )
        )

        btn_open_ymu_folder = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.OpenYmuFolder', 'Open YMU Folder')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "folder.svg")),
            **link_button_colors,
        )
        btn_open_ymu_folder.setObjectName("LinkButton")
        btn_open_ymu_folder.setIconSize(QSize(20, 20))
        btn_open_ymu_folder.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.OpenYmuFolder", "Open YMU folder (%APPDATA%/YMU)"
            )
        )

        btn_report_bug = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.ReportBug', 'Report a Bug')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        btn_report_bug.setObjectName("LinkButton")
        btn_report_bug.setIconSize(QSize(20, 20))
        btn_report_bug.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.ReportBug",
                "Open the bug report page on GitHub in your browser",
            )
        )

        btn_request_feature = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.RequestFeature', 'Request a Feature')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        btn_request_feature.setObjectName("LinkButton")
        btn_request_feature.setIconSize(QSize(20, 20))
        btn_request_feature.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.RequestFeature",
                "Open the feature request page on GitHub in your browser",
            )
        )
        self.btn_check_for_updates = AnimatedButton(
            self.loc_manager.tr("Settings.Btn.CheckUpdates", "Check for YMU Updates"),
            theme_manager=self.theme_manager,
        )
        other_layout.addWidget(other_title)
        other_layout.addLayout(debug_console_layout)
        other_layout.addWidget(btn_open_folder)
        other_layout.addWidget(btn_open_ymu_folder)
        other_layout.addWidget(btn_report_bug)
        other_layout.addWidget(btn_request_feature)
        other_layout.addSpacing(15)
        other_layout.addWidget(
            self.btn_check_for_updates, alignment=Qt.AlignmentFlag.AlignCenter
        )

        content_layout.addWidget(appearance_frame)
        content_layout.addWidget(lua_frame)
        content_layout.addWidget(other_frame)
        content_layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setObjectName("SettingsScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_content_widget)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll_area)

        btn_open_folder.clicked.connect(lambda: self._open_link(YIMMENU_APPDATA_DIR))
        btn_open_ymu_folder.clicked.connect(lambda: self._open_link(YMU_APPDATA_DIR))

        btn_report_bug.clicked.connect(
            lambda: self._open_link(
                "https://github.com/NiiV3AU/YMU/issues/new?template=bug_report.yml"
            )
        )
        btn_request_feature.clicked.connect(
            lambda: self._open_link(
                "https://github.com/NiiV3AU/YMU/issues/new?template=feature_request.yml"
            )
        )
        self.btn_check_for_updates.clicked.connect(self._handle_check_for_updates)
        self.auto_reload_toggle.toggled.connect(self._on_auto_reload_toggled)
        self.debug_console_toggle.toggled.connect(self._on_debug_console_toggled)
        self.auto_reload_toggle.focusChanged.connect(
            lambda has_focus: self._on_toggle_focus_changed(
                self.auto_reload_label, has_focus
            )
        )
        self.debug_console_toggle.focusChanged.connect(
            lambda has_focus: self._on_toggle_focus_changed(
                self.debug_console_label, has_focus
            )
        )
        btn_enable_script.clicked.connect(self._enable_selected_scripts)
        btn_disable_script.clicked.connect(self._disable_selected_scripts)
        btn_open_scripts_folder.clicked.connect(
            lambda: self._open_link(YIMMENU_SCRIPTS_DIR)
        )
        self.btn_refresh_luas.clicked.connect(self._refresh_lua_lists)
        btn_discover_luas.clicked.connect(
            lambda: self._open_link("https://github.com/orgs/YimMenu-Lua/repositories")
        )

        self._refresh_lua_lists()
        self._load_initial_settings()

    def _open_link(self, path_or_url: str):
        """Opens a local folder path or a web URL."""
        if os.path.isdir(path_or_url):
            os.startfile(path_or_url)
        else:
            webbrowser.open(path_or_url)

    def _load_initial_settings(self):
        """Loads settings from the file and sets the UI state."""
        is_enabled = settings_manager.get_setting(
            "lua.enable_auto_reload_changed_scripts", default=False
        )
        self.auto_reload_toggle.setChecked(bool(is_enabled))

        is_debug_enabled = settings_manager.get_setting(
            "debug.external_console", default=False
        )
        self.debug_console_toggle.setChecked(bool(is_debug_enabled))

    def _on_auto_reload_toggled(self, checked: bool):
        """Called when the user clicks the auto-reload toggle."""
        settings_manager.set_setting("lua.enable_auto_reload_changed_scripts", checked)

    def _on_debug_console_toggled(self, checked: bool):
        """Called when the user clicks the debug console toggle."""
        settings_manager.set_setting("debug.external_console", checked)

    def _on_toggle_focus_changed(self, label: QLabel, has_focus: bool):
        """Updates the style of a label based on the focus state of its toggle."""
        if has_focus:
            if self.theme_manager.current_theme == "dark":
                label.setStyleSheet("text-decoration: underline; color: #FFFFFF;")
            else:
                label.setStyleSheet("text-decoration: underline; color: #000000;")
        else:
            label.setStyleSheet("")

    def _refresh_lua_lists(self):
        """Fetches script lists, updates UI, and plays a brief feedback animation."""

        self.btn_refresh_luas.start_animation(duration=500)
        self.btn_refresh_luas.setEnabled(False)

        self.disabled_scripts_list.clear()
        self.enabled_scripts_list.clear()

        scripts = lua_manager.get_scripts()
        self.disabled_scripts_list.addItems(scripts["disabled"])
        self.enabled_scripts_list.addItems(scripts["enabled"])

        item_count = max(
            self.disabled_scripts_list.count(), self.enabled_scripts_list.count()
        )
        height = 100
        if item_count > 0:
            reference_list = (
                self.disabled_scripts_list
                if self.disabled_scripts_list.count() > 0
                else self.enabled_scripts_list
            )
            row_height = reference_list.sizeHintForRow(0)
            if row_height > 0:
                height = item_count * row_height + 10
        max_height = 200
        final_height = min(height, max_height)
        self.disabled_scripts_list.setFixedHeight(final_height)
        self.enabled_scripts_list.setFixedHeight(final_height)

        QTimer.singleShot(500, lambda: self.btn_refresh_luas.setEnabled(True))

    def _enable_selected_scripts(self):
        """Moves selected scripts from the disabled list to the enabled list."""
        selected_items = self.disabled_scripts_list.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            lua_manager.enable_script(item.text())

        self._refresh_lua_lists()

    def _disable_selected_scripts(self):
        """Moves selected scripts from the enabled list to the disabled list."""
        selected_items = self.enabled_scripts_list.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            lua_manager.disable_script(item.text())

        self._refresh_lua_lists()

    def _handle_check_for_updates(self):
        """Starts the background task to check for YMU updates."""
        if self._is_task_running:
            return

        self._is_task_running = True
        self.btn_check_for_updates.setEnabled(False)
        self.btn_check_for_updates.start_animation()

        self.worker_manager.run_task(
            target=update_checker.check_for_updates,
            on_finished=self._on_update_check_finished,
            on_error=self._on_task_error,
        )

    def _on_update_check_finished(self, result):
        self.btn_check_for_updates.stop_animation()
        self.btn_check_for_updates.setEnabled(True)
        self._is_task_running = False

        status, data = result

        if status == update_checker.STATUS_UP_TO_DATE:
            cast(MainWindow, self.window()).notification_manager.show(
                self.loc_manager.tr("Settings.Update.Title", "YMU Updater"),
                self.loc_manager.tr(
                    "Settings.Update.UpToDate", "Your YMU is already up-to-date."
                ),
                icon_type="success",
            )
            self.btn_check_for_updates.setText(
                self.loc_manager.tr("Settings.Btn.UpToDate", "YMU is up-to-date")
            )
            QTimer.singleShot(
                5000,
                lambda: self.btn_check_for_updates.setText(
                    self.loc_manager.tr(
                        "Settings.Btn.CheckUpdates", "Check for YMU Updates"
                    )
                ),
            )

        elif status == update_checker.STATUS_UPDATE_AVAILABLE:
            title = self.loc_manager.tr(
                "Settings.Update.AvailableTitle", "Update Available"
            )
            msg = self.loc_manager.tr(
                "Settings.Update.AvailableMsg", "Update {0} is available!"
            ).format(data)
            prompt = self.loc_manager.tr(
                "Settings.Update.Prompt", "Do you want to download and install it now?"
            )

            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(title)
            msg_box.setText(f"{msg}\n\n{prompt}")
            msg_box.setIcon(QMessageBox.Icon.Question)

            btn_yes = msg_box.addButton(
                self.loc_manager.tr("Common.Yes", "Yes"), QMessageBox.ButtonRole.YesRole
            )
            btn_no = msg_box.addButton(
                self.loc_manager.tr("Common.No", "No"), QMessageBox.ButtonRole.NoRole
            )

            msg_box.exec()

            if msg_box.clickedButton() == btn_yes:
                self._start_updater_download()

        elif status == update_checker.STATUS_AHEAD:
            cast(MainWindow, self.window()).notification_manager.show(
                self.loc_manager.tr("Settings.Update.CheckTitle", "YMU Update Check"),
                self.loc_manager.tr(
                    "Settings.Update.Ahead", "You are running a newer version..."
                ),
                icon_type="info",
            )

        else:
            cast(MainWindow, self.window()).notification_manager.show(
                self.loc_manager.tr("Settings.Update.ErrorTitle", "Update Error"),
                f"{self.loc_manager.tr('Common.Error')}: {data}",
                icon_type="error",
            )

    def _start_updater_download(self):
        """Starts the background task to download and run the updater."""
        if self._is_task_running:
            return

        self._is_task_running = True
        self.btn_check_for_updates.setEnabled(False)
        self.btn_check_for_updates.setText(
            self.loc_manager.tr("Settings.Btn.Downloading", "Downloading Updater...")
        )

        self.worker_manager.run_task(
            target=update_checker.download_and_launch_updater,
            on_finished=self._on_updater_download_finished,
            on_error=self._on_task_error,
            on_progress=self._update_updater_progress,
        )

    def _update_updater_progress(self, percentage: int):
        """Updates the button's progress fill."""
        self.btn_check_for_updates.set_progress(percentage / 100.0)

    def _on_updater_download_finished(self, result):
        success, message = result
        if success:
            logger.info("Updater launched successfully. Exiting.")
            app = QApplication.instance()
            if app:
                app.quit()
        else:
            self.btn_check_for_updates.reset_progress()
            self.btn_check_for_updates.setEnabled(True)
            self._is_task_running = False
            err_title = self.loc_manager.tr(
                "Settings.Update.ErrorTitle", "Update Error"
            )
            cast(MainWindow, self.window()).notification_manager.show(
                err_title,
                message,
                icon_type="error",
            )

    def _on_fetch_lang_clicked(self):
        """Start the manual download and animation."""
        self.btn_update_lang.setEnabled(False)
        self.btn_update_lang.start_animation(duration=500)
        self.loc_manager.fetch_updates()

    def _on_lang_fetch_finished(
        self, success: bool, message: str, restart_needed: bool
    ):
        """Callback from the manager."""
        self.btn_update_lang.stop_animation()
        self.btn_update_lang.setEnabled(True)
        if success:
            title = self.loc_manager.tr("Common.Info", "Information")
            if restart_needed:
                msg = self.loc_manager.tr(
                    "Settings.Notify.LangUpdated",
                    "Translations were successfully downloaded.\nRestart YMU to see the updated Language List in Settings.",
                )
                action_text = self.loc_manager.tr("Common.Restart", "Restart Now")
                cast(MainWindow, self.window()).notification_manager.show(
                    title,
                    msg,
                    icon_type="success",
                    duration=10000,
                    action_text=action_text,
                    action_callback=restart_application,
                )
            else:
                cast(MainWindow, self.window()).notification_manager.show(
                    title, message, icon_type="success"
                )
        else:
            cast(MainWindow, self.window()).notification_manager.show(
                self.loc_manager.tr("Common.Error", "Error"), message, icon_type="error"
            )

    def _commit_language_change(self):
        index = self.lang_combo.currentIndex()
        if index < 0:
            return
        new_locale_code = self.lang_combo.itemData(index)

        if new_locale_code == self.loc_manager.active_locale:
            return

        self.loc_manager.set_locale(new_locale_code)

        msg = self.loc_manager.tr(
            "Settings.Notify.RestartRequired",
            "Please restart YMU to apply the new language.",
        )

        title = self.loc_manager.tr("Settings.Notify.LangTitle", "Language Changed")
        action = self.loc_manager.tr("Common.Restart", "Restart Now")

        cast(MainWindow, self.window()).notification_manager.show(
            title,
            msg,
            icon_type="info",
            duration=10000,
            action_text=action,
            action_callback=restart_application,
        )

    def _on_task_error(self, error: Exception):
        """A generic callback to handle any errors from the worker tasks."""
        self.btn_check_for_updates.stop_animation()
        self.btn_check_for_updates.reset_progress()
        self.btn_check_for_updates.setText(
            self.loc_manager.tr("Settings.Btn.CheckUpdates", "Check for YMU Updates")
        )
        self.btn_check_for_updates.setEnabled(True)
        self._is_task_running = False

        logger.error(f"A settings page task failed in the background: {error}")
        cast(MainWindow, self.window()).notification_manager.show(
            self.loc_manager.tr("Common.Error", "Error"),
            f"{self.loc_manager.tr('Common.UnexpectedError', 'An unexpected error occurred')}: {error}",
            icon_type="error",
        )


def cleanup_updater():
    updater_path = os.path.join(YMU_APPDATA_DIR, "ymu_self_updater.exe")
    if os.path.exists(updater_path):
        try:
            os.remove(updater_path)
            logger.info(f"Removed old updater: {updater_path}")
        except OSError:
            pass


if __name__ == "__main__":
    try:
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        old_ymu_path = os.path.join(script_dir, "ymu")
        if os.path.isdir(old_ymu_path):
            logger.info(
                f"Legacy './ymu' folder found in {script_dir}. Starting cleanup..."
            )
            import shutil

            shutil.rmtree(old_ymu_path)
            logger.info("Legacy folder successfully removed.")
    except Exception as e:
        logger.error(f"Failed to delete the legacy './ymu' folder: {e}")

    app = QApplication(sys.argv)
    cleanup_updater()
    worker_manager = WorkerManager()
    focus_filter = FocusStealingFilter(app)
    app.installEventFilter(focus_filter)
    font_dir = resource_path(os.path.join("assets", "fonts"))
    if os.path.exists(font_dir):
        for font_file in os.listdir(font_dir):
            if font_file.endswith((".ttf")):
                QFontDatabase.addApplicationFont(os.path.join(font_dir, font_file))
    asset_path = resource_path(os.path.join("assets", "icons")).replace("\\", "/")
    theme_manager = ThemeManager(app, STYLESHEET, STYLESHEET_LIGHT, asset_path)
    theme_manager.apply_current_theme()
    loc_manager = LocalizationManager()
    window = MainWindow(
        theme_manager=theme_manager,
        worker_manager=worker_manager,
        loc_manager=loc_manager,
    )
    app.styleHints().colorSchemeChanged.connect(lambda: update_app_icon(app, window))
    update_app_icon(app, window)
    window.show()
    QTimer.singleShot(100, window.show_when_ready)
    exit_code = app.exec()
    worker_manager.cleanup()
    sys.exit(exit_code)
