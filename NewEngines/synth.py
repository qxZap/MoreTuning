"""The 28 engines of docs/ENGINES_SYNTH.md: one MHEngineDataAsset each, and a row in MoreTuning's own table.

    python NewEngines/synth.py          # build the assets, then the rows
    python NewEngines/synth.py demo     # self-check

Run after Rebase/channels.py (which rebuilds VehicleParts_MoreTuning from the 0.7.19 tables and so
drops these rows), then FuelRealism/run.py and EngineTags/run.py, which finish the rows like every
other engine. Rerunnable: it replaces its own rows and assets.

Each asset is a reference engine of the same class cloned and restamped (MaxTorque, MaxRPM,
Inertia, curve, and the torque-dimensioned friction/starter scaled by the same rule of three as
NewEngines/run.py). Only exact-match strings are renamed, so the reference's sound cue paths survive
the rename; SOUND (below) then points each engine at its own cooked cue, see FlatEngines/COOKED.md.
"""
import copy
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(REPO, "Rebase"))
from pipeline import MOD, VANILLA, WORK, from_json, register_names, to_json  # noqa: E402
from rebase import fnames_in  # noqa: E402

_spec = importlib.util.spec_from_file_location("dtframework", os.path.join(REPO, "DataTableFramework", "run.py"))
framework = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(framework)

ENGINE_DIR = os.path.join(MOD, "Cars", "Parts", "Engine")
ENGINE_PKG = "/Game/Cars/Parts/Engine/"
TABLE_PKG = "/Game/DataAsset/VehicleParts/VehicleParts_MoreTuning"
TABLE = os.path.join(MOD, "DataAsset", "VehicleParts", "VehicleParts_MoreTuning.uasset")
PREFIX = "C0001_"  # MoreTuning's channel number: the C<NNNN>_ convention (AGENTS.md)
SOUND_ORDER = ["EnginesSound", "EngineSoundData", "BackfireSound", "IntakeSound", "JakeBrakeSound"]  # usmap 721T1

# reference asset -> its row in the table (the row template)
REFS = {"LS3_430HP": "LS3_430HP", "2JZ320HP": "2JZ320HP", "59cummins": "59cummins",
        "73powerstroke": "73powerstroke", "C18_550HP": "C18_550HP", "N14_435HP": "N14_435HP",
        "DD471_130HP": "DD471_130HP", "Bus_300HP": "Bus_300HP"}

