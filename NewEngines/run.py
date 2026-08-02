"""Build the new engines: sound cues, engine assets, and their rows.

    python run.py            # everything in engines.py
    python run.py LS3_430HP  # just these
    python run.py demo       # self-check

Three things get made per engine:

  1. the sound waves are copied out of the cooked sunete project
  2. a SoundCue cloned from a stock one, repointed at those waves, with its
     PitchMultiplier / VolumeMultiplier set -- this is what makes one wave set
     voice a whole LS family
  3. an MHEngineDataAsset cloned from a reference engine that already drives
     right, with the specs from engines.py

Then the rows go into ElectricMotors/EnginesIN.json, which is the engine table
before the EV generator appends to it. Run ElectricMotors/run.py afterwards.

Cloning is string replacement on the JSON, the same trick the transmission
generator uses: a cooked asset's own name appears in its NameMap, its package
path and its export, so swapping it swaps all three at once.
"""
import copy
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
sys.path.insert(0, HERE)
from pipeline import MOD, WORK, from_json, to_json  # noqa: E402
from engines import ENGINES, REFS, resolve  # noqa: E402

COOKED = (r"C:\Users\Milea\Documents\Unreal Projects\sunete\Saved\Cooked\Windows"
          r"\sunete\Content\Cars\Parts\Engine\Sound")
SOUND_DIR = os.path.join(MOD, "Cars", "Parts", "Engine", "Sound")
ENGINE_DIR = os.path.join(MOD, "Cars", "Parts", "Engine")
SOUND_PKG = "/Game/Cars/Parts/Engine/Sound"
ENGINES_IN = os.path.join(HERE, "..", "ElectricMotors", "EnginesIN.json")

# Stock assets to clone. The cue folders are where the reference engine's own
# sounds live, which is what gets swapped for the new engine's folder.
CUE_SOURCE = {
    "truck": ("x15", "SC_Truck_04", ["Truck_04_Idle", "Truck_04_Mid",
                                     "Truck_04_High", "Truck_04_Exhaust"]),
    "car":   ("2jz", "SC_V8Engine", ["idle", "mid", "high"]),
}
JAKE_CUE = ("x15/jake", "SC_JakeBrake_01", ["JakeBrake_02"])

WAVE_PARTS = (".uasset", ".uexp", ".ubulk")


