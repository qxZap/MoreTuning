"""Rebase a mod part-table onto the current vanilla table.

Game 0.7.19 moved part references from ObjectProperty (hard import, negative
FPackageIndex) to SoftObjectProperty (FSoftObjectPath string): EngineAsset,
TransmissionAsset, LSDAsset on VehiclePartRow, and TirePhysicsDataAsset(_BikeRear)
inside MTVehiclePartTire. Mod tables built the old way no longer parse at all --
UAssetAPI falls back to RawExport and the game ignores the rows.

Which properties flipped is read off the freshly exported vanilla table rather
than hardcoded, so the next property the game converts needs no code change.

This converts old-format mod rows to the new format and stacks them on top of a
freshly exported vanilla table, so vanilla balance changes come along for free.

    python rebase.py <vanilla.json> <mod_old.json> <out.json>

Both inputs are UAssetGUI `tojson` output. Convert the vanilla file with the
CURRENT usmap and the old mod file with the usmap it was built against.
"""
import json
import re
import sys

# UE stores an FName as (base, number): "LSD_Clutch_2_100_40" is base
# "LSD_Clutch_2_100" with number 40, and only the base lives in the NameMap.
# Register the full string instead and UAssetGUI's writer silently produces
# nothing at all -- that is what broke the LSD table.
FNAME_SUFFIX = re.compile(r"^(.+)_(0|[1-9][0-9]*)$")

NONE_PATH = {
    "$type": "UAssetAPI.PropertyTypes.Objects.FSoftObjectPath, UAssetAPI",
    "AssetPath": {
        "$type": "UAssetAPI.PropertyTypes.Objects.FTopLevelAssetPath, UAssetAPI",
        "PackageName": "None",
        "AssetName": "None",
    },
    "SubPathString": None,
}


def resolve_import(imports, link):
    """FPackageIndex -> (package name, asset name). link is negative for imports."""
    if link >= 0:
        return None
    entry = imports[-link - 1]
    outer = entry["OuterIndex"]
    package = imports[-outer - 1]["ObjectName"] if outer < 0 else None
    return package, entry["ObjectName"]


def to_soft_object(prop, imports):
    ref = resolve_import(imports, prop.get("Value")) if isinstance(prop.get("Value"), int) else None
    if ref is None:
        value = json.loads(json.dumps(NONE_PATH))
    else:
        package, asset = ref
        value = json.loads(json.dumps(NONE_PATH))
        value["AssetPath"]["PackageName"] = package
        value["AssetPath"]["AssetName"] = asset
    return {
        "$type": "UAssetAPI.PropertyTypes.Objects.SoftObjectPropertyData, UAssetAPI",
        "Name": prop["Name"],
        "ArrayIndex": prop.get("ArrayIndex", 0),
        "PropertyGuid": None,
        "IsZero": False,
        "PropertyTagFlags": "None",
        "PropertyTypeName": None,
        "PropertyTagExtensions": "NoExtension",
        "Value": value,
    }


def soft_property_names(rows):
    """Property names the current game serialises as soft object paths."""
    names = set()

    def walk(node):
        if isinstance(node, dict):
            if "SoftObjectPropertyData" in node.get("$type", "") and node.get("Name"):
                names.add(node["Name"])
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(rows)
    return names


def is_hard_object(prop):
    # Exact prefix, not a substring test: "SoftObjectPropertyData" contains
    # "ObjectPropertyData", and treating an already-converted property as a hard
    # one throws its path away and re-points it at None.
    return prop.get("$type", "").startswith("UAssetAPI.PropertyTypes.Objects.ObjectPropertyData")


def soften(node, imports, soft_names):
    """Rewrite every ObjectProperty that is now a soft reference, at any depth."""
    if isinstance(node, dict):
        return {k: soften(v, imports, soft_names) for k, v in node.items()}
    if isinstance(node, list):
        return [to_soft_object(item, imports)
                if (isinstance(item, dict)
                    and item.get("Name") in soft_names
                    and is_hard_object(item))
                else soften(item, imports, soft_names)
                for item in node]
    return node


