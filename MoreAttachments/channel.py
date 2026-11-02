"""MoreAttachments on 0.7.20, as its own Items table, listed by the DataTableFramework.

    python MoreAttachments/channel.py

    Items_MoreAttachments  one file: every MoreAttachments row (the free and premium
                           paks share it), plus vanilla's attachments with the scale
                           range opened like ours -- plus the mod's own copy of
                           the Items composite listing it, so it works alone. The
                           framework lists it by name (registry.json "adopted").

No pak ships Items_AttachmentPart any more. What still ships whole is the vendor
-- Vendor_Garage is an NPC blueprint, not a composite -- rebuilt from 0.7.20's
copy: vanilla's items, then ours in the order they always had.

Rows come from the tables as last shipped (old/0.7.19/), rebased like the part
tables. On top of them:

- Paint and lights (native.py). 0.7.20's AttachmentPaintSlots (colour, metallic,
  roughness) paint the mesh's own material, so a part with car-paint slots gets
  one slot each and its actor stops overriding them; a palette-only car part gets
  its own mesh copy on M_Gray; lamp sections become switchable lights, one control
  per section with labelled lines for the MoreAttachments plugin. Textured props
  stay as they are.
- Templates. Generated actors never get the lamp template: a bumper with
  lights built in is still a bumper, and ToggleLight on it does nothing.
- New parts. Body parts, bull bars and wheels that 0.7.20 added get an actor and
  a row, the way run.py makes them, cloned from a row of the same kind with
  every name field set (a clone otherwise reads as its donor).

Saves key attachments by row name, so no existing row is renamed or dropped;
the build fails if one would be.
"""
import copy
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(REPO, "Rebase"))
from pipeline import (CURRENT_MAPPINGS, VANILLA, WORK, from_json, register_names,  # noqa: E402
                      to_json)
from rebase import fnames_in, rebase  # noqa: E402
from paint import mesh_of  # noqa: E402
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "dtframework", os.path.join(REPO, "DataTableFramework", "run.py"))
framework = importlib.util.module_from_spec(spec)
spec.loader.exec_module(framework)

# run.py is a script with its helpers above "# Logic Start"; take those, not the run.
_here = os.getcwd()
os.chdir(HERE)
_src = open("run.py", encoding="utf-8").read()
helpers = {"__name__": "ma_helpers"}
exec(compile(_src[:_src.index("# Logic Start")], "run.py", "exec"), helpers)  # noqa: S102
os.chdir(_here)

OLD = os.path.join(HERE, "old", "0.7.19")
MAIN = os.path.join(REPO, "qxZap_satigt3_MoreAttachments_P", "MotorTown", "Content")
PREMIUM = os.path.join(REPO, "qxZap_satigt3_MoreAttachments_Premium_P", "MotorTown", "Content")
ACTORS = os.path.join(MAIN, "Objects", "MoreAttachments")
ACTOR_ROOT = "/Game/Objects/MoreAttachments"
# Which parts 0.7.20 added, decided once against a 0.7.19 extract and kept in the
# repo: extract folders get overwritten by the next export (vanilla_extract was,
# on 28 Oct, which made every 0.7.20 part look old). Delete the file to redo it.
NEW_PARTS = os.path.join(HERE, "new_in_0.7.20.json")
BASELINE = r"D:\MTLiveMap\vanilla_extract_server\MotorTown\Content"  # 0.7.19, Sep 2026
WORK_MA = os.path.join(WORK, "ma")
COMP = "Items"
OWN_TABLE = "/Game/DataAsset/Items/Items_MoreAttachments"  # what we ship
TABLE = os.path.join("DataAsset", "Items", "Items_AttachmentPart.uasset")
VENDOR = os.path.join("Characters", "NPC", "Vendor_Garage.uasset")
TEXT = "UAssetAPI.PropertyTypes.Objects.TextPropertyData"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rows_of(table):
    return table["Exports"][0]["Table"]["Data"]


def prop(row, name):
    return next((p for p in row["Value"] if p["Name"] == name), None)


def read(path, tag, mappings=CURRENT_MAPPINGS):
    os.makedirs(WORK_MA, exist_ok=True)
    return load(to_json(path, os.path.join(WORK_MA, tag + ".json"), mappings))


# ---- what a part is, read off the 0.7.20 part tables -------------------------

def is_new(package):
    rel = package[len("/Game/"):].replace("/", os.sep) + ".uasset"
    return not os.path.isfile(os.path.join(BASELINE, rel))


