"""Plain file operations (copy / move / trash / rename) used by the file browser."""
from __future__ import annotations

import os
import shutil


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


def trash(paths: list[str], permanent: bool = False) -> tuple[int, list[str]]:
    """Send paths to the Recycle Bin / Trash (or delete for good if permanent)."""
    done = 0
    errors: list[str] = []
    for path in paths:
        try:
            if permanent:
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            else:
                from send2trash import send2trash
                send2trash(os.path.normpath(path))
            done += 1
        except Exception as exc:  # send2trash raises its own error types
            errors.append(f"{os.path.basename(path)}: {exc}")
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
