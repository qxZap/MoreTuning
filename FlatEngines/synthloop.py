# In-game loops from the same mixer as the Telegram fly-bys (scene_iconic.sound), held at one rpm per step:
# the revs wander a little, every firing differs in strength, the load layers blend as in the scenes. Then a short
# outdoor space (ground reflection, a little diffuse tail, air), and the loop is the user's recipe: one steady
# stretch forward then reversed, so both ends meet and the loop has no seam.
#   python -I synthloop.py build cgtv10     wavs -> D:\MT\SoundCook\wav\MT_cgtv10\, levels.json entry, preview mp3
#   python -I synthloop.py demo             self-check of the ping-pong seam and the level setting
import os, sys, json, subprocess, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, sosfiltfilt, fftconvolve
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "cook"))
SR = 48000
OUT = r"D:\MT\SoundCook\wav"
LEVELS = os.path.join(HERE, "cook", "levels.json")
PREVIEW = os.path.join(HERE, "synthloop_preview")
PEAK = 10 ** (-1 / 20)
# Loudness. The user's Lexus V10 (lexusV10/SC_V8Engine) plays its files at cue volume 0.5 times an rpm curve up to
# ~4x at the top, so in game it rises ~13 dB from idle (about -15 LUFS) to full revs (about -2). A data asset has no
# cue: the rise goes into the files (pair LUFS, linear in dB over the rev range) and MASTER (MTEngineSoundDataAsset
# MasterVolume, +8 dB) lifts the whole set, which keeps the files clear of the limiter.
# Take 2 (files -23..-11, MasterVolume 2.5, +8 dB) was too quiet; take 3 (x10, +20 dB) was "earrape": the game
# overdrove files already near full scale. Take 4 meets in the middle (+14 dB over take 2's files): +4 dB of density
# from a clean look-ahead limiter in the files, +10 dB from MasterVolume alone; layer multipliers unset (1).
PAIR = {"car": (-19.0, -7.0)}
# take 9: in game take 8 (MasterVolume 3.2 alone) was "too low" although its files match vanilla's; take 3 (the only
# one with layer multipliers) was the loud one -> MasterVolume looks ignored. 1.8 on both layers: +5 dB if it is,
# +15 dB if both apply; either sits between take 8 (too low) and take 3 (+20, earrape).
VOLUMES = {"MasterVolume": 3.2, "EngineVolumeMultiplier": 3.4, "ExhaustVolumeMultiplier": 3.4}  # +2.5 dB after the first engine-sim test ("louder engine")
ENGINE_DB = -5.0  # intake/mechanical layer under the exhaust note
SEG = 2.5
# Take 5: renders from the patched generator (es_src, enginesound_mt.linux: per-combustion variation + exhaust flow
# noise), whose firings already vary like the real car's, so none of the after-the-fact noise substitution
# (untone / firing_jitter / rasp / midband / debuzz) that made takes 2-4 sound fake.
RENDER = "cgt3"  # take 8: the generator fitted to the real idle (fit_idle.py -> fit/<engine>/best.json)
CLEAN = True
TONES = {}
REFS = {}         # seconds of steady engine per loop; the loop is twice that


def lufs(x):
    import loudness
    return loudness.lufs(x, SR)


def softlimit(v, knee=10 ** (-6 / 20)):
    a = np.abs(v)
    out = v.copy()
    o = a > knee
    out[o] = np.sign(v[o]) * (knee + (PEAK - knee) * np.tanh((a[o] - knee) / (PEAK - knee)))
    return out


def limit(layers, ceiling=PEAK, ms=3.0):
    """Look-ahead peak limiter on a loop (wraps at the seam), one gain for all layers so their sum stays in step.
    Max-filter then box-smooth over the same window: the smoothed gain never exceeds ceiling/|x| (no overs, no
    waveshaping, so no added harmonics)."""
    from scipy.ndimage import maximum_filter1d, uniform_filter1d
    w = int(SR * ms / 1000) | 1
    a = np.max([np.abs(x) for x in layers + [sum(layers)]], axis=0)
    g = np.minimum(1.0, ceiling / np.maximum(maximum_filter1d(a, w, mode="wrap"), 1e-9))
    g = uniform_filter1d(g, w, mode="wrap")
    return [x * g for x in layers]


