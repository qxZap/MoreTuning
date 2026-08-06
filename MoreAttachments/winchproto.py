"""Prototype: give an attachment actor a real winch component.

    python winchproto.py create        # build the winch attachment, first in the list
    python winchproto.py <ActorName>   # or add the component to an existing actor
    python winchproto.py demo

Winches in this game are driven by MTWinchComponent, which is C++ -- it appears
in no content asset, so it is attached at runtime rather than authored. What you
interact with are two plain Actor blueprints holding a mesh each:

    /Game/Objects/Item/IT_WinchHook        the hook you grab
    /Game/Objects/Item/IT_WinchController  the remote that spools in and out

and the C++ side has PickupWinchHook, PickupWinchController, EMTWinchControl,
AttachWinch and CutWinchCable to go with them.

The opening is that MoreAttachments' own actors already carry MotorTown C++
components -- MTInteractableComponent and MTLightControlComponent -- declared as
SCS nodes in the blueprint. So a component can be added to an attachment purely
by editing the asset, no editor required. This does that with MTWinchComponent.

Whether the component does anything useful hanging off an attachment rather than
a vehicle is exactly the unknown worth testing; it may want a parent vehicle, a
rope and hook sockets it will not find here.
"""
import copy
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from pipeline import WORK, from_json, register_names, to_json  # noqa: E402

ACTORS = os.path.join(HERE, "..", "qxZap_satigt3_MoreAttachments_P", "MotorTown",
                      "Content", "Objects", "MoreAttachments")
COMPONENT = "MTWinchComponent"
VARIABLE = "MTWinch"
MOTORTOWN = "/Script/MotorTown"

# The component keeps its own PartRow and looks it up by key, so the winch's
# pulling force and rope length come from an existing row rather than anything
# new: Winch_Tow_04 is the 20t one, the strongest without Motor Works installed.
PART_KEY = "Winch_Tow_04"
NODE_GUID = "{7A19C400-0000-0000-0000-00000000B17C}"

# Copy the shape of a component the template already carries rather than
# inventing one: same import layout, same export layout, same SCS wiring.
# The interactable, not the light control -- that one is a plain ActorComponent
# and this is a scene component, which the loader treats differently.
MODEL_COMPONENT = "MTInteractable_GEN_VARIABLE"


def find_export(asset, name):
    for index, export in enumerate(asset["Exports"]):
        if export["ObjectName"] == name:
            return index, export
    return None, None


def find_import(asset, name):
    for index, entry in enumerate(asset["Imports"]):
        if entry["ObjectName"] == name:
            return -(index + 1), entry
    return None, None


def prop_of(export, name):
    for entry in export.get("Data") or []:
        if isinstance(entry, dict) and entry["Name"] == name:
            return entry
    return None


def name_prop(name, value):
    return {"$type": "UAssetAPI.PropertyTypes.Objects.NamePropertyData, UAssetAPI",
            "Name": name, "ArrayIndex": 0, "PropertyGuid": None, "IsZero": False,
            "PropertyTagFlags": "None", "PropertyTypeName": None,
            "PropertyTagExtensions": "NoExtension", "Value": value}


