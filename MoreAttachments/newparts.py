"""Add the MTMapAddon meshes to MoreAttachments as buyable attachments.

    python newparts.py            # copy meshes, build actors, add rows
    python newparts.py --dry      # say what it would do
    python newparts.py demo       # self-check

Reads NEW_PARTS.json for what to add and how each should be built:

    NONC   plain            ACTOR_TEMPLATE_NOCOLOR
    COL    paintable        ACTOR_TEMPLATE
    LIGHT  lamp             ACTOR_TEMPLATE_LIGHT -- beam, switchable, glowing lens

The meshes come cooked out of the UE project. Nothing else has to ship with
them: every one uses the same material, Mat_PolygonStreetRacer_01_A, and the game
already has it. None of them collide with a mesh the game ships either, which
matters -- shipping our own copy at a package path the game already uses would
override the game's for no gain.

One thing the meshes cannot do. Each has a single material slot, so a lamp's lens
and its frame are the same material and there is no way to light only the lens.
For something that is all lamp -- a fog light, a spot, a light bar -- lighting
the whole mesh is right. For a bumper or a roof basket it would mean a glowing
bumper, so those get the beam and the switch without the glow. Splitting the
slot properly is an edit in the UE project, not something to fake here.
"""
import copy
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from pipeline import WORK, from_json, register_names, to_json  # noqa: E402
import reallights  # noqa: E402

COOKED = (r"C:\Users\Milea\Documents\Unreal Projects\MTMapAddon\Saved\Cooked"
          r"\Windows\MTMapAddon\Content")
GAME = os.path.join(HERE, "..", "..", "Output", "Exports", "MotorTown", "Content")
PAK = os.path.join(HERE, "..", "qxZap_satigt3_MoreAttachments_P", "MotorTown", "Content")
ACTORS_DIR = os.path.join(PAK, "Objects", "MoreAttachments")
ACTOR_PACKAGE = "/Game/Objects/MoreAttachments"
SPEC = os.path.join(HERE, "NEW_PARTS.json")

TEMPLATES = {"NONC": "ACTOR_TEMPLATE_NOCOLOR.json",
             "COL": "ACTOR_TEMPLATE.json",
             "LIGHT": "ACTOR_TEMPLATE_LIGHT.json"}
TEMPLATE_NAME = "Attachment_Neo_RearSpoiler_01"
TEMPLATE_MESH = "/Game/Cars/Models/Neo/RearSpoiler_01"
MESH_SENTINELS = ("-0.96961", "-0.96962", "-0.96963")
LENS_SENTINELS = ("-0.96971", "-0.96972", "-0.96973")

# Lamps whose whole body is the lamp: lighting every slot is what they want.
# Anything else in the LIGHT class is mostly frame, and gets the beam only.
ALL_LAMP = re.compile(r"Light_(Fog|Spot|LightBar|Police_Roof)", re.I)

COST = {"NONC": 400, "COL": 800, "LIGHT": 1500}
MASS = {"NONC": 8.0, "COL": 12.0, "LIGHT": 10.0}

BOTH_PAKS = [os.path.join(HERE, "..", p, "MotorTown", "Content")
             for p in ("qxZap_satigt3_MoreAttachments_P",
                       "qxZap_satigt3_MoreAttachments_Premium_P")]


def local(root, package):
    return os.path.join(root, package.replace("/Game/", "").replace("/", os.sep))


# A stray export sitting in MA_Parts/Rollcages. Not a part.
EXCLUDE = {"StaticMesh"}


def wanted():
    """(package, mesh name, class) for everything NEW_PARTS.json asks for."""
    spec = json.load(open(SPEC, encoding="utf-8"))
    out = []
    for package, classes in spec["folders"].items():
        for kind, names in classes.items():
            if names == "*":
                folder = local(COOKED, package)
                names = sorted(f[: -len(".uasset")] for f in os.listdir(folder)
                               if f.endswith(".uasset")
                               and f[: -len(".uasset")] not in EXCLUDE)
            for name in names:
                out.append((package, name, kind))
    return out


# Every new key is namespaced. There are 585 attachments already and at least one
# straight collision (Attachment_Turbo_01), and a clash would either silently drop
# the part or, worse, overwrite the actor of an existing one. Players never see
# this -- the display name is separate.
PREFIX = "Attachment_SR_"


