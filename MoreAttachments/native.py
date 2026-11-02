"""MoreAttachments: 0.7.20 native paint and per-section lights, for every part they fit.

    python MoreAttachments/native.py demo
    (the build itself runs from channel.py: native.convert_all)

Proven in game on the Duro front bumpers and Zydro rear bumpers (MoreAttachments/lab).
Each actor's mesh slots decide what it gets:

  paint    the mesh's own slot is car paint (M_Body family): one native paint slot each,
           and the actor stops overriding it (the paint system paints the mesh's own
           material; an actor OverrideMaterials is invisible to it)
  palette  only M_Palette (a car part's flat palette): the part gets its own copy of the
           mesh, /Game/MA_Parts/Paint/<original path>, with that slot on M_Gray -- the
           vanilla antenna's paint material -- and the actor points at the copy. The
           shared vanilla mesh is never edited: that would repaint the car itself.
  lamp     a car light material: the slot goes M_AttachmentLight (the car's own
           light materials are driven by the car, not by an attachment), one
           MTLightControlComponent per section. One section: the standard Toggle /
           Mode / Color. Several: labelled lines ("Toggle Brake Light", "Brake Light
           Mode", ...; both signals share "Signal Color") for the MoreAttachments
           plugin -- without it the lines still work, every section together.
  other    textured Synty props (Mat_Polygon*, MI_* palettes), glass, chrome: untouched.

Every actor is rebuilt from a pristine snapshot (Rebase/work/ma_pristine), so a rerun
never stacks edits, and must read back with the same exports and nothing raw -- or it
keeps its original.
"""
import copy
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "Rebase"))
import reallights  # noqa: E402
from paint import mesh_materials, paintable_material  # noqa: E402
from pipeline import VANILLA, WORK, from_json, register_names, to_json  # noqa: E402

MAIN = os.path.join(REPO, "qxZap_satigt3_MoreAttachments_P", "MotorTown", "Content")
ACTORS = os.path.join(MAIN, "Objects", "MoreAttachments")
PRISTINE = os.path.join(WORK, "ma_pristine")
NATIVE_WORK = os.path.join(WORK, "ma_native")
COPY_ROOT = "/Game/MA_Parts/Paint/"
GRAY, GRAY_PKG = "M_Gray", "/Game/Cars/Materials/Body/M_Gray"
LAMPS = {"M_HeadLight", "M_TailLight", "M_TurnSignalLight", "M_ReverseLight", "M_SideMarkerLight"}
NOT_PAINT = ("Glass", "Mirror", "Chrome", "Light", "Lamp", "Emissive")
HEAD = ("Headlight", "High Beam")
COLOURS = {"Tail Light": (1, 0, 0), "Brake Light": (1, 0, 0), "Reverse Light": (1, 1, 1),
           "Left Signal": (1, .45, 0), "Right Signal": (1, .45, 0), "Signal": (1, .45, 0),
           "Side Marker": (1, .45, 0), "Headlight": (1, 1, 1), "High Beam": (1, 1, 1)}
VERBS = {"ToggleLight": "Toggle {}", "ChangeLightMode": "{} Mode", "ChangeLightColor": "{} Color"}


