"""Prototype: give an attachment actor a real winch component.

    python winchproto.py <ActorName>   # e.g. Attachment_Neo_RearSpoiler_01
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


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
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
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main()
