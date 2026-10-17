# main.py - Application entry point and runtime initialization.
import io
import logging
import os
import platform
import sys
import time
from logging.handlers import RotatingFileHandler
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from core import process_manager
from core.paths import (
    LOCAL_VERSION,
    WINDOW_TITLE,
    YMU_APPDATA_DIR,
    YMU_LOG_FILE_PATH,
    cleanup_old_runtime_dirs,
    is_compiled,
    migrate_legacy_dll_dir,
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

IS_WINDOWS = sys.platform == "win32"

# Re-exports for backward compatibility
__all__ = [
    "FocusStealingFilter",
    "MainWindow",
    "cleanup_updater",
    "create_colored_icon",
    "main",
    "restart_application",
    "restart_as_admin",
    "setup_logging",
    "update_app_icon",
]

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configures application root logger with console and rotating file handlers.
    Safe to call multiple times (idempotent). Does not run at module import time.
    """
    root_logger = logging.getLogger()
    if any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        return

    log_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] [%(name)-28s] %(message)s",
        datefmt="%H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    # The file handler is utf-8; make the console handler tolerate non-ASCII too
    # (e.g. a Cyrillic user name in a logged path) instead of raising on a cp1252
    # console. Guarded because the release build has no console (stream is None).
    if isinstance(stream_handler.stream, io.TextIOWrapper):
        stream_handler.stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    stream_handler.setFormatter(log_formatter)

    file_handler = None
    try:
        os.makedirs(os.path.dirname(YMU_LOG_FILE_PATH), exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=YMU_LOG_FILE_PATH,
            maxBytes=1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(log_formatter)
    except OSError:
        pass

    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(stream_handler)
    if file_handler:
        root_logger.addHandler(file_handler)
    else:
        logger.warning(
            "Could not initialize file log handler; running with console logging only."
        )


def _acquire_single_instance() -> Any:
    """Ensures only a single instance of YMU runs.
    If another instance is active, raises existing window to foreground and exits.
    If restarting, synchronously waits for the previous process to exit first.
    Returns the mutex handle (or None on non-Windows) to keep the lock held.
    """
    if not IS_WINDOWS:
        return None

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    kernel32.OpenProcess.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel32.OpenProcess.restype = wintypes.HANDLE

    kernel32.WaitForSingleObject.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
    ]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD

    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    kernel32.CreateMutexW.argtypes = [
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    kernel32.CreateMutexW.restype = wintypes.HANDLE

    kernel32.GetLastError.argtypes = []
    kernel32.GetLastError.restype = wintypes.DWORD

    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND

    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL

    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL

    user32.MessageBoxW.argtypes = [
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.UINT,
    ]
    user32.MessageBoxW.restype = ctypes.c_int

    # If launched as part of a restart, wait for the old process to fully exit first.
    is_restart = "--wait-for-pid" in sys.argv
    if is_restart:
        try:
            pid_idx = sys.argv.index("--wait-for-pid") + 1
            if pid_idx < len(sys.argv):
                old_pid = int(sys.argv[pid_idx])
                PROCESS_SYNCHRONIZE = 0x00100000
                h_proc = kernel32.OpenProcess(PROCESS_SYNCHRONIZE, False, old_pid)
                if h_proc:
                    try:
                        # Wait up to 10000ms for old process to exit
                        kernel32.WaitForSingleObject(h_proc, 10000)
                    finally:
                        kernel32.CloseHandle(h_proc)
                else:
                    time.sleep(0.05)
        except (ValueError, OSError, AttributeError) as e:
            logger.debug(f"Error waiting for old PID: {e}")

    MUTEX_NAME = "Local\\YMU_SingleInstance_Mutex"
    ERROR_ALREADY_EXISTS = 183
    max_attempts = 30 if is_restart else 1

    try:
        for attempt in range(max_attempts):
            h_mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
            if kernel32.GetLastError() != ERROR_ALREADY_EXISTS:
                return h_mutex
            if h_mutex:
                kernel32.CloseHandle(h_mutex)
            if is_restart and attempt < max_attempts - 1:
                time.sleep(0.1)

        hwnd = user32.FindWindowW(None, WINDOW_TITLE)
        if hwnd:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            sys.exit(0)
        elif is_restart:
            # Note: Pre-QApplication / pre-LocalizationManager MessageBoxW calls intentionally stay in English
            # because no Qt event loop or localization subsystem is initialized at this stage.
            user32.MessageBoxW(
                0,
                "Previous YMU instance could not be replaced within the timeout.\n"
                "Please verify in Task Manager that no other YMU processes are running.",
                "YMU Restart Error",
                0x10,
            )
        else:
            user32.MessageBoxW(
                0,
                "Another instance of YMU is already running.",
                "YMU Already Running",
                0x40,  # MB_ICONINFORMATION
            )
            sys.exit(0)
    except Exception as e:
        logger.error(f"Error during instance check: {e}")
        try:
            user32.MessageBoxW(
                0,
                f"Failed to initialize application lock:\n{e}",
                "YMU Initialization Error",
                0x10,
            )
        except Exception:
            pass
        sys.exit(1)


def _log_startup_info():
    system_info = {
        "YMU Version": LOCAL_VERSION,
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


def cleanup_legacy_ymu_dir():
    """Safely cleans up or backs up the legacy './ymu' directory left by older versions.
    Requires an ownership sentinel (.ymu-marker) before recursive removal;
    otherwise renames to ymu.bak-<timestamp> to prevent accidental data loss.
    Never executes in dev mode (uncompiled)."""
    if not is_compiled():
        return

    try:
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        old_ymu_path = os.path.join(script_dir, "ymu")
        if os.path.isdir(old_ymu_path):
            sentinel = os.path.join(old_ymu_path, ".ymu-marker")
            if os.path.isfile(sentinel):
                import shutil

                shutil.rmtree(old_ymu_path)
                logger.info("Legacy folder with ownership marker successfully removed.")
            else:
                bak_path = f"{old_ymu_path}.bak-{int(time.time())}"
                os.rename(old_ymu_path, bak_path)
                logger.warning(
                    f"Legacy './ymu' folder found without marker; renamed to {os.path.basename(bak_path)} to prevent data loss."
                )
    except OSError as e:
        logger.error(f"Failed to clean up legacy './ymu' folder: {e}")


def main():
    setup_logging()
    _single_instance_mutex = _acquire_single_instance()
    _log_startup_info()
    migrate_legacy_dll_dir()
    cleanup_old_runtime_dirs()
    cleanup_legacy_ymu_dir()

    app = QApplication(sys.argv)
    app.setEffectEnabled(Qt.UIEffect.UI_AnimateCombo, False)
    cleanup_updater()
    worker_manager = WorkerManager()
    focus_filter = FocusStealingFilter(app)
    app.installEventFilter(focus_filter)
    font_dir = resource_path(os.path.join("assets", "fonts"))
    if os.path.exists(font_dir):
        for font_file in os.listdir(font_dir):
            if font_file.lower().endswith((".ttf", ".otf", ".ttc")):
                font_path = os.path.join(font_dir, font_file)
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id == -1:
                    logger.warning(f"Failed to load application font: {font_file}")
                else:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    logger.info(f"Loaded application font '{font_file}': {families}")
        assert "Rubik" in QFontDatabase.families(), (
            "Bundled font 'Rubik' must be loaded in QFontDatabase"
        )
    else:
        logger.warning(f"Application font directory not found: {font_dir}")
    asset_path = resource_path(os.path.join("assets", "icons")).replace("\\", "/")
    loc_manager = LocalizationManager(worker_manager=worker_manager)
    app.setLayoutDirection(loc_manager.get_layout_direction())
    theme_manager = ThemeManager(
        app, asset_path=asset_path, is_rtl=loc_manager.is_rtl()
    )
    theme_manager.apply_current_theme()
    window = MainWindow(
        theme_manager=theme_manager,
        worker_manager=worker_manager,
        loc_manager=loc_manager,
    )
    app.styleHints().colorSchemeChanged.connect(window.on_system_color_scheme_changed)
    update_app_icon(app, window)
    window.show()
    QTimer.singleShot(100, window.show_when_ready)
    exit_code = app.exec()
    if not worker_manager.cleanup():
        logger.warning(
            "WorkerManager did not finish all background tasks before process exit."
        )
    # Explicitly keep reference to mutex until program exit
    del _single_instance_mutex
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
