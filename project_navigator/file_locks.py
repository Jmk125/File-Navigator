"""Find and ask programs to close a file that's open (Windows Restart Manager)."""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

ERROR_MORE_DATA = 234
CCH_RM_SESSION_KEY = 32
# RM_APP_TYPE values we must not shut down on the user's behalf
RM_SERVICE, RM_EXPLORER, RM_CONSOLE, RM_CRITICAL = 3, 4, 5, 1000
MAX_FILES = 500


if sys.platform == "win32":
    class _UniqueProcess(ctypes.Structure):
        _fields_ = [("dwProcessId", wintypes.DWORD), ("ProcessStartTime", wintypes.FILETIME)]

    class _ProcessInfo(ctypes.Structure):
        _fields_ = [
            ("Process", _UniqueProcess),
            ("strAppName", wintypes.WCHAR * 256),
            ("strServiceShortName", wintypes.WCHAR * 64),
            ("ApplicationType", ctypes.c_int),
            ("AppStatus", wintypes.ULONG),
            ("TSSessionId", wintypes.DWORD),
            ("bRestartable", wintypes.BOOL),
        ]


def available() -> bool:
    return sys.platform == "win32"


def _files_under(path: str) -> list[str]:
    if not os.path.isdir(path):
        return [path]
    found: list[str] = []
    for root, _dirs, files in os.walk(path):
        for name in files:
            found.append(os.path.join(root, name))
            if len(found) >= MAX_FILES:
                return found
    return found


class _Session:
    """Restart Manager session registered on the given files."""

    def __init__(self, files: list[str]):
        self.rstrtmgr = ctypes.WinDLL("rstrtmgr")
        self.handle = wintypes.DWORD(0)
        key = ctypes.create_unicode_buffer(CCH_RM_SESSION_KEY + 1)
        if self.rstrtmgr.RmStartSession(ctypes.byref(self.handle), 0, key) != 0:
            raise OSError("couldn't start a Restart Manager session")
        arr = (wintypes.LPCWSTR * len(files))(*files)
        result = self.rstrtmgr.RmRegisterResources(self.handle, len(files), arr, 0, None, 0, None)
        if result != 0:
            self.close()
            raise OSError(f"RmRegisterResources failed ({result})")

    def close(self) -> None:
        self.rstrtmgr.RmEndSession(self.handle)

    def processes(self) -> list:
        needed = wintypes.UINT(0)
        count = wintypes.UINT(0)
        reasons = wintypes.DWORD(0)
        result = self.rstrtmgr.RmGetList(self.handle, ctypes.byref(needed), ctypes.byref(count), None,
                                         ctypes.byref(reasons))
        if result == 0 and needed.value == 0:
            return []
        if result != ERROR_MORE_DATA and result != 0:
            raise OSError(f"RmGetList failed ({result})")
        count = wintypes.UINT(needed.value)
        infos = (_ProcessInfo * count.value)()
        result = self.rstrtmgr.RmGetList(self.handle, ctypes.byref(needed), ctypes.byref(count), infos,
                                         ctypes.byref(reasons))
        if result != 0:
            raise OSError(f"RmGetList failed ({result})")
        return list(infos)[:count.value]


def holders(path: str) -> list[tuple[str, int]]:
    """Programs holding path open, as (name, restart-manager type). Empty if unknown/unsupported."""
    if not available():
        return []
    try:
        session = _Session(_files_under(path))
        try:
            return [(p.strAppName, p.ApplicationType) for p in session.processes()]
        finally:
            session.close()
    except Exception:
        return []


def close_holders(path: str) -> tuple[bool, str]:
    """Politely ask the programs holding path to close it. Returns (ok, message).

    Never forces anything shut: a program that refuses (e.g. an unsaved-changes
    prompt) stays open, and Explorer / services are left alone.
    """
    if not available():
        return False, "Closing programs is only supported on Windows"
    try:
        session = _Session(_files_under(path))
    except Exception as exc:
        return False, str(exc)
    try:
        procs = session.processes()
        if not procs:
            return True, ""
        protected = [p.strAppName for p in procs if p.ApplicationType in (RM_SERVICE, RM_EXPLORER, RM_CONSOLE, RM_CRITICAL)]
        if protected:
            return False, (f"{os.path.basename(path)} is held open by {', '.join(protected)}, "
                           "which can't be closed from here")
        result = session.rstrtmgr.RmShutdown(session.handle, 0, None)  # 0 = ask nicely, don't force
        if result != 0:
            names = ", ".join(p.strAppName for p in procs)
            return False, f"{names} didn't close {os.path.basename(path)} (it may be asking to save)"
        return True, ""
    except Exception as exc:
        return False, str(exc)
    finally:
        session.close()
