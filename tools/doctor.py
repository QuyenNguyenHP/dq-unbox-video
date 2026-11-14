"""Kiểm tra máy đã sẵn sàng dựng video chưa:  <python của .venv> tools/doctor.py"""
import subprocess

from common import CFG, MUSIC, ROOT

ok = True


def check(name, cond, hint=""):
    global ok
    print(f"  [{'OK' if cond else '!!'}] {name}" + ("" if cond else f"  -> {hint}"))
    ok = ok and bool(cond)


def ffmpeg_has(filters):
    try:
        out = subprocess.run([CFG["ffmpeg"], "-hide_banner", "-filters"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout
    except OSError:
        return False
    return all(f" {f} " in out for f in filters)


print("Kiểm tra DQ Video:")
check(f"ffmpeg: {CFG['ffmpeg']}", ffmpeg_has(["ass", "sidechaincompress", "loudnorm"]),
      "cài ffmpeg bản đầy đủ (có libass), hoặc đặt 'ffmpeg' trong tools/config.local.json")
check("ffmpeg có zscale (tone-map clip HDR)", ffmpeg_has(["zscale"]), "không bắt buộc; clip HDR sẽ lỗi màu")
check(f"font: {CFG['font_name']} ({CFG['font_file']})", True)
try:
    import faster_whisper  # noqa: F401
    import numpy, PIL, scipy  # noqa: F401,E401
    check("thư viện Python (faster-whisper, numpy, scipy, pillow)", True)
except Exception as e:  # pragma: no cover
    check("thư viện Python", False, str(e))
check("nhạc nền trong MUSIC/", MUSIC.exists() and any(MUSIC.glob("*.*")), "chạy tools/make_music.py")
check("logo assets/logo.png", (ROOT / "assets" / "logo.png").exists(), "đặt logo PNG nền trong suốt vào assets/")
print(f"  Google Drive INPUT : {CFG.get('input_dir') or '(không thấy Google Drive, chỉ dùng INPUT/ trên máy)'}")
print(f"  Google Drive OUTPUT: {CFG.get('drive_dir') or '(không chép lên Drive)'}")
print("Sẵn sàng!" if ok else "Còn mục cần sửa (xem dấu !!).")
