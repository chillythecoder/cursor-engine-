"""Cursor Engine core: image/GIF -> .cur/.ani -> applied as Windows cursor."""
import ctypes, itertools, json, os, struct
from pathlib import Path
from PIL import Image, ImageSequence

APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "CursorEngine"
OUT_DIR = APP_DIR / "cursors"
BACKUP = APP_DIR / "backup.json"

ALL_ROLES = ["Arrow", "Help", "AppStarting", "Wait", "Crosshair", "IBeam", "NWPen",
             "No", "SizeNS", "SizeWE", "SizeNWSE", "SizeNESW", "SizeAll", "UpArrow", "Hand"]
TARGETS = {
    "Normal pointer": ["Arrow"],
    "Link (hand)": ["Hand"],
    "Text (I-beam)": ["IBeam"],
    "Busy / loading": ["AppStarting", "Wait"],
    "Everything": ALL_ROLES,
}


def load_frames(path, size, center=False, max_frames=60):
    """Return (frames, delays_ms, hotspot). Frames are size x size RGBA."""
    img = Image.open(path)
    frames, delays = [], []
    for f in itertools.islice(ImageSequence.Iterator(img), max_frames):
        delays.append(int(f.info.get("duration", 100) or 100))
        im = f.convert("RGBA")
        im.thumbnail((size, size), Image.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        off = ((size - im.width) // 2, (size - im.height) // 2) if center else (0, 0)
        canvas.paste(im, off, im)
        frames.append(canvas)
    hot = (size // 2, size // 2) if center else (0, 0)
    return frames, delays, hot


def make_cur(im, hx, hy):
    """Single 32-bit alpha cursor (BMP/DIB format, works everywhere)."""
    w, h = im.size
    px = im.tobytes("raw", "BGRA")
    rows = [px[y * w * 4:(y + 1) * w * 4] for y in range(h)]
    xor = b"".join(reversed(rows))                      # DIBs are bottom-up
    mask = bytes(((w + 31) // 32 * 4) * h)              # AND mask (unused with alpha)
    bih = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, len(xor) + len(mask), 0, 0, 0, 0)
    data = bih + xor + mask
    head = struct.pack("<HHH", 0, 2, 1)
    entry = struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, hx, hy, len(data), 22)
    return head + entry + data


def _chunk(tag, data):
    return tag + struct.pack("<I", len(data)) + data + (b"\0" if len(data) % 2 else b"")


def make_ani(frames, delays, hx, hy):
    """Animated cursor: RIFF 'ACON' container of .cur frames."""
    n, (w, h) = len(frames), frames[0].size
    jifs = [max(1, round(d * 60 / 1000)) for d in delays]  # 1 jiffy = 1/60 s
    anih = struct.pack("<9I", 36, n, n, w, h, 32, 1, jifs[0], 1)
    rate = struct.pack(f"<{n}I", *jifs)
    icons = b"".join(_chunk(b"icon", make_cur(f, hx, hy)) for f in frames)
    body = b"ACON" + _chunk(b"anih", anih) + _chunk(b"rate", rate) + _chunk(b"LIST", b"fram" + icons)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def build_cursor(src, size=48, center=False):
    """Convert any image/GIF file into a cursor file. Returns (path, frame_count)."""
    frames, delays, (hx, hy) = load_frames(src, size, center)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(src).stem
    if len(frames) == 1:
        out, data = OUT_DIR / f"{stem}_{size}.cur", make_cur(frames[0], hx, hy)
    else:
        out, data = OUT_DIR / f"{stem}_{size}.ani", make_ani(frames, delays, hx, hy)
    out.write_bytes(data)
    return out, len(frames)


def _refresh():
    # SPI_SETCURSORS, with SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    ctypes.windll.user32.SystemParametersInfoW(0x57, 0, None, 3)


def apply_cursor(path, roles):
    import winreg
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors", 0,
                        winreg.KEY_ALL_ACCESS) as k:
        if not BACKUP.exists():                          # remember the originals once
            old = {}
            for r in ALL_ROLES:
                try:
                    old[r] = winreg.QueryValueEx(k, r)[0]
                except OSError:
                    old[r] = ""
            BACKUP.write_text(json.dumps(old))
        for r in roles:
            winreg.SetValueEx(k, r, 0, winreg.REG_EXPAND_SZ, str(path))
    _refresh()


def reset_cursors():
    import winreg
    old = json.loads(BACKUP.read_text()) if BACKUP.exists() else {r: "" for r in ALL_ROLES}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors", 0,
                        winreg.KEY_ALL_ACCESS) as k:
        for r, v in old.items():
            winreg.SetValueEx(k, r, 0, winreg.REG_EXPAND_SZ, v)
    BACKUP.unlink(missing_ok=True)
    _refresh()
