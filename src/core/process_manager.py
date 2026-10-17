# process_manager.py - Handles finding the GTA5.exe process and injecting the DLL.

import base64
import ctypes
import logging
import os
import re
import tempfile
import threading
import time
from ctypes import wintypes
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.menu_modes import MenuMode

logger = logging.getLogger(__name__)


class InjectionError(Exception):
    """A DLL injection failed for a known, user-actionable reason.

    `reason` is a stable key the UI maps to a localized, actionable message so a
    failure never dead-ends at a generic "see logs"; `detail` is the raw
    technical cause kept for the log.
    """

    def __init__(self, reason: str, detail: str = "", mode_key: str | None = None):
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail
        self.mode_key = mode_key


ERROR_ACCESS_DENIED = 5


def _win32_error_message(err: int) -> str:
    """Best-effort text for a Win32 error code (never raises)."""
    try:
        msg_buf = ctypes.create_unicode_buffer(512)
        n = ctypes.windll.kernel32.FormatMessageW(
            0x00001000 | 0x00000200,  # FORMAT_MESSAGE_FROM_SYSTEM | IGNORE_INSERTS
            None,
            err,
            0,
            msg_buf,
            len(msg_buf),
            None,
        )
        if n:
            return msg_buf.value.strip()
    except OSError:
        pass
    return f"winerror={err}"


def _classify_win32_error(api: str, err: int) -> Exception:
    """Map a failed Win32 API call to the UI error contract.

    Access-denied stays a PermissionError so the admin-aware UI branch
    (restart-as-admin vs. already-admin hint) keeps working; everything else
    becomes an InjectionError("unknown") with the API name and error code.
    """
    detail = f"{api} failed ({_win32_error_message(err)} [{err}])"
    if err == ERROR_ACCESS_DENIED:
        return PermissionError(detail)
    return InjectionError("unknown", detail)


# Windows API Constants & Structures for process management
TH32CS_SNAPPROCESS = 0x00000002
PROCESS_CREATE_THREAD = 0x0002
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
SYNCHRONIZE = 0x00100000
MEM_COMMIT = 0x00001000
MEM_RESERVE = 0x00002000
MEM_RELEASE = 0x00008000
PAGE_READWRITE = 0x04
WAIT_TIMEOUT = 0x00000102
WAIT_OBJECT_0 = 0x00000000
WAIT_FAILED = 0xFFFFFFFF
STILL_ACTIVE = 259
LIST_MODULES_ALL = 0x03
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
SEE_MASK_NOCLOSEPROCESS = 0x00000040
# How long to wait for the remote LoadLibraryW thread (GTA under heavy load
# can be slow to run DllMain). A hung loader lock must not block the worker
# forever, so a timeout raises InjectionError("unknown") instead.
REMOTE_THREAD_WAIT_MS = 15000


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

kernel32.GetExitCodeThread.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.GetExitCodeThread.restype = wintypes.BOOL

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

kernel32.GetProcAddress.argtypes = [wintypes.HMODULE, wintypes.LPCSTR]
kernel32.GetProcAddress.restype = ctypes.c_void_p

kernel32.VirtualAllocEx.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    ctypes.c_size_t,
    wintypes.DWORD,
    wintypes.DWORD,
]
kernel32.VirtualAllocEx.restype = wintypes.LPVOID

kernel32.VirtualFreeEx.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    ctypes.c_size_t,
    wintypes.DWORD,
]
kernel32.VirtualFreeEx.restype = wintypes.BOOL

kernel32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.LPCVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.WriteProcessMemory.restype = wintypes.BOOL

kernel32.CreateRemoteThread.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.c_void_p,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.CreateRemoteThread.restype = wintypes.HANDLE

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
        kernel32.SetLastError(0)
        res = shell32.IsUserAnAdmin()
        err = kernel32.GetLastError()
        if not res and err != 0:
            logger.warning(f"IsUserAnAdmin API call failed with winerror={err}")
        return bool(res)
    except (AttributeError, OSError) as e:
        logger.warning(f"Could not determine admin status: {e}")
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


# PE COFF machine types. GTA V (both Legacy and Enhanced) is 64-bit only, so a
# YimMenu DLL must be AMD64; a 32-bit (I386) DLL cannot load into the game.
IMAGE_FILE_MACHINE_AMD64 = 0x8664


_loadlibraryw_addr: int | None = None