# sound key (COOKED.md Row), asset, display name, family, reference, curve, hp, MaxTorque, rev limit,
# kg, inertia, jake steps (None: keep the reference's). MaxTorque from docs/ENGINES_SYNTH.md.
E = [
    ("type1", "VWType1_50HP", "VW Type 1 1600 50HP", "car", "LS3_430HP", "SmallBlock", 50, 1032480, 4500, 115, 2000, None),
    ("4age", "Toyota4AGE_128HP", "Toyota 4A-GE 1.6 16V 128HP", "car", "LS3_430HP", "DOHC", 128, 1424440, 7600, 120, 1800, None),
    ("4g63t", "Mitsubishi4G63T_286HP", "Mitsubishi 4G63T 2.0 Turbo 286HP", "car", "2JZ320HP", "SmallBlock", 286, 3747520, 7000, 170, 2200, None),
    ("rs3five", "AudiRS3_25TFSI_400HP", "Audi RS3 2.5 TFSI 400HP", "car", "2JZ320HP", "SmallBlock", 400, 4780000, 7000, 160, 2800, None),
    ("s65", "BMWS65_414HP", "BMW S65 4.0 V8 414HP", "car", "LS3_430HP", "V12", 414, 3824000, 8400, 202, 3500, None),
    ("voodoo", "FordVoodoo_526HP", "Ford Voodoo 5.2 V8 526HP", "car", "LS3_430HP", "V12", 526, 5563920, 8250, 200, 4000, None),
    ("cgtv10", "PorscheCarreraGTV10_612HP", "Porsche Carrera GT 5.7 V10 612HP", "car", "LS3_430HP", "V12", 612, 5640400, 8400, 214, 3500, None),
    ("sbc350", "SmallBlock350_355HP", "Chevrolet Small-Block 350 355HP", "car", "LS3_430HP", "SmallBlock", 355, 5248440, 5600, 260, 5000, None),
    ("hemi426", "Hemi426_425HP", "Chrysler 426 Street Hemi 425HP", "car", "LS3_430HP", "SmallBlock", 425, 6347840, 6000, 350, 6000, None),
    ("12v", "Cummins12V_215HP", "Cummins 5.9 12-Valve 215HP", "car", "59cummins", "DieselTruck", 215, 5970000, 3000, 500, 6000, 0),
    ("vp44", "CumminsVP44_245HP", "Cummins 5.9 24-Valve VP44 245HP", "car", "59cummins", "DieselTruck", 245, 6850000, 3200, 500, 6000, 0),
    ("cummins67", "Cummins67HO_400HP", "Cummins 6.7 High Output 400HP", "car", "59cummins", "DieselTruck", 400, 13560000, 3200, 520, 6500, 0),
    ("ps60", "Powerstroke60_325HP", "Ford 6.0 Power Stroke 325HP", "car", "73powerstroke", "DieselTruck", 325, 7730000, 3800, 440, 5500, 0),
    ("ntc400", "CumminsNTC400_400HP", "Cummins NTC 400 Big Cam", "truck", "N14_435HP", "DieselTruck", 400, 18708000, 2300, 1300, 52000, 3),
    ("isx15", "CumminsISX15_500HP", "Cummins ISX15 500HP", "truck", "C18_550HP", "DieselTruck", 500, 30096000, 2100, 1320, 50000, 3),
    ("isx15", "CumminsISX15_600HP", "Cummins ISX15 600HP", "truck", "C18_550HP", "DieselTruck", 600, 33348000, 2100, 1320, 50000, 3),
    ("c16", "CATC16_550HP", "CAT C16 550HP", "truck", "C18_550HP", "DieselTruck", 550, 30096000, 2200, 1300, 55000, 3),
    ("c16", "CATC16_600HP", "CAT C16 600HP", "truck", "C18_550HP", "DieselTruck", 600, 30096000, 2200, 1300, 55000, 3),
    ("macke6", "MackE6_350HP", "Mack E6 350HP", "truck", "N14_435HP", "DieselTruck", 350, 20820000, 2100, 1100, 45000, 3),
    ("mp8", "MackMP8_505HP", "Mack MP8 505HP", "truck", "C18_550HP", "DieselTruck", 505, 28632000, 2100, 1200, 48000, 3),
    ("6ct", "Cummins6CT_240HP", "Cummins 6CT 8.3 240HP", "truck", "Bus_300HP", "DieselTruck", 240, 10896000, 2500, 610, 22000, None),
    ("6ct", "Cummins6CT_300HP", "Cummins 6CT 8.3 300HP", "truck", "Bus_300HP", "DieselTruck", 300, 13020000, 2500, 610, 22000, None),
    ("6ct", "Cummins6CT_350HP", "Cummins 6CT 8.3 350HP", "truck", "Bus_300HP", "DieselTruck", 350, 15456000, 2500, 610, 22000, None),
    ("6ct", "Cummins6CT_400HP", "Cummins 6CT 8.3 400HP", "truck", "Bus_300HP", "DieselTruck", 400, 17496000, 2500, 610, 22000, None),
    ("dd671", "Detroit671_238HP", "Detroit Diesel 6-71 238HP", "truck", "DD471_130HP", "DieselTruck", 238, 9924000, 2300, 900, 25000, 3),
    ("dd871", "Detroit8V71_318HP", "Detroit Diesel 8V-71 318HP", "truck", "DD471_130HP", "DieselTruck", 318, 13500000, 2300, 1050, 32000, 3),
    ("dd1271", "Detroit12V71_475HP", "Detroit Diesel 12V-71 475HP", "truck", "DD471_130HP", "DieselTruck", 475, 20172000, 2300, 1500, 48000, 3),
    ("dd1671", "Detroit16V71_635HP", "Detroit Diesel 16V-71 635HP", "truck", "DD471_130HP", "DieselTruck", 635, 26844000, 2300, 1900, 62000, 3),
    ("series60", "DetroitSeries60_515HP", "Detroit Diesel Series 60 515HP", "truck", "C18_550HP", "DieselTruck", 515, 26844000, 2100, 1200, 48000, 3),
    ("cat3406e", "CAT3406E_475HP", "CAT 3406E 475HP", "truck", "C18_550HP", "DieselTruck", 475, 26844000, 2100, 1300, 55000, 3),
    ("macke9", "MackE9_500HP", "Mack E9 V8 500HP", "truck", "C18_550HP", "DieselTruck", 500, 28476000, 2100, 1450, 58000, 3),
    ("om502", "MercedesOM502_630HP", "Mercedes OM502 LA V8 630HP", "truck", "C18_550HP", "DieselTruck", 630, 36000000, 1900, 1150, 45000, 0),
    ("8v92", "Detroit8V92TA_450HP", "Detroit Diesel 8V-92TA 450HP", "truck", "DD471_130HP", "DieselTruck", 450, 21960000, 2100, 1150, 36000, 3),
]
KEYS = ("sound", "asset", "name", "family", "ref", "curve", "hp", "torque", "rpm", "mass", "inertia", "jake")
ENGINES = [dict(zip(KEYS, e)) for e in E]

