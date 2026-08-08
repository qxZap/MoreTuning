"""Make a light attachment actually light something.

    python reallights.py                 # the headlight attachments
    python reallights.py Attachment_Foo  # or named ones
    python reallights.py demo

Our attachments all carry a SpotLightComponent and an MTLightControlComponent,
but only the light was ever configured, and badly -- 50 lumens with no
AttenuationRadius, so it fell back to the 1000 unit default and washed a great
unaimed pool of light over everything. lightsout.py turned all of that off.

This turns it back on for the few that are meant to be lamps, copying the setup
off a light bar that works (Maja's DetailWorks, `Neutz_Light_Aux2`) rather than
guessing. Two things make the difference:

  * the beam is shaped -- 5 lumens, 150 unit radius, exponent 2 falloff, aimed
  * `MTLightControlComponent.LightIntensity` is set, which is what lets the game
    switch the light on and off with the vehicle's own lights; with it unset the
    component has no baseline to scale and the lamp is inert

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

# ponytail: aimed straight down the parent's forward axis. Maja's bar carries a
# baked-in rotation because its mesh sits at an angle; ours are square to the
# vehicle, so zero is the honest starting point -- and this is the knob to turn
# first if the beam points somewhere silly in game.
AIM = {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}

# The donor is an amber warning bar. Headlights are white, so the colour is
# overridden in both places it is held, and they are not the same shape: the
# light's own FColor is written as a "R, G, B" string in 0-255, the control
# component's FLinearColor as fields in 0-1. Leave them disagreeing and the lamp
# changes colour the moment the game first toggles it.
WHITE_255 = "255, 255, 255"
WHITE_LINEAR = {"R": 1.0, "G": 1.0, "B": 1.0, "A": 1.0}


def names_in(value):
    """Every FName a property blob mentions, so the name map can be topped up."""
    out = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("Name", "StructType", "EnumType", "InnerType", "ArrayType") \
                    and isinstance(item, str):
                out.append(item)
            else:
                out += names_in(item)
    elif isinstance(value, list):
        for item in value:
            out += names_in(item)
    return out


def light_up(asset, profile, aim=AIM):
    """Give this actor the working light setup. True if anything changed."""
    changed = False
    for export in asset["Exports"]:
        obj = str(export.get("ObjectName"))
        if "SpotLight" in obj:
            keep = [p for p in export.get("Data") or []
                    if isinstance(p, dict) and p["Name"] == "RelativeLocation"]
            fresh = copy.deepcopy(profile["SpotLight"])
            for prop in fresh:
                if prop["Name"] == "RelativeRotation":
                    prop["Value"][0]["Value"].update(aim)
                elif prop["Name"] == "LightColor":
                    prop["Value"][0]["Value"] = WHITE_255
            export["Data"] = keep + fresh
            changed = True
        elif "MTLightControl" in obj:
            fresh = copy.deepcopy(profile["MTLightControl"])
            for prop in fresh:
                if prop["Name"] == "Net_LightColor":
                    prop["Value"][0]["Value"].update(WHITE_LINEAR)
            export["Data"] = fresh
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
            {"Name": "Intensity", "Value": 5.0},
            {"Name": "AttenuationRadius", "Value": 150.0},
            {"Name": "LightColor", "StructType": "Color",
             "Value": [{"Name": "LightColor", "Value": "255, 166, 0"}]},
            {"Name": "RelativeRotation", "Value": [
                {"Value": {"Pitch": 90.0, "Yaw": 374.0, "Roll": 284.0}}]}],
        "MTLightControl": [
            {"Name": "LightIntensity", "Value": 30.0},
            {"Name": "Net_LightColor", "Value": [{"Value": {"R": 1.0, "G": 0.25, "B": 0.0, "A": 0.0}}]}],
    }
    asset = {"NameMap": [], "NamesReferencedFromExportDataCount": 0, "Exports": [
        {"ObjectName": "SpotLight_GEN_VARIABLE", "Data": [
            {"Name": "Intensity", "Value": 0.0},
            {"Name": "RelativeLocation", "Value": [{"Value": {"X": 7.0}}]}]},
        {"ObjectName": "MTLightControl_GEN_VARIABLE", "Data": []},
        {"ObjectName": "StaticMesh_GEN_VARIABLE", "Data": [{"Name": "Intensity", "Value": 1.0}]}]}

    assert light_up(asset, profile) is True
    spot = {p["Name"]: p.get("Value") for p in asset["Exports"][0]["Data"]}
    assert spot["Intensity"] == 5.0
    assert spot["AttenuationRadius"] == 150.0, "the default 1000 radius is the whole problem"
    assert spot["RelativeLocation"][0]["Value"]["X"] == 7.0, "placement must survive"
    assert spot["RelativeRotation"][0]["Value"] == AIM, "aim is ours, not the donor's"
    control = {p["Name"]: p["Value"] for p in asset["Exports"][1]["Data"]}
    assert control["LightIntensity"] == 30.0, "without this the lamp is inert"
    assert spot["LightColor"][0]["Value"] == WHITE_255, "donor is amber, headlights are not"
    linear = {p["Name"]: p["Value"] for p in asset["Exports"][1]["Data"]}["Net_LightColor"]
    assert linear[0]["Value"] == WHITE_LINEAR, "both colours must agree"
    assert asset["Exports"][2]["Data"][0]["Value"] == 1.0, "must not touch other exports"
    assert "LightColor" in asset["NameMap"] and "Color" in asset["NameMap"], \
        "new properties need their names, or the write drops them"
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main(sys.argv[1:] or HEADLIGHTS)