def work(*parts):
    path = os.path.join(WORK, "newengines", *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def copy_waves(folder, wanted):
    """Copy an engine's sound waves out of the cooked project into the mod."""
    src = os.path.join(COOKED, folder)
    if not os.path.isdir(src):
        sys.exit(f"no cooked sounds at {src}")
    dst = os.path.join(SOUND_DIR, folder)
    os.makedirs(dst, exist_ok=True)

    missing = []
    for wave in wanted:
        found = False
        for ext in WAVE_PARTS:
            if os.path.isfile(os.path.join(src, wave + ext)):
                shutil.copy2(os.path.join(src, wave + ext), os.path.join(dst, wave + ext))
                found = True
        if not found:
            missing.append(wave)
    return missing


def borrow_wave(folder, wave, donor):
    """Fill a wave the cooked set does not have from an engine that does.

    The 149-series recordings have no separate exhaust layer; without one the
    cue would import a package that is not in the pak and the engine goes silent.
    """
    src = os.path.join(SOUND_DIR, donor)
    dst = os.path.join(SOUND_DIR, folder)
    for ext in WAVE_PARTS:
        if os.path.isfile(os.path.join(src, wave + ext)):
            shutil.copy2(os.path.join(src, wave + ext), os.path.join(dst, wave + ext))


def set_float(export, name, value):
    """Set a float property on an export, adding it if the asset omits it."""
    for prop in export["Data"]:
        if prop["Name"] == name:
            prop["Value"] = value
            return
    export["Data"].append({
        "$type": "UAssetAPI.PropertyTypes.Objects.FloatPropertyData, UAssetAPI",
        "Value": value, "Name": name, "ArrayIndex": 0, "PropertyGuid": None,
        "IsZero": False, "PropertyTagFlags": "None", "PropertyTypeName": None,
        "PropertyTagExtensions": "NoExtension"})


def build_cue(spec, src_folder, src_name, out_folder, out_name):
    """Clone a stock cue onto another folder's waves, with its own pitch/volume."""
    src = os.path.join(SOUND_DIR, src_folder, src_name + ".uasset")
    raw = to_json(src, work("cue_src_%s.json" % src_name))
    with open(raw, "r", encoding="utf-8") as f:
        text = f.read()

    text = text.replace(f"{SOUND_PKG}/{src_folder}/", f"{SOUND_PKG}/{out_folder}/")
    if out_name != src_name:
        text = text.replace(src_name, out_name)
    cue = json.loads(text)

    if spec.get("pitch"):
        set_float(cue["Exports"][0], "PitchMultiplier", float(spec["pitch"]))
    if spec.get("volume"):
        set_float(cue["Exports"][0], "VolumeMultiplier", float(spec["volume"]))

    out_json = work(f"cue_{out_name}.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(cue, f, indent=1)
    built = from_json(out_json, work(f"cue_{out_name}.uasset"))

    dst = os.path.join(SOUND_DIR, out_folder)
    os.makedirs(dst, exist_ok=True)
    for ext in (".uasset", ".uexp"):
        shutil.copy2(built[:-len(".uasset")] + ext, os.path.join(dst, out_name + ext))
    return f"{SOUND_PKG}/{out_folder}/{out_name}"


def build_engine(spec):
    """Clone the reference engine asset and stamp this engine's numbers on it."""
    ref_asset = REFS[spec["ref"]][0]
    ref_json = to_json(os.path.join(ENGINE_DIR, ref_asset + ".uasset"),
                       work(f"eng_src_{ref_asset}.json"))
    with open(ref_json, "r", encoding="utf-8") as f:
        text = f.read()

    ref_sound, ref_cue = engine_cue(json.loads(text))
    text = text.replace(f"{SOUND_PKG}/{ref_sound}/", f"{SOUND_PKG}/{spec['sound']}/")
    text = text.replace(ref_cue, "SC_" + spec["key"])
    text = text.replace(ref_asset, spec["key"])
    asset = json.loads(text)

    props = {p["Name"]: p for p in asset["Exports"][0]["Data"]}
    engine = {q["Name"]: q for q in props["EngineProperty"]["Value"]}
    for name, value in (("MaxTorque", spec["torque"]), ("MaxRPM", float(spec["rpm"])),
                        ("Inertia", float(spec["inertia"])),
                        ("FuelConsumption", float(spec["fuel"]))):
        if name in engine:
            engine[name]["Value"] = value

    out_json = work(f"eng_{spec['key']}.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(asset, f, indent=1)
    built = from_json(out_json, work(f"eng_{spec['key']}.uasset"))
    for ext in (".uasset", ".uexp"):
        shutil.copy2(built[:-len(".uasset")] + ext,
                     os.path.join(ENGINE_DIR, spec["key"] + ext))


def engine_cue(asset):
    """(sound folder, cue name) for an engine's own sound.

    Follow EnginesSound rather than picking the first sound import: a car engine
    also imports the shared backfire and intake cues, and grabbing one of those
    by accident rewrites the wrong paths.
    """
    props = {p["Name"]: p for p in asset["Exports"][0]["Data"]}
    link = props["EnginesSound"]["Value"]
    cue_name = asset["Imports"][-link - 1]["ObjectName"]
    for imp in asset["Imports"]:
        name = imp["ObjectName"]
        if name.startswith(SOUND_PKG + "/") and name.endswith("/" + cue_name):
            return name[len(SOUND_PKG) + 1:].rsplit("/", 1)[0], cue_name
    sys.exit(f"cannot find the package for {cue_name}")


def main():
    wanted = [a for a in sys.argv[1:]]
    specs = [resolve(s) for s in ENGINES if not wanted or s["key"] in wanted]
    if wanted and len(specs) != len(wanted):
        sys.exit(f"unknown engine(s): {set(wanted) - {s['key'] for s in specs}}")

    folders_done = set()
    for spec in specs:
        cue_folder, cue_name, waves = CUE_SOURCE[spec["cue"]]
        if spec["sound"] not in folders_done:
            missing = copy_waves(spec["sound"], waves)
            for wave in missing:
                borrow_wave(spec["sound"], wave, cue_folder)
                print(f"  {spec['sound']}: no {wave} in the cooked set, borrowed {cue_folder}'s")
            if spec["cue"] == "truck":
                jake_folder, jake_name, jake_waves = JAKE_CUE
                copy_waves(f"{spec['sound']}/jake", jake_waves)
                build_cue({}, jake_folder, jake_name, f"{spec['sound']}/jake", jake_name)
            folders_done.add(spec["sound"])

        build_cue(spec, cue_folder, cue_name, spec["sound"], "SC_" + spec["key"])
        build_engine(spec)
        print(f"  {spec['key']:22} {spec['hp']:5}HP @ {spec['rpm']:.0f}  "
              f"torque {spec['torque']:.0f}  {spec['cost']:>8}c  "
              f"{spec['level'][0]}:{spec['level'][1]}")

    add_rows(specs)
    print(f"\n{len(specs)} engines built. Now run ElectricMotors/run.py, then rebuild "
          f"the table and pack.")


def add_rows(specs):
    """Insert a table row per engine into EnginesIN.json, after the named row."""
    with open(ENGINES_IN, "r", encoding="utf-8") as f:
        table = json.load(f)
    rows = table["Exports"][0]["Table"]["Data"]

    from pipeline import register_names
    added = []
    for spec in specs:
        rows[:] = [r for r in rows if r["Name"] != spec["key"]]           # rerunnable
        anchor = next((i for i, r in enumerate(rows) if r["Name"] == spec["after"]), None)
        if anchor is None:
            sys.exit(f"{spec['key']}: no row named {spec['after']} to sit after")
        row = make_row(rows, spec)
        rows.insert(anchor + 1, row)
        added.append(row)

    names = []
    for row in added:
        names += [row["Name"], f"{SOUND_PKG.rsplit('/', 3)[0]}"]
        names.append(f"/Game/Cars/Parts/Engine/{row['Name']}")
    register_names(table, names)

    with open(ENGINES_IN, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=2)
    print(f"\n{len(added)} rows inserted into {os.path.relpath(ENGINES_IN, HERE)}")


def make_row(rows, spec):
    """Clone a row of the same family and restamp it."""
    donor = REFS[spec["ref"]][0]
    template = next((r for r in rows if r["Name"] in (donor, "CumminsX15x605", "50coyote")), None)
    if template is None:
        sys.exit("no donor row to clone")
    row = copy.deepcopy(template)
    row["Name"] = spec["key"]

    for prop in row["Value"]:
        name = prop["Name"]
        if name == "Name":
            prop["CultureInvariantString"] = spec["name"]
        elif name == "Desciption":
            prop["CultureInvariantString"] = spec.get("desc", "")
        elif name == "Cost":
            prop["Value"] = int(spec["cost"])
        elif name == "MassKg":
            prop["Value"] = float(spec["mass"])
        elif name == "LevelRequirementToBuy":
            prop["Value"] = level_map(prop, *spec["level"])
        elif name == "EngineAsset":
            prop["Value"]["AssetPath"]["PackageName"] = f"/Game/Cars/Parts/Engine/{spec['key']}"
            prop["Value"]["AssetPath"]["AssetName"] = spec["key"]
    return row


def level_map(prop, klass, value):
    """One (class -> level) entry, reusing the donor row's own key/value shape."""
    existing = prop.get("Value") or []
    if existing:
        entry = copy.deepcopy(existing[0])
        entry[0]["Value"] = klass
        entry[1]["Value"] = int(value)
        return [entry]
    return [[
        {"$type": "UAssetAPI.PropertyTypes.Objects.EnumPropertyData, UAssetAPI",
         "EnumType": None, "InnerType": None, "Name": "LevelRequirementToBuy",
         "ArrayIndex": 0, "PropertyGuid": None, "IsZero": False,
         "PropertyTagFlags": "None", "PropertyTypeName": None,
         "PropertyTagExtensions": "NoExtension", "Value": klass},
        {"$type": "UAssetAPI.PropertyTypes.Objects.IntPropertyData, UAssetAPI",
         "Name": "LevelRequirementToBuy", "ArrayIndex": 0, "PropertyGuid": None,
         "IsZero": False, "PropertyTagFlags": "None", "PropertyTypeName": None,
         "PropertyTagExtensions": "NoExtension", "Value": int(value)},
    ]]


def demo():
    export = {"Data": [{"Name": "VolumeMultiplier", "Value": 0.5}]}
    set_float(export, "VolumeMultiplier", 0.575)
    set_float(export, "PitchMultiplier", 0.92)
    assert {p["Name"]: p["Value"] for p in export["Data"]} == {
        "VolumeMultiplier": 0.575, "PitchMultiplier": 0.92}

    # the shared backfire cue is imported first; following EnginesSound must
    # still land on the engine's own folder
    asset = {"Imports": [
        {"ObjectName": "/Game/Cars/Parts/Engine/Sound/Backfire/SC_Backfire"},
        {"ObjectName": "/Game/Cars/Parts/Engine/Sound/50coyote/SC_V8Engine"},
        {"ObjectName": "SC_Backfire"},
        {"ObjectName": "SC_V8Engine"}],
        "Exports": [{"Data": [{"Name": "EnginesSound", "Value": -4}]}]}
    assert engine_cue(asset) == ("50coyote", "SC_V8Engine")
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main()