# Cooked cues, filled from FlatEngines/COOKED.md: sound key -> {property: soft package path}. An engine
# whose key is missing keeps its reference's sound.
SOUND = {}


def cost(e):
    return round(e["hp"] * (125 if e["family"] == "car" else 500 / 3))  # N14 435 -> 72500, C18 550 -> 91667


def level(e):
    return ("CL_Driver", max(1, round(e["hp"] / 13.2))) if e["family"] == "car" else ("CL_Truck", max(1, round(e["hp"] / 5.4)))


def rename(node, old, new):
    """Swap strings exactly equal to old -> new (so SC_<old> cue paths are left alone)."""
    if isinstance(node, dict):
        for k, v in node.items():
            if v in old:
                node[k] = new[old.index(v)]
            else:
                rename(v, old, new)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, str) and v in old:
                node[i] = new[old.index(v)]
            else:
                rename(v, old, new)


def fields(asset):
    data = asset["Exports"][0]["Data"]
    return {q["Name"]: q for p in data if p["Name"] == "EngineProperty" for q in p["Value"]}


def sounds_in_order(asset):
    """Name each sound import's slot by what it points at, and emit in schema order.

    The mod's car engines were written when BackfireSound sat one slot earlier, so their backfire cue
    now reads back as EngineSoundData (a data asset slot, not a cue). Name it for what it is.
    """
    data = asset["Exports"][0]["Data"]
    for p in data:
        if p["Name"] in SOUND_ORDER and isinstance(p.get("Value"), int) and p["Value"] < 0:
            cue = asset["Imports"][-p["Value"] - 1]["ObjectName"].lower()
            if "backfire" in cue:
                p["Name"] = "BackfireSound"
    names = [p["Name"] for p in data if p["Name"] in SOUND_ORDER]
    assert len(set(names)) == len(names), names
    asset["Exports"][0]["Data"] = ([p for p in data if p["Name"] not in SOUND_ORDER]
                                   + sorted((p for p in data if p["Name"] in SOUND_ORDER),
                                            key=lambda p: SOUND_ORDER.index(p["Name"])))