def is_struct(prop):
    return isinstance(prop, dict) and prop.get("$type", "").startswith(
        "UAssetAPI.PropertyTypes.Structs.StructPropertyData") and isinstance(prop.get("Value"), list)


def reshape(props, template, where):
    """Fit a struct's fields to the template's: fill new ones, relocate moved ones.

    0.7.20 moved the turbo's seven flat fields into new Gasoline and Diesel
    sub-structs; vanilla's own stock turbos carry the old values into both, so a
    field that went one level down is copied into every new sub-struct that has
    it. A field with no home left fails loudly -- writing it kills the table.
    """
    mine = {p["Name"]: p for p in props}
    known = {p["Name"] for p in template}
    orphans = {n: p for n, p in mine.items() if n not in known}
    out = []
    for tp in template:
        if tp["Name"] in mine:
            p = mine[tp["Name"]]
            if is_struct(p) and is_struct(tp):
                p["Value"] = reshape(p["Value"], tp["Value"], f"{where}.{p['Name']}")
            out.append(p)
            continue
        p = json.loads(json.dumps(tp))
        if is_struct(p):
            for i, sub in enumerate(p["Value"]):
                if sub["Name"] in orphans:
                    p["Value"][i] = json.loads(json.dumps(orphans[sub["Name"]]))
        out.append(p)
    moved = {s["Name"] for p in out if is_struct(p) and p["Name"] not in mine for s in p["Value"]}
    lost = set(orphans) - moved
    if lost:
        raise SystemExit(f"{where}: {sorted(lost)} no longer exist in the struct and "
                         f"did not move into a sub-struct -- decide where they go")
    return out


def convert_row(row, imports, defaults, soft_names):
    """Old-format row -> new format. `defaults` fills properties added by the update."""
    out = soften(row, imports, soft_names)["Value"]
    seen = {prop["Name"] for prop in out}

    # Properties the new struct has that the old one didn't: take vanilla's value,
    # inserted at vanilla's position so the row keeps a sane order.
    for index, prop in enumerate(defaults):
        if prop["Name"] not in seen:
            out.insert(min(index, len(out)), json.loads(json.dumps(prop)))

    # Then the same one level down, for structs whose fields changed shape.
    by_name = {p["Name"]: p for p in defaults}
    for prop in out:
        tp = by_name.get(prop["Name"])
        if is_struct(prop) and is_struct(tp):
            prop["Value"] = reshape(prop["Value"], tp["Value"], f"{row['Name']}.{prop['Name']}")

    row = dict(row)
    row["Value"] = out
    return row


def find_hard_refs(node):
    """Yield every ObjectProperty pointing at an import anywhere inside a row."""
    if isinstance(node, dict):
        if is_hard_object(node) and isinstance(node.get("Value"), int) and node["Value"] < 0:
            yield node
        for child in node.values():
            yield from find_hard_refs(child)
    elif isinstance(node, list):
        for child in node:
            yield from find_hard_refs(child)


def count_live_refs(rows):
    """Soft references that actually point at something, for the no-loss check."""
    total = 0

    def walk(node):
        nonlocal total
        if isinstance(node, dict):
            if node.get("$type", "").startswith("UAssetAPI.PropertyTypes.Objects.FSoftObjectPath"):
                if (node.get("AssetPath") or {}).get("PackageName") not in (None, "None"):
                    total += 1
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(rows)
    return total


def graft_imports(out, mod_imports, added_rows):
    """Copy the imports `added_rows` still point at into `out`, repointing the rows.

    Returns the import entries that were appended.
    """
    imports = out["Imports"]
    slot_of = {}
    for slot, entry in enumerate(imports):
        slot_of[(entry["ObjectName"], entry["ClassPackage"], entry["ClassName"],
                 entry["OuterIndex"])] = -(slot + 1)
    appended = []

    def graft(link):
        entry = mod_imports[-link - 1]
        outer = graft(entry["OuterIndex"]) if entry["OuterIndex"] < 0 else entry["OuterIndex"]
        key = (entry["ObjectName"], entry["ClassPackage"], entry["ClassName"], outer)
        if key not in slot_of:
            new_entry = dict(entry, OuterIndex=outer)
            imports.append(new_entry)
            appended.append(new_entry)
            slot_of[key] = -len(imports)
        return slot_of[key]

    dependencies = out["Exports"][0]["CreateBeforeSerializationDependencies"]
    for row in added_rows:
        for prop in find_hard_refs(row):
            prop["Value"] = graft(prop["Value"])
            if prop["Value"] not in dependencies:
                dependencies.append(prop["Value"])
    return appended


