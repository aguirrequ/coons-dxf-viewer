"""Coons DXF Viewer — white linework on a dark background.

Named for Steven Coons, whose surface patches turned CAD from drafting
automation into real geometric modelling.

Styles entities by layer name, so Fusion 360 sheet-metal flat patterns show
bend lines dashed and bend extents as faint dotted lines, and reports the
overall bounding box in the drawing's own units.

Usage:
    python coons.py                 # opens a file picker
    python coons.py drawing.dxf     # opens that file
    (or drag a .dxf onto coons.bat)

Controls:
    scroll wheel  zoom at cursor
    drag          pan (matplotlib pan tool also works via the toolbar)
    e             show/hide bend-extent construction lines
    b             cycle background: navy -> black -> dark grey
    r             reset view
    l             show/hide legend
    q             quit
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import ezdxf
import matplotlib.pyplot as plt
from ezdxf import bbox
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.config import (
    BackgroundPolicy,
    ColorPolicy,
    Configuration,
    LineweightPolicy,
)
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from matplotlib.lines import Line2D

BACKGROUNDS = ["#0d1b2a", "#000000", "#1c1c1c"]  # navy, black, dark grey
FOREGROUND = "#ffffff"

# First matching pattern wins; layer names are matched case-insensitively.
# Fusion 360 flat-pattern DXFs use OUTER_PROFILES / INTERIOR_PROFILES / BEND /
# BEND_EXTENT. Anything unrecognised falls through to the last rule.
LAYER_STYLES: list[tuple[str, dict]] = [
    (
        r"bend[_ ]?extent|extent",
        {
            "linestyle": (0, (1, 4)),
            "color": "#5f7d95",
            "linewidth": 0.7,
            "label": "bend extent",
            "optional": True,
        },
    ),
    (
        r"bend",
        {
            "linestyle": (0, (7, 4)),
            "color": "#ffd166",
            "linewidth": 0.8,
            "label": "bend line",
        },
    ),
    (
        r"interior|inner|hole",
        {"linestyle": "-", "color": FOREGROUND, "linewidth": 1.0, "label": "interior"},
    ),
    (
        r".*",
        {"linestyle": "-", "color": FOREGROUND, "linewidth": 1.2, "label": "profile"},
    ),
]


# $INSUNITS header codes -> display suffix.
UNIT_NAMES = {
    0: "",
    1: "in",
    2: "ft",
    4: "mm",
    5: "cm",
    6: "m",
    11: "Å",
    12: "nm",
    13: "µm",
    14: "dm",
}


def style_for(layer: str) -> dict:
    for pattern, style in LAYER_STYLES:
        if re.search(pattern, layer, re.IGNORECASE):
            return style
    return LAYER_STYLES[-1][1]


def set_taskbar_identity() -> None:
    """Claim our own taskbar slot instead of inheriting Python's.

    Windows groups taskbar buttons by AppUserModelID; without this the window
    shows the Python icon no matter what icon the window itself carries. Must
    run before any window is created.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Coons.DXFViewer")
    except Exception:
        pass


def apply_window_icon(fig) -> None:
    """Replace matplotlib's own window icon with ours.

    matplotlib sets its logo via Tk's `iconphoto`, which outranks `iconbitmap`
    on an existing window — so overriding it means using `iconphoto` too, with
    the PhotoImages kept alive for as long as the window is.
    """
    icon = Path(__file__).resolve().parent / "docs" / "coons.ico"
    if not icon.exists():
        return
    window = getattr(fig.canvas.manager, "window", None)
    if window is None:
        return

    try:  # Tk backends
        from PIL import Image, ImageTk

        images = []
        for size in (256, 64, 48, 32, 16):  # largest first, as Tk expects
            frame = Image.open(icon)
            frame.size = (size, size)
            images.append(ImageTk.PhotoImage(frame.convert("RGBA"), master=window))
        window.iconphoto(False, *images)
        window._coons_icons = images  # without this they are garbage collected
        try:
            window.iconbitmap(default=str(icon))  # also covers child dialogs
        except Exception:
            pass
        return
    except Exception:
        pass

    try:  # Qt backends
        from matplotlib.backends.qt_compat import QtGui

        window.setWindowIcon(QtGui.QIcon(str(icon)))
    except Exception:
        pass


def pick_file() -> Path | None:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    name = filedialog.askopenfilename(
        title="Open DXF file",
        filetypes=[("DXF files", "*.dxf"), ("All files", "*.*")],
    )
    root.destroy()
    return Path(name) if name else None


def _artists(ax) -> list:
    return list(ax.collections) + list(ax.patches) + list(ax.lines) + list(ax.texts)


def _apply(artist, style: dict) -> None:
    for setter, key in (
        ("set_linestyle", "linestyle"),
        ("set_linewidth", "linewidth"),
    ):
        fn = getattr(artist, setter, None)
        if fn is not None:
            try:
                fn(style[key])
            except Exception:
                pass
    for setter in ("set_color", "set_edgecolor"):
        fn = getattr(artist, setter, None)
        if fn is not None:
            try:
                fn(style["color"])
                break
            except Exception:
                pass


