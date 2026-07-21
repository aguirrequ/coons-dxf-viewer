"""Register Coons DXF Viewer as an app that can open .dxf files (Windows).

Writes a ProgID under HKEY_CURRENT_USER only — no admin rights, nothing
machine-wide, and fully undoable with --uninstall.

    python install_association.py
    python install_association.py --uninstall

This does NOT steal the default association. Windows guards the default app
choice with a hashed "UserChoice" key that only the shell itself may write, so
after running this, make Coons the default the supported way:

    right-click any .dxf -> Open with -> Choose another app
    -> "Coons DXF Viewer" -> Always use this app
"""

from __future__ import annotations

import sys
import winreg
from pathlib import Path

PROGID = "Coons.DXFViewer"
FRIENDLY_NAME = "Coons DXF Viewer"
EXT = ".dxf"


def launcher() -> str:
    """pythonw.exe if available (no console window), else python.exe."""
    exe = Path(sys.executable)
    windowed = exe.with_name("pythonw.exe")
    return str(windowed if windowed.exists() else exe)


def install() -> None:
    script = Path(__file__).with_name("coons.py").resolve()
    if not script.exists():
        raise SystemExit(f"coons.py not found next to this script: {script}")
    command = f'"{launcher()}" "{script}" "%1"'

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROGID}") as k:
        winreg.SetValueEx(k, None, 0, winreg.REG_SZ, FRIENDLY_NAME)
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROGID}\shell\open\command"
    ) as k:
        winreg.SetValueEx(k, None, 0, winreg.REG_SZ, command)

    # Offer it in the "Open with" list for .dxf without changing the default.
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, rf"Software\Classes\{EXT}\OpenWithProgids"
    ) as k:
        winreg.SetValueEx(k, PROGID, 0, winreg.REG_NONE, b"")

    print(f"registered: {command}")
    print()
    print("Now make it the default (one time, Windows requires you to do this):")
    print(f"  right-click any {EXT} file -> Open with -> Choose another app")
    print(f'  -> "{FRIENDLY_NAME}" -> check "Always use this app" -> OK')


def uninstall() -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            rf"Software\Classes\{EXT}\OpenWithProgids",
            0,
            winreg.KEY_SET_VALUE,
        ) as k:
            winreg.DeleteValue(k, PROGID)
    except FileNotFoundError:
        pass

    for sub in (
        rf"Software\Classes\{PROGID}\shell\open\command",
        rf"Software\Classes\{PROGID}\shell\open",
        rf"Software\Classes\{PROGID}\shell",
        rf"Software\Classes\{PROGID}",
    ):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
        except FileNotFoundError:
            pass
    print("unregistered. Windows will fall back to your previous default app.")


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("Windows only — on Linux/macOS use your desktop's MIME tools.")
    if "--uninstall" in sys.argv:
        uninstall()
    else:
        install()
