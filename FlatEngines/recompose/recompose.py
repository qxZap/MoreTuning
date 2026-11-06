# Engine sounds recomposed from real exterior recordings (replaces the synthesised loops of the 28 new engines).
#   python -I recompose.py fetch <key> <youtube id|url>...   audio only, 48 kHz mono wav -> src/<key>/, meta.txt
#   python -I recompose.py analyse <key>                     per step: the segment it would use (prints)
#   python -I recompose.py build <key>...                    loops -> D:\MT\SoundCook\wav\MT_<key>\, levels.json, preview mp3
#   python -I recompose.py demo                              self-check on a synthetic engine
# Then cook as COOKED.md (ue_import, Cook, copy_cooked, make_data). Candidate steps are the synth's rpm list
# (cook/work/levels.synth.json); per step ONE steady segment is looped ping-pong (forward, then reversed), and the
# steps are thinned to MIN_GAP. Levels follow the user's own engines (TARGETS), not vanilla's EngineSoundData.
# Downloads are data only: nothing from src/ is executed or imported.
import os, sys, json, glob, subprocess, numpy as np
from scipy.io import wavfile
from scipy.signal import stft, butter, sosfilt, resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
COOK = os.path.join(os.path.dirname(HERE), "cook")
sys.path.insert(0, COOK)
from loudness import lufs  # noqa: E402

SRC, PREV = os.path.join(HERE, "src"), os.path.join(HERE, "preview")
OUT = r"D:\MT\SoundCook\wav"
LEVELS = os.path.join(COOK, "levels.json")
SYNTH = os.path.join(COOK, "work", "levels.synth.json")  # the synth's step lists = the candidate steps
SR, FS = 48000, 8000          # audio rate; analysis rate
HOP = 0.05                    # track hop, s
MAX_SHIFT = 0.12              # pitch shift allowed when filling a step
MIN_CONTRAST = 3.0            # dB the firing comb must stand over the noise between its teeth
MIN_SRC, MAX_SRC = 1.0, 3.0   # s of one steady segment; the ping-pong loop is twice that
MAX_SPREAD = 0.03             # +- rpm spread a segment may have; one that wanders sounds wobbly played reversed
MIN_GAP = {"petrol": 1000, "diesel": 300}  # rpm between kept steps: fewer, well-covered steps
ENGINE_LP, ENGINE_DB = 1200.0, -4.0  # engine layer: low-passed copy of the exhaust recording, 4 dB under it
PEAK = 10 ** (-1 / 20)
# Exhaust-layer LUFS at idle / mid / high of the engine's step span. From the user's own SoundCue engines in
# qxZap_MoreTuning_P (cooked waves decoded, 2026-11-06): cars (LS3, 2jz, 392, 50coyote, L86, GM572, 81bb, lt7,
# rb26, S63B44B, amg, hv8, kg8, 707) median idle -15.3 / mid -13.5 / high -11.8; pickups (59cummins, 66duramax,
# 73powerstroke, LightDiesel, 65detroit) -18.5 / -15.0 / -15.1; trucks (C18, N14, x15, d13, mx13, dc16, detroit,
# fh, catc12, DD471) -19.1 / -15.2 / -14.4, plus their Truck_04_Exhaust layer at -14.1. Their cues scale by
# 0.25-0.5 and back up by rpm/throttle modulators of up to 3-4x, so the file level is the comparable number.
TARGETS = {"car": (-15.5, -13.5, -12.5), "pickup": (-17.0, -15.0, -14.5), "truck": (-17.0, -15.0, -14.0)}
PICKUPS = {"12v", "vp44", "cummins67", "ps60"}


def kind(key, cls):
    return "car" if cls == "petrol" else "pickup" if key in PICKUPS else "truck"


def target(kind_, frac):
    i, m, h = TARGETS[kind_]
    return float(np.interp(frac, [0, 0.5, 1], [i, m, h]))


def spec(key):
    v = json.load(open(SYNTH))["engines"][key]
    return {"key": key, "cyl": v["cylinders"], "steps": [r[0] for r in v["steps"]], "class": v["class"],
            "kind": kind(key, v["class"])}


def firing(rpm, cyl):
    # .esc cylinder counts model the Detroit two-strokes as twice their cylinders on four strokes, so one formula
    return rpm / 60 * cyl / 2


