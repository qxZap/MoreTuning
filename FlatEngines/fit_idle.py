# Fit the patched generator (enginesound_mt.linux) to a real recording: search the pipe / valve / combustion
# parameters until its sound at the recording's rpm has the same tone (1/6-octave envelope in Hz, mic tilt
# removed) and the same tonal-vs-noisy balance per octave. Then every rpm step comes from that one engine.
#   python -I fit_idle.py fit <engine> <clip.wav> <start s> [rounds] [rpm]      -> fit/<engine>/best.json + best.esc
#   python -I fit_idle.py demo
import os, sys, json, subprocess, numpy as np
from scipy.io import wavfile
from scipy.signal import welch
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "recompose")]
SR = 48000
BANDS = np.geomspace(60, 12000, 47)  # 1/6 octave
OCT = [125, 250, 500, 1000, 2000, 4000]
# name: (lo, hi, log scale)
SPACE = {"ex_delay": (0.0002, 0.004, 1), "ex_spread": (0.0, 0.3, 0), "ex_closed": (0.5, 0.97, 0), "ex_beta": (-0.3, 0.3, 0),
         "extr_delay": (0.0003, 0.006, 1), "extr_beta": (-0.3, 0.3, 0),
         "pipe_delay": (0.001, 0.02, 1), "pipe_alpha": (-0.3, 0.5, 0), "pipe_beta": (-0.4, 0.2, 0),
         "muf1": (0.0001, 0.01, 1), "muf2": (0.0001, 0.01, 1), "muf_beta": (-0.2, 0.2, 0),
         "ign_time": (0.02, 0.2, 1), "ign": (0.3, 3.0, 1), "piston": (0.5, 5.0, 1),
         "noise": (0.02, 0.6, 1), "var": (0.05, 0.5, 0), "ex_shift": (0.0, 0.3, 0), "fluct": (0.0, 0.05, 0)}
# crank offsets of the shipped V10 config (cgt/cfg): the firing order stays the engine's
CRANK = [i / 10 for i in range(10)]


def ron(p, rpm, seed=7, exhaust=0.7, intake=0.0, vib=0.0):
    def wg(d, a, b):
        return f"(chamber0:(samples:(delay:{d},),),chamber1:(samples:(delay:{d},),),alpha:{a},beta:{b},)"
    cyls = []
    for i, c in enumerate(CRANK):
        d = p["ex_delay"] * (1 + p["ex_spread"] * ((i * 7) % 10 / 9 - 0.5))
        cyls.append(f"(crank_offset:{c},exhaust_waveguide:{wg(d, 0.92, p['ex_beta'])},intake_waveguide:{wg(0.0012, 0.8, -0.3)},"
                    f"extractor_waveguide:{wg(p['extr_delay'], 0, p['extr_beta'])},intake_open_refl:0.012,intake_closed_refl:0.80,"
                    f"exhaust_open_refl:-0.011,exhaust_closed_refl:{p['ex_closed']},piston_motion_factor:{p['piston']},"
                    f"ignition_factor:{p['ign']},ignition_time:{p['ign_time']},)")
    return (f"(rpm:{rpm},intake_volume:{intake},exhaust_volume:{exhaust},engine_vibrations_volume:{vib},cylinders:[{','.join(cyls)}],"
            f"intake_noise_factor:0.15,intake_noise_lp:(delay:0.0013,),engine_vibration_filter:(delay:0.00026,),"
            f"muffler:(straight_pipe:{wg(p['pipe_delay'], p['pipe_alpha'], p['pipe_beta'])},muffler_elements:"
            f"[{wg(p['muf1'], 0, p['muf_beta'])},{wg(p['muf2'], 0, p['muf_beta'])}],),intake_valve_shift:0.018,"
            f"exhaust_valve_shift:{p['ex_shift']},crankshaft_fluctuation:{p['fluct']},crankshaft_fluctuation_lp:(delay:0.04,),"
            f"combustion_variation:{p['var']},exhaust_noise_factor:{p['noise']},seed:{seed},)")


def features(x, rpm, cyl=10):
    import recompose as rc
    f, P = welch(x, SR, nperseg=8192)
    env = np.array([10 * np.log10(P[(f >= b * 2 ** (-1 / 12)) & (f < b * 2 ** (1 / 12))].mean() + 1e-20) for b in BANDS])
    lb = np.log2(BANDS)
    env -= np.polyval(np.polyfit(lb, env, 1), lb)  # mic / distance tilt is not the engine's: fit the shape
    F = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    fr = np.fft.rfftfreq(len(x), 1 / SR)
    f0 = rc.firing(rpm, cyl)
    d = np.abs(fr / f0 - np.round(fr / f0))
    hnr = []
    for o in OCT:
        b = (fr >= o / 1.414) & (fr < o * 1.414)
        hnr.append(10 * np.log10(F[b & (d < 0.06)].mean() / (F[b & (d > 0.3)].mean() + 1e-30)))
    return env, np.array(hnr)


