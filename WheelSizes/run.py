"""Wheel size versions, and the cheap experiment that says whether they can exist.

    python run.py            # build the test pak
    python run.py demo       # self-check

Every wheel mesh in the game is a 1 metre circle -- all 91 measured between 98.8
and 100.3cm, on wheels that in game run from a kart to a mining truck. They are
normalised on purpose and the vehicle scales them to its own size, which is why
any rim fits any car, and why nothing in the part, the tire or the table carries
a size.

The open question is *how* the vehicle scales them, and there are only two
answers. Either it measures the mesh and scales it to fit a radius it already
knows, or it applies a fixed factor and ignores the mesh entirely. That decides
whether wheel sizes are possible at all, and the two cases are told apart
without touching a single vertex:

    bounds x1.25  ->  renders smaller   the game measures; size is controllable
    bounds x0.75  ->  renders larger    same conclusion, opposite direction
    no change at all                    fixed factor; the idea is dead

Bounds are a structured property, so this needs no binary surgery. If it turns
out the game does measure, the real build multiplies the vertex positions
instead, which is the same maths applied to the render data rather than the box
around it.

This ships as its own ZZZ pak: several mods touch wheels, Maja's among them, and
ZZZ sorts last so it wins. Her table is the base, so her wheels survive.
"""
import copy
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from pipeline import REPO, VANILLA, WORK, from_json, register_names, to_json  # noqa: E402

MAJA = os.path.join(REPO, "MajasMoWheelWorksV5.1-7.19_P", "MotorTown", "Content")
OUT = os.path.join(REPO, "ZZZ_qxZap_MoreTuning_WheelSizes_P", "MotorTown", "Content")
TABLE = os.path.join("DataAsset", "VehicleParts", "Wheels.uasset")
WHEEL_DIR = os.path.join("Cars", "Parts", "Wheels")

# Cervos' rim, because it is an ordinary road wheel on an ordinary car.
DONOR_ROW = "Cervos"
DONOR_MESHES = ("Classic_01_L", "Classic_01_R")

# (suffix, bounds multiplier, label). If the game measures the mesh, a bigger
# box means a smaller wheel -- it is being scaled down to fit the same radius.
VERSIONS = [("Big", 0.75, "Classic 01 (Big test)"),
            ("Small", 1.25, "Classic 01 (Small test)")]


def scale_bounds(asset, factor):
    """Multiply ExtendedBounds. Returns the box extent before and after."""
    before = after = None
    for export in asset["Exports"]:
        for prop in export.get("Data") or []:
            if not isinstance(prop, dict) or prop["Name"] != "ExtendedBounds":
                continue
            for part in prop["Value"]:
                name = part.get("Name")
                if name not in ("Origin", "BoxExtent"):
                    if name == "SphereRadius":
                        v = part.get("Value")
                        part["Value"] = (0.0 if isinstance(v, str) else float(v)) * factor
                    continue
                vec = part["Value"][0]["Value"]
                if name == "BoxExtent":
                    before = max(abs(0.0 if isinstance(vec[k], str) else float(vec[k]))
                                 for k in "XYZ")
                for k in "XYZ":
                    v = vec[k]
                    vec[k] = (0.0 if isinstance(v, str) else float(v)) * factor
                if name == "BoxExtent":
                    after = before * factor
    return before, after


def rename_export(asset, old, new):
    """A data asset is package.object; a copy that keeps the old object name
    resolves to nothing. Learned from the tires."""
    for export in asset["Exports"]:
        if export.get("ObjectName") == old:
            export["ObjectName"] = new
    register_names(asset, [new])


