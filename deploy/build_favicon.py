"""Rasterize the simple SVG primitives for the browser's ICO fallback."""
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "static" / "icons"
SCALE = 8


def main():
    icon = Image.new("RGBA", (64 * SCALE, 64 * SCALE))
    draw = ImageDraw.Draw(icon)
    for element in ET.parse(ROOT / "quote.svg").getroot():
        attr = element.attrib
        def value(name):
            return float(attr[name]) * SCALE
        kind = element.tag.rsplit("}", 1)[-1]
        if kind == "rect":
            draw.rounded_rectangle((0, 0, value("width") - 1, value("height") - 1),
                                   radius=value("rx"), fill=attr["fill"])
        elif kind == "circle":
            x, y, r = value("cx"), value("cy"), value("r")
            half = value("stroke-width") / 2
            draw.ellipse((x-r-half, y-r-half, x+r+half, y+r+half),
                         outline=attr["stroke"], width=int(half * 2))
        elif kind == "line":
            points = [(value("x1"), value("y1")), (value("x2"), value("y2"))]
            width = int(value("stroke-width"))
            draw.line(points, fill=attr["stroke"], width=width)
            for x, y in points:
                r = width / 2
                draw.ellipse((x-r, y-r, x+r, y+r), fill=attr["stroke"])
        else:
            raise ValueError(f"Unsupported favicon primitive: {kind}")
    icon.save(ROOT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    icon.resize((32, 32), Image.Resampling.LANCZOS).save(ROOT / "favicon.png")


if __name__ == "__main__":
    main()
