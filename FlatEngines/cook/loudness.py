# Integrated loudness (ITU-R BS.1770-4, LUFS, mono) and the decoder for cooked BINKA waves.
#   python loudness.py refs      decode the vanilla/Teh engine references, print and save their LUFS
#   python loudness.py demo      self-check: K-weighting/gating against ffmpeg's ebur128 on one file
import os, sys, glob, json, re, subprocess, numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter, resample_poly
HERE = os.path.dirname(os.path.abspath(__file__))
VGM = r"D:\MT\Output\.data\vgmstream-cli.exe"  # FModel's copy
VAN = r"D:\MT\Output\Exports\MotorTown\Content\Cars\Parts\Engine\Sound"
REF_DIR = os.path.join(HERE, "work", "ref")
REF_JSON = os.path.join(HERE, "ref_lufs.json")


def kfilter_48k(x):
    # BS.1770 pre-filter + RLB high-pass, 48 kHz coefficients from the standard
    x = lfilter([1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585], x)
    return lfilter([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621], x)


def lufs(x, sr):
    if sr != 48000:
        x = resample_poly(x, 48000, sr)
    y = kfilter_48k(np.asarray(x, float))
    blk, hop = 19200, 4800  # 400 ms blocks, 75 % overlap
    ms = np.array([np.mean(y[i:i + blk] ** 2) for i in range(0, len(y) - blk + 1, hop)])
    l = -0.691 + 10 * np.log10(ms + 1e-30)
    ms = ms[l > -70]
    rel = -0.691 + 10 * np.log10(ms.mean()) - 10
    ms = ms[-0.691 + 10 * np.log10(ms) > rel]
    return -0.691 + 10 * np.log10(ms.mean())


def read(path):
    sr, x = wavfile.read(path)
    x = x.astype(float) / (32768.0 if x.dtype == np.int16 else 1.0)
    return sr, (x.mean(axis=1) if x.ndim > 1 else x)


def wrap_jump(x):
    """Step from a loop's last sample back to its first, over the 99.9th percentile of the steps inside it: above
    1 the wrap is as big as the biggest steps inside (fine); the check fails above 1.5, a click every time it loops."""
    d = np.abs(np.diff(x))
    return float(abs(x[0] - x[-1]) / (np.percentile(d, 99.9) + 1e-12)) if x.any() else 0.0


def decode(base, out):
    """Cooked SoundWave (base.uexp + base.ubulk) -> wav. The BINKA stream is the 0x1C-byte header inlined in the
    .uexp followed by the .ubulk (verified: our own cooked wave decodes back at corr 0.999, level within 0.01 dB)."""
    ue = open(base + ".uexp", "rb").read()
    r = ue.find(b"RIFF")
    if r >= 0:  # PCM: the wav header (through the data chunk's size) is in the .uexp, the samples are the .ubulk
        d = ue.find(b"data", r)
        open(out, "wb").write(ue[r:d + 8] + open(base + ".ubulk", "rb").read())
        fmt = int.from_bytes(ue[ue.find(b"fmt ", r) + 8:ue.find(b"fmt ", r) + 10], "little")
        if fmt != 1:  # ADPCM and friends share the layout: let vgmstream decode the assembled wav
            tmp = out + ".adpcm.wav"
            os.replace(out, tmp)
            subprocess.run([VGM, "-o", out, tmp], check=True, capture_output=True)
            os.remove(tmp)
        return read(out)
    i = ue.find(b"ABEU")
    assert i >= 0, base
    tmp = out + ".ueba"
    open(tmp, "wb").write(ue[i:i + 0x1C] + open(base + ".ubulk", "rb").read())
    subprocess.run([VGM, "-o", out, tmp], check=True, capture_output=True)
    os.remove(tmp)
    return read(out)


