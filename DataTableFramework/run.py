"""DataTableFramework: an optional compat layer that merges every mod's own tables.

A composite is a list of parent tables, and only one copy of it can win. So each
mod is standalone: it ships its OWN table (<Composite>_<Mod>, e.g.
/Game/DataAsset/VehicleParts/VehicleParts_MoreTuning) and its OWN copy of the
composite -- vanilla's parents plus its table, plus the tables of mods it depends
on (write_composite). Alone, it works. Several mods together knock each other's
copies out -- that is what this fixes.

The framework ships each of the 14 composites once: vanilla's parents, then every
registered mod table (registry.json "adopted"), in registry order -- later wins a
same-named row. Nothing else: no stubs, no channels. Its pak must beat every mod's
copy: it is AAAA_DataTableFramework_99_P, and the chunk number 99 is what does it --
UE ranks a _N_P pak by N before its name, so it outranks every mod pak (plain _P is
chunk 1, and some mods already use _1_P / _2_P) although it sorts first.

A registered table whose mod is not installed is simply absent; the composite
then has a parent that does not exist, and the game has to skip it.
shortcut: that is unverified until the lab test (lab_missing_parent.py) has run
in game -- if it fails, absent mods need stubs in a separate first-loading pak.
A mod that ships no table of its own -- one frozen copy of a vanilla
table (Teh's 0.7.18 Engines, Suspension Expansion's Suspensions) -- needs nothing
here: the framework lists the vanilla table, the copy replaces it.

    python DataTableFramework/run.py                 # every composite
    python DataTableFramework/run.py VehicleParts    # just these
    python DataTableFramework/run.py demo
"""
import copy
import json
import os
import shutil
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from pipeline import VANILLA, from_json, register_names, to_json  # noqa: E402
from rebase import fname_base  # noqa: E402

PAK = "AAAA_DataTableFramework_99_P"
MOD = os.path.join(HERE, "..", PAK, "MotorTown", "Content")
REGISTRY = os.path.join(HERE, "registry.json")
MANIFEST = os.path.join(HERE, "composites.json")
WORK = os.path.join(HERE, "..", "Rebase", "work", "fw")
MARKER = b"Default__CompositeDataTable"


def game_path_to_file(package):
    assert package.startswith("/Game/"), package
    return os.path.join(VANILLA, *package[len("/Game/"):].split("/")) + ".uasset"


def discover():
    """Every vanilla asset whose own export is a CompositeDataTable -> (name, file)."""
    found = []
    for dirpath, _, files in os.walk(VANILLA):
        for f in files:
            if f.endswith(".uasset"):
                path = os.path.join(dirpath, f)
                with open(path, "rb") as fh:
                    if MARKER in fh.read():
                        found.append((f[: -len(".uasset")], path))
    return sorted(found)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(table, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=2)


def imp(table, index):
    return table["Imports"][-index - 1]


def is_composite(table):
    e = table["Exports"][0]
    return (e["$type"].startswith("UAssetAPI.ExportTypes.DataTableExport")
            and imp(table, e["ClassIndex"])["ObjectName"] == "CompositeDataTable")


def props(export):
    return {p["Name"]: p for p in export["Data"]}


def parents(table):
    """Parent tables as package paths, in priority order."""
    out = []
    for p in props(table["Exports"][0])["ParentTables"]["Value"]:
        obj = imp(table, p["Value"])
        out.append(imp(table, obj["OuterIndex"])["ObjectName"])
    return out


def add_import(table, obj, outer, cls_pkg, cls):
    table["Imports"].append({"$type": "UAssetAPI.Import, UAssetAPI", "ObjectName": obj,
                             "OuterIndex": outer, "ClassPackage": cls_pkg, "ClassName": cls,
                             "PackageName": None, "bImportOptional": False})
    return -len(table["Imports"])


