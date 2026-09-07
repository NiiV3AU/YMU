# process_manager.py - Handles finding the GTA5.exe process and injecting the DLL.

import base64
import ctypes
import logging
import os
import shutil
import tempfile
import time
from ctypes import wintypes
from typing import TYPE_CHECKING

import pyinjector

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


# Windows API Constants & Structures for process management
TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
SYNCHRONIZE = 0x00100000
WAIT_TIMEOUT = 0x00000102
WAIT_OBJECT_0 = 0x00000000
STILL_ACTIVE = 259
LIST_MODULES_ALL = 0x03
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
SEE_MASK_NOCLOSEPROCESS = 0x00000040


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


# Win32 API DLL Instances & Explicit Function Prototypes
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32
psapi = ctypes.windll.psapi

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE

kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD

kernel32.GetExitCodeProcess.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.GetExitCodeProcess.restype = wintypes.BOOL

kernel32.GetShortPathNameW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPWSTR,
    wintypes.DWORD,
]
kernel32.GetShortPathNameW.restype = wintypes.DWORD

kernel32.GetLastError.argtypes = []
kernel32.GetLastError.restype = wintypes.DWORD

kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.TerminateProcess.restype = wintypes.BOOL

kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE

kernel32.Process32FirstW.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(PROCESSENTRY32W),
]
kernel32.Process32FirstW.restype = wintypes.BOOL

kernel32.Process32NextW.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(PROCESSENTRY32W),
]
kernel32.Process32NextW.restype = wintypes.BOOL

kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
shell32.ShellExecuteExW.restype = wintypes.BOOL

shell32.IsUserAnAdmin.argtypes = []
shell32.IsUserAnAdmin.restype = wintypes.BOOL

psapi.EnumProcessModulesEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.DWORD,
]
psapi.EnumProcessModulesEx.restype = wintypes.BOOL

psapi.GetModuleFileNameExW.argtypes = [
    wintypes.HANDLE,
    wintypes.HMODULE,
    wintypes.LPWSTR,
    wintypes.DWORD,
]
psapi.GetModuleFileNameExW.restype = wintypes.DWORD


