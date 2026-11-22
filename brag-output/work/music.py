"""Soundtrack + SFX for the Accex launch video: 20 s, 120 BPM, F major, one beat grid from t=0.

python music.py out.wav
"""
import sys
import wave

import numpy as np

SR = 48000
DUR = 20.0
BEAT = 0.5
N = int(SR * DUR)
rng = np.random.default_rng(7)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env_adsr(n, a, d, s, r, sr=SR):
    a, d, r = int(a * sr), int(d * sr), int(r * sr)
    e = np.full(n, s, dtype=np.float64)
    e[:a] = np.linspace(0, 1, a, endpoint=False) if a else e[:a]
    e[a:a + d] = np.linspace(1, s, max(1, min(d, n - a)))[: max(0, min(d, n - a))]
    if r:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):          # small buffers only
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def lp_fast(x, cutoff, passes=2):
    """One-pole lowpass applied via cumulative filtering in blocks (vectorised enough)."""
    from math import exp
    a = exp(-2 * np.pi * cutoff / SR)
    for _ in range(passes):
        y = np.zeros_like(x)
        prev = 0.0
        # block-wise IIR using scipy-free trick: process with python loop on decimated chunks
        for i in range(0, len(x), 4096):
            seg = x[i:i + 4096]
            out = np.empty_like(seg)
            for j, v in enumerate(seg):
                prev = (1 - a) * v + a * prev
                out[j] = prev
            y[i:i + 4096] = out
        x = y
    return x


L = np.zeros(N)
R = np.zeros(N)
WET = np.zeros(N)            # reverb send (mono)


def put(sig, t, gain=1.0, pan=0.0, send=0.0):
    i = int(round(t * SR))
    if i >= N:
        return
    sig = sig[: N - i] * gain
    lg, rg = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    L[i:i + len(sig)] += sig * lg * 1.414
    R[i:i + len(sig)] += sig * rg * 1.414
    WET[i:i + len(sig)] += sig * send


# ---------------------------------------------------------------- harmony
CHORDS = [  # (start, end, pad notes, bass root)
    (0.0, 2.0, [50, 53, 57, 60, 64], 38),     # Dm9
    (2.0, 4.0, [46, 50, 53, 57, 62], 34),     # Bbmaj7
    (4.0, 6.0, [53, 57, 60, 64], 41),         # Fmaj7
    (6.0, 8.0, [57, 60, 64, 67], 45),         # Am7
    (8.0, 10.0, [50, 53, 57, 60], 38),        # Dm7
    (10.0, 12.0, [46, 50, 53, 57, 62], 34),   # Bbmaj7
    (12.0, 13.0, [53, 57, 60, 64], 41),       # Fmaj7
    (13.0, 15.0, [50, 53, 57, 62], 38),       # Dm (scam)
    (15.0, 16.0, [46, 50, 53, 58], 34),       # Bb
    (16.0, 17.0, [48, 52, 55, 60], 36),       # C
    (17.0, 20.0, [53, 57, 60, 64, 67], 29),   # Fmaj9 (resolve)
]


def pad_voice(m, n):
    t = np.arange(n) / SR
    f = hz(m)
    s = np.zeros(n)
    for det in (-0.12, 0.0, 0.11):           # detuned soft saws (few harmonics)
        ff = f * 2 ** (det / 12)
        for k in range(1, 7):
            s += np.sin(2 * np.pi * ff * k * t + k * 0.7) / (k ** 1.6)
    return s / 3


pad = np.zeros(N)
for a, b, notes, _ in CHORDS:
    n = int((b - a + 0.35) * SR)
    body = sum(pad_voice(m, n) for m in notes) / len(notes)
    e = env_adsr(n, 0.25 if a else 0.9, 0.3, 0.85, 0.45)
    i = int(a * SR)
    seg = body * e
    pad[i:i + len(seg)] += seg[: N - i]