def add_component(asset):
    """Add COMPONENT as an SCS node. Returns False if it is already there.

    An export is not just its class and data -- the package header also declares
    what has to exist before it can be created and before it can be read, in four
    dependency arrays. Clone an export without rewriting those and the file still
    points at whatever the donor needed, which is how the first attempt at this
    produced "corrupt data found" on load rather than a running winch.
    """
    if find_export(asset, VARIABLE + "_GEN_VARIABLE")[1] is not None:
        return False

    model_index, model = find_export(asset, MODEL_COMPONENT)
    if model is None:
        sys.exit(f"{MODEL_COMPONENT} not in this actor -- nothing to copy the shape from")
    script_index, script = find_export(asset, "SimpleConstructionScript_0")
    if script is None:
        sys.exit("no SimpleConstructionScript_0")
    node_index, node_model = next(((i, e) for i, e in enumerate(asset["Exports"])
                                   if e["ObjectName"].startswith("SCS_Node_")
                                   and not any(p["Name"] == "ChildNodes" for p in e.get("Data", []))),
                                  (None, None))
    if node_model is None:
        sys.exit("no leaf SCS_Node to copy")

    motortown, _ = find_import(asset, MOTORTOWN)
    if motortown is None:
        sys.exit(f"{MOTORTOWN} is not imported")
    class_export = model["OuterIndex"]                 # the generated Blueprint class

    # Class import, then its default object -- mirrors MTLightControlComponent.
    asset["Imports"].append({"$type": "UAssetAPI.Import, UAssetAPI",
                             "ObjectName": COMPONENT, "OuterIndex": motortown,
                             "ClassPackage": "/Script/CoreUObject", "ClassName": "Class",
                             "PackageName": None, "bImportOptional": False})
    class_link = -len(asset["Imports"])
    asset["Imports"].append({"$type": "UAssetAPI.Import, UAssetAPI",
                             "ObjectName": "Default__" + COMPONENT, "OuterIndex": motortown,
                             "ClassPackage": MOTORTOWN, "ClassName": COMPONENT,
                             "PackageName": None, "bImportOptional": False})
    default_link = -len(asset["Imports"])

    # The component template. MTWinchComponent derives from StaticMeshComponent,
    # so it is a scene component and has to hang off the actor's root like one.
    component = copy.deepcopy(model)
    component["ObjectName"] = VARIABLE + "_GEN_VARIABLE"
    component["ClassIndex"] = class_link
    component["TemplateIndex"] = default_link
    component["Data"] = [name_prop("Net_WinchPartKey", PART_KEY)]
    component["SerializationBeforeSerializationDependencies"] = [class_export]
    component["CreateBeforeSerializationDependencies"] = []
    component["SerializationBeforeCreateDependencies"] = [class_link, default_link]
    component["CreateBeforeCreateDependencies"] = [class_export]
    asset["Exports"].append(component)
    component_index = len(asset["Exports"])            # exports are 1-based when referenced

    # The SCS node that mounts it.
    node = copy.deepcopy(node_model)
    node["ObjectName"] = "SCS_Node_" + VARIABLE
    for entry in node.get("Data", []):
        if entry["Name"] == "ComponentClass":
            entry["Value"] = class_link
        elif entry["Name"] == "ComponentTemplate":
            entry["Value"] = component_index
        elif entry["Name"] == "InternalVariableName":
            entry["Value"] = VARIABLE
        elif entry["Name"] == "VariableGuid":
            # Cloned wholesale this repeats the donor's guid, and two nodes
            # claiming the same variable is its own kind of broken.
            for field in entry["Value"]:
                field["Value"] = NODE_GUID
    node["SerializationBeforeSerializationDependencies"] = []
    node["CreateBeforeSerializationDependencies"] = [component_index, class_link]
    node["CreateBeforeCreateDependencies"] = [script_index + 1]
    asset["Exports"].append(node)
    node_ref = len(asset["Exports"])

    # A scene component is parented, not rooted: it goes under the actor's own
    # scene node. RootNodes is for the loose ActorComponents like the light
    # control, and putting a scene component there is what the game rejects.
    scene_index, _ = find_export(asset, "Scene_GEN_VARIABLE")
    parent = next((e for e in asset["Exports"]
                   if e["ObjectName"].startswith("SCS_Node_")
                   and (prop_of(e, "ComponentTemplate") or {}).get("Value") == scene_index + 1),
                  None)
    children = prop_of(parent, "ChildNodes") if parent is not None else None
    if children is None:
        sys.exit("no scene SCS node to parent the winch under")
    item = copy.deepcopy(children["Value"][0])
    item["Name"] = str(len(children["Value"]))
    item["Value"] = node_ref
    children["Value"].append(item)

    all_nodes = prop_of(script, "AllNodes")
    item = copy.deepcopy(all_nodes["Value"][0])
    item["Name"] = str(len(all_nodes["Value"]))
    item["Value"] = node_ref
    all_nodes["Value"].append(item)
    # The script has to know to build the node before it is read back.
    script.setdefault("CreateBeforeSerializationDependencies", []).append(node_ref)

    register_names(asset, [COMPONENT, "Default__" + COMPONENT, PART_KEY,
                           "Net_WinchPartKey", VARIABLE + "_GEN_VARIABLE",
                           "SCS_Node_" + VARIABLE, VARIABLE])
    return True


