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
Boat row keys: Arini's Vehicles_Biceps (C0700_Tugboat, C0701_ContainerShip, C0702_TenderBoat, C0703_FishingBoat,
C0704_SpeedBoat). The three small boats run petrol outboards / sterndrives (Yamaha F-series, MerCruiser, Mercury Racing).
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

def marine(asset, name, hp, nm, rpm, mass, inertia, boat):
    """One engine; the family's sound, starter share and idle come from the boat (2026-11-11 tests: the tug idles at
    0.05, the ship's 600 rpm engine only just failed to at 0.12)."""
    tug = boat == "C0700_Tugboat"
    return dict(sound="dd1671" if tug else "om502", asset=asset, name=name, family="truck", ref="C18_550HP",
                curve="DieselTruck", hp=hp, torque=nm * 12000, rpm=rpm, mass=mass, inertia=inertia, jake=0,
                starter_rpm=round(rpm * 0.475), idle=0.05 if tug else 0.2, boat=boat, per_nm=12000)


def petrol(asset, name, hp, rpm, mass, inertia, boat, sound):
    """Outboards and sterndrives (2026-11-12, the small boats): car petrol engines, LS3 as the reference, so torque
    at the car scale (9,560 per Nm) and the LS3's own starter and idle. Priced like the marine diesels ($166.67/hp,
    family "truck" only sets that), the table the user approved."""
    nm = hp * 745.7 / (6.2832 * rpm / 60)
    return dict(sound=sound, asset=asset, name=name, family="truck", ref="LS3_430HP", curve="SmallBlock", hp=hp,
                torque=round(nm * 9560), rpm=rpm, mass=mass, inertia=inertia, jake=None, boat=boat, per_nm=9560)


# Upgrades in the garage, one family per boat (the user: "upgradable things within the service menu"). Real ratings;
# torque = hp * 745.7 / (2 pi rpm / 60). The middle one of each is the boat's stock engine.
ENGINES = [
    marine("Marine3508C_1200HP", "Caterpillar 3508C Marine 1200HP", 1200, 5341, 1600, 5000, 285_000, "C0700_Tugboat"),
    marine("Marine3512C_1800HP", "Caterpillar 3512C Marine 1800HP", 1800, 8000, 1600, 7000, 400_000, "C0700_Tugboat"),
    marine("Marine3516C_2575HP", "Caterpillar 3516C Marine 2575HP", 2575, 11460, 1600, 8700, 500_000, "C0700_Tugboat"),
    marine("MaK6M32C_4000HP", "MaK 6M32C Marine 4000HP", 4000, 47750, 600, 31000, 3_000_000, "C0701_ContainerShip"),
    marine("MaK8M32C_5400HP", "MaK 8M32C Marine 5400HP", 5400, 64000, 600, 40000, 4_000_000, "C0701_ContainerShip"),
    marine("MaK9M32C_6000HP", "MaK 9M32C Marine 6000HP", 6000, 71620, 600, 45000, 4_500_000, "C0701_ContainerShip"),
    petrol("Outboard_F70_70HP", "Yamaha F70 Outboard 70HP", 70, 5800, 119, 1500, "C0702_TenderBoat", "4age"),
    petrol("Outboard_F115_115HP", "Yamaha F115 Outboard 115HP", 115, 5500, 172, 1800, "C0702_TenderBoat", "4age"),
    petrol("Outboard_F150_150HP", "Yamaha F150 Outboard 150HP", 150, 5500, 216, 2200, "C0702_TenderBoat", "4age"),
    petrol("Outboard_TwinF150_300HP", "Twin Yamaha F150 Outboards 300HP", 300, 5500, 432, 4400, "C0703_FishingBoat", "4g63t"),
    petrol("Outboard_TwinF200_400HP", "Twin Yamaha F200 Outboards 400HP", 400, 5500, 452, 5000, "C0703_FishingBoat", "4g63t"),
    petrol("Outboard_TwinF250_500HP", "Twin Yamaha F250 V6 Outboards 500HP", 500, 5500, 510, 6000, "C0703_FishingBoat", "4g63t"),
    petrol("Sterndrive_45L_250HP", "MerCruiser 4.5L V6 Sterndrive 250HP", 250, 5000, 390, 3500, "C0704_SpeedBoat", "sbc350"),
    petrol("Sterndrive_62L_300HP", "MerCruiser 6.2L 350 MAG Sterndrive 300HP", 300, 5000, 420, 4500, "C0704_SpeedBoat", "sbc350"),
    petrol("Sterndrive_Racing520_520HP", "Mercury Racing 520 Sterndrive 520HP", 520, 5200, 450, 4000, "C0704_SpeedBoat", "sbc350"),
]
BOXES = [
    dict(asset="MarineGear_Tug", name="Marine Reverse Gear 5:1 (Tug)", ratio=5.0, mass=2000, cost=40000, boat="C0700_Tugboat"),
    dict(asset="MarineGear_Ship", name="Marine Reverse-Reduction Gear 4:1 (Ship)", ratio=4.0, mass=8000, cost=120000,
         boat="C0701_ContainerShip"),
    dict(asset="MarineGear_Tender", name="Outboard Lower Unit 2.15:1 (Tender)", ratio=2.15, mass=20, cost=3000, boat="C0702_TenderBoat"),
    dict(asset="MarineGear_Fisher", name="Outboard Lower Units 1.86:1 (Fishing Boat)", ratio=1.86, mass=40, cost=6000,
         boat="C0703_FishingBoat"),
    dict(asset="MarineGear_Sterndrive", name="Bravo III Sterndrive 2.0:1 (Speedboat)", ratio=2.0, mass=80, cost=8000,
         boat="C0704_SpeedBoat"),
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
    refs = {r: synth.framework.load(to_json(os.path.join(synth.ENGINE_DIR, r + ".uasset"), work(f"ref_{r}.json")))
            for r in {e["ref"] for e in ENGINES}}
    for e in ENGINES:
        a = synth.make_asset(e, refs[e["ref"]])
        # 2026-11-11: with the C18's IdleThrottle (0.017) both died the moment the throttle closed. Starter at the
        # C18's share of its limit (0.48), and more idle fuel: a slow heavy engine needs it to hold its idle.
        if "starter_rpm" in e:  # petrol ones keep the LS3's
            synth.fields(a)["StarterRPM"]["Value"] = float(e["starter_rpm"])
            synth.fields(a)["IdleThrottle"]["Value"] = float(e["idle"])
        src = work(e["asset"] + ".json")
        synth.framework.save(a, src)
        back = check_asset(synth.build(src, os.path.join(synth.ENGINE_DIR, e["asset"] + ".uasset")), e["asset"], "engine")
        f = synth.fields(back)
        assert f["MaxRPM"]["Value"] == e["rpm"] and ("starter_rpm" not in e or f["StarterRPM"]["Value"] == e["starter_rpm"]), e["asset"]
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
    assert all(abs(e["hp"] * 745.7 / (6.2832 * e["rpm"] / 60) - e["torque"] / e["per_nm"]) < 0.02 * e["torque"] / e["per_nm"] for e in ENGINES), "torque off its rating"
    assert all(synth.sound_data(e["sound"]) for e in ENGINES), "a sound set is not cooked"
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["demo"]:
        demo()
    else:
        build_assets()
        build_rows()
        print("Then: python FuelRealism/run.py && python EngineTags/run.py, and modp.bat qxZap_MoreTuning_P")
