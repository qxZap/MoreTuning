"""Build MoreAttachments' tables in the 0.7.19 format.

run.py composes its tables the way it always has -- vanilla rows plus generated
ones, referencing actors and meshes through the import table. 0.7.19 moved those
references to soft object paths on MTItemRow (AttachmentPartActorClass,
StaticMesh, IconTexture, Material, PickupSound, DropActorClass,
HoldableActorClass), so a table built the old way no longer parses and the game
reports corrupt data.

Rather than rewrite run.py's import bookkeeping, its output is rebased onto the
current vanilla table on the way out -- the same migration the vehicle part
tables go through, which reads which properties went soft off vanilla itself.

    from migrate import build
    build("../qxZap_satigt3_MoreAttachments_P/.../Items_AttachmentPart.json")
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from pipeline import CURRENT_MAPPINGS, ENGINE_VERSION, UASSETGUI, VANILLA  # noqa: E402
from rebase import rebase  # noqa: E402

CONTENT_MARKER = os.path.join("MotorTown", "Content") + os.sep


def vanilla_twin(out_json):
    """The vanilla .uasset this output shadows, if there is one."""
    path = os.path.abspath(out_json)
    at = path.replace("/", os.sep).find(CONTENT_MARKER)
    if at < 0:
        return None
    rel = path[at + len(CONTENT_MARKER):]
    candidate = os.path.join(VANILLA, os.path.splitext(rel)[0] + ".uasset")
    return candidate if os.path.isfile(candidate) else None


def to_json(uasset, out, mappings=CURRENT_MAPPINGS):
    if os.path.exists(out):
        os.remove(out)
    subprocess.run([UASSETGUI, "tojson", uasset, out, ENGINE_VERSION, mappings], check=True)
    return out if os.path.exists(out) else None


def build(json_path, keep_json=False):
    """Migrate if it is a table with a vanilla counterpart, then write the asset."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    is_table = data["Exports"][0]["$type"].startswith("UAssetAPI.ExportTypes.DataTableExport")
    twin = vanilla_twin(json_path) if is_table else None
    if twin:
        fresh = to_json(twin, json_path + ".vanilla")
        if not fresh:
            sys.exit(f"could not read vanilla {twin} with {CURRENT_MAPPINGS}")
        with open(fresh, "r", encoding="utf-8") as f:
            vanilla = json.load(f)
        os.remove(fresh)
        merged, kept, added = rebase(vanilla, data)
        print(f"   rebased onto vanilla: {kept} vanilla rows + {added} mod rows")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=1)

    out = json_path.replace(".json", ".uasset")
    for stale in (out, out.replace(".uasset", ".uexp")):
        if os.path.exists(stale):
            os.remove(stale)
    subprocess.run([UASSETGUI, "fromjson", json_path, out, CURRENT_MAPPINGS], check=True)
    if not os.path.exists(out):
        sys.exit(f"UAssetGUI wrote nothing for {json_path} -- see AGENTS.md for why")
    if not keep_json:
        os.remove(json_path)
    return out


def demo():
    assert vanilla_twin(r"X:\a\qxZap_x_P\MotorTown\Content\DataAsset\Items\Nope.json") is None
    real = os.path.join("x", "MotorTown", "Content", "DataAsset", "Items",
                        "Items_AttachmentPart.json")
    assert vanilla_twin(real) == os.path.join(
        VANILLA, "DataAsset", "Items", "Items_AttachmentPart.uasset")
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        for arg in sys.argv[1:]:
            print(build(arg, keep_json=True))
