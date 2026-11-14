"""Tạo vài bản nhạc nền vui, nhịp nhanh (tự tổng hợp, không bản quyền) vào thư mục MUSIC.

Dùng: .venv\\Scripts\\python tools\\make_music.py
Bạn có thể bỏ thêm file .mp3 nhạc không bản quyền vào MUSIC, hệ thống sẽ tự chọn.
"""
import wave

import numpy as np
from scipy.signal import butter, lfilter

from common import MUSIC

SR = 44100
rng = np.random.default_rng(7)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def env(n, a=0.005, d=0.2):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)
    return e


def lp(x, f, order=2):
    b, a = butter(order, f / (SR / 2), "low")
    return lfilter(b, a, x)


def hp(x, f, order=2):
    b, a = butter(order, f / (SR / 2), "high")
    return lfilter(b, a, x)


def saw(freq, n, detune=0.0):
    t = np.arange(n) / SR
    out = np.zeros(n)
    for dt in (-detune, 0, detune):
        ph = (t * freq * (1 + dt)) % 1.0
        out += 2 * ph - 1
    return out / 3


def kick(n=int(0.35 * SR)):
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def clap(n=int(0.22 * SR)):
    x = hp(rng.standard_normal(n), 900) * env(n, 0.001, 0.07)
    return lp(x, 6000) * 0.6


def hat(n=int(0.06 * SR)):
    return hp(rng.standard_normal(n), 7000) * env(n, 0.001, 0.018) * 0.35


def add(buf, x, pos):
    end = min(len(buf), pos + len(x))
    if pos < len(buf):
        buf[pos:end] += x[: end - pos]


def track(bpm, key, prog, seconds=80, bright=3500, swing=0.0):
    beat = 60 / bpm
    n = int(seconds * SR)
    drums, bass, pad, arp = (np.zeros(n) for _ in range(4))
    bars = int(seconds / (beat * 4)) + 1
    pump = np.ones(n)
    for bar in range(bars):
        chord = prog[bar % len(prog)]
        root = key + chord[0]
        notes = [key + c for c in chord]
        bar_start = bar * 4 * beat
        intro = bar < 2
        for b in range(4):
            p = int((bar_start + b * beat) * SR)
            if not intro or b in (0, 2):
                add(drums, kick() * 0.9, p)
                m = np.minimum(1, (np.arange(int(beat * SR)) / SR) / (beat * 0.55)) ** 1.5
                seg = pump[p:p + len(m)]
                pump[p:p + len(seg)] = np.minimum(seg, 0.35 + 0.65 * m[: len(seg)])
            if b in (1, 3) and not intro:
                add(drums, clap(), p)
            for h in (0.5,):
                hp_pos = int((bar_start + (b + h + swing) * beat) * SR)
                add(drums, hat(), hp_pos)
            if not intro:
                add(drums, hat() * 0.5, int((bar_start + (b + 0.25) * beat) * SR))
        # bass: 8th notes
        for e in range(8):
            p = int((bar_start + e * beat / 2) * SR)
            ln = int(beat / 2 * SR * 0.9)
            nn = root - 24 + (12 if e % 4 == 3 else 0)
            x = saw(midi(nn), ln) * env(ln, 0.003, 0.18)
            add(bass, x, p)
        # pad chord
        ln = int(4 * beat * SR)
        x = sum(saw(midi(nt), ln, 0.004) for nt in notes) / len(notes)
        a = np.minimum(1, np.arange(ln) / (0.08 * SR)) * np.minimum(1, (ln - np.arange(ln)) / (0.1 * SR))
        add(pad, x * a, int(bar_start * SR))
        # arp 16ths
        if bar >= 2:
            seq = notes + [notes[1] + 12, notes[2] + 12, notes[0] + 12, notes[2]]
            for s16 in range(16):
                p = int((bar_start + s16 * beat / 4) * SR)
                ln2 = int(beat / 4 * SR)
                f = midi(seq[s16 % len(seq)] + 12)
                t = np.arange(ln2) / SR
                tone = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * env(ln2, 0.002, 0.07)
                add(arp, tone, p)
    bass = lp(bass, 600) * 0.55
    pad = lp(pad, bright) * 0.28 * pump
    arp = lp(arp, 5000) * 0.18
    mix = drums * 0.8 + bass * pump + pad + arp
    fade = int(2 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade)
    # simple stereo: arp/pad slightly wide
    L = mix + 0.08 * np.roll(arp + pad, 300)
    R = mix + 0.08 * np.roll(arp + pad, -300)
    st = np.stack([L, R], 1)
    st = np.tanh(st * 1.2)
    st /= np.max(np.abs(st)) / 0.89
    return st


def save(path, st):
    data = (st * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


if __name__ == "__main__":
    MUSIC.mkdir(exist_ok=True)
    pop = [[0, 4, 7], [7, 11, 14], [9, 12, 16], [5, 9, 12]]       # I V vi IV
    minor = [[0, 3, 7], [-4, 0, 3], [-9, -5, -2], [-2, 2, 5]]     # i VI III VII
    happy = [[0, 4, 7], [5, 9, 12], [9, 12, 16], [7, 11, 14]]     # I IV vi V
    specs = [("dq_upbeat_01.wav", 124, 60, pop, 3800, 0.0),
             ("dq_tech_02.wav", 118, 57, minor, 2600, 0.0),
             ("dq_happy_03.wav", 128, 62, happy, 4500, 0.04)]
    for name, bpm, key, prog, bright, sw in specs:
        save(MUSIC / name, track(bpm, key, prog, bright=bright, swing=sw))
        print("Đã tạo", MUSIC / name)