def fname_base(value):
    """The part of an FName string that actually goes in the NameMap."""
    if not value:
        return None
    match = FNAME_SUFFIX.match(value)
    return match.group(1) if match else value


# JSON slots that hold an FName rather than a plain string. Property *names*
# are not among them -- unversioned assets get those from the usmap, which is
# why vanilla's NameMap has no "AirDragMultiplier" in it.
FNAME_KEYS = ("ArrayType", "InnerType", "ValueType", "EnumType", "StructType",
              "PackageName", "AssetName",
              # a string-table text's table: the paint slots' "Body" label is one
              "TableId")
FNAME_VALUED = ("NamePropertyData", "EnumPropertyData", "GameplayTagContainerPropertyData",
                "GameplayTagPropertyData")


def fnames_in(node):
    """Every FName a row references, by structure rather than by guesswork."""
    if isinstance(node, dict):
        for key in FNAME_KEYS:
            if isinstance(node.get(key), str):
                yield node[key]
        if any(kind in node.get("$type", "") for kind in FNAME_VALUED):
            value = node.get("Value")
            for item in (value if isinstance(value, list) else [value]):
                if isinstance(item, str):
                    yield item
        for child in node.values():
            yield from fnames_in(child)
    elif isinstance(node, list):
        for child in node:
            yield from fnames_in(child)


def all_strings(node, found):
    if isinstance(node, dict):
        for value in node.values():
            all_strings(value, found)
    elif isinstance(node, list):
        for value in node:
            all_strings(value, found)
    elif isinstance(node, str):
        found.add(node)
    return found


def names_for(row, mod_names):
    """FNames a converted row drags in.

    Row keys, enum values, struct types, gameplay tags and soft-path halves are
    all FNames and all have to exist in the NameMap or UAssetGUI writes nothing.
    Two sources, unioned: the structural walk, plus any string in the row that
    the mod file itself had in its NameMap -- that second set is by definition
    the FNames the row used. A stray extra entry costs nothing.
    """
    structural = {row["Name"], *fnames_in(row)}
    inherited = {s for s in all_strings(row, set()) if fname_base(s) in mod_names}
    return {n for n in (fname_base(s) for s in structural | inherited) if n}