def new_in_0720(parts, have):
    """Part ids 0.7.20 added that no attachment covers yet -- from NEW_PARTS if saved."""
    if os.path.isfile(NEW_PARTS):
        return set(load(NEW_PARTS))
    if os.path.isdir(os.path.join(BASELINE, "Cars", "Models", "Duro")):
        sys.exit(f"FAIL: {BASELINE} has 0.7.20 content -- it cannot tell new parts from old")
    ids = sorted(p["part_id"] for p in parts.values()
                 if "Attachment_" + p["part_id"] not in have and is_new(p["mesh_path"]))
    with open(NEW_PARTS, "w", encoding="utf-8") as f:
        json.dump(ids, f, indent=1)
    return set(ids)


def part_sources():
    """Every 0.7.20 part an attachment can be made of -> {part_id: info}."""
    out = {}
    for name, colorable in (("AeroParts", True), ("VehicleParts0", True)):
        table = read(os.path.join(VANILLA, "DataAsset", "VehicleParts", name + ".uasset"),
                     name + ".vanilla720")
        for row in rows_of(table):
            mesh = mesh_of(table, row)
            if not mesh:
                continue
            ptype = (prop(row, "PartType") or {}).get("Value") or ""
            out[row["Name"]] = {
                "part_id": row["Name"], "mesh_path": mesh[0], "mesh_id": mesh[1],
                "price": (prop(row, "Cost") or {}).get("Value") or 2000,
                "mass": (prop(row, "MassKg") or {}).get("Value"),
                "part_type": ptype, "colorable_actor": colorable,
                "color_slots": (prop(row, "ColorSlots") or {}).get("Value") or []}
    # The folders run.py scans for extras; only what 0.7.20 added is new here.
    for sub in ("Wheels", "ControlPanel"):
        folder = os.path.join(VANILLA, "Cars", "Parts", sub)
        for f in sorted(os.listdir(folder)):
            stem = f[: -len(".uasset")] if f.endswith(".uasset") else None
            if not stem or re.search(r"_(R|RL|RRD)$", stem):
                continue
            pid = stem[:-2] if stem.endswith("_L") else stem
            out.setdefault(pid, {
                "part_id": pid, "mesh_path": f"/Game/Cars/Parts/{sub}/{stem}", "mesh_id": stem,
                "price": 2000, "mass": 50, "part_type": sub, "colorable_actor": False,
                "color_slots": []})
    return out


# ---- rows ---------------------------------------------------------------------

def paint_slots(color_slots, template):
    """A part's ColorSlots map -> AttachmentPaintSlots entries, in map order."""
    out = []
    for i, (key, value) in enumerate(color_slots):
        entry = copy.deepcopy(template)
        entry["Name"] = str(i)
        for p in entry["Value"]:
            if p["Name"] == "MaterialSlotName":
                p["Value"] = key["Value"]
            elif p["Name"] == "SaveIndex":
                p["Value"], p["IsZero"] = i, i == 0
            elif p["Name"] == "Slot":
                p["Value"] = copy.deepcopy(value["Value"])
        out.append(entry)
    return out


def whitened(slot_value):
    """A colour slot that starts white -- what vanilla's own paintable body parts default
    to (AeroParts: 255,255,255, metallic 0.3, roughness 0.5) -- not the antenna's gray."""
    out = copy.deepcopy(slot_value)
    for p in out:
        if p["Name"] == "DefaultColor":
            p["Value"][0]["Value"] = "255, 255, 255"
        elif p["Name"] == "DefaultMetallic":
            p["Value"] = 0.30000001192092896
        elif p["Name"] == "DefaultRoughness":
            p["Value"] = 0.5
    return out


def labelled(slot_value, label):
    """An MTVehicleColorSlot body whose shown name is `label` (literal text)."""
    out = copy.deepcopy(slot_value)
    for p in out:
        if p["Name"] == "DisplayName2":
            for arr in p["Value"]:
                if arr["Name"] == "Texts" and arr["Value"]:
                    t = arr["Value"][0]
                    t.pop("TableId", None)
                    t.update(HistoryType="None", Namespace=None, Value=None,
                             CultureInvariantString=label)
                    arr["Value"] = [t]
    return out


