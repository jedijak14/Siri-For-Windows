# Building Canopy.exe on Windows

This repository contains `canopy.py`, a frameless PyQt6 voice-assistant panel for Windows.

## Prerequisites (Windows)

1. **Python 3.11+** installed (ensure "Add Python to PATH" is checked).
2. **PyQt6** and **PyInstaller** installed:
   ```powershell
   pip install PyQt6 pyinstaller
   ```

## Build Instructions

Open a terminal or PowerShell in the root of the repository (`/home/user/Siri-For-Windows` on your local machine) and run:

```powershell
pyinstaller --onefile --windowed --name Canopy canopy.py
```

### Flags Explained:
- `--onefile`: Bundles the application and all dependencies into a single `Canopy.exe`.
- `--windowed`: Prevents a console window from appearing when the app starts (required for the frameless panel).
- `--name Canopy`: Sets the output executable name to `Canopy.exe`.

## Output
The executable will be generated in the `dist/` folder:
- `dist/Canopy.exe`

## Running the App
Double-click `Canopy.exe` to launch the panel.
- **Hotkey**: `Alt + Space` (default) toggles the panel.
- **Quit**: `Ctrl + Q` or close the panel.

## Notes
- The code uses Windows-specific APIs (`user32.dll`, `dwmapi.dll`) and will **only** compile and run on Windows.
- The sandbox environment used to store this code is Linux-based, so the `.exe` cannot be generated directly here.
