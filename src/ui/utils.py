# utils.py - UI helper functions, icon management, and application lifecycle.
import logging
import os
import subprocess
import sys

from PySide6.QtCore import QEvent, QObject, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFocusEvent,
    QIcon,
    QKeyEvent,
    QPainter,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QMainWindow,
    QWidget,
)

from core.paths import is_compiled, resource_path

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"

ICON_LIGHT_PATH = resource_path(os.path.join("assets", "icons", "logo_light.ico"))
ICON_DARK_PATH = resource_path(os.path.join("assets", "icons", "logo_dark.ico"))
ICON_SVG_PATH = resource_path(os.path.join("assets", "icons", "ymu.svg"))


def is_windows_dark_theme() -> bool:
    """Detects whether the Windows system theme (Taskbar/Shell) is dark.

    On Windows 10/11, 'SystemUsesLightTheme' in HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize
    governs the taskbar, start menu, and shell appearance (0 = Dark, 1 = Light).
    If unavailable or on non-Windows platforms, falls back to QApplication.styleHints().colorScheme().
    """
    if IS_WINDOWS:
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                system_light, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
                return int(system_light) == 0
        except (OSError, AttributeError, TypeError, ValueError):
            pass

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app.styleHints().colorScheme() != Qt.ColorScheme.Light
    return True


def update_app_icon(
    app: QApplication,
    window: QWidget | None = None,
    theme: str | None = None,
) -> None:
    """Sets the application and window icons.

    The taskbar icon strictly follows the Windows system theme (Taskbar/Shell),
    as the taskbar is an OS component unaffected by the in-app Qt theme.
    The window titlebar icon (<=24px) reflects the active window/in-app theme when specified.
    """
    # 1. Taskbar icon: strictly determined by the Windows system theme
    windows_is_dark = is_windows_dark_theme()
    if windows_is_dark:
        logger.info("Windows dark theme active. Applying dark theme icon for taskbar.")
        taskbar_icon_path = ICON_DARK_PATH
    else:
        logger.info(
            "Windows light theme active. Applying light theme icon for taskbar."
        )
        taskbar_icon_path = ICON_LIGHT_PATH

    if not os.path.exists(taskbar_icon_path):
        taskbar_icon_path = resource_path(os.path.join("assets", "icons", "ymu.ico"))

    taskbar_icon = (
        QIcon(taskbar_icon_path) if os.path.exists(taskbar_icon_path) else QIcon()
    )
    app.setWindowIcon(taskbar_icon)

    # 2. Window icon: titlebar (<=24px) reflects the in-app theme if provided,
    # while taskbar/large sizes (>=32px) strictly match the Windows system theme.
    if theme is not None:
        titlebar_is_dark = theme.lower() != "light"
        titlebar_icon_path = ICON_DARK_PATH if titlebar_is_dark else ICON_LIGHT_PATH
        if not os.path.exists(titlebar_icon_path):
            titlebar_icon_path = taskbar_icon_path
    else:
        titlebar_icon_path = taskbar_icon_path

    titlebar_icon = (
        QIcon(titlebar_icon_path)
        if os.path.exists(titlebar_icon_path)
        else taskbar_icon
    )

    combined_icon = QIcon()
    for sz in (16, 20, 24):
        pix = titlebar_icon.pixmap(sz, sz)
        if not pix.isNull():
            combined_icon.addPixmap(pix)
    for sz in (32, 48, 64, 128, 256):
        pix = taskbar_icon.pixmap(sz, sz)
        if not pix.isNull():
            combined_icon.addPixmap(pix)

    final_window_icon = combined_icon if not combined_icon.isNull() else taskbar_icon

    if window is not None:
        window.setWindowIcon(final_window_icon)
    for top_widget in app.topLevelWidgets():
        if top_widget is not window:
            top_widget.setWindowIcon(final_window_icon)


