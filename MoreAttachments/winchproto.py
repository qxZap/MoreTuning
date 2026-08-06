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

# Copy the shape of a component the template already carries rather than
# inventing one: same import layout, same export layout, same SCS wiring.
MODEL_COMPONENT = "MTLightControl_GEN_VARIABLE"


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


def add_component(asset):
    """Add COMPONENT as an SCS node. Returns False if it is already there."""
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

    # The component template, at defaults.
    component = copy.deepcopy(model)
    component["ObjectName"] = VARIABLE + "_GEN_VARIABLE"
    component["ClassIndex"] = class_link
    component["TemplateIndex"] = default_link
    component["Data"] = []
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
    asset["Exports"].append(node)
    node_ref = len(asset["Exports"])

    for entry in script.get("Data", []):
        if entry["Name"] in ("RootNodes", "AllNodes"):
            item = copy.deepcopy(entry["Value"][0])
            item["Name"] = str(len(entry["Value"]))
            item["Value"] = node_ref
            entry["Value"].append(item)

    register_names(asset, [COMPONENT, "Default__" + COMPONENT,
                           VARIABLE + "_GEN_VARIABLE", "SCS_Node_" + VARIABLE, VARIABLE])
    return True


NEW_ACTOR = "Attachment_qxWinch"
NEW_ROW = "Attachment_qxWinch"
NEW_LABEL = "Winch (test)"
NEW_MESH = "/Game/Cars/Parts/Winch/Winch_01_Body"
TEMPLATE = os.path.join(HERE, "ACTOR_TEMPLATE.json")
TEMPLATE_NAME = "Attachment_Neo_RearSpoiler_01"
TEMPLATE_MESH = "/Game/Cars/Models/Neo/RearSpoiler_01"
ITEMS = os.path.join(HERE, "..", "qxZap_satigt3_MoreAttachments_P", "MotorTown", "Content",
                     "DataAsset", "Items", "Items_AttachmentPart.uasset")
# A row in Items_AttachmentPart only defines the part. It does not appear in game
# until the vendor is told to sell it -- MTVendor's SellItems on Vendor_Garage.
VENDOR = os.path.join(HERE, "..", "qxZap_satigt3_MoreAttachments_P", "MotorTown", "Content",
                      "Characters", "NPC", "Vendor_Garage.uasset")


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
    text = text.replace(TEMPLATE_MESH, NEW_MESH)
    text = text.replace(TEMPLATE_MESH.rsplit("/", 1)[-1], NEW_MESH.rsplit("/", 1)[-1])
    text = text.replace(TEMPLATE_NAME, NEW_ACTOR)
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
    os.makedirs(ACTORS, exist_ok=True)
    for ext in (".uasset", ".uexp"):
        shutil.copy2(os.path.join(work, NEW_ACTOR + ext), os.path.join(ACTORS, NEW_ACTOR + ext))
    print(f"  actor {NEW_ACTOR}: {COMPONENT} attached, mesh {NEW_MESH.rsplit('/', 1)[-1]}")

    # 2. the row, cloned off a real attachment so every field is already valid
    with open(to_json(ITEMS, os.path.join(work, "items.json")), encoding="utf-8") as f:
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

    items_json = os.path.join(work, "items.edited.json")
    with open(items_json, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=1)
    built = from_json(items_json, os.path.join(work, "Items_AttachmentPart.uasset"))
    check = to_json(built, os.path.join(work, "items.check.json"))
    with open(check, encoding="utf-8") as f:
        back = json.load(f)
    order = [r["Name"] for r in back["Exports"][0]["Table"]["Data"]]
    if order[0] != NEW_ROW:
        sys.exit(f"row did not land first, list starts {order[:3]}")
    for ext in (".uasset", ".uexp"):
        shutil.copy2(os.path.join(work, "Items_AttachmentPart" + ext),
                     ITEMS.replace(".uasset", ext))
    print(f"  row {NEW_ROW} first of {len(order)}, cloned from {donor['Name']}")

    # 3. tell the vendor to sell it, or the row never shows up in game
    with open(to_json(VENDOR, os.path.join(work, "vendor.json")), encoding="utf-8") as f:
        vendor = json.load(f)
    count = sell_first(vendor, NEW_ROW)
    if count is None:
        sys.exit("no SellItems on the vendor")
    register_names(vendor, [NEW_ROW])

    vendor_json = os.path.join(work, "vendor.edited.json")
    with open(vendor_json, "w", encoding="utf-8") as f:
        json.dump(vendor, f, indent=1)
    built = from_json(vendor_json, os.path.join(work, "Vendor_Garage.uasset"))
    check = to_json(built, os.path.join(work, "vendor.check.json"))
    with open(check, encoding="utf-8") as f:
        back = json.load(f)
    sold = next(([i.get("Value") if isinstance(i, dict) else i for i in e["Value"]]
                 for x in back["Exports"] for e in (x.get("Data") or [])
                 if e["Name"] == "SellItems"), [])
    if not sold or sold[0] != NEW_ROW:
        sys.exit(f"vendor does not sell it first, list starts {sold[:3]}")
    for ext in (".uasset", ".uexp"):
        shutil.copy2(os.path.join(work, "Vendor_Garage" + ext), VENDOR.replace(".uasset", ext))
    print(f"  vendor sells it first of {count}")
    print("\nPack qxZap_satigt3_MoreAttachments_P and look at the top of the list.")


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
            {"ObjectName": MODEL_COMPONENT, "ClassIndex": -1, "TemplateIndex": -1, "Data": []},
            {"ObjectName": "SCS_Node_2", "ClassIndex": -1, "TemplateIndex": -1, "Data": [
                {"Name": "ComponentClass", "Value": -9},
                {"Name": "ComponentTemplate", "Value": 2},
                {"Name": "InternalVariableName", "Value": "SpotLight"}]},
            {"ObjectName": "SimpleConstructionScript_0", "ClassIndex": -1, "TemplateIndex": -1,
             "Data": [{"Name": "RootNodes", "Value": [{"Name": "0", "Value": 3}]},
                      {"Name": "AllNodes", "Value": [{"Name": "0", "Value": 3}]}]}],
    }
    assert add_component(asset) is True
    names = [e["ObjectName"] for e in asset["Exports"]]
    assert names[-2:] == ["MTWinch_GEN_VARIABLE", "SCS_Node_MTWinch"], names
    comp = asset["Exports"][-2]
    assert comp["ClassIndex"] == -2 and comp["TemplateIndex"] == -3
    node = {p["Name"]: p["Value"] for p in asset["Exports"][-1]["Data"]}
    assert node["ComponentClass"] == -2
    assert node["ComponentTemplate"] == 5, node
    assert node["InternalVariableName"] == "MTWinch"
    script = {p["Name"]: p["Value"] for p in asset["Exports"][3]["Data"]}
    assert [v["Value"] for v in script["AllNodes"]] == [3, 6]
    assert COMPONENT in asset["NameMap"]
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
