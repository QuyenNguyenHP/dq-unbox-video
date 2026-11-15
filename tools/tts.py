"""Tạo giọng đọc AI (Microsoft Edge neural TTS, cần mạng) cho video không có giọng thật.

Dùng:  <python .venv> tools/tts.py "<tên dự án>" [--voice en-US-EmmaNeural] [--rate +8%]
Đọc lời thoại từ _work/<tên>/voiceover.txt, ghi ra _work/<tên>/voice_ai.mp3.
Sau đó: analyze.py "<tên>" --voice _work/<tên>/voice_ai.mp3 --lang en --skip-sheets

Giọng gợi ý: en-US-EmmaNeural (nữ, vui), en-US-AvaNeural (nữ, ấm), en-US-AndrewNeural (nam),
vi-VN-HoaiMyNeural (nữ tiếng Việt), vi-VN-NamMinhNeural (nam tiếng Việt).
"""
import argparse
import asyncio

from common import CFG, project_dir, work_dir


async def speak(text, voice, rate, out, pitch="+0Hz"):
    import edge_tts
    for attempt in range(6):  # dịch vụ đôi khi trả về rỗng (NoAudioReceived): thử lại
        try:
            await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(out))
            return
        except Exception as e:
            if attempt == 5:
                raise SystemExit(f"Không tạo được giọng {voice}: {e}")
            await asyncio.sleep(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--voice", default=None, help="tên ngắn hoặc mã giọng; bỏ trống = giọng mặc định theo --lang")
    ap.add_argument("--lang", default=None, help="en / vi: chọn giọng mặc định trong config (default_voice)")
    ap.add_argument("--rate", default="+8%")
    ap.add_argument("--pitch", default="+0Hz", help="cao độ, vd. +8Hz (trong trẻ), -6Hz (trầm ấm)")
    ap.add_argument("--variant", default=None, help="vd. vi -> _work/<tên>/vi/voiceover.txt")
    a = ap.parse_args()
    work = work_dir(project_dir(a.name), a.variant)
    text = (work / "voiceover.txt").read_text("utf-8").strip()
    out = work / "voice_ai.mp3"
    if not a.voice:
        lang = a.lang or ("vi" if a.variant == "vi" else "en")
        a.voice = CFG.get("default_voice", {}).get(lang, "emma")
    aliases = {**CFG.get("voice_aliases", {}), **CFG.get("voice_aliases_local", {})}
    voice = aliases.get(a.voice, a.voice)  # tên ngắn -> mã giọng
    if voice.startswith("vbee:"):
        from vbee import synth
        speed = round(1 + int(a.rate.strip("%")) / 100, 2)  # "+10%" -> 1.1
        synth(text, voice[5:], out, speed=speed)
    else:
        asyncio.run(speak(text, voice, a.rate, out, a.pitch))
    print(f"Đã tạo giọng {a.voice} ({voice}): {out}")


if __name__ == "__main__":
    main()