def wheelworks_sections():
    """{vanilla wheel mesh package: [rim sections]} from Maja's Wheel Works table.

    Her pak replaces the wheel meshes at their vanilla paths with ones split into rim
    sections (Wheel_01, Wheel_02) and a tyre, and her ColorSlots name those sections.
    A wheel attachment that keeps the vanilla path and paints her section names paints
    the rim once her mod is installed; without it the vanilla mesh has no such section
    and nothing paints -- so it never needs our M_Gray copy, which would shadow hers.
    Refreshing her table (AGENTS.md, "Maja's Mo Wheel Works compat") refreshes this."""
    import glob
    tables = sorted(glob.glob(os.path.join(REPO, "MajasMoWheelWorks*_P", "MotorTown", "Content",
                                           "DataAsset", "VehicleParts", "Wheels.uasset")))
    if not tables:
        return {}
    src = tables[-1]
    t = None
    for m in ("MotorTown720T2", "MotorTown720T1", "MotorTown719"):  # her table may lag the game
        js = to_json(src, os.path.join(NATIVE_WORK, f"wheelworks.{m}.json"), m)
        t = json.load(open(js, encoding="utf-8"))
        if t["Exports"][0]["$type"].startswith("UAssetAPI.ExportTypes.DataTableExport"):
            break
    else:
        return {}
    imps, out = t["Imports"], {}
    for r in t["Exports"][0]["Table"]["Data"]:
        p = {x["Name"]: x for x in r["Value"]}
        secs = [(kv[0] if isinstance(kv, list) else kv["Key"]).get("Value")
                for kv in (p.get("ColorSlots", {}).get("Value") or [])]
        if not secs or "Wheel" not in p:
            continue
        for side in p["Wheel"]["Value"]:
            v = side.get("Value")
            if side.get("Name") in ("LeftWheelMesh", "RightWheelMesh") and isinstance(v, int) and v < 0:
                pkg = imps[-imps[-v - 1]["OuterIndex"] - 1]["ObjectName"]
                out.setdefault(pkg, secs)
    return out


WHEEL_WORKS = None  # loaded on first use: it exports her table
PROFILE = json.load(open(reallights.PROFILE, encoding="utf-8"))


def section(slot, material):
    """A lamp slot's section: "LeftSignalLight" -> "Left Signal", "HeadLight_HighBeam" -> "High Beam"."""
    s = slot.replace("_", "").lower()
    for key, name in (("leftsignal", "Left Signal"), ("rightsignal", "Right Signal"), ("highbeam", "High Beam"),
                      ("brake", "Brake Light"), ("reverse", "Reverse Light"), ("sidemarker", "Side Marker"),
                      ("tail", "Tail Light"), ("headlight", "Headlight"), ("signal", "Signal")):
        if key in s:
            return name
    return {"M_TailLight": "Tail Light", "M_TurnSignalLight": "Signal", "M_ReverseLight": "Reverse Light",
            "M_SideMarkerLight": "Side Marker", "M_HeadLight": "Headlight"}[material]


def kind(slot, material, package):
    if material in LAMPS:
        return "lamp"
    if material == "M_Palette":
        return "palette"
    if any(w.lower() in (slot or "").lower() or w.lower() in (material or "").lower() for w in NOT_PAINT):
        return "other"
    return "paint" if paintable_material(package, (VANILLA, MAIN)) else "other"


def plan(mesh_pkg):
    """[(index, slot, material, kind)] in StaticMaterials order; [] if the mesh is unknown."""
    return [(i, s, m, kind(s, m, k)) for i, (s, m, k) in enumerate(mesh_materials(mesh_pkg, (VANILLA, MAIN)))]


def mesh_file(pkg):
    for root in (VANILLA, MAIN):
        f = os.path.join(root, *pkg[len("/Game/"):].split("/")) + ".uasset"
        if os.path.isfile(f):
            return f
    return None


def run_uag(*a):
    import subprocess
    subprocess.run([r"D:\MT\UAssetGUI.exe", *a], check=True)


_copies = {}


def copy_mesh(pkg):
    """The part's own copy of a palette mesh, slot on M_Gray -> new package, or None."""
    if pkg in _copies:
        return _copies[pkg]
    src = mesh_file(pkg)
    new_pkg = COPY_ROOT + pkg[len("/Game/"):]
    _copies[pkg] = None
    if not src:
        return None
    os.makedirs(NATIVE_WORK, exist_ok=True)
    tag = pkg[len("/Game/"):].replace("/", "_")
    t = json.load(open(to_json(src, os.path.join(NATIVE_WORK, tag + ".mesh.json")), encoding="utf-8"))
    mat = next((i for i in t["Imports"] if i["ClassName"] == "Material" and i["ObjectName"] == "M_Palette"), None)
    if not mat or mat["OuterIndex"] >= 0:
        return None
    t["Imports"][-mat["OuterIndex"] - 1]["ObjectName"] = GRAY_PKG
    mat["ObjectName"] = GRAY
    for n in (GRAY, GRAY_PKG):
        if n not in t["NameMap"]:
            t["NameMap"].append(n)
    t["NameMap"] = [new_pkg if x == pkg else x for x in t["NameMap"]]
    if t.get("FolderName") == pkg:
        t["FolderName"] = new_pkg
    out = os.path.join(NATIVE_WORK, tag + ".mesh.out.json")
    json.dump(t, open(out, "w", encoding="utf-8"))
    dst = os.path.join(MAIN, *new_pkg[len("/Game/"):].split("/")) + ".uasset"
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    built = from_json(out, dst)
    back = json.load(open(to_json(built, os.path.join(NATIVE_WORK, tag + ".mesh.chk.json")), encoding="utf-8"))
    if any("RawExport" in e.get("$type", "") for e in back["Exports"]):
        return None
    _copies[pkg] = new_pkg
    return new_pkg


