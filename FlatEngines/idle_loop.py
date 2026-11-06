# One step of an engine's set from a real recording, looped forward (not ping-pong): the loop length is picked
# where the waveform one engine cycle after the cut best matches the start, then one cycle is crossfaded, so the
# wrap carries on exactly as the recording did. Pitch is set to the step rpm first (measured firing rate).
#   python -I idle_loop.py <engine> <clip.wav> <start s> <step rpm> [loop s]
#   python -I idle_loop.py demo
# Writes MT_<engine>_<step>rpm_Exhaust.wav (the recording) and _Engine.wav (its 1.2 kHz low-pass, 4 dB under) into
# D:\MT\SoundCook\wav\MT_<engine>, levelled to the pair level synthloop.PAIR gives that step, and updates the
# step's row in cook/levels.json.
import os, sys, json, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt, resample
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "recompose")]
SR = 48000


def seamless(x, cycle, lo, hi):
    """x: steady audio starting at the loop start. Returns a loop of length in [lo, hi] samples whose wrap is
    crossfaded over one engine cycle at the best-matching length."""
    C = int(cycle)
    head = x[:C]
    def score(L):
        b = x[L:L + C]
        return np.dot(head, b) / np.sqrt(np.dot(head, head) * np.dot(b, b) + 1e-30)
    L = max(range(lo, hi), key=score)
    out = x[:L].copy()
    ramp = np.linspace(0, 1, C)
    out[:C] = x[:C] * ramp + x[L:L + C] * (1 - ramp)  # the loop's end runs into x[L..], which fades into the start
    return out, L, score(L)


def build(name, clip, start, step, seconds=2.5):
    import recompose as rc
    import synthloop as sl
    from iconic import ICONIC
    cyl = len(ICONIC[name]["on"])
    x = rc.read(clip)
    a = int(start * SR)
    g = x[a:a + int((seconds + 1.0) * SR)]
    t, rpm, _ = rc.track(g, cyl, 0.5 * step, 1.6 * step)
    f0 = rc.firing(np.median(rpm), cyl) * rc.refine(g, rc.firing(np.median(rpm), cyl))
    true_rpm = f0 * 60 * 2 / cyl
    g = resample(g, int(round(len(g) * true_rpm / step)))  # now fires at exactly the step rpm
    cycle = SR * 120 / step  # one engine cycle (two revs), samples
    n = int(seconds * SR)
    loop, L, sc = seamless(g, cycle, n - int(4 * cycle), n + int(4 * cycle))
    eng = sosfiltfilt(butter(4, 1200, fs=SR, output="sos"), np.r_[loop, loop, loop])[len(loop):2 * len(loop)]
    eng *= 10 ** ((sl.lufs(loop) - 4 - sl.lufs(eng)) / 20)
    # tone of the synth step it replaces, so it hands over to the synth steps above without a change of colour;
    # filtered on three copies so the FIR wraps across the seam (the loop stays seamless)
    syn = sum(sl.step(name, step, np.random.default_rng(11)))
    before = sl.profile(loop + eng, f0 * step / true_rpm)[1] - sl.profile(syn, f0 * step / true_rpm)[1]
    (l3, e3), _ = sl.match_real([np.r_[loop, loop, loop], np.r_[eng, eng, eng]], step, cyl, [(step, syn)])
    loop, eng = l3[len(loop):2 * len(loop)], e3[len(loop):2 * len(loop)]
    after = sl.profile(loop + eng, f0 * step / true_rpm)[1] - sl.profile(syn, f0 * step / true_rpm)[1]
    for lbl, dv in (("real - synth tone before", before), ("after", after)):
        dv = dv - np.nanmean(dv)
        print(f"  {lbl:25s} harmonic 1-60 spread {np.nanstd(dv):.1f} dB, worst {np.nanmax(np.abs(dv)):.1f} dB")
    d = ICONIC[name]
    want = sl.target("car", step, d["idle"], d["top"])
    gain = 1.0
    for _ in range(6):
        ex2, en2 = sl.limit([loop * gain, eng * gain])
        gain *= 10 ** ((want - sl.lufs(ex2 + en2)) / 20)
    folder = os.path.join(sl.OUT, f"MT_{name}")
    for layer, w in (("Exhaust", ex2), ("Engine", en2)):
        wavfile.write(os.path.join(folder, f"MT_{name}_{step}rpm_{layer}.wav"), SR, (w * 32767).astype(np.int16))
    lv = json.load(open(sl.LEVELS))
    rows = lv["engines"][name]["steps"]
    row = next(r for r in rows if r[0] == step)
    row[1:] = [round(sl.lufs(ex2 + en2), 2), round(sl.lufs(ex2), 2), round(sl.lufs(en2), 2), 0.0, len(loop) / SR]
    lv["engines"][name].setdefault("recorded_steps", {})[str(step)] = f"{os.path.basename(clip)[:-4]} {start}s, {true_rpm:.0f} rpm"
    json.dump(lv, open(sl.LEVELS, "w"), indent=1)
    print(f"{name} {step} rpm from {os.path.basename(clip)} @{start}s: measured {true_rpm:.0f} rpm, loop {L / SR:.3f} s, "
          f"wrap match {sc:.3f}, pair {sl.lufs(ex2 + en2):.2f} LUFS (target {want:.2f})")
    return ex2 + en2


def demo():
    # a 25 Hz pulse train with a slow wobble: the chosen loop must wrap with no jump bigger than the signal's own
    rng = np.random.default_rng(0)
    t = np.arange(4 * SR) / SR
    x = np.sin(2 * np.pi * 50 * t) * (1 + 0.3 * np.sin(2 * np.pi * 25 * t)) + 0.01 * rng.standard_normal(len(t))
    loop, L, sc = seamless(x, SR / 25, 2 * SR - 4000, 2 * SR + 4000)
    assert sc > 0.99, sc
    w = np.r_[loop, loop]
    assert np.abs(np.diff(w)).max() <= 1.2 * np.abs(np.diff(x)).max()
    print("demo ok", L, round(sc, 4))


if __name__ == "__main__":
    if sys.argv[1] == "demo":
        demo()
    else:
        build(sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4]), *(float(v) for v in sys.argv[5:]))
