# Engine sound set from engine-sim (D:\MT\engine-sim, es-render.exe): one render per rpm step held on its dyno,
# cut into a forward loop at an engine-cycle boundary (idle_loop.seamless), levelled like synthloop sets, written
# where the cook expects them (D:\MT\SoundCook\wav\MT_<engine>) and recorded in cook/levels.json.
#   python -I es_steps.py <engine> <script.mr relative to engine-sim/assets> [idle throttle]
# Steps are phase-locked: every loop is a whole number of engine cycles and starts at the same point of the cycle,
# so when the game pitches two neighbouring steps to the same rpm their firings coincide and the crossfade cannot
# smear them (the "static" heard when revving fast with arbitrary loop starts).
# engine-sim gives one mono mix, so it is the Exhaust layer; the Engine layer is its 1.2 kHz low-pass 4 dB under
# (what the recorded sets do; loudness.verify checks those on the pair).
import os, sys, json, subprocess, numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly, butter, sosfiltfilt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "recompose")]
ES = r"D:\MT\engine-sim\build"
SR = 48000
# engine-sim's timing jitter is all of the sound above 5 kHz; the script's 0.1 was heard in game as static
JITTER = 0.05  # 0.03 put 1500 rpm over the buzz limit (+5.0): the hiss is what keeps the overtones from standing out
# Engine layer: "lowpass" (the Exhaust's 1.2 kHz low-pass 4 dB under, as recorded sets do) or "silent". The game
# plays the two layers as separate sounds, and a low-passed copy of the same signal comb-filters against it once
# they drift apart -- the cgtv10 mids kept their static through every change to the content
ENGINE_LAYER = "silent"
# every loop is played this much higher than the rpm it was rendered at ("the real engine is much higher-pitched";
# +10% asked 2026-11-06). Circular resample of whole loops: still whole cycles, steps keep their alignment
PITCH = 1.10  # default before 2026-11-07; now per engine (PITCHES)
# in game (2026-11-07): +10% was right for the Carrera GT and the 4A-GE only, everything else read too high
PITCHES = {"cgtv10": 1.10, "4age": 1.10,
           # 2026-11-08: "way too pitched" -- the muscle V8s and the Power Stroke want to sit lower; the RS3 a little
           "voodoo": 0.88, "hemi426": 0.85, "ps60": 0.90, "rs3five": 0.92}
# low shelf (dB under BASS_HZ) for engines heard as thin: "more bass, not dull" (2026-11-08)
BASS_HZ = 200
BASS = {"hemi426": 6.0, "voodoo": 4.0, "ps60": 4.0, "rs3five": 2.0}
# steps EQ'd toward their neighbours' tone (even_tone): only where a step was heard as odd -- the S65 and 4A-GE were
# liked as they were and it moved them up to 11 dB
EVEN_TONE = {"4g63t"}  # "the mid rpm sound of it is very weird" (2026-11-08)
# cycle-to-cycle timing variation (% of a cycle, a random walk pinned to 0 at the wrap). Exact repeating loops made
# neighbouring steps cancel in the game's blend -- it starts each step at its own point, so two near-identical steps
# can sit in antiphase through the whole crossfade: 9-16 dB "cuts" at every blend midpoint (cook/sweep_check.py),
# where vanilla's recordings never drop more than ~4. 1 % brings the sustained blend loss to vanilla's -1..-3 dB.
CYCLE_JITTER = {"petrol": 1.0, "diesel": 1.5}  # diesels: every step is the same render resampled, the most alike
# not a fix for the brief (40 ms) dips of a fast sweep: those follow how much one low harmonic dominates (the bass
# shelf raises it). 1.5-2 % made the Voodoo's worse (median -8.7 -> -10.2 dB, 12 starts); vanilla reaches -9.9.
# in-game level relative to the approved Carrera GT, same structure as it (its curve over the rev range, its volumes,
# the game's default 0.2 idle exhaust ratio): real-life loudness against a V10. 2026-11-08: generated engines were
# ~12 dB under the Carrera GT at full throttle (2 dB rise and 3x against its 11 dB rise and 10.9x) -- "can barely hear"
LOUDNESS_DB = {"hemi426": 3, "voodoo": 1, "sbc350": 2, "s65": 0, "rs3five": 0, "4g63t": -1, "4age": -2, "type1": -1,
               "ps60": 2, "cummins67": 2, "12v": 2, "vp44": 2, "6ct": 1, "ntc400": 1,
               "isx15": 2, "c16": 2, "cat3406e": 2, "series60": 2, "mp8": 2, "macke6": 2, "macke9": 2, "om502": 2,
               "8v92": 3, "dd671": 2, "dd871": 3, "dd1271": 3, "dd1671": 3}
