"""Lab: Zydro rear bumpers 01-03 -- native body paint plus one light section per
function (tail, brake, left/right signal, reverse), each its own
MTLightControlComponent, with labelled Toggle / Mode / Color menu lines.

The game alone applies any light interaction to every control on the actor and
keeps a single mode per attachment; per-section control comes from the
AttachmentLights loader plugin (mt_loader/plugins/attachment_lights.cpp), which
routes each labelled line to its section. Without it the lines still work, all
sections together. Body paint needs no mesh copy here: Body_01 is already M_Body.
Proven in game on 0.7.20.
"""
import copy, json, os, subprocess, sys

SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Rebase", "work", "lab")
os.makedirs(SP, exist_ok=True)
UAG = r"D:\MT\UAssetGUI.exe"
MA = r"D:\MT\MoreTuning\qxZap_satigt3_MoreAttachments_P\MotorTown\Content"
LAB = r"D:\MT\MoreTuning\zzLab_DuroPaint_P\MotorTown\Content"
sys.path.insert(0, r"D:\MT\MoreTuning\MoreAttachments")
import reallights  # noqa: E402
from pipeline import register_names  # noqa: E402  (reallights put Rebase on the path)

PROFILE = json.load(open(reallights.PROFILE, encoding="utf-8"))
CHANNELS = [  # label, mesh slots, default colour
    ("Tail Light", ["TailLight"], {"R": 1.0, "G": 0.0, "B": 0.0}),
    ("Brake Light", ["BrakeLight"], {"R": 1.0, "G": 0.0, "B": 0.0}),
    ("Left Signal", ["LeftSignalLight"], {"R": 1.0, "G": 0.45, "B": 0.0}),
    ("Right Signal", ["RightSignalLight"], {"R": 1.0, "G": 0.45, "B": 0.0}),
    ("Reverse Light", ["ReverseLight"], {"R": 1.0, "G": 1.0, "B": 1.0}),
]


def run(*a):
    subprocess.run([UAG, *a], check=True)


def mesh_slots(asset_mesh_pkg):
    """[(index, slot name)] in StaticMaterials order, from the vanilla mesh."""
    path = os.path.join(r"D:\MT\Output\Exports\MotorTown\Content",
                        *asset_mesh_pkg[len("/Game/"):].split("/")) + ".uasset"
    js = os.path.join(SP, "zmesh.json")
    run("tojson", path, js, "VER_UE5_4", "MotorTown720T1")
    m = json.load(open(js, encoding="utf-8"))
    for e in m["Exports"]:
        for p in e.get("Data") or []:
            if isinstance(p, dict) and p.get("Name") == "StaticMaterials":
                return [(i, next(f["Value"] for f in s["Value"] if f["Name"] == "MaterialSlotName"))
                        for i, s in enumerate(p["Value"])]
    raise SystemExit(f"no StaticMaterials in {asset_mesh_pkg}")


def clone_component(asset, match, count):
    """Give the actor `count` components like the one named `match` (clones + SCS nodes).

    Same recipe as reallights.add_spotlights: clone the export and its SCS node,
    fresh name/variable/guid, hook the node into its parent and the script.
    """
    found = [(i, e) for i, e in enumerate(asset["Exports"], 1)
             if str(e.get("ObjectName")) == f"{match}_GEN_VARIABLE"]
    assert found, f"no {match}"
    first_index, first = found[0]
    node_index, node = reallights.scs_node_for(asset, first_index)
    assert node is not None, f"{match}: no SCS node"
    parent = next((e for e in asset["Exports"]
                   if any(p["Name"] == "ChildNodes" and any(v["Value"] == node_index for v in p["Value"])
                          for p in reallights.export_props(e))), None)
    script = next(e for e in asset["Exports"] if "SimpleConstructionScript" in str(e.get("ObjectName")))
    # a non-scene component (light control) has no parent node: it is a root of the script
    holders = ((parent, "ChildNodes"), (script, "AllNodes")) if parent else \
        ((script, "RootNodes"), (script, "AllNodes"))
    made = [first_index]
    for extra in range(1, count):
        comp = copy.deepcopy(first)
        comp["ObjectName"] = f"{match}{extra}_GEN_VARIABLE"
        asset["Exports"].append(comp)
        comp_index = len(asset["Exports"])
        fresh = copy.deepcopy(node)
        fresh["ObjectName"] = f"SCS_Node_{match}{extra}"
        for prop in fresh.get("Data") or []:
            if prop["Name"] == "ComponentTemplate":
                prop["Value"] = comp_index
            elif prop["Name"] == "InternalVariableName":
                prop["Value"] = f"{match}{extra}"
            elif prop["Name"] == "VariableGuid":
                for field in prop["Value"]:
                    field["Value"] = f"{{7A19C5{extra:02d}-0000-0000-0000-00000000C0DE}}"
        deps = fresh.get("CreateBeforeSerializationDependencies") or []
        fresh["CreateBeforeSerializationDependencies"] = [comp_index if d == first_index else d for d in deps]
        asset["Exports"].append(fresh)
        node_ref = len(asset["Exports"])
        for holder, field in holders:
            for prop in reallights.export_props(holder):
                if prop["Name"] == field:
                    entry = copy.deepcopy(prop["Value"][0])
                    entry["Name"] = str(len(prop["Value"]))
                    entry["Value"] = node_ref
                    prop["Value"].append(entry)
            deps = holder.setdefault("CreateBeforeSerializationDependencies", [])
            if node_ref not in deps:
                deps.append(node_ref)
        register_names(asset, [comp["ObjectName"], fresh["ObjectName"], f"{match}{extra}"])
        made.append(comp_index)
    return made



