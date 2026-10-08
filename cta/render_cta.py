"""Animated CTA lower-third for the Higgsfield Genjutsu ad (The Cat Podcast).

Renders:
  out/cta_higgsfield.mov  - ProRes 4444 with alpha, 1920x1080, 30 fps, 8 s
  out/cta_preview.mp4     - H.264 preview over a dark background
  out/cta_still.png       - static frame preview

Usage: python3 render_cta.py
All tweakable values live in CONFIG below.
"""
import os
import subprocess
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
FONT_DIR = "/usr/share/fonts/opentype/inter"

CONFIG = {
    "title": "Higgsfield Genjutsu",
    "subtitle": "Turn your pet into a movie star",
    "link_label": "Link in description",
    "code": "CODE: CATPODCAST",  # placeholder: replace with the real referral code / link
    "accent": (200, 128, 13),     # #C8800D
    "panel_rgb": (12, 12, 14),
    "panel_alpha": 0.85,
    "margin": 80,                 # distance from left and bottom frame edges
    "radius": 18,
    "title_size": 58,
    "subtitle_size": 32,
    "link_size": 28,
    # timing (seconds)
    "duration": 8.0,
    "fps": 30,
    "panel_in": (0.0, 0.4),
    "bar_in": (0.25, 0.7),
    "line_start": 0.4, "line_gap": 0.15, "line_dur": 0.4,
    "highlight": (3.6, 4.6),
    "out": (7.45, 7.85),
}

W, H = 1920, 1080
SS = 2  # supersampling for the static layers


def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size * SS)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, start, end):
    return clamp((t - start) / (end - start))


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_in(x):
    return x ** 3


def ease_in_out(x):
    return 3 * x * x - 2 * x * x * x


