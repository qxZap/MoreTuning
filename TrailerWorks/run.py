"""MoreTuning requires Maja's Trailer Works: her parts are hers, not copies in our table.

    python TrailerWorks/run.py         # drop her rows and the hitch mesh from MoreTuning (rerunnable)
    python TrailerWorks/run.py demo    # self-check

MoreTuning used to carry Maja's Motor Works rows (the hitch hook, the MMW winches, TaxiLicense2)
and the hitch mesh, because Motor Works' 0.7.19 tables lost to ours. Trailer Works V8 (0.7.20)
ships the same rows in her own VehicleParts0, and our adopted table outranks a vanilla parent, so
our frozen copies would hide every update she makes. With Trailer Works required, they go.

What stays: our copies of *vanilla* rows (hitches, winches, tyres...). They carry the gate
stripping MoreTuning does to every vanilla row, and on 2026-11-18 their values matched hers
(winch lengths included) apart from the gates and her display names.

Run it last, after everything else that writes VehicleParts_MoreTuning (channels.py, NewEngines,
MarineParts, FuelRealism, EngineTags): channels.py puts the rows back.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from pipeline import MOD, build_table  # noqa: E402

TABLE = "VehicleParts_MoreTuning"
# rows Trailer Works V8 adds to VehicleParts0 that MoreTuning also defined
THEIRS = {"TrailerHitch_Hook", "Winch_06_MMW", "Winch_Tow_05_MMW", "Winch_Tow_06_MMW",
          "Winch_Tow_07_MMW", "Winch_Tow_08_MMW", "TaxiLicense2"}
MESH_DIR = os.path.join(MOD, "Cars", "Parts", "TrailerHitch")   # TrailerHitch_Hook: her pak ships it


def keep(rows):
    return [r for r in rows if r["Name"] not in THEIRS]


def demo():
    rows = [{"Name": n} for n in ("TrailerHitch_Hook", "Winch_01", "Winch_06_MMW", "C0001_BBK320")]
    assert [r["Name"] for r in keep(rows)] == ["Winch_01", "C0001_BBK320"]
    print("ok")


def main():
    if os.path.isdir(MESH_DIR):
        shutil.rmtree(MESH_DIR)
        print("removed", MESH_DIR)
    dropped = []

    def transform(rows, table):
        out = keep(rows)
        dropped.extend(sorted({r["Name"] for r in rows} - {r["Name"] for r in out}))
        return out

    build_table(TABLE, transform)
    print(f"  dropped {len(dropped)} rows Trailer Works owns: {', '.join(dropped) or 'none (already done)'}")


if __name__ == "__main__":
    demo() if sys.argv[1:] == ["demo"] else main()
