"""Shared helpers for the DQ Video pipeline."""
import glob
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()


def _load_config():
    """config.json (chung, có trong git) + config.local.json (riêng từng máy, không đưa lên git)."""
    cfg = json.loads((ROOT / "tools" / "config.json").read_text("utf-8"))
    local = ROOT / "tools" / "config.local.json"
    if local.exists():
        cfg.update(json.loads(local.read_text("utf-8")))
    return cfg


def _find_ffmpeg(name):
    p = shutil.which(name)
    if p:
        return p
    exe = name + (".exe" if os.name == "nt" else "")
    pats = [os.path.expandvars(rf"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin\{exe}"),
            os.path.expandvars(rf"%LOCALAPPDATA%\Microsoft\WinGet\Links\{exe}"),
            rf"C:\ffmpeg\bin\{exe}", f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}", f"/usr/bin/{name}",
            str(ROOT / "tools" / "bin" / exe)]
    for pat in pats:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return name  # để lỗi rõ ràng khi chạy


# (đường dẫn font, tên họ font trong file, có cần bật Bold không)
FONT_CANDIDATES = [
    ("C:/Windows/Fonts/seguibl.ttf", "Segoe UI Black", False),
    ("C:/Windows/Fonts/arialbd.ttf", "Arial", True),
    ("/System/Library/Fonts/Supplemental/Arial Black.ttf", "Arial Black", False),
    ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "Arial", True),
    ("/Library/Fonts/Arial Bold.ttf", "Arial", True),
    ("/usr/share/fonts/truetype/noto/NotoSans-Black.ttf", "Noto Sans", False),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVu Sans", True),
]


def _find_font(cfg):
    if cfg.get("font_file", "auto") != "auto" and Path(cfg["font_file"]).exists():
        return cfg["font_file"], cfg.get("font_name", "Arial"), bool(cfg.get("font_bold", False))
    for path, name, bold in FONT_CANDIDATES:
        if Path(path).exists():
            return path, name, bold
    raise SystemExit("Không tìm thấy font đậm hỗ trợ tiếng Việt. Đặt font_file/font_name trong tools/config.local.json")


def _find_drive_root():
    """Thư mục 'My Drive' của Google Drive for desktop (Windows: ổ G:..., macOS: ~/Library/CloudStorage)."""
    names = ("My Drive", "Drive của tôi")
    if os.name == "nt":
        for letter in "GHIJKLMNOPQRSTUVWXYZDEF":
            for n in names:
                p = Path(f"{letter}:/{n}")
                try:
                    if p.is_dir():
                        return p
                except OSError:
                    pass
    else:
        for base in glob.glob(str(HOME / "Library" / "CloudStorage" / "GoogleDrive-*")) + [str(HOME / "Google Drive")]:
            for n in names:
                p = Path(base) / n
                if p.is_dir():
                    return p
    return None


def _resolve(cfg):
    if cfg.get("ffmpeg", "auto") == "auto" or not Path(cfg["ffmpeg"]).exists():
        cfg["ffmpeg"] = _find_ffmpeg("ffmpeg")
    if cfg.get("ffprobe", "auto") == "auto" or not Path(cfg["ffprobe"]).exists():
        sib = Path(cfg["ffmpeg"]).with_name("ffprobe" + (".exe" if os.name == "nt" else ""))
        cfg["ffprobe"] = str(sib) if sib.exists() else _find_ffmpeg("ffprobe")
    cfg["font_file"], cfg["font_name"], cfg["font_bold"] = _find_font(cfg)
    folder = cfg.get("drive_folder", "DQ Video")
    if "auto" in (cfg.get("input_dir"), cfg.get("drive_dir")):
        root = _find_drive_root()
        for key, sub in (("input_dir", "INPUT"), ("drive_dir", "OUTPUT")):
            if cfg.get(key) == "auto":
                cfg[key] = str(root / folder / sub) if root else ""
                if root:
                    Path(cfg[key]).mkdir(parents=True, exist_ok=True)
    return cfg


CFG = _resolve(_load_config())
FFMPEG = CFG["ffmpeg"]
FFPROBE = CFG["ffprobe"]
INPUT = ROOT / "INPUT"
# Thư mục chứa dự án: INPUT trên Drive (nếu có) và INPUT trên máy
INPUT_DIRS = [Path(CFG["input_dir"])] if CFG.get("input_dir") else []
INPUT_DIRS = [d for d in INPUT_DIRS if d.is_dir()] + [INPUT]
OUTPUT = ROOT / "OUTPUT"
WORK = ROOT / "_work"
MUSIC = ROOT / "MUSIC"

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm", ".3gp", ".mts"}
AUDIO_EXT = {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".opus", ".flac", ".wma", ".amr", ".3ga"}
VOICE_HINTS = ("voice", "thuam", "thu_am", "thu-am", "giong", "record", "ghiam", "ghi_am", "audio", "long_tieng", "longtieng")

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def run(cmd, cwd=None, quiet=True):
    cmd = [str(c) for c in cmd]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("LỖI khi chạy:", " ".join(cmd[:6]), "...", file=sys.stderr)
        print(r.stderr[-4000:], file=sys.stderr)
        raise SystemExit(1)
    if not quiet:
        print(r.stdout)
    return r.stdout


def probe(path):
    out = run([FFPROBE, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path])
    return json.loads(out)


def media_duration(path):
    return float(probe(path)["format"]["duration"])


def project_dir(name):
    for base in INPUT_DIRS:
        p = base / name
        if p.is_dir():
            return p
    all_dirs = [d for base in INPUT_DIRS for d in base.iterdir() if d.is_dir()]
    cands = [d for d in all_dirs if name.lower() in d.name.lower()]
    if len(cands) == 1:
        return cands[0]
    names = [str(d) for d in all_dirs]
    print(f"Không tìm thấy (hoặc trùng nhiều) thư mục dự án '{name}'. Hiện có: {names}", file=sys.stderr)
    raise SystemExit(1)


def work_dir(proj):
    w = WORK / proj.name
    w.mkdir(parents=True, exist_ok=True)
    return w


def ass_time(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
