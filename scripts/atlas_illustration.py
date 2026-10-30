"""Editable SVG illustration of the six DataJevBench decision categories."""

from html import escape
import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess


WIDTH, HEIGHT = 1600, 1120
# Keep export resolution separate from the 800 × 560 README display size.
# Render directly from vectors at 4× display resolution for high-density screens.
PNG_WIDTH, PNG_HEIGHT = WIDTH * 2, HEIGHT * 2
INK = "#334155"
MUTED = "#7a828c"
LINE = "#cfd7e5"
PAPER = "#ffffff"
SUBSETS = {
    "D1": ("Data filtering", "#5081c9"),
    "D2": ("Processing plans", "#8a74c6"),
    "D3": ("Output quality", "#49a098"),
    "D4": ("Information sufficiency", "#c99143"),
    "D5": ("Evidence & privacy", "#c6778c"),
    "D6": ("Workflow control", "#79a15c"),
}
CAPTIONS = {
    "D1": "Apply filtering rules in order.",
    "D2": "Choose a feasible operator sequence.",
    "D3": "Judge fidelity against a human rubric.",
    "D4": "Can the answer be determined?",
    "D5": "Check claims and privacy constraints.",
    "D6": "Validate the current file before commit.",
}


def text(x, y, value, size=24, color=INK, weight=400, anchor="start"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{escape(value)}</text>')


def rect(x, y, width, height, fill=PAPER, stroke=LINE, radius=12, extra=""):
    return (f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
            f'rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2.5" {extra}/>')


def path(d, color=LINE, width=3, fill="none", extra=""):
    return (f'<path d="{d}" fill="{fill}" stroke="{color}" stroke-width="{width}" '
            f'stroke-linecap="round" stroke-linejoin="round" {extra}/>')


def circle(x, y, r, fill=PAPER, stroke=LINE, width=2.5):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'


def tick(x, y, color, scale=1):
    return f'<g transform="translate({x} {y}) scale({scale})">{path("M -10 0 L -3 7 L 12 -9", color)}</g>'


def document(x, y, color=LINE, width=62, height=86):
    return "".join([
        rect(x, y, width, height, stroke=color, radius=9),
        path(f"M {x+14} {y+24} H {x+width-14} M {x+14} {y+36} H {x+width-20} M {x+14} {y+48} H {x+width-14}", LINE, 2.5),
    ])


def pill(x, y, label, color, active=False, width=118):
    return "".join([
        rect(x, y, width, 48, PAPER, color if active else LINE, 11),
        text(x+width/2, y+31, label, 24, color if active else MUTED, 500, "middle"),
    ])


def filtering(color):
    return "".join([
        path("M 113 90 H 206 M 278 90 H 312 V 46 H 350", color),
        path("M 312 90 V 137 H 350", LINE),
        '<g transform="rotate(-9 75 81)">', document(36, 33, width=62), '</g>',
        document(46, 39, width=62), document(58, 47, color, width=62),
        circle(242, 90, 36, "#ffffff", color),
        path("M 223 76 H 261 L 248 93 V 108 L 237 114 V 93 Z", color, 3),
        circle(312, 46, 4, color, PAPER, 2),
        pill(350, 22, "Keep", color, True),
        pill(350, 113, "Drop", color),
        text(90, 169, "Records", 23, MUTED, anchor="middle"),
        text(242, 169, "Assess", 23, MUTED, anchor="middle"),
    ])


def processing(color):
    return "".join([
        path("M 99 92 H 135 V 48 H 174", color),
        path("M 135 92 V 138 H 174", LINE),
        document(34, 49, color),
        text(65, 110, "</>", 22, color, 500, "middle"),
        rect(174, 22, 225, 53, "#ffffff", color, 11),
        text(286, 56, "Clean → Split", 24, color, 500, "middle"),
        rect(174, 112, 225, 53, PAPER, LINE, 11),
        text(286, 146, "Split → Clean", 24, MUTED, 400, "middle"),
        path("M 399 48 H 431", color), circle(452, 48, 21, "#ffffff", color), tick(452, 48, color),
        path("M 399 138 H 431", LINE), circle(452, 138, 21),
        path("M 445 131 L 459 145 M 459 131 L 445 145", LINE),
        text(66, 174, "Input", 23, MUTED, anchor="middle"),
    ])


def quality(color):
    return "".join([
        path("M 110 90 H 150 V 55 H 193", color),
        path("M 150 90 V 128 H 337", LINE),
        document(43, 42, width=67, height=96),
        text(76, 174, "Source", 23, MUTED, anchor="middle"),
        rect(193, 22, 103, 126, "#ffffff", color, 12),
        text(211, 51, "A", 22, color, 600),
        path("M 211 70 H 278 M 211 83 H 270 M 211 96 H 277 M 211 109 H 257", color, 2.5),
        circle(279, 25, 17, PAPER, color), tick(279, 25, color, .75),
        rect(337, 50, 103, 98, PAPER, LINE, 12),
        text(355, 79, "B", 22, MUTED, 600),
        path("M 355 98 H 422 M 355 111 H 414 M 355 124 H 399", LINE, 2.5),
        text(317, 174, "Compare outputs", 23, MUTED, anchor="middle"),
    ])


def sufficiency(color):
    return "".join([
        rect(32, 25, 239, 129, PAPER, LINE, 11),
        path("M 32 68 H 271 M 32 111 H 271 M 194 25 V 154", LINE, 2),
        text(49, 54, "Revenue", 23, MUTED), text(232, 54, "120", 23, INK, anchor="middle"),
        text(49, 97, "Costs", 23, MUTED), text(232, 97, "80", 23, INK, anchor="middle"),
        text(49, 140, "Tax", 23, MUTED),
        rect(207, 119, 49, 28, "#f2f1fa", color, 5, 'stroke-dasharray="4 4"'),
        text(232, 141, "?", 24, color, 500, "middle"),
        path("M 274 90 H 342", color, 3, extra='stroke-dasharray="5 7"'),
        circle(386, 90, 39, "#ffffff", color),
        text(386, 105, "?", 45, color, 400, "middle"),
        text(386, 170, "Enough?", 23, MUTED, anchor="middle"),
    ])


def evidence(color):
    return "".join([
        path("M 124 84 H 205 M 284 84 H 352", LINE),
        document(54, 30, width=70, height=111),
        rect(69, 91, 41, 10, "#9ba7b7", "none", 3),
        rect(69, 109, 29, 8, "#cbd3df", "none", 2),
        circle(242, 77, 30, "#ffffff", color),
        path("M 263 99 L 284 120", color, 5),
        tick(242, 77, color, 1.1),
        path("M 388 38 L 422 51 V 83 C 422 106 408 121 388 132 C 368 121 354 106 354 83 V 51 Z", color, 3, "#ffffff"),
        rect(373, 78, 30, 25, PAPER, color, 5),
        path("M 379 78 V 69 A 9 9 0 0 1 397 69 V 78", color, 3),
        circle(388, 90, 2.5, color, color, 1),
        text(89, 174, "Claim", 23, MUTED, anchor="middle"),
        text(245, 174, "Verify", 23, MUTED, anchor="middle"),
        text(388, 174, "Protect", 23, MUTED, anchor="middle"),
    ])


def workflow(color):
    return "".join([
        path("M 128 90 H 210 M 280 90 H 342", color),
        '<g opacity=".65">', rect(30, 24, 64, 82, "#f3f5f9", LINE, 9),
        text(61, 48, "v1", 21, MUTED, anchor="middle"), tick(61, 78, LINE, .8), '</g>',
        rect(62, 52, 66, 89, PAPER, color, 9),
        text(95, 89, "v2", 26, color, 600, "middle"),
        path("M 77 108 H 113 M 77 119 H 101", LINE, 2.5),
        circle(245, 90, 36, "#ffffff", color), tick(245, 90, color, 1.35),
        pill(342, 66, "Commit", color, width=132),
        text(95, 174, "Current", 23, MUTED, anchor="middle"),
        text(245, 174, "Validate", 23, MUTED, anchor="middle"),
    ])


ILLUSTRATIONS = {
    "D1": filtering, "D2": processing, "D3": quality,
    "D4": sufficiency, "D5": evidence, "D6": workflow,
}


def distribution_svg(subsets):
    if [item["id"] for item in subsets] != list(SUBSETS):
        raise ValueError("Unexpected DataJevBench subset order")
    total = sum(item["count"] for item in subsets)
    description = "; ".join(f'{s["id"]} {SUBSETS[s["id"]][0]} {s["count"]} tasks' for s in subsets)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc" font-family="DejaVu Sans,Arial,sans-serif">',
        '<title id="title">DataJevBench: six kinds of data decisions</title>',
        f'<desc id="desc">{escape(description)}. Illustrative data workflow decisions.</desc>',
        '<defs><pattern id="dots" width="18" height="18" patternUnits="userSpaceOnUse"><circle cx="3" cy="3" r=".8" fill="#dce2ee" opacity=".55"/></pattern></defs>',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        f'<rect x="600" y="24" width="400" height="{HEIGHT - 48}" rx="23" fill="#ffffff"/>',
    ]
    for index, subset in enumerate(subsets):
        code = subset["id"]
        title, color = SUBSETS[code]
        x, y = (24 if index < 3 else 1024), 24 + (index % 3) * 364
        parts.extend([
            f'<g transform="translate({x} {y})">',
            rect(0, 0, 552, 340, "#ffffff", "#dce2ec", 18),
            f'<rect x="0" y="14" width="5" height="312" rx="2.5" fill="{color}"/>',
            text(28, 51, code, 26, color, 600),
            text(76, 51, title, 26, INK, 500),
            text(524, 51, f'{subset["count"]} · {subset["count"] / total:.0%}', 23, MUTED, 500, "end"),
            '<g transform="translate(24 84)">',
            rect(0, 0, 504, 188, "#f7f7fc", "#e9edf3", 13),
            '<rect width="504" height="188" rx="13" fill="url(#dots)"/>',
            ILLUSTRATIONS[code](color), '</g>',
            text(28, 313, CAPTIONS[code], 24, MUTED), '</g>',
        ])
    parts.append('<g transform="translate(0 68)">')
    angle = -90
    for subset in subsets:
        span = 360 * subset["count"] / total
        a, b = math.radians(angle + .65), math.radians(angle + span - .65)
        x1, y1 = 800 + 134*math.cos(a), 430 + 134*math.sin(a)
        x2, y2 = 800 + 134*math.cos(b), 430 + 134*math.sin(b)
        parts.append(path(f'M {x1:.3f} {y1:.3f} A 134 134 0 0 1 {x2:.3f} {y2:.3f}', SUBSETS[subset['id']][1], 46, extra='style="stroke-linecap:butt"'))
        angle += span
    parts.extend([
        text(800, 442, str(total), 76, INK, 500, "middle"),
        text(800, 479, "decisions", 25, MUTED, anchor="middle"),
        text(800, 639, "480 Choice · 20 Score", 24, MUTED, anchor="middle"),
        text(800, 685, "EN 60% · ZH 40%", 24, MUTED, anchor="middle"),
        '</g></svg>',
    ])
    return "\n".join(parts) + "\n"


def render_atlas(subsets, output_dir):
    """Build the illustrations from public subset metadata."""
    if not shutil.which("rsvg-convert"):
        raise RuntimeError("PNG export requires rsvg-convert (librsvg)")
    output_dir.mkdir(parents=True, exist_ok=True)
    svg_path = output_dir / "task-distribution.svg"
    svg_path.write_text(distribution_svg(subsets), encoding="utf-8")
    subprocess.run(["rsvg-convert", "-w", str(PNG_WIDTH), "-h", str(PNG_HEIGHT), str(svg_path),
                    "-o", str(output_dir / "task-atlas.png")], check=True)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Regenerate the public subset illustration")
    parser.add_argument("--manifest", type=Path, default=root / "releases/v0.5/manifest.json")
    parser.add_argument("--output-dir", type=Path, default=root / "assets")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    subsets = [{"id": key, "count": manifest["by_subset"][key]} for key in SUBSETS]
    render_atlas(subsets, args.output_dir)
