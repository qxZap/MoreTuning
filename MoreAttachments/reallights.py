"""Make a light attachment actually light something.

    python reallights.py                 # the headlight attachments
    python reallights.py Attachment_Foo  # or named ones
    python reallights.py demo

Our attachments all carry a SpotLightComponent and an MTLightControlComponent,
but only the light was ever configured, and badly -- 50 lumens with no
AttenuationRadius, so it fell back to the 1000 unit default and washed a great
unaimed pool of light over everything. lightsout.py turned all of that off.

This turns it back on for the few that are meant to be lamps, using the game's
own light attachment as the donor -- `Objects/VehicleAttachment/Light_01`, which
is first-party and already 0.7.19, so there is nothing to guess and nothing to
migrate.

The interesting part is what the difference actually was. Vanilla's spot light
is set exactly the way ours already were: 50 lumens, 50 degree cone, 4000K, no
attenuation radius. Its MTLightControlComponent has no properties at all. The
one thing it has that ours did not is `InteractionParams` -- ToggleLight,
ChangeLightMode, ChangeLightColor. Without those the lamp is not switchable, so
it can only sit there lit, which is exactly what was wrong with the painted
parts before lightsout.py turned them off.

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

# No aim and no colour override: vanilla sets neither. The light points down its
# component's own forward axis and takes its colour from a 4000K temperature,
# and ChangeLightColor lets the player pick anyway.


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


def light_up(asset, profile):
    """Give this actor the working light setup. True if anything changed."""
    changed = False
    for export in asset["Exports"]:
        obj = str(export.get("ObjectName"))
        if "SpotLight" in obj:
            # Placement is per attachment; the beam itself comes from vanilla.
            keep = [p for p in export.get("Data") or []
                    if isinstance(p, dict) and p["Name"] == "RelativeLocation"]
            export["Data"] = keep + copy.deepcopy(profile["SpotLight"])
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
        if not light_up(asset, profile):
            print(f"  {name}: no light components")
            continue
        with open(js, "w", encoding="utf-8") as f:
            json.dump(asset, f, indent=1)
        built = from_json(js, os.path.join(work, name + ".uasset"))
        for ext in (".uasset", ".uexp"):
            shutil.copy2(built[: -len(".uasset")] + ext, os.path.join(ACTORS, name + ext))
        print(f"  {name}: lit")
        done += 1
    print(f"\n{done} attachments now cast light")
    print("Pack with: modp.bat qxZap_satigt3_MoreAttachments_P")


def demo():
    profile = {
        "SpotLight": [
            {"Name": "Intensity", "Value": 50.0},
            {"Name": "Temperature", "Value": 4000.0}],
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

    assert light_up(asset, profile) is True
    spot = {p["Name"]: p.get("Value") for p in asset["Exports"][0]["Data"]}
    assert spot["Intensity"] == 50.0, "vanilla's own setting, not a guess"
    assert spot["RelativeLocation"][0]["Value"]["X"] == 7.0, "placement must survive"
    assert asset["Exports"][1]["Data"] == [], "vanilla sets nothing on the light control"
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
