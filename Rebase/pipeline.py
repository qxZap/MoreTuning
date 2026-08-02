"""Read a part table, transform its rows, build it back, check it, install it.

The three row-editing tools (Rebase, RemoveReq, CarbonParts) all used to do the
same dance by hand -- export to JSON, rename to input.json, run a script, rename
output.json back, convert, move the files into a mod folder. This is that dance,
once, with the checks that stop a silently-broken table from shipping.

    from pipeline import build_table
    build_table("License", strip_requirements)
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")

# NOT the UAssetGUI.exe in the repo root -- that one is v1.0.4 and writes an
# older JSON schema, so anything it exports fails to build again on 0.7.19.
UASSETGUI = r"D:\MT\UAssetGUI.exe"
CURRENT_MAPPINGS = "MotorTown719"
ENGINE_VERSION = "VER_UE5_4"

VANILLA = r"D:\MT\Output\Exports\MotorTown\Content"
MOD = os.path.join(REPO, "qxZap_MoreTuning_P", "MotorTown", "Content")
CARBON = os.path.join(REPO, "qxZap_MoreTuning_yCarbon_P", "MotorTown", "Content")
NOLIMITS = os.path.join(REPO, "qxZap_MoreTuning_xNoLimits_P", "MotorTown", "Content")

# Compat with Maja's Mo Wheel Works, which ships its own unlocked Wheels table.
# WHEELWORKS is that mod unpacked; WHEELWORKS_CARBON is the pak that merges it
# with our carbon variants and, being ZZb_, mounts after both.
WHEELWORKS = os.path.join(REPO, "MajasMoWheelWorksV5.1-7.19_P", "MotorTown", "Content")
WHEELWORKS_CARBON = os.path.join(REPO, "ZZb_qxZap_MoreTuning_yWheelWorksCarbon_P",
                                 "MotorTown", "Content")
TABLE_DIR = os.path.join("DataAsset", "VehicleParts")
WORK = os.path.join(HERE, "work")


def uassetgui(*args):
    """UAssetGUI is a WinForms app: it swallows errors and returns 0 either way."""
    subprocess.run([UASSETGUI, *args], check=True)


def to_json(uasset, out, mappings=CURRENT_MAPPINGS):
    # Export to a temp name first: these JSONs are the only pristine copy of a
    # vanilla table between game exports, and a failed read must not destroy the
    # previous one.
    tmp = out + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    uassetgui("tojson", uasset, tmp, ENGINE_VERSION, mappings)
    if not os.path.exists(tmp):
        sys.exit(f"FAIL: could not read {uasset} with mappings {mappings}")
    os.replace(tmp, out)
    return out


def from_json(src, out):
    for path in (out, out[: -len(".uasset")] + ".uexp"):
        if os.path.exists(path):
            os.remove(path)
    uassetgui("fromjson", src, out, CURRENT_MAPPINGS)
    if not os.path.exists(out):
        sys.exit(f"FAIL: UAssetGUI wrote nothing for {src} -- usually an FName "
                 f"missing from the NameMap, or a duplicated property in a row")
    return out


def table_path(root, name):
    return os.path.join(root, TABLE_DIR, name + ".uasset")


def source_root(name, preferred):
    """Where to read a table from: the mod's own copy if it has one, else vanilla."""
    return preferred if os.path.isfile(table_path(preferred, name)) else VANILLA


def name_property(display_name):
    """A part's display name as a culture-invariant literal.

    Vanilla names are localised text (namespace + key, e.g. AeroParts /
    Vista_Bonnet_01_Name) and the game resolves them through its string tables.
    This form has no lookup at all, so whatever string is put here is what shows
    up -- which is how the mod's own added rows have always been named.
    """
    return {
        "$type": "UAssetAPI.PropertyTypes.Objects.TextPropertyData, UAssetAPI",
        "Flags": "CultureInvariant",
        "HistoryType": "None",
        "Namespace": None,
        "CultureInvariantString": display_name,
        "SourceFmt": None,
        "Arguments": None,
        "ArgumentsData": None,
        "TransformType": "ToLower",
        "SourceValue": None,
        "FormatOptions": None,
        "TargetCulture": None,
        "Name": "Name",
        "ArrayIndex": 0,
        "PropertyGuid": None,
        "IsZero": False,
        "PropertyTagFlags": "None",
        "PropertyTypeName": None,
        "PropertyTagExtensions": "NoExtension",
        "Value": None,
    }


def register_names(table, names):
    """Add FNames to the map, in the block the header counts as export-referenced."""
    from rebase import fname_base

    existing = set(table["NameMap"])
    fresh = []
    for name in names:
        base = fname_base(name)
        if base and base not in existing:
            existing.add(base)
            fresh.append(base)
    boundary = table["NamesReferencedFromExportDataCount"]
    table["NameMap"] = table["NameMap"][:boundary] + fresh + table["NameMap"][boundary:]
    table["NamesReferencedFromExportDataCount"] = boundary + len(fresh)
    return fresh


def build_table(name, transform, source=MOD, dest=MOD):
    """Read <source>/<name>.uasset (or vanilla), run transform, install into <dest>.

    transform(rows, table) returns the new row list. Anything it needs in the
    NameMap it should register via register_names.
    """
    os.makedirs(WORK, exist_ok=True)
    root = source_root(name, source)
    print(f"\n=== {name} ===  from {'vanilla' if root == VANILLA else root}")

    src_json = to_json(table_path(root, name), os.path.join(WORK, name + ".in.json"))
    with open(src_json, "r", encoding="utf-8") as f:
        table = json.load(f)
    if table["Exports"][0]["$type"].startswith("UAssetAPI.ExportTypes.RawExport"):
        sys.exit(f"FAIL: {name} did not parse as a DataTable -- wrong usmap.")

    rows = table["Exports"][0]["Table"]["Data"]
    table["Exports"][0]["Table"]["Data"] = transform(rows, table)

    merged = os.path.join(WORK, name + ".json")
    with open(merged, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=2)

    built = from_json(merged, os.path.join(WORK, name + ".uasset"))
    check = to_json(built, os.path.join(WORK, name + ".check.json"))
    subprocess.run([sys.executable, os.path.join(HERE, "verify.py"), check, MOD, VANILLA],
                   check=True)

    import shutil
    os.makedirs(os.path.join(dest, TABLE_DIR), exist_ok=True)
    for ext in (".uasset", ".uexp"):
        shutil.copy2(os.path.join(WORK, name + ext),
                     os.path.join(dest, TABLE_DIR, name + ext))
    print(f"  -> {os.path.join(dest, TABLE_DIR, name)}.uasset/.uexp")