def part_id(mesh):
    """A row key, and the actor's name. Not what the player reads."""
    short = re.sub(r"^SM_Veh_(Attach_|)", "", mesh, flags=re.I)
    return PREFIX + short


def display(mesh):
    short = re.sub(r"^SM_Veh_(Attach_|)", "", mesh, flags=re.I)
    return short.replace("_", " ").strip()


def all_slots(mesh_json):
    """Every material slot, as (index, name). These meshes have one each, so for
    a lamp that one slot is the lamp -- there is nothing finer to aim at."""
    out = []
    for export in mesh_json["Exports"]:
        for prop in export.get("Data") or []:
            if not isinstance(prop, dict) or prop["Name"] != "StaticMaterials":
                continue
            for index, entry in enumerate(prop["Value"]):
                fields = {f["Name"]: f.get("Value") for f in entry["Value"]
                          if isinstance(f, dict)}
                if fields.get("MaterialSlotName"):
                    out.append((index, fields["MaterialSlotName"]))
    return out


def bounds_of(mesh_json):
    found = {}

    def walk(node):
        if isinstance(node, dict):
            value = node.get("Value")
            if node.get("Name") in ("Origin", "BoxExtent") and isinstance(value, dict) \
                    and "X" in value:
                found[node["Name"]] = {k: 0.0 if isinstance(value[k], str) else float(value[k])
                                       for k in "XYZ"}
            else:
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for export in mesh_json["Exports"]:
        for row in export.get("Data") or []:
            if isinstance(row, dict) and row.get("Name") == "ExtendedBounds":
                walk(row["Value"])
    return found


def build_actor(text, name, package, mesh, offset, lens):
    """Fill a template in. Actor name first: the template's own name ends in its
    mesh's name, so renaming the mesh first eats it."""
    text = text.replace(TEMPLATE_NAME, name)
    text = text.replace(TEMPLATE_MESH, f"{package}/{mesh}")
    text = text.replace(TEMPLATE_MESH.rsplit("/", 1)[-1], mesh)
    for sentinel, value in zip(MESH_SENTINELS, offset):
        text = text.replace(sentinel, repr(float(value)))
    for sentinel, value in zip(LENS_SENTINELS, lens):
        text = text.replace(sentinel, repr(float(value)))
    return json.loads(text)


def soft(package, asset):
    return {"$type": "UAssetAPI.PropertyTypes.Objects.FSoftObjectPath, UAssetAPI",
            "AssetPath": {"$type": "UAssetAPI.PropertyTypes.Objects.FTopLevelAssetPath, UAssetAPI",
                          "PackageName": package, "AssetName": asset},
            "SubPathString": None}


def make_row(donor, key, label, package, mesh, actor, cost, mass):
    row = copy.deepcopy(donor)
    row["Name"] = key
    for prop in row["Value"]:
        if prop["Name"] == "AttachmentPartActorClass":
            prop["Value"] = soft(f"{ACTOR_PACKAGE}/{actor}", actor + "_C")
        elif prop["Name"] == "StaticMesh":
            prop["Value"] = soft(f"{package}/{mesh}", mesh)
        elif prop["Name"] == "ItemName":
            prop.update({"CultureInvariantString": label, "Namespace": None,
                         "Value": None, "HistoryType": "None",
                         "Flags": "CultureInvariant"})
        elif prop["Name"] == "Cost":
            prop["Value"] = cost
        elif prop["Name"] == "MassKg":
            prop["Value"] = float(mass)
    return row


def copy_mesh(package, mesh, dry):
    """Cooked mesh plus whatever siblings it cooked with."""
    src_dir, dst_dir = local(COOKED, package), local(PAK, package)
    if os.path.isfile(os.path.join(local(GAME, package), mesh + ".uasset")):
        return None                      # the game has it; never shadow it
    if not dry:
        os.makedirs(dst_dir, exist_ok=True)
    count = 0
    for name in os.listdir(src_dir):
        if not name.startswith(mesh + "."):
            continue
        if not dry:
            shutil.copy2(os.path.join(src_dir, name), os.path.join(dst_dir, name))
        count += 1
    return count