def rebase(vanilla, mod):
    vanilla_rows = vanilla["Exports"][0]["Table"]["Data"]
    template = vanilla_rows[0]["Value"]
    keep = {r["Name"] for r in vanilla_rows}

    soft_names = soft_property_names(vanilla_rows)
    added = [convert_row(r, mod["Imports"], template, soft_names)
             for r in mod["Exports"][0]["Table"]["Data"] if r["Name"] not in keep]

    out = json.loads(json.dumps(vanilla))
    out["Exports"][0]["Table"]["Data"] = vanilla_rows + added

    # Anything still referenced hard (custom tire meshes and the like) is indexed
    # against the mod's import table, which we just replaced with vanilla's.
    # Graft those imports over and repoint the rows at their new slots.
    grafted = graft_imports(out, mod["Imports"], added)

    # Vanilla keeps names referenced by export data at the front of the map and
    # counts them in the header; new names belong in that block, not after it.
    name_map = out["NameMap"]
    known = set(name_map)
    mod_names = set(mod["NameMap"])
    fresh = []
    for row in added:
        for name in sorted(names_for(row, mod_names)):
            if name not in known:
                known.add(name)
                fresh.append(name)

    # A rebase adds rows; it must never end up pointing at fewer real assets than
    # the mod table it started from.
    before = count_live_refs(mod["Exports"][0]["Table"]["Data"])
    after = count_live_refs(out["Exports"][0]["Table"]["Data"])
    if after < before:
        raise SystemExit(f"lost asset references: mod table had {before} live soft "
                         f"refs, rebased table has {after}")

    for entry in grafted:
        for field in ("ObjectName", "ClassPackage", "ClassName"):
            name = fname_base(entry[field])
            if name and name not in known:
                known.add(name)
                fresh.append(name)

    boundary = out["NamesReferencedFromExportDataCount"]
    out["NameMap"] = name_map[:boundary] + fresh + name_map[boundary:]
    out["NamesReferencedFromExportDataCount"] = boundary + len(fresh)

    return out, len(vanilla_rows), len(added)


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    vanilla_path, mod_path, out_path = sys.argv[1:]

    with open(vanilla_path, "r", encoding="utf-8") as f:
        vanilla = json.load(f)
    with open(mod_path, "r", encoding="utf-8") as f:
        mod = json.load(f)

    if vanilla["Exports"][0]["$type"].startswith("UAssetAPI.ExportTypes.RawExport"):
        sys.exit(f"{vanilla_path} did not parse as a DataTable -- wrong usmap.")
    if mod["Exports"][0]["$type"].startswith("UAssetAPI.ExportTypes.RawExport"):
        sys.exit(f"{mod_path} did not parse as a DataTable -- wrong usmap.")

    out, kept, added = rebase(vanilla, mod)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"{out_path}: {kept} vanilla rows + {added} mod rows")


