# Every set played the way the game plays it (game_audio: pitch clamp, log-rpm blend of adjacent steps, each step on
# its own clock), listening for what the user hears as "cutting up": a short drop in level. Two checks per set:
#   loops  -- each loop wrapped 4x: a dip around the wrap (the 40 ms against the loop's median level)
#   sweep  -- revs idle->top->idle at full throttle: any 40 ms window more than DIP_DB under its 600 ms median
#   blends -- each pair of neighbours held at its blend midpoint from 10 random starts: worst level against the two
#             summed incoherently (BLEND_DB; the cut the sweep only catches when the draw is unlucky)
#   python -I cook/sweep_check.py [engine ...]     (default: every enginesim set in levels.json)
#   python -I cook/sweep_check.py demo
import os, sys, glob, re, json, numpy as np
from scipy.io import wavfile
from scipy.ndimage import median_filter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), os.path.join(os.path.dirname(HERE), "recompose")]
import game_audio as ga
SR = 48000
DIP_DB = 10.0  # vanilla on this same sweep, 12 random starts: median -4.7..-8.4, worst -7.3..-9.9 dB
WIN = int(0.040 * SR)  # over a firing period even at a 6-cyl diesel's 600 rpm idle (33 ms): the gaps between
# pulses are the engine, not a cut


def env_db(y):
    n = len(y) // WIN
    r = np.sqrt(np.mean(y[:n * WIN].reshape(n, WIN) ** 2, axis=1)) + 1e-9
    return 20 * np.log10(r)


def dips(y, skip=0.3):
    """(count, worst dB, time s) of 40 ms windows more than DIP_DB under their 600 ms median."""
    e = env_db(y)
    ref = median_filter(e, size=15, mode="nearest")
    d = (e - ref)[int(skip * SR / WIN):]
    loud = ref[int(skip * SR / WIN):] > ref.max() - 30  # ignore near-silence
    bad = (d < -DIP_DB) & loud
    i = int(np.argmin(np.where(loud, d, 0)))
    return int(bad.sum()), round(float(d[i]), 1), round((i * WIN) / SR + skip, 2)


def loop_wrap(x):
    """dB of the 20 ms around the wrap against the loop's median 20 ms level (a dip or a bump at the seam)."""
    y = np.r_[x, x]
    n = WIN  # 20 ms read a 600 rpm diesel idle's gap between pulses as a -3.3 dB seam (its wrap_jump: 0.1)
    seam = np.sqrt(np.mean(y[len(x) - n // 2:len(x) + n // 2] ** 2)) + 1e-9
    k = len(x) // n
    med = np.median(np.sqrt(np.mean(x[:k * n].reshape(k, n) ** 2, axis=1))) + 1e-9
    return round(float(20 * np.log10(seam / med)), 1)


def load(folder, name):
    out = {}
    for p in glob.glob(os.path.join(folder, f"MT_{name}_*rpm_Exhaust.wav")):
        k = int(re.search(r"_(\d+)rpm_", p).group(1))
        out[k] = wavfile.read(p)[1].astype(float) / 32768
    return out


BLEND_DB = -6.0  # vanilla's recordings: worst -0.2..-4 dB


def blend_loss(loops, a, b, seeds=10, sec=1.5):
    """Worst level, over random step starts, of the two steps held at their blend midpoint against their incoherent
    sum: the game starts each step at its own point, so two alike steps can sit in antiphase for the whole crossfade."""
    rms = lambda v: np.sqrt(np.mean(v ** 2))
    r = np.full(int(sec * SR), np.sqrt(a * b))
    out = []
    for s in range(seeds):
        ya = ga.play_layer({a: loops[a]}, r, None, np.random.default_rng(s))
        yb = ga.play_layer({b: loops[b]}, r, None, np.random.default_rng(s + 999))
        out.append(20 * np.log10(rms(0.5 * ya + 0.5 * yb) / np.sqrt(0.25 * rms(ya) ** 2 + 0.25 * rms(yb) ** 2)))
    return round(float(min(out)), 1)


def check(folder, name):
    loops = load(folder, name)
    keys = sorted(loops)
    wraps = {k: loop_wrap(loops[k]) for k in keys}
    lo, hi = keys[0], keys[-1]
    t = np.arange(int(8 * SR)) / SR
    up = lo * (hi / lo) ** np.clip(t / 4, 0, 1)  # 4 s up (log), 4 s down
    rpm = np.where(t < 4, up, up[::-1])
    sweep = dips(ga.play({}, loops, rpm, np.ones_like(rpm)))
    blends = {f"{a}-{b}": blend_loss(loops, a, b) for a, b in zip(keys, keys[1:])}
    return wraps, sweep, blends


def main(names):
    if not names:
        lv = json.load(open(os.path.join(HERE, "levels.json")))["engines"]
        names = [n for n, v in lv.items() if v.get("source") == "enginesim"]
    import synthloop as sl
    bad = 0
    for n in names:
        wraps, sweep, crawl = check(os.path.join(sl.OUT, f"MT_{n}"), n)
        wb = {k: v for k, v in wraps.items() if abs(v) > 3}
        cb = {k: v for k, v in crawl.items() if v < BLEND_DB}
        flag = bool(wb or sweep[0] or cb)
        bad += flag
        print(f"{'CUT ' if flag else 'ok  '}{n:10s} sweep {sweep}  wraps>3dB {wb}  blends {cb}")
    return bad


if __name__ == "__main__":
    if sys.argv[1:] == ["demo"]:
        x = np.sin(2 * np.pi * 110 * np.arange(SR) / SR)
        assert dips(x)[0] == 0 and abs(loop_wrap(x)) < 0.5
        y = x.copy()
        y[SR // 2:SR // 2 + 2 * WIN] *= 0.2
        assert dips(y)[0] >= 1, dips(y)
        print("demo ok")
    else:
        sys.exit(1 if main(sys.argv[1:]) else 0)
