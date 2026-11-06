# The "bee" buzz: firing overtones standing far above the noise between them in 1.5-6 kHz.
# overtone_ratio(): FFT of 2 s; mean power within 8 % (of the firing frequency) of a firing harmonic vs mean power
# more than 25 % away from every harmonic, in dB. A real recording (Teh's boxer4_high.wav) is about -0.4 dB;
# shipped loops must be <= LIMIT.
# turbulence(): firing turbulence, band-passed noise (1.2-9 kHz, 2nd-order Butterworth) under an envelope that
# gets a random-strength pulse (uniform 0.5-1.5) at every firing event and decays with a 1.2 ms time constant,
# mixed at 0.3x the loop's RMS. Built circularly (noise filtered with wrap-around, the envelope wraps too) and the
# firing period divides the loop length, so the loop stays seamless.
#   python buzz.py demo     checks the measure on the coordinator's s65 test files
import os, sys, re, glob, numpy as np
from scipy.signal import butter, sosfilt, lfilter
SR, LIMIT = 48000, 4.0
HERE = os.path.dirname(os.path.abspath(__file__))
FE = os.path.dirname(HERE)


def cylinders(esc_text):
    return esc_text.count("crank_offset:")


def firing_hz(name, rpm, cyl):
    # cyl is counted in the .esc; the Detroit two-strokes are modelled there as twice their cylinders on a
    # four-stroke cycle (dd671 has 12 entries and fires 6 times a revolution, scene_diesel.PULSES_PER_REV), so
    # cyl/2 per revolution holds for every config
    return rpm / 60 * cyl / 2


def overtone_ratio(x, f0, sr=SR, lo=1500, hi=6000):
    n = min(len(x), 2 * sr)
    seg = x[(len(x) - n) // 2:][:n] * np.hanning(n)
    p = np.abs(np.fft.rfft(seg)) ** 2
    f = np.fft.rfftfreq(n, 1 / sr)
    band = (f >= lo) & (f <= hi)
    d = np.abs(f / f0 - np.round(f / f0))  # distance to the nearest harmonic, in units of f0
    near, far = band & (d <= 0.08), band & (d > 0.25)
    return 10 * np.log10(p[near].mean() / p[far].mean())


def turbulence(x, f0, rng, mix=0.3, sr=SR):
    n = len(x)
    noise = rng.standard_normal(n)
    sos = butter(2, [1200, 9000], btype="band", fs=sr, output="sos")
    noise = sosfilt(sos, np.concatenate([noise, noise]))[n:]  # second pass = filter state wrapped around the loop
    env = np.zeros(n)
    k = max(1, int(round(n * f0 / sr)))  # whole number of firings in the loop
    idx = ((np.arange(k) + 0.5) * n / k).astype(int)  # no pulse onset on the seam itself
    env[idx] = rng.uniform(0.5, 1.5, k)
    a = np.exp(-1 / (0.0012 * sr))
    env = lfilter([1.0], [1.0, -a], np.concatenate([env, env]))[n:]  # decay wraps over the loop seam
    t = noise * env
    rms = lambda v: np.sqrt((v ** 2).mean())
    return x + t * (mix * rms(x) / (rms(t) + 1e-12))


def demo():
    from scipy.io import wavfile
    B = r"C:\Users\Milea\AppData\Local\Temp\claude\f94489672dd71875\4b2fff1c-64bc-4ea5-bcd4-bc20961eb931\scratchpad\flat\buzz"
    f0 = firing_hz("s65", 5850, 8)
    for fn in ("s65_base.wav", "s65_fluct30_noise.wav", "s65_turb30.wav"):
        sr, x = wavfile.read(os.path.join(B, fn))
        print(fn, round(overtone_ratio(x.astype(float), f0, sr), 1))
    sr, x = wavfile.read(os.path.join(B, "s65_fluct30_noise.wav"))
    y = turbulence(x.astype(float), f0, np.random.default_rng(1))
    print("ours from fluct30_noise:", round(overtone_ratio(y, f0, sr), 1))
    assert abs(y[-1] - y[0]) < 4 * np.abs(np.diff(y)).mean()  # no step at the seam beyond normal sample-to-sample


if __name__ == "__main__":
    demo()