def clone_component(asset, match, count):
    """`count` components like <match>_GEN_VARIABLE: clones + SCS nodes (a root node when it has no parent)."""
    found = [(i, e) for i, e in enumerate(asset["Exports"], 1) if str(e.get("ObjectName")) == f"{match}_GEN_VARIABLE"]
    if not found:
        return []
    first_index, first = found[0]
    if count <= 1:
        return [first_index]
    node_index, node = reallights.scs_node_for(asset, first_index)
    if node is None:
        return []
    parent = next((e for e in asset["Exports"]
                   if any(p["Name"] == "ChildNodes" and any(v["Value"] == node_index for v in p["Value"])
                          for p in reallights.export_props(e))), None)
    script = next(e for e in asset["Exports"] if "SimpleConstructionScript" in str(e.get("ObjectName")))
    holders = ((parent, "ChildNodes"), (script, "AllNodes")) if parent else ((script, "RootNodes"), (script, "AllNodes"))
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


def menu(sections):
    """Labelled interaction entries: Toggle/Mode per section, Color per section except
    the signals, which share one "Signal Color"."""
    by_type = {next(x["Value"] for x in e["Value"] if x["Name"] == "InteractionType"): e
               for e in PROFILE["MTInteractable"][0]["Value"]}
    lines, signal_colour = [], False
    for s in sections:
        lines += [("ToggleLight", s), ("ChangeLightMode", s)]
        if s.endswith("Signal") and s != "Signal":
            if not signal_colour:
                lines.append(("ChangeLightColor", "Signal"))
                signal_colour = True
        else:
            lines.append(("ChangeLightColor", s))
    out = []
    for verb, label in lines:
        e = copy.deepcopy(by_type[verb])
        e["Name"] = str(len(out))
        next(x for x in e["Value"] if x["Name"] == "CustomName").update(
            HistoryType="None", Namespace=None, Value=None, CultureInvariantString=VERBS[verb].format(label))
        out.append(e)
    return out


def actor_mesh_import(t):
    """(the StaticMesh import's package import, package path) of the actor's Mesh component."""
    e = next((x for x in t["Exports"] if x.get("ObjectName") == "Mesh_GEN_VARIABLE"), None)
    sm = next((p["Value"] for p in (e or {}).get("Data") or [] if isinstance(p, dict) and p.get("Name") == "StaticMesh"), None)
    if not isinstance(sm, int) or sm >= 0:
        return None, None
    o = t["Imports"][-sm - 1]
    if o["OuterIndex"] >= 0:
        return None, None
    pkg = t["Imports"][-o["OuterIndex"] - 1]
    return pkg, pkg["ObjectName"]