def _loadlibraryw_address() -> int:
    """Return the local address of kernel32!LoadLibraryW, cached per process.

    System DLLs (kernel32) map at the same base in every process of the same
    boot session, so this address is valid as the remote thread start routine
    in GTA V as long as both processes share the same bitness (both x64 here).
    """
    global _loadlibraryw_addr
    if _loadlibraryw_addr:
        return _loadlibraryw_addr
    h_kernel32 = kernel32.GetModuleHandleW("kernel32.dll")
    if not h_kernel32:
        err = kernel32.GetLastError()
        raise InjectionError("unknown", f"GetModuleHandleW(kernel32) failed ({err})")
    addr = kernel32.GetProcAddress(h_kernel32, b"LoadLibraryW")
    if not addr:
        err = kernel32.GetLastError()
        raise InjectionError("unknown", f"GetProcAddress(LoadLibraryW) failed ({err})")
    _loadlibraryw_addr = addr
    return addr


def _native_inject(pid: int, dll_path: str) -> None:
    """Inject dll_path into pid via CreateRemoteThread + LoadLibraryW.

    Raises PermissionError on access-denied, InjectionError("module_not_found")
    when LoadLibraryW returns NULL in the target, or InjectionError("unknown")
    with the failing Win32 API + code for every other failure. All opened
    handles and the remote allocation are released on every path.
    """
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        raise InjectionError(
            "bad_architecture", "YMU must run as 64-bit to inject into GTA V (x64)"
        )
    loadlibrary = _loadlibraryw_address()

    desired_access = (
        PROCESS_CREATE_THREAD
        | PROCESS_QUERY_INFORMATION
        | PROCESS_VM_OPERATION
        | PROCESS_VM_WRITE
        | PROCESS_VM_READ
    )
    h_proc = kernel32.OpenProcess(desired_access, False, pid)
    if not h_proc:
        raise _classify_win32_error("OpenProcess", kernel32.GetLastError())

    remote_mem = None
    h_thread = None
    timed_out = False
    try:
        path_buf = ctypes.create_unicode_buffer(dll_path)
        size = ctypes.sizeof(path_buf)
        remote_mem = kernel32.VirtualAllocEx(
            h_proc, None, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
        )
        if not remote_mem:
            raise _classify_win32_error("VirtualAllocEx", kernel32.GetLastError())

        written = ctypes.c_size_t(0)
        if not kernel32.WriteProcessMemory(
            h_proc, remote_mem, path_buf, size, ctypes.byref(written)
        ):
            raise _classify_win32_error("WriteProcessMemory", kernel32.GetLastError())
        if written.value != size:
            raise InjectionError(
                "unknown",
                f"WriteProcessMemory wrote {written.value}/{size} bytes for PID {pid}",
            )

        thread_id = wintypes.DWORD(0)
        h_thread = kernel32.CreateRemoteThread(
            h_proc, None, 0, loadlibrary, remote_mem, 0, ctypes.byref(thread_id)
        )
        if not h_thread:
            raise _classify_win32_error("CreateRemoteThread", kernel32.GetLastError())

        wait = kernel32.WaitForSingleObject(h_thread, REMOTE_THREAD_WAIT_MS)
        if wait == WAIT_TIMEOUT:
            timed_out = True
            raise InjectionError(
                "unknown",
                f"LoadLibraryW thread {thread_id.value} timed out after "
                f"{REMOTE_THREAD_WAIT_MS}ms for PID {pid}",
            )
        if wait == WAIT_FAILED:
            raise _classify_win32_error("WaitForSingleObject", kernel32.GetLastError())
        if wait != WAIT_OBJECT_0:
            raise InjectionError(
                "unknown", f"WaitForSingleObject returned 0x{wait:08X} for PID {pid}"
            )

        exit_code = wintypes.DWORD(0)
        if not kernel32.GetExitCodeThread(h_thread, ctypes.byref(exit_code)):
            raise _classify_win32_error("GetExitCodeThread", kernel32.GetLastError())
        if exit_code.value == STILL_ACTIVE:
            timed_out = True
            raise InjectionError(
                "unknown",
                f"LoadLibraryW thread {thread_id.value} still active for PID {pid}",
            )
        if exit_code.value == 0:
            # Remote LoadLibraryW failed (missing file, missing VC++ runtime
            # dependency, blocked by AV/BattlEye...).
            logger.error(
                f"Remote LoadLibraryW returned NULL for '{os.path.basename(dll_path)}' in PID {pid}."
            )
            raise InjectionError("module_not_found", os.path.basename(dll_path))
        logger.info(
            f"Remote LoadLibraryW returned HMODULE=0x{exit_code.value:X} for PID {pid}."
        )
    finally:
        if h_thread:
            kernel32.CloseHandle(h_thread)
        if remote_mem:
            if timed_out:
                logger.warning(
                    f"Skipping VirtualFreeEx for PID {pid} to avoid UAF while remote LoadLibraryW may still be running."
                )
            else:
                kernel32.VirtualFreeEx(h_proc, remote_mem, 0, MEM_RELEASE)
        kernel32.CloseHandle(h_proc)


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
) -> bool | None:
    """Checks via Windows API whether the specified DLL is loaded in the process's address space.

    Polls for up to `timeout` seconds to account for module load time during heavy game load.
    Returns:
        True: module is confirmed loaded in process memory.
        False: module is confirmed absent (timeout) or process died.
        None: verification impossible (e.g. ERROR_ACCESS_DENIED, restricted query rights).
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
                    f"OpenProcess for PID {pid} returned ERROR_ACCESS_DENIED; query rights restricted."
                )
                return None
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

                count = min(cb_needed.value // hmodule_size, len(modules))
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
        except (OSError, IndexError) as e:
            logger.debug(f"Could not inspect modules for PID {pid}: {e}")
        finally:
            kernel32.CloseHandle(h_proc)

        time.sleep(0.2)

    if not can_query_modules:
        # If the process is gone, this is a crash/exit, NOT insufficient rights
        if not pid_exists(pid):
            return False

        # Return None when the process is confirmed still alive but restricted
        logger.warning(
            f"Could not query modules for PID {pid} (insufficient query rights)."
        )
        return None

    logger.warning(
        f"Module verification timed out: '{target}' was NOT found in PID {pid}'s module list."
    )
    return False


def inject_dll(pid: int, dll_path: str) -> bool:
    """
    Injects a DLL into a process with the given PID.

    Uses a native ctypes CreateRemoteThread + LoadLibraryW path (UTF-16, so
    Umlaut/CJK/Arabic paths work directly with no temp staging copy).

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
        _native_inject(pid, dll_path)
        logger.info(
            f"Remote-thread injection completed for PID {pid}. Verifying module in memory..."
        )

        verification = is_dll_loaded_in_process(pid, dll_path, timeout=2.5)
        if verification is False:
            if not pid_exists(pid):
                logger.error(
                    f"Target process (PID {pid}) crashed during or after injection."
                )
                raise InjectionError("process_gone", f"PID {pid}")

            logger.error(
                f"In-memory verification failed: '{os.path.basename(dll_path)}' "
                f"was not found in memory of PID {pid}."
            )
            raise InjectionError("module_not_loaded", os.path.basename(dll_path))

        if verification is None:
            # If module enumeration is restricted (e.g. by security software or
            # transient query conditions), do not fail: the remote thread
            # injection already succeeded, so warn and return success.
            logger.warning(
                f"Native injection succeeded for PID {pid}, but in-memory verification "
                "could not be confirmed due to restricted query rights."
            )
        else:
            logger.info("Injection completed and verified in memory.")

        return True
    except (InjectionError, PermissionError):
        raise
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
    if custom_dir and isinstance(custom_dir, str) and os.path.isdir(custom_dir):
        return custom_dir

    if mode is None:
        mode = menu_modes.get_mode(get_config().get("mode", "legacy"))

    pid = find_gta_pid(mode.target_executables)
    if pid:
        exe_path = _get_process_image_path(pid)
        if exe_path and os.path.isfile(exe_path):
            return os.path.dirname(exe_path)

    reg_dir = menu_modes.get_install_dir(mode)
    if reg_dir and os.path.isdir(reg_dir):
        return reg_dir

    return None