def refs():
    res = {}
    sets = sorted(glob.glob(os.path.join(VAN, "Truck", "MidDuty_*")) + glob.glob(os.path.join(VAN, "V6Sport", "V6Sport_*")))
    for d in sets:
        for b in sorted(glob.glob(os.path.join(d, "*rpm_*.ubulk"))):
            base = b[:-6]
            m = re.match(r"(\d+)rpm_(Engine|Exhaust)", os.path.basename(base))
            sr, x = decode(base, os.path.join(REF_DIR, f"{os.path.basename(d)}_{os.path.basename(base)}.wav"))
            res.setdefault(os.path.basename(d), []).append([int(m.group(1)), m.group(2), round(lufs(x, sr), 2)])
    # cue-based vanilla loops and Teh's sources, for the record (their cues add volume modulators on top)
    for name in ["V8/Chevy_V8_hot_rod_car_-_short_looping_sound_of_hot_rod_engine_-_idling_and_turnover",
                 "V8/Chevy_V8_hot_rod_car_-_short_looping_sound_of_hot_rod_engine_-_low_speed_-_loop",
                 "V8/Chevy_V8_hot_rod_car_-_short_looping_sound_of_hot_rod_engine_-_high_speed_-_loop",
                 "I4Sport/482826-Mazda_Miata_MX5_NBFL_1_0k", "I4Sport/482874-Mazda_Miata_MX5_NBFL_1_6k",
                 "v12/Ferrari_275_V12_Idle", "v12/Ferrari_275_V12_High",
                 "Truck/Truck_04_Idle", "Truck/Truck_04_Mid", "Truck/Truck_04_High", "Truck/Truck_05_Idle", "Truck/Truck_05_High"]:
        sr, x = decode(os.path.join(VAN, name), os.path.join(REF_DIR, os.path.basename(name) + ".wav"))
        res.setdefault("cue_loops", []).append([name, round(lufs(x, sr), 2)])
    for p in glob.glob(r"D:\MT\MoreTuning\Z_TehsEngineSoundPack_P\MotorTown\Content\Cars\Parts\Engine\Sound\*\*.wav") + \
             glob.glob(r"D:\MT\MoreTuning\SoundTools\out\*.wav"):
        sr, x = read(p)
        res.setdefault("source_wavs", []).append([os.path.relpath(p, r"D:\MT\MoreTuning"), round(lufs(x, sr), 2)])
    json.dump(res, open(REF_JSON, "w"), indent=1)
    for k, v in res.items():
        print(k)
        for r in v:
            print("   ", r)


def demo():
    p = glob.glob(os.path.join(REF_DIR, "MidDuty_02_2000rpm_Exhaust.wav"))[0]
    sr, x = read(p)
    ours = lufs(x, sr)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", p, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True)
    ff = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1])
    print(f"ours {ours:.2f}  ffmpeg {ff:.2f}")
    assert abs(ours - ff) < 0.3
    assert wrap_jump(np.sin(np.arange(4800) * 2 * np.pi / 48)) < 1.5  # whole periods: seamless
    assert wrap_jump(np.sin(np.arange(4812) * 2 * np.pi / 48)) > 1.5  # a quarter period over: a click
    print("wrap check ok")


