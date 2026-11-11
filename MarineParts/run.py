"""Marine engines and gearboxes for the boats: one of each per boat, fitting that boat only.

    python MarineParts/run.py          # build the assets, then the rows
    python MarineParts/run.py demo     # self-check

The user, 2026-11-11: "a ship engine that revs very heavy and takes a lot of time to build speed... a transmission
designated purely for boats... one for the tugboat, another one for the other one"; "three gears: front, neutral,
reverse". The Boats plugin (D:/MTLiveMap/mt_loader/plugins/boats.cpp) pushes with the engine's revs, rpm/limit squared,
so the slow wind-up comes from the engine's inertia and nothing else.

Real figures, scaled like every truck diesel here (docs/ENGINES_SYNTH.md): MaxTorque 12,000 per Nm, $166.67 per hp.
  tug   Caterpillar 3512C, marine V12 58.6 L: 1,800 hp at 1,600 rpm, 8,000 Nm, ~7 t; Reintjes-type 5:1 reverse gear
  ship  MaK 8M32C, medium-speed straight-8: 5,400 hp at 600 rpm, 64,000 Nm, ~40 t; 4:1 reverse-reduction gear
Astern is the same ratio as ahead (a reversing gearbox: the user wants reverse as strong as forward).

Asset names keep "cat" out (FuelRealism reads it as an old mechanical diesel; the 3512C is electronic). Run after
Rebase/channels.py and NewEngines/synth.py, then FuelRealism/run.py and EngineTags/run.py, like synth.py. Rerunnable.
Boat row keys: Arini's Vehicles_Biceps (C0700_Tugboat, C0701_ContainerShip).
"""
import copy
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(REPO, "Rebase"))
sys.path.insert(0, os.path.join(REPO, "NewEngines"))
from pipeline import MOD, VANILLA, WORK, register_names, to_json  # noqa: E402
from rebase import fnames_in  # noqa: E402
import synth  # noqa: E402

TRANS_DIR = os.path.join(MOD, "Cars", "Parts", "Transmission")
TRANS_PKG = "/Game/Cars/Parts/Transmission/"
TRANS_REF = "allisonHT740"  # a 0.7.20-clean box (reserialized); only its gear list changes
PREFIX = synth.PREFIX

ENGINES = [
    dict(sound="dd1671", asset="Marine3512C_1800HP", name="Caterpillar 3512C Marine 1800HP", family="truck",
         ref="C18_550HP", curve="DieselTruck", hp=1800, torque=96_000_000, rpm=1600, mass=7000, inertia=400_000,
         jake=0, starter_rpm=700, boat="C0700_Tugboat"),
    dict(sound="om502", asset="MaK8M32C_5400HP", name="MaK 8M32C Marine 5400HP", family="truck",
         ref="C18_550HP", curve="DieselTruck", hp=5400, torque=768_000_000, rpm=600, mass=40000, inertia=4_000_000,
         jake=0, starter_rpm=250, boat="C0701_ContainerShip"),
]
BOXES = [
    dict(asset="MarineGear_Tug", name="Marine Reverse Gear 5:1 (Tug)", ratio=5.0, mass=2000, cost=40000, boat="C0700_Tugboat"),
    dict(asset="MarineGear_Ship", name="Marine Reverse-Reduction Gear 4:1 (Ship)", ratio=4.0, mass=8000, cost=120000,
         boat="C0701_ContainerShip"),
]


def work(name):
    os.makedirs(os.path.join(WORK, "marine"), exist_ok=True)
    return os.path.join(WORK, "marine", name)


def gears(box, ref_gears):
    """R, N, F from the reference's own R / N / 1 entries: ahead and astern the same ratio."""
    by = {g["Value"][2]["Value"]: g for g in ref_gears}
    out = []
    for i, (label, ratio) in enumerate((("R", -box["ratio"]), ("N", None), ("F", box["ratio"]))):
        g = copy.deepcopy(by["N" if label == "N" else "R" if label == "R" else "1"])
        g["Name"] = str(i)
        if ratio is not None:
            g["Value"][0]["Value"] = float(ratio)
        g["Value"][2]["Value"] = label
        out.append(g)
    return out


def make_box(box, ref):
    asset = copy.deepcopy(ref)
    synth.rename(asset, [TRANS_REF, TRANS_PKG + TRANS_REF], [box["asset"], TRANS_PKG + box["asset"]])
    for p in asset["Exports"][0]["Data"]:
        if p["Name"] == "TransmissionProperty":
            for q in p["Value"]:
                if q["Name"] == "Gears":
                    q["Value"] = gears(box, q["Value"])
                elif q["Name"] == "DefaultGearIndex":
                    q["Value"] = 1  # N
        elif p["Name"] == "DevComment":
            p["Value"] = "qxZap marine gearbox: " + box["name"]
    return asset


def name_key(row, boat):
    for p in row["Value"]:
        if p["Name"] == "VehicleKeys":
            item = {"$type": "UAssetAPI.PropertyTypes.Objects.NamePropertyData, UAssetAPI", "Name": "0", "ArrayIndex": 0,
                    "PropertyGuid": None, "IsZero": False, "PropertyTagFlags": "None", "PropertyTypeName": None,
                    "PropertyTagExtensions": "NoExtension", "Value": boat}
            p["Value"] = [item]
        elif p["Name"] == "LevelRequirementToBuy":
            p["Value"][0][1]["Value"] = 1  # the boat is the gate; truck levels would ask for level 333
        elif p["Name"] == "bIsHidden":
            p["Value"] = False


