"""MoreTuning, No Limits and Carbon as their own VehicleParts tables, listed by the DataTableFramework.

    python Rebase/channels.py          # all three
    python Rebase/channels.py demo

None of the three overrides a vanilla table. Each ships its own table and its own
copy of the VehicleParts composite, so it works without the DataTableFramework;
with it, the framework lists every mod's table by name (registry.json "adopted")
and overrides all the copies. No Limits builds on MoreTuning and Carbon on both,
so their copies list those tables too -- and since the paks load in that order
(_P < xNoLimits < yCarbon), the last copy standing lists all three:

    VehicleParts_MoreTuning          its own rows from every table, plus the vanilla
                                     rows it changes (Motor Works' edits, then the
                                     vehicle gates stripped)
    VehicleParts_MoreTuningNoLimits  every body part and headlight, VehicleKeys gone
    VehicleParts_MoreTuningCarbon    the _Carbon twins only

Rows from different tables share one import table: each source's hard
references are grafted across (rebase.graft_imports). Later parents win a
same-named row, and the registry lists them in that order, so it is also the
priority: No Limits overrides
MoreTuning's own aero rows as well as vanilla's.

The mod's own rows are read from Rebase/old/<version>/ -- the tables as last
shipped -- with the usmap they were built with, and rebased exactly as
rebuild.py always did.

Maja's Motor Works is a hard dependency and ships inside MoreTuning: her 7 rows
are in its own tables, her hitch mesh is in qxZap_MoreTuning_P, and her edits to
vanilla rows (motorworks.py) are applied to vanilla before anything here builds
on it -- so No Limits and Carbon carry them too.
"""
import copy
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pipeline import (CARBON, MOD, NOLIMITS, REPO, VANILLA, WORK,  # noqa: E402
                      register_names, table_path, to_json)
from rebase import fname_base, fnames_in, graft_imports, rebase  # noqa: E402
import motorworks  # noqa: E402
import paint  # noqa: E402
import importlib.util  # noqa: E402


# Three of the tools are each called run.py; load them by path so `run` stays
# RemoveReq's, which is what CarbonParts imports under that name.
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


framework = _load("dtframework", os.path.join(REPO, "DataTableFramework", "run.py"))
sys.path.insert(0, os.path.join(REPO, "RemoveReq"))
removereq = _load("removereq", os.path.join(REPO, "RemoveReq", "run.py"))
carbon = _load("carbonparts", os.path.join(REPO, "CarbonParts", "run.py"))

PREVIOUS_MAPPINGS = "MotorTown719"
OLD = os.path.join(HERE, "old", "0.7.19")
COMP = "VehicleParts"

TABLES = "/Game/DataAsset/VehicleParts/"
MORETUNING, NOLIMITS_T, CARBON_T = (TABLES + "VehicleParts_MoreTuning", TABLES + "VehicleParts_MoreTuningNoLimits",
                                    TABLES + "VehicleParts_MoreTuningCarbon")
OWN = ["Engines", "Transmissions", "LSD", "AeroParts", "VehicleParts0"]
OVERRIDES = ["Engines", "License", "License_OversizeEscort", "VehicleParts0", "AeroParts",
             "Transmissions"]
# "No X" mesh-less parts, retired: VehicleLabs makes these types uninstallable instead
# (vehicle_mod/tables.py OPTIONAL). A car wearing one loses it, leaving the slot empty.
RETIRED = {"No_Bonnet", "No_Roof", "No_Front_Bumper", "No_Rear_Bumper", "No_Fender",
           "No_SideSkirt", "No_Headlight"}
# Not Wheels: an override there sits above Maja's Mo Wheel Works and puts vanilla
# meshes back on all 93 of her rows. Motor Works only unlocks wheels, and Wheel
# Works does that itself.
NOLIMIT_TABLES = ["AeroParts", "Headlights"]
CARBON_TABLES = ["AeroParts", "Headlights", "Wheels"]


def rows_of(table):
    return table["Exports"][0]["Table"]["Data"]


def vanilla(name):
    return framework.load(to_json(table_path(VANILLA, name),
                                  os.path.join(WORK, name + ".vanilla720.json")))


def base(name):
    """0.7.20 vanilla with Motor Works' edits on it -> (table, names of rows she edited)."""
    table = vanilla(name)
    deltas = motorworks.load_deltas()
    motorworks.apply(name, table, deltas)
    return table, set(deltas.get(name, {})) & {r["Name"] for r in rows_of(table)}


def ship(table, package, dest, label):
    """Build `table` at `package` (a mod's own table) into dest."""
    register_names(table, [x for r in rows_of(table) for x in fnames_in(r)])
    check = framework.write_table(table, package, dest)
    subprocess.run([sys.executable, os.path.join(HERE, "verify.py"), check, dest, MOD, VANILLA],
                   check=True)
    print(f"  {package.rsplit('/', 1)[1]} {label}: {len(rows_of(table))} rows")


def changed_only(rows, edit):
    """Copies of the rows `edit` actually changes -- an override channel carries no more."""
    out = []
    for row in rows:
        row = copy.deepcopy(row)
        if edit(row):
            out.append(row)
    return out