def verify():
    """Decode every shipped (cooked) wave pair and check it against levels.json, within 1 dB."""
    MOD = r"D:\MT\MoreTuning\qxZap_MoreTuning_P\MotorTown\Content\Cars\Parts\Engine\Sound"
    lv = json.load(open(os.path.join(HERE, "levels.json")))["engines"]
    tmp = os.path.join(HERE, "work", "verify")
    os.makedirs(tmp, exist_ok=True)
    from buzz import overtone_ratio, firing_hz, LIMIT
    out, worst, worst_buzz, seams = {}, 0.0, -99.0, []
    for name, v in lv.items():
        rows = []
        for k, want, *_ in v["steps"]:
            e, x = (decode(os.path.join(MOD, f"MT_{name}", f"MT_{name}_{k}rpm_{l}"), os.path.join(tmp, f"{l}.wav"))[1]
                    for l in ("Engine", "Exhaust"))
            for l, w in (("Engine", e), ("Exhaust", x)):
                if (j := wrap_jump(w)) > 1.5:
                    seams.append((name, k, l, round(j, 2)))
            n = min(len(e), len(x))
            got = lufs(e[:n] + x[:n], 48000)
            worst = max(worst, abs(got - want))
            f0 = firing_hz(name, k, v["cylinders"]) * v.get("pitch", 1.0)  # es_steps sets play above their rpm
            # recorded engines: their engine layer is the exhaust low-passed at 1.2 kHz, only a filter skirt in the band
            # synthloop sets: the engine layer only ever plays under the exhaust, so the pair is what is heard
            lowpassed = v.get("source") == "recording" or v.get("engine_layer") in ("lowpass", "silent") or \
                (v.get("source") == "synth" and v.get("method") == "pingpong")
            ws = (x[:n], e[:n] + x[:n]) if lowpassed else (e[:n], x[:n], e[:n] + x[:n])
            bz = max(overtone_ratio(w, f0) for w in ws)
            if v.get("source") not in ("scs-mod", "ac-bank"):  # the limit is for synthesised sets; real recordings
                worst_buzz = max(worst_buzz, bz)               # from game mods are judged by ear (2026-11-09)
            rows.append([k, round(want, 2), round(got, 2), round(bz, 1)])
        out[name] = rows
        print(f"{name}: idle {rows[0][2]:.1f}  high {rows[-1][2]:.1f} LUFS  worst {max(abs(r[1] - r[2]) for r in rows):.2f} dB  buzz max {max(r[3] for r in rows):+.1f} dB")
    json.dump(out, open(os.path.join(HERE, "levels_cooked.json"), "w"), indent=1)
    assert not seams, f"shipped waves jump at the loop wrap: {seams}"
    assert worst < 1.0, worst
    assert worst_buzz <= LIMIT, worst_buzz
    print(f"all within {worst:.2f} dB of target, buzz max {worst_buzz:+.1f} dB")


if __name__ == "__main__":
    {"refs": refs, "demo": demo, "verify": verify}[sys.argv[1]]()


CLASSES = {"diesel": ["MidDuty_02", "MidDuty_03"], "petrol": ["V6Sport_02", "V6Sport_03", "V6Sport_04"]}
BANDS = (0.0, 0.5, 1.0)  # idle, mid, high, as a fraction of the set's own rpm span


def pair_curve(rows):
    """[(rpm, layer, lufs)] -> (rpms, combined LUFS of engine+exhaust at each rpm). A layer missing at an rpm is
    interpolated in dB along rpm; a set with no exhaust layer at all is the engine layer alone."""
    out = {}
    for layer in ("Engine", "Exhaust"):
        pts = sorted((r, l) for r, ly, l in rows if ly == layer)
        if pts:
            out[layer] = pts
    rpms = sorted({r for r, _, _ in rows})
    lev = []
    for r in rpms:
        p = sum(10 ** (np.interp(r, [a for a, _ in v], [b for _, b in v]) / 10) for v in out.values())
        lev.append(10 * np.log10(p))
    return np.array(rpms, float), np.array(lev)


def band_targets(ref=None):
    """{class: [LUFS at idle, mid, high]} averaged (in dB) over the class's vanilla EngineSoundData sets."""
    ref = ref or json.load(open(REF_JSON))
    out = {}
    for cls, sets in CLASSES.items():
        vals = []
        for s in sets:
            rp, lv = pair_curve(ref[s])
            vals.append([np.interp(rp[0] + b * (rp[-1] - rp[0]), rp, lv) for b in BANDS])
        out[cls] = list(np.maximum.accumulate(np.mean(vals, axis=0)))  # level never falls with rpm
    return out


def target(cls, frac, bands=None):
    """Target LUFS for a step at `frac` of its engine's rpm span."""
    return float(np.interp(frac, BANDS, (bands or band_targets())[cls]))
