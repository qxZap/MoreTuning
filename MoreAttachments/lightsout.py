"""Stop attachments casting a light on the world.

    python lightsout.py            # fix the templates and every built actor
    python lightsout.py --dry      # say what would change, touch nothing
    python lightsout.py demo       # self-check

Every attachment actor carries a SpotLightComponent, because all three actor
templates do, and all three ship it lit: 50 lumens, a 50 degree cone, 4000K.
That is fine for a headlight and wrong for a wing mirror -- a painted part is
supposed to *show* its colour through its emissive material, not throw a pool of
light onto the road next to it. Emissive is a material property and is not
touched here, so the paint still glows; only the cast light goes.

Intensity 0 is the whole fix. The component stays where it is, wired to
MTLightControlComponent exactly as before, so anything that later wants to turn
one on still can.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from pipeline import WORK, from_json, to_json  # noqa: E402

ACTORS = os.path.join(HERE, "..", "qxZap_satigt3_MoreAttachments_P", "MotorTown",
                      "Content", "Objects", "MoreAttachments")
TEMPLATES = ["ACTOR_TEMPLATE.json", "ACTOR_TEMPLATE_NOCOLOR.json",
             "ACTOR_TEMPLATE_SINGLE_COLOR.json"]

# Nothing is exempt. The obvious candidates -- the Cora and Zino headlights and
# Micky's light -- all ship at zero intensity already: they are mesh swaps, and
# the actual illumination comes from the vehicle's own headlight system. An
# exemption list would only re-light them the next time an actor is rebuilt from
# a template.


def is_zero(value):
    # UAssetGUI writes an exact zero as the string "+0".
    return value is None or (0.0 if isinstance(value, str) else float(value)) == 0.0


def douse(asset):
    """Set every spot light in this actor to zero intensity. True if anything moved."""
    changed = False
    for export in asset["Exports"]:
        if "SpotLight" not in str(export.get("ObjectName")):
            continue
        for prop in export.get("Data") or []:
            if not isinstance(prop, dict) or prop["Name"] != "Intensity":
                continue
            if not is_zero(prop.get("Value")):
                prop["Value"] = 0.0
                changed = True
    return changed


def fix_templates(dry):
    for name in TEMPLATES:
        path = os.path.join(HERE, name)
        asset = json.loads(open(path, encoding="utf-8").read())
        if not douse(asset):
            print(f"  {name}: already dark")
            continue
        if not dry:
            shutil.copy2(path, path + ".lit")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asset, f, indent=1)
        print(f"  {name}: light off{' (dry run)' if dry else ''}")


def fix_actors(dry):
    work = os.path.join(WORK, "lights")
    os.makedirs(work, exist_ok=True)
    names = sorted(f[: -len(".uasset")] for f in os.listdir(ACTORS)
                   if f.endswith(".uasset"))
    doused = dark = 0
    for name in names:
        src = os.path.join(ACTORS, name + ".uasset")
        js = to_json(src, os.path.join(work, name + ".json"))
        asset = json.load(open(js, encoding="utf-8"))
        if not douse(asset):
            dark += 1
            continue
        doused += 1
        if dry:
            continue
        with open(js, "w", encoding="utf-8") as f:
            json.dump(asset, f, indent=1)
        built = from_json(js, os.path.join(work, name + ".uasset"))
        for ext in (".uasset", ".uexp"):
            shutil.copy2(built[: -len(".uasset")] + ext, os.path.join(ACTORS, name + ext))
        if doused % 50 == 0:
            print(f"    {doused} doused...", flush=True)
    print(f"\n  {doused} actors doused, {dark} already dark")
    return doused


def demo():
    def actor(intensity):
        return {"Exports": [
            {"ObjectName": "StaticMesh_GEN_VARIABLE", "Data": [
                {"Name": "Intensity", "Value": 999.0}]},          # not a light
            {"ObjectName": "SpotLight_GEN_VARIABLE", "Data": [
                {"Name": "OuterConeAngle", "Value": 50.0},
                {"Name": "Intensity", "Value": intensity}]}]}

    lit = actor(50.0)
    assert douse(lit) is True
    spot = {p["Name"]: p["Value"] for p in lit["Exports"][1]["Data"]}
    assert spot["Intensity"] == 0.0
    assert spot["OuterConeAngle"] == 50.0, "only the intensity should move"
    assert lit["Exports"][0]["Data"][0]["Value"] == 999.0, "must not touch other exports"
    assert douse(lit) is False, "second pass should be a no-op"

    assert douse(actor("+0")) is False, "'+0' is already zero, not a change"
    assert douse({"Exports": []}) is False
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        dry = "--dry" in sys.argv
        print("templates:")
        fix_templates(dry)
        print("\nbuilt actors:")
        fix_actors(dry)
        if not dry:
            print("\nPack with: modp.bat qxZap_satigt3_MoreAttachments_P")