def import_mesh(table, name):
    """Add a hard import for a wheel mesh, returning its link. Idempotent.

    A wheel mesh is an ObjectProperty pointing at an import, not a soft path --
    the two are not interchangeable and a soft path here simply will not write.
    Each mesh needs a Package import and a StaticMesh import inside it.
    """
    package = f"/Game/Cars/Parts/Wheels/{name}"
    for index, entry in enumerate(table["Imports"], 1):
        if entry.get("ObjectName") == name and entry.get("ClassName") == "StaticMesh":
            return -index
    outer = None
    for index, entry in enumerate(table["Imports"], 1):
        if entry.get("ObjectName") == package:
            outer = -index
    if outer is None:
        table["Imports"].append({
            "$type": "UAssetAPI.Import, UAssetAPI", "ObjectName": package,
            "OuterIndex": 0, "ClassPackage": "/Script/CoreUObject",
            "ClassName": "Package", "PackageName": None, "bImportOptional": False})
        outer = -len(table["Imports"])
    table["Imports"].append({
        "$type": "UAssetAPI.Import, UAssetAPI", "ObjectName": name,
        "OuterIndex": outer, "ClassPackage": "/Script/Engine",
        "ClassName": "StaticMesh", "PackageName": None, "bImportOptional": False})
    return -len(table["Imports"])


def make_row(donor, key, label, left, right):
    row = copy.deepcopy(donor)
    row["Name"] = key
    for prop in row["Value"]:
        if prop["Name"] == "Name":
            prop.update({"CultureInvariantString": label, "Namespace": None,
                         "Value": None, "HistoryType": "None",
                         "Flags": "CultureInvariant"})
        elif prop["Name"] == "Wheel":
            for field in prop["Value"]:
                if not isinstance(field, dict):
                    continue
                if field["Name"] == "LeftWheelMesh":
                    field["Value"] = left
                elif field["Name"] == "RightWheelMesh":
                    field["Value"] = right
    return row


def build_mesh(name, new_name, factor, work):
    """Copy a wheel mesh with its bounds scaled, keeping its bulk data."""
    source = os.path.join(VANILLA, WHEEL_DIR, name + ".uasset")
    staged = os.path.join(os.path.dirname(source), new_name + ".tmp.json")
    asset = json.load(open(to_json(source, staged), encoding="utf-8"))
    rename_export(asset, name, new_name)
    before, after = scale_bounds(asset, factor)
    json.dump(asset, open(staged, "w", encoding="utf-8"), indent=1)
    made = from_json(staged, os.path.join(os.path.dirname(source), new_name + ".tmp.uasset"))

    out_dir = os.path.join(OUT, WHEEL_DIR)
    os.makedirs(out_dir, exist_ok=True)
    for ext in (".uasset", ".uexp"):
        shutil.copy2(made[: -len(".uasset")] + ext, os.path.join(out_dir, new_name + ext))
        os.remove(made[: -len(".uasset")] + ext)
    bulk = source[: -len(".uasset")] + ".ubulk"
    if os.path.isfile(bulk):
        shutil.copy2(bulk, os.path.join(out_dir, new_name + ".ubulk"))
    os.remove(staged)
    return before, after


