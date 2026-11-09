# Starter sound for an engine set: a cold start, the way vanilla's Starter is one (measured 2026-11-06: 0-0.8 s
# slow deep 3-6 Hz pulses at -14.6 dB = the starter turning the engine over; 0.8-2.0 s about 6 dB louder at
# 15-20 Hz = caught, running rough; tapering to 2.4 s). Rendered by es-render's start mode for this engine --
# compression chuffs through the exhaust while cranking, the catch, a modest idle-air flare -- with the starter
# motor laid over it on the same crank speed, which engine-sim does not model: solenoid thunk + pinion clack,
# gear mesh ringing fixed housing resonances, brush noise, load thump on every compression; it lets go when
# the engine has caught and spins down. One-shot, 2.4 s. MT_<engine>_Starter.wav next to the rpm steps.
#   python -I es_starter.py <engine> <script.mr> [car|truck]      python -I es_starter.py demo
import os, sys, json, subprocess, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, sosfiltfilt, lfilter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "cook")]
import es_steps
SR = 48000
LENGTH = 2.4
IGNITION = 0.8      # vanilla's catch
CRANK_DB = -6.5     # cranking (chuffs + motor) against running: vanilla's two parts are ~6 dB apart
# per class: when the starter lets go (big diesels catch slower) and the idle-air flare after the catch
TIMING = {"car": (0.95, 0.18), "pickup": (1.2, 0.08), "truck": (1.3, 0.06)}


def blip(amount):
    return [(0.0, 0.0), (0.85, 0.0), (0.9, amount), (1.1, amount), (1.2, 0.0), (9, 0.0)]
# per starter size: pinion ratio, commutator bars, housing modes (Hz), body thump (Hz), loudness
MOTORS = {
    "car": dict(ratio=11, bars=16, pinion=9, modes=(1150, 2350, 3700, 5200, 7400), thump=110, lufs=-9.5),
    "truck": dict(ratio=13, bars=12, pinion=11, modes=(780, 1600, 2600, 3900, 5600), thump=70, lufs=-9.0),
}


def render_start(script, wav, starter_off=0.95, flare=0.18):
    """engine-sim cold start for this engine: audio (48 kHz, float) and the crank log (t, rpm, starter on)."""
    from scipy.signal import resample_poly
    csv = wav + ".thr.csv"
    P = es_steps.PITCH
    open(csv, "w").write("\n".join(f"{t * P},{v}" for t, v in blip(flare)))
    r = subprocess.run([os.path.join(es_steps.ES, "Release", "es-render.exe"), f"../assets/{script}", wav, "start", csv,
                        str(LENGTH * P + 0.5), str(IGNITION * P), str(starter_off * P)], cwd=es_steps.ES, capture_output=True,
                       text=True, env=dict(os.environ, ES_JITTER=str(es_steps.JITTER)))
    assert r.returncode == 0 and os.path.exists(wav), (r.stdout, r.stderr)
    x = resample_poly(wavfile.read(wav)[1].astype(float) / 32768, 160, 147)
    return x, np.loadtxt(wav + ".rpm.csv", delimiter=",")


def resonators(x, modes, q=14.0):
    out = np.zeros_like(x)
    for i, f in enumerate(modes):
        w = 2 * np.pi * f / SR
        r = np.exp(-w / (2 * q))
        out += lfilter([1 - r], [1, -2 * r * np.cos(w), r * r], x) * (0.8 ** i)
    return out


def motor(crank, m, rng):
    """crank: crank rpm per sample (cranking, so a few hundred). Returns the motor sound, unlevelled."""
    n = len(crank)
    mot_hz = crank * m["ratio"] / 60                       # motor revolutions per second
    load = np.clip(-np.gradient(crank) * SR / 300.0, 0, None)  # crank slowing = compression = current up
    load = sosfiltfilt(butter(2, 60, fs=SR, output="sos"), load)
    load = load / (np.percentile(load, 99) + 1e-9)
    cur = 0.55 + 0.45 * np.clip(load, 0, 1.5)
    # gear mesh: tooth strikes with jittered strength, ringing the housing
    mesh_ph = np.cumsum(m["pinion"] * mot_hz) / SR
    strikes = np.zeros(n)
    idx = np.nonzero(np.diff(np.floor(mesh_ph)) > 0)[0]
    strikes[idx] = cur[idx] * rng.uniform(0.6, 1.4, len(idx))
    gear = resonators(strikes, m["modes"])
    # brushes / commutator: noise bands at the commutation rate's harmonics, following the motor speed
    comm = np.zeros(n)
    base = rng.standard_normal(n)
    fc = m["bars"] * mot_hz
    for h, a in ((1, 1.0), (2, 0.5), (3, 0.3)):
        ph = 2 * np.pi * np.cumsum(h * fc) / SR
        nb = sosfiltfilt(butter(2, 30, fs=SR, output="sos"), base * np.cos(h * 1.7) + rng.standard_normal(n) * 0.3)
        comm += a * (np.cos(ph) * nb)
    comm /= np.abs(comm).max() + 1e-9
    # body thump on each compression, and broadband motor air/brush hiss
    thump = sosfilt(butter(2, [m["thump"] * 0.6, m["thump"] * 1.6], "bp", fs=SR, output="sos"), rng.standard_normal(n)) * load
    hiss = sosfilt(butter(2, [2500, 9000], "bp", fs=SR, output="sos"), rng.standard_normal(n))
    g = gear / (np.abs(gear).max() + 1e-9)
    y = 1.0 * g + 0.45 * comm * cur + 0.5 * thump / (np.abs(thump).max() + 1e-9) + 0.06 * hiss * cur
    return y


