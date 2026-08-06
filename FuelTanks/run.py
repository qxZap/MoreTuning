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

# The game reads the Utility slot from UtilityParts, not VehicleParts0 -- rows
# added to VehicleParts0 never appear in the list. Donor and target are both this
# one table, and MoreTuning has to ship it. Nothing else does, mod or vanilla, so
# there is no override to lose a fight with.
VANILLA_ROOT = r"D:\MT\Output\Exports\MotorTown\Content"
VANILLA_TABLE = os.path.join(VANILLA_ROOT, "DataAsset", "VehicleParts", "UtilityParts.uasset")
DONOR_ROW = "FuelTank_01"
TARGET = "UtilityParts"

# The row carries no transform -- MTVehiclePartAero is only Mesh, SkelealMesh,
# bUseCustomSocket, CustomSocketName, ComponentTags and AttachParentComponentName
# -- so a mesh appears at the slot in its own orientation and there is no way to
# rotate or scale it from here. Which mesh you pick IS the look.
#
# The stock tank is 51 x 69 x 46 cm: it lies down, wider than tall. Upright
# barrels (SM_barrel_2 at 72x72x106, SM_Prop_Rusted_Drum_01 at 70x71x105) stand
# on end in a slot shaped for a lying tank, which is what read as stretched. The
# meshes below all lie down, and the refinery stacks are barrels on their sides
# -- closest in proportion to the stock tank of anything in the game.
#
# Every row this script owns starts with this, so a rerun can clear its own work.
KEY_PREFIX = "qxFuelTank"

# key, display name, mesh package
TANKS = [
    ("qxFuelTank_Small", "Fuel Tank - Small",
     "/Game/Cars/Parts/Utility/FuelTank_01"),
    ("qxFuelTank_Half", "Half Barrel Tank",
     "/Game/PolygonFarm/Meshes/Props/SM_Prop_Barrel_Half_01"),
    ("qxFuelTank_Pallet", "Barrel Pallet Tank",
     "/Game/Env/Meshes/Refinery/SM_Refinery_OilBarrel_Pallet_01"),
    ("qxFuelTank_Stack", "Barrel Stack Tank",
     "/Game/Env/Meshes/Refinery/SM_Refinery_OilBarrel_Stack_01"),
    ("qxFuelTank_StackBig", "Double Barrel Stack Tank",
     "/Game/Env/Meshes/Refinery/SM_Refinery_OilBarrel_Stack_02"),
]

# The stock tank holds 100 litres in a 51x69x46 box, so the game rates a tank at
# roughly 0.61 litres per litre of bounding box. Deriving capacity from the mesh
# the same way keeps a barrel that looks twice the size actually holding twice as
# much, instead of a 900L label on something the size of the stock tank.
REFERENCE_MESH = "/Game/Cars/Parts/Utility/FuelTank_01"
REFERENCE_LITRES = 100.0
SMALL_TANK_LITRES = 60.0        # same mesh as stock, just a cheaper smaller one
COST_PER_LITRE = 13
KG_PER_LITRE = 0.16


def mesh_box_litres(package, work):
    """Bounding box volume of a static mesh, in litres."""
    path = os.path.join(VANILLA_ROOT, package[len("/Game/"):].replace("/", os.sep) + ".uasset")
    if not os.path.isfile(path):
        sys.exit(f"mesh not in the game: {package}")
    data = json.load(open(to_json(path, os.path.join(work, package.rsplit("/", 1)[-1] + ".json")),
                          encoding="utf-8"))

    def walk(node):
        if isinstance(node, dict):
            if node.get("Name") == "BoxExtent" and isinstance(node.get("Value"), dict):
                yield node["Value"]
            for value in node.values():
                yield from walk(value)
        elif isinstance(node, list):
            for value in node:
                yield from walk(value)

    for extent in walk(data):
        if all(k in extent for k in "XYZ"):
            return (extent["X"] * 2) * (extent["Y"] * 2) * (extent["Z"] * 2) / 1000
    sys.exit(f"no bounds on {package}")


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
    # Deliberately no fallback to the ZMTLoader BASE_GAME_DATA copy. It is from
    # December 2025 -- its VehicleParts0 does not even parse under the 0.7.19
    # mappings -- so shipping its UtilityParts as an override could silently drop
    # whatever the game has added to that table since.
    donor_path = VANILLA_TABLE
    if not os.path.isfile(donor_path):
        sys.exit(f"missing {donor_path}\n"
                 f"Export UtilityParts .uasset/.uexp there with FModel. The game "
                 f"pak is AES encrypted, so repak cannot reach it and the only "
                 f"other copies on disk are stale.")

    work = os.path.join(WORK, "fueltanks")
    os.makedirs(work, exist_ok=True)

    with open(to_json(donor_path, os.path.join(work, "donor.json")), encoding="utf-8") as f:
        donor_table = json.load(f)
    donor = next((r for r in donor_table["Exports"][0]["Table"]["Data"]
                  if r["Name"] == DONOR_ROW), None)
    if donor is None:
        sys.exit(f"{DONOR_ROW} not found in {donor_path}")

    # Build on what MoreTuning already ships if it does, else start from vanilla.
    shipped = os.path.join(MOD, TABLE_DIR, TARGET + ".uasset")
    target_path = shipped if os.path.isfile(shipped) else donor_path
    with open(to_json(target_path, os.path.join(work, "target.json")), encoding="utf-8") as f:
        table = json.load(f)
    rows = table["Exports"][0]["Table"]["Data"]

    # Drop by prefix, not by the current key list, so renaming a tank does not
    # leave the old row stranded in the table.
    rows[:] = [r for r in rows if not r["Name"].startswith(KEY_PREFIX)]
    per_litre = REFERENCE_LITRES / mesh_box_litres(REFERENCE_MESH, work)
    sizes = {}
    for key, display, mesh in TANKS:
        box = mesh_box_litres(mesh, work)
        litres = SMALL_TANK_LITRES if mesh == REFERENCE_MESH else round(box * per_litre)
        mass = round(litres * KG_PER_LITRE + 8)
        cost = int(round(litres * COST_PER_LITRE, -2))
        sizes[key] = float(litres)

        link = add_mesh_import(table, mesh)
        rows.append(make_tank(donor, key, f"{display} {litres:.0f}L",
                              float(litres), float(mass), cost, link))
        register_names(table, [key])
        print(f"  {key:22} {litres:6.0f}L {mass:5.0f}kg {cost:>7}c  "
              f"box {box:5.0f}L  {mesh.rsplit('/', 1)[-1]}")

    merged = os.path.join(work, TARGET + ".json")
    with open(merged, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=1)

    built = from_json(merged, os.path.join(work, TARGET + ".uasset"))
    check = to_json(built, os.path.join(work, TARGET + ".check.json"))
    with open(check, encoding="utf-8") as f:
        after = json.load(f)
    back = {r["Name"]: r for r in after["Exports"][0]["Table"]["Data"]}
    for key, litres in sizes.items():
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
