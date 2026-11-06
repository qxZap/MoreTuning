# Listening scenes from the RPM loops: a canyon chase (camera following outside the car, rock-wall
# echoes and reverb, wind) and a drive-by (Doppler, distance, ground reflection, pan).
# The engine is never steady: revs wander, each firing differs in strength, throttle changes the tone,
# petrol engines crackle on lift-off and blip on downshifts, the diesel clatters and whistles its turbo.
import sys, glob, os, numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter, butter, sosfilt, fftconvolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engines import ENGINES

SR, C = 48000, 343.0
rng = np.random.default_rng(7)
CYLS = {"ej25": 4, "fa20": 4, "type1": 4, "gt3": 6, "993": 6, "powerstroke": 8}


def smooth_noise(n, hz, scale):
    k = max(2, int(n * hz / SR) + 2)
    return np.interp(np.arange(n), np.linspace(0, n, k), rng.standard_normal(k)) * scale


def bandpass(lo, hi):
    return butter(2, [lo, hi], 'bandpass', fs=SR, output='sos')


def loops(name, folder):
    out = {}
    for p in glob.glob(f"{folder}/{name}_*.wav"):
        sr, x = wavfile.read(p)
        x = x.astype(float)
        x = x.mean(axis=1) if x.ndim > 1 else x
        out[int(os.path.basename(p).rsplit('_', 1)[1][:-4])] = x / (np.abs(x).max() + 1e-9)
    return dict(sorted(out.items()))


def engine_sound(name, folder, rpm, thr):
    anc = loops(name, folder)
    keys = np.array(list(anc))
    n = len(rpm)
    petrol = ENGINES[name][3]
    rpm = rpm * (1 + smooth_noise(n, 3, 0.006) + smooth_noise(n, 0.4, 0.008))  # never quite steady
    rpm = np.clip(rpm, keys[0] * 0.8, keys[-1] * 1.05)
    lo_idx = np.clip(np.searchsorted(keys, rpm) - 1, 0, len(keys) - 2)
    lo, hi = keys[lo_idx], keys[lo_idx + 1]
    frac = np.clip((rpm - lo) / (hi - lo), 0, 1)
    y = np.zeros(n)
    for k in keys:
        w = np.where(lo == k, 1 - frac, 0) + np.where(hi == k, frac, 0)
        if w.max() == 0:
            continue
        src = anc[k]
        L = len(src)
        pos = np.cumsum(rpm / k) % L  # playback position, pitched by rpm / loop rpm
        i0 = pos.astype(int)
        fr = pos - i0
        y += w * (src[i0] * (1 - fr) + src[(i0 + 1) % L] * fr)
    # each firing a little different: an amplitude held per firing event
    events = np.cumsum(rpm / 60 * CYLS[name] / 2) / SR
    jit = rng.normal(1, 0.10, int(events[-1]) + 2)[events.astype(int)]
    y *= lfilter([0.02], [1, -0.98], jit)
    on = lfilter([0.003], [1, -0.997], thr)
    dark = sosfilt(butter(2, 700 if petrol else 500, fs=SR, output='sos'), y)
    out = (0.35 + 0.65 * on) * (on * y + (1 - on) * dark * 1.3)
    if petrol:
        # overrun crackle: sparse pops while off throttle at high revs
        lift = (thr < 0.1) & (rpm > ENGINES[name][2] * 0.45)
        pops = (rng.random(n) < 0.0009) & lift
        burst = np.zeros(n)
        burst[pops] = rng.uniform(0.4, 1.0, pops.sum())
        out += sosfilt(bandpass(300, 4000), lfilter([1], [1, -0.995], burst) * rng.standard_normal(n)) * 0.9
    else:
        # injection clatter: a sharp tick per firing, loudest at low load
        tick = np.zeros(n)
        tick[np.flatnonzero(np.diff(events.astype(int)) > 0)] = 1
        clat = sosfilt(bandpass(2500, 7000), lfilter([1], [1, -0.93], tick) * rng.standard_normal(n))
        out += clat * (0.55 - 0.3 * on) * 0.9
        # turbo: boost follows load and revs, slowly; a whine plus a rush of air
        boost = lfilter([0.0004], [1, -0.9996], on * np.clip((rpm - 1200) / 1800, 0, 1))
        ph = np.cumsum(2 * np.pi * (2500 + 6500 * boost) / SR)
        out += boost * (0.10 * np.sin(ph) + 0.18 * sosfilt(bandpass(1500, 5000), rng.standard_normal(n)))
    return out


def keyframes(name, frames, dur):
    idle, red = ENGINES[name][1], ENGINES[name][2]
    f = np.array(frames, float)
    t = np.arange(int(dur * SR)) / SR
    rpm = idle + np.interp(t, f[:, 0], f[:, 1]) * (red - idle)
    return t, rpm, np.interp(t, f[:, 0], f[:, 2]), np.interp(t, f[:, 0], f[:, 3])