NEW_ACTOR = "Attachment_qxWinch"
NEW_ROW = "Attachment_qxWinch"
NEW_LABEL = "Winch (test)"
NEW_MESH = "/Game/Cars/Parts/Winch/Winch_01_Body"
TEMPLATE = os.path.join(HERE, "ACTOR_TEMPLATE.json")
TEMPLATE_NAME = "Attachment_Neo_RearSpoiler_01"
TEMPLATE_MESH = "/Game/Cars/Models/Neo/RearSpoiler_01"
def _pak(name, *parts):
    return os.path.join(HERE, "..", name, "MotorTown", "Content", *parts)


# Both paks ship the table and the vendor, and _Premium_P sorts after _P, so the
# premium one wins wherever both are installed. Editing only the free pak leaves
# the change invisible. run.py writes both for the same reason.
#
# A row in Items_AttachmentPart only defines the part; it does not appear in game
# until the vendor is told to sell it -- MTVendor's SellItems on Vendor_Garage.
PAKS = [
    (_pak("qxZap_satigt3_MoreAttachments_P", "DataAsset", "Items", "Items_AttachmentPart.uasset"),
     _pak("qxZap_satigt3_MoreAttachments_P", "Characters", "NPC", "Vendor_Garage.uasset")),
    (_pak("qxZap_satigt3_MoreAttachments_Premium_P",
          "DataAsset", "Items", "Items_AttachmentPart.uasset"),
     _pak("qxZap_satigt3_MoreAttachments_Premium_P", "Characters", "NPC", "Vendor_Garage.uasset")),
]


def sell_first(vendor_asset, key):
    """Put an item key at the front of the vendor's SellItems. True if it moved."""
    for export in vendor_asset["Exports"]:
        for entry in export.get("Data") or []:
            if entry["Name"] != "SellItems":
                continue
            items = entry["Value"]
            existing = [i for i in items
                        if (i.get("Value") if isinstance(i, dict) else i) == key]
            for item in existing:
                items.remove(item)
            first = copy.deepcopy(items[0])
            if isinstance(first, dict):
                first["Value"] = key
            else:
                first = key
            items.insert(0, first)
            for index, item in enumerate(items):
                if isinstance(item, dict) and "Name" in item:
                    item["Name"] = str(index)
            return len(items)
    return None


def soft_path(package, asset):
    return {"$type": "UAssetAPI.PropertyTypes.Objects.FSoftObjectPath, UAssetAPI",
            "AssetPath": {"$type": "UAssetAPI.PropertyTypes.Objects.FTopLevelAssetPath, UAssetAPI",
                          "PackageName": package, "AssetName": asset},
            "SubPathString": None}