def _detect_encoding(path: str) -> str:
    """Detects if file uses UTF-16 BOM, otherwise defaults to utf-8-sig."""
    try:
        with open(path, "rb") as f:
            raw = f.read(2)
            if raw == b"\xfe\xff":
                return "utf-16-be"
            if raw == b"\xff\xfe":
                return "utf-16"
    except OSError:
        pass
    return "utf-8-sig"


def is_nobattleye_enabled(gta_dir: str | None) -> bool:
    """Checks whether -nobattleye is set in commandline.txt inside gta_dir."""
    if not gta_dir or not os.path.isdir(gta_dir):
        return False
    path = os.path.join(gta_dir, "commandline.txt")
    with _commandline_lock:
        if not os.path.isfile(path):
            return False
        enc = _detect_encoding(path)
        try:
            with open(path, encoding=enc, errors="surrogateescape") as f:
                content = f.read()
            return bool(re.search(r"(?i)(?:^|\s)-nobattleye(?:\s|$)", content))
        except OSError:
            return False


def _elevated_write_file(path: str, content: str, encoding: str) -> bool:
    """Writes content to path via an elevated PowerShell process (triggers Windows UAC prompt).

    Design note: Uses in-place elevation via ShellExecuteExW('runas', 'powershell.exe')
    to copy a prepared temp file to the target path without elevating the entire YMU process.
    """
    temp_fd, temp_path = tempfile.mkstemp(suffix=".txt")
    process_running = False
    try:
        with os.fdopen(temp_fd, "w", encoding=encoding, errors="surrogateescape") as f:
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
            exit_code = wintypes.DWORD(0xFFFFFFFF)
            if not kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(exit_code)):
                err = kernel32.GetLastError()
                logger.error(
                    f"GetExitCodeProcess failed for elevated write to {path}: winerror={err}"
                )
                return False
            if exit_code.value != 0:
                logger.error(
                    f"Elevated write process exited with non-zero code: {exit_code.value}"
                )
                return False
            return os.path.isfile(path)
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

            exit_code = wintypes.DWORD(0xFFFFFFFF)
            if not kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(exit_code)):
                err = kernel32.GetLastError()
                logger.error(
                    f"GetExitCodeProcess failed for elevated delete of {path}: winerror={err}"
                )
                return False
            if exit_code.value != 0:
                logger.error(
                    f"Elevated delete process exited with non-zero code: {exit_code.value}"
                )
                return False
            return not os.path.isfile(path)
        finally:
            kernel32.CloseHandle(sei.hProcess)
    except OSError as e:
        logger.error(f"Error during elevated delete: {e}")
        return False


