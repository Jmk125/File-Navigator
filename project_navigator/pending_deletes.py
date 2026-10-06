"""Files that couldn't be deleted because they're open elsewhere; retried until they close."""
from __future__ import annotations

import os
import threading

from PySide6.QtCore import QObject, QTimer, Signal

from . import file_locks, fileops

RETRY_MS = 1500


def _key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


class PendingDeletes(QObject):
    changed = Signal()
    deleted = Signal(str)       # path
    failed = Signal(str, str)   # path, message
    closeFailed = Signal(str)   # message: the program holding the file wouldn't close it

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: dict[str, tuple[str, bool]] = {}  # key -> (path, permanent)
        self._timer = QTimer(self)
        self._timer.setInterval(RETRY_MS)
        self._timer.timeout.connect(self._retry)

    def add(self, path: str, permanent: bool, close: bool = False) -> None:
        """Schedule path for deletion once it's closed; close=True also asks the holder to close it."""
        self._items[_key(path)] = (path, permanent)
        self._timer.start()
        self.changed.emit()
        if close:
            threading.Thread(target=self._close_holders, args=(path,), daemon=True).start()

    def _close_holders(self, path: str) -> None:
        ok, message = file_locks.close_holders(path)  # may block while the program shuts down
        if not ok and message:
            self.closeFailed.emit(message)

    def cancel(self, path: str) -> None:
        if self._items.pop(_key(path), None) is not None:
            if not self._items:
                self._timer.stop()
            self.changed.emit()

    def is_pending(self, path: str) -> bool:
        return _key(path) in self._items

    def count(self) -> int:
        return len(self._items)

    def paths(self) -> list[str]:
        return [p for p, _ in self._items.values()]

    def _retry(self) -> None:
        for key, (path, permanent) in list(self._items.items()):
            if not os.path.lexists(path):
                self._finish(key)  # gone already (moved/deleted elsewhere)
                continue
            try:
                fileops.delete_one(path, permanent)
            except Exception as exc:
                if fileops.is_locked_error(path, exc):
                    continue  # still open; try again next tick
                self._finish(key)
                self.failed.emit(path, f"{os.path.basename(path)}: {exc}")
                continue
            self._finish(key)
            self.deleted.emit(path)

    def _finish(self, key: str) -> None:
        self._items.pop(key, None)
        if not self._items:
            self._timer.stop()
        self.changed.emit()


_manager: PendingDeletes | None = None


def get_manager() -> PendingDeletes:
    """Shared instance (created lazily so a QApplication exists first)."""
    global _manager
    if _manager is None:
        _manager = PendingDeletes()
    return _manager
