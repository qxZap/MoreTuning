# A drive-by from enginesound RPM loops: the engine follows a scripted run (blend of the two nearest
# loops, each pitched to the exact rpm), then the car passes a listener with Doppler, distance, air
# absorption, a ground reflection, stereo pan and tyre noise.
import sys, glob, os, numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter, butter, sosfilt

SR, C = 48000, 343.0

def anchors(engine, folder):
    out = {}
    for p in glob.glob(f"{folder}/{engine}_*.wav"):
        sr, x = wavfile.read(p); x = x.astype(float); x = x.mean(axis=1) if x.ndim > 1 else x
        out[int(os.path.basename(p).split('_')[1][:-4])] = x / (np.abs(x).max() + 1e-9)
    return dict(sorted(out.items()))

def engine_track(anc, rpm, throttle):
    keys = np.array(list(anc)); n = len(rpm); y = np.zeros(n)
    phase = {k: 0.0 for k in keys}
    lo_idx = np.clip(np.searchsorted(keys, rpm) - 1, 0, len(keys) - 2)
    for k_i, k in enumerate(keys):
        # weight of this anchor per sample (linear between neighbours)
        lo, hi = keys[lo_idx], keys[lo_idx + 1]
        w = np.where(lo == k, (hi - rpm) / (hi - lo), 0) + np.where(hi == k, (rpm - lo) / (hi - lo), 0)
        w = np.clip(w, 0, 1)
        if w.max() == 0: continue
        src = anc[k]; L = len(src)
        pos = np.cumsum(rpm / k) % L  # playback position, pitched by rpm / anchor rpm
        i0 = pos.astype(int); fr = pos - i0
        y += w * (src[i0] * (1 - fr) + src[(i0 + 1) % L] * fr)
    # lift-off: quieter and darker, the way an engine on overrun sounds
    on = lfilter([0.002], [1, -0.998], throttle)  # smoothed throttle 0..1
    dark = sosfilt(butter(2, 900, fs=SR, output='sos'), y)
    return (0.45 + 0.55 * on) * (on * y + (1 - on) * dark)

def run(script, dur):
    t = np.arange(int(dur * SR)) / SR
    rpm = np.interp(t, script[:, 0], script[:, 1]); thr = np.interp(t, script[:, 0], script[:, 2])
    speed = np.interp(t, script[:, 0], script[:, 3])  # m/s
    return t, rpm, thr, speed

def place(sig, speed, t, pass_at, d=7.5, h_src=0.4, h_ear=1.6):
    x = np.cumsum(speed) / SR; x -= np.interp(pass_at, t, x)  # 0 when abreast of the listener
    out = np.zeros((len(t), 2))
    for img, gain in ((h_src, 1.0), (-h_src, 0.55)):  # direct path and its ground reflection
        dist = np.sqrt(x**2 + d**2 + (h_ear - img)**2)
        te = t - dist / C  # emission time heard now (Doppler comes from this)
        for _ in range(2):
            xe = np.interp(te, t, x); dist = np.sqrt(xe**2 + d**2 + (h_ear - img)**2); te = t - dist / C
        s = np.interp(te * SR, np.arange(len(sig)), sig, left=0, right=0) * gain * (d / dist)
        # air absorption: lose highs with distance, in 10 ms blocks
        y = np.zeros_like(s); zi = np.zeros(1); B = 480
        for b in range(0, len(s), B):
            fc = np.clip(16000 * (8 / max(dist[b], 8)) ** 0.8, 1500, 16000)
            a = np.exp(-2 * np.pi * fc / SR)
            y[b:b+B], zi = lfilter([1 - a], [1, -a], s[b:b+B], zi=zi)
        az = np.arctan2(np.interp(te, t, x), d)  # left to right as it passes
        out[:, 0] += y * np.cos((az + np.pi / 2) / 2); out[:, 1] += y * np.sin((az + np.pi / 2) / 2)
    return out

def tyres(speed, n):
    noise = np.random.default_rng(1).standard_normal(n)
    return sosfilt(butter(2, [250, 1400], 'bandpass', fs=SR, output='sos'), noise) * (speed / 40) ** 2 * 0.25

def make(engine, folder, script, dur, pass_at, out):
    t, rpm, thr, speed = run(np.array(script, float), dur)
    sig = engine_track(anchors(engine, folder), rpm, thr) + tyres(speed, len(t))
    st = place(sig, speed, t, pass_at)
    st = st / np.abs(st).max() * 0.89
    fade = np.minimum(1, np.minimum(t / 0.6, (dur - t) / 0.8))[:, None]
    wavfile.write(out, SR, (st * fade * 32767).astype(np.int16))
    print(out, f"rpm {rpm.min():.0f}-{rpm.max():.0f}, top {speed.max()*3.6:.0f} km/h")

folder = sys.argv[1]
# time s, rpm, throttle, speed m/s
make("flat4", folder, [
    [0, 3400, 0.4, 24], [3.0, 3500, 0.4, 25],          # cruising up in 3rd
    [3.3, 3700, 1, 26], [5.6, 6400, 1, 41],            # floored past the listener
    [5.75, 4700, 0.2, 41], [5.9, 4750, 1, 41],         # shift to 4th
    [8.6, 5700, 1, 50], [8.8, 5650, 0, 50],            # pulls on, then lifts
    [12.0, 3300, 0, 44]], 12.0, 5.2, sys.argv[2] + "/flat4_driveby.wav")
make("flat6", folder, [
    [0, 4600, 0.5, 30], [2.6, 4800, 0.5, 31],
    [2.9, 5000, 1, 32], [5.4, 7900, 1, 50],            # the wail up to the limiter
    [5.55, 6200, 0.2, 50], [5.7, 6250, 1, 50],         # into 4th
    [8.2, 7600, 1, 61], [8.4, 7550, 0, 61],
    [12.0, 4200, 0, 54]], 12.0, 5.0, sys.argv[2] + "/flat6_driveby.wav")
