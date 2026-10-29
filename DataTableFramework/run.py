"""DataTableFramework: every composite DataTable, shipped once, with N empty channels.

A composite is a list of parent tables. Mods that add rows used to ship their own
copy of the composite to append one parent, and only one copy can win. This
ships each composite once with its vanilla parents plus channel tables
/Game/DataTableFramework/<Composite>/Ch0001..ChNNNN, all empty. A mod overrides
the one channel file it claims; the pak is AAAA_ so it mounts first and every
channel a mod ships beats the stub.

The cost of one pak mounting first: a mod that still ships its own composite
copy beats ours and switches every channel off. Such a mod has to drop the copy
-- its 0.7.19 copies lack 0.7.20's new parents anyway (Horns, RoofRacks,
CargoBedAttachments). Tables those mods add (registry.json "adopted") are
listed as parents already, with an empty stub at each path, so dropping the
copy is the only change they need.

Parents later in the list override earlier ones row-for-row, so channels come
after vanilla and a higher channel beats a lower one.

    python DataTableFramework/run.py                 # all composites, 1000 channels
    python DataTableFramework/run.py --channels 10 VehicleParts
    python DataTableFramework/run.py demo

Channels are ChNNNN, not Ch_NNNN: Ch_1000 is stored as FName (Ch, 1000) and the
NameMap lookup for the whole string misses. Ch0001.. keep the same length, which
is what lets one built stub be cloned by swapping the name in place -- UE throws
the serialized name hashes away on load, and the read-back below proves the
clone parses.
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

MOD = os.path.join(HERE, "..", "AAAA_DataTableFramework_P", "MotorTown", "Content")
REGISTRY = os.path.join(HERE, "registry.json")
WORK = os.path.join(HERE, "..", "Rebase", "work", "fw")
ROOT = "/Game/DataTableFramework"
MARKER = b"Default__CompositeDataTable"


def channel(n):
    return f"Ch{n:04d}"


def channel_package(comp, n):
    return f"{ROOT}/{comp}/{channel(n)}"


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


def make_stub(parent, package):
    """An empty DataTable with the parent's RowStruct, importing nothing else."""
    e = parent["Exports"][0]
    struct = imp(parent, props(e)["RowStruct"]["Value"])
    struct_pkg = imp(parent, struct["OuterIndex"])["ObjectName"]
    name = package.rsplit("/", 1)[1]

    stub = copy.deepcopy(parent)
    stub["Imports"] = []
    engine = add_import(stub, "/Script/Engine", 0, "/Script/CoreUObject", "Package")
    cls = add_import(stub, "DataTable", engine, "/Script/CoreUObject", "Class")
    default = add_import(stub, "Default__DataTable", engine, "/Script/Engine", "DataTable")
    spkg = engine if struct_pkg == "/Script/Engine" else \
        add_import(stub, struct_pkg, 0, "/Script/CoreUObject", "Package")
    row_struct = add_import(stub, struct["ObjectName"], spkg, "/Script/CoreUObject",
                            "ScriptStruct")

    stub["NameMap"] = sorted({fname_base(package), "/Script/CoreUObject", "/Script/Engine",
                              struct_pkg, "Class", "DataTable", "Default__DataTable", "Package",
                              "ScriptStruct", fname_base(name), struct["ObjectName"]})
    stub["NamesReferencedFromExportDataCount"] = 0
    stub["Generations"] = [{"$type": "UAssetAPI.FGenerationInfo, UAssetAPI",
                            "ExportCount": 1, "NameCount": len(stub["NameMap"])}]
    stub["FolderName"] = package
    stub["PackageGuid"] = "{" + str(uuid.uuid4()).upper() + "}"
    stub["SoftObjectPathList"] = []
    stub["DependsMap"] = [[]]
    se = stub["Exports"][0]
    se.update(ObjectName=name, ClassIndex=cls, TemplateIndex=default,
              SerializationBeforeSerializationDependencies=[row_struct],
              CreateBeforeSerializationDependencies=[],
              SerializationBeforeCreateDependencies=[cls, default],
              CreateBeforeCreateDependencies=[])
    for p in se["Data"]:
        if p["Name"] == "RowStruct":
            p["Value"] = row_struct
    se["Table"]["Data"] = []
    return stub


def make_channel(source, comp, n, rows):
    """A channel table holding `rows`, built on the vanilla table they came from.

    Keeping the source's imports is what keeps any hard references in the rows
    valid; the names the rows use are already in its NameMap.
    """
    table = copy.deepcopy(source)
    package = channel_package(comp, n)
    table["FolderName"] = package
    table["PackageGuid"] = "{" + str(uuid.uuid4()).upper() + "}"
    e = table["Exports"][0]
    e["ObjectName"] = channel(n)
    e["Table"]["Data"] = rows
    register_names(table, [r["Name"] for r in rows] + [package, channel(n)])
    table["Generations"][0]["NameCount"] = len(table["NameMap"])
    return table


def write_channel(table, comp, n, mod_content):
    """Build a channel table into <mod_content>/DataTableFramework/<comp>/ and check it.

    Returns the read-back JSON's path, for verify.py.
    """
    os.makedirs(os.path.join(WORK, comp), exist_ok=True)
    src = os.path.join(WORK, comp, f"{channel(n)}.mod.json")
    save(table, src)
    out_dir = os.path.join(mod_content, "DataTableFramework", comp)
    os.makedirs(out_dir, exist_ok=True)
    built = from_json(src, os.path.join(out_dir, channel(n) + ".uasset"))
    struct = imp(table, props(table["Exports"][0])["RowStruct"]["Value"])["ObjectName"]
    check = os.path.join(WORK, comp, f"{channel(n)}.mod.check.json")
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