def distance(fa, fb):
    return float(np.sqrt(np.mean((fa[0] - fb[0]) ** 2)) + 0.5 * np.sqrt(np.mean((fa[1] - fb[1]) ** 2)))


def sample(rng, around=None, scale=1.0):
    p = {}
    for k, (lo, hi, lg) in SPACE.items():
        a, b = (np.log(lo), np.log(hi)) if lg else (lo, hi)
        if around is None:
            v = rng.uniform(a, b)
        else:
            c = np.log(around[k]) if lg else around[k]
            v = np.clip(c + rng.normal(0, 0.15 * scale * (b - a)), a, b)
        p[k] = float(np.exp(v) if lg else v)
    return p


def render(cands, rpm, work):
    os.makedirs(work, exist_ok=True)
    sh = []
    for i, p in enumerate(cands):
        open(os.path.join(work, f"c{i}.esc"), "w").write(ron(p, rpm))
        sh.append(f"/b/es -h -c /w/c{i}.esc -r {rpm} -l 2.5 -w 1.0 -v 1 -o /w/c{i}.wav >/dev/null 2>&1 &\n"
                  f"while [ $(jobs -r | wc -l) -ge 12 ]; do sleep 0.1; done")
    open(os.path.join(work, "run.sh"), "w", newline="\n").write("\n".join(sh) + "\nwait\n")
    for i in range(len(cands)):
        if os.path.exists(os.path.join(work, f"c{i}.wav")):
            os.remove(os.path.join(work, f"c{i}.wav"))
    subprocess.run(["docker", "run", "--rm", "-v", work.replace("\\", "/") + ":/w", "-v", os.path.join(HERE, "enginesound_mt.linux").replace("\\", "/") + ":/b/es",
                    "rust:1", "bash", "/w/run.sh"], check=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
    out = []
    for i in range(len(cands)):
        w = os.path.join(work, f"c{i}.wav")
        if not os.path.exists(w):
            out.append(None)
            continue
        x = wavfile.read(w)[1].astype(float)
        x = x.mean(1) if x.ndim > 1 else x
        out.append(x if np.isfinite(x).all() and np.abs(x).max() > 0 else None)
    return out


def fit(name, clip, start, rounds=8, rpm=None):
    import recompose as rc
    x = rc.read(clip)
    g = x[int(start * SR):int((start + 2.5) * SR)]
    t, r, _ = rc.track(g, 10, 500, 1600)  # same window as idle_loop: 600-1600 locks onto 3/2 of a 970 idle
    rpm = rpm or float(rc.firing(np.median(r), 10) * rc.refine(g, rc.firing(np.median(r), 10)) * 60 * 2 / 10)
    target = features(g, rpm)
    work = os.path.join(HERE, "fit", name)
    rng = np.random.default_rng(1)
    pop = [sample(rng) for _ in range(192)]
    best = []
    for rnd in range(rounds + 1):
        waves = render(pop, round(rpm), work)
        scored = sorted(((distance(features(w, rpm), target), i) for i, w in enumerate(waves) if w is not None))
        best = sorted(best + [(s, pop[i]) for s, i in scored[:8]], key=lambda b: b[0])[:8]
        print(f"round {rnd}: best {best[0][0]:.2f} (of {len(scored)} rendered)", flush=True)
        if rnd < rounds:
            scale = 0.6 ** rnd
            pop = [best[j % len(best)][1] for j in range(4)] + [sample(rng, best[j % len(best)][1], scale) for j in range(188)]
    s, p = best[0]
    fe = features(render([p], round(rpm), work)[0], rpm)
    json.dump({"rpm": rpm, "clip": os.path.basename(clip), "start": start, "distance": s, "params": p,
               "env_err_db": float(np.sqrt(np.mean((fe[0] - target[0]) ** 2))),
               "hnr_real": target[1].round(1).tolist(), "hnr_fit": fe[1].round(1).tolist()}, open(os.path.join(work, "best.json"), "w"), indent=1)
    open(os.path.join(work, "best.esc"), "w").write(ron(p, round(rpm)))
    print(json.dumps(json.load(open(os.path.join(work, "best.json"))), indent=1))


def demo():
    rng = np.random.default_rng(0)
    p = sample(rng)
    s = ron(p, 1000)
    assert s.count("crank_offset") == 10 and s.count("(") == s.count(")"), "RON shape"
    q = sample(rng, p, 0.0)
    assert all(abs(q[k] - p[k]) < 1e-9 * max(1, abs(p[k])) for k in p)
    t = np.arange(SR * 2) / SR
    x = sum(np.sin(2 * np.pi * 83 * h * t) / h for h in range(1, 40)) + 0.01 * rng.standard_normal(len(t))
    fa = features(x, 1000)
    assert distance(fa, fa) == 0 and fa[1][0] > 20, fa[1]
    print("demo ok")


if __name__ == "__main__":
    if sys.argv[1] == "demo":
        demo()
    else:
        fit(sys.argv[2], sys.argv[3], float(sys.argv[4]), *(int(v) for v in sys.argv[5:6]), *(float(v) for v in sys.argv[6:7]))
