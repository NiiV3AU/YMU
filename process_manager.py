# process_manager.py - Handles finding the GTA5.exe process and injecting the DLL.

import psutil
import pyinjector
import os
import logging
from paths import YMU_DLL_DIR

logger = logging.getLogger(__name__)


def find_gta_pid(*args, **kwargs) -> int | None:
    """
    Scans for the GTA5.exe process and returns its PID using multiple robust checks.
    :return: The process ID (PID) of GTA5.exe if found, otherwise None.
    """
    try:
        for p in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
            if p.info["name"] and p.info["name"].lower() == "gta5.exe":
                logger.info(
                    f"Found process by name: '{p.info['name']}' with PID: {p.pid}"
                )
                return p.pid

            if p.info["exe"] and os.path.basename(p.info["exe"]).lower() == "gta5.exe":
                logger.info(
                    f"Found process by executable path: '{p.info['exe']}' with PID: {p.pid}"
                )
                return p.pid

            if (
                p.info["cmdline"]
                and len(p.info["cmdline"]) > 0
                and p.info["cmdline"][0].lower().endswith("gta5.exe")
            ):
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

    logger.warning("GTA5.exe process not found.")
    return None


def inject_dll(pid: int, dll_filename: str) -> bool:
    """
    Injects a DLL into a process with the given PID.
    :param pid: The Process ID of the target process.
    :param dll_path: The absolute path to the DLL file.
    :return: True if injection was successful, otherwise False.
    """
    dll_path = os.path.join(YMU_DLL_DIR, dll_filename)
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
    except (pyinjector.ProcessNotFound, pyinjector.InjectorError) as e:  # type: ignore
        logger.exception(f"A pyinjector error occurred during injection: {e}")
        return False
    except Exception as e:
        logger.exception(f"An unexpected exception occurred during injection: {e}")
        return False


def is_process_running(pid: int) -> bool:
    """
    Checks if a process with the given PID is still running.
    :param pid: The Process ID to check.
    :return: True if the process is running, otherwise False.
    """
    return psutil.pid_exists(pid)
