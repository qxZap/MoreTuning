# Diesel scenes: on-load and overrun loops cross-faded by throttle (the way game audio layers load),
# plus jake brake, Roots blower (Detroit two-strokes), turbo and injection clatter.
# Trucks get a grade: pull away through the gears, lug up a long hill, crest, jake brake down it.
# The pickups get the canyon run. Camera outside, following, with mountain reverb.
import sys, glob, os, numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter, butter, sosfilt, fftconvolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diesels import DIESELS
from scene import smooth_noise, bandpass, canyon_ir, write, CANYON, SR, C, rng

PULSES_PER_REV = {"dd671": 6, "dd871": 8, "dd1271": 12, "dd1671": 16}  # two-strokes; inline sixes: 3


def loops(name, load, folder):
    out = {}
    for p in glob.glob(f"{folder}/{name}_{load}_*.wav"):
        sr, x = wavfile.read(p)
        x = x.astype(float)
        x = x.mean(axis=1) if x.ndim > 1 else x
        k = int(os.path.basename(p).rsplit('_', 1)[1][:-4])
        # synthesis does not keep loudness consistent between rpm steps: set it to rise with revs,
        # the overrun layer a fixed 6 dB under
        out[k] = x / (np.sqrt((x ** 2).mean()) + 1e-12) * (k / DIESELS[name]["top"]) ** 0.6 * (0.5 if load == "off" else 1.0)
    return dict(sorted(out.items()))


def play(anc, rpm):
    keys = np.array(list(anc))
    lo_idx = np.clip(np.searchsorted(keys, rpm) - 1, 0, len(keys) - 2)
    lo, hi = keys[lo_idx], keys[lo_idx + 1]
    frac = np.clip((rpm - lo) / (hi - lo), 0, 1)
    y = np.zeros(len(rpm))
    for k in keys:
        w = np.where(lo == k, 1 - frac, 0) + np.where(hi == k, frac, 0)
        if w.max() == 0:
            continue
        src = anc[k]
        L = len(src)
        pos = np.cumsum(rpm / k) % L
        i0 = pos.astype(int)
        fr = pos - i0
        y += w * (src[i0] * (1 - fr) + src[(i0 + 1) % L] * fr)
    return y


def diesel_sound(name, folder, rpm, thr, jake):
    d = DIESELS[name]
    n = len(rpm)
    rpm = rpm * (1 + smooth_noise(n, 2.5, 0.005) + smooth_noise(n, 0.3, 0.006))
    on_anc, off_anc = loops(name, "on", folder), loops(name, "off", folder)
    on = lfilter([0.004], [1, -0.996], thr)
    # an idling diesel still burns fuel: near idle the on-load layer plays, just quietly
    idling = np.clip(1 - (rpm - d["idle"]) / (0.2 * (d["top"] - d["idle"])), 0, 1)
    fuel = np.maximum(on, idling)
    y = (fuel * play(on_anc, rpm) + (1 - fuel) * play(off_anc, rpm)) * 0.25
    y *= 0.4 + 0.6 * on  # louder the harder it works
    ppr = PULSES_PER_REV.get(name, 3)
    events = np.cumsum(rpm / 60 * ppr) / SR
    fire = np.zeros(n)
    fire[np.flatnonzero(np.diff(events.astype(int)) > 0) + 1] = 1
    jit = rng.normal(1, 0.08, int(events[-1]) + 2)[events.astype(int)]
    y *= lfilter([0.03], [1, -0.97], jit)
    # injection clatter: a tick per firing, loudest at light load
    clat = sosfilt(bandpass(2200, 7000), lfilter([1], [1, -0.92], fire) * rng.standard_normal(n))
    y += clat * d["clatter"] * (0.45 - 0.25 * on) * 0.8
    if d["turbo"]:
        boost = lfilter([0.0003], [1, -0.9997], on * np.clip((rpm - d["idle"] * 1.6) / (d["top"] - d["idle"] * 1.6), 0, 1))
        ph = np.cumsum(2 * np.pi * (2200 + 6000 * boost) / SR)
        y += d["turbo"] * boost * (0.07 * np.sin(ph) + 0.12 * sosfilt(bandpass(1200, 4500), rng.standard_normal(n)))
    if d["blower"]:
        # gear-driven Roots blower: follows revs, not throttle; helical rotors give a bright whine
        f0 = rpm / 60 * 2 * 6
        ph = np.cumsum(2 * np.pi * f0 / SR)
        whine = sum(np.sin(h * ph) / h ** 0.7 for h in range(1, 7))
        y += whine * 0.035 * (rpm / d["top"]) ** 1.5
    if d["jake"]:
        # engine brake: each cylinder dumps its compressed air at the top of the stroke; the stack rings with it
        jk = lfilter([0.01], [1, -0.99], jake * (thr < 0.05))
        burst = lfilter([1], [1, -0.985], fire) * rng.standard_normal(n)
        stack = int(2 * 2.9 / C * SR)
        ring = lfilter([1], np.r_[1, np.zeros(stack - 1), -0.55], sosfilt(bandpass(150, 2600), burst))
        y += ring * jk * 2.2
        y *= 1 - 0.5 * jk + 0.5 * jk * (rpm / d["top"])  # the jake takes over from the engine's own overrun
    return y