def add_rows(new_rows, keys, dry):
    """Append rows to both paks' tables and put them on sale. Appending only:
    moving existing rows is not needed and renaming one would break builds."""
    for content in BOTH_PAKS:
        items = os.path.join(content, "DataAsset", "Items", "Items_AttachmentPart.uasset")
        vendor = os.path.join(content, "Characters", "NPC", "Vendor_Garage.uasset")
        if not os.path.isfile(items):
            continue
        tag = content.split(os.sep)[-3]
        work = os.path.join(WORK, "newparts")
        os.makedirs(work, exist_ok=True)

        table = json.load(open(to_json(items, os.path.join(work, tag + ".items.json")),
                               encoding="utf-8"))
        rows = next(e["Table"]["Data"] for e in table["Exports"] if e.get("Table"))
        donor = next(r for r in rows if r["Name"] == "Attachment_Light_01")
        have = {r["Name"] for r in rows}
        stale = [r for r in rows if r["Name"].startswith(PREFIX)
                 and r["Name"] not in {a[0] for a in new_rows}]
        for row in stale:
            rows.remove(row)
        if stale:
            print(f"\n  dropped {len(stale)} of ours no longer in the spec: "
                  f"{[r['Name'] for r in stale]}")
        have = {r["Name"] for r in rows}
        clash = [a[0] for a in new_rows if a[0] in have]
        if clash:
            print(f"\n  name already taken, skipped: {clash}")
        fresh = [make_row(donor, *args) for args in new_rows if args[0] not in have]
        rows.extend(fresh)
        register_names(table, [a[0] for a in new_rows] + [a[3] for a in new_rows]
                       + [f"{a[2]}/{a[3]}" for a in new_rows]
                       + [f"{ACTOR_PACKAGE}/{a[4]}" for a in new_rows]
                       + [a[4] + "_C" for a in new_rows])
        print(f"  {tag}: +{len(fresh)} rows -> {len(rows)}", end="")
        if not dry:
            js = os.path.join(work, tag + ".items.edited.json")
            json.dump(table, open(js, "w", encoding="utf-8"), indent=1)
            built = from_json(js, os.path.join(work, tag + "_Items.uasset"))
            for ext in (".uasset", ".uexp"):
                shutil.copy2(built[: -len(".uasset")] + ext, items.replace(".uasset", ext))

        shop = json.load(open(to_json(vendor, os.path.join(work, tag + ".vendor.json")),
                              encoding="utf-8"))
        added = 0
        for export in shop["Exports"]:
            for entry in export.get("Data") or []:
                if not isinstance(entry, dict) or entry["Name"] != "SellItems":
                    continue
                sold = entry["Value"]
                known = {i.get("Value") if isinstance(i, dict) else i for i in sold}
                for key in keys:
                    if key in known:
                        continue
                    item = copy.deepcopy(sold[0])
                    if isinstance(item, dict):
                        item["Value"] = key
                    else:
                        item = key
                    sold.append(item)
                    added += 1
                for index, item in enumerate(sold):
                    if isinstance(item, dict) and "Name" in item:
                        item["Name"] = str(index)
        register_names(shop, list(keys))
        print(f", +{added} on sale")
        if not dry:
            js = os.path.join(work, tag + ".vendor.edited.json")
            json.dump(shop, open(js, "w", encoding="utf-8"), indent=1)
            built = from_json(js, os.path.join(work, tag + "_Vendor.uasset"))
            for ext in (".uasset", ".uexp"):
                shutil.copy2(built[: -len(".uasset")] + ext, vendor.replace(".uasset", ext))


