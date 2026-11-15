"""Pixel-forest intro for Cursor Engine. Pure Pillow + winsound: no asset files needed."""
import io, math, random, sys, time, wave
from array import array
from PIL import Image, ImageDraw

W, H, SCALE = 192, 108, 4                      # drawn at 192x108, shown at 4x (768x432)
T_TITLE, T_LOAD, T_CHIME, T_FADE, T_END = 1.0, 2.3, 3.75, 4.0, 4.55
TITLE = "CURSOR ENGINE"
TILE = 320

# ---------------- tiny 5x7 pixel font ----------------
FONT = {
    "C": ".###.|#...#|#....|#....|#....|#...#|.###.",
    "U": "#...#|#...#|#...#|#...#|#...#|#...#|.###.",
    "R": "####.|#...#|#...#|####.|#.#..|#..#.|#...#",
    "S": ".####|#....|#....|.###.|....#|....#|####.",
    "O": ".###.|#...#|#...#|#...#|#...#|#...#|.###.",
    "E": "#####|#....|#....|####.|#....|#....|#####",
    "N": "#...#|##..#|#.#.#|#..##|#...#|#...#|#...#",
    "G": ".###.|#...#|#....|#.###|#...#|#...#|.###.",
    "I": ".###.|..#..|..#..|..#..|..#..|..#..|.###.",
    "L": "#....|#....|#....|#....|#....|#....|#####",
    "A": ".###.|#...#|#...#|#####|#...#|#...#|#...#",
    "D": "####.|#...#|#...#|#...#|#...#|#...#|####.",
    ".": ".....|.....|.....|.....|.....|.....|..#..",
}


