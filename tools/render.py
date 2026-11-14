"""Bước 2: dựng video từ _work/<tên>/edit.json.

Dùng:  .venv\\Scripts\\python tools\\render.py "<tên dự án>" [--draft]

edit.json (mọi mốc thời gian tính trên giọng đã cắt lặng voice_tight.wav, trước voice_speed):
{
  "voice_speed": 1.0,            # 1.0-1.15, tăng tốc giọng nếu video quá 60s
  "music": "auto",               # "auto" | tên file trong MUSIC | null
  "music_volume": 0.22,
  "tail": 0.6,                   # giây giữ lại sau câu cuối
  "segments": [                  # nối tiếp nhau, tổng dur ~ duration_tight + tail
    {"clip": "IMG_0001.MOV", "src": 3.2, "dur": 2.4,
     "speed": 1.0,               # >1 tua nhanh cảnh trong clip
     "fit": "cover",             # cover (cắt đầy khung) | blur (giữ nguyên, nền mờ)
     "cx": 0.5, "cy": 0.5,       # vị trí cắt khi cover (0..1)
     "zoom": 0.0}                # 0.05-0.15 = zoom chậm vào
  ],
  "subtitles": [{"start": 0.0, "end": 1.4, "text": "..."}],   # bỏ trống -> dùng subs_draft.json
  "overlays": [{"start": 0.0, "end": 2.5, "text": "...", "style": "hook|label|big|cta"}]
}
"""
import argparse
import json
import random
import shutil
import sys

from common import CFG, FFMPEG, MUSIC, OUTPUT, ROOT, ass_time, media_duration, project_dir, run, work_dir

W, H, FPS = CFG["width"], CFG["height"], CFG["fps"]
FONT = CFG["font_name"]
BOLD = "-1" if CFG.get("font_bold") else "0"

ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{FONT},72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,{BOLD},0,0,0,100,100,0,0,1,6,3,2,90,90,420,1
Style: hook,{FONT},96,&H0000E6FF,&H00FFFFFF,&H00000000,&H96000000,{BOLD},0,0,0,100,100,0,0,1,8,4,8,70,70,300,1
Style: label,{FONT},66,&H00FFFFFF,&H00FFFFFF,&H00008CFF,&H00000000,{BOLD},0,0,0,100,100,0,0,3,16,0,8,90,90,330,1
Style: big,{FONT},150,&H0000E6FF,&H00FFFFFF,&H00000000,&H96000000,{BOLD},0,0,0,100,100,0,0,1,10,5,5,60,60,0,1
Style: cta,{FONT},68,&H00000000,&H00FFFFFF,&H0000E6FF,&H00000000,{BOLD},0,0,0,100,100,0,0,3,18,0,5,90,90,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

POP = r"{\fad(80,120)\fscx80\fscy80\t(0,140,\fscx100\fscy100)}"


def ass_text(t):
    return t.replace("{", "(").replace("}", ")").replace("\n", r"\N")


def write_ass(path, subs, overlays, k):
    out = [ASS_HEADER]
    for o in overlays:
        style = o.get("style", "label")
        if style in BADGE_STYLES:
            continue  # vẽ bằng PNG bo tròn (make_badges)
        out.append(f"Dialogue: 1,{ass_time(o['start'] / k)},{ass_time(o['end'] / k)},{style},,0,0,0,,"
                   f"{POP}{ass_text(o['text'])}")
    for s in subs:
        out.append(f"Dialogue: 0,{ass_time(s['start'] / k)},{ass_time(s['end'] / k)},Sub,,0,0,0,,"
                   f"{{\\fad(40,40)}}{ass_text(s['text'])}")
    path.write_text("\n".join(out) + "\n", "utf-8-sig")


# Màu thương hiệu DQ Tech (lấy từ assets/logo.png)
BRAND = {"orange": (244, 73, 17), "blue": (8, 145, 222)}
BADGE_STYLES = {"label": {"color": "orange", "size": 58, "y": 330},
                "cta": {"color": "blue", "size": 64, "y": None}}
LOGO = ROOT / "assets" / "logo.png"
LOGO_W, LOGO_X, LOGO_Y = 140, 40, 150  # logo góc trên phải, tránh thanh menu TikTok/Reels


