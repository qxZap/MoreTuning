# Rendered layers (layers.py, 32-bit float) -> 16-bit PCM WAVs for the editor import, one folder per engine:
# MT_<engine>_<rpm>rpm_Engine.wav and MT_<engine>_<rpm>rpm_Exhaust.wav, the pairs an MTEngineSoundDataAsset
# plays per rpm step. Names end in "_Engine"/"_Exhaust", not digits, so no FName number suffix.
# Loudness: every step is set so its two layers summed hit the vanilla level for that class and rpm band
# (loudness.target: idle/mid/high LUFS of vanilla's own EngineSoundData waves, MidDuty_02/03 for diesels,
# V6Sport_02..04 for petrol, interpolated across the engine's rpm span, never falling with rpm). Both layers of
# a step get the same gain, so their synthesised balance is kept. Writes levels.json for COOKED.md.
import os, sys, glob, re, json, zlib, numpy as np
from scipy.io import wavfile
HERE = os.path.dirname(os.path.abspath(__file__))
FE = os.path.dirname(HERE)
sys.path.insert(0, FE)
from iconic import ICONIC
from diesels import DIESELS
from engines import ENGINES

OUT = r"D:\MT\SoundCook\wav"
PEAK = 10 ** (-1 / 20)
SOURCES = [  # (folder, engines, two loads?)
    ("iconic/anchors", ["rs3five", "s65", "voodoo", "cgtv10", "sbc350", "hemi426", "4age", "4g63t", "series60",
                        "cat3406e", "macke9", "om502", "8v92", "cummins67", "ps60"], True),
    ("diesel/anchors", ["ntc400", "isx15", "c16", "macke6", "mp8", "6ct", "12v", "vp44", "dd671", "dd871", "dd1271",
                        "dd1671"], True),
    ("anchors", ["type1"], False),
]


def top(name):
    return (ICONIC.get(name) or DIESELS.get(name) or {"top": ENGINES[name][2]})["top"]


def softlimit(v, knee=10 ** (-6 / 20)):
    """Leaves everything under the knee alone and bends what is above it smoothly under PEAK."""
    a = np.abs(v)
    over = a > knee
    out = v.copy()
    out[over] = np.sign(v[over]) * (knee + (PEAK - knee) * np.tanh((a[over] - knee) / (PEAK - knee)))
    return out


def engine_class(name):
    d = ICONIC.get(name)
    return "petrol" if (d["petrol"] if d else name in ENGINES) else "diesel"


def engine_layers(folder, name, loads):
    """{rpm: (engine, exhaust)} as rendered."""
    from layers import steps
    out = {}
    for k in steps(folder, name, loads):
        e, x = (wavfile.read(os.path.join(FE, "layers", "anchors", f"{name}_{k}_{l}.wav"))[1].astype(float)
                for l in ("engine", "exhaust"))
        n = min(len(e), len(x))
        out[k] = (e[:n], x[:n])
    return out


def deburr(name, k, e, x, cyl):
    """Firing turbulence on both layers (buzz.turbulence) at 0.3x, then raised on whichever layer still shows
    overtones more than buzz.LIMIT dB over the noise between them (the pair is checked too).
    Returns (e, x, worst ratio, (engine mix, exhaust mix))."""
    from buzz import turbulence, overtone_ratio, firing_hz, LIMIT
    f0 = firing_hz(name, k, cyl)
    MIXES = (0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2)
    for floor in MIXES:  # a pair that still buzzes raises both layers' starting mix
        out, mixes = [], []
        for li, v in enumerate((e, x)):
            for mix in [m for m in MIXES if m >= floor]:
                rng = np.random.default_rng(zlib.crc32(f"{name}_{k}_{li}".encode()))  # same noise every run
                w = turbulence(v, f0, rng, mix)
                if overtone_ratio(w, f0) <= LIMIT:
                    break
            out.append(w)
            mixes.append(mix)
        worst = max(overtone_ratio(v, f0) for v in (out[0], out[1], out[0] + out[1]))
        if worst <= LIMIT:
            break
    return out[0], out[1], worst, tuple(mixes)


def main():
    from loudness import lufs, target, band_targets
    bands = band_targets()
    total, levels, buzzing = 0, {}, []
    old = json.load(open(os.path.join(HERE, "levels.json")))["engines"] if os.path.exists(os.path.join(HERE, "levels.json")) else {}
    recorded = {n: v for n, v in old.items() if v.get("source") == "recording"}  # recompose.py owns those wavs
    for folder, names, loads in SOURCES:
        for name in names:
            if name in recorded:
                levels[name] = recorded[name]
                continue
            lp = engine_layers(folder, name, loads)
            assert lp, f"no layers for {name}"
            cls, ks = engine_class(name), sorted(lp)
            d = os.path.join(OUT, f"MT_{name}")
            os.makedirs(d, exist_ok=True)
            for f in glob.glob(os.path.join(d, "*.wav")):
                os.remove(f)
            rows = []
            cyl = open(os.path.join(FE, "layers", "cfg", f"{name}_engine.esc")).read().count("crank_offset:")
            for k in ks:
                e, x, buzz_db, mix = deburr(name, k, *lp[k], cyl)
                want = target(cls, (k - ks[0]) / (ks[-1] - ks[0]), bands)
                g = 10 ** ((want - lufs(e + x, 48000)) / 20)
                e, x = e * g, x * g
                if max(np.abs(e).max(), np.abs(x).max()) > PEAK:  # spiky top steps: soft-limit the peaks, then make up
                    for _ in range(6):
                        e, x = softlimit(e), softlimit(x)
                        m = 10 ** ((want - lufs(e + x, 48000)) / 20)
                        if abs(20 * np.log10(m)) < 0.05:
                            break
                        e, x = e * m, x * m
                    e, x = softlimit(e), softlimit(x)
                peak = max(np.abs(e).max(), np.abs(x).max())  # each file must not clip; the game sums them in float
                for layer, v in (("Engine", e), ("Exhaust", x)):
                    wavfile.write(os.path.join(d, f"MT_{name}_{k}rpm_{layer}.wav"), 48000,
                                  np.round(v * 32767).astype(np.int16))
                rows.append([k, round(want, 2), round(lufs(e + x, 48000), 2), round(20 * np.log10(peak), 2), round(buzz_db, 1), mix])
            levels[name] = {"class": cls, "cylinders": cyl, "steps": rows}
            buzzing += [f"{name} {r[0]}: {r[4]:+.1f} dB (mix {r[5]})" for r in rows if r[4] > 4.0]
            total += 2 * len(lp)
            print(f"{name} ({cls}): {len(lp)} steps, {rows[0][2]:.1f} .. {rows[-1][2]:.1f} LUFS, worst miss {max(r[1] - r[2] for r in rows):.1f} dB, buzz max {max(r[4] for r in rows):+.1f} dB")
    json.dump({"bands": bands, "engines": levels}, open(os.path.join(HERE, "levels.json"), "w"), indent=1)
    print("total", total)
    if buzzing:
        sys.exit("still buzzing: " + "; ".join(buzzing))


if __name__ == "__main__":
    main()