# sets the user approved as they were: no later idle processing, the game's own idle level (2026-11-07: the Carrera GT
# went "awful at idle" once the idle shelf, idle de-buzz and a 0.6 IdleExhaustRatio were laid over its approved build)
APPROVED = {"cgtv10"}
# the idle step: darker (a shelf off above IDLE_SHELF_HZ) and de-buzzed to IDLE_BUZZ -- idle was the buzziest step of
# nearly every engine (steady, unloaded combustion leaves the harmonics bare), heard as buzz right at idle
IDLE_SHELF_HZ, IDLE_SHELF_DB, IDLE_BUZZ = 1500, -6.0, 0.0
# cranking step: the engine turned over with the ignition off (compression chuffs), so the game's start -- it spins
# the engine up from 0 with its own starter -- does not stretch the idle loop down to a fifth of its pitch
CRANK, CRANK_DB = 250, -6.0  # retired 2026-11-07: blended into idle as a low, buzzy pitch; kept for old levels
# exhaust resonances that land on one step (Hz, gain dB, Q), cut before looping
# de-buzz target (buzz dB) for steps heard as buzzing in game although under the limit: 2026-11-09 the Voodoo and the
# RS3 "buzz at ~4000 rpm floored" -- the game's blend around their 3850 step measured +4.5 / +2.7 against ~+2 / -2
# mid-only diesels: steps from this rpm up come from a second render here instead of the mid one, so the top is not
# the mid render played ~1.8x fast (2026-11-09: 6.7 "high rpm wrong", 6.0 "high rpm trash")
UPPER_BASE = {"cummins67": 2750, "ps60": 3200}
DEBUZZ_TO = {("voodoo", 3850): 1.0, ("rs3five", 3850): 0.0, ("ps60", 2700): 1.0}
NOTCHES = {("cgtv10", 7000): [(1750, -18, 12), (1727, -6, 20)],  # +24 dB over the 6500/7500 steps
           ("cgtv10", 1500): [(1750, -6, 8)]}  # firing h14 6 dB over h12/h16: buzz +4.5 against the 4.0 limit


def render(script, out, rpm, throttle, seconds=3.5, warmup=2.0, ignition=1, volume=None):
    r = subprocess.run([os.path.join(ES, "Release", "es-render.exe"), f"../assets/{script}", out, str(rpm), str(throttle),
                        str(seconds), str(warmup), str(ignition)], cwd=ES, capture_output=True, text=True,
                       env=dict(os.environ, ES_JITTER=str(JITTER), **({"ES_VOLUME": str(volume)} if volume else {})))
    assert r.returncode == 0 and os.path.exists(out), (r.stdout, r.stderr)
    return r.stdout.strip()


def folded(x, cycle, bins=240):
    """Firing-envelope over one engine cycle (cycle-synchronous average), for aligning steps to each other."""
    from scipy.signal import hilbert
    y = sosfiltfilt(butter(2, [80, 2500], "bp", fs=SR, output="sos"), x)
    e = np.abs(hilbert(y))
    ph = (np.arange(len(e)) % cycle) / cycle
    h = np.bincount((ph * bins).astype(int), weights=e, minlength=bins)[:bins] / np.maximum(
        np.bincount((ph * bins).astype(int), minlength=bins)[:bins], 1)
    return (h - h.mean()) / (h.std() + 1e-12)


def peak_cut(f0, gain, q):
    """RBJ peaking biquad as sos."""
    A, w = 10 ** (gain / 40), 2 * np.pi * f0 / SR
    al = np.sin(w) / (2 * q)
    b, a = [1 + al * A, -2 * np.cos(w), 1 - al * A], [1 + al / A, -2 * np.cos(w), 1 - al / A]
    return np.array([[*np.divide(b, a[0]), 1, a[1] / a[0], a[2] / a[0]]])


def lag(a, b):
    """Circular shift (fraction of a cycle) that best lines b up with a."""
    c = np.real(np.fft.ifft(np.fft.fft(a) * np.conj(np.fft.fft(b))))
    return int(np.argmax(c)) / len(a)


def phase_loop(x, cycle, start, seconds=2.5):
    """Loop of a whole number of cycles from `start`, the cycle count chosen so that length lands nearest a whole
    sample (no drift between steps over many wraps); the wrap is crossfaded over one cycle."""
    ms = range(max(2, int(seconds * SR / cycle) - 3), int(seconds * SR / cycle) + 4)
    m = min(ms, key=lambda m: (round(abs(m * cycle - round(m * cycle)), 3), abs(m * cycle - seconds * SR)))  # ties: nearest the wanted length
    L, C = int(round(m * cycle)), int(cycle)
    seg = x[start:start + L + C]
    out = seg[:L].copy()
    ramp = np.linspace(0, np.pi / 2, C)  # equal power: a linear fade between two partly unlike cycles dipped
    out[:C] = seg[:C] * np.sin(ramp) + seg[L:L + C] * np.cos(ramp)  # (-1.2 dB once a loop on ps60 3700, heard as static)
    return out, m


