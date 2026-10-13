"""Create CanyonGlow's original geometric icon (optional: pip install pillow).

Copyright (c) 2026 rattensuppe
SPDX-License-Identifier: MIT
No photographs, manufacturer logos or external artwork are used.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "picture"
SCALE = 4

WALLS = (
    ("#247d9b", ((48, 62), (101, 88), (94, 145), (126, 203), (73, 180), (48, 127))),
    ("#45c7dc", ((48, 62), (101, 88), (88, 108), (63, 95))),
    ("#414c9a", ((208, 62), (160, 92), (173, 136), (152, 178), (130, 203), (189, 180), (208, 126))),
    ("#7883dc", ((208, 62), (160, 92), (167, 113), (193, 95))),
)
LIGHTS = (
    ("#57edb6", ((125, 58), (116, 111), (141, 149), (121, 195))),
    ("#54cfff", ((139, 62), (130, 111), (155, 149), (135, 197))),
    ("#fa6aa9", ((153, 66), (144, 111), (169, 149), (149, 199))),
)


def points_text(points):
    return " ".join(f"{x},{y}" for x, y in points)


def main():
    OUT.mkdir(exist_ok=True)
    canvas = Image.new("RGBA", (256 * SCALE, 256 * SCALE))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((12 * SCALE, 12 * SCALE, 244 * SCALE, 244 * SCALE),
                           radius=48 * SCALE, fill="#101c30")
    for colour, points in WALLS:
        draw.polygon([(x * SCALE, y * SCALE) for x, y in points], fill=colour)
    for colour, points in LIGHTS:
        scaled = [(x * SCALE, y * SCALE) for x, y in points]
        draw.line(scaled, fill=colour, width=8 * SCALE, joint="curve")
        for x, y in scaled:
            draw.ellipse((x - 4 * SCALE, y - 4 * SCALE,
                          x + 4 * SCALE, y + 4 * SCALE), fill=colour)
    final = canvas.resize((512, 512), Image.Resampling.LANCZOS)
    final.save(OUT / "CanyonGlow.png")
    final.save(OUT / "CanyonGlow.ico", sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)])
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">',
           '<!-- Copyright (c) 2026 rattensuppe; SPDX-License-Identifier: MIT -->',
           '<rect x="12" y="12" width="232" height="232" rx="48" fill="#101c30"/>']
    svg += [f'<polygon points="{points_text(points)}" fill="{colour}"/>'
            for colour, points in WALLS]
    svg += [f'<polyline points="{points_text(points)}" fill="none" stroke="{colour}" '
            'stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>'
            for colour, points in LIGHTS]
    (OUT / "CanyonGlow.svg").write_text("\n".join(svg + ["</svg>"]) + "\n", encoding="utf-8")
    print("Created original CanyonGlow SVG, PNG and multi-size ICO.")


if __name__ == "__main__":
    main()