def build(n):
    src = os.path.join(MA, "Objects", "MoreAttachments", f"Attachment_Zydro_RearBumper_{n}.uasset")
    js = os.path.join(SP, f"z_{n}.json")
    run("tojson", src, js, "VER_UE5_4", "MotorTown720T1")
    t = json.load(open(js, encoding="utf-8"))
    slots = mesh_slots(f"/Game/Cars/Models/Zydro/RearBumper_{n}")
    index_of = {name: i for i, name in slots}

    # one light control per channel
    controls = clone_component(t, "MTLightControl", len(CHANNELS))
    for idx, (label, names, colour) in zip(controls, CHANNELS):
        ctl = copy.deepcopy(PROFILE["MTLightControl"])
        reallights.set_emissive(ctl, names)  # also sets intensity + white
        for p in ctl:
            if p["Name"] == "Net_LightColor":
                p["Value"][0]["Value"].update(colour)
        t["Exports"][idx - 1]["Data"] = ctl

    # labelled Toggle / Mode / Color lines. The game alone drives every control
    # from any of them; the AttachmentLights plugin routes each to its own
    # section (sections come from Toggle/Mode lines, in order -> control k).
    # The two signals share one colour line: "Signal Color" covers every section
    # whose name ends in "Signal".
    verbs = {"ToggleLight": "Toggle {}", "ChangeLightMode": "{} Mode", "ChangeLightColor": "{} Color"}
    by_type = {next(x["Value"] for x in e["Value"] if x["Name"] == "InteractionType"): e
               for e in PROFILE["MTInteractable"][0]["Value"]}
    menu = []
    for label, _, _ in CHANNELS:
        menu += [("ToggleLight", label), ("ChangeLightMode", label)]
        if not label.endswith("Signal"):
            menu.append(("ChangeLightColor", label))
        elif label == "Right Signal":
            menu.append(("ChangeLightColor", "Signal"))
    params = []
    for verb, label in menu:
        e = copy.deepcopy(by_type[verb])
        e["Name"] = str(len(params))
        next(x for x in e["Value"] if x["Name"] == "CustomName").update(
            HistoryType="None", Namespace=None, Value=None, CultureInvariantString=verbs[verb].format(label))
        params.append(e)
    inter = next(e for e in t["Exports"] if str(e.get("ObjectName")) == "MTInteractable_GEN_VARIABLE")
    keep = [p for p in inter["Data"] if not (isinstance(p, dict) and p["Name"] == "InteractionParams")]
    ip = copy.deepcopy(PROFILE["MTInteractable"][0])
    ip["Value"] = params
    inter["Data"] = keep + [ip]

    # body + palette keep the mesh's own materials (Body_01 is M_Body: natively
    # painted); every lamp slot becomes M_AttachmentLight
    lamps = [(index_of[s], s) for _, names, _ in CHANNELS for s in names]
    reallights.override_lamp_materials(t, lamps, len(slots))

    register_names(t, reallights.names_in(PROFILE) + [s for _, s in slots]
                   + [reallights.ATTACHMENT_LIGHT, reallights.ATTACHMENT_LIGHT_PACKAGE,
                      "Material", "OverrideMaterials"])
    out = os.path.join(SP, f"z_{n}.out.json")
    json.dump(t, open(out, "w", encoding="utf-8"), indent=1)
    dst = os.path.join(LAB, "Objects", "MoreAttachments", f"Attachment_Zydro_RearBumper_{n}.uasset")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    run("fromjson", out, dst, "MotorTown720T1")
    assert os.path.isfile(dst), f"UAssetGUI wrote nothing: {dst}"
    chk = os.path.join(SP, f"z_{n}.chk.json")
    run("tojson", dst, chk, "VER_UE5_4", "MotorTown720T1")
    back = json.load(open(chk, encoding="utf-8"))
    assert not any("RawExport" in e.get("$type", "") for e in back["Exports"]), f"{n} RawExport"
    assert len(back["Exports"]) == len(t["Exports"]), f"{n} export count changed"
    got = [e for e in back["Exports"] if "MTLightControl" in str(e.get("ObjectName")) and "SCS" not in str(e.get("ObjectName"))]
    assert len(got) == len(CHANNELS), (n, [e["ObjectName"] for e in got])
    return dst


for n in ("01", "02", "03"):
    print("actor", build(n))
print(f"OK: 3 Zydro rear bumpers, {len(CHANNELS)} light channels each")
