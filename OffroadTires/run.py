"""Add a +60% off-road tire to the classes that stop at +40%.

    python run.py            # build the tires and add the rows
    python run.py --dry      # show what it would do
    python run.py demo       # self-check

Off-road grip is `OffroadFriction` on a tire's physics asset: 1.0 is no bonus,
and the game already runs a ladder of 1.2, 1.4 and 1.6.

    1.2   +20%   HeavyMachine 20-ton
    1.4   +40%   vanilla Offroad, our Baja, our HeavyMachine OffRoad
    1.6   +60%   RallyTire, Motorcycle2x

Cars and bikes can already reach +60%; the heavier classes cannot, and neither
can a plain off-road tire. So each of those gets a top rung built from the tire
one step below it -- same carcass, same on-road behaviour, more bite off it.

Only OffroadFriction moves. The tire keeps the static and sliding friction, the
springs, the load rating and the wear rate of the tire it is based on, so this
is a wider ladder rather than a better tire in every direction.
"""
import copy
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from pipeline import (MOD, TABLE_DIR, VANILLA, WORK, from_json, register_names,
                      to_json)  # noqa: E402

TIRE_DIR = os.path.join("Cars", "Parts", "Tire")
TABLE = "VehicleParts0"
OFFROAD_60 = 1.6

# (row to clone, new row, new asset, new asset it is based on, display, cost)
NEW_TIRES = [
    ("Offroad", "Offroad60", "OffroadTire60", "OffroadTire", "Offroad+", 2200),
    ("HeavyDutyBajaFrontTire", "HeavyDutyBaja60FrontTire",
     "HeavyDutyBaja60FrontTire", "HeavyDutyBajaFrontTire", "KMHQB2", 3000),
    ("HeavyDutyBajaRearTire", "HeavyDutyBaja60RearTire",
     "HeavyDutyBaja60RearTire", "HeavyDutyBajaRearTire", "KMHQB2-DRW", 6000),
    ("HeavyMachineOffRoadFrontTire", "HeavyMachineOffRoad60FrontTire",
     "HeavyMachine_OffRoad60_FrontTire", "HeavyMachine_OffRoad_FrontTire",
     "KMHM3", 4500),
    ("HeavyMachineOffRoadRearTire", "HeavyMachineOffRoad60RearTire",
     "HeavyMachine_OffRoad60_RearTire", "HeavyMachine_OffRoad_RearTire",
     "KMHM3-DRW", 9000),
]


def source_of(name):
    """Our copy of a tire asset if we have one, else the game's."""
    ours = os.path.join(MOD, TIRE_DIR, name + ".uasset")
    return ours if os.path.isfile(ours) else os.path.join(VANILLA, TIRE_DIR, name + ".uasset")


def set_offroad(asset, value):
    """Raise OffroadFriction and leave every other property alone."""
    for export in asset["Exports"]:
        for prop in export.get("Data") or []:
            if not isinstance(prop, dict) or prop["Name"] != "TirePhysicsParams":
                continue
            for field in prop["Value"]:
                if isinstance(field, dict) and field["Name"] == "OffroadFriction":
                    old = field.get("Value")
                    old = 0.0 if isinstance(old, str) else float(old or 0)
                    field["Value"] = value
                    return old
    return None


def soft(package, asset):
    return {"$type": "UAssetAPI.PropertyTypes.Objects.FSoftObjectPath, UAssetAPI",
            "AssetPath": {"$type": "UAssetAPI.PropertyTypes.Objects.FTopLevelAssetPath, UAssetAPI",
                          "PackageName": package, "AssetName": asset},
            "SubPathString": None}


def make_row(donor, key, label, tire_asset, cost):
    row = copy.deepcopy(donor)
    row["Name"] = key
    for prop in row["Value"]:
        if prop["Name"] == "Name":
            prop.update({"CultureInvariantString": label, "Namespace": None,
                         "Value": None, "HistoryType": "None",
                         "Flags": "CultureInvariant"})
        elif prop["Name"] == "Cost":
            prop["Value"] = cost
        elif prop["Name"] == "Tire":
            for field in prop["Value"]:
                if isinstance(field, dict) and field["Name"] == "TirePhysicsDataAsset":
                    field["Value"] = soft(f"/Game/Cars/Parts/Tire/{tire_asset}", tire_asset)
    return row


