"""Bước 1: phân tích một dự án trong INPUT/<tên>.

- Tìm clip quay và file thu âm giọng.
- Lấy thông tin clip và tạo ảnh "contact sheet" (khung hình kèm mốc giây) để chọn cảnh.
- Nhận dạng giọng nói (faster-whisper) lấy mốc thời gian từng từ.
- Cắt bớt khoảng lặng trong giọng đọc (cho nhịp nhanh) -> voice_tight.wav.
- Tạo phụ đề nháp.

Dùng:  .venv\\Scripts\\python tools\\analyze.py "<tên dự án>" [--model medium] [--max-gap 0.3] [--no-tighten]
"""
import argparse
import json
import math
import shutil
from pathlib import Path

from common import (AUDIO_EXT, CFG, FFMPEG, ROOT, VIDEO_EXT, VOICE_HINTS, media_duration, probe,
                    project_dir, run, work_dir)


def find_inputs(proj):
    files = [f for f in proj.rglob("*") if f.is_file() and not f.name.startswith(".")]
    vids = [f for f in files if f.suffix.lower() in VIDEO_EXT]
    auds = [f for f in files if f.suffix.lower() in AUDIO_EXT]
    hinted = lambda f: any(h in f.stem.lower().replace(" ", "_") for h in VOICE_HINTS) or "voice" in [p.lower() for p in f.parts]
    voice = None
    if auds:
        h = [f for f in auds if hinted(f)]
        voice = max(h or auds, key=lambda f: f.stat().st_size)
    else:
        h = [f for f in vids if hinted(f)]
        if h:
            voice = h[0]
    clips = sorted([f for f in vids if f != voice], key=lambda f: f.name.lower())
    return clips, voice


