# utils.py - UI helper functions, icon management, and application lifecycle.
import logging
import os
import subprocess
import sys

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget

from core.paths import resource_path

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"

ICON_LIGHT_PATH = resource_path(os.path.join("assets", "icons", "logo_light.ico"))
ICON_DARK_PATH = resource_path(os.path.join("assets", "icons", "logo_dark.ico"))


def update_app_icon(app: QApplication, window):
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

    for widget in QApplication.topLevelWidgets():
        widget.hide()

    is_compiled = (
        "__compiled__" in globals()
        or getattr(sys, "frozen", False)
        or sys.argv[0].lower().endswith(".exe")
    )

    clean_env = _strip_nuitka_env()

    if is_compiled:
        executable = os.path.abspath(sys.argv[0])
        args = [executable, "--wait-for-pid", str(old_pid)]
    else:
        executable = sys.executable
        script_path = os.path.abspath(sys.argv[0])
        args = [sys.executable, script_path, "--wait-for-pid", str(old_pid)]

    if IS_WINDOWS:
        try:
            logger.info(
                f"Restarting executable at: {executable} (waiting for PID {old_pid})"
            )
            # In compiled GUI mode, detach from parent; in dev (python.exe) mode, keep console attached
            creationflags = (
                (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
                if is_compiled
                else subprocess.CREATE_NEW_PROCESS_GROUP
            )
            subprocess.Popen(args, creationflags=creationflags, env=clean_env)
        except OSError as e:
            logger.error(f"Failed to restart via subprocess.Popen: {e}")
    else:
        subprocess.Popen(args, env=clean_env)

    QApplication.quit()
    sys.exit(0)


def restart_as_admin():
    """Relaunches YMU elevated via ShellExecute 'runas', which triggers the UAC prompt."""
    import ctypes

    logger.info("Requesting restart with Admin privileges...")
    old_pid = os.getpid()

    for widget in QApplication.topLevelWidgets():
        widget.hide()

    is_compiled = (
        "__compiled__" in globals()
        or getattr(sys, "frozen", False)
        or sys.argv[0].lower().endswith(".exe")
    )

    _strip_nuitka_env()

    if is_compiled:
        executable = os.path.abspath(sys.argv[0])
        params = f"--wait-for-pid {old_pid}"
    else:
        executable = sys.executable
        clean_script = os.path.abspath(sys.argv[0])
        params = f'\"{clean_script}\" --wait-for-pid {old_pid}'

    logger.info(f"Target executable for Admin restart: {executable}")
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, params, None, 1
        )
        logger.info(f"ShellExecute returned code: {result}")
        if result > 32:
            logger.info("UAC prompt triggered successfully. Exiting.")
            QApplication.quit()
            sys.exit(0)
        else:
            logger.error(f"Failed to start as Admin. Error code: {result}")
            for widget in QApplication.topLevelWidgets():
                widget.show()

    except (OSError, AttributeError) as e:
        logger.error(f"Exception during restart_as_admin: {e}")
        for widget in QApplication.topLevelWidgets():
            widget.show()


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
        etype = event.type()
        if etype == QEvent.Type.KeyPress:
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
            and hasattr(event, "reason")
            and event.reason() == Qt.FocusReason.ActiveWindowFocusReason
            and not self._keyboard_nav_active
        ):
            watched.clearFocus()
            return True

        return super().eventFilter(watched, event)


def play_success_sound():
    """Plays an audible confirmation chime if running on Windows."""
    if not IS_WINDOWS:
        return
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except (RuntimeError, OSError) as e:
        logger.debug(f"Could not play success sound: {e}")