def main():
    work = os.path.join(WORK, "wheelsizes")
    os.makedirs(work, exist_ok=True)

    print(f"{'mesh':30}{'half-extent cm':>16}{'after':>10}")
    made = {}
    for suffix, factor, _ in VERSIONS:
        for mesh in DONOR_MESHES:
            new_name = f"{mesh}_{suffix}"
            before, after = build_mesh(mesh, new_name, factor, work)
            made[new_name] = True
            print(f"{new_name:30}{before:16.1f}{after:10.1f}")

    source = os.path.join(MAJA, TABLE)
    if not os.path.isfile(source):
        sys.exit(f"no wheel table to base on at {source}")
    table = json.load(open(to_json(source, os.path.join(work, "wheels.json")),
                           encoding="utf-8"))
    rows = next(e["Table"]["Data"] for e in table["Exports"] if e.get("Table"))
    donor = next((r for r in rows if r["Name"] == DONOR_ROW), None)
    if donor is None:
        sys.exit(f"no {DONOR_ROW} row to clone")

    names = []
    for suffix, _, label in VERSIONS:
        key = f"{DONOR_ROW}_{suffix}"
        left, right = f"{DONOR_MESHES[0]}_{suffix}", f"{DONOR_MESHES[1]}_{suffix}"
        row = make_row(donor, key, label,
                       import_mesh(table, left), import_mesh(table, right))
        existing = next((r for r in rows if r["Name"] == key), None)
        if existing is not None:
            rows.remove(existing)
        rows.insert(rows.index(donor) + 1, row)      # beside the wheel it copies
        names += [key, label, left, right,
                  f"/Game/Cars/Parts/Wheels/{left}", f"/Game/Cars/Parts/Wheels/{right}"]
    register_names(table, names)

    js = os.path.join(work, "wheels.edited.json")
    json.dump(table, open(js, "w", encoding="utf-8"), indent=1)
    built = from_json(js, os.path.join(work, "Wheels.uasset"))
    out_table = os.path.join(OUT, TABLE)
    os.makedirs(os.path.dirname(out_table), exist_ok=True)
    for ext in (".uasset", ".uexp"):
        shutil.copy2(built[: -len(".uasset")] + ext, out_table.replace(".uasset", ext))

    order = [r["Name"] for r in rows]
    at = order.index(f"{DONOR_ROW}_{VERSIONS[0][0]}")
    print(f"\n{len(rows)} rows, based on Maja's table")
    print(f"   order around the donor: {order[at-2:at+3]}")
    print("\nPack with: modp.bat ZZZ_qxZap_MoreTuning_WheelSizes_P")


def demo():
    asset = {"NameMap": [], "NamesReferencedFromExportDataCount": 0, "Exports": [
        {"ObjectName": "Classic_01_L", "Data": [
            {"Name": "ExtendedBounds", "Value": [
                {"Name": "Origin", "Value": [{"Value": {"X": 2.0, "Y": "+0", "Z": 4.0}}]},
                {"Name": "BoxExtent", "Value": [{"Value": {"X": 50.0, "Y": 20.0, "Z": 50.0}}]},
                {"Name": "SphereRadius", "Value": 70.0}]}]}]}
    before, after = scale_bounds(asset, 0.75)
    assert (before, after) == (50.0, 37.5)
    box = asset["Exports"][0]["Data"][0]["Value"][1]["Value"][0]["Value"]
    assert box["X"] == 37.5 and box["Y"] == 15.0
    origin = asset["Exports"][0]["Data"][0]["Value"][0]["Value"][0]["Value"]
    assert origin["X"] == 1.5 and origin["Y"] == 0.0, "the offset scales with the box"
    assert asset["Exports"][0]["Data"][0]["Value"][2]["Value"] == 52.5

    rename_export(asset, "Classic_01_L", "Classic_01_L_Big")
    assert asset["Exports"][0]["ObjectName"] == "Classic_01_L_Big"
    assert "Classic_01_L_Big" in asset["NameMap"], "package.object must agree"

    donor = {"Name": "Cervos", "Value": [
        {"Name": "Name", "CultureInvariantString": "Cervos"},
        {"Name": "Wheel", "Value": [
            {"Name": "LeftWheelMesh", "Value": 0},
            {"Name": "RightWheelMesh", "Value": 0}]}]}
    row = make_row(donor, "Cervos_Big", "Classic 01 (Big test)", -101, -102)
    assert row is not donor and donor["Name"] == "Cervos", "donor untouched"
    wheel = {f["Name"]: f for f in row["Value"][1]["Value"]}
    assert wheel["LeftWheelMesh"]["Value"] == -101, "a hard import, not a soft path"
    assert wheel["RightWheelMesh"]["Value"] == -102

    table = {"Imports": []}
    a = import_mesh(table, "Classic_01_L_Big")
    assert len(table["Imports"]) == 2, "a package import and the mesh inside it"
    assert table["Imports"][-1]["ClassName"] == "StaticMesh"
    assert table["Imports"][-1]["OuterIndex"] == -1
    assert import_mesh(table, "Classic_01_L_Big") == a, "must not stack duplicates"
    b = import_mesh(table, "Classic_01_R_Big")
    assert b != a and len(table["Imports"]) == 4
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main()
