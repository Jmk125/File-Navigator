"""Emoji-glyph icon lookup and small text-formatting helpers shared by the views."""
from __future__ import annotations

from datetime import datetime

FILE_ICONS = {
    "pdf": "\U0001F4C4",
    "doc": "\U0001F4DD", "docx": "\U0001F4DD",
    "xls": "\U0001F4CA", "xlsx": "\U0001F4CA",
    "ppt": "\U0001F4FD", "pptx": "\U0001F4FD",
    "txt": "\U0001F4DD",
    "jpg": "\U0001F5BC", "jpeg": "\U0001F5BC", "png": "\U0001F5BC", "gif": "\U0001F5BC",
    "zip": "\U0001F4E6", "rar": "\U0001F4E6",
    "exe": "⚙",
    "mp3": "\U0001F3B5", "wav": "\U0001F3B5",
    "mp4": "\U0001F3AC", "avi": "\U0001F3AC",
}
DEFAULT_FILE_ICON = "\U0001F4C4"
FOLDER_ICON = "\U0001F4C1"


def tint(hex_color: str, alpha: int) -> str:
    """A translucent version of hex_color for use in Qt stylesheets.

    Qt's stylesheet/QColor hex parser treats 8-digit strings as #AARRGGBB
    (alpha first), unlike CSS's #RRGGBBAA - so plain string concatenation
    like f"{hex_color}30" is silently wrong. Use rgba() instead.
    """
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def file_icon(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return FILE_ICONS.get(ext, DEFAULT_FILE_ICON)


def format_file_size(num_bytes: int) -> str:
    if num_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    return f"{round(size, 2)} {units[unit_index]}"


def format_relative_time(timestamp_ms: int) -> str:
    diff_seconds = max(0, (_now_ms() - timestamp_ms) / 1000)
    minutes = int(diff_seconds // 60)
    hours = minutes // 60
    days = hours // 24
    if minutes < 60:
        return f"{minutes}m ago"
    if hours < 24:
        return f"{hours}h ago"
    return f"{days}d ago"


def _now_ms() -> int:
    return int(datetime.now().timestamp() * 1000)


def format_modified(iso_timestamp: str) -> str:
    try:
        dt = datetime.strptime(iso_timestamp, "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso_timestamp