def measure(entities, units: str) -> str | None:
    """Overall bounding-box size of the real geometry, as display text."""
    try:
        box = bbox.extents(entities, fast=False)
    except Exception:
        return None
    if not box.has_data:
        return None
    width, height, _ = box.size
    suffix = f" {units}" if units else ""
    return f"bounding box\n{width:.2f} × {height:.2f}{suffix}"


def render(path: Path, ax, bg: str) -> tuple[dict[str, list], str | None]:
    """Draw the modelspace layer by layer.

    Returns ({style label: [artists]}, bounding-box text).
    """
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    units = UNIT_NAMES.get(doc.header.get("$INSUNITS", 0), "")

    config = Configuration(
        color_policy=ColorPolicy.CUSTOM,
        custom_fg_color=FOREGROUND,
        background_policy=BackgroundPolicy.CUSTOM,
        custom_bg_color=bg + "ff",
        lineweight_policy=LineweightPolicy.RELATIVE_FIXED,
    )

    ctx = RenderContext(doc)
    ctx.set_current_layout(msp)
    backend = MatplotlibBackend(ax)
    frontend = Frontend(ctx, backend, config=config)

    by_layer: dict[str, list] = {}
    for entity in msp:
        by_layer.setdefault(entity.dxf.layer, []).append(entity)

    groups: dict[str, list] = {}
    measured: list = []
    for layer, entities in by_layer.items():
        before = set(map(id, _artists(ax)))
        frontend.draw_entities(entities)
        new = [a for a in _artists(ax) if id(a) not in before]

        style = style_for(layer)
        for artist in new:
            _apply(artist, style)
        groups.setdefault(style["label"], []).extend(new)
        if not style.get("optional"):  # construction lines don't set the size
            measured.extend(entities)

    backend.finalize()
    return groups, measure(measured, units)


def main() -> int:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = pick_file()
        if path is None:
            return 0

    if not path.is_file():
        print(f"not a file: {path}")
        return 1

    state = {"bg": 0, "extents": True, "legend": True}
    set_taskbar_identity()
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.canvas.manager.set_window_title(f"Coons DXF Viewer — {path.name}")
    apply_window_icon(fig)
    optional_labels = {s["label"] for _, s in LAYER_STYLES if s.get("optional")}

    def draw() -> None:
        ax.clear()
        bg = BACKGROUNDS[state["bg"]]
        fig.patch.set_facecolor(bg)
        ax.set_facecolor(bg)
        groups, size_text = render(path, ax, bg)

        for label in optional_labels & groups.keys():
            for artist in groups[label]:
                artist.set_visible(state["extents"])

        if state["legend"] and groups:
            handles = []
            for _, style in LAYER_STYLES:
                label = style["label"]
                if label not in groups or label in {h.get_label() for h in handles}:
                    continue
                handles.append(
                    Line2D(
                        [],
                        [],
                        color=style["color"],
                        linestyle=style["linestyle"],
                        linewidth=style["linewidth"],
                        label=label,
                    )
                )
            legend = ax.legend(
                handles=handles,
                loc="upper right",
                facecolor=bg,
                edgecolor="#44586b",
                labelcolor=FOREGROUND,
                framealpha=0.85,
            )
            legend.set_visible(state["legend"])

        if state["legend"] and size_text:
            ax.text(
                0.995,
                0.01,
                size_text,
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                color=FOREGROUND,
                family="monospace",
                fontsize=9,
                linespacing=1.5,
                bbox={
                    "facecolor": bg,
                    "edgecolor": "#44586b",
                    "alpha": 0.85,
                    "boxstyle": "round,pad=0.5",
                },
            )

        ax.set_axis_off()
        ax.set_aspect("equal")
        fig.canvas.draw_idle()

    draw()
    home = (ax.get_xlim(), ax.get_ylim())

    def redraw_keeping_view() -> None:
        xlim, ylim = ax.get_xlim(), ax.get_ylim()
        draw()
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        fig.canvas.draw_idle()

    def on_scroll(event) -> None:
        if event.inaxes is not ax:
            return
        scale = 0.8 if event.button == "up" else 1.25
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        cx, cy = event.xdata, event.ydata
        ax.set_xlim(cx + (x0 - cx) * scale, cx + (x1 - cx) * scale)
        ax.set_ylim(cy + (y0 - cy) * scale, cy + (y1 - cy) * scale)
        fig.canvas.draw_idle()

    def on_key(event) -> None:
        if event.key == "b":
            state["bg"] = (state["bg"] + 1) % len(BACKGROUNDS)
            redraw_keeping_view()
        elif event.key == "e":
            state["extents"] = not state["extents"]
            redraw_keeping_view()
        elif event.key == "l":
            state["legend"] = not state["legend"]
            redraw_keeping_view()
        elif event.key == "r":
            ax.set_xlim(home[0])
            ax.set_ylim(home[1])
            fig.canvas.draw_idle()

    fig.canvas.mpl_connect("scroll_event", on_scroll)
    fig.canvas.mpl_connect("key_press_event", on_key)
    plt.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