def frames_to(name, frames, dur):
    d = DIESELS[name]
    f = np.array(frames, float)
    t = np.arange(int(dur * SR)) / SR
    rpm = d["idle"] + np.interp(t, f[:, 0], f[:, 1]) * (d["top"] - d["idle"])
    jake = np.interp(t, f[:, 0], f[:, 4]) if f.shape[1] > 4 else np.zeros(len(t))
    return t, rpm, np.interp(t, f[:, 0], f[:, 2]), np.interp(t, f[:, 0], f[:, 3]), jake


# time s, rpm share of idle..top, throttle, speed m/s, jake 0/1
GRADE = [[0, 0.0, 0, 0, 0], [1.6, 0.0, 0, 0, 0], [2.0, 0.30, 0.8, 0.5, 0], [2.6, 0.20, 0.6, 1.5, 0]]
t, sp = 2.6, 1.5
for g in range(6):  # six upshifts: pull, then a slow truck shift
    GRADE += [[t + 2.1, 0.72, 1, sp + 2.4, 0], [t + 2.2, 0.70, 0, sp + 2.4, 0], [t + 2.8, 0.47, 0, sp + 2.3, 0], [t + 3.0, 0.47, 1, sp + 2.3, 0]]
    t, sp = t + 3.0, sp + 2.3
GRADE += [[t + 6.0, 0.55, 1, sp - 1, 0], [t + 10.0, 0.42, 1, sp - 3, 0],                      # lugging up the grade
          [t + 10.3, 0.40, 0, sp - 3, 0], [t + 10.9, 0.66, 0.6, sp - 3, 0], [t + 11.1, 0.64, 1, sp - 3, 0],  # downshift
          [t + 14.0, 0.58, 1, sp - 4, 0], [t + 14.5, 0.62, 0, sp - 3.5, 1],                   # crest: off the fuel, jake on
          [t + 19.0, 0.86, 0, sp + 2, 1], [t + 19.3, 0.62, 0, sp + 2, 1], [t + 19.6, 0.88, 0, sp + 2, 1],  # downshift on the jake
          [t + 23.5, 0.80, 0, sp - 2, 1], [t + 24.0, 0.40, 0.2, sp - 3, 0], [t + 26.0, 0.30, 0.2, sp - 4, 0]]
GRADE_DUR = t + 26.0
PICKUP = [r + [0] for r in CANYON]


def chase(name, folder, frames, dur, out, cam=11.0):
    t, rpm, thr, speed, jake = frames_to(name, frames, dur)
    n = len(t)
    eng = diesel_sound(name, folder, rpm, thr, jake)
    tyre = sosfilt(bandpass(120, 900), rng.standard_normal(n)) * (speed / 30) ** 2 * 0.18
    wind = sosfilt(butter(2, 350, fs=SR, output='sos'), rng.standard_normal(n)) * (speed / 40) ** 2 * 0.4
    dist = cam + 2.5 * np.sin(t * 0.35) + smooth_noise(n, 0.25, 1.0)
    pan = 0.25 * np.sin(t * 0.27 + 0.5)
    dry = (eng + tyre) * (cam / dist)
    wet = fftconvolve(dry, canyon_ir())[:n] * 0.5
    st = np.stack([dry * (1 - pan) + wet + wind * 0.7, dry * (1 + pan) + wet * 0.9 + wind * 0.7], axis=1)
    env = np.sqrt(lfilter([0.0005], [1, -0.9995], (st ** 2).mean(axis=1)) + 1e-9)
    st *= np.minimum(1, (env / env.max()) ** -0.15 * 0.8)[:, None]  # gentle compression for small speakers
    write(st, t, out)


if __name__ == "__main__":
    folder, dst = sys.argv[1], sys.argv[2]
    for name in ("ntc400", "isx15", "c16", "macke6", "mp8", "6ct", "dd671", "dd871", "dd1271", "dd1671"):
        chase(name, folder, GRADE, GRADE_DUR, f"{dst}/{name}_grade.wav")
    for name in ("12v", "vp44"):
        chase(name, folder, PICKUP, 36.0, f"{dst}/{name}_canyon.wav", cam=8.0)
