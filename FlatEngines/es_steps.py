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
CROSSFADE = 500  # vanilla layout: 1000 rpm steps, 500 crossfade (15 steps at 500/150 gave static from low to high rpm; vanilla does not)
# engine-sim's timing jitter is all of the sound above 5 kHz; the script's 0.1 was heard in game as static
JITTER = 0.05  # 0.03 put 1500 rpm over the buzz limit (+5.0): the hiss is what keeps the overtones from standing out
# Engine layer: "lowpass" (the Exhaust's 1.2 kHz low-pass 4 dB under, as recorded sets do) or "silent". The game
# plays the two layers as separate sounds, and a low-passed copy of the same signal comb-filters against it once
# they drift apart -- the cgtv10 mids kept their static through every change to the content
ENGINE_LAYER = "silent"
# every loop is played this much higher than the rpm it was rendered at ("the real engine is much higher-pitched";
# +10% asked 2026-11-06). Circular resample of whole loops: still whole cycles, steps keep their alignment
PITCH = 1.10
# cranking step: the engine turned over with the ignition off (compression chuffs), so the game's start -- it spins
# the engine up from 0 with its own starter -- does not stretch the idle loop down to a fifth of its pitch
CRANK, CRANK_DB = 250, -6.0
# exhaust resonances that land on one step (Hz, gain dB, Q), cut before looping
NOTCHES = {("cgtv10", 7000): [(1750, -18, 12), (1727, -6, 20)],  # +24 dB over the 6500/7500 steps
           ("cgtv10", 1500): [(1750, -6, 8)]}  # firing h14 6 dB over h12/h16: buzz +4.5 against the 4.0 limit


def render(script, out, rpm, throttle, seconds=3.5, warmup=2.0, ignition=1):
    r = subprocess.run([os.path.join(ES, "Release", "es-render.exe"), f"../assets/{script}", out, str(rpm), str(throttle),
                        str(seconds), str(warmup), str(ignition)], cwd=ES, capture_output=True, text=True,
                       env=dict(os.environ, ES_JITTER=str(JITTER)))
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
    ramp = np.linspace(0, 1, C)
    out[:C] = seg[:C] * ramp + seg[L:L + C] * (1 - ramp)
    return out, m


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


def main(name, script, idle_throttle=0.02, spacing=1000):
    import synthloop as sl
    import idle_loop
    from iconic import ICONIC
    d = ICONIC[name]
    steps = [CRANK] + list(range(d["idle"], d["top"], spacing))
    work = os.path.join(HERE, "es2", name)
    os.makedirs(work, exist_ok=True)
    folder = os.path.join(sl.OUT, f"MT_{name}")
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))
    rows, prev = [], None
    for k in steps:
        raw = os.path.join(work, f"step_{k}.wav")
        if not os.path.exists(raw):
            print(render(script, raw, k, 0.0 if k == CRANK else idle_throttle if k == d["idle"] else 1.0, seconds=4.0,
                         ignition=0 if k == CRANK else 1), flush=True)
        x = wavfile.read(raw)[1].astype(float) / 32768
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
        L, sc = len(loop), float(np.corrcoef(loop[:int(cycle)], x[start + len(loop):start + len(loop) + int(cycle)])[0, 1])
        eng = sosfiltfilt(butter(4, 1200, fs=SR, output="sos"), np.r_[loop, loop, loop])[len(loop):2 * len(loop)]
        eng *= 10 ** ((sl.lufs(loop) - 4 - sl.lufs(eng)) / 20) if ENGINE_LAYER == "lowpass" else 0.0
        want = sl.target("car", d["idle"], d["idle"], d["top"]) + CRANK_DB if k == CRANK else sl.target("car", k, d["idle"], d["top"])
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
    print("  hiss >5 kHz (before, after):", hf_even(folder, name), flush=True)
    pitch_up(folder, name, PITCH)
    lv = json.load(open(sl.LEVELS))
    lv["engines"][name] = {"class": "petrol", "kind": "car", "cylinders": len(d["on"]), "steps": rows, "source": "enginesim",
                           "engine_layer": ENGINE_LAYER, "method": "forward-loop", "script": script, "volumes": sl.VOLUMES,
                           # the game does not keep steps in phase: a crossfade over the whole spacing was heard as
                           # static on fast revs, so blend only near each midpoint (vanilla blends half its spacing)
                           "crossfade": CROSSFADE, "jitter": JITTER, "pitch": PITCH}
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