def create_colored_icon(
    icon_path: str, color: QColor, target_size: QSize | None = None
) -> QIcon:
    """Loads an SVG file, recolors it with antialiasing and DPR awareness, and returns it as a QIcon."""
    renderer = QSvgRenderer(icon_path)
    if not renderer.isValid():
        return QIcon()

    base_size = target_size if target_size is not None else renderer.defaultSize()
    icon = QIcon()
    for dpr in (1.0, 2.0):
        scaled_size = QSize(int(base_size.width() * dpr), int(base_size.height() * dpr))
        pixmap = QPixmap(scaled_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        pixmap.setDevicePixelRatio(dpr)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, base_size.width(), base_size.height()))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(QRectF(0, 0, base_size.width(), base_size.height()), color)
        painter.end()
        icon.addPixmap(pixmap)

    return icon


def create_colored_pixmap(
    icon_path: str, color: QColor, target_size: QSize | None = None, dpr: float = 1.0
) -> QPixmap:
    """Loads an SVG file, recolors it with the specified color, and returns it as a QPixmap."""
    renderer = QSvgRenderer(icon_path)
    if not renderer.isValid():
        return QPixmap()

    base_size = target_size if target_size is not None else renderer.defaultSize()
    scaled_size = QSize(int(base_size.width() * dpr), int(base_size.height() * dpr))
    pixmap = QPixmap(scaled_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    if dpr != 1.0:
        pixmap.setDevicePixelRatio(dpr)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, base_size.width(), base_size.height()))

    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(QRectF(0, 0, base_size.width(), base_size.height()), color)
    painter.end()

    return pixmap


def adjust_button_to_text(
    button: QAbstractButton,
    min_width: int = 0,
    padding: int = 40,
) -> int:
    """Dynamically sizes a button to fit its current text without clipping.

    The padding argument must cover whatever the stylesheet adds around the
    label: dark.qss sets `padding: 10px 18px` plus a 2px transparent border on
    QPushButton, so 2 * (18 + 2) = 40. A hard-coded width clips the moment a
    translation is longer than the string the width was chosen for.
    """
    button.ensurePolished()
    button.adjustSize()
    needed = button.sizeHint().width()
    if needed > button.width() or min_width > button.width():
        button.setFixedWidth(max(min_width, needed))
    return button.width()


def adjust_combobox_to_contents(
    combo: QComboBox,
    min_width: int = 150,
    max_width: int = 340,
    padding: int = 58,
) -> int:
    """Dynamically sizes a QComboBox to snugly fit its current items without clipping."""
    combo.ensurePolished()
    fm = combo.fontMetrics()
    max_text_width = max(
        (fm.horizontalAdvance(combo.itemText(i)) for i in range(combo.count())),
        default=0,
    )
    target_width = max(min_width, min(max_width, max_text_width + padding))
    combo.setFixedWidth(target_width)
    return target_width


def _strip_nuitka_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """Removes Nuitka onefile environment variables to ensure child processes start a clean bootstrap."""
    target = env if env is not None else os.environ.copy()
    for key in list(target.keys()):
        if key.startswith("NUITKA_"):
            target.pop(key, None)
    for key in list(os.environ.keys()):
        if key.startswith("NUITKA_"):
            os.environ.pop(key, None)
    return target


def _get_main_window() -> QWidget | None:
    """Finds and returns the application's main window if present."""
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QMainWindow) or widget.__class__.__name__ == "MainWindow":
            return widget
    for widget in QApplication.topLevelWidgets():
        if widget.isWindow() and not widget.parent():
            return widget
    return None


