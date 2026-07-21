"""Generate demo_part.dxf — a fake sheet-metal flat pattern.

Writes a U-channel bracket using the same layer names Fusion 360 exports, so
the viewer can be tried out (and the README screenshot regenerated) without any
real part file.

    python examples/demo_part.py
"""

from pathlib import Path

import ezdxf

WIDTH, HEIGHT = 240.0, 120.0
FLANGE = 40.0  # distance from each end to its bend line
KERF = 3.0  # half-width of the bend relief zone


def build() -> ezdxf.document.Drawing:
    doc = ezdxf.new(setup=True)
    doc.header["$INSUNITS"] = 4  # millimetres
    for name in ("OUTER_PROFILES", "INTERIOR_PROFILES", "BEND", "BEND_EXTENT"):
        doc.layers.add(name)
    msp = doc.modelspace()

    msp.add_lwpolyline(
        [(0, 0), (WIDTH, 0), (WIDTH, HEIGHT), (0, HEIGHT)],
        close=True,
        dxfattribs={"layer": "OUTER_PROFILES"},
    )

    for x in (30.0, WIDTH - 30.0):
        for y in (25.0, HEIGHT - 25.0):
            msp.add_circle((x, y), 5.0, dxfattribs={"layer": "INTERIOR_PROFILES"})
    msp.add_lwpolyline(
        [(WIDTH / 2 - 30, 45), (WIDTH / 2 + 30, 45), (WIDTH / 2 + 30, 75), (WIDTH / 2 - 30, 75)],
        close=True,
        dxfattribs={"layer": "INTERIOR_PROFILES"},
    )

    for x in (FLANGE, WIDTH - FLANGE):
        msp.add_line((x, 0), (x, HEIGHT), dxfattribs={"layer": "BEND"})
        for offset in (-KERF, KERF):
            msp.add_line(
                (x + offset, 0),
                (x + offset, HEIGHT),
                dxfattribs={"layer": "BEND_EXTENT"},
            )

    return doc


if __name__ == "__main__":
    out = Path(__file__).with_name("demo_part.dxf")
    build().saveas(out)
    print(f"wrote {out}")