def outdoors(y, rng):
    # a little diffuse space and air, no ground bounce: a fixed short echo is a comb, which is what sounded "in a tube"
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    ir = sosfilt(butter(2, 4000, fs=SR, output='sos'), rng.standard_normal(n)) * np.exp(-t / 0.08)
    ir[:int(0.004 * SR)] = 0
    y = y + fftconvolve(y, ir / np.sqrt((ir ** 2).sum()) * 0.12)[:len(y)]
    return sosfilt(butter(1, 12000, fs=SR, output='sos'), y)  # air


def debuzz(y, rng, keep=0.15, split=1000):
    """The bee is the synth's top end being perfectly periodic: firing overtones stand clear of the noise between
    them. A real engine's combustion differs every cycle, so up there it is noise shaped by the firing pulses.
    Above `split`, keep `keep` of the original and replace the rest with noise carrying the band's own envelope
    (same energy), so the rhythm and the brightness stay and the comb goes."""
    low = sosfiltfilt(butter(4, split, fs=SR, output='sos'), y)
    high = y - low
    from scipy.signal import hilbert
    env = sosfiltfilt(butter(2, 400, fs=SR, output='sos'), np.abs(hilbert(high)))
    nz = sosfiltfilt(butter(4, split, 'highpass', fs=SR, output='sos'), rng.standard_normal(len(y))) * np.maximum(env, 0)
    nz *= np.sqrt((high ** 2).mean() / ((nz ** 2).mean() + 1e-20))
    return low + keep * high + np.sqrt(1 - keep ** 2) * nz


def fixed_tones(folder, name):
    """Per-frequency excess (dB) present at EVERY rpm of a render set: a peak whose pitch does not move with the
    engine is a resonance of the model (in the V10, 996 Hz stands 8 dB proud at all revs), not part of an engine.
    That constant tone under the note is the buzz the user hears once the engine is loud enough."""
    import glob
    from scipy.signal import welch
    ex = []
    for p in sorted(glob.glob(os.path.join(folder, f"{name}_on_*.wav"))):
        sr, x = wavfile.read(p)
        x = x.astype(float)
        x = x.mean(1) if x.ndim > 1 else x
        f, P = welch(x, sr, nperseg=8192)
        P = 10 * np.log10(P + 1e-20)
        base = np.array([np.median(P[max(0, i - int(i * 0.12)):i + int(i * 0.12) + 2]) for i in range(len(P))])
        ex.append(P - base)
    return f, np.clip(np.array(ex).min(axis=0), 0, None)


def untone(y, f, m, over=1.5):
    """Cut every fixed resonance back to its surroundings: linear-phase FIR with gain -m dB where m > over."""
    from scipy.signal import firwin2
    g = 10 ** (-np.where((m > over) & (f > 60), m, 0) / 20)
    h = firwin2(4097, f / (SR / 2), g)
    return fftconvolve(y, h, mode="same")


def firing_jitter(y, rpm, cyl, rng, sd=0.28):
    """Every combustion differs: a random strength per firing (real Carrera GT clips vary 0.18-0.78 cycle to cycle,
    the synth 0.11-0.18). Random AM at the firing rate also spreads each harmonic into the noise between them."""
    ev = np.cumsum(rpm / 60 * cyl / 2) / SR
    g = np.clip(rng.normal(1, sd, int(ev[-1]) + 2), 0.35, 1.9)
    i = ev.astype(int)
    fr = ev - i
    return y * (g[i] * (1 - fr) + g[i + 1] * fr)


def midband(y, rng, keep=0.55, lo=150, hi=1500):
    """The bee lives in 150-1500 Hz: the synth's firing tones stand 18-29 dB over the noise there, the real
    engine's 0-21. Same idea as debuzz, gentler: part of the band becomes noise riding the band's own envelope."""
    from scipy.signal import hilbert
    sos = butter(3, [lo, hi], 'bandpass', fs=SR, output='sos')
    band = sosfiltfilt(sos, y)
    env = sosfiltfilt(butter(2, 300, fs=SR, output='sos'), np.abs(hilbert(band)))
    nz = sosfiltfilt(sos, rng.standard_normal(len(y))) * np.maximum(env, 0)
    nz *= np.sqrt((band ** 2).mean() / ((nz ** 2).mean() + 1e-20))
    return y - band + keep * band + np.sqrt(1 - keep ** 2) * nz


