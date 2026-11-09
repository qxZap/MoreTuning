# Engine sound steps from an Assetto Corsa car mod's FMOD bank, or from an ETS2/ATS engine sound mod (SCS layout:
# exhaust_NNN / engine_NNN / intake_NNN per rpm, NNN = 010 for 1000, 070 for 700; banks stored raw in the .scs) (vgmstream extracts its FSB5 streams), replacing an
# engine-sim set's steps (2026-11-09: engine-sim's RS3 and diesels still buzzed at mid rpm in game).
#   python -I ac_import.py <engine>            uses SETS[engine]: bank, {rpm: stream name}, steps kept from engine-sim
# AC samples are named by the rpm they play at unpitched and are palindromes (forward + reversed, last sample = first),
# so a loop is the stream minus its last sample. Exhaust layer = the sample (mono, 48 kHz), Engine layer silent like
# the engine-sim sets; each step levelled to the set's existing curve (levels.json "curve"), then cook as COOKED.md.
import os, sys, json, subprocess, tempfile, numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "recompose")]
import synthloop as sl
VG = r"D:\MT\Output\.data\vgmstream-cli.exe"
AC = r"D:\SteamLibrary\steamapps\common\assettocorsa\content\cars"
SR = 48000
SETS = {
    # Ceky's TT RS 2020 (same 2.5 TFSI five as the RS3). The bank holds two recording sessions ("STM RS3_*" and
    # "rs35_*"); alternating them was heard as every rpm band having its own tone (2026-11-09): rs35 only
    "rs3five": dict(bank=r"cky_audi_ttrs_performance_gapplebees\sfx\cky_audi_ttrs_performance_gapplebees.bank",
                    steps={3000: "rs35_3000", 4000: "rs35_4000", 6000: "rs35_6000", 8000: "rs35_8000"},
                    keep=[850]),
}


# ETS2/ATS engine sound mods by zeemods (E:\Digi\Moduri ETS\zee): real recordings of the same engines as our trucks
ZEE = r"E:\Digi\Moduri ETS\zee"
SCS = {"cat3406e": "zeemod.c3406e_v1.1.1.scs", "c16": "zeemods.c16_v1.2.scs", "8v92": "zeemods.detroit_8v92_v1.0.scs",
       "ntc400": "zeemods.cummins.bigcam_v1.1.scs"}
MAX_LOOP = 8.0  # s: longer recordings are cut here and looped with a crossfade (the C16's run 30-50 s at 192 kHz)


def carve(mod, out):
    """FSB5 banks stored uncompressed in a mod archive (zeemods zero the zip's local headers): cut out by their own
    header sizes. -> paths"""
    import struct
    b, paths = open(mod, "rb").read(), []
    i = b.find(b"FSB5")
    while i != -1:
        ver, ns, sh, nt, ds = struct.unpack("<5I", b[i + 4:i + 24])
        size = (60 if ver == 1 else 64) + sh + nt + ds
        if 0 < size <= len(b) - i:
            paths.append(os.path.join(out, f"bank{len(paths)}.fsb"))
            open(paths[-1], "wb").write(b[i:i + size])
        i = b.find(b"FSB5", i + 4)
    return paths


def rpm_of(nnn):
    v = int(nnn)
    return v * 100 if v <= 30 else v * 10


