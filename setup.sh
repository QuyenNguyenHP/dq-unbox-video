#!/usr/bin/env bash
# DQ Video - cài đặt trên macOS / Linux (chạy một lần):  bash setup.sh
# Tuỳ chọn: DQ_PYTHON=/đường/dẫn/python3 bash setup.sh
set -e
cd "$(dirname "$0")"
echo "== DQ Video setup =="

if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then brew install ffmpeg
  elif command -v apt-get >/dev/null 2>&1; then sudo apt-get update && sudo apt-get install -y ffmpeg fonts-dejavu-core
  else echo "Hãy cài ffmpeg (có libass) rồi chạy lại."; exit 1; fi
else
  echo "ffmpeg: đã có"
fi

PY="${DQ_PYTHON:-python3}"
"$PY" -c 'import sys; assert (3,10) <= sys.version_info[:2] <= (3,12), sys.version' \
  || { echo "Cần Python 3.10-3.12 (đặt DQ_PYTHON nếu có nhiều bản)"; exit 1; }
[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt

mkdir -p MUSIC
ls MUSIC/*.wav MUSIC/*.mp3 MUSIC/*.m4a >/dev/null 2>&1 || .venv/bin/python tools/make_music.py

HF_HUB_DISABLE_SYMLINKS_WARNING=1 .venv/bin/python -W ignore tools/doctor.py
