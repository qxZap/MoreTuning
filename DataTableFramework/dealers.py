"""rtwin's dealer slots on the current game: DriveGameModeBP + 32 DealerComponent stubs.

rtwin's ReservedVehicleFramework puts a car on sale without touching the world map: the game mode's component tree
(SimpleConstructionScript) holds one node per slot, under the root node, whose template is the ChildActorComponent at
/Game/ReservedRegistration/Slots/SlotNN/DealerComponent. Empty slots are stubs (no child actor); a car pak replaces its
slot's DealerComponent with one that spawns MTDealerVehicleSpawnPoint at a world position with its VehicleParams.

His framework ships a 0.7.19 DriveGameModeBP, which on the current game reads raw and lacks four components the game
has since gained (HousingPlanning, Mail, MotionWarping, VoiceModeration). This regenerates it from current vanilla each
update and adds only the 32 slot nodes -- that copy goes in the framework pak (it outranks everything, and no other mod
ships the game mode). No stubs ship (2026-11-09, the user: one framework pak): inside _99_P a stub would beat a car
pak's own slot, and an empty slot needs none -- the game ran for days with the old AAAA_DataTableFramework_Slots_P
switched off in Mods [Review]. A car pak brings its own SlotNN/DealerComponent; unused slots stay empty.

Templates (templates/): rtwin's slot node properties and an empty slot, read once from his framework pak.
    python DataTableFramework/dealers.py          python DataTableFramework/dealers.py demo
"""
import copy
import json
import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run import MOD, WORK, add_import, load, save  # noqa: E402
from pipeline import VANILLA, from_json, register_names, to_json  # noqa: E402

SLOTS = 32
TEMPLATES = os.path.join(HERE, "templates")
slot_pkg = lambda i: f"/Game/ReservedRegistration/Slots/Slot{i:02d}/DealerComponent"
slot_obj = lambda i: f"DealerComponent_Slot{i:02d}"
slot_node = lambda i: f"SCS_Node_DealerSlot{i:02d}"


def find_import(t, name, cls):
    for k, x in enumerate(t["Imports"]):
        if x["ObjectName"] == name and x["ClassName"] == cls:
            return -(k + 1)
    return 0


def export_index(t, name):
    return next(k + 1 for k, e in enumerate(t["Exports"]) if e.get("ObjectName") == name)


def add_slots(gm, tpl):
    """Add the slot nodes to a game mode's component tree. Returns the names it uses."""
    ex = gm["Exports"]
    scs_i = next(k + 1 for k, e in enumerate(ex) if e["ClassIndex"] < 0 and gm["Imports"][-e["ClassIndex"] - 1]["ObjectName"] == "SimpleConstructionScript")
    root_i = export_index(gm, "SCS_Node_0")
    root, scs = ex[root_i - 1], ex[scs_i - 1]
    assert not any(e.get("ObjectName", "").startswith("SCS_Node_DealerSlot") for e in ex), "already has dealer slots"
    engine = find_import(gm, "/Script/Engine", "Package")
    cac = find_import(gm, "ChildActorComponent", "Class") or add_import(gm, "ChildActorComponent", engine, "/Script/CoreUObject", "Class")
    names = ["ChildActorComponent", "ObjectProperty"]
    children = copy.deepcopy(tpl["childnodes_prop"])
    children["Value"] = []
    for i in range(1, SLOTS + 1):
        pkg = add_import(gm, slot_pkg(i), 0, "/Script/CoreUObject", "Package")
        obj = add_import(gm, slot_obj(i), pkg, "/Script/Engine", "ChildActorComponent")
        node = copy.deepcopy(root)
        node["ObjectName"] = slot_node(i)
        node["Data"] = copy.deepcopy(tpl["node_data"])
        for p in node["Data"]:
            if p["Name"] == "ComponentClass":
                p["Value"] = cac
            elif p["Name"] == "ComponentTemplate":
                p["Value"] = obj
            elif p["Name"] == "VariableGuid":
                p["Value"][0]["Value"] = "{" + str(uuid.uuid4()).upper() + "}"
        node["SerializationBeforeSerializationDependencies"] = [obj]
        node["CreateBeforeSerializationDependencies"] = []
        node["SerializationBeforeCreateDependencies"] = list(root["SerializationBeforeCreateDependencies"])
        node["CreateBeforeCreateDependencies"] = [scs_i]
        ex.append(node)
        ni = len(ex)
        entry = copy.deepcopy(tpl["childnodes_prop"]["Value"][0])
        entry["Name"], entry["Value"] = str(i - 1), ni
        children["Value"].append(entry)
        for lst in (root["CreateBeforeSerializationDependencies"], scs["CreateBeforeSerializationDependencies"]):
            lst.append(ni)
        allnodes = next(p for p in scs["Data"] if p["Name"] == "AllNodes")
        e2 = copy.deepcopy(allnodes["Value"][0])
        e2["Name"], e2["Value"] = str(len(allnodes["Value"])), ni
        allnodes["Value"].append(e2)
        names += [slot_pkg(i), slot_obj(i), slot_node(i)]
    # the root node gets its ChildNodes (vanilla's has none), after its ComponentClass like rtwin's
    root["Data"] = [p for p in root["Data"] if p["Name"] != "ChildNodes"]
    at = next(k for k, p in enumerate(root["Data"]) if p["Name"] == "ComponentClass") + 1
    root["Data"].insert(at, children)
    return names


def build(table, out, tag):
    src = os.path.join(WORK, f"{tag}.json")
    save(table, src)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    built = from_json(src, out)
    return load(to_json(built, os.path.join(WORK, f"{tag}.check.json")))


def main():
    os.makedirs(WORK, exist_ok=True)
    tpl = json.load(open(os.path.join(TEMPLATES, "dealer_scs_node.json"), encoding="utf-8"))
    gm = load(to_json(os.path.join(VANILLA, "GameMode", "DriveGameModeBP.uasset"), os.path.join(WORK, "DriveGameModeBP.vanilla.json")))
    n_before = len(gm["Exports"])
    names = add_slots(gm, tpl)
    register_names(gm, names)
    gm["Generations"][0]["NameCount"] = len(gm["NameMap"])
    back = build(gm, os.path.join(MOD, "GameMode", "DriveGameModeBP.uasset"), "DriveGameModeBP.framework")
    raw = [e["ObjectName"] for e in back["Exports"] if not e["$type"].startswith("UAssetAPI.ExportTypes.") or "RawExport" in e["$type"]]
    assert not raw, f"exports read back raw: {raw[:5]}"
    nodes = [e for e in back["Exports"] if e.get("ObjectName", "").startswith("SCS_Node_DealerSlot")]
    assert len(back["Exports"]) == n_before + SLOTS and len(nodes) == SLOTS, (len(back["Exports"]), len(nodes))
    print(f"  DriveGameModeBP: current vanilla ({n_before} exports) + {SLOTS} dealer slot nodes, read back")

if __name__ == "__main__":
    if sys.argv[1:] == ["demo"]:
        assert slot_pkg(2) == "/Game/ReservedRegistration/Slots/Slot02/DealerComponent" and slot_obj(32) == "DealerComponent_Slot32"
        print("demo ok")
    else:
        main()
