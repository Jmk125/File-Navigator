# Project Navigator - Python Desktop App

A native desktop file navigator built with [PySide6](https://doc.qt.io/qtforpython/) (Qt for Python). No browser, no HTML/JS, no local web server - just a Python GUI app, packaged into a Windows `.exe` with PyInstaller.

## Layout

- **Left pane** - your projects, Windows-Explorer-Quick-Access style. Click a project to see its folders in the main area.
- **Main area** - either the selected project's quick access folders (as a grid of tiles), or, once you open one, a traditional file browser (breadcrumb, sortable columns, type-to-filter).

## Key features

- **Type-ahead filtering** - once you're browsing a folder, just start typing; the filter box grabs focus automatically, no need to click into it first.
- **Escape to back out** - press `Esc` to clear the filter, then close the file browser, then deselect the project, one step at a time.
- **Number-key hotkeys** - each project's quick access folders are numbered 1-9 (shown as a small badge on the folder icon). Press the number to jump straight in.
- **Drag to reassign hotkeys** - drag a folder tile to reorder it; its position is its hotkey number.
- **Inconspicuous management controls** - project cards don't show Edit/Duplicate/Delete by default. Toggle the "✎" button above the project list to reveal them.
- Recent files, "Open in Explorer", "Add current folder to quick access", and project duplication all carry over from the original version.

## Data location

Your project/recent-file data is saved as JSON, same location and format as before:

- Windows: `%APPDATA%\ProjectNavigator\`
- macOS: `~/Library/Application Support/ProjectNavigator/`
- Linux: `~/.project-navigator/`

Files: `projects.json`, `recent_files.json`

## Run from source

1. Install Python 3.11 or newer.
2. Double-click `run.bat` (Windows) - the first run creates a `.venv` folder and installs dependencies.

Or manually:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Build a Windows EXE

Double-click `build-exe.bat`, or run:

```bash
pyinstaller --onefile --windowed --name "Project Navigator" app.py
```

The executable will be created at `dist\Project Navigator.exe`. Make a desktop shortcut to it.

## Notes

- Paths like `\\server\share\Project Folder` work directly, as long as you already have permission to access the share.
- File/folder opening uses the OS default handler (`os.startfile` on Windows).