def create():
    """Build a winch attachment of its own and put its row first in the list."""
    work = os.path.join(WORK, "winch")
    os.makedirs(work, exist_ok=True)

    # 1. the actor: the template, repointed at a winch body, plus the component
    with open(TEMPLATE, encoding="utf-8") as f:
        text = f.read()
    # Actor name first. The template's own name ends in the mesh's name, so
    # renaming the mesh first eats it -- which leaves the package called
    # Attachment_qxWinch while its class is still called after the donor mesh,
    # and a row pointing at a class that does not exist.
    text = text.replace(TEMPLATE_NAME, NEW_ACTOR)
    text = text.replace(TEMPLATE_MESH, NEW_MESH)
    text = text.replace(TEMPLATE_MESH.rsplit("/", 1)[-1], NEW_MESH.rsplit("/", 1)[-1])
    asset = json.loads(text)
    if not add_component(asset):
        sys.exit("template already carries the component")

    actor_json = os.path.join(work, NEW_ACTOR + ".json")
    with open(actor_json, "w", encoding="utf-8") as f:
        json.dump(asset, f, indent=1)
    built = from_json(actor_json, os.path.join(work, NEW_ACTOR + ".uasset"))
    check = to_json(built, os.path.join(work, NEW_ACTOR + ".check.json"))
    with open(check, encoding="utf-8") as f:
        after = json.load(f)
    if find_export(after, VARIABLE + "_GEN_VARIABLE")[1] is None:
        sys.exit("component did not survive the actor round trip")
    if find_export(after, NEW_ACTOR + "_C")[1] is None:
        sys.exit(f"the class is not called {NEW_ACTOR}_C, so the row will not resolve it: "
                 f"{[e['ObjectName'] for e in after['Exports'][:2]]}")
    os.makedirs(ACTORS, exist_ok=True)
    for ext in (".uasset", ".uexp"):
        shutil.copy2(os.path.join(work, NEW_ACTOR + ext), os.path.join(ACTORS, NEW_ACTOR + ext))
    print(f"  actor {NEW_ACTOR}: {COMPONENT} attached, mesh {NEW_MESH.rsplit('/', 1)[-1]}")

    for items_path, vendor_path in PAKS:
        if not os.path.isfile(items_path):
            print(f"  skipped {os.path.basename(os.path.dirname(items_path))}: not built")
            continue
        add_to_pak(items_path, vendor_path, work)
    print("\nPack both MoreAttachments paks and look at the top of the list.")