def read(p):
    sr, x = wavfile.read(p)
    x = x.astype(float) / (32768.0 if x.dtype == np.int16 else 1.0)
    x = x.mean(axis=1) if x.ndim > 1 else x
    assert sr == SR, (p, sr)
    return x


# ---------------------------------------------------------------- fetch
def fetch(key, ids):
    d = os.path.join(SRC, key)
    os.makedirs(d, exist_ok=True)
    for i in ids:
        url = i if i.startswith("http") else f"https://www.youtube.com/watch?v={i}"
        subprocess.run(["yt-dlp", "-q", "--no-playlist", "-f", "bestaudio", "-x", "--audio-format", "wav",
                        "--postprocessor-args", "ffmpeg:-ar 48000 -ac 1", "-o", os.path.join(d, "%(id)s.%(ext)s"),
                        "--print-to-file", "%(id)s|%(webpage_url)s|%(channel)s|%(title)s", os.path.join(d, "meta.txt"), url])  # a dead id is skipped


# ---------------------------------------------------------------- rpm tracking
def track(x, cyl, rpm_lo, rpm_hi):
    """rpm(t) every HOP s: subharmonic summation over a whitened spectrum, Viterbi with a cost on pitch jumps.
    Returns (t, rpm, salience z-score)."""
    y = resample_poly(x, 1, SR // FS)
    nper = int(0.25 * FS)
    f, t, Z = stft(y, FS, nperseg=nper, noverlap=nper - int(HOP * FS), nfft=8192, boundary=None)
    M = np.abs(Z) ** 0.5
    # whiten: divide by a 60 Hz moving average across frequency, so the harmonic comb counts, not the tilt
    k = max(1, int(60 / (f[1] - f[0])))
    M = M / (np.apply_along_axis(lambda c: np.convolve(c, np.ones(k) / k, "same"), 0, M) + 1e-9)
    grid = np.geomspace(firing(rpm_lo, cyl), firing(rpm_hi, cyl), 300)
    H = 8
    S = np.zeros((len(grid), M.shape[1]))
    for h in range(1, H + 1):
        idx = np.clip(np.round(grid * h / (f[1] - f[0])).astype(int), 0, len(f) - 1)
        S += 0.85 ** (h - 1) * M[idx]
    # odd sub-harmonics present -> the true firing rate is lower; absent -> penalise the half
    for h in (0.5, 1.5, 2.5):
        idx = np.clip(np.round(grid * h / (f[1] - f[0])).astype(int), 0, len(f) - 1)
        S -= 0.5 * M[idx]
    Zs = (S - S.mean(0)) / (S.std(0) + 1e-9)
    lg = np.log2(grid)
    jump = np.abs(lg[:, None] - lg[None, :]) / 0.06  # cost in units of 6 % per frame (free revs are fast)
    cost = jump ** 2 * 0.5
    acc = Zs[:, 0].copy()
    back = np.zeros(Zs.shape, int)
    for j in range(1, Zs.shape[1]):
        tot = acc[None, :] - cost  # [to, from]
        back[:, j] = tot.argmax(1)
        acc = tot.max(1) + Zs[:, j]
    path = np.zeros(Zs.shape[1], int)
    path[-1] = acc.argmax()
    for j in range(Zs.shape[1] - 1, 0, -1):
        path[j - 1] = back[path[j], j]
    fz = grid[path]
    return t, fz * 60 * 2 / cyl, Zs[path, np.arange(len(path))]


def comb_contrast(g, f0):
    """dB of mean power on the firing harmonics (+-6 %) over mean power between them (> 30 % away), 30-2500 Hz.
    Noise or music ~0 dB; an engine that dominates its recording is well above. The roar of a wide-open engine
    is real, so this asks only that the firing comb stands out, not that it carries most of the energy."""
    F = np.abs(np.fft.rfft(g * np.hanning(len(g)))) ** 2
    fr = np.fft.rfftfreq(len(g), 1 / SR)
    b = (fr > 30) & (fr < 2500)
    d = np.abs(fr / f0 - np.round(fr / f0))
    return float(10 * np.log10(F[b & (d < 0.06)].mean() / (F[b & (d > 0.3)].mean() + 1e-30)))


def odd_orders(g, rpm):
    """dB of power at odd multiples of rpm/120 over the noise between multiples. A four-stroke repeats every two
    revs, so at the true rpm these (the half orders) carry energy; at half the true rpm they fall on noise. The
    octave test: the true rpm is the one of rpm/2, rpm, 2 rpm whose odd teeth stand out most."""
    b = rpm / 120
    F = np.abs(np.fft.rfft(g * np.hanning(len(g)))) ** 2
    fr = np.fft.rfftfreq(len(g), 1 / SR)
    m = (fr > 20) & (fr < 1500)
    u = fr / b
    d = np.abs(u - np.round(u))
    return float(10 * np.log10(F[m & (np.round(u) % 2 == 1) & (d < 0.12)].mean() / (F[m & (d > 0.35)].mean() + 1e-30)))


def refine(g, f0, span=0.05):
    """The tracker is good to a few %; the harmonic comb on the warped grain finds the rest. -> correction ratio."""
    F = np.abs(np.fft.rfft(g * np.hanning(len(g)), n=max(len(g), 1 << 16))) ** 2
    fr = np.fft.rfftfreq(max(len(g), 1 << 16), 1 / SR)
    band = (fr > 30) & (fr < 2000)
    F, fr = F[band], fr[band]
    best = max(np.linspace(1 - span, 1 + span, 101),
               key=lambda q: F[np.abs(fr / (f0 * q) - np.round(fr / (f0 * q))) < 0.04].sum())
    return best


# ---------------------------------------------------------------- loops
def flatten(seg, tt, r, k):
    """Time-warp a grain so its firing rate is exactly step rpm k (local pitch ratio k / r(t)). Done at 2x so the
    interpolation stays anti-aliased."""
    up = resample_poly(seg, 2, 1)
    rr = np.interp(tt[0] + np.arange(len(up)) / (2 * SR), tt, r)
    ph = np.cumsum(rr / k) / (2 * SR)  # output time of each input sample
    y = resample_poly(np.interp(np.arange(0, ph[-1], 1 / (2 * SR)), ph, up), 1, 2)
    e = int(0.01 * SR)  # the resampler's zero-padded edges ramp; the ping-pong turnarounds sit there
    return y[e:-e]


def pingpong(g):
    """Forward then reversed, without repeating the two turnaround samples: the loop wraps back to g[0] the way
    the reversed run arrives at it, so it is seamless by construction; its period is twice the segment."""
    return np.concatenate([g, g[-2:0:-1]])


def circ_filter(sos, x):
    y = sosfilt(sos, np.concatenate([x, x, x]))
    return y[len(x):2 * len(x)]


HP = butter(2, 25, "highpass", fs=SR, output="sos")
LP = butter(4, ENGINE_LP, "lowpass", fs=SR, output="sos")


def softlimit(v, knee=10 ** (-6 / 20)):
    a = np.abs(v)
    o = v.copy()
    m = a > knee
    o[m] = np.sign(v[m]) * (knee + (PEAK - knee) * np.tanh((a[m] - knee) / (PEAK - knee)))
    return o


class Clip:
    def __init__(self, p, sp):
        self.name = os.path.basename(p)[:-4]
        self.x = read(p)
        self.t, self.rpm, self.sal = track(self.x, sp["cyl"], sp["steps"][0] * 0.75, sp["steps"][-1] * 1.1)
        self.t = self.t + 0.125  # stft frame centre


def spread(r):
    """rpm stability of a stretch of the track, as +- fraction of its median: half the 5-95 % range. Drift and
    wobble both show in it; the pitch bend straightens them, but reversed (ping-pong) a wander still sounds."""
    return float((np.percentile(r, 95) - np.percentile(r, 5)) / 2 / np.median(r))


def grains(clips, k, cyl, w):
    """Every run of track frames within +-w of step rpm k, in every clip, as a grain warped to exactly k.
    Rejected: weak track (salience z < 1.5), firing comb under MIN_CONTRAST dB, tracked an octave off, clipped."""
    out = []
    n, n_min = int(MAX_SRC / HOP), int(MIN_SRC / HOP) + 1
    for c in clips:
        inb = np.abs(c.rpm / k - 1) <= w
        i = 0
        while i < len(inb):
            if not inb[i]:
                i += 1
                continue
            j = i
            while j < len(inb) and inb[j]:
                j += 1
            i0, i1 = i, j
            i = j
            if i1 - i0 < 3:  # under 0.15 s
                continue
            if i1 - i0 > n_min:  # the steadiest window of MIN_SRC..MAX_SRC s in this run, length only a tie-break
                best = None
                for L in range(min(n, i1 - i0), n_min - 1, -5):
                    for a0 in range(i0, i1 - L + 1, 2):
                        q = spread(c.rpm[a0:a0 + L]) - 0.001 * L * HOP  # 0.1 % per second of length
                        if best is None or q < best[0]:
                            best = (q, a0, L)
                i0, i1 = best[1], best[1] + best[2]
            sal = float(np.mean(c.sal[i0:i1]))
            a, b = int((c.t[i0] - HOP / 2) * SR), int((c.t[i1 - 1] + HOP / 2) * SR)
            seg = c.x[max(a, 0):b]
            clipped = float(np.mean(np.abs(seg) > 0.98))
            if sal < 1.5 or clipped > 0.001:
                continue
            r = c.rpm[i0:i1] * refine(flatten(seg, c.t[i0:i1], c.rpm[i0:i1], k), firing(k, cyl))
            g = flatten(seg, c.t[i0:i1], r, k)
            harm = comb_contrast(g, firing(k, cyl))  # on the warped grain: a sweep smears it otherwise
            if harm < MIN_CONTRAST:
                continue
            if len(g) >= 0.5 * SR and cyl <= 12:  # long enough to resolve rpm/120; Detroits have no half orders
                o = {h: odd_orders(g, k * h) for h in (0.5, 1, 2)}
                if max(o[0.5], o[2]) > o[1] + 2:  # tracked an octave off
                    continue
            if len(g) < int(4 * 120 / k * SR) // max(1, cyl // 12 + 1):  # under ~4 cycles after the warp
                continue
            g = g * 10 ** ((-20 - lufs(g, SR)) / 20) if len(g) >= 0.4 * SR else g / (np.sqrt(np.mean(g ** 2)) + 1e-12) * 0.1
            slope = float(np.polyfit(c.t[i0:i1], c.rpm[i0:i1], 1)[0])  # rpm/s; falling = overrun
            warp = float(np.max(np.abs(k / r - 1)))
            dur = len(g) / SR
            med = float(np.median(r))
            sp_ = spread(c.rpm[i0:i1])
            # rpm stability first: +-1 % of spread costs as much as everything else can earn; then length, clarity, level
            out.append({"clip": c.name, "t0": c.t[i0], "t1": c.t[i1 - 1], "rpm": med, "dev": abs(med / k - 1),
                        "sal": sal, "harm": harm, "warp": warp, "slope": slope, "g": g, "dur": dur, "spread": sp_,
                        "score": -400 * sp_ + 0.3 * min(dur, MAX_SRC) + harm / 15 + 0.1 * sal
                                 - (0.6 if slope < -100 else 0) - 3 * warp})
    return sorted(out, key=lambda d: -d["score"])


def assign(sp, clips, gap=None):
    """Per candidate step: the best single steady segment (>= MIN_SRC s) within MAX_SHIFT of it, favouring the
    clip that covers most steps so the character holds. Then thinned: the idle-most and top-most steps first,
    then the rest by quality, each at least `gap` rpm from every kept one. -> {rpm: (segment, grain, filled?)}"""
    gap = MIN_GAP[sp["class"]] if gap is None else gap
    from buzz import overtone_ratio, LIMIT  # the "bee": firing overtones standing over the noise, 1.5-6 kHz
    cand = {k: [g for g in grains(clips, k, sp["cyl"], MAX_SHIFT)
                if g["dur"] >= MIN_SRC and g["spread"] <= MAX_SPREAD and overtone_ratio(g["g"], firing(k, sp["cyl"])) <= LIMIT - 0.5]
            for k in sp["steps"]}
    cover = {}
    for gs in cand.values():
        for c in {g["clip"] for g in gs}:
            cover[c] = cover.get(c, 0) + 1
    top = max(cover.values(), default=1)
    best = {}
    for k, gs in cand.items():
        if gs:
            g = max(gs, key=lambda g: g["score"] + 0.6 * cover[g["clip"]] / top)  # same recording: a tie-break
            best[k] = (g["g"], g, g["dev"] > 0.06)
    if not best:
        return {}
    ks = sorted(best)
    order = [ks[0], ks[-1]] + sorted(ks[1:-1], key=lambda k: -best[k][1]["score"])
    keep = []
    for k in order:  # a stretch already looped for another step adds nothing the game's pitching does not
        g = best[k][1]
        reused = any(best[j][1]["clip"] == g["clip"] and best[j][1]["t0"] < g["t1"] and g["t0"] < best[j][1]["t1"] for j in keep)
        if not reused and all(abs(k - j) >= gap for j in keep):
            keep.append(k)
    return {k: best[k] for k in sorted(keep)}


def load(key, sp):
    return [Clip(p, sp) for p in sorted(glob.glob(os.path.join(SRC, key, "*.wav")))]


def describe(g):
    return f"{g['clip']} {g['t0']:.1f}-{g['t1']:.1f}s@{g['rpm']:.0f} +-{g['spread'] * 100:.1f}%"


def analyse(key):
    """Per step: the segment it would use, without writing anything."""
    sp = spec(key)
    clips = load(key, sp)
    for c in clips:
        print(f"{c.name}: {c.t[-1]:.0f} s, rpm 5-95 % {np.percentile(c.rpm, 5):.0f}..{np.percentile(c.rpm, 95):.0f}")
    for k, (seg, g, filled) in sorted(assign(sp, clips).items()):
        print(f"  {k:5d} {'fill ' if filled else 'found'} segment {len(seg) / SR:.2f}s (loop {2 * len(seg) / SR:.2f}s)"
              f" score {g['score']:.1f} harm {g['harm']:.1f}: {describe(g)}")


def build(key):
    from buzz import overtone_ratio, firing_hz
    sp = spec(key)
    got = assign(sp, load(key, sp))
    if len(got) < 3:
        sys.exit(f"{key}: too little material ({sorted(got)}): no usable recording")
    d = os.path.join(OUT, f"MT_{key}")
    os.makedirs(d, exist_ok=True)
    for f in glob.glob(os.path.join(d, "*.wav")):
        os.remove(f)
    lv = json.load(open(LEVELS))
    ks = sorted(got)
    rows, pairs = [], {}
    for k in ks:
        seg, g, filled = got[k]
        x = circ_filter(HP, pingpong(seg))
        e = circ_filter(LP, circ_filter(LP, x)[::-1])[::-1] * 10 ** (ENGINE_DB / 20)  # zero-phase: sums with x
        lo, hi = sp["steps"][0], sp["steps"][-1]  # the engine's whole rev range, not just the kept steps
        want = target(sp["kind"], (k - lo) / (hi - lo))  # exhaust layer
        for _ in range(8):  # level the exhaust layer, soft-limit the peaks of both, repeat
            m = 10 ** ((want - lufs(x, SR)) / 20)
            e, x = e * m, x * m
            if max(np.abs(e).max(), np.abs(x).max()) <= PEAK and abs(20 * np.log10(m)) < 0.05:
                break
            e, x = softlimit(e), softlimit(x)
        e, x = np.clip(e, -PEAK, PEAK), np.clip(x, -PEAK, PEAK)
        got_x = lufs(x, SR)
        assert abs(got_x - want) < 0.3, (key, k, got_x, want)  # the loudness check: exhaust layer on its target
        for layer, v in (("Engine", e), ("Exhaust", x)):
            wavfile.write(os.path.join(d, f"MT_{key}_{k}rpm_{layer}.wav"), SR, np.round(v * 32767).astype(np.int16))
        pair = lufs(e + x, SR)
        pairs[k] = e + x
        # exhaust layer and pair: the engine layer alone is low-passed at 1.2 kHz, so in the 1.5-6 kHz band the
        # measure uses it is only the filter skirt and reads high whatever the recording
        bz = max(overtone_ratio(w, firing_hz(key, k, sp["cyl"])) for w in (x, e + x))
        # row[1] is what loudness.py verify checks the cooked pair against
        rows.append([k, round(pair, 2), round(pair, 2), round(20 * np.log10(max(np.abs(e).max(), np.abs(x).max())), 2),
                     round(bz, 1), "fill" if filled else "found", round(g["warp"] * 100, 1), round(len(x) / SR, 2),
                     round(want, 2), round(got_x, 2), round(lufs(e, SR), 2), describe(g)])
        print(f"  {k:5d} {'fill ' if filled else 'found'} warp<={g['warp'] * 100:4.1f}%  loop {len(x) / SR:.2f}s"
              f"  exhaust {got_x:6.1f} (want {want:.1f})  engine {rows[-1][10]:6.1f}  pair {pair:6.1f} LUFS"
              f"  buzz {bz:+.1f} dB  {describe(g)}")
    print(f"{key}: kept {ks}; not kept {[k for k in sp['steps'] if k not in got]}")
    lv["engines"][key] = {"class": sp["class"], "kind": sp["kind"], "cylinders": sp["cyl"], "steps": rows,
                          "source": "recording", "method": "pingpong"}
    json.dump(lv, open(LEVELS, "w"), indent=1)
    preview(key, pairs)


def preview(key, pairs, each=4.0):
    """idle > mid > high steps, each looped for `each` s with a short crossfade, as mp3."""
    os.makedirs(PREV, exist_ok=True)
    ks = sorted(pairs)
    pick = sorted({ks[0], ks[len(ks) // 4], ks[len(ks) // 2], ks[3 * len(ks) // 4], ks[-1]})
    xf = int(0.15 * SR)
    out = np.zeros(0)
    for k in pick:
        v = np.tile(pairs[k], int(np.ceil(each * SR / len(pairs[k]))) + 1)[:int(each * SR) + xf]
        if len(out):
            w = np.linspace(0, 1, xf)
            out[-xf:] = out[-xf:] * (1 - w) + v[:xf] * w
            v = v[xf:]
        out = np.concatenate([out, v])
    wav = os.path.join(PREV, f"{key}.wav")
    wavfile.write(wav, SR, np.round(np.clip(out, -1, 1) * 32767).astype(np.int16))
    mp3 = wav[:-4] + ".mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-b:a", "192k", mp3], check=True)
    os.remove(wav)
    print(f"  preview {mp3}: steps {pick}")


# ---------------------------------------------------------------- self-check
def demo():
    """Synthetic V8 holding 800, sweeping to 2000 and holding it: the tracker must follow within 3 %, 800 and 2000
    must get ping-pong loops (seamless, twice the segment), 2150 a fill when it is the only high candidate, and
    1400 (swept past in 0.2 s) nothing."""
    cyl, dur = 8, 8.0
    tt = np.arange(int(dur * SR)) / SR
    rpm = np.interp(tt, [0, 2.5, 4, 8], [800, 800, 2000, 2000])
    ph = 2 * np.pi * np.cumsum(firing(rpm, cyl)) / SR
    rng = np.random.default_rng(1)
    x = sum(0.8 ** h * np.sin(h * ph + h) for h in range(1, 10)) * 0.1 + rng.normal(0, 0.01, len(tt))
    c = Clip.__new__(Clip)
    c.name, c.x = "demo", x
    c.t, c.rpm, c.sal = track(x, cyl, 600, 3000)
    c.t = c.t + 0.125
    truth = np.interp(c.t, tt, rpm)
    assert np.median(np.abs(c.rpm / truth - 1)) < 0.03, np.median(np.abs(c.rpm / truth - 1))
    got = assign({"steps": [800, 1400, 2000], "cyl": cyl, "class": "petrol"}, [c], gap=300)
    assert set(got) == {800, 2000} and not got[2000][2], {k: v[2] for k, v in got.items()}
    assert len(got[2000][0]) >= 2.5 * SR, len(got[2000][0]) / SR
    fill = assign({"steps": [800, 2150], "cyl": cyl, "class": "petrol"}, [c], gap=300)
    assert fill[2150][2], "2150 should be a fill from the 2000 hold"
    seg = got[2000][0]
    loop = pingpong(seg)
    assert len(loop) == 2 * len(seg) - 2 and np.array_equal(loop[len(seg):], seg[-2:0:-1])
    steps = np.abs(np.diff(np.concatenate([loop, loop[:1]])))
    assert steps[-1] <= np.percentile(steps, 99.9), "wrap is not seamless"
    print("demo ok, segments", {k: round(len(v[0]) / SR, 2) for k, v in got.items()})


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "fetch":
        fetch(sys.argv[2], sys.argv[3:])
    elif cmd == "analyse":
        analyse(sys.argv[2])
    elif cmd == "build":
        for k in sys.argv[2:]:
            build(k)
    else:
        demo()