def crackle(x):
    """Worst 10 ms 2-8 kHz frame over the loop's median, dB: engine-sim's odd crackle, heard once per wrap."""
    w, hop = 1024, SR // 100
    xx = np.r_[x, x[:w]]
    f = np.fft.rfftfreq(w, 1 / SR)
    band, win = (f > 2000) & (f < 8000), np.hanning(w)
    e = np.array([(np.abs(np.fft.rfft(xx[i:i + w] * win)) ** 2)[band].sum() for i in range(0, len(x), hop)])
    return float(10 * np.log10(e.max() / np.median(e)))


def play(x, k, r, n, off=0.0):
    """The game's blend: every step on one clock, pitched by r/k, looping (linear interpolation)."""
    pos = (off + np.arange(n) * r / k) % len(x)
    i = pos.astype(int)
    f = pos - i
    return x[i] * (1 - f) + x[(i + 1) % len(x)] * f


def align_chain(folder, name, n=SR):
    """Rotate each step's loops (both layers, circularly, so the seam is untouched) to the start whose waveform best
    matches the step below when both are pitched to the rpm between them -- what the crossfade actually sums.
    Searched over one engine cycle of the upper step; chained from idle up. Returns the match per pair."""
    import glob, re
    ks = sorted(int(re.search(r"_(\d+)rpm_", p).group(1)) for p in glob.glob(os.path.join(folder, f"MT_{name}_*rpm_Exhaust.wav")))
    path = lambda k, l: os.path.join(folder, f"MT_{name}_{k}rpm_{l}.wav")
    rd = lambda k, l: wavfile.read(path(k, l))[1].astype(float)
    out = []
    for a, b in zip(ks, ks[1:]):
        r = (a + b) / 2
        pa = play(rd(a, "Exhaust"), a, r, n)
        xb = rd(b, "Exhaust")
        cyc = SR * 120 / b  # one engine cycle of b, in its own samples
        offs = np.arange(0, cyc, max(1.0, cyc / 720))
        best = max(offs, key=lambda o: np.dot(pa, play(xb, b, r, n, o)))
        sh = int(round(best))
        for l in ("Exhaust", "Engine"):
            w = np.roll(rd(b, l), -sh)
            wavfile.write(path(b, l), SR, w.astype(np.int16))
        out.append(float(np.corrcoef(pa, play(np.roll(xb, -sh), b, r, n))[0, 1]))
        print(f"  {a}->{b}: rotated {sh} samples, match {out[-1]:.2f}", flush=True)
    return out


def hf_even(folder, name, fc=5000):
    """engine-sim's air noise leaves each render with its own amount of hiss above `fc` (cgtv10: -34..-21 dB under
    the full band, zig-zagging 6 dB between 500 rpm neighbours), heard as static switching on and off while revving.
    Puts each Exhaust loop's band above fc on a straight line across rpm; zero-phase and circular, so seams and the
    alignment between steps are kept. Returns {rpm: (before, after)} in dB."""
    import glob, re
    hp = butter(4, fc, "hp", fs=SR, output="sos")
    path = lambda k: os.path.join(folder, f"MT_{name}_{k}rpm_Exhaust.wav")
    ks = sorted(int(re.search(r"_(\d+)rpm_", p).group(1)) for p in glob.glob(path("*")))
    xs, hs, db = {}, {}, {}
    for k in ks:
        x = wavfile.read(path(k))[1].astype(float)
        h = sosfiltfilt(hp, np.r_[x, x, x])[len(x):2 * len(x)]
        xs[k], hs[k], db[k] = x, h, 10 * np.log10((h ** 2).mean() / (x ** 2).mean())
    fit = np.polyval(np.polyfit(ks, [db[k] for k in ks], 1), ks)
    out = {}
    for k, want in zip(ks, fit):
        y = xs[k] + hs[k] * (10 ** ((want - db[k]) / 20) - 1)
        wavfile.write(path(k), SR, np.clip(y, -32768, 32767).astype(np.int16))
        out[k] = (round(db[k], 1), round(float(want), 1))
    return out


def pitch_up(folder, name, factor):
    """Resample every loop of the set (both layers) to play `factor` higher, circularly (FFT), so the wrap stays
    seamless."""
    from scipy.signal import resample
    for p in os.listdir(folder):
        if p.startswith(f"MT_{name}_") and p.endswith(".wav"):
            x = wavfile.read(os.path.join(folder, p))[1].astype(float)
            y = resample(x, int(round(len(x) / factor))) if x.any() else x[:int(round(len(x) / factor))]
            wavfile.write(os.path.join(folder, p), SR, np.clip(y, -32768, 32767).astype(np.int16))