def strip_gates(row):
    changed = removereq.strip_row(row)
    return removereq.unlock_winches([row]) > 0 or changed


def nolimits(row):
    changed = removereq.strip_row(row, removereq.NOLIMIT_GATES)
    return removereq.rename_numbered(row) or changed


def paint_templates():
    """A ColorSlots pair for its JSON shape, and the antennas' slot as its content."""
    aero = vanilla("AeroParts")
    pair = next(p["Value"][0] for r in rows_of(aero) for p in r["Value"]
                if p["Name"] == "ColorSlots" and p["Value"])
    items = framework.load(to_json(os.path.join(VANILLA, "DataAsset", "Items",
                                                "Items_AttachmentPart.uasset"),
                                   os.path.join(WORK, "Items_AttachmentPart.vanilla720.json")))
    slot = next(s for r in rows_of(items) for p in r["Value"]
                if p["Name"] == "AttachmentPaintSlots" and p["Value"]
                for s in p["Value"][0]["Value"] if s["Name"] == "Slot")
    return pair, slot["Value"]


def painter(table, templates):
    """An edit giving a part one ColorSlot per M_Body slot of its mesh, if it has none.

    No Limits and Carbon put parts on cars they were not made for, where the
    car's own slot names rarely line up with the part's -- see paint.py.
    """
    def add_paint(row):
        slots = next((p for p in row["Value"] if p["Name"] == "ColorSlots"), None)
        mesh = paint.mesh_of(table, row)
        if slots is None or slots["Value"] or not mesh:
            return False
        names = paint.body_slots(mesh[0])
        slots["Value"] = paint.color_slot_entries(names, *templates)
        return bool(names)
    return add_paint


def own_rows(name):
    """MoreTuning's rows of one table, rebased onto 0.7.20 -> (merged table, rows)."""
    van, _ = base(name)
    old = framework.load(to_json(table_path(OLD, name), os.path.join(WORK, name + ".old.json"),
                                 PREVIOUS_MAPPINGS))
    merged, kept, added = rebase(van, old)
    vanilla_now = {r["Name"] for r in rows_of(van)}
    before = previous_vanilla(name)
    collided = sorted(r["Name"] for r in rows_of(old)
                      if r["Name"] in vanilla_now and r["Name"] not in before)
    if collided:
        print(f"  WARNING {name}: vanilla now has rows the mod also defines, vanilla's kept: "
              f"{collided[:10]}")
    # A row vanilla now has in ANY parent is vanilla's: 0.7.20 moved the taxi
    # licences from VehicleParts0 into License, and our 0.7.19 copies would win.
    moved = vanilla_composite_names() - vanilla_now
    # out of the merged table itself: No Limits and Carbon are built from it
    retired = [r["Name"] for r in rows_of(merged)[kept:] if r["Name"] in RETIRED]
    if retired:
        rows_of(merged)[kept:] = [r for r in rows_of(merged)[kept:] if r["Name"] not in RETIRED]
        added -= len(retired)
        print(f"  {name}: retired {sorted(retired)}")
    rows = [r for r in rows_of(merged)[kept:] if r["Name"] not in moved]
    if added != len(rows):
        print(f"  {name}: dropped {added - len(rows)} rows vanilla now has in another table: "
              f"{sorted(r['Name'] for r in rows_of(merged)[kept:] if r['Name'] in moved)}")
    for r in rows:
        removereq.strip_row(r)
    return merged, rows


_composite_names = None


def vanilla_composite_names():
    """Every row name in vanilla's VehicleParts composite (its cooked row cache)."""
    global _composite_names
    if _composite_names is None:
        t = framework.load(to_json(os.path.join(VANILLA, "DataAsset", "VehicleParts", "VehicleParts.uasset"),
                                   os.path.join(WORK, "VehicleParts.composite720.json")))
        _composite_names = {r["Name"] for r in rows_of(t)}
    return _composite_names


def previous_vanilla(name):
    """Row names vanilla had when the mod was last built, to tell a collision from a copy."""
    table = framework.load(to_json(table_path(motorworks.BASELINE, name),
                                   os.path.join(WORK, name + ".vanilla719.json"),
                                   PREVIOUS_MAPPINGS))
    return {r["Name"] for r in rows_of(table)}


def combine(parts):
    """One channel table from [(source table, rows)]: the first source's imports,
    with every other source's hard references grafted in."""
    base_table, first = parts[0]
    out = copy.deepcopy(base_table)
    rows = copy.deepcopy(first)
    for source, more in parts[1:]:
        more = copy.deepcopy(more)  # graft repoints them; the sources stay reusable
        grafted = graft_imports(out, source["Imports"], more)
        register_names(out, [fname_base(e[k]) for e in grafted
                             for k in ("ObjectName", "ClassPackage", "ClassName")])
        rows += more
    names = [r["Name"] for r in rows]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        sys.exit(f"FAIL: rows defined twice in one channel: {dupes[:10]}")
    return out, rows


