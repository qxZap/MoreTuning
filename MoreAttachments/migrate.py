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


SCALE_PROPS = ("AttachmentScaleMin", "AttachmentScaleMax")


def unlock_scaling(rows, vanilla_count):
    """Give vanilla attachments the same scale range the mod's own parts use.

    Vanilla ships most attachments locked at AttachmentScaleMin = Max = 1.0, so
    they cannot be resized in game. The generated rows use a wider range; take
    whatever that is rather than hardcoding it, and apply it to the vanilla rows
    the rebase brought back.
    """
    def scale_of(row):
        found = {p["Name"]: p for p in row["Value"] if p["Name"] in SCALE_PROPS}
        return found if len(found) == len(SCALE_PROPS) else None

    ranges = [tuple(scale_of(r)[n]["Value"] for n in SCALE_PROPS)
              for r in rows[vanilla_count:] if scale_of(r)]
    if not ranges:
        return 0
    target = max(set(ranges), key=ranges.count)

    changed = 0
    for row in rows[:vanilla_count]:
        found = scale_of(row)
        if not found:
            continue
        if tuple(found[n]["Value"] for n in SCALE_PROPS) == target:
            continue
        for name, value in zip(SCALE_PROPS, target):
            found[name]["Value"] = value
        changed += 1
    if changed:
        print(f"   unlocked scaling on {changed} vanilla rows -> {target[0]}..{target[1]}")
    return changed


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
        unlock_scaling(merged["Exports"][0]["Table"]["Data"], kept)
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
    def row(name, lo, hi):
        return {"Name": name, "Value": [
            {"Name": "AttachmentScaleMin", "Value": lo},
            {"Name": "AttachmentScaleMax", "Value": hi}]}

    rows = [row("van_locked", 1.0, 1.0), row("van_half", 0.5, 1.0),
            row("mod_a", 0.25, 5.0), row("mod_b", 0.25, 5.0)]
    assert unlock_scaling(rows, 2) == 2
    assert [(r["Value"][0]["Value"], r["Value"][1]["Value"]) for r in rows[:2]] == [
        (0.25, 5.0), (0.25, 5.0)]
    assert unlock_scaling(rows, 2) == 0, "second pass should be a no-op"
    # a table with no mod rows to learn from must be left alone
    only_vanilla = [row("van", 1.0, 1.0)]
    assert unlock_scaling(only_vanilla, 1) == 0
    assert only_vanilla[0]["Value"][0]["Value"] == 1.0

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