def profile(x, f0, h=np.geomspace(0.25, 60, 120)):
    """Spectral envelope on the harmonic axis (frequency / firing rate), smoothed to 1/3 octave, in dB."""
    from scipy.signal import welch
    f, P = welch(x, SR, nperseg=8192)
    out = []
    for hh in h:
        b = (f >= hh * f0 * 2 ** (-1 / 6)) & (f < hh * f0 * 2 ** (1 / 6))
        out.append(10 * np.log10(P[b].mean() + 1e-20) if b.any() else np.nan)
    return h, np.array(out)


def real_refs(name):
    """(rpm, clip segment) of the real recordings recompose.py chose for this engine (cook/work/levels.recorded.json)."""
    lv = json.load(open(os.path.join(HERE, "cook", "work", "levels.recorded.json")))["engines"].get(name)
    refs = []
    for st in (lv or {}).get("steps", []):
        clip, span = st[-1].split()[:2]
        a, b = map(float, span.split("s@")[0].split("-"))
        at = int(span.split("@")[1])
        sr, x = wavfile.read(os.path.join(HERE, "recompose", "src", name, clip + ".wav"))
        x = x.astype(float)
        refs.append((at, (x.mean(1) if x.ndim > 1 else x)[int(a * sr):int(b * sr)]))
    return refs


def match_real(layers, k, cyl, refs, lim=15.0):
    """EQ both layers (same filter) so their sum has the tone of the nearest real recording, compared on the
    harmonic axis so a recording at another rpm still lines up. Gain limited to +-lim dB."""
    from scipy.signal import firwin2
    at, ref = min(refs, key=lambda r: abs(np.log(r[0] / k)))
    f0, f0r = k / 60 * cyl / 2, at / 60 * cyl / 2
    h, pr = profile(ref, f0r)
    _, ps = profile(sum(layers), f0)
    ok = np.isfinite(pr) & np.isfinite(ps) & (h * f0 < 20000) & (h * f0r < 20000)
    d = (pr - ps)[ok]
    d -= np.average(d, weights=h[ok] ** -0.5)  # tone, not level: the level is set afterwards
    gf = np.r_[0, h[ok] * f0, SR / 2]
    gd = np.clip(np.r_[d[0], d, d[-1]], -lim, lim)
    keep = np.r_[True, np.diff(gf) > 0]
    fir = firwin2(4097, gf[keep] / (SR / 2), 10 ** (gd[keep] / 20))
    return [fftconvolve(x, fir, mode="same") for x in layers], at


def envelope(x, bands):
    from scipy.signal import welch
    f, P = welch(x, SR, nperseg=8192)
    return np.array([10 * np.log10(P[(f >= b * 2 ** (-1 / 12)) & (f < b * 2 ** (1 / 12))].mean() + 1e-20) for b in bands])


def fixed_eq(layers, eq):
    from scipy.signal import firwin2
    f, g = np.array(eq["hz"]), np.array(eq["db"])
    fir = firwin2(4097, np.r_[0, f, SR / 2] / (SR / 2), 10 ** (np.r_[g[0], g, g[-1]] / 20))
    return [fftconvolve(x, fir, mode="same") for x in layers]


