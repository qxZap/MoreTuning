"""Prototype: extra fuel tanks as buyable parts, into MoreTuning's VehicleParts0.

    python run.py        # build and install
    python run.py demo   # self-check

The game already supports this and ships exactly one of them. UtilityParts has a
row `FuelTank_01` -- 100 litres, 1000c, 20kg -- carrying:

    FuelTank.FuelLiter   how much it adds
    Aero.Mesh            the mesh, a hard object import
    PartType             reads "Headlight", which every utility part uses

So a fuel tank is just a VehiclePartRow with FuelLiter set and a mesh hung off
Aero.Mesh. This clones that row into VehicleParts0 -- which MoreTuning already
ships, so no new table and no stale-vanilla risk -- varying capacity, mass, cost
and mesh.

The meshes are the interesting half: rather than one tank scaled up and down,
these borrow barrels and drums already in the game, so a truck ends up hauling a
refinery barrel. Numbers are prototype numbers, tune them in TANKS.
"""
import copy
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from pipeline import MOD, TABLE_DIR, WORK, from_json, register_names, to_json  # noqa: E402

# The one vanilla fuel tank, to clone the row shape from. The export folder gets
# wiped by FModel runs, so fall back to the copy ZMTLoader keeps.
DONOR_TABLE = [
    r"D:\MT\Output\Exports\MotorTown\Content\DataAsset\VehicleParts\UtilityParts.uasset",
    r"D:\MT\ZMTLoader\ZMTLoader\BASE_GAME_DATA\MotorTown\Content\DataAsset\VehicleParts"
    r"\UtilityParts.uasset",
]
DONOR_ROW = "FuelTank_01"
TARGET = "VehicleParts0"

# key, display name, litres, kg, cost, mesh package
TANKS = [
    ("qxFuelTank_Small_60", "Fuel Tank 60L", 60.0, 14.0, 700,
     "/Game/Cars/Parts/Utility/FuelTank_01"),
    ("qxFuelTank_Large_200", "Fuel Tank 200L", 200.0, 38.0, 2600,
     "/Game/Cars/Parts/Utility/FuelTank_01"),
    ("qxFuelTank_Drum_300", "Rusted Drum 300L", 300.0, 55.0, 3800,
     "/Game/PolygonFarm/Meshes/Props/SM_Prop_Rusted_Drum_01"),
    ("qxFuelTank_Barrel_500", "Oil Barrel 500L", 500.0, 80.0, 6200,
     "/Game/AssetsvilleTown/Meshes/StreetProps/SM_barrel_2"),
    ("qxFuelTank_Refinery_900", "Refinery Barrel 900L", 900.0, 130.0, 11000,
     "/Game/Env/Meshes/Refinery/SM_Refinery_OilBarrel_04"),
]


def import_entry(object_name, outer, class_package, class_name):
    return {"$type": "UAssetAPI.Import, UAssetAPI", "ObjectName": object_name,
            "OuterIndex": outer, "ClassPackage": class_package,
            "ClassName": class_name, "PackageName": None, "bImportOptional": False}


def add_mesh_import(table, package):
    """Add a StaticMesh import (and its package) and return the link to it."""
    imports = table["Imports"]
    asset = package.rsplit("/", 1)[-1]
    for index, existing in enumerate(imports):
        if existing["ObjectName"] == asset and existing["ClassName"] == "StaticMesh":
            return -(index + 1)

    imports.append(import_entry(package, 0, "/Script/CoreUObject", "Package"))
    package_link = -len(imports)
    imports.append(import_entry(asset, package_link, "/Script/Engine", "StaticMesh"))
    link = -len(imports)

    # A hard reference has to be declared or the loader will not have the mesh
    # ready when the row is serialised.
    deps = table["Exports"][0]["CreateBeforeSerializationDependencies"]
    if link not in deps:
        deps.append(link)
    register_names(table, [package, asset])
    return link


def prop(row, name):
    for entry in row["Value"]:
        if entry["Name"] == name:
            return entry
    return None


def sub(struct, name):
    for entry in struct["Value"]:
        if entry.get("Name") == name:
            return entry
    return None


def make_tank(donor, key, display, litres, mass, cost, mesh_link):
    row = copy.deepcopy(donor)
    row["Name"] = key
    prop(row, "Cost")["Value"] = int(cost)
    prop(row, "MassKg")["Value"] = float(mass)
    sub(prop(row, "FuelTank"), "FuelLiter")["Value"] = float(litres)
    sub(prop(row, "Aero"), "Mesh")["Value"] = mesh_link

    name = prop(row, "Name")
    if name is not None:
        name["CultureInvariantString"] = display
        name["Namespace"] = None
        name["Value"] = None
        name["HistoryType"] = "None"
        name["Flags"] = "CultureInvariant"
    return row


