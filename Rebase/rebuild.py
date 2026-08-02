"""Rebase MoreTuning's part tables onto the current vanilla ones.

    python rebuild.py                 # every table in TABLES
    python rebuild.py Engines LSD     # just these

For each table: read vanilla with the new usmap, read the mod's own copy with
the usmap it was last built against, keep vanilla's version of shared rows, and
carry the mod-only rows across -- converting any reference the game has since
turned into a soft path. Then build, read back, check, and install.

After a game update: export the new build, drop its usmap in
%LOCALAPPDATA%\\UAssetGUI\\Mappings, set CURRENT_MAPPINGS to it and
PREVIOUS_MAPPINGS to whatever the mod folder currently holds, and run this.

Because vanilla wins on shared rows, this puts back any restriction RemoveReq
stripped -- rerun RemoveReq (and CarbonParts) afterwards.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pipeline import (CURRENT_MAPPINGS, MOD, TABLE_DIR, VANILLA, WORK,  # noqa: E402
                      from_json, table_path, to_json)

# The usmap the tables sitting in the mod folder were built with. Equal to
# CURRENT_MAPPINGS between game updates; bump it as part of doing an update.
PREVIOUS_MAPPINGS = "MotorTown719"

TABLES = ["Engines", "Transmissions", "LSD", "AeroParts", "VehicleParts0"]

# Snapshots of the pre-0.7.19 tables, kept in Rebase/old/ as JSON in case a row
# ever needs recovering. Not part of the build.


def build(name):
    print(f"\n=== {name} ===")
    os.makedirs(WORK, exist_ok=True)

    vanilla_json = to_json(table_path(VANILLA, name),
                           os.path.join(WORK, name + ".vanilla.json"), CURRENT_MAPPINGS)
    mod_json = to_json(table_path(MOD, name),
                       os.path.join(WORK, name + ".old.json"), PREVIOUS_MAPPINGS)

    merged = os.path.join(WORK, name + ".json")
    subprocess.run([sys.executable, os.path.join(HERE, "rebase.py"), vanilla_json, mod_json, merged],
                   check=True)

    built = from_json(merged, os.path.join(WORK, name + ".uasset"))
    check = to_json(built, os.path.join(WORK, name + ".check.json"), CURRENT_MAPPINGS)
    subprocess.run([sys.executable, os.path.join(HERE, "verify.py"), check, MOD, VANILLA],
                   check=True)

    import shutil
    for ext in (".uasset", ".uexp"):
        shutil.copy2(os.path.join(WORK, name + ext),
                     os.path.join(MOD, TABLE_DIR, name + ext))
    print(f"  -> {os.path.join(TABLE_DIR, name)}.uasset/.uexp")


def main():
    wanted = sys.argv[1:] or TABLES
    unknown = [n for n in wanted if n not in TABLES]
    if unknown:
        sys.exit(f"unknown table(s): {unknown}\nknown: {TABLES}")
    for name in wanted:
        build(name)
    print("\nRebased. Now rerun RemoveReq/run.py and CarbonParts/run.py, "
          "then pack with: modp.bat qxZap_MoreTuning_P")


if __name__ == "__main__":
    main()
