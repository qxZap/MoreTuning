# Writes one MTEngineSoundDataAsset per engine, the game's own per-rpm engine sound (what vanilla's
# MidDuty_02/03 and V6Sport_02..04 use instead of a SoundCue): RPMSources[{RPM, EngineSound, ExhaustSound}],
# CrossfadeRPMRange, StarterMotorSound. Built from vanilla MidDuty_02/EngineSoundData as the template and
# written with UAssetGUI, then read back. Output next to the cooked waves in the mod:
#   /Game/Cars/Parts/Engine/Sound/MT_<engine>/MT_<engine>_EngineSoundData
import os, sys, json, copy, glob, re, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
UAG, MAP = r"D:\MT\UAssetGUI.exe", "MotorTown720T6"
IDLE_EXHAUST = 0.6  # engine-sim sets: exhaust at 60% of full with the throttle shut (game default 0.2), ~4.4 dB under
TEMPLATE = r"D:\MT\Output\Exports\MotorTown\Content\Cars\Parts\Engine\Sound\Truck\MidDuty_02\EngineSoundData.uasset"
MOD = r"D:\MT\MoreTuning\qxZap_MoreTuning_P\MotorTown\Content\Cars\Parts\Engine\Sound"
WAV = r"D:\MT\SoundCook\wav"
WORK = os.path.join(HERE, "work")
ROOT = "/Game/Cars/Parts/Engine/Sound"
STARTER = f"{ROOT}/Starter"


def uag(*a):
    subprocess.run([UAG, *a], check=True)


def tojson(src, dst):
    if os.path.exists(dst):
        os.remove(dst)
    uag("tojson", src, dst, "VER_UE5_4", MAP)
    assert os.path.exists(dst), f"UAssetGUI wrote nothing for {src}"  # it fails silently
    return json.load(open(dst))


def build(tpl, name, rpms, master=None, crossfade=None, idle_exhaust=None):
    d = copy.deepcopy(tpl)
    pkg_of = lambda obj: f"{ROOT}/MT_{name}/{obj}"
    asset = f"MT_{name}_EngineSoundData"
    imp = lambda obj, outer, cp, cn: {"$type": "UAssetAPI.Import, UAssetAPI", "ObjectName": obj, "OuterIndex": outer,
                                      "ClassPackage": cp, "ClassName": cn, "PackageName": None, "bImportOptional": False}
    imports = [imp("MTEngineSoundDataAsset", -3, "/Script/CoreUObject", "Class"),
               imp("Default__MTEngineSoundDataAsset", -3, "/Script/MotorTown", "MTEngineSoundDataAsset"),
               imp("/Script/MotorTown", 0, "/Script/CoreUObject", "Package")]

    def wave(pkg, obj):
        imports.append(imp(pkg, 0, "/Script/CoreUObject", "Package"))
        imports.append(imp(obj, -len(imports), "/Script/Engine", "SoundWave"))
        return -len(imports)

    # the engine's own starter (es_starter.py) when the set has one, else vanilla's generic one
    own = f"MT_{name}_Starter"
    starter = wave(pkg_of(own), own) if os.path.exists(os.path.join(WAV, f"MT_{name}", own + ".wav")) else wave(STARTER, "Starter")
    tsrc = d["Exports"][0]["Data"][0]["Value"][0]
    sources, deps = [], []
    for i, r in enumerate(rpms):
        s = copy.deepcopy(tsrc)
        s["Name"] = str(i)
        p = {x["Name"]: x for x in s["Value"]}
        p["RPM"]["Value"] = float(r)
        for layer in ("Engine", "Exhaust"):
            obj = f"MT_{name}_{r}rpm_{layer}"
            p[f"{layer}Sound"]["Value"] = wave(pkg_of(obj), obj)
            deps.append(p[f"{layer}Sound"]["Value"])
        sources.append(s)
    e = d["Exports"][0]
    props = {x["Name"]: x for x in e["Data"]}
    props["RPMSources"]["Value"] = sources
    # adjacent steps cross over each other and no further; vanilla uses 500 on 500-1000 rpm spacing
    # a set whose steps do not stay in phase in game blends audibly (engine-sim's cgtv10), so it can ask for less
    props["CrossfadeRPMRange"]["Value"] = float(crossfade or min(b - a for a, b in zip(rpms, rpms[1:])))
    props["StarterMotorSound"]["Value"] = starter
    # master: {"MasterVolume": x, "EngineVolumeMultiplier": y, "ExhaustVolumeMultiplier": z}, all unset in vanilla
    # (1.0). Floats like CrossfadeRPMRange, placed after it in schema order.
    at = e["Data"].index(props["CrossfadeRPMRange"]) + 1
    keys = [k for k in ("MasterVolume", "EngineVolumeMultiplier", "ExhaustVolumeMultiplier") if k in (master or {})]
    for i, key in enumerate(keys):
        mv = copy.deepcopy(props["CrossfadeRPMRange"])
        mv["Name"], mv["Value"] = key, float(master[key])
        e["Data"].insert(at + i, mv)
    # with the throttle shut the game plays the exhaust layer at IdleExhaustRatio of full (default 0.2, measured
    # 2026-11-07 by the SoundProbe); engine-sim sets are exhaust only, so idle sat 14 dB under the floor. Schema
    # order: after the volumes, before StarterMotorSound.
    if idle_exhaust is not None:
        r = copy.deepcopy(props["CrossfadeRPMRange"])
        r["Name"], r["Value"] = "IdleExhaustRatio", float(idle_exhaust)
        e["Data"].insert(e["Data"].index(props["StarterMotorSound"]), r)
    e["ObjectName"] = asset
    e["ClassIndex"], e["TemplateIndex"] = -1, -2
    e["CreateBeforeSerializationDependencies"] = deps + [starter]
    e["SerializationBeforeCreateDependencies"] = [-1, -2]
    d["Imports"] = imports
    d["FolderName"] = pkg_of(asset)
    names = {pkg_of(asset), asset, "/Script/CoreUObject", "/Script/Engine", "Class", "Package", "SoundWave"}
    for x in imports:
        names |= {x["ObjectName"], x["ClassPackage"], x["ClassName"]}
    d["NameMap"] = sorted(names, key=lambda s: s.encode())
    assert not [n for n in d["NameMap"] if re.search(r"_[1-9]\d*$", n)], "number-suffixed FName registered whole"
    d["Generations"][0]["NameCount"] = len(d["NameMap"])
    return d, asset


