# process_manager.py - Handles finding the GTA5.exe process and injecting the DLL.

import logging
import os

import psutil
import pyinjector

logger = logging.getLogger(__name__)


def is_admin() -> bool:
    """True if the current process runs with Administrator privileges."""
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def find_gta_pid(
    target_executables: tuple[str, ...],
    *args,
    **kwargs,
) -> int | None:
    """
    Scans for a GTA5 process matching one of the given executable names and
    returns its PID. The caller passes the executables of the active edition
    (see menu_modes.py) so Legacy mode never targets the Enhanced process and
    vice versa.

    Matching is strictly by executable name (gta5.exe / gta5_enhanced.exe).
    A configured custom install directory is used only to *launch* the game
    (PlayGTAV.exe, see gui._start_game_from_dir) and never to identify the
    running process: launcher and helper executables (PlayGTAV.exe,
    Launcher.exe, the social-club service, ...) live in that same directory,
    so matching by directory would return one of those PIDs and inject into
    the wrong process instead of the game.
    :return: The process ID (PID) if found, otherwise None.
    """
    targets = tuple(t.lower() for t in target_executables)
    try:
        for p in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
            if p.info["name"] and p.info["name"].lower() in targets:
                logger.info(
                    f"Found process by name: '{p.info['name']}' with PID: {p.pid}"
                )
                return p.pid

            if p.info["exe"] and os.path.basename(p.info["exe"]).lower() in targets:
                logger.info(
                    f"Found process by executable path: '{p.info['exe']}' with PID: {p.pid}"
                )
                return p.pid

            if p.info["cmdline"] and len(p.info["cmdline"]) > 0:
                exe_in_cmd = p.info["cmdline"][0].lower()
                if any(exe_in_cmd.endswith(target) for target in targets):
                    logger.info(
                        f"Found process by command line: '{p.info['cmdline'][0]}' with PID: {p.pid}"
                    )
                    return p.pid

    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred while searching for the game process: {e}"
        )

    logger.warning(f"No process matching {targets} found.")
    return None


def inject_dll(pid: int, dll_path: str, **kwargs) -> bool:
    """
    Injects a DLL into a process with the given PID.
    :param pid: The Process ID of the target process.
    :param dll_path: The absolute path to the DLL file.
    :return: True if injection was successful, otherwise False.
    """
    if not os.path.isabs(dll_path):
        dll_path = os.path.abspath(dll_path)
    if not os.path.exists(dll_path):
        logger.error(f"DLL not found at path: {dll_path}")
        return False
    try:
        if not psutil.pid_exists(pid):
            logger.error(f"Process with PID {pid} does not exist. Cannot inject.")
            return False
        logger.info(f"Attempting to inject '{dll_path}' into PID {pid}...")
        pyinjector.inject(pid, dll_path)
        logger.info("Injection successful.")
        return True
    except pyinjector.InjectorError as e:
        error_msg = str(e)
        if "Access is denied" in error_msg:
            logger.warning("Injection blocked due to insufficient permissions.")
            raise PermissionError("Access Denied")
        logger.exception(f"A pyinjector error occurred during injection: {e}")
        return False
    except Exception as e:
        logger.exception(f"An unexpected exception occurred during injection: {e}")
        raise e


def is_process_running(pid: int) -> bool:
    """
    Checks if a process with the given PID is still running.
    :param pid: The Process ID to check.
    :return: True if the process is running, otherwise False.
    """
    return psutil.pid_exists(pid)
