"""Suspension Expansion on 0.7.20, as its own table VehicleParts_SuspensionExpansion.

    python SuspensionExpansion/run.py [path\\to\\Z_SuspensionExpansion_P.pak]

The 0.7.18 pak is one whole Suspensions table: vanilla's 52 rows plus 57 of
its own (springs and dampers up to 600, ride height -20..+15, wheel spacers
25..115, angle kits 15..30). A frozen table like that would hide anything
vanilla adds and no longer parses since 0.7.19, so the port ships its own table
(plus its own copy of the VehicleParts composite listing it):

- its 57 rows, rebased onto 0.7.20 (old hard refs become soft paths);
- its balance edits to vanilla's rows -- Cost and MassKg only, e.g. ride height
  at a flat 1000 -- applied onto 0.7.20's own copy of each row. Vanilla had the
  same values in 0.7.19 and 0.7.20, so these are the author's, not drift.
"""
import copy
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(REPO, "Rebase"))
import channels  # noqa: E402
from pipeline import WORK, table_path, to_json  # noqa: E402
from rebase import rebase  # noqa: E402

SOURCE_PAK = r"D:\SteamLibrary\steamapps\common\Motor Town\MotorTown\Content\_disabled_paks\pre_0.7.20\Z_SuspensionExpansion_P.pak"
SOURCE_MAPPINGS = "MotorTown718P1"
BASELINE = os.path.join(REPO, "Rebase", "old", "0.7.19", "vanilla")  # 0.7.19 vanilla, frozen (motorworks.py)
REPAK = r"D:\MT\PakMerge\repak.exe"
DEST = os.path.join(REPO, "Z_SuspensionExpansion_P", "MotorTown", "Content")
TABLE = "/Game/DataAsset/VehicleParts/VehicleParts_SuspensionExpansion"
EDITED = ("Cost", "MassKg")


def value(row, name):
    return next((p.get("Value") for p in row["Value"] if p["Name"] == name), None)


def balance_edits(theirs, before, now):
    """Copies of 0.7.20 rows carrying the mod's Cost/MassKg where it changed 0.7.19's."""
    old = {r["Name"]: r for r in channels.rows_of(before)}
    out = []
    for row in channels.rows_of(now):
        mine, was = theirs.get(row["Name"]), old.get(row["Name"])
        if not mine or not was:
            continue
        changed = [k for k in EDITED if value(mine, k) != value(was, k)]
        if changed:
            row = copy.deepcopy(row)
            for p in row["Value"]:
                if p["Name"] in changed:
                    p["Value"] = value(mine, p["Name"])
            out.append(row)
    return out


def main(argv):
    pak = argv[0] if argv else SOURCE_PAK
    src = os.path.join(WORK, "susp", "src")
    os.makedirs(src, exist_ok=True)
    subprocess.run([REPAK, "unpack", "-q", "-f", "-o", src, pak], check=True)
    content = os.path.join(src, "MotorTown", "Content")
    load = channels.framework.load

    theirs = load(to_json(table_path(content, "Suspensions"),
                          os.path.join(WORK, "susp", "Suspensions.old.json"), SOURCE_MAPPINGS))
    now = channels.vanilla("Suspensions")
    before = load(to_json(table_path(BASELINE, "Suspensions"),
                          os.path.join(WORK, "susp", "Suspensions.vanilla719.json"), "MotorTown719"))
    merged, kept, added = rebase(now, theirs)
    own = channels.rows_of(merged)[kept:]
    edits = balance_edits({r["Name"]: r for r in channels.rows_of(theirs)}, before, now)
    channels.ship_one([(merged, own), (now, edits)], TABLE, DEST, "Suspension Expansion")
    print(f"  {len(own)} new parts + {len(edits)} vanilla rows rebalanced")


def demo():
    row = lambda n, c: {"Name": n, "Value": [{"Name": "Cost", "Value": c}, {"Name": "Tire", "Value": "x"}]}
    t = lambda *rows: {"Exports": [{"Table": {"Data": list(rows)}}]}
    out = balance_edits({"A": row("A", 1000), "B": row("B", 500)},
                        t(row("A", 2000), row("B", 500)), t(row("A", 2500), row("B", 600)))
    assert [r["Name"] for r in out] == ["A"], "only rows the mod changed"
    assert out[0]["Value"] == [{"Name": "Cost", "Value": 1000}, {"Name": "Tire", "Value": "x"}]
    print("ok")


if __name__ == "__main__":
    demo() if sys.argv[1:] == ["demo"] else main(sys.argv[1:])