def make_asset(e, ref_asset):
    asset = copy.deepcopy(ref_asset)
    ref = asset["Exports"][0]["ObjectName"]
    rename(asset, [ref, ENGINE_PKG + ref], [e["asset"], ENGINE_PKG + e["asset"]])
    text = json.dumps(asset)
    old_curve = next(i["ObjectName"] for i in asset["Imports"] if i["ClassName"] == "CurveFloat")
    asset = json.loads(text.replace(old_curve, "TorqueCurve_" + e["curve"]))
    f = fields(asset)
    by_torque = e["torque"] / f["MaxTorque"]["Value"]
    by_speed = by_torque * f["MaxRPM"]["Value"] / e["rpm"]
    for name, k in (("FrictionCoulombCoeff", by_torque), ("StarterTorque", by_torque), ("FrictionViscosityCoeff", by_speed)):
        f[name]["Value"] = float(round(f[name]["Value"] * k))
    f["MaxTorque"]["Value"] = float(e["torque"])
    f["MaxRPM"]["Value"] = float(e["rpm"])
    f["Inertia"]["Value"] = float(e["inertia"])
    f["FuelConsumption"]["Value"] = float(round(e["hp"] / 3))  # placeholder: FuelRealism/run.py sets it
    if e["jake"] is not None and "MaxJakeBrakeStep" in f:
        f["MaxJakeBrakeStep"]["Value"] = e["jake"]
    set_sound(asset, SOUND.get(e["sound"], {}))
    sounds_in_order(asset)
    return asset


def set_sound(asset, cues):
    """Repoint sound slots at cooked cues: {property: '/Game/.../SC_X'} (package path = object path)."""
    data = asset["Exports"][0]["Data"]
    for prop, package in cues.items():
        obj = package.rsplit("/", 1)[1]
        slot = next((p for p in data if p["Name"] == prop), None)
        if slot is None:
            sys.exit(f"{asset['Exports'][0]['ObjectName']}: no {prop} slot on the reference to repoint")
        cue = asset["Imports"][-slot["Value"] - 1]
        outer = asset["Imports"][-cue["OuterIndex"] - 1]
        if sum(1 for p in data if p["Name"] in SOUND_ORDER and p.get("Value") == slot["Value"]) > 1:
            sys.exit("shared sound import, cannot repoint one slot")
        outer["ObjectName"], cue["ObjectName"] = package, obj
        register_names(asset, [package, obj])


def build(src, out):
    """from_json, retried: with another UAssetGUI running, a write that works alone sometimes comes out empty."""
    for _ in range(2):
        try:
            return from_json(src, out)
        except SystemExit:
            pass
    return from_json(src, out)


def build_assets():
    work = os.path.join(WORK, "synth")
    os.makedirs(work, exist_ok=True)
    refs = {}
    for e in ENGINES:
        if e["ref"] not in refs:
            refs[e["ref"]] = framework.load(to_json(os.path.join(ENGINE_DIR, e["ref"] + ".uasset"),
                                                    os.path.join(work, "ref_" + e["ref"] + ".json")))
        asset = make_asset(e, refs[e["ref"]])
        src = os.path.join(work, e["asset"] + ".json")
        framework.save(asset, src)
        out = build(src, os.path.join(ENGINE_DIR, e["asset"] + ".uasset"))
        back = framework.load(to_json(out, os.path.join(work, e["asset"] + ".check.json")))
        x = back["Exports"][0]
        if not x["$type"].startswith("UAssetAPI.ExportTypes.NormalExport") or x["ObjectName"] != e["asset"]:
            sys.exit(f"FAIL {e['asset']}: reads back as {x['$type']} named {x.get('ObjectName')}")
        got = fields(back)
        if got["MaxTorque"]["Value"] != e["torque"] or got["MaxRPM"]["Value"] != e["rpm"]:
            sys.exit(f"FAIL {e['asset']}: torque/rpm did not survive the round trip")
        print(f"  {e['asset']:28} {e['hp']:4}hp {e['torque']:>10,} @ {e['rpm']}  from {e['ref']}  "
              + ", ".join(f"{p['Name']}={back['Imports'][-p['Value'] - 1]['ObjectName']}"
                          for p in x["Data"] if p["Name"] in SOUND_ORDER))


