"""Build coons.exe — a tiny native launcher for Coons DXF Viewer (Windows).

Windows' "Open with" dialog will not offer a handler whose command is a bare
interpreter like pythonw.exe, so double-click association needs a real .exe.
This compiles a ~5 KB C# stub with the .NET Framework compiler that ships with
Windows — no PyInstaller, no toolchain to install.

    python build_launcher.py

The stub finds coons.py next to itself, so you can move the folder freely; only
the Python interpreter path is baked in at build time.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ICON = HERE / "docs" / "coons.ico"

SOURCE = r"""
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

static class Coons
{
    [STAThread]
    static int Main(string[] args)
    {
        string dir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        string script = Path.Combine(dir, "coons.py");
        if (!File.Exists(script))
        {
            MessageBox.Show("coons.py not found next to coons.exe:\n" + script,
                            "Coons DXF Viewer", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }

        string python = @"__PYTHONW__";
        if (!File.Exists(python)) python = "pythonw.exe";

        StringBuilder cmd = new StringBuilder();
        cmd.Append('"').Append(script).Append('"');
        foreach (string a in args) cmd.Append(" \"").Append(a).Append('"');

        ProcessStartInfo psi = new ProcessStartInfo(python, cmd.ToString());
        psi.UseShellExecute = false;
        psi.WorkingDirectory = dir;
        try
        {
            Process.Start(psi);
        }
        catch (Exception ex)
        {
            MessageBox.Show("Could not start Python:\n" + python + "\n\n" + ex.Message,
                            "Coons DXF Viewer", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        return 0;
    }
}
"""


def find_csc() -> Path:
    root = Path(r"C:\Windows\Microsoft.NET\Framework64")
    candidates = sorted(root.glob("v4*/csc.exe"), reverse=True)
    if not candidates:
        raise SystemExit("csc.exe not found — is the .NET Framework 4 present?")
    return candidates[0]


def pythonw() -> str:
    exe = Path(sys.executable)
    windowed = exe.with_name("pythonw.exe")
    return str(windowed if windowed.exists() else exe)


def make_icon(path: Path) -> bool:
    """Draw a small flat-pattern glyph: white outline, dashed amber bend."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False

    size = 256
    img = Image.new("RGBA", (size, size), (13, 27, 42, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([28, 68, 228, 188], radius=6, outline=(255, 255, 255, 255), width=7)
    for x in (88, 168):  # dashed bend lines
        for y in range(74, 184, 26):
            d.line([(x, y), (x, y + 14)], fill=(255, 209, 102, 255), width=7)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return True


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("Windows only.")

    has_icon = make_icon(ICON)
    out = HERE / "coons.exe"

    with tempfile.TemporaryDirectory() as tmp:
        cs = Path(tmp) / "coons.cs"
        cs.write_text(SOURCE.replace("__PYTHONW__", pythonw()), encoding="utf-8")

        cmd = [
            str(find_csc()),
            "/nologo",
            "/target:winexe",
            "/optimize+",
            f"/out:{out}",
            "/r:System.Windows.Forms.dll",
        ]
        if has_icon:
            cmd.append(f"/win32icon:{ICON}")
        cmd.append(str(cs))

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            sys.stderr.write(result.stdout + result.stderr)
            return result.returncode

    print(f"built {out} ({out.stat().st_size} bytes), python = {pythonw()}")
    print("next: python install_association.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
