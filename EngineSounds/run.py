"""Re-bind engine sound cues to the property they actually belong to.

    python run.py            # every engine in the mod
    python run.py 59cummins  # just these

MHEngineDataAsset stores its properties unversioned -- by schema position, with
no names in the file. The game inserted a sound property into that struct after
these assets were authored, so every slot past EnginesSound now resolves one
name later than it was written as:

    stored as            reads back today as
    EnginesSound     ->  EnginesSound      (fine)
    JakeBrakeSound   ->  IntakeSound
    IntakeSound      ->  BackfireSound

Which is why jake brakes are silent (nothing is bound to JakeBrakeSound), the
intake plays the jake brake cue, and backfire plays the intake cue.

The fix does not assume the shift is exactly one slot: it looks at what each
property actually points at and re-binds by that, so it stays correct however
far the schema has drifted.
"""
import glob
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from pipeline import MOD, WORK, from_json, to_json  # noqa: E402

ENGINE_DIR = os.path.join(MOD, "Cars", "Parts", "Engine")

# Schema index order, taken from a vanilla engine that sets all of them. The
# unversioned writer needs ascending indices, so emit in this order.
SOUND_ORDER = ["EnginesSound", "IntakeSound", "JakeBrakeSound", "BackfireSound"]


def classify(cue):
    """Which property a sound cue belongs to, from the cue's own name."""
    name = cue.lower()
    if "jakebrake" in name or "jake" in name:
        return "JakeBrakeSound"
    if "intake" in name:
        return "IntakeSound"
    if "backfire" in name:
        return "BackfireSound"
    return "EnginesSound"


def rebind(asset):
    """Rename each sound property to match its target. True if anything moved."""
    imports = asset["Imports"]
    data = asset["Exports"][0]["Data"]

    sounds, others = [], []
    for prop in data:
        if prop["Name"] in SOUND_ORDER and isinstance(prop.get("Value"), int):
            sounds.append(prop)
        else:
            others.append(prop)

    changed = False
    for prop in sounds:
        link = prop["Value"]
        if link >= 0:
            continue
        want = classify(imports[-link - 1]["ObjectName"])
        if prop["Name"] != want:
            prop["Name"] = want
            changed = True

    seen = [p["Name"] for p in sounds]
    if len(set(seen)) != len(seen):
        raise SystemExit(f"two cues want the same property: {seen}")

    sounds.sort(key=lambda p: SOUND_ORDER.index(p["Name"]))
    asset["Exports"][0]["Data"] = others + sounds
    return changed


def fix(path):
    name = os.path.splitext(os.path.basename(path))[0]
    work = os.path.join(WORK, "engines")
    os.makedirs(work, exist_ok=True)

    src = to_json(path, os.path.join(work, name + ".json"))
    with open(src, "r", encoding="utf-8") as f:
        asset = json.load(f)
    if not rebind(asset):
        return None

    with open(src, "w", encoding="utf-8") as f:
        json.dump(asset, f, indent=2)

    built = from_json(src, os.path.join(work, name + ".uasset"))
    check = to_json(built, os.path.join(work, name + ".check.json"))
    with open(check, "r", encoding="utf-8") as f:
        after = json.load(f)

    # Prove it against the rebuilt file, not the JSON we just wrote.
    imports = after["Imports"]
    bound = {}
    for prop in after["Exports"][0]["Data"]:
        if prop["Name"] in SOUND_ORDER and isinstance(prop.get("Value"), int) and prop["Value"] < 0:
            cue = imports[-prop["Value"] - 1]["ObjectName"]
            if classify(cue) != prop["Name"]:
                raise SystemExit(f"{name}: {prop['Name']} still points at {cue}")
            bound[prop["Name"]] = cue

    for ext in (".uasset", ".uexp"):
        shutil.copy2(os.path.join(work, name + ext), os.path.join(ENGINE_DIR, name + ext))
    return bound


def main():
    wanted = sys.argv[1:]
    paths = ([os.path.join(ENGINE_DIR, n + ".uasset") for n in wanted] if wanted
             else sorted(glob.glob(os.path.join(ENGINE_DIR, "*.uasset"))))

    fixed = jake = 0
    for path in paths:
        result = fix(path)
        if result is None:
            continue
        fixed += 1
        jake += "JakeBrakeSound" in result
        print(f"  {os.path.splitext(os.path.basename(path))[0]:26} "
              + ", ".join(f"{k}={v}" for k, v in sorted(result.items())))
    print(f"\n{fixed} engines re-bound, {jake} of them now have a jake brake sound "
          f"({len(paths) - fixed} already correct)")
    print("Pack with: modp.bat qxZap_MoreTuning_P")


def demo():
    asset = {
        "Imports": [{"ObjectName": "SC_Truck_04"}, {"ObjectName": "SC_JakeBrake_01"},
                    {"ObjectName": "SC_Intake02_HeavyDuty"}],
        "Exports": [{"Data": [
            {"Name": "EngineProperty", "Value": []},
            {"Name": "EnginesSound", "Value": -1},
            {"Name": "BackfireSound", "Value": -3},
            {"Name": "IntakeSound", "Value": -2},
        ]}],
    }
    assert rebind(asset) is True
    data = asset["Exports"][0]["Data"]
    assert [p["Name"] for p in data] == [
        "EngineProperty", "EnginesSound", "IntakeSound", "JakeBrakeSound"], data
    by_name = {p["Name"]: p["Value"] for p in data if p["Name"] != "EngineProperty"}
    assert by_name == {"EnginesSound": -1, "IntakeSound": -3, "JakeBrakeSound": -2}
    assert rebind(asset) is False, "second pass should be a no-op"

    # an engine with no jake cue keeps two properties, correctly named
    petrol = {"Imports": [{"ObjectName": "SC_V8Engine"}, {"ObjectName": "SC_Intake01"}],
              "Exports": [{"Data": [{"Name": "EnginesSound", "Value": -1},
                                    {"Name": "BackfireSound", "Value": -2}]}]}
    assert rebind(petrol) is True
    assert [p["Name"] for p in petrol["Exports"][0]["Data"]] == ["EnginesSound", "IntakeSound"]

    # a custom cue name that is not a keyword is an engine sound
    assert classify("hayabusa") == "EnginesSound"
    assert classify("SC_JakeBrake_01") == "JakeBrakeSound"
    assert classify("SC_Intake02_Kart") == "IntakeSound"
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main()
