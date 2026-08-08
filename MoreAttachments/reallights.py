"""Make a light attachment actually light something.

    python reallights.py                 # the headlight attachments
    python reallights.py Attachment_Foo  # or named ones
    python reallights.py demo

Our attachments all carry a SpotLightComponent and an MTLightControlComponent,
but the light was the only part ever configured, and it was never switchable, so
it just sat on. lightsout.py turned all of that off. This turns it back on for
the few that are meant to be lamps.

The donor is the game's own, `Objects/VehicleAttachment/Light_05` -- first party
and already 0.7.19, so there is nothing to guess and nothing to migrate. Of the
vanilla light attachments it is the bright one: 200 lumens over a 1500 unit
attenuation radius at 5000K, where Light_01 is 50 lumens with no radius set at
all and reads as a glow rather than a beam.

What was actually missing all along was `InteractionParams` -- ToggleLight,
ChangeLightMode, ChangeLightColor. A light without those cannot be switched, so
it can only sit there lit, which is also the whole story behind the painted
parts: they were built from a template carrying a lamp's settings and no way to
turn it off.

`LIGHT_PROFILE.json` holds the harvested settings, so retuning is a data edit.
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
PROFILE = os.path.join(HERE, "LIGHT_PROFILE.json")

# The attachments that are lamps rather than trim. Everything else stays dark.
HEADLIGHTS = ["Attachment_CoraHeadlight_01", "Attachment_CoraHeadlight_02",
              "Attachment_ZinoHeadlight_01", "Attachment_ZinoHeadlight_02",
              "Attachment_ZinoHeadlight_03", "Attachment_Micky_Light"]

# Square to the attachment, which points down the road once the beam is actually
# where the lamp is. The half turn tried before was compensating for the light
# being in the wrong place, not for it facing the wrong way.
AIM = {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}

# A part mesh is authored in vehicle space -- a Zino headlight's geometry sits at
# X=199 because that is where it lives on the car -- so the actor shifts the mesh
# component back by that origin to land it on the attachment point. run.py works
# this out with get_x_bounding and it is right for a mesh.
#
# It is wrong for a light. A spot light is a point with no geometry to drag back,
# so the same offset does not correct anything, it just moves the lamp two metres
# behind the car and half a metre down -- under the middle of the vehicle, which
# is exactly where it was showing up. The light belongs at the actor origin,
# pushed forward to the face of the lamp so the beam starts at the lens.
VANILLA = os.path.join(HERE, "..", "..", "Output", "Exports", "MotorTown", "Content")

# The material that says "this part of the mesh is a lamp". No M_HeadLight, no
# beam -- which is how Micky_Light_L, a wheel arch trim piece, gets left alone.
LIGHT_MATERIALS = ("M_HeadLight",)

# Colour is left alone: the profile carries a colour temperature rather than an
# RGB, and ChangeLightColor lets the player pick anyway.


# An enum entry and an FName are stored as names, not as text, so "ToggleLight"
# has to be in the map like any property name. Miss these and the write drops
# the interactions on the floor without saying anything.
NAME_VALUED = ("EnumPropertyData", "NamePropertyData")


def names_in(value):
    """Every FName a property blob mentions, so the name map can be topped up."""
    out = []
    if isinstance(value, dict):
        kind = value.get("$type", "")
        for key, item in value.items():
            if key in ("Name", "StructType", "EnumType", "InnerType", "ArrayType") \
                    and isinstance(item, str):
                out.append(item)
            elif key == "Value" and isinstance(item, str) \
                    and any(k in kind for k in NAME_VALUED):
                out.append(item)
            else:
                out += names_in(item)
    elif isinstance(value, list):
        for item in value:
            out += names_in(item)
    return out


def mesh_package(asset):
    """The car part this attachment is built from."""
    for entry in asset["Imports"]:
        name = str(entry.get("ObjectName"))
        if name.startswith("/Game/Cars/"):
            return name
    return None


def extended_bounds(mesh):
    """The mesh's own origin and half-size, the same field run.py reads."""
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

    for export in mesh["Exports"]:
        for row in export.get("Data") or []:
            if isinstance(row, dict) and row.get("Name") == "ExtendedBounds":
                walk(row["Value"])
    return found


def mesh_facts(package, work):
    """Bounds and materials of the part mesh behind an attachment."""
    path = os.path.join(VANILLA, *package.replace("/Game/", "").split("/")) + ".uasset"
    if not os.path.isfile(path):
        return None
    mesh = json.load(open(to_json(path, os.path.join(work, "mesh.json")), encoding="utf-8"))
    return {"bounds": extended_bounds(mesh),
            "materials": [i["ObjectName"] for i in mesh["Imports"]
                          if i.get("ClassName") in ("MaterialInstanceConstant", "Material")]}


def beam_origin(facts):
    """Where the light itself goes: on the attachment point, forward to the lens."""
    extent = (facts or {}).get("bounds", {}).get("BoxExtent")
    return {"X": float(extent["X"]) if extent else 0.0, "Y": 0.0, "Z": 0.0}