# time s, rpm as a share of idle..redline, throttle, speed m/s
CANYON = [
    [0, 0.02, 0, 0], [1.4, 0.02, 0, 0], [1.6, 0.40, 1, 0], [2.0, 0.05, 0, 0],      # a rev at standstill
    [3.0, 0.08, 0.6, 0.5], [3.4, 0.25, 1, 3], [5.2, 0.86, 1, 14],                 # pull away in 1st
    [5.4, 0.48, 0.2, 14], [5.55, 0.50, 1, 14], [8.2, 0.90, 1, 26],                # 2nd
    [8.4, 0.58, 0.2, 26], [8.55, 0.60, 1, 26], [11.4, 0.92, 1, 37],               # 3rd
    [11.6, 0.86, 0, 36], [12.4, 0.62, 0, 30],                                     # lift and brake: crackle
    [12.6, 0.86, 0.9, 28], [12.75, 0.80, 0, 27], [13.5, 0.62, 0, 22],             # blip, down to 2nd
    [13.7, 0.84, 0.9, 20], [13.85, 0.78, 0, 19], [14.8, 0.50, 0.15, 15],          # blip, down again: the corner
    [15.6, 0.55, 1, 16], [18.0, 0.93, 1, 29],                                     # power out
    [18.2, 0.60, 0.2, 29], [18.35, 0.62, 1, 29], [21.6, 0.98, 1, 43],             # 3rd to the limiter
    [21.7, 0.93, 1, 43], [21.8, 0.99, 1, 43], [21.9, 0.93, 1, 43], [22.0, 0.99, 1, 43],
    [22.2, 0.70, 0.2, 43], [22.35, 0.72, 1, 43], [25.6, 0.88, 1, 52],             # 4th
    [25.8, 0.84, 0, 51], [27.6, 0.50, 0, 34],                                     # long lift, braking
    [27.8, 0.72, 0.9, 32], [27.95, 0.66, 0, 31], [29.2, 0.45, 0.3, 26],           # blip, settle
    [32.0, 0.40, 0.35, 27], [34.5, 0.30, 0.1, 24], [36.0, 0.25, 0, 22]]

TRUCK = [[0, 0.40, 0.5, 18], [2.5, 0.42, 0.5, 18], [2.8, 0.45, 1, 18.5], [6.0, 0.95, 1, 25],   # hauling
         [6.3, 0.60, 0.3, 25], [6.5, 0.62, 1, 25], [9.5, 0.90, 1, 30], [9.8, 0.85, 0, 30], [13.0, 0.35, 0, 26]]


def canyon_ir():
    n = int(2.6 * SR)
    t = np.arange(n) / SR
    ir = sosfilt(butter(2, 3500, fs=SR, output='sos'), rng.standard_normal(n) * np.exp(-t * 6.9 / 2.4) * 0.06)
    ir[0] = 1.0
    for d, g in ((0.11, 0.42), (0.17, 0.33), (0.29, 0.22), (0.41, 0.16), (0.63, 0.10)):  # rock walls
        ir[int(d * SR)] += g
    return ir


def write(st, t, out):
    st = st / np.abs(st).max() * 0.89
    fade = np.minimum(1, np.minimum(t / 0.5, (t[-1] - t) / 1.0))[:, None]
    wavfile.write(out, SR, (st * fade * 32767).astype(np.int16))
    print(os.path.basename(out))


def chase(name, folder, out):
    t, rpm, thr, speed = keyframes(name, CANYON, 36.0)
    n = len(t)
    eng = engine_sound(name, folder, rpm, thr)
    tyre = sosfilt(bandpass(200, 1200), rng.standard_normal(n)) * (speed / 40) ** 2 * 0.22
    wind = sosfilt(butter(2, 400, fs=SR, output='sos'), rng.standard_normal(n)) * (speed / 45) ** 2 * 0.5
    dist = 8 + 2.5 * np.sin(t * 0.45) + smooth_noise(n, 0.3, 0.8)  # the camera drifts as the road bends
    pan = 0.25 * np.sin(t * 0.3 + 1)
    dry = (eng + tyre) * (8 / dist)
    wet = fftconvolve(dry, canyon_ir())[:n] * 0.5
    st = np.stack([dry * (1 - pan) + wet + wind * 0.7, dry * (1 + pan) + wet * 0.9 + wind * 0.7], axis=1)
    write(st, t, out)


def driveby(name, folder, frames, dur, pass_at, out, d=7.5):
    t, rpm, thr, speed = keyframes(name, frames, dur)
    sig = engine_sound(name, folder, rpm, thr)
    sig += sosfilt(bandpass(250, 1400), rng.standard_normal(len(t))) * (speed / 40) ** 2 * 0.25
    x = np.cumsum(speed) / SR
    x -= np.interp(pass_at, t, x)
    st = np.zeros((len(t), 2))
    for img, gain in ((0.5, 1.0), (-0.5, 0.55)):  # direct sound and its ground reflection
        dist = np.sqrt(x ** 2 + d ** 2 + (1.6 - img) ** 2)
        te = t - dist / C
        for _ in range(2):
            xe = np.interp(te, t, x)
            dist = np.sqrt(xe ** 2 + d ** 2 + (1.6 - img) ** 2)
            te = t - dist / C
        s = np.interp(te * SR, np.arange(len(sig)), sig, left=0, right=0) * gain * (d / dist)
        y = np.zeros_like(s)
        zi = np.zeros(1)
        for b in range(0, len(s), 480):  # air absorption, in 10 ms blocks
            fc = np.clip(16000 * (8 / max(dist[b], 8)) ** 0.8, 1500, 16000)
            a = np.exp(-2 * np.pi * fc / SR)
            y[b:b + 480], zi = lfilter([1 - a], [1, -a], s[b:b + 480], zi=zi)
        az = np.arctan2(np.interp(te, t, x), d)
        st[:, 0] += y * np.cos((az + np.pi / 2) / 2)
        st[:, 1] += y * np.sin((az + np.pi / 2) / 2)
    write(st, t, out)


if __name__ == "__main__":
    folder, dst = sys.argv[1], sys.argv[2]
    for name in ("ej25", "fa20", "type1", "gt3", "993", "powerstroke"):
        chase(name, folder, f"{dst}/{name}_canyon.wav")
    driveby("powerstroke", folder, TRUCK, 13.0, 6.0, f"{dst}/powerstroke_driveby.wav", d=6.0)