def make_table(source, package, rows):
    """A table at `package` holding `rows`, built on the table they came from.

    Keeping the source's imports is what keeps any hard references in the rows
    valid; the names the rows use are already in its NameMap. This is how a mod's
    own table is built.
    """
    name = package.rsplit("/", 1)[1]
    table = copy.deepcopy(source)
    table["FolderName"] = package
    table["PackageGuid"] = "{" + str(uuid.uuid4()).upper() + "}"
    e = table["Exports"][0]
    e["ObjectName"] = name
    e["Table"]["Data"] = rows
    register_names(table, [r["Name"] for r in rows] + [package, name])
    table["Generations"][0]["NameCount"] = len(table["NameMap"])
    return table


def write_table(table, package, mod_content):
    """Build a table into <mod_content>/<package path> and check it reads back.

    Returns the read-back JSON's path, for verify.py.
    """
    assert package.startswith("/Game/"), package
    name = package[len("/Game/"):].replace("/", "_")  # unique per path
    work = os.path.join(WORK, "tables")
    os.makedirs(work, exist_ok=True)
    src = os.path.join(work, f"{name}.mod.json")
    save(table, src)
    out = os.path.join(mod_content, *package[len("/Game/"):].split("/")) + ".uasset"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    built = from_json(src, out)
    struct = imp(table, props(table["Exports"][0])["RowStruct"]["Value"])["ObjectName"]
    check = os.path.join(work, f"{name}.mod.check.json")
    check_table(built, struct, len(table["Exports"][0]["Table"]["Data"]), check)
    return check


def add_parents(comp_table, packages):
    """Append these tables to ParentTables, after every vanilla parent, in order."""
    e = comp_table["Exports"][0]
    plist = props(e)["ParentTables"]["Value"]
    template = imp(comp_table, plist[0]["Value"])
    names = []
    for pkg in packages:
        name = pkg.rsplit("/", 1)[1]
        outer = add_import(comp_table, pkg, 0, "/Script/CoreUObject", "Package")
        obj = add_import(comp_table, name, outer, template["ClassPackage"],
                         template["ClassName"])
        entry = copy.deepcopy(plist[0])
        entry["Name"] = str(len(plist))
        entry["Value"] = obj
        plist.append(entry)
        e["SerializationBeforeSerializationDependencies"].append(obj)
        names += [fname_base(pkg), fname_base(name)]
    # Import names are not export-referenced, so they go after the boundary.
    existing = set(comp_table["NameMap"])
    for n in names:
        if n not in existing:
            existing.add(n)
            comp_table["NameMap"].append(n)
    comp_table["Generations"][0]["NameCount"] = len(comp_table["NameMap"])


def adopted(comp):
    with open(REGISTRY, encoding="utf-8") as f:
        return list(json.load(f)["adopted"].get(comp, {}))


def check_table(path, expect_struct, expect_rows=0, out=None):
    t = load(to_json(path, out or path[: -len(".uasset")] + ".check.json"))
    e = t["Exports"][0]
    if not e["$type"].startswith("UAssetAPI.ExportTypes.DataTableExport"):
        sys.exit(f"FAIL: {path} read back as {e['$type']}")
    got = imp(t, props(e)["RowStruct"]["Value"])["ObjectName"]
    if got != expect_struct or len(e["Table"]["Data"]) != expect_rows:
        sys.exit(f"FAIL: {path}: struct {got}, {len(e['Table']['Data'])} rows")
    return t




def write_composite(comp_table, src_file, packages, mod_content, tag):
    """comp_table (vanilla's composite) + packages after its parents, written at the
    composite's own path under mod_content and read back. Returns the parent list."""
    table = copy.deepcopy(comp_table)
    add_parents(table, packages)
    tmp = os.path.join(WORK, f"{os.path.basename(src_file)[:-7]}.{tag}.json")
    os.makedirs(WORK, exist_ok=True)
    save(table, tmp)
    dest = os.path.join(mod_content, os.path.relpath(src_file, VANILLA))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    from_json(tmp, dest)
    back = load(to_json(dest, tmp[:-5] + ".check.json"))
    if not is_composite(back) or parents(back) != parents(table):
        sys.exit(f"FAIL: {dest} did not read back as the composite with its parents")
    return parents(table)