def is_admin() -> bool:
    """True if the current process runs with Administrator privileges."""
    try:
        return bool(shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _iter_processes() -> list[tuple[int, str]]:
    """Return (pid, exe_name) for all active processes via Toolhelp32 snapshot.

    Eagerly materializes the process list and closes the snapshot handle immediately
    in finally, preventing handle leaks when callers break or return early.
    """
    h_snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not h_snap or h_snap in (-1, INVALID_HANDLE_VALUE):
        return []
    processes: list[tuple[int, str]] = []
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if kernel32.Process32FirstW(h_snap, ctypes.byref(pe)):
            while True:
                processes.append((pe.th32ProcessID, pe.szExeFile))
                if not kernel32.Process32NextW(h_snap, ctypes.byref(pe)):
                    break
    finally:
        kernel32.CloseHandle(h_snap)
    return processes


def _get_process_image_path(pid: int) -> str | None:
    """Return the full executable image path for a PID using QueryFullProcessImageNameW."""
    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_proc:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
            return buf.value
    finally:
        kernel32.CloseHandle(h_proc)
    return None


def pid_exists(pid: int) -> bool:
    """Checks whether a process with the given PID is currently running."""
    if pid <= 0:
        return False

    h_proc = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid
    )
    if not h_proc:
        # ERROR_ACCESS_DENIED (5) indicates the process exists but is protected
        return kernel32.GetLastError() == 5
    try:
        res = kernel32.WaitForSingleObject(h_proc, 0)
        if res == WAIT_TIMEOUT:
            return True
        if res == WAIT_OBJECT_0:
            return False
        exit_code = wintypes.DWORD()
        if kernel32.GetExitCodeProcess(h_proc, ctypes.byref(exit_code)):
            return exit_code.value == STILL_ACTIVE
        return True
    finally:
        kernel32.CloseHandle(h_proc)


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
        for pid, name in _iter_processes():
            if name and name.lower() in targets:
                logger.info(f"Found process by name: '{name}' with PID: {pid}")
                return pid
    except Exception:
        logger.exception(
            "An unexpected error occurred while searching for the game process"
        )

    logger.debug(f"No process matching {targets} found.")
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
        for _pid, name in _iter_processes():
            if name and name.lower() in BATTLEYE_EXECUTABLES:
                logger.info(f"BattlEye process detected: {name}")
                return True
    except OSError as e:
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
    if not pid_exists(pid):
        logger.warning(f"Process PID {pid} is not running. Cannot verify module.")
        return False

    target = os.path.basename(dll_name_or_path).lower()
    start = time.time()
    can_query_modules = False

    while time.time() - start < timeout:
        if not pid_exists(pid):
            logger.warning(f"Process PID {pid} terminated during module verification.")
            return False

        h_proc = kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
            False,
            pid,
        )
        if not h_proc:
            err = kernel32.GetLastError()
            if err == 5:  # ERROR_ACCESS_DENIED
                logger.warning(
                    f"OpenProcess for PID {pid} returned ERROR_ACCESS_DENIED; assuming injection succeeded."
                )
                return True
            time.sleep(0.2)
            continue

        try:
            cb_needed = wintypes.DWORD()
            initial_count = 1024
            modules = (wintypes.HMODULE * initial_count)()
            cb = ctypes.sizeof(modules)
            hmodule_size = ctypes.sizeof(wintypes.HMODULE)

            if psapi.EnumProcessModulesEx(
                h_proc, modules, cb, ctypes.byref(cb_needed), LIST_MODULES_ALL
            ):
                can_query_modules = True
                if cb_needed.value > cb:
                    mod_count = cb_needed.value // hmodule_size
                    modules = (wintypes.HMODULE * mod_count)()
                    cb = ctypes.sizeof(modules)
                    if not psapi.EnumProcessModulesEx(
                        h_proc, modules, cb, ctypes.byref(cb_needed), LIST_MODULES_ALL
                    ):
                        continue

                count = cb_needed.value // hmodule_size
                buf = ctypes.create_unicode_buffer(1024)
                for i in range(count):
                    h_mod = modules[i]
                    if (
                        psapi.GetModuleFileNameExW(h_proc, h_mod, buf, len(buf))
                        and os.path.basename(buf.value).lower() == target
                    ):
                        logger.info(
                            f"Verified module '{target}' in memory of PID {pid}: {buf.value}"
                        )
                        return True
        except OSError as e:
            logger.debug(f"Could not inspect modules for PID {pid}: {e}")
        finally:
            kernel32.CloseHandle(h_proc)

        time.sleep(0.2)

    if not can_query_modules:
        # If the process is gone, this is a crash/exit, NOT insufficient rights
        if not pid_exists(pid):
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
    if not pid_exists(pid):
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
            if not pid_exists(pid):
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
    return pid_exists(pid)


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
        exe_path = _get_process_image_path(pid)
        if exe_path and os.path.isfile(exe_path):
            return os.path.dirname(exe_path)

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


