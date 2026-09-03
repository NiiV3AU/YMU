# process_manager.py - Handles finding the GTA5.exe process and injecting the DLL.

import ctypes
import logging
import os
import shutil
import tempfile
import time
from typing import TYPE_CHECKING

import psutil
import pyinjector
import win32api
import win32con
import win32process

if TYPE_CHECKING:
    from core.menu_modes import MenuMode

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
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
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
    (PlayGTAV.exe, see InjectPage._start_game_from_dir in
    ui/pages/inject_page.py) and never to identify the
    running process: launcher and helper executables (PlayGTAV.exe,
    Launcher.exe, the social-club service, ...) live in that same directory,
    so matching by directory would return one of those PIDs and inject into
    the wrong process instead of the game.
    :return: The process ID (PID) if found, otherwise None.
    """
    targets = tuple(t.lower() for t in target_executables)
    try:
        for p in psutil.process_iter(["pid", "name"]):
            try:
                name = p.info.get("name")
                if name and name.lower() in targets:
                    logger.info(f"Found process by name: '{name}' with PID: {p.pid}")
                    return p.pid

                # Fallback to exe / cmdline only if name is missing/empty
                if not name:
                    exe = p.exe()
                    if exe and os.path.basename(exe).lower() in targets:
                        logger.info(
                            f"Found process by executable path: '{exe}' with PID: {p.pid}"
                        )
                        return p.pid

                    cmdline = p.cmdline()
                    if cmdline and len(cmdline) > 0:
                        exe_in_cmd = cmdline[0].lower()
                        if any(exe_in_cmd.endswith(target) for target in targets):
                            logger.info(
                                f"Found process by command line: '{cmdline[0]}' with PID: {p.pid}"
                            )
                            return p.pid
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    except Exception:
        logger.exception(
            "An unexpected error occurred while searching for the game process"
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
            try:
                name = p.info["name"]
                if name and name.lower() in BATTLEYE_EXECUTABLES:
                    logger.info(f"BattlEye process detected: {name}")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except (psutil.Error, OSError) as e:
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


def is_dll_loaded_in_process(
    pid: int, dll_name_or_path: str, timeout: float = 2.5
) -> bool:
    """Checks via Windows API whether the specified DLL is loaded in the process's address space.

    Polls for up to `timeout` seconds to account for module load time during heavy game load.
    """
    if not psutil.pid_exists(pid):
        logger.warning(f"Process PID {pid} is not running. Cannot verify module.")
        return False

    target = os.path.basename(dll_name_or_path).lower()
    start = time.time()
    can_open_process = False

    while time.time() - start < timeout:
        if not psutil.pid_exists(pid):
            logger.warning(f"Process PID {pid} terminated during module verification.")
            return False

        h_proc = None
        try:
            h_proc = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                False,
                pid,
            )
            can_open_process = True
            modules = win32process.EnumProcessModulesEx(
                h_proc, win32process.LIST_MODULES_ALL
            )
            for m in modules:
                try:
                    mod_path = win32process.GetModuleFileNameEx(h_proc, m)
                    if os.path.basename(mod_path).lower() == target:
                        logger.info(
                            f"Verified module '{target}' in memory of PID {pid}: {mod_path}"
                        )
                        return True
                except (OSError, win32api.error):
                    continue
        except (OSError, win32api.error) as e:
            logger.debug(f"Could not inspect modules for PID {pid}: {e}")
        finally:
            if h_proc:
                win32api.CloseHandle(h_proc)

        time.sleep(0.2)

    if not can_open_process:
        # If the process is gone, this is a crash/exit, NOT insufficient rights
        if not psutil.pid_exists(pid):
            return False

        # Fail open ONLY if the process is confirmed still alive but restricted
        logger.warning(
            f"Could not query modules for PID {pid} (insufficient rights); assuming injection succeeded."
        )
        return True

    logger.warning(
        f"Module verification timed out: '{target}' was NOT found in PID {pid}'s module list."
    )
    return False


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
        logger.info(
            f"pyinjector.inject completed for PID {pid}. Verifying module in memory..."
        )

        if not is_dll_loaded_in_process(pid, inject_path, timeout=2.5):
            if not psutil.pid_exists(pid):
                logger.error(
                    f"Target process (PID {pid}) crashed during or after injection."
                )
                raise InjectionError("process_gone", f"PID {pid}")

            logger.error(
                f"In-memory verification failed: '{os.path.basename(inject_path)}' "
                f"was not found in memory of PID {pid}."
            )
            raise InjectionError("module_not_loaded", os.path.basename(inject_path))

        logger.info("Injection successful and verified in memory.")
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
    except Exception:
        logger.exception("An unexpected exception occurred during injection")
        raise


def is_process_running(pid: int) -> bool:
    """
    Checks if a process with the given PID is still running.
    :param pid: The Process ID to check.
    :return: True if the process is running, otherwise False.
    """
    return psutil.pid_exists(pid)


def get_gta_directory(mode: "MenuMode | None" = None) -> str | None:
    """Resolves the GTA V install directory.

    Checks:
    1. User-configured custom directory in config ('paths.gta_dir').
    2. Running GTA V process path if currently running.
    3. Rockstar registry install directory for the active edition.
    """
    from core import menu_modes
    from core.config import get_config

    custom_dir = get_config().get("paths.gta_dir")
    if custom_dir and os.path.isdir(custom_dir):
        return custom_dir

    if mode is None:
        mode = menu_modes.get_mode(get_config().get("mode", "legacy"))

    # Check running process
    pid = find_gta_pid(mode.target_executables)
    if pid:
        try:
            p = psutil.Process(pid)
            exe_path = p.exe()
            if exe_path and os.path.isfile(exe_path):
                return os.path.dirname(exe_path)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Check registry
    reg_dir = menu_modes.get_install_dir(mode)
    if reg_dir and os.path.isdir(reg_dir):
        return reg_dir

    return None


def _detect_encoding(path: str) -> str:
    """Detects if file uses UTF-16 BOM, otherwise defaults to utf-8-sig."""
    try:
        with open(path, "rb") as f:
            raw = f.read(2)
            if raw in (b"\xff\xfe", b"\xfe\xff"):
                return "utf-16"
    except OSError:
        pass
    return "utf-8-sig"


def is_nobattleye_enabled(gta_dir: str | None) -> bool:
    """Checks whether -nobattleye is set in commandline.txt inside gta_dir."""
    if not gta_dir or not os.path.isdir(gta_dir):
        return False
    path = os.path.join(gta_dir, "commandline.txt")
    if not os.path.isfile(path):
        return False
    enc = _detect_encoding(path)
    try:
        with open(path, "r", encoding=enc, errors="ignore") as f:
            return "-nobattleye" in f.read().lower().split()
    except OSError:
        return False


def set_nobattleye_enabled(gta_dir: str, enable: bool) -> bool:
    """Adds or removes -nobattleye in commandline.txt inside gta_dir.

    Preserves other existing commandline arguments. If -nobattleye was
    the only argument when disabling, deletes commandline.txt cleanly.
    """
    if not gta_dir or not os.path.isdir(gta_dir):
        return False
    path = os.path.join(gta_dir, "commandline.txt")
    enc = _detect_encoding(path) if os.path.isfile(path) else "utf-8"

    if enable:
        if is_nobattleye_enabled(gta_dir):
            return True
        existing = ""
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding=enc, errors="ignore") as f:
                    existing = f.read()
            except OSError as e:
                logger.error(f"Could not read existing commandline.txt: {e}")
                return False

        write_enc = "utf-16" if enc == "utf-16" else "utf-8"
        try:
            with open(path, "w", encoding=write_enc) as f:
                if existing and not existing.endswith("\n"):
                    existing += "\n"
                f.write(existing + "-nobattleye\n")
            logger.info(f"Added -nobattleye to {path}")
            return True
        except OSError as e:
            logger.error(f"Could not write to commandline.txt: {e}")
            return False
    else:
        if not os.path.isfile(path):
            return True
        try:
            with open(path, "r", encoding=enc, errors="ignore") as f:
                lines = f.readlines()
        except OSError as e:
            logger.error(f"Could not read commandline.txt: {e}")
            return False

        cleaned_lines = []
        for line in lines:
            words = [w for w in line.strip().split() if w.lower() != "-nobattleye"]
            if words:
                cleaned_lines.append(" ".join(words))

        try:
            if cleaned_lines:
                write_enc = "utf-16" if enc == "utf-16" else "utf-8"
                with open(path, "w", encoding=write_enc) as f:
                    f.write("\n".join(cleaned_lines) + "\n")
                logger.info(f"Removed -nobattleye from {path}")
            else:
                os.remove(path)
                logger.info(f"Removed empty commandline.txt at {path}")
            return True
        except OSError as e:
            logger.error(f"Could not update/delete commandline.txt: {e}")
            return False
