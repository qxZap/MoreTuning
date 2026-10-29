"""Lab: the 4 Duro front bumpers, natively paintable (color+metallic+roughness),
and the two with a lamp section given a working light.

The attachment paint system paints the *mesh's own* material in the named slot.
A Duro bumper's slot is M_Palette (textures only, no Color parameter), and it is
a shared vanilla car mesh, so it cannot be changed in place without repainting
the Duro itself. Per part:
  - copy the mesh to /Game/MA_Parts/Duro/ with the "Palette" slot swapped to
    M_Gray -- the vanilla antenna's paint material, which the paint system drives
    (M_PaintableMetal does not: it has no Color parameter, it was only ever tinted
    through ChangeLightColor);
  - repoint the actor's StaticMesh import at the copy;
  - no lamp section: drop the actor's OverrideMaterials and its ChangeLightColor,
    so the painted mesh material is what renders;
  - a lamp section (HeadLight_HighBeam): reallights' treatment -- OverrideMaterials
    null for the body slot, M_AttachmentLight for the lamp, ToggleLight /
    ChangeLightMode / ChangeLightColor.
paint_slots.py adds the item rows' paint slot. Proven in game on 0.7.20.
"""
import json, os, subprocess, shutil, sys

SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Rebase", "work", "lab")
os.makedirs(SP, exist_ok=True)
UAG = r"D:\MT\UAssetGUI.exe"
VAN = r"D:\MT\Output\Exports\MotorTown\Content"
MA = r"D:\MT\MoreTuning\qxZap_satigt3_MoreAttachments_P\MotorTown\Content"
LAB = r"D:\MT\MoreTuning\zzLab_DuroPaint_P\MotorTown\Content"
PAINTABLE = "M_Gray"  # the vanilla antenna's paint material; the paint system drives it
PAINTABLE_PKG = "/Game/Cars/Materials/Body/M_Gray"
NS = ["01", "02", "03", "04"]
LIGHTS = {"02", "03"}  # these have a HeadLight_HighBeam section -> make it a working lamp

sys.path.insert(0, r"D:\MT\MoreTuning\MoreAttachments")
import reallights  # noqa: E402
PROFILE = json.load(open(reallights.PROFILE, encoding="utf-8"))


def tojson(src, dst):
    subprocess.run([UAG, "tojson", src, dst, "VER_UE5_4", "MotorTown720T1"], check=True)
    return json.load(open(dst, encoding="utf-8"))