def restart_application():
    """Restarts the application.

    Under Nuitka onefile, sys.argv[0] is the real EXE while sys.executable is
    the temporary bootstrap interpreter, so the relaunch target is picked
    accordingly. Nuitka onefile environment variables are stripped so the
    restarted instance bootstraps cleanly into a new payload directory instead
    of inheriting the expiring one.
    """
    logger.info("Restart requested via UI. Relaunching...")
    old_pid = os.getpid()

    is_compiled_build = is_compiled()

    clean_env = _strip_nuitka_env()

    if is_compiled_build:
        executable = os.path.abspath(sys.argv[0])
        args = [executable, "--wait-for-pid", str(old_pid)]
    else:
        executable = sys.executable
        script_path = os.path.abspath(sys.argv[0])
        args = [sys.executable, script_path, "--wait-for-pid", str(old_pid)]

    try:
        if IS_WINDOWS:
            logger.info(
                f"Restarting executable at: {executable} (waiting for PID {old_pid})"
            )
            # In compiled GUI mode, detach from parent; in dev (python.exe) mode, keep console attached
            creationflags = (
                (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
                if is_compiled_build
                else subprocess.CREATE_NEW_PROCESS_GROUP
            )
            subprocess.Popen(args, creationflags=creationflags, env=clean_env)
        else:
            subprocess.Popen(args, env=clean_env)
    except OSError as e:
        logger.error(f"Failed to restart via subprocess.Popen: {e}")
        main_win = _get_main_window()
        if main_win:
            main_win.show()
            main_win.activateWindow()
            main_win.raise_()
            from PySide6.QtWidgets import QMessageBox

            from ui.i18n.localization_manager import get_localization_manager

            loc = getattr(main_win, "loc_manager", None) or get_localization_manager()
            title = loc.tr("Common.Notify.RestartFailedTitle", "Restart Failed")
            msg = loc.tr(
                "Common.Notify.RestartFailedMsg",
                "Failed to restart application:\n{0}",
            ).format(e)
            QMessageBox.warning(main_win, title, msg)
        return

    for widget in QApplication.topLevelWidgets():
        widget.hide()
    QApplication.quit()
    sys.exit(0)


def restart_as_admin():
    """Relaunches YMU elevated via ShellExecute 'runas', which triggers the UAC prompt."""
    import ctypes
    from ctypes import wintypes

    logger.info("Requesting restart with Admin privileges...")
    old_pid = os.getpid()

    main_window = _get_main_window()
    if main_window:
        main_window.hide()

    is_compiled_build = is_compiled()

    _strip_nuitka_env()

    if is_compiled_build:
        executable = os.path.abspath(sys.argv[0])
        params = f"--wait-for-pid {old_pid}"
    else:
        executable = sys.executable
        clean_script = os.path.abspath(sys.argv[0])
        params = f'"{clean_script}" --wait-for-pid {old_pid}'

    logger.info(f"Target executable for Admin restart: {executable}")
    try:
        shell32 = ctypes.windll.shell32
        shell32.ShellExecuteW.argtypes = [
            wintypes.HWND,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            ctypes.c_int,
        ]
        shell32.ShellExecuteW.restype = wintypes.HINSTANCE

        result = shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
        res_code = int(result) if result else 0
        logger.info(f"ShellExecute returned code: {res_code}")
        if res_code > 32:
            logger.info("UAC prompt triggered successfully. Exiting.")
            QApplication.quit()
            sys.exit(0)
        else:
            logger.error(f"Failed to start as Admin. Error code: {res_code}")
            if main_window:
                main_window.show()
                main_window.activateWindow()
                main_window.raise_()

    except (OSError, AttributeError) as e:
        logger.error(f"Exception during restart_as_admin: {e}")
        if main_window:
            main_window.show()
            main_window.activateWindow()
            main_window.raise_()


class FocusStealingFilter(QObject):
    """
    An event filter that manages keyboard vs mouse navigation focus:
    - Clears focus on mouse clicks, unless clicking an animating button.
    - Tracks keyboard navigation (Tab/Backtab).
    - Prevents Qt from artificially auto-focusing the first child widget upon
      window restore or activation when the user was not using keyboard navigation.
    """

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._keyboard_nav_active = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        try:
            etype = event.type()
            if etype == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
                if event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                    self._keyboard_nav_active = True
            elif etype == QEvent.Type.MouseButtonPress:
                self._keyboard_nav_active = False
                if not getattr(watched, "_is_animating", False):
                    focused_widget = QApplication.focusWidget()
                    if focused_widget:
                        focused_widget.clearFocus()
            elif (
                etype == QEvent.Type.FocusIn
                and isinstance(watched, QWidget)
                and isinstance(event, QFocusEvent)
                and event.reason() == Qt.FocusReason.ActiveWindowFocusReason
                and not self._keyboard_nav_active
            ):
                watched.clearFocus()
                return True

            return super().eventFilter(watched, event)
        except RuntimeError:
            return False


def play_success_sound():
    """Plays an audible confirmation chime if running on Windows."""
    if not IS_WINDOWS:
        return
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except (RuntimeError, OSError) as e:
        logger.debug(f"Could not play success sound: {e}")