def loop_cut(x, sr):
    """Mono 48 kHz loop of at most MAX_LOOP s: a longer one is cut and its tail crossfaded (equal power, 80 ms) into
    its head, so it wraps seamlessly; a shorter one is used whole (the mod's own loop)."""
    x = resample_poly(np.r_[x, x, x], SR, sr)[len(x) * SR // sr:2 * len(x) * SR // sr] if sr != SR else x
    n = int(MAX_LOOP * SR)
    if len(x) <= n:  # the mod's own loop: its wrap crossfaded over 20 ms anyway (ntc400 1500 jumped 1.9x at it)
        c = int(0.02 * SR)
        y = x[c:].copy()
        r = np.linspace(0, np.pi / 2, c)
        y[-c:] = x[-c:] * np.cos(r) + x[:c] * np.sin(r)
        return y
    c = int(0.08 * SR)
    y = x[:n].copy()
    r = np.linspace(0, np.pi / 2, c)
    y[:c] = x[n:n + c] * np.cos(r) + x[:c] * np.sin(r)
    return y


def scs(key):
    import re, es_steps
    d = es_steps.engine_spec(key)
    lv = json.load(open(sl.LEVELS))
    e = lv["engines"][key]
    c = e["curve"]
    curve = lambda k: float(np.interp(k, c[0], c[1]))
    folder = os.path.join(sl.OUT, f"MT_{key}")
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))
    with tempfile.TemporaryDirectory() as t:
        got = {}  # (layer, rpm) -> (bank, index), first bank wins
        for bank in carve(os.path.join(ZEE, SCS[key]), t):
            for name, i in streams(bank).items():
                m = re.fullmatch(r"(exhaust|engine|intake)_(\d{3})", name)
                if m:
                    got.setdefault((m.group(1), rpm_of(m.group(2))), (bank, i))
        ks = sorted(k for (l, k) in got if l == "exhaust" and ("engine", k) in got and d["idle"] - 150 <= k <= d["top"] + 300)
        rows = []
        for k in ks:
            def load(layer):
                b, i = got[(layer, k)]
                p = os.path.join(t, "s.wav")
                subprocess.run([VG, "-s", str(i), "-i", "-o", p, b], capture_output=True, check=True)
                sr, x = wavfile.read(p)
                x = x.astype(float) / 32768
                return (x.mean(1) if x.ndim > 1 else x), sr
            ex, sr = load("exhaust")
            ex = loop_cut(ex, sr)
            en, sr2 = load("engine")
            en = loop_cut(en, sr2)
            if ("intake", k) in got:
                it = loop_cut(*load("intake"))
                if len(it) == len(en):  # recorded together (same length once at 48 kHz): one layer
                    en = en + it
            # the layers loop at their own lengths, so they are limited apart and the pair is their energy sum
            both = lambda x2, e2: 10 * np.log10(10 ** (sl.lufs(x2) / 10) + 10 ** (sl.lufs(e2) / 10))
            g = 1.0
            for _ in range(8):
                x2, e2 = sl.limit([ex * g])[0], sl.limit([en * g])[0]
                g *= 10 ** ((curve(k) - both(x2, e2)) / 20)
            for layer, w in (("Exhaust", x2), ("Engine", e2)):
                wavfile.write(os.path.join(folder, f"MT_{key}_{k}rpm_{layer}.wav"), SR, (w * 32767).astype(np.int16))
            pair = both(x2, e2)
            n = min(len(x2), len(e2))  # row[1] is what loudness.verify checks: the layers summed over the shorter one
            rows.append([k, round(sl.lufs(x2[:n] + e2[:n]), 2), round(sl.lufs(x2), 2), round(sl.lufs(e2), 2), 0.0, len(x2) / SR])
            print(f"  {k} rpm: exhaust {len(x2) / SR:.1f} s {sl.lufs(x2):.1f}, engine {len(e2) / SR:.1f} s {sl.lufs(e2):.1f}, pair {pair:.2f} (target {curve(k):.2f})")
    e.update(steps=rows, pitch=1.0, source="scs-mod", method="scs-mod", mod=SCS[key], engine_layer="recorded",
             crossfade=min(b - a for a, b in zip(ks, ks[1:])) // 2)
    json.dump(lv, open(sl.LEVELS, "w"), indent=1)


# American Truck Simulator's own trucks (banks cut out of the DLC .scs by D:\MT\scs_x\scs_banks.py): rpm-named samples,
# a main family -> Exhaust layer and a second one -> Engine layer (the nearest rpm, pitched to the step, within 25 %)
ATS = r"D:\MT\scs_x\ats"
GAME = {
    "mp8": dict(fsb=r"dlc_mack_pinnacle\0.fsb", main=r"mack_2-t00\d_(\d{4})(?:_load)?", second=r"mack_2-t006_exhaust_track_mono_exhaust_(\d{4})"),
    "isx15": dict(fsb=r"dlc_peterbilt_389\0.fsb", main=r"load_(\d{4})", second=r"exhaust_(\d{4})"),
    "series60": dict(fsb=r"dlc_freightliner_cascadia2019\0.fsb", main=r"cascadia_exhaust_(\d{4})", second=r"cascadia_dd15_unloaded_(\d{4})",
                     idle=("cascadia_exhaust_idle", 600)),
}


def game(key):
    import re
    from scipy.signal import resample
    s = GAME[key]
    bank = os.path.join(ATS, s["fsb"])
    ids = streams(bank)
    fam = {f: {int(m.group(1)): i for n, i in ids.items() if (m := re.fullmatch(s[f], n))} for f in ("main", "second")}
    if "idle" in s:  # an idle loop named without its rpm
        fam["main"][s["idle"][1]] = ids[s["idle"][0]]
    lv = json.load(open(sl.LEVELS))
    e = lv["engines"][key]
    c = e["curve"]
    curve = lambda k: float(np.interp(k, c[0], c[1]))
    folder = os.path.join(sl.OUT, f"MT_{key}")
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))
    both = lambda x2, e2: 10 * np.log10(10 ** (sl.lufs(x2) / 10) + (10 ** (sl.lufs(e2) / 10) if e2.any() else 0))
    rows = []
    with tempfile.TemporaryDirectory() as t:
        def load(i):
            p = os.path.join(t, "s.wav")
            subprocess.run([VG, "-s", str(i), "-i", "-o", p, bank], capture_output=True, check=True)
            sr, x = wavfile.read(p)
            x = x.astype(float) / 32768
            return loop_cut(x.mean(1) if x.ndim > 1 else x, sr)
        for k in sorted(fam["main"]):
            ex = load(fam["main"][k])
            j = min(fam["second"], key=lambda r: abs(r - k), default=None)
            en = np.zeros(len(ex))
            if j is not None and abs(j / k - 1) <= 0.25:
                y = load(fam["second"][j])
                en = resample(y, int(round(len(y) * j / k)))  # whole-loop (circular) resample: the seam stays
            g = 1.0
            for _ in range(8):
                x2 = sl.limit([ex * g])[0]
                e2 = sl.limit([en * g])[0] if en.any() else en
                g *= 10 ** ((curve(k) - both(x2, e2)) / 20)
            for layer, w in (("Exhaust", x2), ("Engine", e2)):
                wavfile.write(os.path.join(folder, f"MT_{key}_{k}rpm_{layer}.wav"), SR, (w * 32767).astype(np.int16))
            n = min(len(x2), len(e2))
            rows.append([k, round(sl.lufs(x2[:n] + e2[:n]), 2), round(sl.lufs(x2), 2), round(sl.lufs(e2), 2) if e2.any() else None, 0.0, len(x2) / SR])
            print(f"  {k} rpm: main {len(x2) / SR:.1f} s, second {'from %d' % j if e2.any() else 'none'}, pair {both(x2, e2):.2f} (target {curve(k):.2f})")
    ks = [r[0] for r in rows]
    e.update(steps=rows, pitch=1.0, source="scs-mod", method="ats", bank=s["fsb"], engine_layer="recorded",
             crossfade=min(b - a for a, b in zip(ks, ks[1:])) // 2)
    json.dump(lv, open(sl.LEVELS, "w"), indent=1)


def relevel(key, old_levels):
    """A set rebuilt by recompose.py (real recordings, its own older targets) brought back to the loudness curve the
    engine had before (old_levels: a saved levels.json), both layers by one gain, then limited."""
    old = json.load(open(old_levels))["engines"][key]
    c = old["curve"]
    curve = lambda k: float(np.interp(k, c[0], c[1]))
    lv = json.load(open(sl.LEVELS))
    e = lv["engines"][key]
    folder = os.path.join(sl.OUT, f"MT_{key}")
    for r in e["steps"]:
        k = r[0]
        rd = lambda l: wavfile.read(os.path.join(folder, f"MT_{key}_{k}rpm_{l}.wav"))[1].astype(float) / 32768
        x, en = rd("Exhaust"), rd("Engine")
        g = 1.0
        for _ in range(8):
            x2, e2 = sl.limit([x * g, en * g])
            g *= 10 ** ((curve(k) - sl.lufs(x2 + e2)) / 20)
        for l, w in (("Exhaust", x2), ("Engine", e2)):
            wavfile.write(os.path.join(folder, f"MT_{key}_{k}rpm_{l}.wav"), SR, (w * 32767).astype(np.int16))
        r[1] = r[2] = round(sl.lufs(x2 + e2), 2)
        print(f"  {k} rpm: pair {r[1]:.2f} (target {curve(k):.2f})")
    e["curve"] = c
    for f in ("starter", "volumes", "idle_exhaust_ratio", "loudness_db"):  # recompose rewrites the whole entry: the
        if f in old:                                                       # approved starter and the in-game volumes
            e[f] = old[f]
    ks = [r[0] for r in e["steps"]]
    e["crossfade"] = min(b - a for a, b in zip(ks, ks[1:])) // 2  # blend near each midpoint, like the other sets
    json.dump(lv, open(sl.LEVELS, "w"), indent=1)


def streams(bank):
    out = subprocess.run([VG, "-m", bank], capture_output=True, text=True).stdout
    n = int(next(l.split(":")[1] for l in out.splitlines() if l.startswith("stream count")))
    names = {}
    for i in range(1, n + 1):
        m = subprocess.run([VG, "-m", "-s", str(i), bank], capture_output=True, text=True).stdout
        names[next(l.split(": ", 1)[1].strip() for l in m.splitlines() if l.startswith("stream name"))] = i
    return names


def extract(bank, i):
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "s.wav")
        subprocess.run([VG, "-s", str(i), "-i", "-o", p, bank], capture_output=True, check=True)
        assert os.path.exists(p), (bank, i)
        sr, x = wavfile.read(p)
    x = x.astype(float) / 32768
    x = x.mean(1) if x.ndim > 1 else x
    assert x[0] == x[-1] or abs(x[0] - x[-1]) < 1e-3, "not a palindrome loop"
    x = x[:-1]
    return resample_poly(np.r_[x, x, x], SR, sr)[len(x) * SR // sr:2 * len(x) * SR // sr]  # circular: seam kept


def main(key):
    s = SETS[key]
    bank = os.path.join(AC, s["bank"])
    ids = streams(bank)
    folder = os.path.join(sl.OUT, f"MT_{key}")
    lv = json.load(open(sl.LEVELS))
    e = lv["engines"][key]
    c = e["curve"]
    curve = lambda k: float(np.interp(k, c[0], c[1]))
    rows = [r for r in e["steps"] if r[0] in s["keep"]]
    for f in os.listdir(folder):
        k = int(f.split("_")[-2][:-3])
        if k not in s["keep"]:
            os.remove(os.path.join(folder, f))
    for k, name in sorted(s["steps"].items()):
        x = extract(bank, ids[name])
        g = 1.0
        for _ in range(6):
            y = sl.limit([x * g])[0]
            g *= 10 ** ((curve(k) - sl.lufs(y)) / 20)
        wavfile.write(os.path.join(folder, f"MT_{key}_{k}rpm_Exhaust.wav"), SR, (y * 32767).astype(np.int16))
        wavfile.write(os.path.join(folder, f"MT_{key}_{k}rpm_Engine.wav"), SR, np.zeros(len(y), np.int16))
        rows.append([k, round(sl.lufs(y), 2), round(sl.lufs(y), 2), None, 0.0, len(y) / SR])
        print(f"  {k} rpm <- {name}: {len(y) / SR:.2f} s, {sl.lufs(y):.2f} LUFS (target {curve(k):.2f})")
    import es_steps  # one tone across the set: the kept idle EQ'd to the first sample, the middle steps evened
    print("  idle matched (dB at 1/3/6 kHz):", es_steps.match_idle(folder, key, min(s["keep"])))
    print("  tone evened (max dB):", es_steps.even_tone(folder, key, min(s["keep"])))
    e.update(steps=sorted(rows), pitch=1.0, source="ac-bank", method="ac-bank", bank=s["bank"],
             crossfade=min(b - a for a, b in zip(sorted(r[0] for r in rows), sorted(r[0] for r in rows)[1:])) // 2)
    json.dump(lv, open(sl.LEVELS, "w"), indent=1)


if __name__ == "__main__":
    if sys.argv[1] == "relevel":
        relevel(sys.argv[2], sys.argv[3])
    else:
        (scs if sys.argv[1] in SCS else game if sys.argv[1] in GAME else main)(sys.argv[1])
