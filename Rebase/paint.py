"""Which material slots of a part are paint, read off its mesh.

Body parts paint where a mesh slot uses M_Body. Vanilla mostly leaves it at that:
388 of 413 AeroParts rows have no ColorSlots, and the car paints the slot only
if its name lines up with the car's own (RearWing, Body_01, Body_02 ... differ
from car to car). On its own car that holds; on any other it often does not,
which is why No Limits parts came out unpaintable.

A ColorSlots entry per M_Body slot makes a part carry its own paint slot -- the
0.7.20 colour, metallic and roughness sliders -- wherever it is fitted.
M_Palette and the PolygonStreetRacer textured bodies are fixed palette
textures, not paint, and are left alone.

Attachments (attachment_slots) get one paint slot per channel whose material
takes paint: one with a "Color" parameter of its own or inherited -- M_Body has
Color, Metallic and Roughness, the antenna's M_Gray has Color. A palette
material has only textures, so painting it does nothing; those channels get no
slot (the actor's old tint-the-whole-part trick covers them instead).

Mesh reads are cached in work/mesh_materials3.json; delete it after a game update.
"""
import copy
import json
import os
import re

from pipeline import VANILLA, WORK, to_json

PAINT_MATERIALS = ("M_Body",)
CACHE = os.path.join(WORK, "mesh_materials3.json")
COLOR_PARAM = b"\x06\x00\x00\x00Color\x00"  # the NameMap entry "Color"
_paintable = {}
NOT_PAINT = ("Light", "Glass", "Lamp", "Emissive", "Signal", "Mirror")
_cache = None


def _load_cache():
    global _cache
    if _cache is None:
        _cache = json.load(open(CACHE, encoding="utf-8")) if os.path.isfile(CACHE) else {}
    return _cache


def mesh_of(table, row):
    """The first StaticMesh a part row references, as (package, object), or None."""
    imports = table["Imports"]
    found = []

    def walk(n):
        if isinstance(n, dict):
            v = n.get("Value")
            if n.get("$type", "").startswith("UAssetAPI.PropertyTypes.Objects.ObjectPropertyData")                     and isinstance(v, int) and v < 0:
                o = imports[-v - 1]
                if o["ClassName"] == "StaticMesh":
                    found.append((imports[-o["OuterIndex"] - 1]["ObjectName"], o["ObjectName"]))
            for x in n.values():
                walk(x)
        elif isinstance(n, list):
            for x in n:
                walk(x)
    walk(row)
    return found[0] if found else None


def material_slots(mesh_json):
    """[(slot name, material object name, material package)] of a StaticMesh export."""
    out = []
    imports = mesh_json["Imports"]
    for e in mesh_json["Exports"]:
        for p in e.get("Data") or []:
            if isinstance(p, dict) and p.get("Name") == "StaticMaterials":
                for sm in p["Value"]:
                    d = {x["Name"]: x for x in sm["Value"]}
                    mi = d.get("MaterialInterface", {}).get("Value")
                    mat = pkg = None
                    if isinstance(mi, int) and mi < 0:
                        mat = imports[-mi - 1]["ObjectName"]
                        outer = imports[-mi - 1]["OuterIndex"]
                        pkg = imports[-outer - 1]["ObjectName"] if outer < 0 else None
                    out.append((d.get("MaterialSlotName", {}).get("Value"), mat, pkg))
    return out


def mesh_materials(package, roots=(VANILLA,)):
    """[(slot, material, material package)] of this mesh package; [] if not found."""
    cache = _load_cache()
    if package not in cache:
        rel = package[len("/Game/"):].replace("/", os.sep) + ".uasset"
        path = next((os.path.join(r, rel) for r in roots if os.path.isfile(os.path.join(r, rel))),
                    None)
        found = []
        if path:
            mesh = json.load(open(to_json(path, os.path.join(WORK, "paint_mesh.json")),
                                  encoding="utf-8"))
            found = [[s, m, k] for s, m, k in material_slots(mesh) if s]
        cache[package] = found
        os.makedirs(WORK, exist_ok=True)
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=1)
    return cache[package]


def body_slots(package, roots=(VANILLA,)):
    """Slot names of this mesh that are car paint (M_Body)."""
    return [s for s, m, _ in mesh_materials(package, roots) if m in PAINT_MATERIALS]


def paintable_material(package, roots=(VANILLA,), depth=0):
    """Does this material take paint: a "Color" parameter, its own or a parent's."""
    if not package or not package.startswith("/Game/") or depth > 4:
        return False
    if package not in _paintable:
        rel = package[len("/Game/"):].replace("/", os.sep) + ".uasset"
        path = next((os.path.join(r, rel) for r in roots if os.path.isfile(os.path.join(r, rel))),
                    None)
        data = open(path, "rb").read() if path else b""
        own = COLOR_PARAM in data
        parents = {m.decode() for m in re.findall(rb"/Game/[A-Za-z0-9_/]+/M[I]?_[A-Za-z0-9_]+", data)}
        _paintable[package] = own or any(paintable_material(p, roots, depth + 1)
                                         for p in parents - {package})
    return _paintable[package]


def attachment_slots(package, roots=(VANILLA,)):
    """Channels of this mesh an attachment can paint natively, in mesh order."""
    return [s for s, m, k in mesh_materials(package, roots)
            if paintable_material(k, roots)
            and not any(w.lower() in s.lower() or w.lower() in (m or "").lower() for w in NOT_PAINT)]


def color_slot_entries(slots, pair_template, slot_value):
    """ColorSlots map pairs for these slot names.

    pair_template is any vanilla [key, value] pair of a ColorSlots map, for the
    JSON shape; slot_value is the MTVehicleColorSlot body to give each (the
    0.7.20 antennas' one: literal "Body", grey, metallic/roughness 0.375).
    """
    out = []
    for slot in slots:
        key, value = copy.deepcopy(pair_template)
        key["Value"] = slot
        value["Value"] = copy.deepcopy(slot_value)
        out.append([key, value])
    return out


def demo():
    mesh = {"Imports": [{"ObjectName": "M_Body"}, {"ObjectName": "M_Palette"}],
            "Exports": [{"Data": [{"Name": "StaticMaterials", "Value": [
                {"Value": [{"Name": "MaterialSlotName", "Value": "Body_01"},
                           {"Name": "MaterialInterface", "Value": -1}]},
                {"Value": [{"Name": "MaterialSlotName", "Value": "Palette"},
                           {"Name": "MaterialInterface", "Value": -2}]}]}]}]}
    assert material_slots(mesh) == [("Body_01", "M_Body"), ("Palette", "M_Palette")]
    pair = [{"Name": "ColorSlots", "Value": "X"}, {"Name": "ColorSlots", "Value": []}]
    out = color_slot_entries(["Body_01"], pair, [{"Name": "DefaultMetallic", "Value": 0.375}])
    assert out[0][0]["Value"] == "Body_01" and out[0][1]["Value"][0]["Value"] == 0.375
    assert pair[0]["Value"] == "X"
    print("ok")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    demo()