def engage(n, m, rng):
    """Solenoid thunk then the pinion clacking into the ring gear 25 ms later."""
    y = np.zeros(n)
    k = np.arange(int(0.08 * SR))
    thunk = np.sin(2 * np.pi * m["thump"] * 0.8 * k / SR) * np.exp(-k / (0.018 * SR))
    tick = resonators(np.r_[1.0, np.zeros(len(k) - 1)], m["modes"][1:], q=30) * 6
    y[:len(k)] += thunk * 0.9 + tick * 0.5
    j = int(0.025 * SR)
    clack = resonators(rng.standard_normal(len(k)) * np.exp(-k / (0.003 * SR)), m["modes"], q=20)
    y[j:j + len(k)] += clack * 0.6
    return y


def build(x, log, m, rng):
    """Engine start (played PITCH faster, like the loops) + the starter motor on its crank speed -> 2.4 s."""
    from scipy.signal import resample
    P = es_steps.PITCH
    n = int(LENGTH * SR)
    x = resample(x, int(round(len(x) / P)))
    x = np.r_[x, np.zeros(max(0, n - len(x)))][:n]
    t = np.arange(n) / SR
    crank = np.maximum(np.interp(t * P, log[:, 0], log[:, 1]), 30.0) * P
    engaged = np.interp(t * P, log[:, 0], log[:, 2]) > 0.5
    off = int(np.argmax(~engaged)) if (~engaged).any() else n
    mot = motor(np.minimum(crank, crank[max(off - 1, 0)]) if off < n else crank, m, rng)
    # after release the motor freewheels down and the pinion drops out
    if off < n:
        mot[off:] *= np.exp(-(t[off:] - t[off]) / 0.15)
    spin = np.clip(t / 0.12, 0, 1)
    crank_part = slice(int(0.15 * SR), int(IGNITION * SR * 0.95))
    rms = lambda v: np.sqrt(np.mean(v ** 2)) + 1e-9
    e_rms, m_rms, r_rms = rms(x[crank_part]), rms(mot[crank_part]), rms(x[int(1.0 * SR):int(2.0 * SR)])
    # cranking sits CRANK_DB under running, whatever engine-sim's chuffs come out at (big diesels: next to nothing):
    # the chuffs carry at most a third of it, the motor the rest
    target = r_rms * 10 ** (CRANK_DB / 20)
    gc = min(1.0, target * 0.6 / e_rms)
    gm = np.sqrt(max(target ** 2 - (gc * e_rms) ** 2, (0.5 * target) ** 2)) / m_rms
    x = x * np.interp(t, [0, IGNITION, IGNITION + 0.1, 9], [gc, gc, 1, 1])
    y = x + mot * spin * gm + engage(n, m, rng) * target * 3
    y[-int(0.35 * SR):] *= np.cos(np.linspace(0, np.pi / 2, int(0.35 * SR))) ** 2
    y[:int(0.002 * SR)] *= np.linspace(0, 1, int(0.002 * SR))
    return y, crank


def level(y, lufs):
    import synthloop as sl
    g = 1.0
    for _ in range(6):
        z = sl.limit([y * g])[0]
        g *= 10 ** ((lufs - sl.lufs(z)) / 20)
    return z


def main(name, script, kind="car"):
    import synthloop as sl
    m = MOTORS[kind]
    work = os.path.join(HERE, "es2", name)
    os.makedirs(work, exist_ok=True)
    off, flare = TIMING[es_steps.engine_spec(name)["kind"]]
    x, log = render_start(script, os.path.join(work, "start.wav"), off, flare)
    ran = log[log[:, 0] > (IGNITION + 0.5) * es_steps.PITCH, 1]
    idle = es_steps.engine_spec(name)["idle"]
    assert ran.size and ran.max() > 0.7 * idle, f"engine did not catch: {ran.max() if ran.size else 0:.0f} rpm after ignition"
    y, crank = build(x, log, m, np.random.default_rng(7))
    z = level(y, m["lufs"])
    out = os.path.join(sl.OUT, f"MT_{name}", f"MT_{name}_Starter.wav")
    wavfile.write(out, SR, (z * 32767).astype(np.int16))
    seg = lambda a, b: 20 * np.log10(np.sqrt(np.mean(z[int(a * SR):int(b * SR)] ** 2)) + 1e-9)
    pk = int(np.argmax(crank))
    print(f"{name} starter ({kind}): cranking {crank[int(0.4 * SR)]:.0f} rpm at {seg(0.1, 0.75):.1f} dB, caught and running "
          f"{seg(0.9, 2.0):.1f} dB (vanilla -14.6 / -8.5), flare {crank[pk]:.0f} rpm at {pk / SR:.2f} s, {sl.lufs(z):.1f} LUFS")
    lv = json.load(open(sl.LEVELS))
    lv["engines"][name]["starter"] = {"length": LENGTH, "kind": kind, "lufs": round(float(sl.lufs(z)), 2), "cold_start": True}
    json.dump(lv, open(sl.LEVELS, "w"), indent=1)


if __name__ == "__main__":
    if sys.argv[1] == "demo":
        rng = np.random.default_rng(1)
        n = SR
        crank = 220 + 50 * np.sin(2 * np.pi * 18 * np.arange(n) / SR)
        y = motor(crank, MOTORS["car"], rng)
        # louder where the crank slows (compression) than where it speeds up
        slow = np.gradient(crank) < 0
        env = np.abs(sosfiltfilt(butter(2, 200, fs=SR, output="sos"), np.abs(y)))
        assert env[slow].mean() > env[~slow].mean(), (env[slow].mean(), env[~slow].mean())
        e = engage(n, MOTORS["car"], rng)
        assert np.abs(e[:int(0.002 * SR)]).max() > 0 and np.abs(e[int(0.2 * SR):]).max() == 0
        print("demo ok")
    else:
        main(*sys.argv[1:4])