def with_extra(slot_value, sections):
    """An MTVehicleColorSlot body that also paints `sections` (ExtraMaterialSlotNames)."""
    out = copy.deepcopy(slot_value)
    for p in out:
        if p["Name"] == "ExtraMaterialSlotNames":
            p["Value"] = [{"$type": "UAssetAPI.PropertyTypes.Objects.NamePropertyData, UAssetAPI",
                           "Name": str(i), "ArrayIndex": 0, "PropertyGuid": None, "IsZero": False,
                           "PropertyTagFlags": "None", "PropertyTypeName": None,
                           "PropertyTagExtensions": "NoExtension", "Value": s}
                          for i, s in enumerate(sections)]
    return out


def set_name(row, text):
    """Every display-name field, as a literal -- the shop reads ItemNameTexts."""
    def walk(n):
        if isinstance(n, dict):
            if n.get("$type", "").startswith(TEXT):
                n.update(HistoryType="None", Namespace=None, Value=None,
                         CultureInvariantString=text)
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    for name in ("ItemNameAndNumber", "ItemNameTexts"):
        if prop(row, name):
            walk(prop(row, name))


def display_name(part):
    t = helpers["clean_part_name"](part["part_type"])
    return (t + " " + helpers["clean_part_name"](part["part_id"])
            .replace(f" {part['part_type']} ", " ").replace(f" {t} ", " ")).strip()


def new_row(donor, part):
    row = copy.deepcopy(donor)
    old_id, new_id = donor["Name"], "Attachment_" + part["part_id"]
    row["Name"] = new_id
    set_name(row, display_name(part))
    prop(row, "Cost")["Value"] = part["price"]
    prop(row, "MassKg")["Value"] = float(part["mass"] or 0)
    actor = prop(row, "AttachmentPartActorClass")["Value"]["AssetPath"]
    actor["PackageName"] = actor["PackageName"].replace(old_id, new_id)
    actor["AssetName"] = actor["AssetName"].replace(old_id, new_id)
    icon = os.path.join(MAIN, "UI", "MoreAttachments", part["part_type"] + ".uasset")
    if os.path.isfile(icon):
        prop(row, "IconTexture")["Value"]["AssetPath"].update(
            PackageName=f"/Game/UI/MoreAttachments/{part['part_type']}",
            AssetName=part["part_type"])
    return row


def new_actor(part):
    name = "Attachment_" + part["part_id"]
    mesh = read(os.path.join(VANILLA, *part["mesh_path"][len("/Game/"):].split("/")) + ".uasset",
                "mesh")
    bounds = [(-1) * b for b in helpers["get_x_bounding"](mesh)] \
        if helpers["get_x_bounding"](mesh) != "+0" else [0.0, 0.0, 0.0]
    actor = helpers["make_new_actor"](ACTOR_ROOT, name, part["mesh_id"], part["mesh_path"],
                                      bounds, colorable_actor=part["colorable_actor"],
                                      # Never the lamp template: everything made
                                      # here is a body part, wheel or panel, and
                                      # a bumper with lights built in (Duro 02)
                                      # is still a bumper -- no ToggleLight.
                                      lens_bounding=None)
    src = os.path.join(WORK_MA, name + ".json")
    with open(src, "w", encoding="utf-8") as f:
        json.dump(actor, f)
    out = from_json(src, os.path.join(ACTORS, name + ".uasset"))
    back = read(out, "actor.check")
    if any(e["$type"].startswith("UAssetAPI.ExportTypes.RawExport") for e in back["Exports"]):
        sys.exit(f"FAIL: actor {name} reads back raw")


# ---- vendor -------------------------------------------------------------------

def place(names, new, group_of):
    """names with each of new inserted into its own group, in alphabetical place.

    The list is grouped by part type -- every bonnet, then every fender, then
    the front bumpers, Atlas to Zydro -- and the shop shows it in that order. A
    part appended at the end lands below all the props, where nobody looks for a
    bumper. Only the group's longest run counts -- the lamps were moved to the
    top, and one wheel-arch light among them must not pull every new wheel up
    there. One with no group yet goes at the end.
    """
    out = list(names)
    for name in new:
        g = group_of(name)
        runs, start = [], None
        for i, n in enumerate(out + [None]):
            if g and n is not None and group_of(n) == g:
                start = i if start is None else start
            elif start is not None:
                runs.append((start, i))
                start = None
        if not runs:
            out.append(name)
            continue
        lo, hi = max(runs, key=lambda r: r[1] - r[0])
        after = [i for i in range(lo, hi) if out[i].lower() > name.lower()]
        out.insert(after[0] if after else hi, name)
    return out


def sell_items(vendor):
    for e in vendor["Exports"]:
        for p in e.get("Data") or []:
            if isinstance(p, dict) and p.get("Name") == "SellItems":
                return p["Value"]
    sys.exit("no SellItems in vendor")