def add_to_pak(ITEMS, VENDOR, work):
    tag = ITEMS.split(os.sep)[-6]
    # 2. the row, cloned off a real attachment so every field is already valid
    with open(to_json(ITEMS, os.path.join(work, tag + ".items.json")), encoding="utf-8") as f:
        table = json.load(f)
    rows = table["Exports"][0]["Table"]["Data"]
    rows[:] = [r for r in rows if r["Name"] != NEW_ROW]
    donor = next((r for r in rows if r["Name"].startswith("Attachment_")
                  and any(p["Name"] == "AttachmentPartActorClass"
                          and isinstance(p.get("Value"), dict)
                          and (p["Value"]["AssetPath"]["PackageName"] or "").startswith(
                              "/Game/Objects/MoreAttachments/") for p in r["Value"])), None)
    if donor is None:
        sys.exit("no MoreAttachments row to clone")

    row = copy.deepcopy(donor)
    row["Name"] = NEW_ROW
    for entry in row["Value"]:
        if entry["Name"] == "AttachmentPartActorClass":
            entry["Value"] = soft_path(f"/Game/Objects/MoreAttachments/{NEW_ACTOR}",
                                       NEW_ACTOR + "_C")
        elif entry["Name"] == "StaticMesh":
            entry["Value"] = soft_path(NEW_MESH, NEW_MESH.rsplit("/", 1)[-1])
        elif entry["Name"] == "ItemName":
            entry["CultureInvariantString"] = NEW_LABEL
            entry["Namespace"] = None
            entry["Value"] = None
            entry["HistoryType"] = "None"
            entry["Flags"] = "CultureInvariant"
        elif entry["Name"] == "Cost":
            entry["Value"] = 1000

    rows.insert(0, row)                                    # first in the whole list
    register_names(table, [NEW_ROW, f"/Game/Objects/MoreAttachments/{NEW_ACTOR}",
                           NEW_ACTOR + "_C", NEW_MESH, NEW_MESH.rsplit("/", 1)[-1]])

    items_json = os.path.join(work, tag + ".items.edited.json")
    with open(items_json, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=1)
    built = from_json(items_json, os.path.join(work, tag + "_Items_AttachmentPart.uasset"))
    check = to_json(built, os.path.join(work, tag + ".items.check.json"))
    with open(check, encoding="utf-8") as f:
        back = json.load(f)
    order = [r["Name"] for r in back["Exports"][0]["Table"]["Data"]]
    if order[0] != NEW_ROW:
        sys.exit(f"row did not land first, list starts {order[:3]}")
    for ext in (".uasset", ".uexp"):
        shutil.copy2(os.path.join(work, tag + "_Items_AttachmentPart" + ext),
                     ITEMS.replace(".uasset", ext))
    print(f"  {tag}: row first of {len(order)}", end="")

    # 3. tell the vendor to sell it, or the row never shows up in game
    with open(to_json(VENDOR, os.path.join(work, tag + ".vendor.json")), encoding="utf-8") as f:
        vendor = json.load(f)
    count = sell_first(vendor, NEW_ROW)
    if count is None:
        sys.exit("no SellItems on the vendor")
    register_names(vendor, [NEW_ROW])

    vendor_json = os.path.join(work, tag + ".vendor.edited.json")
    with open(vendor_json, "w", encoding="utf-8") as f:
        json.dump(vendor, f, indent=1)
    built = from_json(vendor_json, os.path.join(work, tag + "_Vendor_Garage.uasset"))
    check = to_json(built, os.path.join(work, tag + ".vendor.check.json"))
    with open(check, encoding="utf-8") as f:
        back = json.load(f)
    sold = next(([i.get("Value") if isinstance(i, dict) else i for i in e["Value"]]
                 for x in back["Exports"] for e in (x.get("Data") or [])
                 if e["Name"] == "SellItems"), [])
    if not sold or sold[0] != NEW_ROW:
        sys.exit(f"vendor does not sell it first, list starts {sold[:3]}")
    for ext in (".uasset", ".uexp"):
        shutil.copy2(os.path.join(work, tag + "_Vendor_Garage" + ext), VENDOR.replace(".uasset", ext))
    print(f", vendor sells it first of {count}")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    if sys.argv[1] == "create":
        create()
        return
    name = sys.argv[1]
    source = os.path.join(ACTORS, name + ".uasset")
    if not os.path.isfile(source):
        sys.exit(f"no such actor: {source}")

    work = os.path.join(WORK, "winch")
    os.makedirs(work, exist_ok=True)
    with open(to_json(source, os.path.join(work, name + ".json")), encoding="utf-8") as f:
        asset = json.load(f)

    if not add_component(asset):
        print(f"{name} already has {COMPONENT}")
        return
    print(f"  added {COMPONENT} to {name}: "
          f"{len(asset['Imports'])} imports, {len(asset['Exports'])} exports")

    edited = os.path.join(work, name + ".edited.json")
    with open(edited, "w", encoding="utf-8") as f:
        json.dump(asset, f, indent=1)

    built = from_json(edited, os.path.join(work, name + ".uasset"))
    check = to_json(built, os.path.join(work, name + ".check.json"))
    with open(check, encoding="utf-8") as f:
        after = json.load(f)
    if find_export(after, VARIABLE + "_GEN_VARIABLE")[1] is None:
        sys.exit("component did not survive the round trip")
    print(f"  round trip ok, {COMPONENT} present in the rebuilt actor")

    for ext in (".uasset", ".uexp"):
        shutil.copy2(os.path.join(work, name + ext), os.path.join(ACTORS, name + ext))
    print(f"  installed into {name}")