def make_badge(text, color, size, path):
    """Nhãn bo tròn kiểu viên thuốc, chữ trắng, có bóng mờ."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    font = ImageFont.truetype(CFG["font_file"], size)
    # "① ..." hoặc "1. ..." ở đầu -> vẽ số trong vòng tròn trắng (font không có ký tự ①)
    num = None
    circled = "①②③④⑤⑥⑦⑧⑨"
    if text[:1] in circled:
        num, text = str(circled.index(text[0]) + 1), text[1:].strip()
    elif len(text) > 2 and text[0].isdigit() and text[1] in ".)":
        num, text = text[0], text[2:].strip()
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    l, t, r, b = tmp.textbbox((0, 0), text, font=font, anchor="ls")
    tw = r - l
    th = int(size * 1.0)
    padx, pady, sh = int(size * 0.75), int(size * 0.38), 14
    h = th + 2 * pady
    cd = h - 16 if num else 0
    w = tw + 2 * padx + (cd - padx // 2 + 8 if num else 0)
    img = Image.new("RGBA", (w + 2 * sh, h + 2 * sh), (0, 0, 0, 0))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((sh, sh + 6, sh + w, sh + h + 6), radius=h // 2, fill=(0, 0, 0, 110))
    img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(8)))
    d = ImageDraw.Draw(img)
    rgb = BRAND.get(color, BRAND["orange"])
    d.rounded_rectangle((sh, sh, sh + w, sh + h), radius=h // 2, fill=rgb + (255,),
                        outline=(255, 255, 255, 230), width=4)
    if num:
        cx0, cy0 = sh + 8, sh + 8
        d.ellipse((cx0, cy0, cx0 + cd, cy0 + cd), fill=(255, 255, 255, 255))
        nf = ImageFont.truetype(CFG["font_file"], int(size * 0.9))
        d.text((cx0 + cd / 2, cy0 + cd / 2), num, font=nf, fill=rgb + (255,), anchor="mm")
        tx = cx0 + cd + (w - cd - 8) / 2 - 4
    else:
        tx = sh + w / 2
    d.text((tx, sh + h / 2), text, font=font, fill=(255, 255, 255, 255), anchor="mm")
    img.save(path)
    return img.size


def make_badges(overlays, work, k):
    bdir = work / "badges"
    bdir.mkdir(exist_ok=True)
    items = []
    for i, o in enumerate(overlays):
        st = o.get("style", "label")
        if st not in BADGE_STYLES:
            continue
        spec = BADGE_STYLES[st]
        p = bdir / f"b{i:02d}.png"
        bw, bh = make_badge(o["text"], o.get("color", spec["color"]), spec["size"], p)
        y = spec["y"] if spec["y"] is not None else (H - bh) // 2
        items.append((p, o["start"] / k, o["end"] / k, (W - bw) // 2, y))
    return items


HDR_TM = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
          "zscale=t=bt709:m=bt709:r=tv,format=yuv420p,")


def render_segment(seg, clip, outdur, dst, draft):
    speed = float(seg.get("speed", 1.0))
    src = max(0.0, float(seg.get("src", 0.0)))
    need = outdur * speed
    if src >= clip["duration"] - 0.1:
        src = max(0.0, clip["duration"] - need)
    fit = seg.get("fit") or ("cover" if clip["orientation"] == "doc" else "blur")
    zoom = float(seg.get("zoom", 0.0))
    cx, cy = float(seg.get("cx", 0.5)), float(seg.get("cy", 0.5))
    fgs = float(seg.get("scale", 1.0))  # blur: phóng khung chính (1.0 = vừa ngang, 1.5 = to hơn, cắt hai bên)
    pre = (HDR_TM if clip.get("hdr") else "") + f"setpts=(PTS-STARTPTS)/{speed},fps={FPS},"
    if fit == "blur":
        g = (f"[0:v]{pre}split[a][b];"
             f"[a]scale={W // 4}:{H // 4}:force_original_aspect_ratio=increase,crop={W // 4}:{H // 4},"
             f"boxblur=12:2,eq=brightness=-0.06,scale={W}:{H}[bg];"
             f"[b]scale={int(W * fgs) // 2 * 2}:-2,crop='min(iw,{W})':'min(ih,{H})':x='(iw-ow)*{cx}':y='(ih-oh)*{cy}'[fg];"
             f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v0]")
    else:
        g = (f"[0:v]{pre}scale={W}:{H}:force_original_aspect_ratio=increase,"
             f"crop={W}:{H}:x='(iw-{W})*{cx}':y='(ih-{H})*{cy}'[v0]")
    if zoom > 0:
        g += (f";[v0]scale=w='trunc({W}*(1+{zoom}*t/{outdur:.3f})/2)*2':h=-2:eval=frame,"
              f"crop={W}:{H}[v1]")
        last = "[v1]"
    else:
        last = "[v0]"
    g += f";{last}tpad=stop_mode=clone:stop_duration={outdur:.3f},trim=duration={outdur:.3f},setsar=1,format=yuv420p[v]"
    run([FFMPEG, "-y", "-v", "error", "-ss", f"{src:.3f}", "-t", f"{need + 0.2:.3f}", "-i", clip["path"],
         "-filter_complex", g, "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "ultrafast" if draft else "veryfast",
         "-crf", "26" if draft else "17", "-r", str(FPS), dst])


def pick_music(edit, name):
    m = edit.get("music", "auto")
    if not m:
        return None
    tracks = sorted(p for p in MUSIC.iterdir() if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"))
    if m != "auto":
        p = MUSIC / m
        if p.exists():
            return p
        print(f"Không thấy nhạc '{m}', chọn tự động.")
    return random.Random(name).choice(tracks) if tracks else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--draft", action="store_true", help="dựng nhanh chất lượng thấp để xem thử")
    a = ap.parse_args()

    proj = project_dir(a.name)
    work = work_dir(proj)
    edit = json.loads((work / "edit.json").read_text("utf-8"))
    clips = json.loads((work / "clips.json").read_text("utf-8"))
    tr = json.loads((work / "transcript.json").read_text("utf-8"))
    k = float(edit.get("voice_speed", 1.0))
    voice_d = tr["duration_tight"] / k
    tail = float(edit.get("tail", 0.6))
    segs = edit["segments"]

    # --- kiểm tra ---
    problems = []
    for i, s in enumerate(segs):
        if s["clip"] not in clips:
            problems.append(f"đoạn {i}: không có clip '{s['clip']}' (có: {list(clips)})")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        raise SystemExit(1)
    durs = [float(s["dur"]) / k for s in segs]
    D = max(sum(durs), voice_d + tail)
    if sum(durs) < D:
        durs[-1] += D - sum(durs)
    print(f"Giọng {voice_d:.2f}s, tổng video {D:.2f}s, {len(segs)} đoạn cắt")

    # --- dựng từng đoạn hình ---
    seg_dir = work / "segs"
    if seg_dir.exists():
        shutil.rmtree(seg_dir)
    seg_dir.mkdir()
    lst = []
    for i, (s, d) in enumerate(zip(segs, durs)):
        dst = seg_dir / f"s{i:03d}.mp4"
        render_segment(s, clips[s["clip"]], d, dst, a.draft)
        lst.append(f"file 'segs/s{i:03d}.mp4'")
        print(f"  đoạn {i + 1}/{len(segs)}: {s['clip']} @{s.get('src', 0)}s  {d:.2f}s")
    (work / "concat.txt").write_text("\n".join(lst), "utf-8")
    run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "concat.txt", "-c", "copy", "video.mp4"], cwd=work)

    # --- phụ đề + chữ ---
    subs = edit.get("subtitles") or json.loads((work / "subs_draft.json").read_text("utf-8"))
    write_ass(work / "subs.ass", subs, edit.get("overlays", []), k)

    # --- âm thanh + xuất ---
    music = pick_music(edit, proj.name)
    mv = float(edit.get("music_volume", CFG.get("music_volume", 0.22)))
    fmt = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
    voice_chain = (f"[1:a]{'atempo=%.4f,' % k if abs(k - 1) > 1e-3 else ''}highpass=f=80,afftdn=nf=-30,"
                   f"acompressor=threshold=0.125:ratio=3:attack=5:release=120:makeup=2,"
                   f"loudnorm=I=-14:TP=-1.5:LRA=9,{fmt},apad=whole_dur={D:.3f}")
    cmd = [FFMPEG, "-y", "-v", "error", "-i", "video.mp4", "-i", "voice_tight.wav"]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        graph = (f"{voice_chain},asplit=2[vo][sc];"
                 f"[2:a]{fmt},atrim=0:{D:.3f},asetpts=N/SR/TB,volume={mv},afade=t=in:d=0.4,"
                 f"afade=t=out:st={max(0, D - 1.5):.3f}:d=1.5[mu];"
                 f"[mu][sc]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=350[mud];"
                 f"[vo][mud]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[aout];")
        print(f"Nhạc nền: {music.name}")
    else:
        graph = f"{voice_chain},alimiter=limit=0.95[aout];"
    # --- chữ (ASS) + nhãn bo tròn + logo ---
    idx = 3 if music else 2
    graph += "[0:v]ass=subs.ass:fontsdir=fonts[v0]"
    last = "[v0]"
    for j, (png, s0, s1, x, y) in enumerate(make_badges(edit.get("overlays", []), work, k)):
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{D:.3f}", "-i", str(png)]
        fo = max(s0, s1 - 0.15)
        graph += (f";[{idx}:v]format=rgba,fade=t=in:st={s0:.3f}:d=0.15:alpha=1,"
                  f"fade=t=out:st={fo:.3f}:d=0.15:alpha=1[b{j}];"
                  f"{last}[b{j}]overlay=x={x}:y={y}:enable='between(t,{s0:.3f},{s1:.3f})'[v{j + 1}]")
        last = f"[v{j + 1}]"
        idx += 1
    if LOGO.exists() and edit.get("logo", True):
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{D:.3f}", "-i", str(LOGO)]
        graph += (f";[{idx}:v]scale={LOGO_W}:-1,format=rgba,colorchannelmixer=aa=0.95[lg];"
                  f"{last}[lg]overlay=x=W-w-{LOGO_X}:y={LOGO_Y}[vl]")
        last = "[vl]"
    graph += f";{last}null[vout]"
    out_name = proj.name + ("_draft" if a.draft else "") + ".mp4"
    tmp = work / "final.mp4"
    run(cmd + ["-filter_complex", graph, "-map", "[vout]", "-map", "[aout]", "-t", f"{D:.3f}",
               "-c:v", "libx264", "-preset", "veryfast" if a.draft else "medium", "-crf", "28" if a.draft else "19",
               "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(FPS),
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "final.mp4"], cwd=work)

    OUTPUT.mkdir(exist_ok=True)
    out = OUTPUT / out_name
    shutil.copy(tmp, out)
    print(f"Đã xuất: {out}  ({media_duration(out):.1f}s)")
    cap = work / "caption.txt"
    if cap.exists() and not a.draft:
        shutil.copy(cap, OUTPUT / f"{proj.name}_caption.txt")
        print(f"Caption: {OUTPUT / f'{proj.name}_caption.txt'}")

    # ảnh kiểm tra: 1 khung mỗi 2.5s
    run([FFMPEG, "-y", "-v", "error", "-i", "final.mp4", "-vf",
         "fps=0.4,scale=216:-2,drawtext=fontfile=fonts/font.ttf:text='%{eif\\:t\\:d}s':x=6:y=6:fontsize=24:"
         "fontcolor=yellow:box=1:boxcolor=black@0.7,tile=8x3:padding=4:color=gray",
         "-frames:v", "1", "-q:v", "4", "check.jpg"], cwd=work)
    print(f"Ảnh kiểm tra: {work / 'check.jpg'}")

    drive = CFG.get("drive_dir")
    if drive and not a.draft:
        from pathlib import Path
        dd = Path(drive)
        if dd.parent.exists():
            dd.mkdir(parents=True, exist_ok=True)
            shutil.copy(out, dd / out_name)
            print(f"Đã chép lên Google Drive: {dd / out_name}")
            if (OUTPUT / f"{proj.name}_caption.txt").exists():
                shutil.copy(OUTPUT / f"{proj.name}_caption.txt", dd / f"{proj.name}_caption.txt")
        else:
            print(f"CẢNH BÁO: không thấy thư mục Google Drive {dd}, chưa chép lên Drive.")


if __name__ == "__main__":
    main()
