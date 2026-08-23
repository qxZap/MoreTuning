"""Wheels in every size, built against whatever wheel mods are installed.

    python run.py                 # what it would build, and how big
    python run.py --build         # build it
    python run.py --build Maja    # just the sources whose name matches
    python run.py demo            # self-check

A wheel mesh is a 1 metre circle and the vehicle scales it, so size is not a
property anywhere -- it is the geometry. Changing it means multiplying every
vertex position in the render data, and moving the mesh's bounds with them,
because the bounds are what the collision follows. Do one without the other and
the wheel either draws at the old size or floats above the road.

Being mod-aware is the other half. Several mods ship their own Wheels table and
whichever loads last wins, so a single build would quietly delete whichever one
it did not know about. Instead every installed source is found, and one pak is
built per source, based on that source's own table. Install the one that matches
your setup: with Maja's wheels installed take the Maja build, and her rims are
in it alongside the sized ones.

Everything this needs is configured at the top of this file rather than in the
environment, so a game update is one edit here.
"""
import base64
import copy
import json
import os
import re
import shutil
import struct
import subprocess
import sys

# --------------------------------------------------------------------------
# Configuration. Update these when the game does.
# --------------------------------------------------------------------------
UASSETGUI = r"D:\MT\UAssetGUI.exe"
REPAK = r"D:\MT\PakMerge\repak.exe"
MAPPINGS = "MotorTown719"                 # the usmap UAssetGUI reads by name
ENGINE_VERSION = "VER_UE5_4"
GAME_PAKS = r"D:\SteamLibrary\steamapps\common\Motor Town\MotorTown\Content\Paks"
GAME_EXPORT = r"D:\MT\Output\Exports\MotorTown\Content"

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORK = os.path.join(HERE, "work")

# Sizes to offer, as a multiple of the original. 1.0 is stock and is skipped.
SCALE_MIN, SCALE_MAX, SCALE_STEP = 0.5, 2.0, 0.1

# Which rims to offer in every size. Every rim in every size is 93 x 15 copies
# of a 60KB mesh, which is 136MB per source and about a gigabyte across all of
# them -- and pointless, because any rim already fits any vehicle. A spread of
# designs in every size is the same product for a fiftieth of the download.
# Set to None to do the lot.
RIMS = None
_CURATED = [
    "Cervos",        # plain road wheel
    "Voltex",        # sports
    "Trophy",        # offroad
    "Savanah",       # utility
    "Muhan",         # van
    "Atlas",         # heavy duty
    "Kart",          # tiny
    "Vista",         # classic
]

TABLE_IN_PAK = "MotorTown/Content/DataAsset/VehicleParts/Wheels.uasset"
TABLE_REL = os.path.join("DataAsset", "VehicleParts", "Wheels.uasset")
WHEEL_DIR = os.path.join("Cars", "Parts", "Wheels")
WHEEL_PACKAGE = "/Game/Cars/Parts/Wheels"

# Our own output must not be mistaken for a source to build from.
# Lowercase, and four z's. Pak load order is by filename and last one wins, and
# ASCII puts every lowercase letter after every uppercase one -- so a ZZZ_ prefix
# loses to qxZap_MoreTuning_yCarbon_P and to zzzProxyTechWheels, which is exactly
# the pair this has to beat. zzzz_ sorts after both.
OUT_PREFIX = "zzzz_qxZap_WheelSizes_"

# Anything of ours, whatever it was called, must never be treated as a source.
OURS = re.compile(r"WheelSizes|WheelWorkshop", re.I)

# Sources not worth a build. MotorWorks ships a wheel table but is not a wheel
# mod, so a compat pak for it is a build nobody installs.
SKIP_SOURCES = re.compile(r"MotorWorks", re.I)


def scales():
    """Every size we offer, stock excluded."""
    out, value = [], SCALE_MIN
    while value <= SCALE_MAX + 1e-9:
        if abs(value - 1.0) > 1e-9:
            out.append(round(value, 2))
        value = round(value + SCALE_STEP, 10)
    return out


def suffix_for(scale):
    """A row and mesh suffix that sorts and reads sensibly: 80 for 0.8, 150 for 1.5."""
    return f"{int(round(scale * 100))}"


def label_for(scale):
    percent = int(round((scale - 1.0) * 100))
    return f"{percent:+d}%"


# --------------------------------------------------------------------------
# Talking to the tools
# --------------------------------------------------------------------------
def uassetgui(*args):
    """UAssetGUI is a WinForms app: it returns 0 whether or not it worked, so
    every call has to be judged by whether the file appeared."""
    subprocess.run([UASSETGUI, *args], check=False, capture_output=True)