def demo():
    imports = [
        {"ObjectName": "2JZ320HP", "OuterIndex": -2},
        {"ObjectName": "/Game/Cars/Parts/Engine/2JZ320HP", "OuterIndex": 0},
    ]
    old = {"$type": "UAssetAPI.PropertyTypes.Structs.StructPropertyData, UAssetAPI", "Name": "2JZ320HP", "Value": [
        {"$type": "UAssetAPI.PropertyTypes.Objects.ObjectPropertyData, UAssetAPI", "Name": "EngineAsset", "Value": -1},
        {"$type": "UAssetAPI.PropertyTypes.Objects.ObjectPropertyData, UAssetAPI", "Name": "LSDAsset", "Value": 0},
        {"$type": "UAssetAPI.PropertyTypes.Structs.StructPropertyData, UAssetAPI", "Name": "Tire",
         "StructType": "MTVehiclePartTire", "Value": [
             {"$type": "UAssetAPI.PropertyTypes.Objects.ObjectPropertyData, UAssetAPI",
              "Name": "TirePhysicsDataAsset", "Value": -1}]},
    ]}
    default = {"$type": "UAssetAPI.PropertyTypes.Objects.BoolPropertyData, UAssetAPI",
               "Name": "bTruckClassIncludeNone", "Value": True}
    soft_names = {"EngineAsset", "LSDAsset", "TirePhysicsDataAsset"}
    row = convert_row(old, imports, [default], soft_names)
    by_name = {p["Name"]: p for p in row["Value"]}
    assert by_name["EngineAsset"]["$type"].startswith("UAssetAPI.PropertyTypes.Objects.SoftObjectPropertyData")
    assert by_name["EngineAsset"]["Value"]["AssetPath"] == {
        "$type": "UAssetAPI.PropertyTypes.Objects.FTopLevelAssetPath, UAssetAPI",
        "PackageName": "/Game/Cars/Parts/Engine/2JZ320HP", "AssetName": "2JZ320HP"}
    assert by_name["LSDAsset"]["Value"]["AssetPath"]["PackageName"] == "None"
    assert by_name["bTruckClassIncludeNone"]["Value"] is True
    # nested soft refs are converted too, not just the row-level ones
    nested = by_name["Tire"]["Value"][0]
    assert nested["$type"].startswith("UAssetAPI.PropertyTypes.Objects.SoftObjectPropertyData")
    assert nested["Value"]["AssetPath"]["AssetName"] == "2JZ320HP"
    assert soft_property_names(row) == {"EngineAsset", "LSDAsset", "TirePhysicsDataAsset"}

    # Converting an already-converted row must be a no-op, not a wipe.
    assert convert_row(row, imports, [default], soft_names) == row
    assert count_live_refs(row) == 2
    assert names_for(row, set()) == {
        "2JZ320HP", "/Game/Cars/Parts/Engine/2JZ320HP", "None", "MTVehiclePartTire"}
    assert fname_base("LSD_Clutch_2_100_40") == "LSD_Clutch_2_100"
    assert fname_base("EF6_4106") == "EF6"
    assert fname_base("2JZ320HP") == "2JZ320HP"
    assert fname_base("Cargos_01") == "Cargos_01"  # leading zero is not a number suffix

    # A hard mesh ref in a mod row gets its import (and the import's package)
    # copied over, and is repointed at the new slot.
    vanilla = {"NameMap": ["None"], "NamesReferencedFromExportDataCount": 1,
               "Imports": [{"ObjectName": "DataTable", "ClassPackage": "/Script/CoreUObject",
                            "ClassName": "Class", "OuterIndex": 0}],
               "Exports": [{"CreateBeforeSerializationDependencies": [],
                            "Table": {"Data": [{"Name": "Stock", "Value": [default]}]}}]}
    mod = {"NameMap": ["BT2", "/Game/Cars/Parts/Tire/BigTire", "BigTire"], "Imports": [
        {"ObjectName": "BigTire", "ClassPackage": "/Script/Engine", "ClassName": "StaticMesh", "OuterIndex": -2},
        {"ObjectName": "/Game/Cars/Parts/Tire/BigTire", "ClassPackage": "/Script/CoreUObject",
         "ClassName": "Package", "OuterIndex": 0}],
        "Exports": [{"Table": {"Data": [
            {"Name": "BT2", "Value": [
                {"$type": "UAssetAPI.PropertyTypes.Objects.ObjectPropertyData, UAssetAPI",
                 "Name": "TireMesh", "Value": -1}]}]}}]}
    merged, kept, added_n = rebase(vanilla, mod)
    assert (kept, added_n) == (1, 1)
    mesh = {p["Name"]: p for p in merged["Exports"][0]["Table"]["Data"][1]["Value"]}["TireMesh"]
    assert mesh["Value"] == -3, mesh["Value"]
    assert merged["Imports"][1]["ObjectName"] == "/Game/Cars/Parts/Tire/BigTire"  # outer first
    assert merged["Imports"][2]["ObjectName"] == "BigTire"
    assert merged["Imports"][2]["OuterIndex"] == -2

    # 0.7.20: flat turbo fields move into both new fuel sub-structs.
    S = "UAssetAPI.PropertyTypes.Structs.StructPropertyData, UAssetAPI"
    F = "UAssetAPI.PropertyTypes.Objects.FloatPropertyData, UAssetAPI"
    old_turbo = {"$type": S, "Name": "Turbocharger", "Value": [
        {"$type": F, "Name": "bIsValid", "Value": True},
        {"$type": F, "Name": "TorqueMultiplier", "Value": 1.5}]}
    new_turbo = {"$type": S, "Name": "Turbocharger", "Value": [
        {"$type": F, "Name": "bIsValid", "Value": False},
        *({"$type": S, "Name": fuel, "Value": [{"$type": F, "Name": "TorqueMultiplier", "Value": 1.0}]}
          for fuel in ("Gasoline", "Diesel"))]}
    turbo = convert_row({"Name": "T", "Value": [old_turbo]}, [], [new_turbo], set())["Value"][0]
    assert turbo["Value"][0]["Value"] is True
    assert [s["Value"][0]["Value"] for s in turbo["Value"][1:]] == [1.5, 1.5]
    try:
        convert_row({"Name": "T", "Value": [{"$type": S, "Name": "Turbocharger", "Value": [
            {"$type": F, "Name": "Gone", "Value": 1}]}]}, [], [new_turbo], set())
        raise AssertionError("a field with nowhere to go must fail")
    except SystemExit:
        pass
    assert merged["Exports"][0]["CreateBeforeSerializationDependencies"] == [-3]
    assert "/Game/Cars/Parts/Tire/BigTire" in merged["NameMap"]
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main()