def build_vendor(shipped_path, extra, dest, group_of):
    vendor = read(os.path.join(VANILLA, VENDOR), "Vendor_Garage.vanilla720")
    items = sell_items(vendor)
    have = {x["Value"] for x in items}
    shipped = [x["Value"] for x in sell_items(read(shipped_path, "vendor.old", "MotorTown719"))]
    wanted = place([n for n in dict.fromkeys(shipped) if n not in have],
                   [n for n in extra if n not in have and n not in shipped], group_of)
    for name in wanted:
        entry = copy.deepcopy(items[-1])
        entry["Name"], entry["Value"] = str(len(items)), name
        items.append(entry)
    register_names(vendor, wanted)
    src = os.path.join(WORK_MA, "Vendor_Garage.json")
    with open(src, "w", encoding="utf-8") as f:
        json.dump(vendor, f)
    os.makedirs(os.path.dirname(os.path.join(dest, VENDOR)), exist_ok=True)
    out = from_json(src, os.path.join(dest, VENDOR))
    print(f"  vendor -> {len(items)} items ({os.path.relpath(dest, REPO).split(os.sep)[0]})")
    return out


# ---- build ----------------------------------------------------------------------

def main():
    vanilla = read(os.path.join(VANILLA, TABLE), "Items_AttachmentPart.vanilla720")
    shipped = read(os.path.join(OLD, "main", TABLE), "ma.main.old", "MotorTown719")
    merged, kept, added = rebase(vanilla, shipped)
    own = rows_of(merged)[kept:]
    before = {r["Name"] for r in rows_of(shipped)} - {r["Name"] for r in rows_of(vanilla)}
    lost = before - {r["Name"] for r in own}
    if lost:
        sys.exit(f"FAIL: rows would disappear from saves: {sorted(lost)[:10]}")

    template = next(prop(r, "AttachmentPaintSlots")["Value"][0] for r in rows_of(vanilla)
                    if (prop(r, "AttachmentPaintSlots") or {}).get("Value"))
    parts = part_sources()
    by_id = {r["Name"]: r for r in own}

    # New 0.7.20 parts: a mesh no attachment uses yet, and one 0.7.19 did not have.
    donors = {False: by_id["Attachment_Vista_Bonnet_01"],
              True: next(r for n, r in by_id.items() if "Wheel" in n)}
    wanted = new_in_0720(parts, by_id)
    fresh = [p for p in parts.values() if p["part_id"] in wanted]
    for part in fresh:
        new_actor(part)
        row = new_row(donors[part["part_type"] == "Wheels"], part)
        by_id[row["Name"]] = row
    # Hand-made extras (Attachment_BullbarMuhan_01) have no part row; their name
    # still says what they are.
    kinds = sorted({p["part_type"] for p in parts.values() if p["part_type"]}, key=len, reverse=True)
    group_of = lambda n: ((parts.get(n[len("Attachment_"):]) or {}).get("part_type")  # noqa: E731
                          or next((k for k in kinds if k.lower() in n.lower()), None))
    order = place([r["Name"] for r in own], ["Attachment_" + p["part_id"] for p in fresh], group_of)
    own = [by_id[n] for n in order]
    print(f"  {len(fresh)} new attachments: {sorted(p['part_id'] for p in fresh)}")

    # 0.7.20 native paint + per-section lights (native.py): every actor rebuilt from
    # its pristine snapshot; the rows get one paint slot per mesh slot it paints.
    import native
    painted = native.convert_all(regenerated={"Attachment_" + p["part_id"] for p in fresh})
    body = whitened(next(p["Value"] for p in template["Value"] if p["Name"] == "Slot"))
    for row in own:
        slots = prop(row, "AttachmentPaintSlots")
        if slots is None:
            continue
        actor = prop(row, "AttachmentPartActorClass")["Value"]["AssetPath"]["PackageName"] or ""
        names = painted.get(actor.rsplit("/", 1)[-1], [])
        # a car wheel's paint sections are its rim (Wheel_01/02, as vanilla's own wheels);
        # the tyre is the palette section and keeps its rubber
        if names and all(n.startswith("Wheel_") for n in names):
            # a car wheel's paint sections are its rim (Wheel_01/02, as vanilla's and
            # Wheel Works' own wheels); the tyre is the palette section and keeps its rubber
            pairs = [({"Value": n}, {"Value": labelled(body, "Rim" if len(names) == 1 else f"Rim {k + 1}")})
                     for k, n in enumerate(names)]
        else:
            pairs = [({"Value": n}, {"Value": body if len(names) == 1 else labelled(body, f"Body {k + 1}")})
                     for k, n in enumerate(names)]
        slots["Value"] = paint_slots(pairs, template) if names else []

    scale = {n: prop(by_id["Attachment_Vista_Bonnet_01"], n)["Value"]
             for n in ("AttachmentScaleMin", "AttachmentScaleMax")}
    opened = []
    for row in copy.deepcopy(rows_of(vanilla)):
        if all(prop(row, n)["Value"] == v for n, v in scale.items()):
            continue
        for n, v in scale.items():
            prop(row, n)["Value"] = v
        opened.append(row)

    # merged is vanilla's table with our imports appended, so vanilla's rows'
    # references stay valid in it and both kinds share the one file.
    import shutil
    shutil.rmtree(os.path.join(MAIN, "DataTableFramework"), ignore_errors=True)  # the old Items Ch0001
    rows = own + opened
    table = framework.make_table(merged, OWN_TABLE, rows)
    register_names(table, [x for r in rows for x in fnames_in(r)])
    framework.write_table(table, OWN_TABLE, MAIN)
    framework.mod_composite(COMP, [OWN_TABLE], MAIN)  # works without the framework
    print(f"  {OWN_TABLE.rsplit('/', 1)[1]}: {len(own)} attachments + {len(opened)} vanilla scale rows")

    new_ids = ["Attachment_" + p["part_id"] for p in fresh]
    build_vendor(os.path.join(OLD, "main", VENDOR), new_ids, MAIN, group_of)
    build_vendor(os.path.join(OLD, "premium", VENDOR), new_ids, PREMIUM, group_of)


