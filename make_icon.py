"""Generate docs/coons.ico — the app icon.

An icosahedron projected orthographically along a 3-fold axis: hexagonal
silhouette, fully triangulated interior. Edges hidden behind the solid are
drawn dashed in amber, the same technical-drawing convention the viewer uses
for bend lines; visible edges are white on the viewer's navy background.

    python make_icon.py
"""

from __future__ import annotations

import math
from itertools import combinations
from pathlib import Path

from PIL import Image, ImageDraw

BG = (13, 27, 42, 255)  # #0d1b2a — same navy as the viewer
VISIBLE = (255, 255, 255, 255)
HIDDEN = (122, 156, 184, 255)  # slate — quiet enough to survive a 16px icon

SS = 4  # supersampling factor, for smooth edges
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def icosahedron() -> tuple[list, list, list]:
    """Vertices, edges (index pairs) and faces (index triples)."""
    phi = (1 + math.sqrt(5)) / 2
    verts = []
    for a in (-1, 1):
        for b in (-phi, phi):
            verts += [(0, a, b), (a, b, 0), (b, 0, a)]

    def dist(i, j):
        return math.dist(verts[i], verts[j])

    n = len(verts)
    edge_len = min(dist(i, j) for i, j in combinations(range(n), 2))
    close = lambda a, b: abs(a - b) < 1e-9  # noqa: E731

    edges = [(i, j) for i, j in combinations(range(n), 2) if close(dist(i, j), edge_len)]
    faces = [
        (i, j, k)
        for i, j, k in combinations(range(n), 3)
        if close(dist(i, j), edge_len)
        and close(dist(j, k), edge_len)
        and close(dist(i, k), edge_len)
    ]
    return verts, edges, faces


def look_along(normal) -> list[list[float]]:
    """Rotation matrix bringing `normal` onto +Z."""
    nx, ny, nz = normal
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    z = [nx / length, ny / length, nz / length]

    helper = [0.0, 0.0, 1.0] if abs(z[2]) < 0.9 else [1.0, 0.0, 0.0]
    x = [
        helper[1] * z[2] - helper[2] * z[1],
        helper[2] * z[0] - helper[0] * z[2],
        helper[0] * z[1] - helper[1] * z[0],
    ]
    xl = math.sqrt(sum(c * c for c in x))
    x = [c / xl for c in x]
    y = [
        z[1] * x[2] - z[2] * x[1],
        z[2] * x[0] - z[0] * x[2],
        z[0] * x[1] - z[1] * x[0],
    ]
    return [x, y, z]


def dashed(draw, p0, p1, width, colour, dash, gap) -> None:
    (x0, y0), (x1, y1) = p0, p1
    total = math.hypot(x1 - x0, y1 - y0)
    if total == 0:
        return
    ux, uy = (x1 - x0) / total, (y1 - y0) / total
    pos = 0.0
    while pos < total:
        end = min(pos + dash, total)
        draw.line(
            [(x0 + ux * pos, y0 + uy * pos), (x0 + ux * end, y0 + uy * end)],
            fill=colour,
            width=width,
        )
        pos = end + gap


def build(size: int = 256) -> Image.Image:
    verts, edges, faces = icosahedron()

    # View down a face normal -> hexagonal silhouette with 3-fold symmetry.
    a, b, c = faces[0]
    normal = [sum(verts[i][k] for i in (a, b, c)) / 3 for k in range(3)]
    rot = look_along(normal)
    pts3 = [
        [sum(rot[r][k] * v[k] for k in range(3)) for r in range(3)] for v in verts
    ]

    # Spin so a silhouette vertex sits at the top, as in a drafting view.
    spin = math.pi / 2 - math.atan2(pts3[0][1], pts3[0][0])
    cs, sn = math.cos(spin), math.sin(spin)
    pts3 = [[p[0] * cs - p[1] * sn, p[0] * sn + p[1] * cs, p[2]] for p in pts3]

    # Face visibility: the viewer sits at +Z looking back toward the origin.
    normals = {}
    for face in faces:
        centre = [sum(pts3[i][k] for i in face) / 3 for k in range(3)]
        normals[face] = centre[2]  # convex solid: centroid Z sign == facing

    hidden = set()
    for edge in edges:
        touching = [f for f in faces if edge[0] in f and edge[1] in f]
        if all(normals[f] < 0 for f in touching):
            hidden.add(edge)

    canvas = size * SS
    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = canvas * 0.16
    draw.rounded_rectangle([0, 0, canvas - 1, canvas - 1], radius=radius, fill=BG)

    scale = canvas * 0.40 / max(math.hypot(p[0], p[1]) for p in pts3)
    half = canvas / 2
    flat = [(half + p[0] * scale, half - p[1] * scale) for p in pts3]

    # Small icons need proportionally heavier strokes, and the hidden edges
    # just turn to mush below ~32px, so drop them there.
    width = max(2, int(canvas * (0.016 if size >= 48 else 0.026)))
    show_hidden = size >= 32

    for edge in edges:
        p0, p1 = flat[edge[0]], flat[edge[1]]
        if edge in hidden:
            if show_hidden:
                dashed(draw, p0, p1, max(2, int(width * 0.8)), HIDDEN,
                       dash=canvas * 0.035, gap=canvas * 0.025)
        else:
            draw.line([p0, p1], fill=VISIBLE, width=width)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    out = Path(__file__).with_name("docs") / "coons.ico"
    out.parent.mkdir(parents=True, exist_ok=True)

    # Draw every size at its own scale rather than downsampling one master, so
    # the 16px tile is a legible drawing instead of a smudge.
    frames = [build(w) for w, _ in SIZES]
    master = frames[-1]
    master.save(out, sizes=SIZES, append_images=frames[:-1])
    master.save(out.with_suffix(".png"))
    print(f"wrote {out} ({len(frames)} sizes)")


if __name__ == "__main__":
    main()
