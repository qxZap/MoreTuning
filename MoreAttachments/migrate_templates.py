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
"""
import copy
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from migrate import to_json  # noqa: E402

SOURCE = os.path.join(HERE, "..", "qxZap_satigt3_MoreAttachments_P", "MotorTown", "Content",
                      "Objects", "MoreAttachments", "Attachment_Neo_RearSpoiler_01.uasset")
MESH_EXPORT = "Mesh_GEN_VARIABLE"


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

    for name in ("ACTOR_TEMPLATE.json", "ACTOR_TEMPLATE_NOCOLOR.json",
                 "ACTOR_TEMPLATE_SINGLE_COLOR.json"):
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

        with open(path, "w", encoding="utf-8") as f:
            json.dump(asset, f, indent=1)
        _, check = override_materials(asset)
        entries = 0 if check is None else len(check["Value"])
        print(f"  {name:34} OverrideMaterials entries={entries}")

    print("\n3 templates regenerated (old ones kept as *.pre719)")


if __name__ == "__main__":
    main()