def to_json(uasset, out):
    tmp = out + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    uassetgui("tojson", uasset, tmp, ENGINE_VERSION, MAPPINGS)
    if not os.path.exists(tmp):
        sys.exit(f"could not read {uasset} with mappings {MAPPINGS}")
    os.replace(tmp, out)
    return out


def from_json(src, out):
    for path in (out, out[: -len(".uasset")] + ".uexp"):
        if os.path.exists(path):
            os.remove(path)
    uassetgui("fromjson", src, out, MAPPINGS)
    if not os.path.exists(out):
        sys.exit(f"UAssetGUI wrote nothing for {src} -- usually a name missing "
                 f"from the NameMap, or the wrong reference type")
    return out


def pak_get(pak, entry, out):
    """Pull one file out of a pak without unpacking the whole thing."""
    result = subprocess.run([REPAK, "get", pak, entry], capture_output=True)
    if result.returncode != 0 or not result.stdout:
        return None
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as f:
        f.write(result.stdout)
    return out


def pak_has(pak, pattern):
    result = subprocess.run([REPAK, "list", pak], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines()
            if re.search(pattern, line.strip())]


# --------------------------------------------------------------------------
# Which wheel tables exist to build against
# --------------------------------------------------------------------------
def find_sources():
    """Every installed pak that ships a wheel table, plus the game's own.

    Whichever wheel table loads last is the one the game uses, so a build based
    on the wrong one silently drops another mod's wheels. One build per source
    is the only way to be compatible with all of them at once.
    """
    found = [("Vanilla", os.path.join(GAME_EXPORT, TABLE_REL), None)]
    if not os.path.isdir(GAME_PAKS):
        return found
    for name in sorted(os.listdir(GAME_PAKS)):
        if not name.endswith(".pak") or OURS.search(name):
            continue
        pak = os.path.join(GAME_PAKS, name)
        if SKIP_SOURCES.search(name) or not pak_has(pak, r"VehicleParts/Wheels\.uasset$"):
            continue
        found.append((name[: -len(".pak")], None, pak))
    return found


def fetch_table(source):
    """Get a source's wheel table (and its .uexp) somewhere we can read it."""
    name, path, pak = source
    if path:
        return path
    out_dir = os.path.join(WORK, "sources", name)
    got = pak_get(pak, TABLE_IN_PAK, os.path.join(out_dir, "Wheels.uasset"))
    if not got:
        return None
    pak_get(pak, TABLE_IN_PAK.replace(".uasset", ".uexp"),
            os.path.join(out_dir, "Wheels.uexp"))
    return got


# --------------------------------------------------------------------------
# Making a wheel a different size
# --------------------------------------------------------------------------
POSITION_STRIDE = 12


def box_range(asset, name):
    """The corners a mesh says it occupies, for checking a buffer against."""
    for export in asset["Exports"]:
        if export.get("ObjectName") != name:
            continue
        for prop in export.get("Data") or []:
            if not isinstance(prop, dict) or prop["Name"] != "ExtendedBounds":
                continue
            got = {}
            for part in prop["Value"]:
                if part.get("Name") in ("Origin", "BoxExtent"):
                    v = part["Value"][0]["Value"]
                    got[part["Name"]] = [0.0 if isinstance(v[k], str) else float(v[k])
                                         for k in "XYZ"]
            if "Origin" not in got or "BoxExtent" not in got:
                return None, None
            o, e = got["Origin"], got["BoxExtent"]
            return [o[i] - e[i] for i in range(3)], [o[i] + e[i] for i in range(3)]
    return None, None


def find_positions(blob, box_lo, box_hi, tolerance=0.5):
    """Offset and count of the vertex position buffer, or None.

    Inside the render data a position buffer is a stride of 12, a vertex count,
    and that many packed float triples. A stride of 12 also turns up by chance,
    and a wrong guess silently corrupts a mesh, so a candidate is only accepted
    if the coordinates it yields reproduce the mesh's own stated bounds.
    """
    for off in range(0, max(0, len(blob) - 8)):
        stride, count = struct.unpack_from("<ii", blob, off)
        if stride != POSITION_STRIDE or not 16 <= count <= 200000:
            continue
        if off + 8 + count * POSITION_STRIDE > len(blob):
            continue
        try:
            coords = struct.unpack_from(f"<{count * 3}f", blob, off + 8)
        except struct.error:
            continue
        if not all(-1e4 < v < 1e4 for v in coords):
            continue
        axes = [coords[i::3] for i in range(3)]
        if all(abs(min(axes[i]) - box_lo[i]) < tolerance
               and abs(max(axes[i]) - box_hi[i]) < tolerance for i in range(3)):
            return off, count
    return None