def fromjson(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    subprocess.run([UAG, "fromjson", src, dst, "MotorTown720T1"], check=True)
    assert os.path.isfile(dst), f"UAssetGUI wrote nothing: {dst}"


def add_name(t, name):
    if name not in t["NameMap"]:
        t["NameMap"].append(name)


def build_mesh(n):
    old_pkg = f"/Game/Cars/Models/Duro/FrontBumper_{n}"
    new_pkg = f"/Game/MA_Parts/Duro/FrontBumper_{n}"
    t = tojson(os.path.join(VAN, "Cars", "Models", "Duro", f"FrontBumper_{n}.uasset"),
               os.path.join(SP, f"m_{n}.json"))
    # swap the Palette slot's material import M_Palette -> M_PaintableMetal
    mat = next((im for im in t["Imports"]
                if im["ClassName"] == "Material" and im["ObjectName"] == "M_Palette"), None)
    assert mat, f"FrontBumper_{n}: no M_Palette import"
    pkg = t["Imports"][-mat["OuterIndex"] - 1]
    mat["ObjectName"] = PAINTABLE
    pkg["ObjectName"] = PAINTABLE_PKG
    add_name(t, PAINTABLE)
    add_name(t, PAINTABLE_PKG)
    # retarget the package's self-name
    t["NameMap"] = [new_pkg if x == old_pkg else x for x in t["NameMap"]]
    if t.get("FolderName") == old_pkg:
        t["FolderName"] = new_pkg
    out = os.path.join(SP, f"m_{n}.out.json")
    json.dump(t, open(out, "w", encoding="utf-8"), indent=1)
    dst = os.path.join(LAB, "MA_Parts", "Duro", f"FrontBumper_{n}.uasset")
    fromjson(out, dst)
    back = tojson(dst, os.path.join(SP, f"m_{n}.chk.json"))
    assert not any("RawExport" in e.get("$type", "") for e in back["Exports"]), f"mesh {n} RawExport"
    mats = [im["ObjectName"] for im in back["Imports"] if im["ClassName"] == "Material"]
    assert PAINTABLE in mats, (n, mats)
    return dst


def build_actor(n):
    old_pkg = f"/Game/Cars/Models/Duro/FrontBumper_{n}"
    new_pkg = f"/Game/MA_Parts/Duro/FrontBumper_{n}"
    t = tojson(os.path.join(MA, "Objects", "MoreAttachments", f"Attachment_Duro_FrontBumper_{n}.uasset"),
               os.path.join(SP, f"a_{n}.json"))
    pkg = next((im for im in t["Imports"]
                if im["ClassName"] == "Package" and im["ObjectName"] == old_pkg), None)
    assert pkg, f"actor {n}: no mesh package import {old_pkg}"
    pkg["ObjectName"] = new_pkg
    add_name(t, new_pkg)

    if n in LIGHTS:
        # Lamp bumper: the body is painted (Palette slot renders M_Gray), the
        # HeadLight_HighBeam slot becomes a switchable light. reallights sets
        # OverrideMaterials null for the body slot and M_AttachmentLight for the
        # lamp, and wires ToggleLight / ChangeLightMode / ChangeLightColor.
        facts = reallights.mesh_facts(f"/Game/Cars/Models/Duro/FrontBumper_{n}", SP)
        slots = facts["lamp_slots"]
        assert slots, f"actor {n}: expected a lamp slot"
        reallights.light_up(t, PROFILE, places=reallights.beam_places(facts), slots=slots)
        reallights.override_lamp_materials(t, slots, facts["slot_count"])
    else:
        # Paint-only bumper: drop the override (so the mesh's own M_Gray renders
        # and the paint drives it) and the old ChangeLightColor.
        dropped_ov = dropped_cc = 0
        for e in t["Exports"]:
            data = e.get("Data")
            if not isinstance(data, list):
                continue
            if e.get("ObjectName") == "Mesh_GEN_VARIABLE":
                keep = [p for p in data if not (isinstance(p, dict) and p.get("Name") == "OverrideMaterials")]
                dropped_ov += len(data) - len(keep)
                e["Data"] = keep
                data = keep
            for p in data:
                if isinstance(p, dict) and p.get("Name") == "InteractionParams":
                    keep = [ip for ip in p["Value"]
                            if not any(x.get("Name") == "InteractionType" and x.get("Value") == "ChangeLightColor"
                                       for x in ip["Value"])]
                    dropped_cc += len(p["Value"]) - len(keep)
                    p["Value"] = keep
        assert dropped_ov == 1, f"actor {n}: expected 1 OverrideMaterials, dropped {dropped_ov}"
        assert dropped_cc == 1, f"actor {n}: expected 1 ChangeLightColor, dropped {dropped_cc}"
    out = os.path.join(SP, f"a_{n}.out.json")
    json.dump(t, open(out, "w", encoding="utf-8"), indent=1)
    dst = os.path.join(LAB, "Objects", "MoreAttachments", f"Attachment_Duro_FrontBumper_{n}.uasset")
    fromjson(out, dst)
    back = tojson(dst, os.path.join(SP, f"a_{n}.chk.json"))
    assert not any("RawExport" in e.get("$type", "") for e in back["Exports"]), f"actor {n} RawExport"
    assert len(back["Exports"]) == len(t["Exports"]), f"actor {n} export count changed"
    assert any(im["ObjectName"] == new_pkg for im in back["Imports"]), f"actor {n} repoint lost"
    return dst


for n in NS:
    print("mesh ", build_mesh(n))
    print("actor", build_actor(n))
print("OK: 4 paintable Duro meshes + 4 repointed actors in lab pak")