_commandline_lock = threading.RLock()


def _remove_nobattleye_token(content: str) -> str:
    """Removes the -nobattleye token from commandline.txt content while strictly
    preserving other arguments, spacing (including tabs and spaces inside quotes),
    and line endings (CRLF or LF)."""
    lines = content.splitlines(keepends=True)
    new_lines = []
    for line in lines:
        ending = (
            "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
        )
        body = line[: -len(ending)] if ending else line
        if body.strip().lower() == "-nobattleye":
            continue
        new_body = re.sub(r"(?i)(?<!\S)-nobattleye(?=\s|$)\s*", "", body)
        new_lines.append(new_body + ending)

    result = "".join(new_lines)
    return "" if not result.strip() else result


def set_nobattleye_enabled(gta_dir: str, enable: bool) -> bool:
    """Adds or removes -nobattleye in commandline.txt inside gta_dir.

    Preserves other existing commandline arguments. If -nobattleye was
    the only argument when disabling, deletes commandline.txt cleanly.
    Falls back to a Windows UAC prompt if admin rights are required.
    """
    if not gta_dir or not os.path.isdir(gta_dir):
        return False
    path = os.path.join(gta_dir, "commandline.txt")

    needs_elevation = False
    new_content = ""
    cleaned_content = ""
    write_enc = "utf-8"

    with _commandline_lock:
        enc = _detect_encoding(path) if os.path.isfile(path) else "utf-8"

        if enable:
            if is_nobattleye_enabled(gta_dir):
                return True
            existing = ""
            if os.path.isfile(path):
                try:
                    with open(
                        path,
                        encoding=enc,
                        errors="surrogateescape",
                        newline="",
                    ) as f:
                        existing = f.read()
                except OSError as e:
                    logger.error(f"Could not read existing commandline.txt: {e}")
                    return False

            write_enc = enc if enc in ("utf-16", "utf-16-be") else "utf-8"
            newline = "\r\n" if "\r\n" in existing else "\n"
            new_content = existing
            if new_content and not new_content.endswith(("\r\n", "\n")):
                new_content += newline
            new_content += f"-nobattleye{newline}"

            temp_path = f"{path}.tmp"
            try:
                with open(
                    temp_path,
                    "w",
                    encoding=write_enc,
                    errors="surrogateescape",
                    newline="",
                ) as f:
                    f.write(new_content)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_path, path)
                logger.info(f"Added -nobattleye to {path}")
                return True
            except PermissionError:
                if os.path.isfile(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                needs_elevation = True
            except (OSError, UnicodeError) as e:
                if os.path.isfile(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                logger.error(f"Could not write to commandline.txt: {e}")
                return False
        else:
            if not os.path.isfile(path):
                return True
            try:
                with open(
                    path, encoding=enc, errors="surrogateescape", newline=""
                ) as f:
                    content = f.read()
            except OSError as e:
                logger.error(f"Could not read commandline.txt: {e}")
                return False

            cleaned_content = _remove_nobattleye_token(content)
            write_enc = enc if enc in ("utf-16", "utf-16-be") else "utf-8"

            temp_path = f"{path}.tmp"
            try:
                if cleaned_content:
                    with open(
                        temp_path,
                        "w",
                        encoding=write_enc,
                        errors="surrogateescape",
                        newline="",
                    ) as f:
                        f.write(cleaned_content)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(temp_path, path)
                    logger.info(f"Removed -nobattleye from {path}")
                else:
                    os.remove(path)
                    logger.info(f"Removed empty commandline.txt at {path}")
                return True
            except PermissionError:
                if os.path.isfile(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                needs_elevation = True
            except (OSError, UnicodeError) as e:
                if os.path.isfile(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                logger.error(f"Could not update/delete commandline.txt: {e}")
                return False

    if needs_elevation:
        if enable:
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
        else:
            logger.info(
                f"Permission denied modifying {path}; requesting UAC elevation..."
            )
            if cleaned_content:
                if _elevated_write_file(path, cleaned_content, write_enc):
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

    return False