def box_row(box, donor):
    row = copy.deepcopy(donor)
    row["Name"] = PREFIX + box["asset"]
    for p in row["Value"]:
        if p["Name"] == "Name":
            p.update({"Flags": "CultureInvariant", "HistoryType": "None", "Namespace": None, "Value": None,
                      "CultureInvariantString": box["name"]})
        elif p["Name"] == "Cost":
            p["Value"] = box["cost"]
        elif p["Name"] == "MassKg":
            p["Value"] = float(box["mass"])
        elif p["Name"] == "TransmissionAsset":
            p["Value"]["AssetPath"]["PackageName"] = TRANS_PKG + box["asset"]
            p["Value"]["AssetPath"]["AssetName"] = box["asset"]
    name_key(row, box["boat"])
    return row


def check_asset(out, name, kind):
    back = synth.framework.load(to_json(out, work(name + ".check.json")))
    x = back["Exports"][0]
    if not x["$type"].startswith("UAssetAPI.ExportTypes.NormalExport") or x["ObjectName"] != name:
        sys.exit(f"FAIL {name}: reads back as {x['$type']} named {x.get('ObjectName')}")
    return back


def build_assets():
    ref_e = synth.framework.load(to_json(os.path.join(synth.ENGINE_DIR, "C18_550HP.uasset"), work("ref_engine.json")))
    for e in ENGINES:
        a = synth.make_asset(e, ref_e)
        synth.fields(a)["StarterRPM"]["Value"] = float(e["starter_rpm"])
        src = work(e["asset"] + ".json")
        synth.framework.save(a, src)
        back = check_asset(synth.build(src, os.path.join(synth.ENGINE_DIR, e["asset"] + ".uasset")), e["asset"], "engine")
        f = synth.fields(back)
        assert f["MaxRPM"]["Value"] == e["rpm"] and f["StarterRPM"]["Value"] == e["starter_rpm"], e["asset"]
        print(f"  {e['asset']:22} {e['hp']}hp {e['torque']:,} @ {e['rpm']}, inertia {e['inertia']:,}, for {e['boat']}")
    ref_t = synth.framework.load(to_json(os.path.join(TRANS_DIR, TRANS_REF + ".uasset"), work("ref_box.json")))
    for b in BOXES:
        src = work(b["asset"] + ".json")
        synth.framework.save(make_box(b, ref_t), src)
        back = check_asset(synth.build(src, os.path.join(TRANS_DIR, b["asset"] + ".uasset")), b["asset"], "box")
        g = [q for q in back["Exports"][0]["Data"][0]["Value"] if q["Name"] == "Gears"][0]["Value"]
        got = [(x["Value"][2]["Value"], round(float(x["Value"][0]["Value"]), 3)) for x in g]
        assert got == [("R", -b["ratio"]), ("N", 0.0), ("F", b["ratio"])], got
        print(f"  {b['asset']:22} {got}, for {b['boat']}")


def build_rows():
    table = synth.framework.load(to_json(synth.TABLE, work("table.before.json")))
    rows = table["Exports"][0]["Table"]["Data"]
    before = {r["Name"] for r in rows}
    ours = {PREFIX + x["asset"] for x in ENGINES + BOXES}
    by_name = {r["Name"]: r for r in rows}
    rows[:] = [r for r in rows if r["Name"] not in ours]
    new = []
    for e in ENGINES:
        r = synth.make_row(e, by_name[synth.REFS[e["ref"]]])
        name_key(r, e["boat"])
        new.append(r)
    new += [box_row(b, by_name[TRANS_REF]) for b in BOXES]
    rows += new
    register_names(table, [x for r in new for x in fnames_in(r)] + [r["Name"] for r in new])
    check = synth.framework.write_table(table, synth.TABLE_PKG, MOD)
    after = {r["Name"] for r in synth.framework.load(check)["Exports"][0]["Table"]["Data"]}
    lost = (before - ours) - after
    if lost or not ours <= after:
        sys.exit(f"FAIL: rows lost {sorted(lost)[:10]}, missing {sorted(ours - after)[:10]}")
    subprocess.run([sys.executable, os.path.join(REPO, "Rebase", "verify.py"), check, MOD, VANILLA], check=True)
    print(f"  VehicleParts_MoreTuning: {len(before)} -> {len(after)} rows, none lost")


def demo():
    ref = []
    for label, ratio in (("R", -3.5), ("N", "+0"), ("1", 4.7), ("2", 2.9)):
        ref.append({"Name": "x", "Value": [{"Value": ratio}, {"Value": 100.0}, {"Value": label}]})
    g = gears({"ratio": 5.0}, ref)
    assert [(x["Name"], x["Value"][2]["Value"], x["Value"][0]["Value"]) for x in g] == [("0", "R", -5.0), ("1", "N", "+0"), ("2", "F", 5.0)], g
    assert all("cat" not in e["asset"].lower() for e in ENGINES)
    assert all(abs(e["torque"] / 12000 - n) < 1 for e, n in zip(ENGINES, (8000, 64000)))
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["demo"]:
        demo()
    else:
        build_assets()
        build_rows()
        print("Then: python FuelRealism/run.py && python EngineTags/run.py, and modp.bat qxZap_MoreTuning_P")