def comb_cut(x, f0, gain_db, wide=False):
    """Turn down the firing harmonics' own lines in 1.5-6 kHz (tapered 1.2-1.5 and 6-7 kHz), nothing else. A loop is a
    whole number of engine cycles, so every harmonic sits exactly on its FFT lines: a pure level change on lines
    already there -- no noise added (the old de-buzz added noise: the hiss heard in game) and the loop stays periodic."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    d = np.abs(f / f0 - np.round(f / f0))
    # wide: everything within 8 % of a harmonic, the band the buzz check counts -- for an engine whose energy sits in
    # sidebands around each harmonic rather than on it (the 16V71: 0.3 % of the band on the lines themselves)
    near = d <= 0.08 if wide else d * f0 <= max(SR / len(x) * 1.5, 2.0)
    w = np.clip((f - 1200) / 300, 0, 1) * np.clip((7000 - f) / 1000, 0, 1)
    return np.fft.irfft(X * np.where(near, 10 ** (gain_db * w / 20), 1.0), len(x))


def debuzz(folder, name, cyl, crank=None, pitch=1.0, idle=None):
    """The "bee" buzz/beeping: firing harmonics standing too clean in 1.5-6 kHz (cook/buzz.py, verify's limit).
    Cut those lines (comb_cut) in 2 dB steps until the step is 0.5 dB under the limit (at most -40 dB), at the same
    loudness, on both layers. Returns {rpm: (cut dB, buzz)} for the steps it touched."""
    import glob, re
    import synthloop as sl
    from buzz import overtone_ratio, LIMIT
    out = {}
    for p in glob.glob(os.path.join(folder, f"MT_{name}_*rpm_Exhaust.wav")):
        k = int(re.search(r"_(\d+)rpm_", p).group(1))
        x = wavfile.read(p)[1].astype(float) / 32768
        f0 = k / 60 * cyl / 2 * pitch  # measured on the pitched loop, as verify measures the shipped wave
        to = DEBUZZ_TO.get((name, k), LIMIT - 0.5)
        if not x.any() or overtone_ratio(x, f0) <= to:
            continue
        g, y, wide = 0, x, False
        while overtone_ratio(y, f0) > to and g > -40:
            g -= 2
            y = comb_cut(x, f0, g)
        if overtone_ratio(y, f0) > to:  # the lines alone were not enough: the sidebands around them
            g, wide = 0, True
            while overtone_ratio(y, f0) > to and g > -40:
                g -= 2
                y = comb_cut(x, f0, g, wide=True)
        want, gg = sl.lufs(x), 1.0
        for _ in range(6):  # back to the step's loudness through the levelling's limiter
            z = sl.limit([y * gg])[0]
            gg *= 10 ** ((want - sl.lufs(z)) / 20)
        wavfile.write(p, SR, (z * 32767).astype(np.int16))
        out[k] = (f"{g}{' wide' if wide else ''}", round(float(overtone_ratio(z, f0)), 1))
    return out


def darken_idle(folder, name, idle):
    """High shelf off the idle step (both layers), zero-phase on the tripled loop so the wrap stays seamless, at the
    same loudness. Returns the treble change in dB."""
    import synthloop as sl
    from scipy.signal import lfilter
    A, w = 10 ** (IDLE_SHELF_DB / 40), 2 * np.pi * IDLE_SHELF_HZ / SR
    al = np.sin(w) / 2 * np.sqrt(2)
    b = [A * ((A + 1) + (A - 1) * np.cos(w) + 2 * np.sqrt(A) * al), -2 * A * ((A - 1) + (A + 1) * np.cos(w)),
         A * ((A + 1) + (A - 1) * np.cos(w) - 2 * np.sqrt(A) * al)]
    a = [(A + 1) - (A - 1) * np.cos(w) + 2 * np.sqrt(A) * al, 2 * ((A - 1) - (A + 1) * np.cos(w)),
         (A + 1) - (A - 1) * np.cos(w) - 2 * np.sqrt(A) * al]  # RBJ high shelf
    sos = np.array([[*np.divide(b, a[0]), 1.0, a[1] / a[0], a[2] / a[0]]])
    p = os.path.join(folder, f"MT_{name}_{idle}rpm_Exhaust.wav")
    x = wavfile.read(p)[1].astype(float) / 32768
    if not x.any():
        return None
    y = sosfiltfilt(sos, np.r_[x, x, x])[len(x):2 * len(x)]
    want, g = sl.lufs(x), 1.0
    for _ in range(6):
        z = sl.limit([y * g])[0]
        g *= 10 ** ((want - sl.lufs(z)) / 20)
    wavfile.write(p, SR, (z * 32767).astype(np.int16))
    hi = lambda v: 10 * np.log10(np.mean(sosfiltfilt(butter(4, 3000, "hp", fs=SR, output="sos"), v) ** 2) + 1e-20)
    return round(float(hi(z) - hi(x)), 1)


def match_idle(folder, name, idle):
    """EQ the idle step (both layers) to the tone of the step above it, third-octave by third-octave (+-18 dB, over
    150 Hz-16 kHz), applied around the loop so the wrap stays seamless, at the same loudness. engine-sim's unloaded
    idle came out ~18 dB brighter at 2-4 kHz than the loaded steps (rs3five), so in game idle sounded louder than
    flooring it and the blend from idle into the first loaded step was heard as something weird in the background.
    Returns the gain applied at 1 / 3 / 6 kHz."""
    import glob, re
    import synthloop as sl
    from scipy.signal import welch
    ks = sorted(int(re.search(r"_(\d+)rpm_", p).group(1)) for p in glob.glob(os.path.join(folder, f"MT_{name}_*rpm_Exhaust.wav")))
    if idle not in ks or ks.index(idle) + 1 >= len(ks):
        return None
    nxt = ks[ks.index(idle) + 1]
    rd = lambda k: wavfile.read(os.path.join(folder, f"MT_{name}_{k}rpm_Exhaust.wav"))[1].astype(float) / 32768
    x, ref = rd(idle), rd(nxt)
    if not x.any():
        return None
    cents = 1000 * 2 ** (np.arange(-9, 14) / 3)  # third octaves 125 Hz..16 kHz
    def bands(v):
        f, p = welch(v, SR, nperseg=8192)
        return np.array([p[(f >= c / 2 ** (1 / 6)) & (f < c * 2 ** (1 / 6))].sum() + 1e-20 for c in cents])
    gain_db = np.clip(10 * np.log10(bands(ref) / bands(x)), -18, 3)  # cut freely, lift little: a lift above 6 kHz is hiss
    gain_db -= np.interp(np.log2(800), np.log2(cents), gain_db)  # tone only: loudness is restored below
    gain_db = np.minimum(gain_db, 3.0)  # after centring too: a lift above 6 kHz is hiss
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = np.interp(np.log2(np.maximum(f, 20)), np.log2(cents), gain_db)
    g[f < cents[0] / 2 ** (1 / 6)] = gain_db[0] * 0 + 0.0  # below 110 Hz untouched
    y = np.fft.irfft(X * 10 ** (g / 20), len(x))
    want, gg = sl.lufs(x), 1.0
    for _ in range(6):
        z = sl.limit([y * gg])[0]
        gg *= 10 ** ((want - sl.lufs(z)) / 20)
    wavfile.write(os.path.join(folder, f"MT_{name}_{idle}rpm_Exhaust.wav"), SR, (z * 32767).astype(np.int16))
    return {hz: round(float(np.interp(np.log2(hz), np.log2(cents), gain_db)), 1) for hz in (1000, 3000, 6000)}


def _relevel(x, y):
    """y through the levelling's limiter at x's loudness."""
    import synthloop as sl
    want, gg = sl.lufs(x), 1.0
    for _ in range(6):
        z = sl.limit([y * gg])[0]
        gg *= 10 ** ((want - sl.lufs(z)) / 20)
    return z


def _steps(folder, name):
    import glob, re
    return sorted(int(re.search(r"_(\d+)rpm_", p).group(1)) for p in glob.glob(os.path.join(folder, f"MT_{name}_*rpm_Exhaust.wav")))


def bass_shelf(folder, name, db, hz=BASS_HZ):
    """Low shelf (smooth, +db below hz, 0 above 4*hz) on every step, circular so the wrap stays seamless, at the same
    loudness -- the tone moves down, not the level up."""
    for k in _steps(folder, name):
        p = os.path.join(folder, f"MT_{name}_{k}rpm_Exhaust.wav")
        x = wavfile.read(p)[1].astype(float) / 32768
        if not x.any():
            continue
        f = np.fft.rfftfreq(len(x), 1 / SR)
        g = db * np.clip(np.log2(4 * hz / np.maximum(f, 1)) / 2, 0, 1)
        g[f < 30] = 0.0  # no sub-30 Hz rumble lifted
        y = np.fft.irfft(np.fft.rfft(x) * 10 ** (g / 20), len(x))
        wavfile.write(p, SR, (_relevel(x, y) * 32767).astype(np.int16))


def even_tone(folder, name, idle, max_db=6.0):
    """EQ each loaded step (not idle, not the top) toward the mean third-octave tone of itself and its neighbours,
    +-max_db, centred, at the same loudness: engine-sim's steps jump in tone where the rpm crosses a pipe resonance
    (4g63t: 125 Hz -3, -8.5, -5, -3, -18.5 dB across the mids), heard as one step sounding "weird" in the blend."""
    from scipy.signal import welch
    ks = [k for k in _steps(folder, name) if k != idle]
    if len(ks) < 3:
        return {}
    cents = 1000 * 2 ** (np.arange(-9, 14) / 3)
    rd = lambda k: wavfile.read(os.path.join(folder, f"MT_{name}_{k}rpm_Exhaust.wav"))[1].astype(float) / 32768
    def bands(v):
        f, p = welch(v, SR, nperseg=8192)
        return 10 * np.log10(np.array([p[(f >= c / 2 ** (1 / 6)) & (f < c * 2 ** (1 / 6))].sum() + 1e-20 for c in cents]))
    xs = {k: rd(k) for k in ks}
    B = {k: bands(xs[k]) - bands(xs[k]).max() for k in ks}
    out = {}
    for i, k in enumerate(ks[1:-1], 1):
        gain = np.clip((B[ks[i - 1]] + B[k] + B[ks[i + 1]]) / 3 - B[k], -max_db, max_db)
        gain = np.clip(gain - np.interp(np.log2(800), np.log2(cents), gain), -max_db, max_db)  # centred, still capped
        x = xs[k]
        f = np.fft.rfftfreq(len(x), 1 / SR)
        g = np.interp(np.log2(np.maximum(f, 20)), np.log2(cents), gain)
        y = np.fft.irfft(np.fft.rfft(x) * 10 ** (g / 20), len(x))
        wavfile.write(os.path.join(folder, f"MT_{name}_{k}rpm_Exhaust.wav"), SR, (_relevel(x, y) * 32767).astype(np.int16))
        out[k] = round(float(np.abs(gain).max()), 1)
    return out


def cycle_jitter(folder, name, pct, pitch=1.0, seed=0):
    """Per-cycle timing variation on every step: a random walk of pct % of a cycle per engine cycle, pinned to 0 at
    both ends of the loop (a Brownian bridge, periodic spline), read circularly from a 4x band-limited copy -- the wrap
    stays seamless and the loop stays its length. Each step gets its own walk, so neighbours do not stay in antiphase."""
    from scipy.signal import resample
    from scipy.interpolate import CubicSpline
    for j, k in enumerate(_steps(folder, name)):
        p = os.path.join(folder, f"MT_{name}_{k}rpm_Exhaust.wav")
        x = wavfile.read(p)[1].astype(float) / 32768
        if not x.any():
            continue
        L, cyc = len(x), SR * 120 / (k * pitch)
        m = max(2, int(round(L / cyc)))
        rng = np.random.default_rng(seed * 1000 + j)
        walk = np.r_[0, np.cumsum(rng.normal(0, pct / 100 * cyc, m))]
        walk -= np.linspace(0, walk[-1], m + 1)
        d = CubicSpline(np.linspace(0, L, m + 1), walk, bc_type="periodic")(np.arange(L))
        up = resample(x, 4 * L)
        pos = ((np.arange(L) + d) * 4) % (4 * L)
        i = pos.astype(int)
        fr = pos - i
        y = up[i] * (1 - fr) + up[(i + 1) % (4 * L)] * fr
        wavfile.write(p, SR, (_relevel(x, y) * 32767).astype(np.int16))


def engine_spec(name):
    """idle, top, firing cylinders (a two-stroke counts double, as the model does), kind, step spacing: from
    es_engines.SPECS, or ICONIC for the Carrera GT. Cars step 1000 rpm like vanilla's car sets, diesels 500 like
    vanilla's MidDuty truck set (they only rev to 2000-3800)."""
    import es_engines
    from iconic import ICONIC
    if name in es_engines.SPECS:
        s = es_engines.SPECS[name]
        return dict(idle=s["idle"], top=s["top"] + 1, cyl=s["cyl"] * (2 if s.get("strokes", 4) == 2 else 1), kind=s["kind"],
                    spacing=1000 if s["kind"] == "car" else 500, idle_throttle=0.0)  # idle air is calibrated (es_engines)
    d = ICONIC[name]
    return dict(idle=d["idle"], top=d["top"], cyl=len(d["on"]), kind="car", spacing=1000)


def main(name, script, idle_throttle=0.02, mid_only=None):
    import synthloop as sl
    from concurrent.futures import ThreadPoolExecutor
    d = engine_spec(name)
    spacing = d["spacing"]
    if mid_only is None:  # diesels: engine-sim's mid revs were the only part that sounded right in game (2026-11-07)
        import es_engines
        mid_only = bool(es_engines.SPECS.get(name, {}).get("diesel"))
    steps = list(range(d["idle"], d["top"], spacing))
    if d["top"] - steps[-1] > 0.4 * spacing:  # a step near the limit, so the top is not one step stretched far up
        steps.append((d["top"] - 100) // 50 * 50)
    lv = json.load(open(sl.LEVELS))
    old = lv["engines"].get(name, {})
    gt = lv["engines"]["cgtv10"]["curve"]  # the approved level curve every generated set follows (by rev fraction)
    gt_curve = lambda k: float(np.interp((k - d["idle"]) / (d["top"] - d["idle"]),
                                         [(r - gt[0][0]) / (gt[0][-1] - gt[0][0]) for r in gt[0]], gt[1])) + LOUDNESS_DB.get(name, 0)
    # loudness: the Carrera GT keeps its curve; every other engine keeps the one it was matched to vanilla with
    # (per class and rpm band), read off its old steps before they are replaced
    if name == "cgtv10" or not old.get("steps") or old.get("source") == "enginesim":
        curve = lambda k: sl.target("car", k, d["idle"], d["top"])
        if name != "cgtv10" and old.get("curve"):
            curve = lambda k, c=old["curve"]: float(np.interp(k, c[0], c[1]))
    else:
        c = ([r[0] for r in old["steps"]], [r[1] for r in old["steps"]])
        curve = lambda k: float(np.interp(k, c[0], c[1]))
    knots = [[k for k in steps if k != CRANK], [round(curve(k), 2) for k in steps if k != CRANK]]
    work = os.path.join(HERE, "es2", name)
    os.makedirs(work, exist_ok=True)
    folder = os.path.join(sl.OUT, f"MT_{name}")
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))

    def raw_of(k):
        raw = os.path.join(work, f"step_{k}.wav")
        args = dict(seconds=4.0, ignition=0 if k == CRANK else 1)
        thr = 0.0 if k == CRANK else d.get("idle_throttle", idle_throttle) if k == d["idle"] else 1.0
        if not os.path.exists(raw):
            print(render(script, raw, k, thr, **args), flush=True)
        # a big diesel idling or cranking renders ~-50..-70 LUFS, near 16-bit's floor at the normal synth volume:
        # render it again hot enough to sit near -30, so levelling it up does not bring the floor up with it
        x = wavfile.read(raw)[1].astype(float) / 32768
        lv = sl.lufs(x[int(0.3 * 44100):])
        if not np.isfinite(lv) or lv < -40:
            vol = min(64.0, 0.25 * 10 ** ((-30 - lv) / 20)) if np.isfinite(lv) else 16.0
            print(render(script, raw, k, thr, volume=round(vol, 3), **args), f"(re-rendered hot: {lv:.0f} LUFS at 0.25)", flush=True)
        return raw
    with ThreadPoolExecutor(8) as ex:  # each es-render is one thread: render the steps side by side
        raws = dict(zip(steps, ex.map(raw_of, steps)))
    rows, prev = [], None
    base = min((k for k in steps if k != d["idle"]), key=lambda k: abs(k - (d["idle"] + d["top"]) / 2)) if mid_only else None
    for k in steps:
        if mid_only:  # every step is the mid render, resampled to its rpm: one sound, pitch and volume only
            b = UPPER_BASE[name] if name in UPPER_BASE and k >= (base + UPPER_BASE[name]) / 2 else base
            long_raw = os.path.join(work, f"step_{b}_long.wav")  # long enough to be squeezed up to the limit
            if not os.path.exists(long_raw):
                print(render(script, long_raw, b, 1.0, seconds=4.0 * d["top"] / b + 2.0), flush=True)
            x = resample_poly(wavfile.read(long_raw)[1].astype(float) / 32768, 160, 147)
            from scipy.signal import resample
            x = resample(x, int(round(len(x) * b / k)))
        else:
            x = wavfile.read(raws[k])[1].astype(float) / 32768
            x = resample_poly(x, 160, 147)  # engine-sim runs at 44.1 kHz
        for f0, gain, q in NOTCHES.get((name, k), []):
            x = sosfiltfilt(peak_cut(f0, gain / 2, q), x)  # filtfilt runs it twice: half the cut each way
        cycle = SR * 120 / k
        x = x[int(0.3 * SR):]
        f = folded(x[:int(3 * SR)], cycle)
        # cycle phase of this render relative to the previous step (neighbours look alike; the chain carries phase 0
        # from the first step all the way up)
        rel = 0.0 if prev is None else (prev[1] + lag(prev[0], f)) % 1.0
        prev = (f, rel)
        # this render leads the reference by `rel` cycles, so its phase 0 sits at -rel (checked on a pattern unique
        # within the cycle: -rel matches 1.000, +rel 0.873); at least one cycle in, past the render's start
        start = int(round((-rel % 1.0) * cycle)) + int(cycle)
        loop, m = phase_loop(x, cycle, start)
        if mid_only:  # the cleanest stretch of the render: whole cycles later keeps the phase chain
            n = int((len(x) - start - len(loop) - 2 * cycle) // cycle)
            if n > 0:
                start = min((int(round(start + j * cycle)) for j in range(0, n, max(1, n // 40))),
                            key=lambda s0: crackle(phase_loop(x, cycle, s0)[0]))
                loop, m = phase_loop(x, cycle, start)
        if k == CRANK and not np.isfinite(sl.lufs(loop)) or sl.lufs(loop) < -60:
            print(f"  {k} rpm: silent ({sl.lufs(loop):.0f} LUFS) -- step dropped, the idle step covers it", flush=True)
            prev = None  # the next step starts the phase chain afresh
            continue
        L, sc = len(loop), float(np.corrcoef(loop[:int(cycle)], x[start + len(loop):start + len(loop) + int(cycle)])[0, 1])
        eng = sosfiltfilt(butter(4, 1200, fs=SR, output="sos"), np.r_[loop, loop, loop])[len(loop):2 * len(loop)]
        eng *= 10 ** ((sl.lufs(loop) - 4 - sl.lufs(eng)) / 20) if ENGINE_LAYER == "lowpass" else 0.0
        want = curve(k) if name == "cgtv10" else gt_curve(k)
        g = 1.0
        for _ in range(6):
            ex2, en2 = sl.limit([loop * g, eng * g])
            g *= 10 ** ((want - sl.lufs(ex2 + en2)) / 20)
        for layer, w in (("Exhaust", ex2), ("Engine", en2)):
            wavfile.write(os.path.join(folder, f"MT_{name}_{k}rpm_{layer}.wav"), SR, (w * 32767).astype(np.int16))
        pair = sl.lufs(ex2 + en2)
        rows.append([k, round(pair, 2), round(sl.lufs(ex2), 2), round(sl.lufs(en2), 2) if en2.any() else None, 0.0, len(loop) / SR])
        print(f"  {k} rpm: {m} cycles = {L / SR:.3f} s, phase {rel:.3f}, pair {pair:.2f} LUFS (target {want:.2f})", flush=True)
    align_chain(folder, name)
    if not mid_only:  # one source has one hiss level and one tone already
        print("  hiss >5 kHz (before, after):", hf_even(folder, name), flush=True)
    pitch = PITCHES.get(name, 1.0)
    if pitch != 1.0:
        pitch_up(folder, name, pitch)
    if not mid_only and name not in APPROVED:  # (replaces the fixed shelf: match the idle's tone to the step above)
        print("  idle matched to the next step (dB at 1/3/6 kHz):", match_idle(folder, name, d["idle"]), flush=True)
    # de-buzz by cutting the harmonic lines themselves (comb_cut), never by adding noise: the noise was the hiss heard
    # in game (ps60's top step went from -60 to -22 dB above 4 kHz). The approved Carrera GT is left as it was.
    if name in EVEN_TONE:
        print("  tone evened across steps (max dB):", even_tone(folder, name, d["idle"]), flush=True)
    if BASS.get(name):
        bass_shelf(folder, name, BASS[name])
        print(f"  bass shelf +{BASS[name]} dB under {BASS_HZ} Hz", flush=True)
    if name not in APPROVED:
        import es_engines
        cj = CYCLE_JITTER["diesel" if es_engines.SPECS.get(name, {}).get("diesel") else "petrol"]
        cycle_jitter(folder, name, cj, pitch, seed=sum(map(ord, name)))
        print(f"  cycle jitter {cj} % per cycle", flush=True)
        # last, so the limit holds on what ships (jitter + relevel put the s65 back over it: +4.3)
        print("  de-buzzed (cut dB, buzz):", debuzz(folder, name, d["cyl"], None, pitch), flush=True)
    if mid_only:
        print(f"  mid-only: every step from the {base} rpm render", flush=True)
    lv = json.load(open(sl.LEVELS))
    lv["engines"][name] = {"class": old.get("class", "petrol"), "kind": old.get("kind", d["kind"]), "cylinders": d["cyl"],
                           "steps": rows, "source": "enginesim", "curve": knots,
                           "engine_layer": ENGINE_LAYER, "method": "forward-loop", "script": script, "volumes": sl.VOLUMES,  # Master x layer (10.9x = +21 dB, SoundProbe 2026-11-07): every set at the Carrera GT's structure (LOUDNESS_DB)
                           # the game does not keep steps in phase: a crossfade over the whole spacing was heard as
                           # static on fast revs, so blend only near each midpoint (vanilla blends half its spacing)
                           "crossfade": spacing // 2, "jitter": JITTER, "pitch": pitch,
                           "idle_exhaust_ratio": None, "loudness_db": LOUDNESS_DB.get(name, 0),
                           **({"starter": old["starter"]} if "starter" in old else {})}  # the approved starter stays
    json.dump(lv, open(sl.LEVELS, "w"), indent=1)


if __name__ == "__main__":
    if sys.argv[1] == "demo":
        # a pulse train at two rates with a known cycle offset: alignment must recover it, loops are whole cycles
        t = np.arange(4 * SR) / SR
        k1, k2 = 3000, 3500
        a = np.sin(2 * np.pi * (k1 / 120) * t) ** 40 * np.sin(2 * np.pi * 400 * t)
        b = np.sin(2 * np.pi * (k2 / 120) * (t + 0.3 * 120 / k2)) ** 40 * np.sin(2 * np.pi * 400 * t)
        fa, fb = folded(a, SR * 120 / k1), folded(b, SR * 120 / k2)
        got = lag(fa, fb)
        assert min(abs(got - 0.3), abs(got - 0.3 + 1), abs(got - 0.3 - 1)) < 0.02 or min(abs((got - 0.3) * 2 % 1), 1 - (got - 0.3) * 2 % 1) < 0.04, got
        loop, m = phase_loop(a, SR * 120 / k1, 0)
        assert abs(len(loop) - m * SR * 120 / k1) < 1
        print("demo ok", round(got, 3), m)
    else:
        main(sys.argv[1], sys.argv[2], *(float(v) for v in sys.argv[3:4]))
