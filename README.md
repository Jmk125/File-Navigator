# Project Navigator - Python Desktop Version

This is the Option A conversion: the existing Project Navigator interface runs in a desktop window instead of a normal browser tab.

## What changed

- Replaced the Node/Pi server with a local Python backend.
- Kept the existing HTML/CSS/JavaScript UI.
- Added a desktop window using `pywebview`.
- Replaced browser `localStorage` with JSON files stored in your Windows user profile.
- Kept project cards, project colors, quick access folders, folder browsing, recent files, duplicate project, file opening, and Open in Explorer.

## Data location

On Windows, your project/recent-file data is saved here:

```text
%APPDATA%\ProjectNavigator\
```

Files:

```text
projects.json
recent_files.json
```

## Run from source

1. Install Python 3.11 or newer.
2. Double-click `run.bat`.

The first run creates a `.venv` folder and installs dependencies.

## Build a Windows EXE

Double-click:

```text
build-exe.bat
```

The executable will be created here:

```text
dist\Project Navigator\Project Navigator.exe
```

You can make a desktop shortcut to that `.exe`.

## Fallback browser mode

If `pywebview` has trouble on a machine, you can still run the Python backend and open the UI in your default browser:

```bash
python app.py --browser
```

## Notes

- Paths like `\\server\share\Project Folder` should work directly from your Windows workstation as long as you already have permission to access the share.
- Opening files happens on the local workstation, which is what you wanted after removing the Pi/server architecture.
- This is still using the web UI internally, but the user experience is a standalone desktop app window.
