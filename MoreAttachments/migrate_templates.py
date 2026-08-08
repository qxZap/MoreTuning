"""Regenerate the three ACTOR_TEMPLATE files in the current JSON schema.

    python migrate_templates.py

The templates were exported with UAssetGUI v1.0.2, whose JSON the current v1.1.1
cannot read, so actor generation (CREATE_ACTORS) fails. The actor format itself
did not change in 0.7.19 -- a built actor parses identically under the 0.7.18 and
0.7.19 mappings -- so the fix is simply to re-export one through the current
tool and re-derive the variants from it.

Attachment_Neo_RearSpoiler_01 in the built pak is the template's own subject, so
reading it back gives the base template unchanged. The variants differ only in
the mesh's OverrideMaterials:

    ACTOR_TEMPLATE               one entry   (paintable)
    ACTOR_TEMPLATE_SINGLE_COLOR  two entries (same material twice)
    ACTOR_TEMPLATE_NOCOLOR       property absent
    ACTOR_TEMPLATE_LIGHT         one entry, plus a lamp that works

The source is a *built* actor, so its offsets are that one spoiler's real
numbers. run.py fills those in per mesh by string-replacing sentinel values, and
re-deriving from a built actor is exactly what quietly dropped them -- new actors
then came out with a Neo spoiler's offset baked in. They are put back here.

Note the mesh and the light do not share an offset any more. The mesh offset
cancels the part's authored position so the geometry lands on the attachment
point; a light has no geometry to cancel, and giving it the same number put the
lamp under the middle of the car.
"""
import copy
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
import reallights  # noqa: E402
from migrate import to_json  # noqa: E402

SOURCE = os.path.join(HERE, "..", "qxZap_satigt3_MoreAttachments_P", "MotorTown", "Content",
                      "Objects", "MoreAttachments", "Attachment_Neo_RearSpoiler_01.uasset")
MESH_EXPORT = "Mesh_GEN_VARIABLE"
LIGHT_EXPORT = "SpotLight_GEN_VARIABLE"
PROFILE = os.path.join(HERE, "LIGHT_PROFILE.json")

# What run.py string-replaces per mesh. Distinctive enough not to collide with a
# real coordinate, which is the whole reason they are these numbers.
MESH_OFFSET = {"X": -0.96961, "Y": -0.96962, "Z": -0.96963}
LENS_OFFSET = {"X": -0.96971, "Y": -0.96972, "Z": -0.96973}


def located(export):
    for prop in export.get("Data") or []:
        if isinstance(prop, dict) and prop["Name"] == "RelativeLocation":
            return prop["Value"][0]["Value"]
    return None


def export_named(asset, name):
    for export in asset["Exports"]:
        if export["ObjectName"] == name:
            return export
    return None


def restore_placeholders(asset):
    """Put the sentinels back, one set for the mesh and one for the lamp."""
    for name, values in ((MESH_EXPORT, MESH_OFFSET), (LIGHT_EXPORT, LENS_OFFSET)):
        export = export_named(asset, name)
        if export is None:
            continue
        where = located(export)
        if where is not None:
            where.update(values)


def override_materials(asset):
    for export in asset["Exports"]:
        if export["ObjectName"] != MESH_EXPORT:
            continue
        for prop in export.get("Data", []):
            if prop["Name"] == "OverrideMaterials":
                return export, prop
        return export, None
    sys.exit(f"no {MESH_EXPORT} export in the source actor")


def main():
    if not os.path.isfile(SOURCE):
        sys.exit(f"missing {SOURCE} -- needs one built actor to re-export from")

    work = os.path.join(HERE, "_template.json")
    if not to_json(SOURCE, work):
        sys.exit("could not read the built actor with the current mappings")
    with open(work, "r", encoding="utf-8") as f:
        base = json.load(f)
    os.remove(work)

    # Whichever variant this actor happened to be built from, every entry points
    # at the same paintable material, so one entry is enough to rebuild all three.
    _, prop = override_materials(base)
    if prop is None or not prop["Value"]:
        sys.exit("source actor has no OverrideMaterials to derive the variants from")
    slot = copy.deepcopy(prop["Value"][0])

    profile = json.load(open(PROFILE, encoding="utf-8")) if os.path.isfile(PROFILE) else None

    for name in ("ACTOR_TEMPLATE.json", "ACTOR_TEMPLATE_NOCOLOR.json",
                 "ACTOR_TEMPLATE_SINGLE_COLOR.json", "ACTOR_TEMPLATE_LIGHT.json"):
        path = os.path.join(HERE, name)
        if os.path.isfile(path) and not os.path.isfile(path + ".pre719"):
            shutil.copy2(path, path + ".pre719")

        asset = copy.deepcopy(base)
        export, materials = override_materials(asset)
        if name.endswith("NOCOLOR.json"):
            export["Data"] = [p for p in export["Data"] if p["Name"] != "OverrideMaterials"]
        else:
            slots = 2 if name.endswith("SINGLE_COLOR.json") else 1
            materials["Value"] = [copy.deepcopy(slot) for _ in range(slots)]
            for index, entry in enumerate(materials["Value"]):
                entry["Name"] = str(index)

        lit = ""
        if name.endswith("LIGHT.json"):
            if profile is None:
                sys.exit(f"{PROFILE} is missing -- run reallights.py's harvest first")
            reallights.light_up(asset, profile)
            lit = "  + a working lamp"

        restore_placeholders(asset)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asset, f, indent=1)
        _, check = override_materials(asset)
        entries = 0 if check is None else len(check["Value"])
        print(f"  {name:34} OverrideMaterials entries={entries}{lit}")

    print("\n4 templates regenerated (old ones kept as *.pre719)")
    print("mesh offset sentinel", MESH_OFFSET["X"], " lens offset sentinel", LENS_OFFSET["X"])


if __name__ == "__main__":
    main()
