"""Add the MTMapAddon meshes to MoreAttachments as buyable attachments.

    python newparts.py            # copy meshes, build actors, add rows
    python newparts.py --rows     # only refresh the rows (names, price, mass)
    python newparts.py --dry      # say what it would do
    python newparts.py demo       # self-check

Reads NEW_PARTS.json for what to add and how each should be built:

    NONC   plain            ACTOR_TEMPLATE_NOCOLOR
    COL    paintable        ACTOR_TEMPLATE
    LIGHT  lamp             ACTOR_TEMPLATE_LIGHT -- casts a beam, switchable

The meshes come cooked out of the UE project. Nothing else has to ship with
them: every one uses the same material, Mat_PolygonStreetRacer_01_A, and the game
already has it. None of them collide with a mesh the game ships either, which
matters -- shipping our own copy at a package path the game already uses would
override the game's for no gain.

One thing the meshes cannot do. Each has a single material slot, so a lamp's lens
and its frame are the same material and lighting the lens means lighting the
housing, the metal frame and all. None of them glow because of it -- they cast a
beam and switch on and off, and that is all. Give a mesh a second material slot
for its lens in the UE project and the glow starts working with no change here,
the way the Cora and Zino headlights already do off M_HeadLight.
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

# No emissive on any of these. Every one of the twenty light meshes has a single
# material slot and there is no _Light or _Lens variant the way vanilla splits its
# lamps, so lighting the lens means lighting the whole part -- housing, metal
# frame and all. Doing that for some shapes and not others just makes the odd
# ones look like mistakes, so none of them glow.
#
# They still cast a beam and still switch on and off. The glow comes back on its
# own, with no change here, the moment a mesh gets a second material slot for its
# lens: the Cora and Zino headlights already work that way off M_HeadLight.
ALL_LAMP = re.compile(r"(?!)")          # matches nothing, deliberately

# What you hold and drop, as opposed to what bolts to the car. 588 of the 622
# existing rows use this one, and it is not decoration: the part meshes have no
# collision baked in, so holding one and dropping it sends it through the floor.
HELD_MESH = "/Game/Objects/VehicleAttachment/Meshes/EmergencyLightBar_01_Light"

# Shop icons, first match wins. The mod's own set is drawn for vehicle parts; a
# few vanilla ones fit better than anything in it.
MOD_ICON = "/Game/UI/MoreAttachments/"
ITEM_ICON = "/Game/UI/Icons/Item/"
ICONS = [
    (r"Light_", ITEM_ICON + "LightBulb"),
    # Both bumper meshes are bullbars and go on the front, rear name or not.
    (r"Bumper_\d+_(Front|Rear)|Nudge_Bar_Front", MOD_ICON + "FrontBumper"),
    (r"Nudge_Bar_Rear", MOD_ICON + "RearBumper"),
    (r"Nudge_Bar_Side|Running_Board", MOD_ICON + "SideSkirt"),
    (r"Scifi_Wing", MOD_ICON + "RearWing"),
    (r"Spoiler", MOD_ICON + "RearSpoiler"),
    (r"Rollcage|Roof_", MOD_ICON + "Roof"),
    (r"Bonnet_Clip", MOD_ICON + "Bonnet"),
    (r"Gear_Stick|Handbrake|E_Brake", MOD_ICON + "ControlPanel"),
    (r"Seat", ITEM_ICON + "Stool"),
    (r"Fire_Extinguisher", ITEM_ICON + "FireExtinguisher"),
    (r"Cooler_Radiator", ITEM_ICON + "Radiator"),
    (r"Number_Plate", ITEM_ICON + "Plate"),
    (r"Badge", ITEM_ICON + "Ornament"),
    (r"Wheelie_Bar|Sway_Bar|Tow_Hook", MOD_ICON + "Wheels"),
]
DEFAULT_ICON = MOD_ICON + "Utility"


def icon_for(mesh):
    for pattern, icon in ICONS:
        if re.search(pattern, mesh, re.I):
            return icon
    return DEFAULT_ICON

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


# The mesh names are an artist's filing system, not a shop label. Left alone they
# read as "Light Fog 02" and "Exotic 01 Spoiler 02", so the noise comes out and
# the words go in the order a person would say them. Order matters: the specific
# rewrites run before the generic tidy-up.
RENAMES = [
    (r"^Light_Police_Roof_(\d+)$", r"Police Light Bar \1"),
    (r"^Light_LightBar_(\d+)$", r"Light Bar \1"),
    (r"^Light_Fog_(\d+)$", r"Fog Light \1"),
    (r"^Light_Spot_(\d+)$", r"Spot Light \1"),
    (r"^Bumper_\d+_Front_(\d+)$", r"Front Bumper \1"),
    # Bumper_01_Rear_01/02 are bullbars, whatever the mesh happens to be called.
    (r"^Bumper_\d+_Rear_(\d+)$", r"Bullbar \1"),
    (r"^Nudge_Bar_(Front|Rear|Side)_(\d+)$", r"\1 Nudge Bar \2"),
    (r"^Child_Seat_(\d+)_Handle$", r"Child Seat Handle \1"),
    (r"^Intake_(\d+)_(Valve|Shroud)$", r"Intake \2 \1"),
    (r"^E_Brake_(\d+)$", r"E-Brake \1"),
    (r"^Scifi_Wing_(\d+)$", r"Sci-Fi Wing \1"),
    (r"^Motorbike_Exhaust_(\d+)$", r"Motorbike Exhaust \1"),
    # Body-style parts: "Exotic_01_Spoiler_02" -- the 01 is which car model the
    # artist drew it on and means nothing in a shop.
    (r"^([A-Za-z]+)_\d+_(Spoiler|Rollcage|Exhaust)_(\d+)(_Boot)?$",
     r"\1 \2 \3\4"),
]


def display(mesh):
    short = re.sub(r"^SM_Veh_(Attach_|)", "", mesh, flags=re.I)
    for pattern, into in RENAMES:
        new = re.sub(pattern, into, short)
        if new != short:
            short = new
            break
    return re.sub(r"\s+", " ", short.replace("_", " ")).strip()


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


def set_label(prop, label):
    """Write the shop name where the game actually looks for it.

    ItemNameTexts.Texts is the list the UI builds a name out of; ItemName is a
    string table lookup the vanilla rows use and ours cannot. Cloning a donor row
    and setting only ItemName leaves the donor's table entry in Texts, so every
    part inherits the donor's name -- 138 of them called Round Light 01.
    """
    for field in prop["Value"]:
        if not isinstance(field, dict) or field.get("Name") != "Texts":
            continue
        first = copy.deepcopy(field["Value"][0]) if field["Value"] else {
            "$type": "UAssetAPI.PropertyTypes.Objects.TextPropertyData, UAssetAPI",
            "Name": "0", "ArrayIndex": 0, "PropertyGuid": None, "IsZero": False,
            "PropertyTagFlags": "None", "PropertyTypeName": None,
            "PropertyTagExtensions": "NoExtension", "TransformType": "ToLower"}
        first.update({"Flags": 0, "HistoryType": "None", "Namespace": None,
                      "TableId": None, "CultureInvariantString": label,
                      "SourceFmt": None, "Arguments": None, "ArgumentsData": None,
                      "SourceValue": None, "FormatOptions": None,
                      "TargetCulture": None, "Name": "0", "Value": None})
        field["Value"] = [first]
        return True
    return False


def make_row(donor, key, label, package, mesh, actor, cost, mass):
    """Fill a row in. Pass a donor to clone for a new part, or an existing row to
    correct it in place -- which is how a renamed label reaches a shipped row."""
    row = copy.deepcopy(donor) if donor.get("Name") != key else donor
    row["Name"] = key
    for prop in row["Value"]:
        if prop["Name"] == "AttachmentPartActorClass":
            prop["Value"] = soft(f"{ACTOR_PACKAGE}/{actor}", actor + "_C")
        elif prop["Name"] == "StaticMesh":
            # The standard held prop, not the part's own mesh: these have no
            # collision, so holding one and dropping it drops it through the map.
            prop["Value"] = soft(HELD_MESH, HELD_MESH.rsplit("/", 1)[-1])
        elif prop["Name"] == "IconTexture":
            icon = icon_for(mesh)
            prop["Value"] = soft(icon, icon.rsplit("/", 1)[-1])
        elif prop["Name"] == "ItemName":
            # Not what the shop reads. Cleared, or the donor's string table entry
            # rides along and every part comes out called Round Light 01.
            prop.update({"CultureInvariantString": None, "Namespace": None,
                         "Value": None, "HistoryType": "None", "Flags": 0,
                         "TableId": None})
        elif prop["Name"] == "ItemNameTexts":
            set_label(prop, label)
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
        # Correct rows that are already there rather than skipping them: that is
        # how a renamed label, or a reprice, reaches a row from an earlier run.
        by_key = {r["Name"]: r for r in rows}
        fresh, updated = [], 0
        for args in new_rows:
            existing = by_key.get(args[0])
            if existing is not None:
                make_row(existing, *args)
                updated += 1
            else:
                fresh.append(make_row(donor, *args))
        rows.extend(fresh)
        register_names(table, [a[0] for a in new_rows] + [a[3] for a in new_rows]
                       + [HELD_MESH, HELD_MESH.rsplit("/", 1)[-1]]
                       + [i for _, i in ICONS] + [DEFAULT_ICON]
                       + [i.rsplit("/", 1)[-1] for _, i in ICONS]
                       + [DEFAULT_ICON.rsplit("/", 1)[-1]]
                       + [f"{a[2]}/{a[3]}" for a in new_rows]
                       + [f"{ACTOR_PACKAGE}/{a[4]}" for a in new_rows]
                       + [a[4] + "_C" for a in new_rows])
        print(f"  {tag}: +{len(fresh)} new, {updated} updated -> {len(rows)}", end="")
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
                key_of = lambda i: i.get("Value") if isinstance(i, dict) else i
                known = {key_of(i) for i in sold}
                gone = [i for i in sold
                        if str(key_of(i)).startswith(PREFIX) and key_of(i) not in set(keys)]
                for item in gone:
                    sold.remove(item)
                if gone:
                    print(f"\n  no longer sold: {len(gone)}", end="")
                known = {key_of(i) for i in sold}
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


def main(dry=False, rows_only=False):
    work = os.path.join(WORK, "newparts")
    os.makedirs(work, exist_ok=True)
    templates = {k: open(os.path.join(HERE, v), encoding="utf-8").read()
                 for k, v in TEMPLATES.items()}
    if not dry:
        os.makedirs(ACTORS_DIR, exist_ok=True)

    new_rows, keys, built, skipped = [], [], 0, 0
    for package, mesh, kind in wanted():
        copied = None if rows_only else copy_mesh(package, mesh, dry)
        if not rows_only and copied is None:
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
        if kind == "NONC":
            # Every template carries a ChangeLightColor interaction. On a part
            # with no paint and no lamp that is a menu entry that does nothing,
            # so it comes off -- an exhaust tip should not offer to be recoloured.
            for export in asset["Exports"]:
                if "MTInteractable" not in str(export.get("ObjectName")):
                    continue
                for prop in export.get("Data") or []:
                    if isinstance(prop, dict) and prop["Name"] == "InteractionParams":
                        prop["Value"] = []
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
        if not dry and not rows_only:
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

    # Take away what the spec no longer asks for. Dropping a part from the list
    # is not enough on its own -- its actor and its mesh would sit in the pak
    # forever, paid for in download size by everyone, referenced by nobody.
    keep_actors = {a[4] for a in new_rows}
    keep_meshes = {(a[2], a[3]) for a in new_rows}
    removed = 0
    if not dry and not rows_only:
        for name in sorted(os.listdir(ACTORS_DIR)) if os.path.isdir(ACTORS_DIR) else []:
            stem = name.split(".")[0]
            if stem.startswith(PREFIX) and stem not in keep_actors:
                os.remove(os.path.join(ACTORS_DIR, name))
                removed += name.endswith(".uasset")
        for package in {a[2] for a in new_rows}:
            folder = local(PAK, package)
            for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
                if (package, name.split(".")[0]) not in keep_meshes:
                    os.remove(os.path.join(folder, name))
    print(f"\n{built} actors built, {skipped} skipped, {removed} removed")
    add_rows(new_rows, keys, dry)
    print("\nPack both MoreAttachments paks.")


def demo():
    assert part_id("SM_Veh_Attach_Antenna_01") == "Attachment_SR_Antenna_01"
    assert part_id("SM_Veh_Exotic_01_Spoiler_02") == "Attachment_SR_Exotic_01_Spoiler_02"
    assert not part_id("SM_Veh_Attach_Turbo_01").startswith("Attachment_Turbo"),         "Attachment_Turbo_01 already exists; the namespace is what keeps it safe"
    assert display("SM_Veh_Attach_Roof_Scoop_01") == "Roof Scoop 01"
    assert display("SM_Veh_Attach_Light_Fog_02") == "Fog Light 02"
    assert display("SM_Veh_Attach_Light_Police_Roof_01") == "Police Light Bar 01"
    assert display("SM_Veh_Attach_Bumper_01_Front_01") == "Front Bumper 01"
    assert display("SM_Veh_Exotic_01_Spoiler_02") == "Exotic Spoiler 02",         "the model number the artist drew it on means nothing in a shop"
    assert display("SM_Veh_Attach_E_Brake_01") == "E-Brake 01"
    assert display("SM_Veh_Attach_Nudge_Bar_Side_02") == "Side Nudge Bar 02"

    assert icon_for("SM_Veh_Attach_Light_Fog_02").endswith("LightBulb")
    assert icon_for("SM_Veh_Attach_Bumper_01_Front_01").endswith("FrontBumper")
    assert icon_for("SM_Veh_Attach_Bumper_01_Rear_01").endswith("FrontBumper"),         "the rear bumper meshes are bullbars and go on the front"
    assert icon_for("SM_Veh_Attach_Nudge_Bar_Rear_02").endswith("RearBumper")
    assert icon_for("SM_Veh_Exotic_01_Spoiler_02").endswith("RearSpoiler")
    assert icon_for("SM_Veh_Ute_01_Rollcage_01").endswith("Roof")
    assert icon_for("SM_Veh_Attach_Seat_02").endswith("Stool")
    assert icon_for("SM_Veh_Attach_Number_Plate_01").endswith("Plate")
    assert icon_for("SM_Veh_Attach_Turbo_01") == DEFAULT_ICON, "no icon fits, fall back"
    assert not ALL_LAMP.search("SM_Veh_Attach_Light_LightBar_03"),         "a light bar has a metal frame that must not glow with the lenses"
    assert not ALL_LAMP.search("SM_Veh_Attach_Light_Police_Roof_01")
    assert not ALL_LAMP.search("SM_Veh_Attach_Light_Fog_02"),         "one slot means glowing the whole lamp, so none of them glow for now"

    texts = {"Name": "ItemNameTexts", "Value": [
        {"Name": "Texts", "Value": [
            {"HistoryType": "StringTableEntry", "TableId": "/Game/T.T",
             "CultureInvariantString": None, "Value": "RoundLight"}]}]}
    assert set_label(texts, "Fog Light 02") is True
    got = texts["Value"][0]["Value"]
    assert len(got) == 1 and got[0]["CultureInvariantString"] == "Fog Light 02"
    assert got[0]["HistoryType"] == "None" and got[0]["TableId"] is None,         "the donor's string table entry has to go, or its name wins"
    assert got[0]["Value"] is None

    donor = {"Name": "Donor", "Value": [
        {"Name": "ItemName", "CultureInvariantString": None, "Value": "Light"},
        {"Name": "ItemNameTexts", "Value": [
            {"Name": "Texts", "Value": [
                {"HistoryType": "StringTableEntry", "CultureInvariantString": None,
                 "Value": "RoundLight"}]}]},
        {"Name": "Cost"}, {"Name": "MassKg"}]}
    made = make_row(donor, "K", "Label", "/Game/P", "M", "A", 5, 6.0)
    assert made is not donor and donor["Name"] == "Donor", "a donor must be cloned"
    again = make_row(made, "K", "Renamed", "/Game/P", "M", "A", 5, 6.0)
    assert again is made, "an existing row is corrected in place, not duplicated"
    shown = next(p for p in made["Value"] if p["Name"] == "ItemNameTexts")
    assert shown["Value"][0]["Value"][0]["CultureInvariantString"] == "Renamed"
    name = next(p for p in made["Value"] if p["Name"] == "ItemName")
    assert name["Value"] is None and name["CultureInvariantString"] is None,         "the donor's string table lookup must not survive"
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
        main(dry="--dry" in sys.argv, rows_only="--rows" in sys.argv)