def scale_positions(blob, off, count, factor):
    out = bytearray(blob)
    for i in range(count * 3):
        at = off + 8 + i * 4
        value, = struct.unpack_from("<f", out, at)
        struct.pack_into("<f", out, at, value * factor)
    return bytes(out)


def scale_bounds(asset, factor):
    """Move the bounds with the geometry -- the collision follows these."""
    for export in asset["Exports"]:
        for prop in export.get("Data") or []:
            if not isinstance(prop, dict) or prop["Name"] != "ExtendedBounds":
                continue
            for part in prop["Value"]:
                name = part.get("Name")
                if name == "SphereRadius":
                    v = part.get("Value")
                    part["Value"] = (0.0 if isinstance(v, str) else float(v)) * factor
                elif name in ("Origin", "BoxExtent"):
                    vec = part["Value"][0]["Value"]
                    for k in "XYZ":
                        v = vec[k]
                        vec[k] = (0.0 if isinstance(v, str) else float(v)) * factor


def register_names(asset, names):
    """Add names in the block the header counts as referenced by export data."""
    existing = set(asset["NameMap"])
    fresh = []
    for name in names:
        base = re.sub(r"_\d+$", "", name) if re.search(r"_[1-9]\d*$", name) else name
        for candidate in (name, base):
            if candidate and candidate not in existing:
                existing.add(candidate)
                fresh.append(candidate)
    boundary = asset["NamesReferencedFromExportDataCount"]
    asset["NameMap"] = asset["NameMap"][:boundary] + fresh + asset["NameMap"][boundary:]
    asset["NamesReferencedFromExportDataCount"] = boundary + len(fresh)
    return fresh


def cached_mesh(mesh, new_name, factor):
    """Resize a rim once and keep it. The same rim at the same size is the same
    mesh in every source, and the resize is the slow part -- four sources means
    four copies of a file, not four rounds through UAssetGUI."""
    cache = os.path.join(WORK, "meshes")
    made = os.path.join(cache, new_name + ".uasset")
    if os.path.isfile(made):
        return cache
    if resize_mesh(find_mesh(mesh), new_name, factor, cache) is None:
        return None
    return cache


def resize_mesh(source, new_name, factor, out_dir):
    """Write a resized copy of a wheel mesh. Returns its vertex count."""
    name = os.path.basename(source)[: -len(".uasset")]
    staged = os.path.join(os.path.dirname(source), new_name + ".tmp.json")
    asset = json.load(open(to_json(source, staged), encoding="utf-8"))

    lo, hi = box_range(asset, name)
    if lo is None:
        os.remove(staged)
        return None
    moved = None
    for export in asset["Exports"]:
        if export.get("ObjectName") != name or not export.get("Extras"):
            continue
        blob = base64.b64decode(export["Extras"])
        found = find_positions(blob, lo, hi)
        if found is None:
            break
        off, count = found
        export["Extras"] = base64.b64encode(
            scale_positions(blob, off, count, factor)).decode("ascii")
        export["ObjectName"] = new_name
        moved = count
    if moved is None:
        os.remove(staged)
        return None

    register_names(asset, [new_name])
    scale_bounds(asset, factor)
    json.dump(asset, open(staged, "w", encoding="utf-8"), indent=1)
    built = from_json(staged, os.path.join(os.path.dirname(source),
                                           new_name + ".tmp.uasset"))
    os.makedirs(out_dir, exist_ok=True)
    for ext in (".uasset", ".uexp"):
        shutil.copy2(built[: -len(".uasset")] + ext, os.path.join(out_dir, new_name + ext))
        os.remove(built[: -len(".uasset")] + ext)
    bulk = source[: -len(".uasset")] + ".ubulk"
    if os.path.isfile(bulk):
        shutil.copy2(bulk, os.path.join(out_dir, new_name + ".ubulk"))
    os.remove(staged)
    return moved


# --------------------------------------------------------------------------
# Building a pak per source
# --------------------------------------------------------------------------
def wheel_rows(table):
    for export in table["Exports"]:
        if export.get("Table"):
            return export["Table"]["Data"]
    return []


def mesh_link(table, name):
    """Hard import for a wheel mesh. These are ObjectProperty references, not
    soft paths -- a soft path here does not write at all."""
    package = f"{WHEEL_PACKAGE}/{name}"
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


MESH_FIELDS = ("LeftWheelMesh", "RightWheelMesh", "DRWLeftWheelMesh",
               "DRWRightWheelMesh", "RearLeftWheelMesh", "RearRightWheelMesh",
               "QuadWheelMesh")


