"""Cover images (1280x720) for the mod pages.

    python covers.py <out_dir>

One look for all of them -- dark gradient, accent colour, title, tagline -- and a
motif per mod that says what it does at a glance.
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
FONTS = r"C:\Windows\Fonts"


def font(bold, size):
    return ImageFont.truetype(os.path.join(FONTS, "segoeuib.ttf" if bold else "segoeui.ttf"), size)


def base(top, bottom):
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / H
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        for x in range(W):
            px[x, y] = c
    return img, ImageDraw.Draw(img, "RGBA")


def text(d, title, tagline, lines, accent):
    d.text((70, 90), title, font=font(True, 84), fill=(255, 255, 255))
    d.rectangle([70, 205, 230, 211], fill=accent)
    d.text((70, 235), tagline, font=font(False, 34), fill=(225, 230, 240))
    for i, line in enumerate(lines):
        d.text((70, 330 + 52 * i), "\u2022  " + line, font=font(False, 28), fill=(190, 198, 212))
    d.text((70, H - 70), "Motor Town  \u00b7  qxZap", font=font(False, 24), fill=(140, 150, 168))


def framework(d, accent):
    x0, y0, s, g = 900, 240, 40, 10
    for r in range(8):
        for c in range(7):
            n = r * 7 + c
            x, y = x0 + c * (s + g), y0 + r * (s + g)
            filled = n in (0, 1, 2, 4, 9, 23)
            d.rounded_rectangle([x, y, x + s, y + s], 8,
                                fill=accent + (220,) if filled else (255, 255, 255, 18),
                                outline=(255, 255, 255, 60))
    d.text((x0, y0 + 8 * (s + g) + 6), "Ch0001  \u2026  Ch1000", font=font(True, 26),
           fill=(230, 235, 245))


def loader(d, accent):
    cx, cy = 980, 360
    for i, label in enumerate(("Economy", "Parker", "Fitment", "Yours")):
        a = -math.pi / 2 + i * math.pi / 2 + math.pi / 4
        px, py = cx + 230 * math.cos(a), cy + 200 * math.sin(a)
        d.line([(cx, cy), (px, py)], fill=accent + (200,), width=6)
        d.rounded_rectangle([px - 85, py - 34, px + 85, py + 34], 14, fill=(255, 255, 255, 30),
                            outline=accent)
        d.text((px, py), label, font=font(True, 26), fill=(240, 244, 250), anchor="mm")
    d.rounded_rectangle([cx - 110, cy - 70, cx + 110, cy + 70], 20, fill=accent)
    d.text((cx, cy - 12), "version.dll", font=font(True, 30), fill=(20, 24, 32), anchor="mm")
    d.text((cx, cy + 24), "loader", font=font(False, 24), fill=(20, 24, 32), anchor="mm")


def economy(d, accent):
    a, b = (760, 580), (1180, 160)
    pts = []
    for i in range(121):
        t = i / 120
        off = 140 * math.sin(t * math.pi * 2) * math.sin(t * math.pi)
        nx, ny = -(b[1] - a[1]), b[0] - a[0]
        n = math.hypot(nx, ny)
        pts.append((a[0] + (b[0] - a[0]) * t + off * nx / n, a[1] + (b[1] - a[1]) * t + off * ny / n))
    d.line(pts, fill=(255, 255, 255, 70), width=14, joint="curve")
    d.line([a, b], fill=accent, width=8)
    for p in (a, b):
        d.ellipse([p[0] - 18, p[1] - 18, p[0] + 18, p[1] + 18], fill=accent)
    d.text((1000, 470), "pay = straight line", font=font(True, 26), fill=accent)


def parker(d, accent):
    x, y, s = 860, 140, 300
    d.rounded_rectangle([x, y, x + s, y + s], 40, fill=accent)
    d.text((x + s / 2, y + s / 2 + 6), "P", font=font(True, 240), fill=(255, 255, 255), anchor="mm")
    d.rectangle([x + s / 2 - 10, y + s, x + s / 2 + 10, y + s + 120], fill=(200, 205, 215))
    d.rounded_rectangle([x + 20, y + s + 140, x + s - 20, y + s + 200], 12, fill=(255, 255, 255, 30),
                        outline=accent)
    d.text((x + s / 2, y + s + 170), "Ctrl + F10", font=font(True, 32), fill=(240, 244, 250),
           anchor="mm")


def smoke(d, accent):
    cx, cy, r = 860, 470, 118
    # the cloud first, behind the tyre: puffs rolling back along the road, swelling,
    # rising and thinning; drawn on their own layer and blurred so they read as smoke
    from PIL import ImageFilter
    img = d._image
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for i in range(22):
        t = i / 21
        x = cx + 50 + 400 * t + 30 * math.sin(i * 2.3)
        y = cy + r - 45 - 230 * t ** 1.25 + 22 * math.cos(i * 1.7)
        pr = 48 + 120 * t
        a = int(200 * (1 - t) ** 1.1 + 70)
        ld.ellipse([x - pr, y - pr, x + pr, y + pr], fill=(228, 231, 238, a))
    layer = layer.filter(ImageFilter.GaussianBlur(11))
    img.paste(layer, (0, 0), layer)
    # tyre: tread ring with lugs, sidewall, rim
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(26, 26, 30))
    for k in range(24):
        a = k * math.pi / 12
        x1, y1 = cx + (r - 2) * math.cos(a), cy + (r - 2) * math.sin(a)
        x2, y2 = cx + (r - 20) * math.cos(a), cy + (r - 20) * math.sin(a)
        d.line([x1, y1, x2, y2], fill=(52, 52, 58), width=9)
    d.ellipse([cx - r + 32, cy - r + 32, cx + r - 32, cy + r - 32], fill=(40, 40, 46))
    d.ellipse([cx - 52, cy - 52, cx + 52, cy + 52], fill=(170, 176, 188))
    for k in range(5):
        a = -math.pi / 2 + k * 2 * math.pi / 5
        d.line([cx, cy, cx + 48 * math.cos(a), cy + 48 * math.sin(a)], fill=(110, 116, 128), width=10)
    d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=(90, 94, 104))
    # heat where rubber meets road, and the road
    d.rectangle([700, cy + r, 1240, cy + r + 6], fill=(70, 74, 84))
    d.ellipse([cx - 90, cy + r - 12, cx + 90, cy + r + 12], fill=accent + (150,))


COVERS = {
    "DataTableFramework": ((14, 22, 40), (10, 40, 52), (64, 196, 255), framework,
                           "One table, a thousand channels",
                           ["Every composite table, shipped once", "Mods add rows -- never copy tables",
                            "No more compat packs", "Install once, every mod uses it"]),
    "PluginLoader": ((22, 16, 38), (36, 14, 44), (190, 120, 255), loader,
                     "Every native mod, one version.dll",
                     ["Loads plugins\\mt_plugin_*.dll", "One safe hook, shared by all",
                      "Plugins keep working across updates", "Drop in, nothing to configure"]),
    "CapitalistEconomy": ((12, 26, 30), (10, 46, 30), (90, 220, 140), economy,
                          "Pay that makes sense",
                          ["Straight-line distance, not road km", "Real weight and size",
                           "Fragile cargo pays more", "Works on dedicated servers"]),
    "VehicleParker": ((30, 20, 14), (44, 26, 12), (255, 170, 40), parker,
                      "Park the fleet in one keypress",
                      ["Ctrl+F10 sends your vehicles home", "Uses the game's own Despawn",
                       "Campers stay put", "Nothing is ever deleted"]),
    "Smoke": ((22, 22, 26), (40, 24, 20), (255, 112, 52), smoke,
              "Burnouts that leave a cloud",
              ["Tire smoke lasts 4x longer", "Every puff 1.5x bigger",
               "Drifts and burnouts hang in the air", "Tune both in smoke.ini"]),
}


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name, (top, bottom, accent, motif, tagline, lines) in COVERS.items():
        img, d = base(top, bottom)
        motif(d, accent)
        title = {"DataTableFramework": "DataTable Framework", "PluginLoader": "Plugin Loader",
                 "CapitalistEconomy": "Capitalist Economy", "VehicleParker": "Vehicle Parker",
                 "Smoke": "Smoke"}[name]
        text(d, title, tagline, lines, accent)
        path = os.path.join(out_dir, name, name + ".png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.save(path)
        print("  ", path)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