def convert(t, mesh_pkg, slots):
    """Edit the actor JSON in place -> the mesh slot names that get a native paint slot."""
    paint = [s for _, s, _, k in slots if k == "paint"]
    palette = [s for _, s, _, k in slots if k == "palette"]
    lamps = [(i, s, section(s, m)) for i, s, m, k in slots if k == "lamp"]
    global WHEEL_WORKS
    if WHEEL_WORKS is None:
        WHEEL_WORKS = wheelworks_sections()
    if not paint and mesh_pkg in WHEEL_WORKS:
        paint = list(WHEEL_WORKS[mesh_pkg])  # her rim sections; live once Wheel Works is installed
        register_names(t, paint)
    elif palette and not paint and "/Cars/Parts/Wheels/" in mesh_pkg:
        pass  # a wheel never paints whole: the palette section is its tyre too
    elif palette and not paint:
        new_pkg = copy_mesh(mesh_pkg)
        if new_pkg:
            pkg_import, _ = actor_mesh_import(t)
            pkg_import["ObjectName"] = new_pkg
            register_names(t, [new_pkg])
            paint = palette
    mesh = next(e for e in t["Exports"] if e.get("ObjectName") == "Mesh_GEN_VARIABLE")
    inter = next((e for e in t["Exports"] if e.get("ObjectName") == "MTInteractable_GEN_VARIABLE"), None)

    if lamps and inter:
        sections = list(dict.fromkeys(s for _, _, s in lamps))
        if any(s in HEAD for s in sections):  # a lamp that casts a beam: reallights' spotlight setup
            facts = reallights.mesh_facts(mesh_pkg, NATIVE_WORK)
            reallights.light_up(t, PROFILE, places=reallights.beam_places(facts), slots=[(i, s) for i, s, _ in lamps])
        controls = clone_component(t, "MTLightControl", len(sections))
        for idx, sec in zip(controls, sections):
            ctl = copy.deepcopy(PROFILE["MTLightControl"])
            reallights.set_emissive(ctl, [s for _, s, x in lamps if x == sec])
            r, g, b = COLOURS.get(sec, (1, 1, 1))
            for p in ctl:
                if p["Name"] == "Net_LightColor":
                    p["Value"][0]["Value"].update({"R": r, "G": g, "B": b})
            t["Exports"][idx - 1]["Data"] = ctl
        keep = [p for p in inter["Data"] if not (isinstance(p, dict) and p["Name"] == "InteractionParams")]
        ip = copy.deepcopy(PROFILE["MTInteractable"][0])
        if len(controls) > 1:
            ip["Value"] = menu(sections)
        inter["Data"] = keep + [ip]
        reallights.override_lamp_materials(t, [(i, s) for i, s, _ in lamps], len(slots))
    else:
        mesh["Data"] = [p for p in mesh["Data"] if not (isinstance(p, dict) and p.get("Name") == "OverrideMaterials")]
        if inter:
            for p in inter["Data"]:
                if isinstance(p, dict) and p.get("Name") == "InteractionParams":
                    p["Value"] = [ip for ip in p["Value"]
                                  if not any(x.get("Name") == "InteractionType" and x.get("Value") == "ChangeLightColor"
                                             for x in ip["Value"])]
    register_names(t, reallights.names_in(PROFILE) + [s for _, s, _, _ in slots]
                   + [reallights.ATTACHMENT_LIGHT, reallights.ATTACHMENT_LIGHT_PACKAGE, "Material", "OverrideMaterials"])
    return paint


def wanted(actor_file):
    """(mesh package, slots) if this actor gets paint or lamps, else None -- read off the
    actor's name table and the cached mesh slots, without a full export."""
    data = open(actor_file, "rb").read()
    for pkg in dict.fromkeys(m.decode() for m in re.findall(rb"/Game/[A-Za-z0-9_/]+", data)):
        if "/Materials/" in pkg or pkg.startswith("/Game/Objects/MoreAttachments"):
            continue
        slots = plan(pkg) if mesh_file(pkg) else []
        if slots:
            global WHEEL_WORKS
            if WHEEL_WORKS is None:
                WHEEL_WORKS = wheelworks_sections()
            kinds = {k for *_, k in slots}
            return (pkg, slots) if kinds & {"paint", "palette", "lamp"} or pkg in WHEEL_WORKS else None
    return None