def main():
    donor_path = next((p for p in DONOR_TABLE if os.path.isfile(p)), None)
    if not donor_path:
        sys.exit("no UtilityParts to clone FuelTank_01 from; tried:\n  "
                 + "\n  ".join(DONOR_TABLE))

    work = os.path.join(WORK, "fueltanks")
    os.makedirs(work, exist_ok=True)

    with open(to_json(donor_path, os.path.join(work, "donor.json")), encoding="utf-8") as f:
        donor_table = json.load(f)
    donor = next((r for r in donor_table["Exports"][0]["Table"]["Data"]
                  if r["Name"] == DONOR_ROW), None)
    if donor is None:
        sys.exit(f"{DONOR_ROW} not found in {donor_path}")

    target_path = os.path.join(MOD, TABLE_DIR, TARGET + ".uasset")
    with open(to_json(target_path, os.path.join(work, "target.json")), encoding="utf-8") as f:
        table = json.load(f)
    rows = table["Exports"][0]["Table"]["Data"]

    keys = {k for k, *_ in TANKS}
    rows[:] = [r for r in rows if r["Name"] not in keys]          # rerunnable
    for key, display, litres, mass, cost, mesh in TANKS:
        link = add_mesh_import(table, mesh)
        rows.append(make_tank(donor, key, display, litres, mass, cost, link))
        register_names(table, [key])
        print(f"  {key:26} {litres:6.0f}L {mass:5.0f}kg {cost:>7}c  {mesh.rsplit('/', 1)[-1]}")

    merged = os.path.join(work, TARGET + ".json")
    with open(merged, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=1)

    built = from_json(merged, os.path.join(work, TARGET + ".uasset"))
    check = to_json(built, os.path.join(work, TARGET + ".check.json"))
    with open(check, encoding="utf-8") as f:
        after = json.load(f)
    back = {r["Name"]: r for r in after["Exports"][0]["Table"]["Data"]}
    for key, _, litres, *_ in TANKS:
        if key not in back:
            sys.exit(f"{key} missing after the round trip")
        got = sub(prop(back[key], "FuelTank"), "FuelLiter")["Value"]
        if got != litres:
            sys.exit(f"{key}: FuelLiter came back {got}, expected {litres}")

    for ext in (".uasset", ".uexp"):
        shutil.copy2(os.path.join(work, TARGET + ext),
                     os.path.join(MOD, TABLE_DIR, TARGET + ext))
    print(f"\n{len(TANKS)} fuel tanks added to {TARGET} "
          f"({len(after['Exports'][0]['Table']['Data'])} rows). Pack and test.")


def demo():
    table = {"Imports": [], "NameMap": [], "NamesReferencedFromExportDataCount": 0,
             "Exports": [{"CreateBeforeSerializationDependencies": []}]}
    link = add_mesh_import(table, "/Game/Env/Meshes/Refinery/SM_Refinery_OilBarrel_04")
    assert link == -2, link
    assert table["Imports"][0]["ClassName"] == "Package"
    assert table["Imports"][1]["ObjectName"] == "SM_Refinery_OilBarrel_04"
    assert table["Imports"][1]["OuterIndex"] == -1
    assert table["Exports"][0]["CreateBeforeSerializationDependencies"] == [-2]
    assert "SM_Refinery_OilBarrel_04" in table["NameMap"]
    # asking twice must reuse the import, not add a second one
    assert add_mesh_import(table, "/Game/Env/Meshes/Refinery/SM_Refinery_OilBarrel_04") == -2
    assert len(table["Imports"]) == 2

    donor = {"Name": DONOR_ROW, "Value": [
        {"Name": "Cost", "Value": 1000}, {"Name": "MassKg", "Value": 20.0},
        {"Name": "Name", "CultureInvariantString": "Fuel Tank - A", "Value": "k",
         "Namespace": "x", "HistoryType": "Base", "Flags": 0},
        {"Name": "FuelTank", "Value": [{"Name": "FuelLiter", "Value": 100.0}]},
        {"Name": "Aero", "Value": [{"Name": "Mesh", "Value": -41}]}]}
    row = make_tank(donor, "qxTank", "Big Tank", 500.0, 80.0, 6200, -2)
    assert row["Name"] == "qxTank"
    assert sub(prop(row, "FuelTank"), "FuelLiter")["Value"] == 500.0
    assert sub(prop(row, "Aero"), "Mesh")["Value"] == -2
    assert prop(row, "Name")["CultureInvariantString"] == "Big Tank"
    assert prop(row, "Name")["Value"] is None, "the string-table key has to go"
    assert sub(prop(donor, "FuelTank"), "FuelLiter")["Value"] == 100.0, "donor untouched"
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main()
