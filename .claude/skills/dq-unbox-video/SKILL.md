---
name: dq-unbox-video
description: Write the script for, and auto-edit, short (9:16 by default, or 16:9 / original ratio on request; 40-60s) unboxing/review videos of electronics, embedded boards, robots and tech gear for TikTok and Facebook Reels, using the user's own hand-and-product clips and their single-take voice recording, or an AI voiceover (e.g. English female) or music only when there is no recording; also works for travel/event clips. Use when the user asks to write a script ("viết kịch bản", "lên kịch bản") for a product video, or to edit/build/render a video ("dựng video", "làm video", "ghép video") from a folder in DQ Video/INPUT. Not for long-form videos or for videos with the user on camera.
---

# DQ Unbox Video

Always talk to the user in Vietnamese. The user is often on their phone (remote chat), so keep replies short and say exactly which folder or file they need to fill.

Project root: the folder containing `tools/` and `.claude/` (this repo, `DQ Video`).
Python: `.venv\Scripts\python.exe` on Windows, `.venv/bin/python` on macOS/Linux (the commands below use the Windows form; swap it on other systems). Run from the project root.
If `.venv` does not exist, this machine is not set up yet: run `setup.ps1` (Windows: `powershell -ExecutionPolicy Bypass -File setup.ps1`) or `bash setup.sh`, in the background since it can take 5-10 minutes, and check that `tools/doctor.py` prints "Sẵn sàng!".
Settings: `tools/config.json`, overridden per machine by `tools/config.local.json`. `"auto"` values are detected: ffmpeg, a bold Vietnamese-capable font, and Google Drive (`input_dir` = `My Drive/DQ Video/INPUT`, `drive_dir` = `My Drive/DQ Video/OUTPUT`; empty = not used).

## Folder layout

Projects are looked up first in the Google Drive input folder (`input_dir`, which the user fills from their phone) and then in the local `INPUT/`. Finished videos are copied to `drive_dir` (`My Drive/DQ Video/OUTPUT`). If the user has just uploaded from the phone, files on the Drive folder may still be syncing: if analyze fails to read a file or sizes look tiny, wait a minute and retry, and tell the user.

```
INPUT/<ten-video>/      (or the same on Drive) user drops: clips (.mp4/.mov), ONE voice recording (.m4a/.mp3/.wav, ideally named voice.*), optional kichban.md
_work/<ten-video>/      generated: clips.json, sheets/*.jpg, transcript.*, voice_tight.wav, edit.json, check.jpg
OUTPUT/<ten-video>.mp4  finished video (also copied to drive_dir)
MUSIC/                  background music (auto-picked; user may add royalty-free .mp3)
assets/logo.png         DQ Tech logo, put on every video
```

Style: fun, energetic, fast. The user is never on camera: only hands + product. Platform: TikTok / Facebook Reels.

---

## Mode A: write a script (kịch bản)