def main(dry=False):
    work = os.path.join(WORK, "newparts")
    os.makedirs(work, exist_ok=True)
    templates = {k: open(os.path.join(HERE, v), encoding="utf-8").read()
                 for k, v in TEMPLATES.items()}
    if not dry:
        os.makedirs(ACTORS_DIR, exist_ok=True)

    new_rows, keys, built, skipped = [], [], 0, 0
    for package, mesh, kind in wanted():
        copied = copy_mesh(package, mesh, dry)
        if copied is None:
            print(f"  skip {mesh}: the game already ships it")
            skipped += 1
            continue

        source = os.path.join(local(COOKED, package), mesh + ".uasset")
        mesh_json = json.load(open(to_json(source, os.path.join(work, "m.json")),
                                   encoding="utf-8"))
        info = bounds_of(mesh_json)
        slots = all_slots(mesh_json)
        origin = info.get("Origin") or {"X": 0.0, "Y": 0.0, "Z": 0.0}
        extent = info.get("BoxExtent") or {"X": 0.0, "Y": 0.0, "Z": 0.0}
        offset = (-origin["X"], -origin["Y"], -origin["Z"])
        lens = (extent["X"], 0.0, 0.0) if kind == "LIGHT" else (0.0, 0.0, 0.0)

        actor = part_id(mesh)
        asset = build_actor(templates[kind], actor, package, mesh, offset, lens)
        # A trailing _<digits> is an FName number, not part of the name: UAssetGUI
        # stores SM_Veh_Attach_Exhaust_Tip_10 as base + 10 and then needs that
        # base in the map. _01 keeps its leading zero and stays literal, which is
        # why the first nine of a set write happily and the tenth does not.
        register_names(asset, [mesh, actor, f"{package}/{mesh}",
                               f"{ACTOR_PACKAGE}/{actor}", actor + "_C"])
        if kind == "LIGHT" and ALL_LAMP.search(mesh) and slots:
            # The whole mesh is the lamp, so the whole mesh glows: point the light
            # control at its slots and give them the material it can drive. A
            # paintable slot cannot also be a lit one, and lighting up is the
            # point of these.
            profile = json.load(open(reallights.PROFILE, encoding="utf-8"))
            for export in asset["Exports"]:
                if "MTLightControl" in str(export.get("ObjectName")):
                    control = copy.deepcopy(profile["MTLightControl"])
                    reallights.set_emissive(control, [n for _, n in slots])
                    export["Data"] = control
            reallights.override_lamp_materials(asset, slots, len(slots))
            register_names(asset, [n for _, n in slots] + reallights.names_in(profile)
                           + [reallights.ATTACHMENT_LIGHT,
                              reallights.ATTACHMENT_LIGHT_PACKAGE,
                              "Material", "OverrideMaterials"])
        if not dry:
            js = os.path.join(work, actor + ".json")
            json.dump(asset, open(js, "w", encoding="utf-8"), indent=1)
            out = from_json(js, os.path.join(work, actor + ".uasset"))
            for ext in (".uasset", ".uexp"):
                shutil.copy2(out[: -len(".uasset")] + ext,
                             os.path.join(ACTORS_DIR, actor + ext))
        key = part_id(mesh)
        new_rows.append((key, display(mesh), package, mesh, actor,
                         COST[kind], MASS[kind]))
        keys.append(key)
        built += 1

    print(f"\n{built} actors built, {skipped} skipped")
    add_rows(new_rows, keys, dry)
    print("\nPack both MoreAttachments paks.")


def demo():
    assert part_id("SM_Veh_Attach_Antenna_01") == "Attachment_SR_Antenna_01"
    assert part_id("SM_Veh_Exotic_01_Spoiler_02") == "Attachment_SR_Exotic_01_Spoiler_02"
    assert not part_id("SM_Veh_Attach_Turbo_01").startswith("Attachment_Turbo"),         "Attachment_Turbo_01 already exists; the namespace is what keeps it safe"
    assert display("SM_Veh_Attach_Roof_Scoop_01") == "Roof Scoop 01"
    assert ALL_LAMP.search("SM_Veh_Attach_Light_Fog_02")
    assert ALL_LAMP.search("SM_Veh_Attach_Light_Police_Roof_01")
    assert not ALL_LAMP.search("SM_Veh_Attach_Bumper_01_Front_01"), \
        "a bumper is mostly frame and must not glow all over"
    assert not ALL_LAMP.search("SM_Veh_Attach_Roof_Basket_01")

    text = json.dumps({"n": TEMPLATE_NAME, "m": TEMPLATE_MESH,
                       "leaf": TEMPLATE_MESH.rsplit("/", 1)[-1],
                       "o": [MESH_SENTINELS[0]], "l": [LENS_SENTINELS[0]]})
    out = build_actor(text.replace('"' + MESH_SENTINELS[0] + '"', MESH_SENTINELS[0])
                          .replace('"' + LENS_SENTINELS[0] + '"', LENS_SENTINELS[0]),
                      "Attachment_X", "/Game/P", "SM_Y", (1.5, 0, 0), (2.5, 0, 0))
    assert out["n"] == "Attachment_X" and out["m"] == "/Game/P/SM_Y"
    assert out["leaf"] == "SM_Y", "the mesh leaf name has to be replaced too"
    assert out["o"] == [1.5] and out["l"] == [2.5]
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main(dry="--dry" in sys.argv)