def ship_one(parts, package, dest, label, needs=()):
    """One table from several sources, plus the mod's own copy of the composite listing
    vanilla, the tables of mods it builds on (`needs`) and its own -- so it works without
    the framework. Clears dest's DataTableFramework/ -- channel files from before."""
    import shutil
    shutil.rmtree(os.path.join(dest, "DataTableFramework"), ignore_errors=True)
    table, rows = combine([p for p in parts if p[1]])
    ship(framework.make_table(table, package, rows), package, dest, label)
    framework.mod_composite(COMP, [*needs, package], dest)


def main():
    os.makedirs(WORK, exist_ok=True)
    merged, parts = {}, []
    print("=== MoreTuning (qxZap_MoreTuning_P)")
    for name in OWN:
        merged[name], rows = own_rows(name)
        parts.append((merged[name], rows))
        print(f"  {name}: {len(rows)} own rows")
    for name in OVERRIDES:
        table, edited = base(name)
        rows = [r for r in rows_of(table)
                if (name in removereq.TABLES and strip_gates(r)) | (r["Name"] in edited)]
        parts.append((table, rows))
        print(f"  {name}: {len(rows)} vanilla rows changed ({len(edited)} by Motor Works)")
    ship_one(parts, MORETUNING, MOD, "MoreTuning")

    print("=== No Limits (qxZap_MoreTuning_xNoLimits_P)")
    templates = paint_templates()
    parts = []
    for name in NOLIMIT_TABLES:
        source = merged.get(name) or base(name)[0]
        add_paint = painter(source, templates)
        parts.append((source, changed_only(rows_of(source), lambda r: nolimits(r) | add_paint(r))))
    ship_one(parts, NOLIMITS_T, NOLIMITS, "No Limits", needs=[MORETUNING])

    print("=== Carbon (qxZap_MoreTuning_yCarbon_P)")
    parts = []
    for name in CARBON_TABLES:
        source = merged.get(name) or base(name)[0]
        twins = [t for t in (carbon.carbon_twin(r) for r in rows_of(source)
                             if not r["Name"].endswith(carbon.SUFFIX)) if t]
        add_paint = painter(source, templates)
        for t in twins:
            add_paint(t)
        parts.append((source, twins))
    ship_one(parts, CARBON_T, CARBON, "Carbon twins", needs=[MORETUNING, NOLIMITS_T])
    print("\nPack: qxZap_MoreTuning_P, qxZap_MoreTuning_xNoLimits_P, qxZap_MoreTuning_yCarbon_P"
          " (AAAA_DataTableFramework_P must be installed)")


def demo():
    row = {"Name": "Bumper", "Value": [
        {"Name": "VehicleKeys", "Value": ["Vista"]},
        {"Name": "VehicleTypes", "Value": []}]}
    untouched = {"Name": "Free", "Value": [{"Name": "VehicleKeys", "Value": []}]}
    out = changed_only([row, untouched], nolimits)
    assert [r["Name"] for r in out] == ["Bumper"] and out[0]["Value"][0]["Value"] == []
    assert row["Value"][0]["Value"] == ["Vista"], "source rows must stay untouched"
    assert changed_only([row], strip_gates) == [], "base strip leaves VehicleKeys alone"
    listed = list(framework.adopted(COMP))  # the composite lists them in registry order: later wins
    assert all(t in listed for t in (MORETUNING, NOLIMITS_T, CARBON_T)), "register the tables in registry.json"
    assert listed.index(MORETUNING) < listed.index(NOLIMITS_T) < listed.index(CARBON_T), \
        "No Limits must override MoreTuning's rows, Carbon both"
    # Two tables, one channel: the second's hard ref is re-pointed into the first.
    a = {"Imports": [{"ObjectName": "/Game/A", "ClassPackage": "/Script/CoreUObject",
                      "ClassName": "Package", "OuterIndex": 0}],
         "NameMap": [], "NamesReferencedFromExportDataCount": 0,
         "Exports": [{"CreateBeforeSerializationDependencies": []}]}
    b = {"Imports": [{"ObjectName": "Mesh", "ClassPackage": "/Script/Engine", "ClassName": "StaticMesh",
                      "OuterIndex": -2},
                     {"ObjectName": "/Game/B", "ClassPackage": "/Script/CoreUObject",
                      "ClassName": "Package", "OuterIndex": 0}]}
    ref = {"$type": "UAssetAPI.PropertyTypes.Objects.ObjectPropertyData, UAssetAPI", "Name": "M", "Value": -1}
    out, rows = combine([(a, [{"Name": "R1", "Value": []}]), (b, [{"Name": "R2", "Value": [ref]}])])
    assert [r["Name"] for r in rows] == ["R1", "R2"] and ref["Value"] == -1, "sources untouched"
    assert out["Imports"][rows[1]["Value"][0]["Value"] * -1 - 1]["ObjectName"] == "Mesh"
    assert "/Game/B" in out["NameMap"]
    print("ok")


if __name__ == "__main__":
    demo() if sys.argv[1:] == ["demo"] else main()