def row_meshes(row, table):
    """The meshes a wheel row points at, as {field: mesh name}."""
    out = {}
    for prop in row["Value"]:
        if prop["Name"] != "Wheel":
            continue
        for field in prop["Value"]:
            if not isinstance(field, dict) or field["Name"] not in MESH_FIELDS:
                continue
            link = field.get("Value")
            if isinstance(link, int) and link < 0:
                out[field["Name"]] = table["Imports"][-link - 1].get("ObjectName")
    return out


def make_row(donor, key, label, links):
    row = copy.deepcopy(donor)
    row["Name"] = key
    for prop in row["Value"]:
        if prop["Name"] == "Name":
            prop.update({"CultureInvariantString": label, "Namespace": None,
                         "Value": None, "HistoryType": "None",
                         "Flags": "CultureInvariant"})
        elif prop["Name"] == "Wheel":
            for field in prop["Value"]:
                if isinstance(field, dict) and field["Name"] in links:
                    field["Value"] = links[field["Name"]]
    return row


def base_label(row):
    for prop in row["Value"]:
        if prop["Name"] == "Name":
            return prop.get("CultureInvariantString") or row["Name"]
    return row["Name"]


def find_mesh(name):
    """Where a wheel mesh lives. Only the game's own copy is resized -- a mod's
    rim is that mod's to ship, and resizing it here would override it."""
    path = os.path.join(GAME_EXPORT, WHEEL_DIR, name + ".uasset")
    return path if os.path.isfile(path) else None


def build(source, out_root, dry=True):
    name = source[0]
    table_path = fetch_table(source)
    if not table_path:
        print(f"  {name}: could not read its wheel table"); return None
    work = os.path.join(WORK, "build", name)
    os.makedirs(work, exist_ok=True)
    table = json.load(open(to_json(table_path, os.path.join(work, "wheels.json")),
                           encoding="utf-8"))
    rows = wheel_rows(table)

    sizes = scales()
    plan, skipped = [], 0
    for row in list(rows):
        if RIMS is not None and row["Name"] not in RIMS:
            continue
        meshes = row_meshes(row, table)
        usable = {f: m for f, m in meshes.items() if m and find_mesh(m)}
        if not usable:
            skipped += 1
            continue
        plan.append((row, usable))

    bytes_each = 0
    for _, usable in plan[:1]:
        for m in usable.values():
            p = find_mesh(m)
            for ext in (".uasset", ".uexp", ".ubulk"):
                f = p[: -len(".uasset")] + ext
                bytes_each += os.path.getsize(f) if os.path.isfile(f) else 0
    projected = bytes_each * len(plan) * len(sizes)
    print(f"  {name:44} {len(plan):3} wheels x {len(sizes)} sizes"
          f"  ~{projected/1048576:6.0f} MB  ({skipped} skipped)")
    if dry:
        return projected

    out = os.path.join(out_root, OUT_PREFIX + name.replace("_P", "") + "_P",
                       "MotorTown", "Content")
    made = 0
    for row, usable in plan:
        # Keep them ascending under the rim they came from: -50% first, +100%
        # last. Inserting each one straight after the donor reverses them.
        step = 0
        for scale in sizes:
            tag = suffix_for(scale)
            links = {}
            for field, mesh in usable.items():
                new_name = f"{mesh}_{tag}"
                target = os.path.join(out, WHEEL_DIR, new_name + ".uasset")
                if not os.path.isfile(target):
                    cache = cached_mesh(mesh, new_name, scale)
                    if cache is None:
                        links = {}
                        break
                    os.makedirs(os.path.join(out, WHEEL_DIR), exist_ok=True)
                    for ext in (".uasset", ".uexp", ".ubulk"):
                        src = os.path.join(cache, new_name + ext)
                        if os.path.isfile(src):
                            shutil.copy2(src, os.path.join(out, WHEEL_DIR, new_name + ext))
                links[field] = mesh_link(table, new_name)
            if not links:
                continue
            key = f"{row['Name']}_{tag}"
            fresh = make_row(row, key, f"{base_label(row)} {label_for(scale)}", links)
            existing = next((r for r in rows if r["Name"] == key), None)
            if existing is not None:
                rows.remove(existing)
            step += 1
            rows.insert(rows.index(row) + step, fresh)
            register_names(table, [key] + list(
                {n for f, n in [(f, table["Imports"][-l - 1]["ObjectName"])
                                for f, l in links.items()]}))
            made += 1
    js = os.path.join(work, "wheels.edited.json")
    json.dump(table, open(js, "w", encoding="utf-8"), indent=1)
    built = from_json(js, os.path.join(work, "Wheels.uasset"))
    target = os.path.join(out, TABLE_REL)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    for ext in (".uasset", ".uexp"):
        shutil.copy2(built[: -len(".uasset")] + ext, target.replace(".uasset", ext))
    print(f"     built {made} sized wheels, {len(rows)} rows")
    return made


