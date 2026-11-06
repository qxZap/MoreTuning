# Scenes for iconic.py: the diesel mixer (load layers, jake, turbo, blower, clatter) with the petrol
# extras on top: VTEC switch-over, blow-off valve, cam lope at idle, overrun crackle.
import sys, os, numpy as np
from scipy.signal import lfilter, butter, sosfilt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene_diesel as sd
from iconic import ICONIC
from scene import smooth_noise, bandpass, SR, rng

sd.DIESELS = ICONIC
sd.PULSES_PER_REV = {name: len(d["on"]) / 2 for name, d in ICONIC.items()}  # firings per revolution
PLAIN = sd.diesel_sound


def sound(name, folder, rpm, thr, jake):
    d = ICONIC[name]
    n = len(rpm)
    if d["lope"]:  # a lumpy cam: idle that hunts and stumbles
        idling = np.clip(1 - (rpm - d["idle"]) / (0.15 * (d["top"] - d["idle"])), 0, 1)
        rpm = rpm * (1 + idling * smooth_noise(n, 2.2, d["lope"]))
    y = PLAIN(name, folder, rpm, thr, jake)
    on = lfilter([0.004], [1, -0.996], thr)
    if d["lope"]:
        y *= 1 + idling * smooth_noise(n, 9, 0.35)
    if d["vtec"]:  # second cam lobe: the intake opens up and the top end gets hard and bright
        cam = np.clip((rpm - d["vtec"]) / 250, 0, 1) * on
        y += sosfilt(butter(2, 1400, 'highpass', fs=SR, output='sos'), y) * cam * 1.2
    if d["bov"]:
        boost = lfilter([0.0004], [1, -0.9996], on * np.clip((rpm - 2500) / 3500, 0, 1))
        lifts = np.flatnonzero((thr[1:] < 0.2) & (thr[:-1] >= 0.2)) + 1
        pssh = np.zeros(n)
        for i in lifts:
            if boost[i] > 0.15:
                m = min(n - i, int(0.5 * SR))
                pssh[i:i + m] += boost[i] * np.exp(-np.arange(m) / (0.12 * SR))
        y += sosfilt(bandpass(900, 6500), rng.standard_normal(n)) * pssh * 0.9
    if d["crackle"]:
        lift = (thr < 0.1) & (rpm > d["top"] * 0.45)
        pops = (rng.random(n) < 0.0009) & lift
        burst = np.zeros(n)
        burst[pops] = rng.uniform(0.4, 1.0, pops.sum())
        y += sosfilt(bandpass(300, 4000), lfilter([1], [1, -0.995], burst) * rng.standard_normal(n)) * 0.25
    return y


def chase(name, folder, frames, dur, out, cam):
    # sd.chase calls sd.diesel_sound: route it through sound() for this render only
    sd.diesel_sound = sound
    try:
        sd.chase(name, folder, frames, dur, out, cam=cam)
    finally:
        sd.diesel_sound = PLAIN


if __name__ == "__main__":
    folder, dst = sys.argv[1], sys.argv[2]
    names = sys.argv[3:] or list(ICONIC)
    for name in names:
        if name in ("series60", "cat3406e", "macke9", "om502", "8v92"):
            chase(name, folder, sd.GRADE, sd.GRADE_DUR, f"{dst}/{name}_grade.wav", 11.0)
        else:
            chase(name, folder, sd.PICKUP, 36.0, f"{dst}/{name}_canyon.wav", 8.0)