def _elevated_write_file(path: str, content: str, encoding: str) -> bool:
    """Writes content to path via an elevated PowerShell process (triggers Windows UAC prompt)."""
    temp_fd, temp_path = tempfile.mkstemp(suffix=".txt")
    process_running = False
    try:
        with os.fdopen(temp_fd, "w", encoding=encoding) as f:
            f.write(content)

        escaped_src = temp_path.replace("'", "''")
        escaped_dst = path.replace("'", "''")
        ps_script = f"Copy-Item -LiteralPath '{escaped_src}' -Destination '{escaped_dst}' -Force"
        encoded_cmd = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
        params = f"-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand {encoded_cmd}"

        sei = SHELLEXECUTEINFOW()
        sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
        sei.fMask = SEE_MASK_NOCLOSEPROCESS
        sei.hwnd = None
        sei.lpVerb = "runas"
        sei.lpFile = "powershell.exe"
        sei.lpParameters = params
        sei.nShow = 0  # SW_HIDE

        if not shell32.ShellExecuteExW(ctypes.byref(sei)):
            logger.warning(f"Elevated write to {path} cancelled or failed.")
            return False

        if not sei.hProcess:
            return False

        process_running = True
        try:
            wait_res = kernel32.WaitForSingleObject(sei.hProcess, 10000)
            if wait_res == WAIT_TIMEOUT:
                logger.warning(
                    f"Elevated write to {path} timed out; terminating process."
                )
                kernel32.TerminateProcess(sei.hProcess, 1)
                kernel32.WaitForSingleObject(sei.hProcess, 1000)
                process_running = False
                return False

            process_running = False
            exit_code = wintypes.DWORD()
            kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(exit_code))
            return exit_code.value == 0
        finally:
            kernel32.CloseHandle(sei.hProcess)
    except OSError as e:
        logger.error(f"Error during elevated write: {e}")
        return False
    finally:
        if not process_running and os.path.isfile(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _elevated_delete_file(path: str) -> bool:
    """Deletes path via an elevated PowerShell process (triggers Windows UAC prompt)."""
    try:
        escaped_path = path.replace("'", "''")
        ps_script = f"Remove-Item -LiteralPath '{escaped_path}' -Force"
        encoded_cmd = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
        params = f"-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand {encoded_cmd}"

        sei = SHELLEXECUTEINFOW()
        sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
        sei.fMask = SEE_MASK_NOCLOSEPROCESS
        sei.hwnd = None
        sei.lpVerb = "runas"
        sei.lpFile = "powershell.exe"
        sei.lpParameters = params
        sei.nShow = 0  # SW_HIDE

        if not shell32.ShellExecuteExW(ctypes.byref(sei)):
            logger.warning(f"Elevated delete of {path} cancelled or failed.")
            return False

        if not sei.hProcess:
            return False

        try:
            wait_res = kernel32.WaitForSingleObject(sei.hProcess, 10000)
            if wait_res == WAIT_TIMEOUT:
                logger.warning(
                    f"Elevated delete of {path} timed out; terminating process."
                )
                kernel32.TerminateProcess(sei.hProcess, 1)
                kernel32.WaitForSingleObject(sei.hProcess, 1000)
                return False

            exit_code = wintypes.DWORD()
            kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(exit_code))
            return exit_code.value == 0
        finally:
            kernel32.CloseHandle(sei.hProcess)
    except OSError as e:
        logger.error(f"Error during elevated delete: {e}")
        return False


def set_nobattleye_enabled(gta_dir: str, enable: bool) -> bool:
    """Adds or removes -nobattleye in commandline.txt inside gta_dir.

    Preserves other existing commandline arguments. If -nobattleye was
    the only argument when disabling, deletes commandline.txt cleanly.
    Falls back to a Windows UAC prompt if admin rights are required.
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
        new_content = existing
        if new_content and not new_content.endswith("\n"):
            new_content += "\n"
        new_content += "-nobattleye\n"

        try:
            with open(path, "w", encoding=write_enc) as f:
                f.write(new_content)
            logger.info(f"Added -nobattleye to {path}")
            return True
        except PermissionError:
            logger.info(
                f"Permission denied writing {path}; requesting UAC elevation..."
            )
            if _elevated_write_file(path, new_content, write_enc):
                logger.info(f"Added -nobattleye to {path} via elevated prompt")
                return True
            logger.error(
                "Could not write to commandline.txt (elevation failed or denied)"
            )
            return False
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
                new_content = "\n".join(cleaned_lines) + "\n"
                with open(path, "w", encoding=write_enc) as f:
                    f.write(new_content)
                logger.info(f"Removed -nobattleye from {path}")
            else:
                os.remove(path)
                logger.info(f"Removed empty commandline.txt at {path}")
            return True
        except PermissionError:
            logger.info(
                f"Permission denied modifying {path}; requesting UAC elevation..."
            )
            if cleaned_lines:
                write_enc = "utf-16" if enc == "utf-16" else "utf-8"
                new_content = "\n".join(cleaned_lines) + "\n"
                if _elevated_write_file(path, new_content, write_enc):
                    logger.info(f"Removed -nobattleye from {path} via elevated prompt")
                    return True
            elif _elevated_delete_file(path):
                logger.info(
                    f"Deleted empty commandline.txt at {path} via elevated prompt"
                )
                return True
            logger.error(
                "Could not modify/delete commandline.txt (elevation failed or denied)"
            )
            return False
        except OSError as e:
            logger.error(f"Could not update/delete commandline.txt: {e}")
            return False
