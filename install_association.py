"""Register Coons DXF Viewer as an app that can open .dxf files (Windows).

Writes to HKEY_CURRENT_USER only — no admin rights, nothing machine-wide, and
fully undoable with --uninstall.

    python build_launcher.py        # build coons.exe first
    python install_association.py
    python install_association.py --uninstall

This does NOT seize the default association. Windows guards the default app
behind a hashed "UserChoice" key that only the shell may write, so finish up in
the shell:

    right-click any .dxf -> Open with -> Choose another app
    -> "Coons DXF Viewer" -> Always use this app

If it still isn't listed, use "Choose an app on your PC" / "Look for another
app on this PC" in that dialog and browse to coons.exe.
"""

from __future__ import annotations

import sys
import winreg
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGID = "Coons.DXFViewer"
APP_EXE = "coons.exe"
FRIENDLY_NAME = "Coons DXF Viewer"
EXT = ".dxf"


def _set(root: str, name: str | None, value: str, kind: int = winreg.REG_SZ) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, root) as key:
        winreg.SetValueEx(key, name, 0, kind, value)


def install() -> None:
    exe = HERE / APP_EXE
    if not exe.exists():
        raise SystemExit(f"{APP_EXE} not found — run: python build_launcher.py")
    command = f'"{exe}" "%1"'

    # The ProgID: what "open a .dxf with Coons" actually means.
    _set(rf"Software\Classes\{PROGID}", None, FRIENDLY_NAME)
    _set(rf"Software\Classes\{PROGID}", "FriendlyTypeName", "AutoCAD Interchange Drawing")
    _set(rf"Software\Classes\{PROGID}\DefaultIcon", None, f"{exe},0")
    _set(rf"Software\Classes\{PROGID}\shell\open\command", None, command)

    # The application registration — this is what makes Windows list the app by
    # name in the "Open with" dialog rather than hiding it.
    app = rf"Software\Classes\Applications\{APP_EXE}"
    _set(app, "FriendlyAppName", FRIENDLY_NAME)
    _set(rf"{app}\DefaultIcon", None, f"{exe},0")
    _set(rf"{app}\shell\open\command", None, command)
    _set(rf"{app}\SupportedTypes", EXT, "")

    # Offer it for .dxf without changing the current default.
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, rf"Software\Classes\{EXT}\OpenWithProgids"
    ) as key:
        winreg.SetValueEx(key, PROGID, 0, winreg.REG_NONE, b"")

    print(f"registered: {command}")
    print()
    print("Now make it the default (Windows requires this step to be done by hand):")
    print(f"  right-click any {EXT} -> Open with -> Choose another app")
    print(f'  -> "{FRIENDLY_NAME}" -> tick "Always use this app" -> OK')
    print()
    print("If it is not listed, pick 'Choose an app on your PC' and browse to:")
    print(f"  {exe}")


def _delete_tree(path: str) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            while True:
                try:
                    _delete_tree(f"{path}\\{winreg.EnumKey(key, 0)}")
                except OSError:
                    break
    except FileNotFoundError:
        return
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
    except OSError:
        pass


def uninstall() -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            rf"Software\Classes\{EXT}\OpenWithProgids",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, PROGID)
    except (FileNotFoundError, OSError):
        pass

    _delete_tree(rf"Software\Classes\{PROGID}")
    _delete_tree(rf"Software\Classes\Applications\{APP_EXE}")
    print("unregistered. Windows falls back to your previous default app.")


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("Windows only — on Linux/macOS use your desktop's MIME tools.")
    if "--uninstall" in sys.argv:
        uninstall()
    else:
        install()