def light_up(asset, profile, aim=AIM, place=None):
    """Give this actor the working light setup. True if anything changed."""
    changed = False
    for export in asset["Exports"]:
        obj = str(export.get("ObjectName"))
        if "SpotLight" in obj:
            keep = [p for p in export.get("Data") or []
                    if isinstance(p, dict) and p["Name"] == "RelativeLocation"]
            if place is not None:
                for prop in keep:
                    prop["Value"][0]["Value"].update(place)
            fresh = copy.deepcopy(profile["SpotLight"])
            for prop in fresh:
                if prop["Name"] == "RelativeRotation":
                    prop["Value"][0]["Value"].update(aim)
            export["Data"] = keep + fresh
            changed = True
        elif "MTLightControl" in obj:
            export["Data"] = copy.deepcopy(profile["MTLightControl"])
            changed = True
        elif "MTInteractable" in obj:
            # Without this the lamp is wired but unreachable: there is no
            # ToggleLight on the interaction menu, so nothing ever switches it
            # on. Keep whatever the actor already declared about how it is
            # interacted with, and add the light options.
            keep = [p for p in export.get("Data") or []
                    if isinstance(p, dict) and p["Name"] != "InteractionParams"]
            export["Data"] = keep + copy.deepcopy(profile["MTInteractable"])
            changed = True
    if changed:
        register_names(asset, names_in(profile))
    return changed


def main(wanted):
    profile = json.load(open(PROFILE, encoding="utf-8"))
    work = os.path.join(WORK, "reallights")
    os.makedirs(work, exist_ok=True)
    done = 0
    for name in wanted:
        src = os.path.join(ACTORS, name + ".uasset")
        if not os.path.isfile(src):
            print(f"  {name}: no such actor")
            continue
        js = to_json(src, os.path.join(work, name + ".json"))
        asset = json.load(open(js, encoding="utf-8"))

        package = mesh_package(asset)
        facts = mesh_facts(package, work) if package else None
        if facts and not any(m in facts["materials"] for m in LIGHT_MATERIALS):
            print(f"  {name}: no lamp material on {package.rsplit('/', 1)[-1]}, left dark")
            continue
        place = beam_origin(facts)

        if not light_up(asset, profile, place=place):
            print(f"  {name}: no light components")
            continue
        with open(js, "w", encoding="utf-8") as f:
            json.dump(asset, f, indent=1)
        built = from_json(js, os.path.join(work, name + ".uasset"))
        for ext in (".uasset", ".uexp"):
            shutil.copy2(built[: -len(".uasset")] + ext, os.path.join(ACTORS, name + ext))
        print(f"  {name}: lit, beam at X={place['X']:.0f}")
        done += 1
    print(f"\n{done} attachments now cast light")
    print("Pack with: modp.bat qxZap_satigt3_MoreAttachments_P")


def demo():
    profile = {
        "SpotLight": [
            {"Name": "Intensity", "Value": 200.0},
            {"Name": "Temperature", "Value": 5000.0},
            {"Name": "RelativeRotation", "Value": [
                {"Value": {"Pitch": 10.0, "Yaw": 0.0, "Roll": 0.0}}]}],
        "MTInteractable": [{"Name": "InteractionParams", "Value": [
            {"StructType": "MTInteractionParams", "Name": "0", "Value": [
                {"$type": "...EnumPropertyData, UAssetAPI", "Name": "InteractionType",
                 "EnumType": "EMotorTownInteractableType", "Value": "ToggleLight"}]}]}],
        "MTLightControl": [],
    }
    asset = {"NameMap": [], "NamesReferencedFromExportDataCount": 0, "Exports": [
        {"ObjectName": "SpotLight_GEN_VARIABLE", "Data": [
            {"Name": "Intensity", "Value": 0.0},
            {"Name": "RelativeLocation", "Value": [{"Value": {"X": 7.0}}]}]},
        {"ObjectName": "MTLightControl_GEN_VARIABLE", "Data": []},
        {"ObjectName": "MTInteractable_GEN_VARIABLE", "Data": [
            {"Name": "bInteractbyActor", "Value": True},
            {"Name": "InteractionParams", "Value": []}]},
        {"ObjectName": "StaticMesh_GEN_VARIABLE", "Data": [{"Name": "Intensity", "Value": 1.0}]}]}

    assert light_up(asset, profile, place={"X": 12.0, "Y": 0.0, "Z": 0.0}) is True
    spot = {p["Name"]: p.get("Value") for p in asset["Exports"][0]["Data"]}
    assert spot["Intensity"] == 200.0, "vanilla's own setting, not a guess"
    assert spot["RelativeRotation"][0]["Value"] == AIM, "the donor's aim is not ours"

    facts = {"bounds": {"BoxExtent": {"X": 8.8, "Y": 69.9, "Z": 9.6}}}
    assert beam_origin(facts) == {"X": 8.8, "Y": 0.0, "Z": 0.0}
    assert beam_origin(None) == {"X": 0.0, "Y": 0.0, "Z": 0.0}, "no mesh, no guess"
    assert spot["RelativeLocation"][0]["Value"]["X"] == 12.0,         "the light goes to the lens, not to the mesh's pivot correction"
    assert asset["Exports"][1]["Data"] == profile["MTLightControl"]
    inter = asset["Exports"][2]["Data"]
    kinds = [f["Value"] for p in inter if p["Name"] == "InteractionParams"
             for st in p["Value"] for f in st["Value"] if f["Name"] == "InteractionType"]
    assert kinds == ["ToggleLight"], kinds
    assert any(p["Name"] == "bInteractbyActor" for p in inter),         "the actor's own interaction settings must survive"
    assert "ToggleLight" in asset["NameMap"], "an enum entry is a name, or it is dropped"
    assert "MTInteractionParams" in asset["NameMap"]
    assert asset["Exports"][3]["Data"][0]["Value"] == 1.0, "must not touch other exports"
    assert "Temperature" in asset["NameMap"], \
        "new properties need their names, or the write drops them"
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main(sys.argv[1:] or HEADLIGHTS)