def make_eq(name, clip, start, lim=6.0, trust_hz=250.0, bass=0.0):
    """fit/<name>/eq.json: real recording's envelope over the fitted generator's (both at idle, after outdoors()),
    level removed, smoothed over 1/3 octave, limited to +-lim dB. Nothing below trust_hz: a video's microphone has
    no real bass, and copying its -12 dB there made take 8 sound like a can in game."""
    import fit_idle
    sr, x = wavfile.read(clip)
    real = x.astype(float)[int(start * SR):int((start + 2.5) * SR)]
    eq = os.path.join(HERE, "fit", name, "eq.json")
    if os.path.exists(eq):
        os.remove(eq)
    from iconic import ICONIC
    ex, en = step(name, ICONIC[name]["idle"], np.random.default_rng(11))
    bands = fit_idle.BANDS
    d = envelope(real, bands) - envelope(ex + en, bands)
    d = np.convolve(np.r_[d[0], d, d[-1]], np.ones(3) / 3, "valid")
    d = np.clip(d - np.median(d[bands >= trust_hz]), -lim, lim)
    d[bands < trust_hz] = bass  # a level for the bass, by ear: the video cannot say
    json.dump({"hz": bands.round(1).tolist(), "db": d.round(2).tolist(), "clip": os.path.basename(clip), "start": start}, open(eq, "w"))
    print("eq", " ".join(f"{b:.0f}:{v:+.0f}" for b, v in list(zip(bands, d))[::3]))


def pingpong(seg):
    return np.r_[seg, seg[::-1]]


def target(kind, k, idle, top):
    lo, hi = PAIR[kind]
    return float(np.interp(k, [idle, top], [lo, hi]))


def rasp(y, rng, mix=0.35):
    """The exhaust note's rasp: turbulence at the tailpipe, noise from 350 Hz up that bursts with every pulse
    (envelope of the note itself, sharpened), so it reads as a crackly exhaust rather than a clean tone."""
    env = sosfiltfilt(butter(2, 250, fs=SR, output='sos'), np.abs(y))
    env = (env / (env.max() + 1e-12)) ** 1.6
    nz = sosfiltfilt(butter(2, [350, 7000], 'bandpass', fs=SR, output='sos'), rng.standard_normal(len(y))) * env
    return y + nz * mix * np.sqrt((y ** 2).mean() / ((nz ** 2).mean() + 1e-20))


def step(name, k, rng):
    # exhaust note and intake/mechanical layer from separate renders (synthloop/cgt: same engine, one voice muted
    # each); the scene rng is rewound for the second so both layers share the same rev wander and firing strengths
    import scene_iconic as si, scene
    n = int((SEG + 5) * SR)
    rpm, thr, jake = np.full(n, float(k)), np.ones(n), np.zeros(n)
    state = scene.rng.bit_generator.state
    out = {}
    for layer in ("exh", "eng"):
        scene.rng.bit_generator.state = state
        out[layer] = si.sound(name, os.path.join(HERE, RENDER, layer), rpm, thr, jake)
    from iconic import ICONIC
    cyl = len(ICONIC[name]["on"])
    if CLEAN:
        ex, en = outdoors(out["exh"], rng), outdoors(out["eng"], rng)
        eq = os.path.join(HERE, "fit", name, "eq.json")
        if os.path.exists(eq):  # one fixed EQ for every step: the residual of the idle fit, a colour in Hz
            ex, en = fixed_eq([ex, en], json.load(open(eq)))
        else:
            if name not in REFS:
                REFS[name] = real_refs(name)
            if REFS[name]:
                (ex, en), at = match_real([ex, en], k, cyl, REFS[name])
        a, b = int(4 * SR), int((4 + SEG) * SR)
        return pingpong(ex[a:b]), pingpong(en[a:b])
    for layer in out:
        if layer not in TONES:
            TONES[layer] = fixed_tones(os.path.join(HERE, "cgt", layer), name)
        out[layer] = untone(out[layer], *TONES[layer])
    from iconic import ICONIC
    cyl = len(ICONIC[name]["on"])
    jit = np.random.default_rng(rng.integers(1 << 30))
    for layer in out:  # the same firing strengths on both layers: it is one engine
        out[layer] = firing_jitter(out[layer], rpm, cyl, np.random.default_rng(jit.integers(1)))
    ex = outdoors(debuzz(midband(rasp(out["exh"], rng), rng), rng), rng)
    en = outdoors(debuzz(midband(out["eng"], rng), rng), rng)
    if name not in REFS:
        REFS[name] = real_refs(name)
    if REFS[name]:
        (ex, en), at = match_real([ex, en], k, cyl, REFS[name])
    a, b = int(4 * SR), int((4 + SEG) * SR)  # after the throttle smoothing has settled
    return pingpong(ex[a:b]), pingpong(en[a:b])


