"""Plain file operations (copy / move / trash / rename) used by the file browser."""
from __future__ import annotations

import os
import shutil
import sys


def unique_destination(dest_dir: str, name: str) -> str:
    """Return a path in dest_dir for name that doesn't exist yet ("a - Copy.txt", "a - Copy (2).txt")."""
    candidate = os.path.join(dest_dir, name)
    if not os.path.lexists(candidate):
        return candidate
    stem, ext = os.path.splitext(name) if not os.path.isdir(os.path.join(dest_dir, name)) else (name, "")
    candidate = os.path.join(dest_dir, f"{stem} - Copy{ext}")
    counter = 2
    while os.path.lexists(candidate):
        candidate = os.path.join(dest_dir, f"{stem} - Copy ({counter}){ext}")
        counter += 1
    return candidate


def _is_same_or_inside(path: str, folder: str) -> bool:
    path = os.path.normcase(os.path.abspath(path))
    folder = os.path.normcase(os.path.abspath(folder))
    return path == folder or folder.startswith(path.rstrip(os.sep) + os.sep)


def transfer(sources: list[str], dest_dir: str, move: bool) -> tuple[int, list[str]]:
    """Copy or move sources into dest_dir. Returns (success_count, error_messages)."""
    done = 0
    errors: list[str] = []
    for src in sources:
        name = os.path.basename(src.rstrip("\\/"))
        try:
            if not os.path.lexists(src):
                raise FileNotFoundError("no longer exists")
            if os.path.isdir(src) and _is_same_or_inside(src, dest_dir):
                raise OSError("can't put a folder inside itself")
            if move and os.path.normcase(os.path.abspath(os.path.dirname(src))) == \
                    os.path.normcase(os.path.abspath(dest_dir)):
                continue  # moving into the folder it's already in
            target = unique_destination(dest_dir, name)
            if move:
                shutil.move(src, target)
            elif os.path.isdir(src) and not os.path.islink(src):
                shutil.copytree(src, target)
            else:
                shutil.copy2(src, target)
            done += 1
        except (OSError, shutil.Error) as exc:
            errors.append(f"{name}: {exc}")
    return done, errors


def delete_one(path: str, permanent: bool) -> None:
    """Delete a single path (Recycle Bin unless permanent). Raises on failure."""
    if permanent:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    else:
        from send2trash import send2trash
        send2trash(os.path.normpath(path))


def _handle_blocks_delete(path: str) -> bool:
    """Windows: True if some other process has path open without allowing deletion."""
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
    ]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    # DELETE access, share everything, OPEN_EXISTING, BACKUP_SEMANTICS (needed to open folders)
    handle = kernel32.CreateFileW(path, 0x10000, 7, None, 3, 0x02000000, None)
    if handle in (None, ctypes.c_void_p(-1).value):
        return ctypes.get_last_error() in (32, 33)
    kernel32.CloseHandle(handle)
    return False


def is_open_elsewhere(path: str) -> bool:
    """True if path (or, for a folder, a file inside it) is held open by another program."""
    if sys.platform != "win32" or not os.path.lexists(path):
        return False
    try:
        if not os.path.isdir(path) or os.path.islink(path):
            return _handle_blocks_delete(path)
        checked = 0
        for root, _dirs, files in os.walk(path):
            for name in files:
                if _handle_blocks_delete(os.path.join(root, name)):
                    return True
                checked += 1
                if checked >= 2000:
                    return False
        return False
    except Exception:
        return False


def is_locked_error(path: str, exc: Exception) -> bool:
    """True if exc means "another program has this open" rather than a real failure."""
    if not os.path.lexists(path):
        return False
    # send2trash reports COM HRESULTs (e.g. 0x80070020), so compare the low 16 bits
    code = getattr(exc, "winerror", None)
    if isinstance(code, int) and (code & 0xFFFF) in (32, 33):  # sharing / lock violation
        return True
    if "being used by another process" in str(exc):
        return True
    return is_open_elsewhere(path)  # access denied, aborted, etc.: ask Windows directly


def trash_split(paths: list[str], permanent: bool = False) -> tuple[int, list[str], list[str]]:
    """Like trash(), but also returns the paths that failed only because they're open elsewhere."""
    done = 0
    errors: list[str] = []
    locked: list[str] = []
    for path in paths:
        try:
            delete_one(path, permanent)
            done += 1
        except Exception as exc:  # send2trash raises its own error types
            if is_locked_error(path, exc):
                locked.append(path)
            else:
                errors.append(f"{os.path.basename(path)}: {exc}")
    return done, errors, locked


def trash(paths: list[str], permanent: bool = False) -> tuple[int, list[str]]:
    """Send paths to the Recycle Bin / Trash (or delete for good if permanent)."""
    done, errors, locked = trash_split(paths, permanent)
    errors += [f"{os.path.basename(p)}: in use by another program" for p in locked]
    return done, errors


def rename(path: str, new_name: str) -> str:
    """Rename path in place; returns the new path. Raises OSError on failure."""
    if not new_name or any(c in new_name for c in '\\/') or new_name in (".", ".."):
        raise OSError("invalid name")
    target = os.path.join(os.path.dirname(path), new_name)
    if os.path.lexists(target) and os.path.normcase(target) != os.path.normcase(path):
        raise FileExistsError(f'"{new_name}" already exists')
    os.rename(path, target)
    return target


def make_folder(parent: str, name: str) -> str:
    if not name or any(c in name for c in '\\/'):
        raise OSError("invalid name")
    target = os.path.join(parent, name)
    os.mkdir(target)
    return target
