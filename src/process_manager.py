# process_manager.py - Handles finding the GTA5.exe process and injecting the DLL.

import ctypes
import logging
import os
import shutil
import tempfile

import psutil
import pyinjector

logger = logging.getLogger(__name__)


class InjectionError(Exception):
    """A DLL injection failed for a known, user-actionable reason.

    `reason` is a stable key the UI maps to a localized, actionable message so a
    failure never dead-ends at a generic "see logs"; `detail` is the raw
    technical cause kept for the log.
    """

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail


def _classify_injector_error(e: pyinjector.InjectorError) -> Exception:
    """Translate a pyinjector error into a typed exception with a UI `reason`.

    Windows reports the concrete cause in the trailing message (error_str),
    while ret_val -5 is only the umbrella "LoadLibrary in the target failed",
    so the message text is matched first.
    """
    text = (getattr(e, "error_str", "") or str(e)).lower()
    if "access is denied" in text:
        # Kept as PermissionError so the admin-aware UI branch handles it.
        return PermissionError("Access Denied")
    if "not a valid win32 application" in text or "bad exe format" in text:
        return InjectionError("bad_architecture", str(e))
    if "could not be found" in text or "specified module" in text:
        return InjectionError("module_not_found", str(e))
    return InjectionError("unknown", str(e))


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


# BattlEye's user-mode service. If it runs, BattlEye is enabled — YMU/YimMenu
# require it OFF; injecting anyway risks a ban and usually fails outright.
BATTLEYE_EXECUTABLES = ("beservice.exe", "beservice_x64.exe")


def is_battleye_running() -> bool:
    """True if a BattlEye service process is currently running.

    Fails open (returns False) on any scan error so a flaky check can never
    block an otherwise valid injection.
    """
    try:
        for p in psutil.process_iter(["name"]):
            name = p.info["name"]
            if name and name.lower() in BATTLEYE_EXECUTABLES:
                logger.info(f"BattlEye process detected: {name}")
                return True
    except Exception as e:
        logger.debug(f"BattlEye check failed, assuming not running: {e}")
    return False


def _short_path(path: str) -> str | None:
    """Return the Windows 8.3 short-name form of *path*, or None if unavailable."""
    get_short = ctypes.windll.kernel32.GetShortPathNameW
    length = get_short(path, None, 0)
    if not length:
        return None
    buf = ctypes.create_unicode_buffer(length)
    if get_short(path, buf, length):
        return buf.value
    return None


def _ascii_safe_dll_path(dll_path: str) -> str:
    """
    pyinjector writes the DLL path into the target process as UTF-8 bytes and
    loads it via the ANSI LoadLibraryA, which resolves those bytes with the
    system code page. Any non-ASCII character in the path (most commonly the
    Windows user name, e.g. C:\\Users\\Пользователь\\... or C:\\Users\\Müller\\...)
    is therefore mangled, so LoadLibrary cannot find the file and injection
    fails with error -5
    ("The specified module could not be found").

    Return an ASCII-only path pointing at the same DLL: the 8.3 short-name form
    when the volume provides one, otherwise a copy placed in an ASCII directory.
    """
    if dll_path.isascii():
        return dll_path

    short = _short_path(dll_path)
    if short and short.isascii():
        return short

    base = os.environ.get("PUBLIC") or tempfile.gettempdir()
    ascii_dir = os.path.join(base, "YMU")
    os.makedirs(ascii_dir, exist_ok=True)
    name = os.path.basename(dll_path)
    dst = os.path.join(ascii_dir, name if name.isascii() else "inject.dll")
    shutil.copy2(dll_path, dst)
    if not dst.isascii():
        dst = _short_path(dst) or dst
    return dst


# PE COFF machine types. GTA V (both Legacy and Enhanced) is 64-bit only, so a
# YimMenu DLL must be AMD64; a 32-bit (I386) DLL cannot load into the game.
IMAGE_FILE_MACHINE_AMD64 = 0x8664
IMAGE_FILE_MACHINE_I386 = 0x14C


def get_dll_machine(dll_path: str) -> int | None:
    """Read the PE 'machine' field of dll_path.

    Returns the machine type (e.g. 0x8664 = x64, 0x14C = x86) for a valid PE,
    0 if the file is readable but not a PE image at all, or None if the header
    could not be read (the caller should fail open in that case).
    """
    try:
        with open(dll_path, "rb") as f:
            if f.read(2) != b"MZ":
                return 0
            f.seek(0x3C)
            pe_offset = int.from_bytes(f.read(4), "little")
            f.seek(pe_offset)
            if f.read(4) != b"PE\x00\x00":
                return 0
            return int.from_bytes(f.read(2), "little")
    except OSError as e:
        logger.debug(f"Could not read PE header of {dll_path}: {e}")
        return None


def inject_dll(pid: int, dll_path: str, **kwargs) -> bool:
    """
    Injects a DLL into a process with the given PID.

    :param pid: The Process ID of the target process.
    :param dll_path: The absolute path to the DLL file.
    :return: True on success. Known failures raise InjectionError (or
        PermissionError for access-denied) carrying a stable `reason` the UI
        turns into actionable guidance.
    """
    if not os.path.isabs(dll_path):
        dll_path = os.path.abspath(dll_path)
    if not os.path.exists(dll_path):
        # Usually the antivirus quarantined the DLL after download (YimMenu is
        # routinely flagged), or it was never downloaded in the first place.
        logger.error(f"DLL not found at inject time: {dll_path}")
        raise InjectionError("dll_missing", dll_path)
    machine = get_dll_machine(dll_path)
    if machine == 0:
        logger.error(f"Selected file is not a valid PE/DLL: {dll_path}")
        raise InjectionError("not_a_dll", dll_path)
    if machine is not None and machine != IMAGE_FILE_MACHINE_AMD64:
        logger.error(
            f"DLL is not 64-bit (machine=0x{machine:04x}); GTA V requires x64: "
            f"{dll_path}"
        )
        raise InjectionError("bad_architecture", f"machine=0x{machine:04x}")
    if not psutil.pid_exists(pid):
        logger.error(f"Target process (PID {pid}) is gone. Cannot inject.")
        raise InjectionError("process_gone", f"PID {pid}")
    try:
        logger.info(f"Attempting to inject '{dll_path}' into PID {pid}...")
        inject_path = _ascii_safe_dll_path(dll_path)
        if inject_path != dll_path:
            logger.info(f"Using ASCII-safe injection path: {inject_path}")
        pyinjector.inject(pid, inject_path)
        logger.info("Injection successful.")
        return True
    except pyinjector.InjectorError as e:
        classified = _classify_injector_error(e)
        if isinstance(classified, PermissionError):
            logger.warning("Injection blocked due to insufficient permissions.")
        else:
            reason = getattr(classified, "reason", "unknown")
            logger.error(
                f"Injection failed [{reason}]: code={getattr(e, 'ret_val', '?')} "
                f"detail={getattr(e, 'error_str', None) or str(e)!r}"
            )
        raise classified from e
    except Exception as e:
        logger.exception(f"An unexpected exception occurred during injection: {e}")
        raise


def is_process_running(pid: int) -> bool:
    """
    Checks if a process with the given PID is still running.
    :param pid: The Process ID to check.
    :return: True if the process is running, otherwise False.
    """
    return psutil.pid_exists(pid)
