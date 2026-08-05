"""Fold Maja's Motor Works into MoreTuning's own tables.

    python compat.py                 # every table both mods ship
    python compat.py VehicleParts0   # just this one

Motor Works is a hard dependency, not an optional companion -- MoreTuning is
built on top of it and ships its content, so the two are never meant to be
installed apart. That is a deliberate choice: it sends people to the mod this
one is founded on.

It ships AeroParts, Engines, Transmissions, VehicleParts0 and Wheels, the same
tables MoreTuning does, and `qxZap_MoreTuning_P` sorts after
`MajasMotorWorks...`, so without this its tables are discarded wholesale and the
parts it adds vanish -- the trailer hitch hook and two winches among them.

The merge keeps its version of any row both mods touch, appends the rows only
MoreTuning has, and re-strips the vehicle gates, since rebase hands the donor's
rows back and RemoveReq's pass has to be redone on top. The result is written
into MoreTuning itself, which is why it has to run before RemoveReq, NoLimits
and CarbonParts -- those build on these tables and inherit the merge.

Extract its tables first. repak reads its pak fine as long as the repak used has
oo2core_9_win64.dll beside its own exe, which D:\\MT\\PakMerge\\repak.exe does:

    D:\\MT\\PakMerge\\repak.exe unpack -o <dir> "<...>\\MajasMotorWorksV7.1-7.19_P.pak"

then copy DataAsset/VehicleParts/* into THEIR_TABLES below. No FModel needed --
and do not point FModel at the vanilla export, which it wipes.
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "RemoveReq"))
from pipeline import CURRENT_MAPPINGS, MOD, REPO, TABLE_DIR, WORK, from_json, to_json  # noqa: E402
from rebase import count_live_refs, rebase  # noqa: E402
from run import GATE_ARRAYS, strip_row  # noqa: E402  (RemoveReq)

# Their tables, extracted from their pak. Mirrors the MajasMoWheelWorks layout.
THEIR_TABLES = os.path.join(REPO, "MajasMotorWorksV7.1-7.19_P", "MotorTown", "Content")

# Straight into MoreTuning. There used to be a ZZa_ compat pak for this, but a
# pak mounting after MoreTuning also mounts after xNoLimits and yCarbon and
# would override them -- costing the carbon body parts. Merging in here instead
# means those two are built from the merged tables and inherit the changes.
DEST = MOD

# AeroParts is safe to take now that the merge lands in MoreTuning rather than a
# pak mounting after xNoLimits and yCarbon. Wheels is skipped only because
# MoreTuning does not ship it; the WheelWorks compat pak handles wheels.
TABLES = ["VehicleParts0", "Engines", "Transmissions", "AeroParts", "Wheels"]


def build(name):
    theirs_uasset = os.path.join(THEIR_TABLES, TABLE_DIR, name + ".uasset")
    ours_uasset = os.path.join(MOD, TABLE_DIR, name + ".uasset")
    if not os.path.isfile(theirs_uasset):
        return None
    if not os.path.isfile(ours_uasset):
        print(f"  {name}: MoreTuning does not ship it, nothing to merge")
        return None

    work = os.path.join(WORK, "compat")
    os.makedirs(work, exist_ok=True)
    print(f"\n=== {name} ===")

    theirs = load(to_json(theirs_uasset, os.path.join(work, name + ".theirs.json")))
    ours = load(to_json(ours_uasset, os.path.join(work, name + ".ours.json")))

    # Their rows win where both touch the same part; ours are added on top.
    merged, kept, added = rebase(theirs, ours)
    rows = merged["Exports"][0]["Table"]["Data"]
    stripped = sum(strip_row(row, GATE_ARRAYS) for row in rows)
    print(f"  {kept} of theirs + {added} of ours = {len(rows)} rows, "
          f"{stripped} re-stripped, {count_live_refs(rows)} live refs")

    merged_path = os.path.join(work, name + ".json")
    with open(merged_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=1)

    built = from_json(merged_path, os.path.join(work, name + ".uasset"))
    check = to_json(built, os.path.join(work, name + ".check.json"))
    subprocess.run([sys.executable, os.path.join(HERE, "verify.py"), check,
                    MOD, THEIR_TABLES, r"D:\MT\Output\Exports\MotorTown\Content"], check=True)

    dest = os.path.join(DEST, TABLE_DIR)
    os.makedirs(dest, exist_ok=True)
    for ext in (".uasset", ".uexp"):
        shutil.copy2(os.path.join(work, name + ext), os.path.join(dest, name + ext))
    return len(rows)


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data["Exports"][0]["$type"].startswith("UAssetAPI.ExportTypes.RawExport"):
        sys.exit(f"{path} did not parse as a DataTable -- wrong usmap")
    return data


def main():
    where = os.path.join(THEIR_TABLES, TABLE_DIR)
    missing = (f"extract Motor Works' tables to\n  {where}\n"
               f"with D:\\MT\\PakMerge\\repak.exe, which has oo2core_9_win64.dll "
               f"beside it.")
    if not os.path.isdir(where):
        sys.exit(f"nothing to merge -- {missing}")

    wanted = sys.argv[1:] or TABLES
    done = [n for n in wanted if build(n) is not None]
    if not done:
        sys.exit(f"none of {wanted} found -- {missing}")
    print(f"\n{len(done)} tables merged into MoreTuning: {', '.join(done)}")
    print("Now rerun RemoveReq, RemoveReq --nolimits and CarbonParts, then pack.")


if __name__ == "__main__":
    main()