def demo():
    extra = with_extra([{"Name": "ExtraMaterialSlotNames", "Value": []}], ["Wheel_02"])
    assert [e["Value"] for e in extra[0]["Value"]] == ["Wheel_02"], extra
    key = {"Value": "RearWing"}
    value = {"Value": [{"Name": "DefaultMetallic", "Value": 0.3}]}
    template = {"Name": "0", "Value": [{"Name": "MaterialSlotName", "Value": "Body_01"},
                                       {"Name": "SaveIndex", "Value": 0, "IsZero": True},
                                       {"Name": "Slot", "Value": []}]}
    out = paint_slots([(key, value), ({"Value": "Trim"}, value)], template)
    assert [s["Value"][0]["Value"] for s in out] == ["RearWing", "Trim"]
    assert [s["Value"][1]["Value"] for s in out] == [0, 1]
    assert out[0]["Value"][2]["Value"] == [{"Name": "DefaultMetallic", "Value": 0.3}]
    assert template["Value"][0]["Value"] == "Body_01", "template must stay untouched"
    gray = [{"Name": "DefaultColor", "Value": [{"Value": "98, 98, 98"}]}, {"Name": "DefaultRoughness", "Value": 0.375}]
    white = whitened(gray)
    assert white[0]["Value"][0]["Value"] == "255, 255, 255" and white[1]["Value"] == 0.5
    assert gray[0]["Value"][0]["Value"] == "98, 98, 98", "the source slot stays as it was"
    kind = {"A_Atlas_FB": "FB", "A_Zydro_FB": "FB", "A_Cora_Bonnet": "Bonnet", "A_Prop": None,
            "A_Duro_FB": "FB", "A_New_Thing": "Hitch", "A_Lamp_W": "W", "A_W1": "W", "A_W3": "W",
            "A_W2": "W"}.get
    assert place(["A_Lamp_W", "A_Prop", "A_W1", "A_W3"], ["A_W2"], kind) ==         ["A_Lamp_W", "A_Prop", "A_W1", "A_W2", "A_W3"], "longest run wins over a stray"
    assert place(["A_Cora_Bonnet", "A_Atlas_FB", "A_Zydro_FB", "A_Prop"], ["A_Duro_FB", "A_New_Thing"], kind)         == ["A_Cora_Bonnet", "A_Atlas_FB", "A_Duro_FB", "A_Zydro_FB", "A_Prop", "A_New_Thing"]
    assert display_name({"part_type": "FrontBumper", "part_id": "Duro_FrontBumper_01"}) \
        == "Front Bumper Duro 1"
    print("ok")


if __name__ == "__main__":
    demo() if sys.argv[1:] == ["demo"] else main()