def text_w(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(d, text, x, y, scale, rgb, alphas=None, dys=None, shine=None):
    cx = x
    for i, ch in enumerate(text):
        a = 255 if alphas is None else alphas[i]
        if ch != " " and a > 0:
            oy = 0 if dys is None else dys[i]
            for ry, row in enumerate(FONT[ch].split("|")):
                for rx, c in enumerate(row):
                    if c == "#":
                        px, py = cx + rx * scale, y + oy + ry * scale
                        col = (255, 255, 255) if shine is not None and abs(px - shine) < 6 else rgb
                        d.rectangle([px, py, px + scale - 1, py + scale - 1], fill=col + (a,))
        cx += 6 * scale


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def ease(v):
    v = clamp(v)
    return v * v * (3 - 2 * v)


# ---------------- the forest ----------------
class Forest:
    def __init__(self):
        r = random.Random(11)
        self.sky = self._sky()
        self.layers = [                                    # (tile, speed px/sec)
            (self._doubled(self._trees(r, 84, 28, 42, 12, (38, 42, 98))), 1.5),
            (self._doubled(self._trees(r, 96, 36, 50, 16, (20, 46, 72))), 3.0),
            (self._doubled(self._mist(r)), 5.0),
            (self._doubled(self._trees(r, 112, 40, 58, 34, (9, 28, 40))), 7.0),
        ]
        self.ground = self._ground(r)
        self.vig = self._vignette()
        self.stars = [(r.randrange(W), r.randrange(0, 56), r.uniform(0, 6.3), r.uniform(1, 3))
                      for _ in range(46)]
        self.flies = [(r.uniform(8, W - 8), r.uniform(52, 94), r.uniform(0.4, 1.1), r.uniform(0.5, 1.3),
                       r.uniform(0, 6.3), r.uniform(0, 6.3), r.uniform(1.2, 2.6), r.uniform(0, 6.3))
                      for _ in range(15)]

    def _sky(self):
        im = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(im)
        top, bot = (6, 8, 26), (70, 52, 120)
        for y in range(H):
            k = round(clamp(y / (H * 0.85)) * 14) / 14       # banded gradient = pixel look
            d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)) + (255,))
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        mx, my = 152, 18
        for rad, a in ((20, 12), (15, 20), (12, 32)):
            gd.ellipse([mx - rad, my - rad, mx + rad, my + rad], fill=(200, 210, 255, a))
        im.alpha_composite(glow)
        d = ImageDraw.Draw(im)
        d.ellipse([mx - 8, my - 8, mx + 8, my + 8], fill=(244, 240, 214, 255))
        for cx, cy, cr in ((mx - 3, my - 3, 2), (mx + 3, my + 2, 1), (mx - 2, my + 4, 1)):
            d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(224, 220, 188, 255))
        return im

    @staticmethod
    def _doubled(img):
        d = Image.new("RGBA", (TILE * 2, H), (0, 0, 0, 0))
        d.paste(img, (0, 0))
        d.paste(img, (TILE, 0))
        return d

    @staticmethod
    def _pine(d, x, base, h, w, color):
        col = color + (255,)
        d.rectangle([x - 1, base - 4, x, base], fill=col)
        for i in range(3):
            top = base - h + int(i * h * 0.26)
            bot = top + int(h * 0.42)
            hw = int(w * (0.55 + 0.3 * i))
            d.polygon([(x, top), (x - hw, bot), (x + hw, bot)], fill=col)

    def _trees(self, r, base, hmin, hmax, step, color):
        img = Image.new("RGBA", (TILE, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        x = r.randrange(step)
        while x < TILE + step:
            h = r.randint(hmin, hmax)
            for dx in (-TILE, 0, TILE):                       # draw wrapped copies so the tile loops
                self._pine(d, x + dx, base, h, max(4, h // 4 + 2), color)
            x += r.randint(step, step + step // 2)
        return img

    @staticmethod
    def _mist(r):
        img = Image.new("RGBA", (TILE, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img, "RGBA")
        for _ in range(7):
            x, y = r.randrange(TILE), r.randint(74, 98)
            w, h = r.randint(40, 80), r.randint(5, 10)
            for dx in (-TILE, 0, TILE):
                for k in range(3):
                    d.ellipse([x + dx - w // 2 + k * 3, y - h // 2 + k, x + dx + w // 2 - k * 3, y + h // 2 - k],
                              fill=(170, 190, 230, 9))
        return img

    @staticmethod
    def _ground(r):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        col = (6, 16, 24, 255)
        d.rectangle([0, H - 8, W, H], fill=col)
        for x in range(W):
            if r.random() < 0.35:
                d.line([(x, H - 8), (x, H - 8 - r.randint(1, 3))], fill=col)
        return img

    @staticmethod
    def _vignette():
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for i in range(10):
            d.rectangle([i, i, W - 1 - i, H - 1 - i], outline=(0, 0, 10, int(95 * (1 - i / 10) ** 2)))
        return img

    def render(self, t):
        base = self.sky.copy()
        d = ImageDraw.Draw(base, "RGBA")
        for x, y, ph, sp in self.stars:                       # twinkling stars (behind the trees)
            b = 0.5 + 0.5 * math.sin(t * sp + ph)
            d.point((x, y), fill=(255, 255, 235, int(70 + 170 * b)))
            if b > 0.9:
                for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    d.point((x + ox, y + oy), fill=(255, 255, 235, 60))
        for tile, speed in self.layers:                       # parallax drift
            o = int(t * speed) % TILE
            base.alpha_composite(tile.crop((o, 0, o + W, H)))
        base.alpha_composite(self.ground)

        glow_in = clamp(t / 1.5)                              # fireflies
        for bx, by, sx, sy, px, py, sb, pb in self.flies:
            x = int(bx + 9 * math.sin(t * sx + px))
            y = int(by + 5 * math.cos(t * sy + py))
            b = 0.5 + 0.5 * math.sin(t * sb + pb)
            a = int(255 * b ** 1.5 * glow_in)
            d.point((x, y), fill=(255, 236, 130, a))
            if b > 0.6:
                for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    d.point((x + ox, y + oy), fill=(255, 220, 90, a // 3))
        base.alpha_composite(self.vig)

        # title: letters pop in one by one, then a shine sweeps across
        x0, y0 = (W - text_w(TITLE, 2)) // 2, 28
        al = [int(255 * clamp((t - (T_TITLE + 0.09 * i)) / 0.14)) for i in range(len(TITLE))]
        dy = [int(-4 * (1 - a / 255)) for a in al]
        draw_text(d, TITLE, x0 + 1, y0 + 2, 2, (4, 10, 20), [int(a * 0.7) for a in al], dy)
        shine = x0 - 8 + (t - 2.15) / 0.5 * (text_w(TITLE, 2) + 16) if 2.15 < t < 2.65 else None
        draw_text(d, TITLE, x0, y0, 2, (214, 255, 226), al, dy, shine)

        if t > T_LOAD:                                        # loading plate
            f = clamp((t - T_LOAD) / 0.3)
            d.rectangle([58, 74, 134, 97], fill=(4, 10, 20, int(150 * f)), outline=(70, 90, 120, int(200 * f)))
            label = "LOADING" + "." * (int(t * 3) % 4)
            draw_text(d, label, (W - text_w("LOADING...", 1)) // 2, 77, 1, (190, 230, 210), [int(255 * f)] * len(label))
            p = clamp((t - T_LOAD) / (T_CHIME - T_LOAD))
            d.rectangle([63, 87, 129, 94], outline=(110, 140, 170, int(255 * f)))
            for sx in range(65, 65 + int(62 * p), 4):
                d.rectangle([sx, 89, min(sx + 2, 126), 92], fill=(118, 226, 140, 255))
                d.line([(sx, 89), (min(sx + 2, 126), 89)], fill=(190, 255, 200, 255))
        d.rectangle([0, 0, W - 1, H - 1], outline=(18, 24, 44, 255))
        return base.convert("RGB").resize((W * SCALE, H * SCALE), Image.NEAREST)


# ---------------- synthesized sound effects ----------------
SR = 22050


def _tone(buf, start, dur, freq, amp, decay=5.0, shape="sine", vib=0.0):
    i0, n = int(start * SR), int(dur * SR)
    for k in range(n):
        j = i0 + k
        if j >= len(buf):
            break
        t = k / SR
        env = math.exp(-decay * t)
        if env < 0.002:
            break
        env *= min(1.0, k / (0.004 * SR))
        s = math.sin(2 * math.pi * freq * t + vib * math.sin(2 * math.pi * 5.5 * t))
        if shape == "square":
            s = 0.6 if s > 0 else -0.6
        buf[j] += amp * env * s


def make_sfx():
    """Forest wind + crickets, a magic shimmer, typewriter blips for each letter, and a final chime."""
    dur = 4.8
    n = int(dur * SR)
    buf = [0.0] * n
    r = random.Random(5)
    y = 0.0
    for i in range(n):                                        # wind: low-passed noise, slowly swelling
        t = i / SR
        y += 0.02 * (r.uniform(-1, 1) - y)
        buf[i] += y * 2.2 * min(1.0, t / 1.2) * (0.65 + 0.35 * math.sin(t * 1.9))
    t = 0.4
    while t < 4.2:                                            # crickets
        for p in range(3):
            _tone(buf, t + p * 0.032, 0.016, 4300, 0.022, decay=45)
        t += r.uniform(0.35, 0.7)
    for i, f in enumerate((1046.5, 1318.5, 1568.0, 2093.0)):  # shimmer
        _tone(buf, 0.25 + 0.13 * i, 1.0, f, 0.09, decay=3.2, vib=0.6)
    notes = [523.25, 587.33, 659.25, 783.99, 880.0, 1046.5, 1174.7, 1318.5, 1568.0, 1760.0, 2093.0, 2349.3]
    k = 0
    for i, ch in enumerate(TITLE):                            # one blip per letter, in sync with the reveal
        if ch != " ":
            ti = T_TITLE + 0.09 * i
            _tone(buf, ti, 0.06, notes[k], 0.07, decay=45, shape="square")
            _tone(buf, ti, 0.2, notes[k] * 2, 0.025, decay=12)
            k += 1
    for f in (1046.5, 1318.5, 1568.0):                        # chime as the bar fills
        _tone(buf, T_CHIME, 1.0, f, 0.08, decay=3.5)
    gain = 0.85 / (max(abs(v) for v in buf) or 1)
    out = array("h")
    for i, v in enumerate(buf):
        t = i / SR
        f = min(1.0, t / 0.25, (dur - t) / 0.5)
        out.append(int(clamp(v * gain * f, -1, 1) * 32767))
    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(out.tobytes())
    return bio.getvalue()


def _play(wav):
    if sys.platform == "win32":
        try:
            import winsound
            winsound.PlaySound(wav, winsound.SND_MEMORY | winsound.SND_ASYNC)
        except Exception:
            pass


def _stop():
    if sys.platform == "win32":
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass


# ---------------- the splash window ----------------
class Splash:
    """Borderless fade-in/out window. Click or press any key to skip. Calls on_done() at the end."""

    def __init__(self, root, on_done):
        import tkinter as tk
        from PIL import ImageTk
        self._ImageTk = ImageTk
        self.root, self.on_done, self.done = root, on_done, False
        self.forest = Forest()
        wav = make_sfx()
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.0)
        w, h = W * SCALE, H * SCALE
        x, y = (self.win.winfo_screenwidth() - w) // 2, (self.win.winfo_screenheight() - h) // 2
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.label = tk.Label(self.win, bd=0, highlightthickness=0)
        self.label.pack()
        for ev in ("<Button-1>", "<Key>"):
            self.win.bind(ev, lambda e: self.finish())
        self.win.focus_force()
        self.photo = ImageTk.PhotoImage(self.forest.render(0))
        self.label.configure(image=self.photo)
        self.win.update_idletasks()
        self.t0 = time.perf_counter()
        _play(wav)
        self.tick()

    def tick(self):
        if self.done:
            return
        t = time.perf_counter() - self.t0
        if t >= T_END:
            return self.finish()
        self.photo = self._ImageTk.PhotoImage(self.forest.render(t))
        self.label.configure(image=self.photo)
        a = ease(t / 0.8) if t < 0.8 else (1 - ease((t - T_FADE) / (T_END - T_FADE)) if t > T_FADE else 1)
        self.win.attributes("-alpha", clamp(a))
        self.root.after(15, self.tick)

    def finish(self):
        if self.done:
            return
        self.done = True
        _stop()
        self.win.destroy()
        self.on_done()