def demo():
    asset = {
        "NameMap": ["/Script/MotorTown"], "NamesReferencedFromExportDataCount": 1,
        "Imports": [{"ObjectName": "/Script/MotorTown", "OuterIndex": 0,
                     "ClassPackage": "/Script/CoreUObject", "ClassName": "Package"}],
        "Exports": [
            {"ObjectName": "Thing_C", "ClassIndex": -1, "TemplateIndex": 0, "Data": []},
            {"ObjectName": MODEL_COMPONENT, "ClassIndex": -1, "TemplateIndex": -1,
             "OuterIndex": 1, "Data": []},
            {"ObjectName": "Scene_GEN_VARIABLE", "ClassIndex": -1, "TemplateIndex": -1,
             "OuterIndex": 1, "Data": []},
            {"ObjectName": "SCS_Node_1", "ClassIndex": -1, "TemplateIndex": -1, "Data": [
                {"Name": "ComponentClass", "Value": -6},
                {"Name": "ComponentTemplate", "Value": 3},
                {"Name": "ChildNodes", "Value": [{"Name": "0", "Value": 5}]},
                {"Name": "InternalVariableName", "Value": "Scene"}]},
            {"ObjectName": "SCS_Node_2", "ClassIndex": -1, "TemplateIndex": -1, "Data": [
                {"Name": "ComponentClass", "Value": -9},
                {"Name": "ComponentTemplate", "Value": 2},
                {"Name": "VariableGuid", "Value": [{"Value": "{DEAD-DEAD}"}]},
                {"Name": "InternalVariableName", "Value": "SpotLight"}]},
            {"ObjectName": "SimpleConstructionScript_0", "ClassIndex": -1, "TemplateIndex": -1,
             "Data": [{"Name": "RootNodes", "Value": [{"Name": "0", "Value": 4}]},
                      {"Name": "AllNodes", "Value": [{"Name": "0", "Value": 4},
                                                     {"Name": "1", "Value": 5}]}]}],
    }
    assert add_component(asset) is True
    names = [e["ObjectName"] for e in asset["Exports"]]
    assert names[-2:] == ["MTWinch_GEN_VARIABLE", "SCS_Node_MTWinch"], names

    comp = asset["Exports"][-2]
    assert comp["ClassIndex"] == -2 and comp["TemplateIndex"] == -3
    assert prop_of(comp, "Net_WinchPartKey")["Value"] == PART_KEY
    assert comp["SerializationBeforeCreateDependencies"] == [-2, -3], \
        "the loader must know to make the class before reading the template"
    assert comp["CreateBeforeCreateDependencies"] == [1], "outer is the generated class"

    node = asset["Exports"][-1]
    fields = {p["Name"]: p["Value"] for p in node["Data"]}
    assert fields["ComponentClass"] == -2
    assert fields["ComponentTemplate"] == 7, fields
    assert fields["InternalVariableName"] == "MTWinch"
    assert fields["VariableGuid"][0]["Value"] == NODE_GUID, "must not reuse the donor's"
    assert node["CreateBeforeSerializationDependencies"] == [7, -2]
    assert node["CreateBeforeCreateDependencies"] == [6], "outer is the construction script"

    script = asset["Exports"][5]
    by_name = {p["Name"]: p["Value"] for p in script["Data"]}
    assert [v["Value"] for v in by_name["AllNodes"]] == [4, 5, 8]
    assert [v["Value"] for v in by_name["RootNodes"]] == [4], \
        "a scene component is parented, not rooted"
    assert script["CreateBeforeSerializationDependencies"] == [8]
    scene_children = prop_of(asset["Exports"][3], "ChildNodes")
    assert [v["Value"] for v in scene_children["Value"]] == [5, 8], \
        "the winch hangs off the actor's scene node"

    assert COMPONENT in asset["NameMap"] and PART_KEY in asset["NameMap"]
    assert add_component(asset) is False, "second run must be a no-op"

    vendor = {"Exports": [{"Data": [{"Name": "SellItems", "Value": [
        {"Name": "0", "Value": "Coolant_01"}, {"Name": "1", "Value": "CargoStrap"}]}]}]}
    assert sell_first(vendor, "Attachment_qxWinch") == 3
    items = vendor["Exports"][0]["Data"][0]["Value"]
    assert [i["Value"] for i in items] == ["Attachment_qxWinch", "Coolant_01", "CargoStrap"]
    assert [i["Name"] for i in items] == ["0", "1", "2"], "array indices must renumber"
    assert sell_first(vendor, "Attachment_qxWinch") == 3, "must not duplicate on rerun"
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main()