def convert_all(regenerated=()):
    """Every actor in the mod: restore from the pristine snapshot, convert, verify.
    regenerated: actors channel.py just rebuilt from the template (not restored).
    Returns {actor name: [mesh slot names to paint]}."""
    os.makedirs(PRISTINE, exist_ok=True)
    os.makedirs(NATIVE_WORK, exist_ok=True)
    out, stats = {}, {"paint": 0, "copies": 0, "lamps": 0, "sections": 0, "failed": [], "untouched": 0}
    names = sorted(f[:-7] for f in os.listdir(ACTORS) if f.endswith(".uasset"))
    for n, name in enumerate(names, 1):
        base = os.path.join(ACTORS, name)
        snap = os.path.join(PRISTINE, name)
        if name in regenerated:
            for ext in (".uasset", ".uexp"):
                shutil.copy2(base + ext, snap + ext)
        elif os.path.isfile(snap + ".uasset"):
            for ext in (".uasset", ".uexp"):
                shutil.copy2(snap + ext, base + ext)
        else:
            for ext in (".uasset", ".uexp"):
                shutil.copy2(base + ext, snap + ext)
        w = wanted(base + ".uasset")
        if not w:
            stats["untouched"] += 1
            continue
        mesh_pkg, slots = w
        js = to_json(base + ".uasset", os.path.join(NATIVE_WORK, name + ".json"))
        t = json.load(open(js, encoding="utf-8"))
        if actor_mesh_import(t)[1] != mesh_pkg or not any(e.get("ObjectName") == "Mesh_GEN_VARIABLE" for e in t["Exports"]):
            stats["untouched"] += 1
            continue
        before = len(copy.deepcopy(t["Exports"]))
        paint = convert(t, mesh_pkg, slots)
        edited = os.path.join(NATIVE_WORK, name + ".out.json")
        json.dump(t, open(edited, "w", encoding="utf-8"))
        tmp = os.path.join(NATIVE_WORK, name + ".built.uasset")
        try:
            built = from_json(edited, tmp)
            back = json.load(open(to_json(built, os.path.join(NATIVE_WORK, name + ".chk.json")), encoding="utf-8"))
            ok = not any("RawExport" in e.get("$type", "") for e in back["Exports"]) \
                and len(back["Exports"]) == len(t["Exports"]) >= before
        except Exception as e:  # UAssetGUI wrote nothing, or a read-back failed
            print(f"  {name}: {e}")
            ok = False
        if not ok:
            stats["failed"].append(name)
            continue
        for ext in (".uasset", ".uexp"):
            shutil.copy2(tmp[:-7] + ext, base + ext)
        out[name] = paint
        stats["paint"] += bool(paint)
        stats["copies"] += any(k == "palette" for *_, k in slots) and not any(k == "paint" for *_, k in slots)
        secs = len({section(s, m) for _, s, m, k in slots if k == "lamp"})
        stats["lamps"] += bool(secs)
        stats["sections"] += secs > 1
        if n % 50 == 0:
            print(f"  native: {n}/{len(names)}", flush=True)
    print(f"  native: {stats['paint']} painted ({stats['copies']} on their own mesh copy), "
          f"{stats['lamps']} lamps ({stats['sections']} with sections), {stats['untouched']} untouched, "
          f"{len(stats['failed'])} kept original: {stats['failed'][:10]}")
    return out


def demo():
    assert section("LeftSignalLight", "M_TurnSignalLight") == "Left Signal"
    assert section("HeadLight_HighBeam", "M_HeadLight") == "High Beam"
    assert section("BrakeLight", "M_TailLight") == "Brake Light"
    labels = [next(x["CultureInvariantString"] for x in e["Value"] if x["Name"] == "CustomName")
              for e in menu(["Tail Light", "Left Signal", "Right Signal"])]
    assert labels == ["Toggle Tail Light", "Tail Light Mode", "Tail Light Color", "Toggle Left Signal",
                      "Left Signal Mode", "Signal Color", "Toggle Right Signal", "Right Signal Mode"], labels
    assert kind("Palette", "M_Palette", "/Game/Cars/Materials/Palette/M_Palette") == "palette"
    assert kind("Glass", "M_Glass", "") == "other" and kind("TailLight", "M_TailLight", "") == "lamp"
    print("ok")


if __name__ == "__main__":
    demo() if sys.argv[1:] == ["demo"] else sys.exit(__doc__)