pad = lp_fast(pad, 1800, passes=1)
pad_gain = np.interp(np.arange(N) / SR, [0, 3, 3.01, 13, 14, 17, 20], [0.20, 0.26, 0.2, 0.2, 0.24, 0.30, 0.30])
L += pad * pad_gain
R += pad * pad_gain
WET += pad * 0.12

# ---------------------------------------------------------------- drums


def kick():
    n = int(0.42 * SR)
    t = np.arange(n) / SR
    f = 46 + 110 * np.exp(-t * 32)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 7.5) + 0.15 * np.sin(ph * 2) * np.exp(-t * 30)


def hat(open_=False):
    n = int((0.16 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    x = rng.standard_normal(n)
    x = x - lp_fast(x, 7000, passes=1)        # highpass
    return x * np.exp(-t * (28 if open_ else 90))


def clap():
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    x = rng.standard_normal(n)
    x = lp_fast(x, 2600, passes=1) - lp_fast(x, 900, passes=1)
    e = np.exp(-t * 22)
    for off in (0.0, 0.011, 0.022):
        e += 0.5 * np.exp(-np.maximum(t - off, 0) * 120) * (t >= off)
    return x * e


K, H, C = kick(), hat(), clap()
for i in range(40):
    t = i * BEAT
    if 3.0 <= t < 13.0 and i % 2 == 0:
        put(K, t, 0.55)
    if 13.0 <= t < 17.0 and t in (14.0, 16.0):
        put(K, t, 0.5)
    if 7.0 <= t < 13.0 and i % 4 == 3:
        put(C, t, 0.16, 0.1, send=0.25)
for j in range(160):                           # 8th-note off-beat hats
    t = j * 0.25
    if 7.0 <= t < 12.75 and j % 2 == 1:
        put(H, t, 0.10, 0.35)
    if 4.0 <= t < 7.0 and j % 4 == 3:
        put(H, t, 0.06, 0.35)
put(K, 17.0, 0.5)

# ---------------------------------------------------------------- bass


def bass_note(m, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(m)
    s = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t)
    return s * env_adsr(n, 0.01, 0.15, 0.6, 0.08)


for a, b, _, root in CHORDS:
    if a < 3.0:
        continue
    step = 1.0 if a >= 13.0 else 0.5
    t = max(a, 3.0)
    while t < b - 1e-6:
        dur = min(step * 0.9, b - t)
        put(bass_note(root, dur), t, 0.30 if a < 17 else 0.22)
        t += step
    if a >= 17.0:
        break
put(bass_note(29, 2.8), 17.0, 0.26)

# ---------------------------------------------------------------- arp (the "working" energy)


def pluck(m, dur=0.22):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(m)
    s = 2 / np.pi * np.arcsin(np.sin(2 * np.pi * f * t))     # triangle
    s += 0.3 * np.sin(2 * np.pi * 2 * f * t)
    return s * np.exp(-t * 14) * np.minimum(1, t * 400)


for j in range(160):
    t = j * 0.125
    if not (7.0 <= t < 12.875):
        continue
    notes = next(c[2] for c in CHORDS if c[0] <= t < c[1])
    seq = [notes[k % len(notes)] + 12 for k in (0, 2, 1, 3, 2, 4, 3, 1)]
    m = seq[j % 8]
    put(pluck(m), t, 0.075, 0.4 * np.sin(j), send=0.3)
for j in range(16):                                         # gentle 8th arp in the reveal
    t = 4.0 + j * 0.25
    if t >= 6.75:
        break
    notes = next(c[2] for c in CHORDS if c[0] <= t < c[1])
    put(pluck(notes[(0, 2, 1, 3)[j % 4] % len(notes)] + 12, 0.3), t, 0.05, -0.3, send=0.4)

# ---------------------------------------------------------------- SFX (same key, same grid)


def bell(m, dur=1.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(m)
    s = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2.0 * f * t) * np.exp(-t * 4)
         + 0.12 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 6))
    return s * np.exp(-t * 3.2) * np.minimum(1, t * 300)