Input: product name + any info/link/specs the user gives. If key facts are missing (price, what's in the box, the 2-3 features they want to show), ask once, briefly; otherwise make reasonable assumptions and mark them `[?]`.

Target 50-58s finished. Vietnamese fast speech after silence trimming is about 3.5 syllables/s, so the spoken lines total **about 165-190 syllables (âm tiết)**.

Structure:

| Time | Part | Rule |
|---|---|---|
| 0-3s | HOOK | One punchy line: question, surprising number or bold claim. No greeting. |
| 3-13s | UNBOX | What's in the box, quick and funny. |
| 13-38s | FEATURES | Exactly 3 features, each ~8s: what it is + why it's cool. Use concrete numbers. |
| 38-52s | PROJECTS | 1-2 project ideas this enables (robot, IoT, smart home, ...). |
| 52-58s | END + CTA | One-line verdict + call to comment/follow. |

Write the file `INPUT/<ten-video>/kichban.md` (create the folder) with:
1. A title line and the on-screen hook text (≤ 7 words).
2. A table per part: time, **lời đọc** (each spoken line on its own row, starting with `> `), **cảnh cần quay** (concrete shot for the hand-held camera: e.g. "close-up chip, xoay nhẹ", "cắm cáp USB-C, đèn LED sáng").
3. A short shot checklist the user can follow while filming (vertical 9:16, good light, 3-5s per shot, keep the hands slow).

Lines starting with `> ` are fed to speech recognition as a vocabulary hint, so spell tech terms the way they should appear (ESP32-S3, Arduino, USB-C).
Show the script in chat too (compact) and tell the user: record the whole voice in one take, then put clips + voice in `INPUT/<ten-video>/`.

## Mode B: edit the video (dựng video)

### 1. Analyze
```
.venv\Scripts\python.exe tools\analyze.py "<ten-video>"
```
Takes a few minutes: heavy clips (HEVC/10-bit/>1080p/HDR, e.g. DJI or iPhone) are first converted once to an H.264 1080p proxy in `_work/<x>/proxy/`, and speech recognition (model `small`, ~45s per minute of voice) runs on the CPU. Run it in the background if it may pass 10 minutes. Options: `--max-gap 0.2` cuts pauses harder; `--no-tighten` keeps the natural pauses; `--reuse` reuses the previous speech recognition (fast re-run); `--skip-sheets` skips the frame images.
If it says no voice or no clips, tell the user which files are missing. The voice is the audio file whose name contains voice/thuam/giong/record, otherwise the largest audio file. If the voice was uploaded to the Drive INPUT root instead of the video's folder (phone recorders give files names like "New Recording 26.m4a"), copy the newest audio file into the project folder as `voice.m4a`.

**Flubs and retakes:** the user records in one take and sometimes repeats a sentence. Read the "Giọng gốc" section at the end of `transcript.md` (raw-file times). When a sentence is started and then read again, cut the first attempt and re-run:
```
.venv\Scripts\python.exe tools\analyze.py "<ten-video>" --reuse --skip-sheets --cut 18.7-22.5 [--cut a-b ...]
```
Hesitations inside a sentence (long "ừm", pauses) are removed automatically from the audio loudness.

### 2. Understand the material
- Read `_work/<x>/transcript.md` (sentence chunks with times on the trimmed voice timeline) and `INPUT/<x>/kichban.md` if it exists.
- Read `_work/<x>/clips.json`, then **look at every image** in `_work/<x>/sheets/` (`cNN_MM.jpg` = clip NN in clips order; each tile is labelled with its second in the source clip). Note what each clip shows at which seconds, and which moments are shaky, blurry, empty or out of frame.

### 3. Write `_work/<x>/edit.json`
All times are on the trimmed-voice timeline (`duration_tight`). Schema:
```json
{
  "aspect": "9:16",
  "voice_speed": 1.0,
  "music": "auto",
  "music_volume": 0.22,
  "tail": 0.6,
  "segments": [
    {"clip": "IMG_0001.MOV", "src": 3.0, "dur": 2.2, "speed": 1.0, "fit": "cover", "cx": 0.5, "cy": 0.5, "zoom": 0.0}
  ],
  "subtitles": [{"start": 0.0, "end": 1.4, "text": "..."}],
  "overlays": [{"start": 0.0, "end": 2.4, "text": "...", "style": "hook"}]
}
```
**Frame / aspect ratio** (`"aspect"`): default `"9:16"` (1080x1920, TikTok/Reels). When the user asks to keep the original ratio ("giữ nguyên tỷ lệ", "16:9", "quay ngang"), use `"16:9"` (1920x1080) for horizontal footage, or `"source"` to follow the majority orientation of the clips used. `"1:1"` and `"4:5"` also work. When the clip has the same orientation as the frame, leave out `fit`/`scale`/`cx`: the clip fills the frame (`cover`). Text sizes and positions adapt automatically (subtitles near the bottom, labels at the top, logo top-right). Remember the user's choice for that video in edit.json, and ask before changing it on later videos.

Rules for **segments** (played one after another; the sum of `dur` ≈ `duration_tight + tail`, and the last one is stretched automatically):
- Match the picture to the words: hook → the most striking shot (product hero close-up or the coolest demo moment); unbox → box opening and contents; each feature → the shot showing that part or behaviour; projects → demo or best wide shots; CTA → a clean hero shot.
- Cut on sentence/chunk boundaries from the transcript. Each cut is 1.2-3.5s, and there is a new shot at least every ~3s to keep the pace fast.
- `src` = second in the source clip, from the sheets. Make sure `src + dur*speed` fits in the clip (the last frame is held otherwise). Do not reuse the same moment twice unless you have to.
- `speed` 1.5-3 for slow actions (peeling, plugging in, long pans). `zoom` 0.06-0.12 on static shots. `fit`: `cover` fills the frame (default for vertical clips; for horizontal clips use `cx` to aim the crop); `blur` puts the frame on a blurred background (default for horizontal clips).
- Horizontal footage in a 9:16 frame (common: DJI on a desk): use `"fit": "blur", "scale": 1.5` for hand-held close-ups and `1.8` for wider shots, so the product stays big. Aim with `cx` (0 = left, 1 = right): estimate the product's horizontal centre `c` (0..1) from the sheet, then `cx ≈ (c - 0.5/scale) / (1 - 1/scale)`, clamped to 0..1.
- Skip shaky or blurry moments.

**subtitles**: start from `_work/<x>/subs_draft.json` and fix the recognition errors using the script and common sense: Vietnamese diacritics, tech names (ESP32, Arduino, Raspberry Pi, USB-C, LiDAR...), numbers. Keep the timings and keep each chunk ≤ ~30 characters. Leave it `[]` only if the draft is already perfect.

**overlays** (no emoji, the font cannot draw them):
- `hook`: big yellow top text, 0 → ~2.5s, ≤ 7 words.
- `label`: big yellow text with a black outline at the top, naming each feature while it is being talked about. Number them "① WiFi + BLE 5.0" (rendered as "1. WiFi + BLE 5.0").
- `big`: huge centre text for a price or key number ("150K", "240MHz"), 1-2s.
- `cta`: big yellow text in the centre for the last ~2-3s ("Follow để xem thêm!").

**Labels are always big yellow text, for every kind of video** (the user decided against the orange/blue pills). The old pill style still exists behind `"label_style": "pill"`; use it only if the user asks for it again.
**Logo:** tech videos (electronics, boards, robots, IT gear) get the DQ Tech logo (`assets/logo.png`) automatically in the top-right corner, below the TikTok/Reels top bar. Non-tech videos (travel, events, food, daily life...): set `"brand": false` in edit.json, which means no logo.

**Length**: if `duration_tight + tail` > 60s, set `voice_speed` (max 1.15). The render divides all times by it, so do not rescale anything yourself. If it would need more than 1.15, re-run analyze with `--max-gap 0.2`, or tell the user which part to cut.

### 3b. Write the post caption `_work/<x>/caption.txt`
Every finished video comes with a ready-to-paste caption for TikTok / Facebook Reels (the render copies it to `OUTPUT/<x>_caption.txt` and to Drive next to the video). Vietnamese, same fun tone, **short: 3 lines, about 200 characters before the hashtags** (the user found ~330 too long):
```
<hook line, a question or a bold claim, 1 emoji>
<product name: the features as keywords, separated by commas>
<(warning if needed) + CTA question to drive comments, 1 emoji>
#<product> #DQTech #unboxing #review #congnghe #<1 topic tag: dientu, iot, robot, esp32...>
```
Emoji are fine in the caption (only on-screen text can't show them), 2-3 in total. About 6 hashtags, lowercase except #DQTech. Facts must match what the video says; don't add claims. If the product could be misused (RF/NFC tools, cameras, jammers...), keep a "chỉ dùng với thiết bị của bạn" line.

### 4. Render and check
```
.venv\Scripts\python.exe tools\render.py "<ten-video>"
```
(`--draft` is a fast low-quality preview.) It takes ~1-3 minutes and writes `OUTPUT/<ten-video>.mp4` and `_work/<x>/check.jpg` (a frame every 2.5s), and copies the video to `drive_dir` when that is set.
Look at `check.jpg`: does each frame match what is being said at that time, is the text readable and not overlapping, are there no black or frozen frames? Fix `edit.json` and re-render if needed (at most 2 rounds without asking the user).

### 5. Report
Tell the user in a few lines: final length, the Drive/OUTPUT path, which music track, **the caption in a code block so it is easy to copy on the phone**, and anything you guessed (for example subtitle words you were unsure about). Send the finished mp4 with SendUserFile if that tool is available. Phone viewers only receive files ≤ 30 MB, so when the mp4 is bigger, make a 720p preview in the scratchpad (`ffmpeg -i OUTPUT/<x>.mp4 -vf scale=720:-2 -c:v libx264 -preset veryfast -crf 26 -c:a aac -b:a 128k -movflags +faststart <scratchpad>/<x>_preview.mp4`) and send that, noting that the full 1080p is on Drive. Ask if they want changes ("đổi nhạc", "cắt bớt đoạn X", "đổi chữ hook").

## Mode C: no user voice (AI voiceover or music only)

When the folder has clips but no voice recording, or the user asks for a voiceover "giọng AI / giọng nữ / tiếng Anh", or music only:
- Clips can be anything (travel, events, not only tech). Duplicate uploads like `IMG_5400 (1).MOV` with the same size are skipped automatically.
- First run `analyze.py "<x>"` (no voice is fine) to get proxies and frame sheets, and look at all sheets to understand the story.
- **AI voiceover**: write `_work/<x>/voiceover.txt` (plain spoken text, no markup; ~110-140 English words ≈ 40-50s, or ~170 Vietnamese syllables), in the house tone, hook first, CTA last, facts only from what is visible or well known (say "usually" for schedules). Then:
  ```
  .venv\Scripts\python.exe tools\tts.py "<x>" --voice en-US-EmmaNeural --rate +5%
  .venv\Scripts\python.exe tools\analyze.py "<x>" --voice _work\<x>\voice_ai.mp3 --lang en --no-tighten --skip-sheets
  ```
  Voices: `en-US-EmmaNeural` (female, cheerful; the user's choice for English), `en-US-AvaNeural`, `en-US-AndrewNeural` (male), `vi-VN-HoaiMyNeural` / `vi-VN-NamMinhNeural` (Vietnamese; use `--lang vi`). tts.py needs internet (Microsoft Edge TTS). Then continue with steps 2-5 as usual; subtitles, labels and caption are in the voiceover's language.
- **Music only**: skip the voiceover; segments alone set the length (aim 25-45s, cuts 1.5-3s on the strongest moments); leave `subtitles` empty, keep a hook and a CTA overlay. The music is louder automatically.

## Revisions
Edit `_work/<x>/edit.json` and re-run render only; there is no need to re-run analyze unless the voice file changed. To change the music: `"music": "<file in MUSIC>"` or `null` for none.

## Troubleshooting
- Run `tools/doctor.py` first: it shows the ffmpeg, font and Google Drive folders that were detected. To force a path, put it in `tools/config.local.json` (e.g. `{"ffmpeg": "..."}`).
- Phone HDR clips (iPhone HEVC) are tone-mapped automatically (`hdr: true` in clips.json).
- To regenerate the bundled music: `.venv\Scripts\python.exe tools\make_music.py`.