def main(build_it=False, only=None):
    os.makedirs(WORK, exist_ok=True)
    sources = [s for s in find_sources()
               if not only or any(o.lower() in s[0].lower() for o in only)]
    if not sources:
        sys.exit("no wheel tables found to build against")
    print(f"{len(sources)} source(s), {len(scales())} sizes "
          f"({SCALE_MIN:g}x to {SCALE_MAX:g}x in {SCALE_STEP:g} steps)\n")
    total = 0
    for source in sources:
        got = build(source, REPO, dry=not build_it)
        total += got or 0
    if not build_it:
        print(f"\n  projected total ~{total/1048576:.0f} MB across {len(sources)} paks")
        print("  run with --build to write it")
    else:
        print(f"\n  {total} sized wheels written")
        print("  pack each with: modp.bat <folder name>")


def demo():
    s = scales()
    assert 1.0 not in s, "stock is not a variant"
    assert s[0] == 0.5 and s[-1] == 2.0 and len(s) == 15
    assert suffix_for(0.8) == "80" and suffix_for(1.5) == "150"
    assert label_for(0.5) == "-50%" and label_for(2.0) == "+100%"

    # A buffer big enough to be believable: the finder ignores tiny ones.
    verts = [(-10.0, 0.0, -10.0), (10.0, 5.0, 10.0)] + [(0.0, 1.0, 0.0)] * 18
    blob = (struct.pack("<ii", 12, len(verts))
            + struct.pack(f"<{len(verts) * 3}f", *[c for v in verts for c in v]))
    found = find_positions(blob, [-10, 0, -10], [10, 5, 10])
    assert found == (0, len(verts)), found
    assert find_positions(blob, [-99, -99, -99], [99, 99, 99]) is None,         "a buffer that does not match the bounds must be refused, not used"
    out = scale_positions(blob, 0, len(verts), 2.0)
    assert struct.unpack_from("<3f", out, 8) == (-20.0, 0.0, -20.0)
    assert struct.unpack_from("<ii", out, 0) == (12, len(verts)), "the header must not move"
    assert len(out) == len(blob), "scaling must not change the size of the data"

    asset = {"Exports": [{"Data": [{"Name": "ExtendedBounds", "Value": [
        {"Name": "Origin", "Value": [{"Value": {"X": 1.0, "Y": "+0", "Z": 2.0}}]},
        {"Name": "BoxExtent", "Value": [{"Value": {"X": 50.0, "Y": 20.0, "Z": 50.0}}]},
        {"Name": "SphereRadius", "Value": 70.0}]}], "ObjectName": "W"}]}
    lo, hi = box_range(asset, "W")
    assert lo == [-49.0, -20.0, -48.0] and hi == [51.0, 20.0, 52.0]
    scale_bounds(asset, 2.0)
    assert asset["Exports"][0]["Data"][0]["Value"][2]["Value"] == 140.0
    assert box_range(asset, "W")[1] == [102.0, 40.0, 104.0]

    table = {"Imports": []}
    a = mesh_link(table, "Classic_01_L_80")
    assert len(table["Imports"]) == 2 and table["Imports"][-1]["ClassName"] == "StaticMesh"
    assert mesh_link(table, "Classic_01_L_80") == a, "must not stack duplicate imports"

    donor = {"Name": "Cervos", "Value": [
        {"Name": "Name", "CultureInvariantString": "Cervos"},
        {"Name": "Wheel", "Value": [{"Name": "LeftWheelMesh", "Value": -1},
                                    {"Name": "RightWheelMesh", "Value": -2}]}]}
    row = make_row(donor, "Cervos_80", "Cervos -20%", {"LeftWheelMesh": -9})
    assert donor["Name"] == "Cervos", "donor untouched"
    wheel = {f["Name"]: f["Value"] for f in row["Value"][1]["Value"]}
    assert wheel["LeftWheelMesh"] == -9 and wheel["RightWheelMesh"] == -2
    assert base_label(donor) == "Cervos"
    assert RIMS is None or len(RIMS) == len(set(RIMS)), "no rim listed twice"
    print("ok")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["demo"]:
        demo()
    else:
        main(build_it="--build" in args,
             only=[a for a in args if not a.startswith("--")] or None)