def clip_info(path, key):
    p = probe(path)
    v = next((s for s in p["streams"] if s["codec_type"] == "video"), None)
    if v is None:
        return None
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    rot = rot or int(float(v.get("tags", {}).get("rotate", 0)))
    if abs(rot) % 180 == 90:
        w, h = h, w
    num, den = (v.get("avg_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    return {
        "key": key,
        "path": str(path),
        "duration": round(float(p["format"]["duration"]), 3),
        "width": w,
        "height": h,
        "orientation": "doc" if h > w else "ngang",
        "fps": round(fps, 2),
        "hdr": v.get("color_transfer") in ("smpte2084", "arib-std-b67"),
        "codec": v.get("codec_name"),
        "pix_fmt": v.get("pix_fmt"),
        "has_audio": any(s["codec_type"] == "audio" for s in p["streams"]),
    }


def make_proxy(info, work):
    """Giải mã clip nặng (HEVC, 10-bit, >1080p, HDR) một lần sang H.264 1080p để dựng nhanh hơn."""
    heavy = (info["codec"] != "h264" or "10" in (info["pix_fmt"] or "") or info["hdr"]
             or min(info["width"], info["height"]) > 1080)
    if not heavy:
        return
    pdir = work / "proxy"
    pdir.mkdir(exist_ok=True)
    dst = pdir / (Path(info["key"]).stem + ".mp4")
    src = Path(info["path"])
    if not (dst.exists() and dst.stat().st_mtime > src.stat().st_mtime):
        print(f"  tạo proxy cho {info['key']} (một lần, giúp dựng nhanh hơn)...")
        size = "scale=-2:1080" if info["orientation"] == "ngang" else "scale=1080:-2"
        vf = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
              "zscale=t=bt709:m=bt709:r=tv," if info["hdr"] else "") + size + ",format=yuv420p"
        run([FFMPEG, "-y", "-v", "error", "-i", src, "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "16", "-g", "15", dst])
    info["source"] = info["path"]
    info["path"] = str(dst)
    info["hdr"] = False


def contact_sheets(info, sheets_dir, idx):
    d = info["duration"]
    step = 1 if d <= 30 else 2 if d <= 80 else math.ceil(d / 40)
    tw = 216 if info["orientation"] == "doc" else 384
    cols, rows = (6, 3) if info["orientation"] == "doc" else (4, 5)
    pattern = f"c{idx:02d}_%02d.jpg"
    vf = (f"fps=1/{step},scale={tw}:-2,"
          f"drawtext=fontfile=fonts/font.ttf:text='%{{eif\\:t\\:d}}s':x=6:y=6:fontsize=26:"
          f"fontcolor=yellow:box=1:boxcolor=black@0.7:boxborderw=4,"
          f"tile={cols}x{rows}:padding=4:color=gray")
    run([FFMPEG, "-y", "-v", "error", "-i", info["path"], "-vf", vf, "-q:v", "4", f"sheets/{pattern}"],
        cwd=sheets_dir.parent)
    return sorted(str(p) for p in sheets_dir.glob(f"c{idx:02d}_*.jpg")), step


def transcribe(wav16, prompt, model_name):
    from faster_whisper import WhisperModel
    import os
    import wave

    import numpy as np
    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4,
                         download_root=str(ROOT / ".models"))
    with wave.open(str(wav16), "rb") as wf:
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    # Không dùng initial_prompt: với kịch bản làm gợi ý, mô hình từng bỏ sót cả đoạn đầu.
    # VAD tắt để không mất câu nói nhỏ; Claude sửa chính tả phụ đề theo kịch bản ở bước sau.
    segs, info = model.transcribe(audio, language=CFG.get("language", "vi"), word_timestamps=True,
                                  vad_filter=False, beam_size=5, condition_on_previous_text=False)
    words = []
    for s in segs:
        for w in s.words or []:
            t = w.word.strip()
            if t:
                words.append({"w": t, "s": round(w.start, 3), "e": round(w.end, 3)})
    return words


def make_spans(words, total, max_gap, pad):
    spans = []
    for w in words:
        s, e = max(0.0, w["s"] - pad), min(total, w["e"] + pad)
        if spans and s - spans[-1][1] <= max_gap:
            spans[-1][1] = max(spans[-1][1], e)
        else:
            spans.append([s, e])
    return spans


def refine_spans(spans, wav16, max_gap, pad, frame=0.02):
    """Cắt thêm các khoảng lặng thật (theo âm lượng) nằm bên trong span, ví dụ chỗ ngập ngừng giữa câu."""
    import wave

    import numpy as np
    with wave.open(str(wav16), "rb") as wf:
        sr = wf.getframerate()
        a = np.frombuffer(wf.readframes(wf.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    n = int(sr * frame)
    fr = a[: len(a) // n * n].reshape(-1, n)
    db = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
    thr = max(np.percentile(db, 90) - 24, -50)
    silent = db < thr
    out = []
    min_sil = max_gap + 2 * pad
    for s, e in spans:
        i0, i1 = int(s / frame), min(int(e / frame), len(silent))
        cur = s
        i = i0
        while i < i1:
            if silent[i]:
                j = i
                while j < i1 and silent[j]:
                    j += 1
                if (j - i) * frame >= min_sil and i > i0 and j < i1:
                    out.append([cur, i * frame + pad])
                    cur = j * frame - pad
                i = j
            else:
                i += 1
        out.append([cur, e])
    return [p for p in out if p[1] - p[0] > 0.05]


def remap(t, spans):
    off = 0.0
    for s, e in spans:
        if t < s:
            return off
        if t <= e:
            return off + (t - s)
        off += e - s
    return off


def build_tight(raw, spans, work):
    parts, labels = [], []
    for i, (s, e) in enumerate(spans):
        d = e - s
        parts.append(f"[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d=0.012,afade=t=out:st={max(0, d - 0.012):.3f}:d=0.012[a{i}]")
        labels.append(f"[a{i}]")
    graph = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(spans)}:v=0:a=1[out]"
    (work / "tight_filter.txt").write_text(graph, "utf-8")
    run([FFMPEG, "-y", "-v", "error", "-i", raw, "-/filter_complex", work / "tight_filter.txt", "-map", "[out]",
         "-ar", "48000", "-ac", "1", work / "voice_tight.wav"])


def chunk_subs(words):
    subs, cur = [], []

    def flush(next_start):
        if not cur:
            return
        start, end = cur[0]["s"], cur[-1]["e"]
        end = max(end, min(next_start, end + 0.35)) if next_start is not None else end + 0.35
        subs.append({"start": round(start, 2), "end": round(end, 2), "text": " ".join(x["w"] for x in cur)})
        cur.clear()

    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        text = " ".join(x["w"] for x in cur)
        gap = (nxt["s"] - w["e"]) if nxt else 9
        punct = w["w"][-1] in ".,!?;:…"
        too_long = len(cur) >= 7 or len(text) >= 28
        # tránh để lại 1 từ lẻ cuối câu ở dòng sau
        if too_long and not punct and nxt and nxt["w"][-1] in ".,!?;:…" and len(text) < 40 and gap <= 0.25:
            continue
        if punct or too_long or gap > 0.25:
            flush(nxt["s"] if nxt else None)
    flush(None)
    return subs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--model", default=CFG.get("whisper_model", "medium"))
    ap.add_argument("--max-gap", type=float, default=0.30, help="khoảng lặng dài hơn mức này sẽ bị cắt")
    ap.add_argument("--pad", type=float, default=0.10)
    ap.add_argument("--no-tighten", action="store_true")
    ap.add_argument("--skip-sheets", action="store_true")
    ap.add_argument("--lang", default=None, help="ngôn ngữ giọng đọc (mặc định theo config, 'vi')")
    ap.add_argument("--cut", action="append", default=[], help="bỏ đoạn giọng gốc từ-đến (giây), lặp lại được")
    ap.add_argument("--reuse", action="store_true", help="dùng lại kết quả nhận dạng lần trước (nhanh)")
    a = ap.parse_args()

    proj = project_dir(a.name)
    work = work_dir(proj)
    (work / "fonts").mkdir(exist_ok=True)
    shutil.copy(CFG["font_file"], work / "fonts" / "font.ttf")
    clips, voice = find_inputs(proj)
    if not clips:
        raise SystemExit(f"Không có clip video nào trong {proj}")
    if not voice:
        raise SystemExit(f"Không tìm thấy file thu âm giọng trong {proj} (đặt file audio, ví dụ voice.m4a)")
    print(f"Dự án: {proj.name}\nGiọng đọc: {voice.name}\nSố clip: {len(clips)}")

    # --- clips ---
    sheets = work / "sheets"
    if sheets.exists() and not a.skip_sheets:
        shutil.rmtree(sheets)
    sheets.mkdir(exist_ok=True)
    infos = {}
    for i, c in enumerate(clips, 1):
        key = c.name
        info = clip_info(c, key)
        if not info:
            continue
        make_proxy(info, work)
        if not a.skip_sheets:
            info["sheets"], info["sheet_step"] = contact_sheets(info, sheets, i)
        infos[key] = info
        print(f"  [{i}] {key}: {info['duration']}s {info['width']}x{info['height']} ({info['orientation']})"
              f"{' HDR' if info['hdr'] else ''}")
    (work / "clips.json").write_text(json.dumps(infos, ensure_ascii=False, indent=1), "utf-8")

    # --- voice ---
    raw, wav16 = work / "voice_raw.wav", work / "voice16.wav"
    run([FFMPEG, "-y", "-v", "error", "-i", voice, "-vn", "-ac", "1", "-ar", "48000", raw])
    run([FFMPEG, "-y", "-v", "error", "-i", raw, "-ac", "1", "-ar", "16000", wav16])
    total = media_duration(raw)
    if a.lang:
        CFG["language"] = a.lang
    cache = work / "raw_words.json"
    sig = f"{voice}|{voice.stat().st_size}|{a.model}|{CFG.get('language')}"
    cached = json.loads(cache.read_text("utf-8")) if cache.exists() else {}
    if a.reuse and cached.get("sig") == sig:
        words = cached["words"]
        print("Dùng lại kết quả nhận dạng giọng nói đã có.")
    else:
        print(f"Nhận dạng giọng nói (model {a.model}), giọng dài {total:.1f}s ...")
        words = transcribe(wav16, "", a.model)
        cache.write_text(json.dumps({"sig": sig, "words": words}, ensure_ascii=False, indent=1), "utf-8")
    if not words:
        raise SystemExit("Không nhận dạng được lời nói nào trong file thu âm.")
    raw_subs = chunk_subs([dict(w) for w in words])

    # Bỏ các đoạn đọc vấp / đọc lại: --cut 18.9-21.4 (giây trên file giọng gốc)
    cuts = []
    for c in a.cut:
        s, e = (float(x) for x in c.split("-"))
        cuts.append((s, e))
    if cuts:
        before = len(words)
        words = [w for w in words if not any(s <= (w["s"] + w["e"]) / 2 <= e for s, e in cuts)]
        print(f"Đã bỏ {before - len(words)} từ trong các đoạn cắt {cuts}")

    if a.no_tighten:
        spans = [[0.0, total]]
        for s, e in sorted(cuts, reverse=True):
            spans = [p for sp in spans for p in ([sp[0], min(sp[1], s)], [max(sp[0], e), sp[1]]) if p[1] - p[0] > 0.02]
    else:
        spans = make_spans(words, total, a.max_gap, a.pad)
        spans = refine_spans(spans, wav16, a.max_gap, a.pad)
        if cuts:  # đảm bảo không còn phần nào của đoạn cắt lọt lại do pad
            spans = [[s, e] for s, e in spans]
            for cs, ce in cuts:
                new = []
                for s, e in spans:
                    if e <= cs or s >= ce:
                        new.append([s, e])
                    else:
                        if s < cs:
                            new.append([s, cs])
                        if e > ce:
                            new.append([ce, e])
                spans = [p for p in new if p[1] - p[0] > 0.05]
    build_tight(raw, spans, work)
    tight_total = media_duration(work / "voice_tight.wav")
    for w in words:
        w["s"], w["e"] = round(remap(w["s"], spans), 3), round(remap(w["e"], spans), 3)
    subs = chunk_subs(words)

    (work / "transcript.json").write_text(json.dumps({
        "voice_file": str(voice), "duration_raw": round(total, 2), "duration_tight": round(tight_total, 2),
        "spans": spans, "words": words}, ensure_ascii=False, indent=1), "utf-8")
    (work / "subs_draft.json").write_text(json.dumps(subs, ensure_ascii=False, indent=1), "utf-8")

    lines = [f"# Transcript {proj.name}", f"Giọng gốc {total:.1f}s -> sau khi cắt lặng {tight_total:.1f}s", ""]
    lines += [f"{s['start']:6.2f}-{s['end']:6.2f}  {s['text']}" for s in subs]
    lines += ["", "## Giọng gốc (mốc giây trên file thu âm, dùng cho --cut khi có đoạn đọc vấp/đọc lại)"]
    lines += [f"{s['start']:6.2f}-{s['end']:6.2f}  {s['text']}" for s in raw_subs]
    (work / "transcript.md").write_text("\n".join(lines), "utf-8")
    print("\n".join(lines))
    print(f"\nXong. Thư mục làm việc: {work}")
    if tight_total > 62:
        print(f"CẢNH BÁO: giọng dài {tight_total:.1f}s > 60s, cân nhắc voice_speed 1.05-1.12 trong edit.json")


if __name__ == "__main__":
    main()
