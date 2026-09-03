# main.py - Application entry point and runtime initialization.
import io
import logging
import os
import platform
import sys
from logging.handlers import RotatingFileHandler

try:
    import win32gui

    IS_WINDOWS = True
except (ImportError, AttributeError):
    IS_WINDOWS = False

# Single-instance guard via Windows Named Mutex and relaunch synchronization.
if IS_WINDOWS:
    import ctypes

    ctypes.windll.kernel32.OpenProcess.argtypes = [
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint32,
    ]
    ctypes.windll.kernel32.OpenProcess.restype = ctypes.c_void_p
    ctypes.windll.kernel32.WaitForSingleObject.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    ctypes.windll.kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    ctypes.windll.kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    ctypes.windll.kernel32.CloseHandle.restype = ctypes.c_int
    ctypes.windll.kernel32.CreateMutexW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_wchar_p,
    ]
    ctypes.windll.kernel32.CreateMutexW.restype = ctypes.c_void_p

    # If launched as part of a restart, wait for the old process to fully exit first.
    is_restart = "--wait-for-pid" in sys.argv
    if is_restart:
        try:
            pid_idx = sys.argv.index("--wait-for-pid") + 1
            if pid_idx < len(sys.argv):
                old_pid = int(sys.argv[pid_idx])
                import time

                PROCESS_SYNCHRONIZE = 0x00100000
                h_proc = ctypes.windll.kernel32.OpenProcess(
                    PROCESS_SYNCHRONIZE, False, old_pid
                )
                if h_proc:
                    # Wait up to 3000ms for old process to exit
                    ctypes.windll.kernel32.WaitForSingleObject(h_proc, 3000)
                    ctypes.windll.kernel32.CloseHandle(h_proc)
                else:
                    time.sleep(0.05)
        except (ValueError, OSError, AttributeError) as e:
            logging.getLogger(__name__).debug(f"Error waiting for old PID: {e}")

    WINDOW_TITLE = "YimMenuUpdater | NV3"
    MUTEX_NAME = "Local\\YMU_SingleInstance_Mutex"
    _single_instance_mutex = None
    try:
        ERROR_ALREADY_EXISTS = 183
        max_attempts = 20 if is_restart else 1
        for attempt in range(max_attempts):
            _single_instance_mutex = ctypes.windll.kernel32.CreateMutexW(
                None, False, MUTEX_NAME
            )
            if ctypes.windll.kernel32.GetLastError() != ERROR_ALREADY_EXISTS:
                break
            if is_restart and attempt < max_attempts - 1:
                import time

                time.sleep(0.05)
        else:
            hwnd = win32gui.FindWindow(None, WINDOW_TITLE)
            if hwnd != 0:
                win32gui.ShowWindow(hwnd, 9)
                win32gui.SetForegroundWindow(hwnd)
            sys.exit(0)
    except (OSError, AttributeError) as e:
        logging.getLogger(__name__).error(f"Error during instance check: {e}")

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from core import process_manager
from core.paths import (
    LOCAL_VERSION,
    YMU_APPDATA_DIR,
    YMU_LOG_FILE_PATH,
    resource_path,
)
from core.worker_manager import WorkerManager
from ui.i18n.localization_manager import LocalizationManager
from ui.main_window import MainWindow
from ui.styles.theme_manager import ThemeManager
from ui.utils import (
    FocusStealingFilter,
    create_colored_icon,
    restart_application,
    restart_as_admin,
    update_app_icon,
)

# Re-exports for backward compatibility
__all__ = [
    "FocusStealingFilter",
    "MainWindow",
    "cleanup_updater",
    "create_colored_icon",
    "main",
    "restart_application",
    "restart_as_admin",
    "update_app_icon",
]

log_formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)-8s] [%(name)-24s] %(message)s", datefmt="%H:%M:%S"
)

stream_handler = logging.StreamHandler()
# The file handler is utf-8; make the console handler tolerate non-ASCII too
# (e.g. a Cyrillic user name in a logged path) instead of raising on a cp1252
# console. Guarded because the release build has no console (stream is None).
if isinstance(stream_handler.stream, io.TextIOWrapper):
    stream_handler.stream.reconfigure(encoding="utf-8", errors="backslashreplace")
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

ymu_version = LOCAL_VERSION

system_info = {
    "YMU Version": ymu_version,
    "Operating System": f"{platform.system()} {platform.release()}",
    "Architecture": platform.architecture()[0],
    "Administrator": process_manager.is_admin(),
    "Working Directory": os.getcwd(),
}

logger.info("--- Initializing YMU ---")
for key, value in system_info.items():
    logger.info(f"{key}: {value}")
logger.info("--------------------------")


def cleanup_updater():
    updater_path = os.path.join(YMU_APPDATA_DIR, "ymu_self_updater.exe")
    if os.path.exists(updater_path):
        try:
            os.remove(updater_path)
            logger.info(f"Removed old updater: {updater_path}")
        except OSError as e:
            logger.debug(f"Could not remove old updater {updater_path}: {e}")


def main():
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
    except OSError as e:
        logger.error(f"Failed to delete the legacy './ymu' folder: {e}")

    app = QApplication(sys.argv)
    cleanup_updater()
    worker_manager = WorkerManager()
    focus_filter = FocusStealingFilter(app)
    app.installEventFilter(focus_filter)
    font_dir = resource_path(os.path.join("assets", "fonts"))
    if os.path.exists(font_dir):
        for font_file in os.listdir(font_dir):
            if font_file.endswith(".ttf"):
                QFontDatabase.addApplicationFont(os.path.join(font_dir, font_file))
    asset_path = resource_path(os.path.join("assets", "icons")).replace("\\", "/")
    theme_manager = ThemeManager(app, asset_path=asset_path)
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


if __name__ == "__main__":
    main()