def main():
    os.makedirs(WORK, exist_ok=True)
    tpl = tojson(TEMPLATE, os.path.join(WORK, "template.json"))
    levels = json.load(open(os.path.join(HERE, "levels.json")))["engines"]
    ok = 0
    for folder in sorted(glob.glob(os.path.join(WAV, "MT_*"))):
        name = os.path.basename(folder)[3:]
        rpms = sorted({int(m.group(1)) for f in os.listdir(folder) if (m := re.match(rf"MT_{re.escape(name)}_(\d+)rpm_Engine\.wav$", f))})
        for r in rpms:  # every step must ship both cooked layers
            for layer in ("Engine", "Exhaust"):
                assert os.path.exists(os.path.join(MOD, f"MT_{name}", f"MT_{name}_{r}rpm_{layer}.uexp")), (name, r, layer)
        if os.path.exists(os.path.join(folder, f"MT_{name}_Starter.wav")):  # an own starter must have cooked too
            assert os.path.exists(os.path.join(MOD, f"MT_{name}", f"MT_{name}_Starter.uexp")), (name, "Starter")
        master = levels.get(name, {}).get("volumes")
        v = levels.get(name, {})
        d, asset = build(tpl, name, rpms, master, v.get("crossfade"),
                         v.get("idle_exhaust_ratio", IDLE_EXHAUST if v.get("source") == "enginesim" else None))
        js = os.path.join(WORK, f"{asset}.json")
        out = os.path.join(MOD, f"MT_{name}", f"{asset}.uasset")
        json.dump(d, open(js, "w"), indent=1)
        for f in (out, out[:-6] + "uexp"):
            if os.path.exists(f):
                os.remove(f)
        uag("fromjson", js, out, MAP)
        assert os.path.exists(out), f"UAssetGUI wrote nothing for {asset}"
        back = tojson(out, js[:-5] + ".readback.json")
        ex = back["Exports"][0]
        assert ex["$type"].endswith("NormalExport, UAssetAPI"), ex["$type"]
        got = {x["Name"]: x for x in ex["Data"]}
        assert len(got["RPMSources"]["Value"]) == len(rpms)
        for key, v in (master or {}).items():
            assert abs(got[key]["Value"] - v) < 1e-6, f"{key} did not read back"

        ok += 1
        print(f"{asset}: {len(rpms)} rpm steps {rpms[0]}..{rpms[-1]}, crossfade {got['CrossfadeRPMRange']['Value']:.0f}")
    print(ok, "EngineSoundData assets")


if __name__ == "__main__":
    main()