def make_row(e, donor):
    row = copy.deepcopy(donor)
    row["Name"] = PREFIX + e["asset"]
    for p in row["Value"]:
        if p["Name"] == "Name":
            p.update({"Flags": "CultureInvariant", "HistoryType": "None", "Namespace": None, "Value": None,
                      "CultureInvariantString": e["name"]})
        elif p["Name"] == "Cost":
            p["Value"] = cost(e)
        elif p["Name"] == "MassKg":
            p["Value"] = float(e["mass"])
        elif p["Name"] == "LevelRequirementToBuy":
            p["Value"][0][0]["Value"], p["Value"][0][1]["Value"] = level(e)
        elif p["Name"] == "EngineAsset":
            p["Value"]["AssetPath"]["PackageName"] = ENGINE_PKG + e["asset"]
            p["Value"]["AssetPath"]["AssetName"] = e["asset"]
    return row


def build_rows():
    work = os.path.join(WORK, "synth")
    table = framework.load(to_json(TABLE, os.path.join(work, "table.before.json")))
    rows = table["Exports"][0]["Table"]["Data"]
    before = {r["Name"] for r in rows}
    ours = {PREFIX + e["asset"] for e in ENGINES}
    by_name = {r["Name"]: r for r in rows}
    rows[:] = [r for r in rows if r["Name"] not in ours]
    new = [make_row(e, by_name[REFS[e["ref"]]]) for e in ENGINES]
    rows += new
    register_names(table, [x for r in new for x in fnames_in(r)] + [r["Name"] for r in new])
    check = framework.write_table(table, TABLE_PKG, MOD)  # exits unless a DataTable with every row
    after = {r["Name"] for r in framework.load(check)["Exports"][0]["Table"]["Data"]}
    lost = (before - ours) - after
    if lost or not ours <= after:
        sys.exit(f"FAIL: rows lost {sorted(lost)[:10]}, missing {sorted(ours - after)[:10]}")
    import subprocess
    subprocess.run([sys.executable, os.path.join(REPO, "Rebase", "verify.py"), check, MOD, VANILLA], check=True)
    print(f"  {TABLE_PKG.rsplit('/', 1)[1]}: {len(before)} -> {len(after)} rows, none lost")


def demo():
    assert cost(dict(hp=435, family="truck")) == 72500 and cost(dict(hp=550, family="truck")) == 91667
    assert cost(dict(hp=430, family="car")) == 53750 and level(dict(hp=430, family="car")) == ("CL_Driver", 33)
    assert level(dict(hp=550, family="truck")) == ("CL_Truck", 102)
    assert len(ENGINES) == 33 and len({e["asset"] for e in ENGINES}) == 33
    assert all(e["ref"] in REFS for e in ENGINES)
    a = {"Imports": [{"ObjectName": "SC_Backfire"}, {"ObjectName": "SC_V8"}, {"ObjectName": "SC_Intake01"}],
         "Exports": [{"Data": [{"Name": "EngineProperty"}, {"Name": "EnginesSound", "Value": -2},
                               {"Name": "EngineSoundData", "Value": -1}, {"Name": "IntakeSound", "Value": -3}]}]}
    sounds_in_order(a)
    assert [p["Name"] for p in a["Exports"][0]["Data"]] == ["EngineProperty", "EnginesSound", "BackfireSound", "IntakeSound"]
    t = {"x": "C18_550HP", "y": ["/Game/Cars/Parts/Engine/C18_550HP", "SC_C18_550HP"]}
    rename(t, ["C18_550HP", ENGINE_PKG + "C18_550HP"], ["N", ENGINE_PKG + "N"])
    assert t == {"x": "N", "y": [ENGINE_PKG + "N", "SC_C18_550HP"]}
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["demo"]:
        demo()
    else:
        build_assets()
        build_rows()
        print("Then: python FuelRealism/run.py && python EngineTags/run.py")
