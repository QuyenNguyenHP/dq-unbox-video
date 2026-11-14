# DQ Video

Automatic editing pipeline for short (50-60s, 9:16) unboxing/review videos of electronics, embedded boards, robots and tech gear, for TikTok and Facebook Reels.
For any request to write a script or to edit/build a video, follow the skill `.claude/skills/dq-unbox-video/SKILL.md`.

- Always reply to the user in Vietnamese.
- First time on a machine (no `.venv`): run `setup.ps1` (Windows) or `setup.sh` (macOS/Linux), then `tools/doctor.py` must say "Sẵn sàng!".
- Python: `.venv\Scripts\python.exe` on Windows, `.venv/bin/python` on macOS/Linux. On Windows ARM laptops it must be an x64 Python (faster-whisper has no ARM64 wheels); setup handles it.
- Scripts: `tools/analyze.py`, `tools/render.py`, `tools/make_music.py`, `tools/doctor.py`. Shared settings: `tools/config.json`; per-machine overrides: `tools/config.local.json` (not in git). ffmpeg, font and the Google Drive folder are auto-detected.

## House style (the channel owner's rules)
- The user is never on camera: hands + product only. Tone: fun, energetic, fast.
- Every video carries the DQ Tech logo (`assets/logo.png`) in the top-right corner. Never drop it unless asked.
- Feature labels are rounded pills in the brand colours: orange `#F44911` and blue `#0891DE` (alternate them). The CTA pill is blue.
- No emoji in on-screen text.
- Finished videos go to `OUTPUT/` and to Google Drive `My Drive/DQ Video/OUTPUT` when Google Drive for desktop is installed.