def composite(comp):
    """Vanilla's copy of a composite -> (table, file), via the manifest run.py writes."""
    entry = next((m for m in json.load(open(MANIFEST, encoding="utf-8")) if m["composite"] == comp), None) \
        if os.path.isfile(MANIFEST) else None
    path = game_path_to_file(entry["path"]) if entry else dict(discover()).get(comp)
    if not path:
        sys.exit(f"FAIL: no composite called {comp}")
    return load(to_json(path, os.path.join(WORK, comp + ".vanilla.json"))), path


def mod_composite(comp, packages, mod_content):
    """A mod's own copy of `comp`: vanilla's parents, then its own table(s) -- and the
    tables of mods it builds on, first. What makes a mod work without the framework."""
    table, path = composite(comp)
    got = write_composite(table, path, packages, mod_content, "own")
    print(f"  own {comp} composite: {len(got) - len(packages)} vanilla parents + "
          + ", ".join(p.rsplit("/", 1)[1] for p in packages))


def build(comp, comp_file):
    """The framework's copy: vanilla's parents + every registered table of this composite."""
    os.makedirs(WORK, exist_ok=True)
    table = load(to_json(comp_file, os.path.join(WORK, comp + ".vanilla.json")))
    if not is_composite(table):
        print(f"  skip {comp}: not a CompositeDataTable export")
        return None
    vanilla_parents = parents(table)
    struct = imp(table, props(table["Exports"][0])["RowStruct"]["Value"])["ObjectName"]
    theirs = adopted(comp)
    write_composite(table, comp_file, theirs, MOD, "framework")
    print(f"  {comp}: {struct}, {len(vanilla_parents)} vanilla parents + {len(theirs)} mod tables")
    rel = os.path.relpath(comp_file, VANILLA)
    return {"composite": comp, "path": "/Game/" + rel[: -len(".uasset")].replace(os.sep, "/"),
            "row_struct": struct, "vanilla_parents": vanilla_parents, "mod_tables": theirs}


def demo():
    t = {"Imports": [], "NameMap": [], "Generations": [{"NameCount": 0}],
         "Exports": [{"SerializationBeforeSerializationDependencies": [], "Data": []}]}
    pkg = add_import(t, "/Game/DataAsset/VehicleParts/Engines", 0, "/Script/CoreUObject", "Package")
    obj = add_import(t, "Engines", pkg, "/Script/Engine", "DataTable")
    t["Exports"][0]["Data"] = [{"Name": "ParentTables", "Value": [{"Name": "0", "Value": obj}]}]
    add_parents(t, ["/Game/DataAsset/VehicleParts/VehicleParts_MoreTuning",
                    "/Game/DataAsset/VehicleParts/VehicleParts_MoreTuningNoLimits"])
    assert parents(t) == ["/Game/DataAsset/VehicleParts/Engines",
                          "/Game/DataAsset/VehicleParts/VehicleParts_MoreTuning",
                          "/Game/DataAsset/VehicleParts/VehicleParts_MoreTuningNoLimits"], parents(t)
    assert "VehicleParts_MoreTuning" in t["NameMap"] and t["Generations"][0]["NameCount"] == len(t["NameMap"])
    assert PAK.endswith("_99_P"), "the framework must outrank every mod pak's composite copy"
    print("demo ok")


def main(argv):
    if argv[:1] == ["demo"]:
        return demo()
    wanted = set(argv)
    os.makedirs(WORK, exist_ok=True)
    if not wanted:
        shutil.rmtree(MOD, ignore_errors=True)
    manifest = []
    for comp, path in discover():
        if wanted and comp not in wanted:
            continue
        print(f"=== {comp}")
        info = build(comp, path)
        if info:
            manifest.append(info)
    if not wanted:
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    main(sys.argv[1:])
