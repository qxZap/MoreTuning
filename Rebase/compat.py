"""Merge another mod's part tables with MoreTuning's, into a compat pak.

    python compat.py                 # every table both mods ship
    python compat.py VehicleParts0   # just this one

Maja's Motor Works ships AeroParts, Engines, Transmissions, VehicleParts0 and
Wheels -- the same tables MoreTuning ships. Pak names decide load order and
`qxZap_MoreTuning_P` sorts after `MajasMotorWorks...`, so hers is discarded
wholesale: her added parts (the trailer hitch hook among them) simply vanish,
which is what shows up as winching and towing being broken.

The merge keeps her version of any row both mods touch, then appends the rows
only MoreTuning has, then strips the vehicle gates again -- rebase hands back
the donor's rows, so RemoveReq's work has to be redone on top. The result goes
in a pak that sorts after both.

Her tables have to be extracted first; repak cannot read her pak (Oodle). Export
them with FModel to THEIR_TABLES below -- not into the vanilla export, which
FModel wipes.
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

# Their tables, extracted with FModel. Mirrors the MajasMoWheelWorks layout.
THEIR_TABLES = os.path.join(REPO, "MajasMotorWorksV7.1-7.19_P", "MotorTown", "Content")
COMPAT = os.path.join(REPO, "ZZa_MajaMotorWorks_qxZap_MoreTuning_P", "MotorTown", "Content")

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

    dest = os.path.join(COMPAT, TABLE_DIR)
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
    if not os.path.isdir(os.path.join(THEIR_TABLES, TABLE_DIR)):
        sys.exit(f"nothing to merge -- extract their tables to\n  "
                 f"{os.path.join(THEIR_TABLES, TABLE_DIR)}\n"
                 f"with FModel (repak cannot read their pak: Oodle).")

    wanted = sys.argv[1:] or TABLES
    done = [n for n in wanted if build(n) is not None]
    if not done:
        sys.exit(f"none of {wanted} found in\n  "
                 f"{os.path.join(THEIR_TABLES, TABLE_DIR)}\n"
                 f"Extract their .uasset/.uexp there with FModel first "
                 f"(repak cannot read their pak: Oodle).")
    print(f"\n{len(done)} tables merged into {os.path.relpath(COMPAT, REPO)}: "
          f"{', '.join(done)}")
    print("Pack with: modp.bat ZZa_MajaMotorWorks_qxZap_MoreTuning_P")


if __name__ == "__main__":
    main()
