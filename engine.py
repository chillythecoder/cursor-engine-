"""Cursor Engine core: image/GIF -> .cur/.ani -> applied as Windows cursor."""
import ctypes, io, itertools, json, os, shutil, struct
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


# ---------- existing .cur / .ani files ----------
NATIVE = {".cur", ".ani"}


def is_native(path):
    return Path(path).suffix.lower() in NATIVE


def _decode_cur(data):
    """Decode the biggest image in a .cur/.ico (BMP or PNG entries) to RGBA, honoring alpha and the AND mask."""
    _, typ, count = struct.unpack("<HHH", data[:6])
    if typ not in (1, 2) or count < 1:
        raise ValueError("not a cursor file")
    best = None
    for i in range(count):
        w, h, _c, _r, _a, _b, size, off = struct.unpack("<BBBBHHII", data[6 + 16 * i:22 + 16 * i])
        w, h = w or 256, h or 256
        if best is None or w * h > best[0] * best[1]:
            best = (w, h, size, off)
    _, _, size, off = best
    blob = data[off:off + size]
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        return Image.open(io.BytesIO(blob)).convert("RGBA")
    hsize, w, bh, _pl, bpp, comp = struct.unpack("<IiiHHI", blob[:20])
    clr_used = struct.unpack("<I", blob[32:36])[0]
    if comp != 0:
        raise ValueError("compressed cursor bitmap")
    h = abs(bh) // 2
    ncol = (clr_used or (1 << bpp)) if bpp <= 8 else 0
    pal = blob[hsize:hsize + ncol * 4]
    pix_off = hsize + ncol * 4
    stride = ((w * bpp + 31) // 32) * 4
    xor = blob[pix_off:pix_off + stride * h]
    if bpp == 32:
        im = Image.frombuffer("RGBA", (w, h), xor, "raw", "BGRA", stride, -1)
    elif bpp == 24:
        im = Image.frombuffer("RGB", (w, h), xor, "raw", "BGR", stride, -1).convert("RGBA")
    elif bpp in (1, 4, 8):
        im = Image.frombuffer("P", (w, h), xor, "raw", "P" if bpp == 8 else f"P;{bpp}", stride, -1)
        im.putpalette([c for i in range(ncol) for c in (pal[4 * i + 2], pal[4 * i + 1], pal[4 * i])])
        im = im.convert("RGBA")
    else:
        raise ValueError(f"{bpp}-bit cursors are not supported")
    if bpp != 32 or im.getchannel("A").getextrema() == (0, 0):   # transparency lives in the AND mask
        mstride = ((w + 31) // 32) * 4
        mdata = blob[pix_off + stride * h:pix_off + stride * h + mstride * h]
        if len(mdata) >= mstride * h:
            m = Image.frombuffer("1", (w, h), mdata, "raw", "1", mstride, -1).convert("L")
            im.putalpha(m.point(lambda v: 0 if v else 255))
        elif bpp == 32:
            im.putalpha(255)
    return im


def _open_cur(data):
    try:
        return _decode_cur(data)
    except Exception:
        return Image.open(io.BytesIO(data)).convert("RGBA")


def placeholder(size=128):
    from PIL import ImageDraw
    im = Image.new("RGBA", (size, size), (40, 40, 48, 255))
    ImageDraw.Draw(im).text((size // 2 - 28, size // 2 - 5), "No preview", fill=(170, 170, 180, 255))
    return im


def read_native(path, max_frames=120):
    """Read an existing .cur or .ani. Returns (frames, delays_ms)."""
    data = Path(path).read_bytes()
    if data[:4] != b"RIFF":                       # plain .cur
        return [_open_cur(data)], [100]
    if data[8:12] != b"ACON":
        raise ValueError("That doesn't look like a valid .ani file")
    icons, rates, seq, default = [], [], [], 10

    def walk(pos, end):
        nonlocal rates, seq, default
        while pos + 8 <= end:
            tag, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
            body = data[pos + 8:pos + 8 + size]
            if tag == b"LIST":
                if body[:4] == b"fram":
                    walk(pos + 12, pos + 8 + size)
            elif tag == b"icon":
                icons.append(body)
            elif tag == b"anih" and size >= 32:
                default = struct.unpack("<I", body[28:32])[0] or 10
            elif tag == b"rate":
                rates = list(struct.unpack(f"<{size // 4}I", body))
            elif tag == b"seq ":
                seq = list(struct.unpack(f"<{size // 4}I", body))
            pos += 8 + size + (size % 2)

    walk(12, len(data))
    if not icons:
        raise ValueError("No frames found in that .ani file")
    raw = [_open_cur(b) for b in icons]
    frames, delays = [], []
    for i, step in enumerate((seq or list(range(len(raw))))[:max_frames]):
        if step < len(raw):
            frames.append(raw[step])
            jif = rates[i] if i < len(rates) else default
            delays.append(max(1, round(jif * 1000 / 60)))
    return frames, delays


def load_any(path, size=48, center=False):
    """Frames + delays for preview, for images, GIFs, .cur and .ani alike."""
    if is_native(path):
        return read_native(path)
    frames, delays, _ = load_frames(path, size, center)
    return frames, delays


def build_cursor(src, size=48, center=False):
    """Convert any image/GIF into a cursor file (or reuse a .cur/.ani as-is). Returns (path, frames)."""
    if is_native(src):
        try:
            n = len(read_native(src)[0])          # only used to count frames, never blocks applying
        except Exception:
            n = 2 if Path(src).suffix.lower() == ".ani" else 1
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / Path(src).name
        if Path(src).resolve() != out.resolve():
            shutil.copy2(src, out)
        return out, n
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


# ---------- cursor library (so you can switch between past cursors) ----------
LIB_DIR = APP_DIR / "library"
LIB_FILE = APP_DIR / "library.json"


def load_library():
    try:
        return json.loads(LIB_FILE.read_text())
    except (OSError, ValueError):
        return []


def _save_library(items):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    LIB_FILE.write_text(json.dumps(items, indent=1))


def add_to_library(src, size, center, target):
    """Keep a private copy of the source image and remember the settings. Newest first."""
    LIB_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(src)
    dest = LIB_DIR / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    entry = {"name": src.stem, "file": str(dest), "size": int(size),
             "center": bool(center), "target": target}
    items = [e for e in load_library() if e != entry]
    _save_library([entry] + items)
    return entry


def remove_from_library(entry):
    items = [e for e in load_library() if e != entry]
    _save_library(items)
    if not any(e["file"] == entry["file"] for e in items):
        Path(entry["file"]).unlink(missing_ok=True)


def apply_entry(entry):
    """Switch to a saved cursor. Returns the frame count."""
    path, n = build_cursor(entry["file"], entry["size"], entry["center"])
    apply_cursor(path, TARGETS[entry["target"]])
    return n
