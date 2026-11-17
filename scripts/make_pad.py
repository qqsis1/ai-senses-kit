#!/usr/bin/env python3
"""正弦波四和弦铺底：一个音一个音算，不用任何采样音源。

用法：python make_pad.py <秒数> <输出.wav> [bpm]
默认 78 BPM、A 小调 Am–F–C–G，44.1kHz 单声道。
"""
import sys
import wave

import numpy as np

CHORDS = [
    [110.00, 164.81, 220.00],   # Am
    [87.31, 130.81, 174.61],    # F
    [130.81, 196.00, 261.63],   # C
    [98.00, 146.83, 196.00],    # G
]


def main() -> None:
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    out = sys.argv[2] if len(sys.argv) > 2 else "pad.wav"
    bpm = float(sys.argv[3]) if len(sys.argv) > 3 else 78.0

    sr = 44100
    beat = 60.0 / bpm
    bar = beat * 4

    n = int(dur * sr)
    pad = np.zeros(n)

    for i in range(int(dur / bar) + 1):
        start = i * bar
        if start > dur:
            break
        chord = CHORDS[i % 4]
        seg_n = int(min(bar, dur - start) * sr)
        if seg_n <= 0:
            break
        t = np.arange(seg_n) / sr
        env = np.minimum(1.0, t / 0.35) * np.minimum(1.0, (seg_n / sr - t) / 0.5)
        env = np.clip(env, 0, 1)
        seg = np.zeros(seg_n)
        for f in chord:
            seg += np.sin(2 * np.pi * f * t) * 0.33
            seg += np.sin(2 * np.pi * f * 2 * t) * 0.08
        a = int(start * sr)
        pad[a:a + seg_n] += seg * env

    # 低频轻律动：每拍一下衰减
    for k in range(int(dur / beat)):
        a = int(k * beat * sr)
        m = int(0.18 * sr)
        if a + m > n:
            break
        t = np.arange(m) / sr
        pad[a:a + m] += np.sin(2 * np.pi * 55 * t) * 0.06 * np.exp(-t * 18)

    pad = pad / (np.max(np.abs(pad)) + 1e-9) * 0.6
    fade = int(0.5 * sr)
    pad[:fade] *= np.linspace(0, 1, fade)
    pad[-fade:] *= np.linspace(1, 0, fade)

    data = (pad * 32767).astype(np.int16)
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())
    print("wrote", out, round(dur, 1), "s")


if __name__ == "__main__":
    main()