def click(bright=1.0):
    n = int(0.03 * SR)
    t = np.arange(n) / SR
    x = rng.standard_normal(n)
    x = x - lp_fast(x, 2500 * bright, passes=1)
    return x * np.exp(-t * 260) + 0.4 * np.sin(2 * np.pi * 1760 * t) * np.exp(-t * 200)


def whoosh(dur=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = rng.standard_normal(n)
    x = lp_fast(x, 1400, passes=2)
    e = (t / dur) ** 2.2
    return x * e / (np.abs(x).max() + 1e-9)


# listening earcon at 3.8: two rising notes (A5 -> D6)
put(bell(81, 0.5), 3.75, 0.10, send=0.3)
put(bell(86, 0.6), 3.875, 0.10, send=0.3)
# thinking at 5.5: soft high F
put(bell(89, 0.8), 5.5, 0.05, send=0.4)
# cursor click 8.5, typing 9.0-9.7, enter 10.0
put(click(1.0), 8.5, 0.30, 0.2)
for j in range(6):
    put(click(1.6), 9.0 + j * 0.125, 0.10 + 0.03 * (j % 2), 0.15)
put(click(0.8), 10.0, 0.34, 0.1)
# done chime at 10.5: F6 A6 C7
for k, m in enumerate((89, 93, 96)):
    put(bell(m, 1.3), 10.5 + k * 0.125, 0.11, (k - 1) * 0.3, send=0.45)
# whooshes into each cut
for t in (7.0, 13.0, 17.0):
    w = whoosh(0.5)
    put(w, t - 0.5, 0.07, 0, send=0.3)
# scam blocked at 14.0: low D-minor stab + thud
stab_n = int(0.9 * SR)
tt = np.arange(stab_n) / SR
stab = sum(np.sin(2 * np.pi * hz(m) * tt) * (1 + 0.3 * np.sin(2 * np.pi * 2 * hz(m) * tt)) for m in (38, 45, 50, 53))
stab *= np.exp(-tt * 4.5) * np.minimum(1, tt * 200) / 4
put(stab, 14.0, 0.42, send=0.35)
put(K, 14.0, 0.25)
# outro bells at 17.0: F5 C6 F6 then A6
for k, m in enumerate((77, 84, 89)):
    put(bell(m, 2.6), 17.0 + k * 0.125, 0.10, (k - 1) * 0.35, send=0.55)
put(bell(93, 2.4), 17.5, 0.08, 0.2, send=0.55)

# ---------------------------------------------------------------- reverb (FFT convolution with a noise tail)
ir_n = int(1.6 * SR)
ti = np.arange(ir_n) / SR
irL = rng.standard_normal(ir_n) * np.exp(-ti * 3.2)
irR = rng.standard_normal(ir_n) * np.exp(-ti * 3.2)
irL, irR = lp_fast(irL, 5000, 1), lp_fast(irR, 5000, 1)
irL /= np.sqrt((irL ** 2).sum()); irR /= np.sqrt((irR ** 2).sum())
size = 1 << int(np.ceil(np.log2(N + ir_n)))
Wf = np.fft.rfft(WET, size)
L += np.fft.irfft(Wf * np.fft.rfft(irL, size), size)[:N] * 0.5
R += np.fft.irfft(Wf * np.fft.rfft(irR, size), size)[:N] * 0.5

# ---------------------------------------------------------------- master
fade_in = np.minimum(1, np.arange(N) / (0.05 * SR))
fade_out = np.clip((DUR - np.arange(N) / SR) / 0.6, 0, 1)
mix = np.stack([L, R]) * fade_in * fade_out
mix = np.tanh(mix * 1.3) / np.tanh(1.3)
mix /= np.abs(mix).max() / 0.89
pcm = (mix.T * 32767).astype(np.int16)
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("wrote", sys.argv[1])
