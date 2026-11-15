"""Giọng đọc tiếng Việt từ Vbee (studio.vbee.vn), kể cả giọng bạn đã nhân bản (clone).

Cần trong tools/config.local.json (KHÔNG đưa lên git):
  {"vbee_app_id": "<App ID>", "vbee_token": "<token eyJ...>"}

Dùng:
  <python .venv> tools/vbee.py voices                       # liệt kê giọng (của bạn + Vbee)
  <python .venv> tools/vbee.py say "<giọng>" "<lời>" out.mp3 [--speed 1.1]
  tools/tts.py "<dự án>" --voice vbee:<mã giọng> ...           # dùng trong quy trình dựng video
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from common import CFG

TTS_URL = "https://api.vbee.vn/v1/tts"
VOICES_URL = "https://vbee.vn/api/public/v1/voices"
# Không có máy chủ nhận webhook: dùng địa chỉ cục bộ (không gửi dữ liệu cho bên thứ ba), rồi tự hỏi kết quả.
LOCAL_WEBHOOK = "https://localhost/vbee-callback"


def _headers():
    if not CFG.get("vbee_token") or not CFG.get("vbee_app_id"):
        raise SystemExit("Thiếu vbee_app_id / vbee_token trong tools/config.local.json")
    return {"Authorization": f"Bearer {CFG['vbee_token']}", "App-Id": CFG["vbee_app_id"],
            "Content-Type": "application/json", "Accept": "application/json, audio/mpeg"}


def _request(url, body=None, method="GET", timeout=120):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read()


def list_voices(ownership=None, language="vi-VN"):
    out, cursor = [], None
    for own in ([ownership] if ownership else ["PERSONAL", "VBEE"]):
        cursor = None
        while True:
            q = f"?voice_ownership={own}&language_code={language}&limit=100" + (f"&cursor={cursor}" if cursor else "")
            code, _, raw = _request(VOICES_URL + q)
            if code != 200:
                raise SystemExit(f"Vbee lỗi {code}: {raw[:300]!r}")
            res = json.loads(raw)["result"]
            for v in res.get("voices", []):
                v["ownership"] = own
                out.append(v)
            cursor = res.get("pagination", {}).get("next_cursor")
            if not res.get("pagination", {}).get("has_next_page"):
                break
    return out


def _chunks(text, limit=280):
    """Chế độ đồng bộ chỉ nhận ≤300 ký tự: tách theo câu."""
    parts, cur = [], ""
    for sent in re.split(r"(?<=[.!?…])\s+|\n+", text.strip()):
        sent = sent.strip()
        if not sent:
            continue
        while len(sent) > limit:  # câu quá dài: cắt ở dấu phẩy gần nhất
            cut = sent.rfind(",", 0, limit)
            cut = cut if cut > 50 else limit
            parts.append(sent[:cut + 1].strip())
            sent = sent[cut + 1:].strip()
        if cur and len(cur) + 1 + len(sent) > limit:
            parts.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        parts.append(cur)
    return parts


def _sync(text, voice, speed):
    code, ctype, raw = _request(TTS_URL, {"text": text, "voiceCode": voice, "mode": "sync",
                                          "outputFormat": "mp3", "bitrate": 128, "speed": speed}, "POST")
    if code == 200 and "json" not in ctype and len(raw) > 1000:
        return raw
    raise RuntimeError(f"sync {code}: {raw[:300]!r}")


def _async(text, voice, speed):
    code, _, raw = _request(TTS_URL, {"text": text, "voiceCode": voice, "mode": "async", "webhookUrl": LOCAL_WEBHOOK,
                                      "outputFormat": "mp3", "bitrate": 128, "speed": speed}, "POST")
    if code not in (200, 201):
        raise RuntimeError(f"async {code}: {raw[:300]!r}")
    rid = json.loads(raw)["requestId"]
    for _ in range(120):
        time.sleep(2)
        code, _, raw = _request(f"{TTS_URL}/requests/{rid}")
        info = json.loads(raw) if raw else {}
        info = info.get("result", info)
        st = info.get("status")
        if st == "COMPLETED" and info.get("audioLink"):
            with urllib.request.urlopen(info["audioLink"], timeout=120) as r:
                return r.read()
        if st == "FAILED":
            raise RuntimeError(f"Vbee báo lỗi: {info}")
    raise RuntimeError("Vbee xử lý quá lâu")


def synth(text, voice, out, speed=1.0, ffmpeg=None):
    """Tạo mp3. Thử chế độ đồng bộ theo từng câu; giọng không hỗ trợ thì dùng chế độ bất đồng bộ."""
    out = Path(out)
    if CFG.get("vbee_mode", "async") == "async":  # gói hiện tại không hỗ trợ chế độ sync
        out.write_bytes(_async(text, voice, speed))
        return out
    try:
        pieces = [_sync(p, voice, speed) for p in _chunks(text)]
    except RuntimeError as e:
        print(f"  (chế độ nhanh không dùng được cho giọng này: {str(e)[:120]}; chuyển sang chế độ chờ)")
        out.write_bytes(_async(text, voice, speed))
        return out
    if len(pieces) == 1:
        out.write_bytes(pieces[0])
        return out
    # ghép các đoạn mp3 bằng ffmpeg cho sạch
    from common import FFMPEG, run
    tmpdir = out.parent / (out.stem + "_parts")
    tmpdir.mkdir(exist_ok=True)
    lst = []
    for i, b in enumerate(pieces):
        f = tmpdir / f"p{i:03d}.mp3"
        f.write_bytes(b)
        lst.append(f"file '{f.as_posix()}'")
    (tmpdir / "list.txt").write_text("\n".join(lst), "utf-8")
    run([ffmpeg or FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", tmpdir / "list.txt",
         "-c:a", "libmp3lame", "-b:a", "192k", out])
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("voices")
    s = sub.add_parser("say")
    s.add_argument("voice")
    s.add_argument("text")
    s.add_argument("out")
    s.add_argument("--speed", type=float, default=1.0)
    a = ap.parse_args()
    if a.cmd == "voices":
        for v in list_voices():
            tag = "GIỌNG CỦA BẠN" if v["ownership"] == "PERSONAL" else ""
            print(f"{v['code']} | {v['name']} | {v['gender']} | x{v.get('credit_factor')} {tag}")
    else:
        synth(a.text, a.voice, a.out, a.speed)
        print("Đã tạo", a.out)


if __name__ == "__main__":
    main()