def main(dry=False):
    work = os.path.join(WORK, "tires")
    os.makedirs(work, exist_ok=True)
    out_dir = os.path.join(MOD, TIRE_DIR)
    os.makedirs(out_dir, exist_ok=True)

    built = []
    for _, _, new_asset, base_asset, _, _ in NEW_TIRES:
        source = source_of(base_asset)
        if not os.path.isfile(source):
            sys.exit(f"no tire asset to base {new_asset} on: {source}")
        # Stage beside the source; UAssetGUI resolves siblings from that folder.
        staged = os.path.join(os.path.dirname(source), new_asset + ".tmp.json")
        asset = json.load(open(to_json(source, staged), encoding="utf-8"))
        was = set_offroad(asset, OFFROAD_60)
        if was is None:
            sys.exit(f"{base_asset} has no OffroadFriction to raise")
        built.append((new_asset, base_asset, was))
        if dry:
            os.remove(staged)
            continue
        json.dump(asset, open(staged, "w", encoding="utf-8"), indent=1)
        made = from_json(staged, os.path.join(os.path.dirname(source),
                                              new_asset + ".tmp.uasset"))
        for ext in (".uasset", ".uexp"):
            shutil.copy2(made[: -len(".uasset")] + ext,
                         os.path.join(out_dir, new_asset + ext))
            os.remove(made[: -len(".uasset")] + ext)
        os.remove(staged)

    print(f"{'tire':34}{'based on':34}{'offroad':>9}")
    for new_asset, base_asset, was in built:
        print(f"{new_asset:34}{base_asset:34}{was:6.1f} -> {OFFROAD_60}")

    table_path = os.path.join(MOD, TABLE_DIR, TABLE + ".uasset")
    table = json.load(open(to_json(table_path, os.path.join(work, "parts.json")),
                           encoding="utf-8"))
    rows = next(e["Table"]["Data"] for e in table["Exports"] if e.get("Table"))
    by_key = {r["Name"]: r for r in rows}

    added = updated = 0
    names = []
    for donor_key, key, asset_name, _, label, cost in NEW_TIRES:
        donor = by_key.get(donor_key)
        if donor is None:
            sys.exit(f"no row to clone: {donor_key}")
        row = make_row(donor, key, label, asset_name, cost)
        if key in by_key:
            by_key[key].clear()
            by_key[key].update(row)
            updated += 1
        else:
            rows.append(row)
            added += 1
        names += [key, label, asset_name, f"/Game/Cars/Parts/Tire/{asset_name}"]
    register_names(table, names)
    print(f"\n{added} rows added, {updated} refreshed -> {len(rows)} rows")

    if not dry:
        js = os.path.join(work, "parts.edited.json")
        json.dump(table, open(js, "w", encoding="utf-8"), indent=1)
        made = from_json(js, os.path.join(work, TABLE + ".uasset"))
        for ext in (".uasset", ".uexp"):
            shutil.copy2(made[: -len(".uasset")] + ext,
                         os.path.join(MOD, TABLE_DIR, TABLE + ext))
    print("\nPack with: modp.bat qxZap_MoreTuning_P")


def demo():
    asset = {"Exports": [{"Data": [{"Name": "TirePhysicsParams", "Value": [
        {"Name": "StaticMu", "Value": 1.4},
        {"Name": "OffroadFriction", "Value": 1.4},
        {"Name": "WearRate", "Value": 2.0}]}]}]}
    assert set_offroad(asset, 1.6) == 1.4
    got = {f["Name"]: f["Value"] for f in asset["Exports"][0]["Data"][0]["Value"]}
    assert got["OffroadFriction"] == 1.6
    assert got["StaticMu"] == 1.4 and got["WearRate"] == 2.0, \
        "a wider ladder, not a better tire in every direction"
    assert set_offroad({"Exports": []}, 1.6) is None

    donor = {"Name": "HeavyDutyBajaFrontTire", "Value": [
        {"Name": "Name", "CultureInvariantString": "KMHQB1"},
        {"Name": "Cost", "Value": 2000},
        {"Name": "MassKg", "Value": 25.0},
        {"Name": "Tire", "Value": [{"Name": "TirePhysicsDataAsset", "Value": {}}]}]}
    row = make_row(donor, "HeavyDutyBaja60FrontTire", "KMHQB2", "NewTire", 3000)
    assert row is not donor and donor["Value"][1]["Value"] == 2000, "donor untouched"
    fields = {p["Name"]: p for p in row["Value"]}
    assert row["Name"] == "HeavyDutyBaja60FrontTire"
    assert fields["Name"]["CultureInvariantString"] == "KMHQB2"
    assert fields["Cost"]["Value"] == 3000
    assert fields["MassKg"]["Value"] == 25.0, "mass comes from the tire it is based on"
    path = fields["Tire"]["Value"][0]["Value"]["AssetPath"]
    assert path["PackageName"] == "/Game/Cars/Parts/Tire/NewTire"
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main(dry="--dry" in sys.argv)
