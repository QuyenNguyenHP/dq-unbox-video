"""Tạo giọng đọc AI (Microsoft Edge neural TTS, cần mạng) cho video không có giọng thật.

Dùng:  <python .venv> tools/tts.py "<tên dự án>" [--voice en-US-EmmaNeural] [--rate +8%]
Đọc lời thoại từ _work/<tên>/voiceover.txt, ghi ra _work/<tên>/voice_ai.mp3.
Sau đó: analyze.py "<tên>" --voice _work/<tên>/voice_ai.mp3 --lang en --skip-sheets

Giọng gợi ý: en-US-EmmaNeural (nữ, vui), en-US-AvaNeural (nữ, ấm), en-US-AndrewNeural (nam),
vi-VN-HoaiMyNeural (nữ tiếng Việt), vi-VN-NamMinhNeural (nam tiếng Việt).
"""
import argparse
import asyncio

from common import project_dir, work_dir


async def speak(text, voice, rate, out):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--voice", default="en-US-EmmaNeural")
    ap.add_argument("--rate", default="+8%")
    a = ap.parse_args()
    work = work_dir(project_dir(a.name))
    text = (work / "voiceover.txt").read_text("utf-8").strip()
    out = work / "voice_ai.mp3"
    asyncio.run(speak(text, a.voice, a.rate, out))
    print(f"Đã tạo giọng {a.voice}: {out}")


if __name__ == "__main__":
    main()