def build(name):
    import buzz
    from iconic import ICONIC
    d = ICONIC[name]
    kind, cyl = "car", len(d["on"])
    rng = np.random.default_rng(11)
    steps = list(range(d["idle"], d["top"], 1000))
    folder = os.path.join(OUT, f"MT_{name}")
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))
    rows, loops = [], {}
    for k in steps:
        ex, eng = step(name, k, rng)
        want = target(kind, k, d["idle"], d["top"])
        eng *= 10 ** ((lufs(ex) + ENGINE_DB - lufs(eng)) / 20)
        if lufs(ex + eng) < lufs(ex - eng):  # both layers come from the same pulses: never let them cancel
            eng = -eng
        g = 1.0
        for _ in range(6):  # limiting takes loudness back: push the gain until the limited pair hits the target
            lex, leng = limit([ex * g, eng * g])
            g *= 10 ** ((want - lufs(lex + leng)) / 20)
        ex, eng = lex, leng
        pair = lufs(ex + eng)
        f0 = buzz.firing_hz(name, k, cyl)
        bz = max(buzz.overtone_ratio(w, f0) for w in (ex, ex + eng))
        for layer, w in (("Engine", eng), ("Exhaust", ex)):
            wavfile.write(os.path.join(folder, f"MT_{name}_{k}rpm_{layer}.wav"), SR, (w * 32767).astype(np.int16))
        loops[k] = ex + eng
        rows.append([k, round(pair, 2), round(lufs(ex), 2), round(lufs(eng), 2), round(bz, 1), len(ex) / SR])
        print(f"{k:5d} rpm  exhaust {lufs(ex):6.2f}  engine {lufs(eng):6.2f}  pair {pair:6.2f} (target {want:6.2f})  buzz {bz:+.1f} dB  loop {len(ex) / SR:.1f} s")
    lv = json.load(open(LEVELS))
    lv["engines"][name] = {"class": "petrol", "kind": kind, "cylinders": cyl, "steps": rows,
                           "source": "synth", "method": "pingpong", "volumes": VOLUMES}
    json.dump(lv, open(LEVELS, "w"), indent=1)
    preview(name, loops, d["idle"], d["top"])


def preview(name, loops, idle, top):
    # the way the game plays it: the two nearest steps cross-faded and pitched to the exact rpm
    import scene_diesel as sd
    os.makedirs(PREVIEW, exist_ok=True)
    t = np.arange(int(16 * SR)) / SR
    rpm = np.interp(t, [0, 3, 9, 10.5, 13, 16], [idle, idle, top - 300, top - 300, 3000, idle])
    y = sd.play(dict(sorted(loops.items())), rpm)
    y = y / np.abs(y).max() * 0.89
    wav = os.path.join(PREVIEW, f"{name}.wav")
    wavfile.write(wav, SR, (y * 32767).astype(np.int16))
    mp3 = wav[:-4] + ".mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-b:a", "192k", mp3], check=True)
    print("preview", mp3)


def demo():
    rng = np.random.default_rng(0)
    seg = sosfilt(butter(2, 2000, fs=SR, output='sos'), rng.standard_normal(SR))
    lp = pingpong(seg)
    wrapped = np.r_[lp, lp]
    jumps = np.abs(np.diff(wrapped))
    assert jumps[len(lp) - 1] <= 3 * np.median(jumps) + 1e-9, "seam jump"  # loop end -> start
    assert jumps[len(seg) - 1] == 0  # the turnaround repeats one sample
    x = rng.standard_normal(SR * 3) * 0.1
    x *= 10 ** ((-14 - lufs(x)) / 20)
    assert abs(lufs(x) + 14) < 0.01
    assert np.abs(softlimit(x * 20)).max() <= PEAK
    a, b = limit([x * 20, x * 5])
    assert max(np.abs(a).max(), np.abs(b).max(), np.abs(a + b).max()) <= PEAK + 1e-9
    print("demo ok")


if __name__ == "__main__":
    {"build": lambda: [build(n) for n in sys.argv[2:]], "demo": demo,
     "eq": lambda: make_eq(sys.argv[2], sys.argv[3], float(sys.argv[4]), bass=float(sys.argv[5]) if len(sys.argv) > 5 else 0.0)}[sys.argv[1]]()