def clone(src_base, dst_base, old, new):
    assert len(old) == len(new)
    for ext in (".uasset", ".uexp"):
        with open(src_base + ext, "rb") as f:
            data = f.read()
        if ext == ".uasset":
            data = data.replace(old.encode(), new.encode())
        with open(dst_base + ext, "wb") as f:
            f.write(data)


def check_table(path, expect_struct, expect_rows=0, out=None):
    t = load(to_json(path, out or path[: -len(".uasset")] + ".check.json"))
    e = t["Exports"][0]
    if not e["$type"].startswith("UAssetAPI.ExportTypes.DataTableExport"):
        sys.exit(f"FAIL: {path} read back as {e['$type']}")
    got = imp(t, props(e)["RowStruct"]["Value"])["ObjectName"]
    if got != expect_struct or len(e["Table"]["Data"]) != expect_rows:
        sys.exit(f"FAIL: {path}: struct {got}, {len(e['Table']['Data'])} rows")
    return t


def build(comp, comp_file, count):
    os.makedirs(os.path.join(WORK, comp), exist_ok=True)
    table = load(to_json(comp_file, os.path.join(WORK, comp + ".vanilla.json")))
    if not is_composite(table):
        print(f"  skip {comp}: not a CompositeDataTable export")
        return None
    vanilla_parents = parents(table)
    struct = imp(table, props(table["Exports"][0])["RowStruct"]["Value"])["ObjectName"]

    parent = load(to_json(game_path_to_file(vanilla_parents[0]),
                          os.path.join(WORK, comp, "parent.json")))
    stub_json = os.path.join(WORK, comp, channel(1) + ".json")
    save(make_stub(parent, channel_package(comp, 1)), stub_json)
    built = from_json(stub_json, os.path.join(WORK, comp, channel(1) + ".uasset"))
    check_table(built, struct)

    out_dir = os.path.join(MOD, "DataTableFramework", comp)
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    for n in range(1, count + 1):
        clone(built[: -len(".uasset")], os.path.join(out_dir, channel(n)),
              channel(1), channel(n))
    # A clone is only as good as its read-back: check the last one, the
    # furthest from the stub UAssetGUI actually wrote.
    check_table(os.path.join(out_dir, channel(count) + ".uasset"), struct)
    os.remove(os.path.join(out_dir, channel(count) + ".check.json"))

    # Adopted tables: a stub at each path, built from the channel stub's JSON.
    theirs = adopted(comp)
    for pkg in theirs:
        stub = os.path.join(WORK, comp, pkg.rsplit("/", 1)[1] + ".json")
        save(make_stub(parent, pkg), stub)
        dest = os.path.join(MOD, *pkg[len("/Game/"):].split("/")) + ".uasset"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        check_table(from_json(stub, dest), struct, 0, stub[:-5] + ".check.json")

    add_parents(table, theirs + [channel_package(comp, n) for n in range(1, count + 1)])
    comp_json = os.path.join(WORK, comp + ".json")
    save(table, comp_json)
    rel = os.path.relpath(comp_file, VANILLA)
    dest = os.path.join(MOD, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    from_json(comp_json, dest)
    back = load(to_json(dest, os.path.join(WORK, comp + ".check.json")))
    if not is_composite(back) or parents(back) != parents(table):
        sys.exit(f"FAIL: {comp} composite did not read back with its channels")
    print(f"  {comp}: {struct}, {len(vanilla_parents)} vanilla parents + {len(theirs)} adopted"
          f" + {count} channels")
    return {"composite": comp, "path": "/Game/" + rel[: -len(".uasset")].replace(os.sep, "/"),
            "row_struct": struct, "vanilla_parents": vanilla_parents, "adopted": theirs,
            "channels": count}


def demo():
    parent = {"Imports": [], "NameMap": [], "Exports": [{"ClassIndex": 0, "Data": [], "Table": {"Data": [1]}}]}
    add_import(parent, "/Script/MotorTown", 0, "/Script/CoreUObject", "Package")
    rs = add_import(parent, "VehiclePartRow", -1, "/Script/CoreUObject", "ScriptStruct")
    parent["Exports"][0]["Data"] = [{"Name": "RowStruct", "Value": rs}]
    stub = make_stub(parent, channel_package("VehicleParts", 7))
    e = stub["Exports"][0]
    assert e["ObjectName"] == "Ch0007" and e["Table"]["Data"] == []
    assert imp(stub, e["Data"][0]["Value"])["ObjectName"] == "VehiclePartRow"
    assert imp(stub, e["ClassIndex"])["ObjectName"] == "DataTable"
    assert "/Game/DataTableFramework/VehicleParts/Ch0007" in stub["NameMap"]
    assert channel(1000) == "Ch1000" and len(channel(1)) == len(channel(1000))
    print("demo ok")


def main(argv):
    if argv[:1] == ["demo"]:
        return demo()
    count = 1000
    if "--channels" in argv:
        i = argv.index("--channels")
        count = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    wanted = set(argv)
    os.makedirs(WORK, exist_ok=True)
    if not wanted:
        shutil.rmtree(MOD, ignore_errors=True)
    manifest = []
    for comp, path in discover():
        if wanted and comp not in wanted:
            continue
        print(f"=== {comp}")
        info = build(comp, path, count)
        if info:
            manifest.append(info)
    with open(os.path.join(HERE, "composites.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    main(sys.argv[1:])