def text_layer(text, fnt, color, size):
    """Text rendered on its own transparent layer at final (1x) resolution."""
    l, t, r, b = fnt.getbbox(text)
    asc, desc = fnt.getmetrics()
    img = Image.new("RGBA", (r + 8 * SS, asc + desc + 4 * SS), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((0, 0), text, font=fnt, fill=color)
    return img.resize((img.width // SS, img.height // SS), Image.LANCZOS)


def build_layers(c):
    white = (255, 255, 255, 255)
    soft = (255, 255, 255, 220)
    title = text_layer(c["title"], font("Inter-Bold.otf", c["title_size"]), c["accent"] + (255,), c["title_size"])
    sub = text_layer(c["subtitle"], font("Inter-Medium.otf", c["subtitle_size"]), soft, c["subtitle_size"])

    # link line: label + separator dot + code (code in semibold white)
    lf = font("Inter-SemiBold.otf", c["link_size"])
    a = text_layer(c["link_label"], lf, white, c["link_size"])
    dot = text_layer("  •  ", lf, c["accent"] + (255,), c["link_size"])
    b = text_layer(c["code"], font("Inter-Bold.otf", c["link_size"]), white, c["link_size"])
    link = Image.new("RGBA", (a.width + dot.width + b.width, max(a.height, b.height)), (0, 0, 0, 0))
    link.alpha_composite(a, (0, 0))
    link.alpha_composite(dot, (a.width, 0))
    link.alpha_composite(b, (a.width + dot.width, 0))

    pad_l, pad_r, pad_t, pad_b = 52, 56, 34, 30
    gap1, gap2 = 6, 18
    content_w = max(title.width, sub.width, link.width)
    pw = pad_l + content_w + pad_r
    ph = pad_t + title.height + gap1 + sub.height + gap2 + link.height + pad_b

    # panel (supersampled rounded rect)
    panel = Image.new("RGBA", (pw * SS, ph * SS), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle(
        (0, 0, pw * SS - 1, ph * SS - 1), radius=c["radius"] * SS,
        fill=c["panel_rgb"] + (int(255 * c["panel_alpha"]),))
    panel = panel.resize((pw, ph), Image.LANCZOS)

    # soft shadow
    sh_pad = 40
    shadow = Image.new("RGBA", (pw + 2 * sh_pad, ph + 2 * sh_pad), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (sh_pad, sh_pad + 6, sh_pad + pw, sh_pad + ph + 6), radius=c["radius"], fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))

    bar_x, bar_w = 24, 5
    bar_top, bar_bot = pad_t + 6, ph - pad_b - 4

    y1 = pad_t
    y2 = y1 + title.height + gap1
    y3 = y2 + sub.height + gap2
    lines = [(title, (pad_l, y1)), (sub, (pad_l, y2)), (link, (pad_l, y3))]
    return dict(panel=panel, shadow=shadow, sh_pad=sh_pad, pw=pw, ph=ph, lines=lines,
                bar=(bar_x, bar_w, bar_top, bar_bot), link_box=(pad_l - 14, y3 - 6, pad_l + link.width + 10, y3 + link.height + 2))


def compose_card(L, c, t):
    """Card in local coordinates (with shadow margin) at time t."""
    sp = L["sh_pad"]
    card = Image.new("RGBA", (L["pw"] + 2 * sp, L["ph"] + 2 * sp), (0, 0, 0, 0))
    card.alpha_composite(L["shadow"])
    card.alpha_composite(L["panel"], (sp, sp))
    draw = ImageDraw.Draw(card)

    # link highlight: soft amber pill that swells and fades once, with a light sweep
    hp = prog(t, *c["highlight"])
    if 0 < hp < 1:
        x0, y0, x1, y1 = L["link_box"]
        k = (1 - abs(2 * hp - 1)) ** 1.5  # 0 -> 1 -> 0
        pill = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        ImageDraw.Draw(pill).rounded_rectangle((0, 0, pill.width - 1, pill.height - 1), radius=10,
                                               fill=c["accent"] + (int(70 * k),))
        # sweep band
        band = Image.new("L", pill.size, 0)
        bx = int(-80 + (pill.width + 160) * ease_in_out(hp))
        ImageDraw.Draw(band).polygon([(bx - 40, 0), (bx + 20, 0), (bx + 40, pill.height), (bx - 20, pill.height)], fill=int(90 * k))
        band = band.filter(ImageFilter.GaussianBlur(12))
        sweep = Image.new("RGBA", pill.size, (255, 236, 200, 0))
        sweep.putalpha(ImageChops.multiply(band, pill.getchannel("A").point(lambda v: 255 if v else 0)))
        pill.alpha_composite(sweep)
        card.alpha_composite(pill, (sp + x0, sp + y0))

    # amber bar drawn top -> bottom
    bp = ease_out(prog(t, *c["bar_in"]))
    bx, bw, btop, bbot = L["bar"]
    if bp > 0:
        yb = btop + (bbot - btop) * bp
        bar = Image.new("RGBA", (bw * SS, int((yb - btop) * SS) + 1), (0, 0, 0, 0))
        ImageDraw.Draw(bar).rounded_rectangle((0, 0, bar.width - 1, bar.height - 1), radius=bw * SS // 2,
                                              fill=c["accent"] + (255,))
        bar = bar.resize((bw, max(1, int(yb - btop))), Image.LANCZOS)
        card.alpha_composite(bar, (sp + bx, sp + btop))

    # text lines rise in one after another
    for i, (img, (lx, ly)) in enumerate(L["lines"]):
        s = c["line_start"] + i * c["line_gap"]
        p = ease_out(prog(t, s, s + c["line_dur"]))
        if p <= 0:
            continue
        dy = (1 - p) * 18
        layer = img
        if p < 1:
            layer = img.copy()
            layer.putalpha(layer.getchannel("A").point(lambda v: int(v * p)))
            layer = layer.transform(layer.size, Image.AFFINE, (1, 0, 0, 0, 1, -dy % 1), Image.BILINEAR)
        card.alpha_composite(layer, (sp + lx, sp + ly + int(dy)))
    return card


def frame(L, c, t):
    sp = L["sh_pad"]
    pin = ease_out(prog(t, *c["panel_in"]))
    pout = ease_in(prog(t, *c["out"]))
    travel = c["margin"] + L["pw"] + sp + 10
    x = c["margin"] - sp - travel * (1 - pin) - travel * pout
    y = H - c["margin"] - L["ph"] - sp
    card = compose_card(L, c, t)
    fa = (1 - pout) * clamp(pin * 1.5)
    if fa < 1:
        card.putalpha(card.getchannel("A").point(lambda v: int(v * fa)))
    # sub-pixel horizontal position
    xi = int(x // 1)
    frac = x - xi
    if frac:
        card = card.transform(card.size, Image.AFFINE, (1, 0, -frac, 0, 1, 0), Image.BILINEAR)
    tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # clip-safe placement (card may be partly off-screen on the left)
    cx0, cy0 = max(0, xi), max(0, int(y))
    sx0, sy0 = cx0 - xi, cy0 - int(y)
    if sx0 < card.width:
        crop = card.crop((sx0, sy0, card.width, card.height))
        tmp.alpha_composite(crop, (cx0, cy0))
    return tmp


def main():
    os.makedirs(OUT, exist_ok=True)
    c = CONFIG
    L = build_layers(c)
    n = int(c["duration"] * c["fps"])
    mov = os.path.join(OUT, "cta_higgsfield.mov")
    enc = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
        "-r", str(c["fps"]), "-i", "-", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
        "-alpha_bits", "16", "-vendor", "apl0", mov], stdin=subprocess.PIPE)
    for i in range(n):
        f = frame(L, c, i / c["fps"])
        enc.stdin.write(f.tobytes())
        if i == int(2.5 * c["fps"]):
            bg = Image.new("RGBA", (W, H), (28, 30, 34, 255))
            bg.alpha_composite(f)
            bg.convert("RGB").save(os.path.join(OUT, "cta_still.png"))
    enc.stdin.close()
    enc.wait()

    # preview: dark vignette background + guide circle where the cat's face sits
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c=0x1c1e22:s={W}x{H}:r={c['fps']}:d={c['duration']},vignette=PI/4",
        "-i", mov, "-filter_complex", "[0][1]overlay=format=auto,format=yuv420p",
        "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-movflags", "+faststart",
        os.path.join(OUT, "cta_preview.mp4")], check=True)
    print("done:", OUT)


if __name__ == "__main__":
    main()
