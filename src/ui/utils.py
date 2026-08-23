# utils.py - UI helper functions, icon management, and application lifecycle.
import logging
import os
import subprocess
import sys

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

from paths import resource_path

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


def restart_application():
    """Restarts the application.

    Under Nuitka onefile, sys.argv[0] is the real EXE while sys.executable is
    the temporary bootstrap interpreter, so the relaunch target is picked
    accordingly.
    """
    logger.info("Restart requested via UI. Relaunching...")
    old_pid = os.getpid()

    for widget in QApplication.topLevelWidgets():
        widget.hide()

    if "__compiled__" in globals() or getattr(sys, "frozen", False):
        executable = os.path.abspath(sys.argv[0])
        args = [executable, "--wait-for-pid", str(old_pid)]
    else:
        executable = sys.executable
        args = [sys.executable, sys.argv[0], "--wait-for-pid", str(old_pid)]

    if IS_WINDOWS:
        try:
            logger.info(
                f"Restarting executable at: {executable} (waiting for PID {old_pid})"
            )
            creationflags = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
            subprocess.Popen(args, creationflags=creationflags)
        except OSError as e:
            logger.error(f"Failed to restart via subprocess.Popen: {e}")
    else:
        subprocess.Popen(args)

    QApplication.quit()
    sys.exit(0)


def restart_as_admin():
    """Relaunches YMU elevated via ShellExecute 'runas', which triggers the UAC prompt."""
    import ctypes

    logger.info("Requesting restart with Admin privileges...")
    old_pid = os.getpid()

    for widget in QApplication.topLevelWidgets():
        widget.hide()

    if "__compiled__" in globals() or getattr(sys, "frozen", False):
        executable = os.path.abspath(sys.argv[0])
        params = f"--wait-for-pid {old_pid}"
    else:
        executable = sys.executable
        clean_script = sys.argv[0]
        params = f'"{clean_script}" --wait-for-pid {old_pid}'
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
    An event filter that clears focus on mouse clicks, but ignores clicks
    on an AnimatedButton that is currently animating to prevent race conditions.
    """

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            if getattr(watched, "_is_animating", False):
                pass
            else:
                focused_widget = QApplication.focusWidget()
                if focused_widget:
                    focused_widget.clearFocus()

        return super().eventFilter(watched, event)
