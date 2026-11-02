"""AMC Tires on the current game, as its own table VehicleParts_AMCTires.

    python AmcTires/run.py <path\\to\\ZZZZZ_AMC_Tires_V3_7.19_PDPartsCombined_P.pak>
    python AmcTires/run.py demo

AMC's 0.7.19 paks each replace VehicleParts0 whole, with other mods' rows folded in:
three paks for three mod combinations. All three hold the same 21 AMC rows and AMC_*
tire assets, so the port ships those alone, in a table the framework lists
(registry.json "adopted"). Nothing is left to combine, and any mod can sit beside it.

Left out on purpose: PD Parts' rows and APF_* assets, Motor Works' rows, and the
gate-stripped copies of vanilla rows. Those belong to their own mods.

Then run reserialize.py over the folder for class layout shifts, and
DataTableFramework/run.py so the composite lists the table.
"""
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(REPO, "Rebase"))
import channels  # noqa: E402
from pipeline import WORK, table_path, to_json  # noqa: E402
from rebase import rebase  # noqa: E402

SOURCE_MAPPINGS = "MotorTown719"
REPAK = r"D:\MT\PakMerge\repak.exe"
MOD = "ZZZZZ_AMC_Tires_V3.4_7.20_P"
DEST = os.path.join(REPO, MOD, "MotorTown", "Content")
TABLE = "/Game/DataAsset/VehicleParts/VehicleParts_AMCTires"


def ours(rows):
    return [r for r in rows if r["Name"].startswith("AMC_")]


def main(argv):
    work = os.path.join(WORK, "amc_port")
    shutil.rmtree(work, ignore_errors=True)
    src = os.path.join(work, "src")
    os.makedirs(src)
    subprocess.run([REPAK, "unpack", "-q", "-f", "-o", src, argv[0]], check=True)
    content = os.path.join(src, "MotorTown", "Content")

    theirs = channels.framework.load(to_json(table_path(content, "VehicleParts0"), os.path.join(work, "theirs.json"), SOURCE_MAPPINGS))
    now = channels.vanilla("VehicleParts0")
    merged, kept, _ = rebase(now, theirs)
    rows = ours(channels.rows_of(merged)[kept:])
    if len(rows) != 21:
        sys.exit(f"FAIL: expected AMC's 21 rows, found {len(rows)}")
    channels.ship_one([(merged, rows)], TABLE, DEST, "AMC Tires")

    tires = os.path.join(DEST, "Cars", "Parts", "Tire")
    os.makedirs(tires, exist_ok=True)
    assets = glob.glob(os.path.join(content, "Cars", "Parts", "Tire", "AMC_*"))
    for f in assets:
        shutil.copy2(f, tires)
    print(f"  {len(rows)} rows, {len(assets)} tire files")


def demo():
    assert [r["Name"] for r in ours([{"Name": "AMC_Bike_16"}, {"Name": "APF_78A"}, {"Name": "201"}])] == ["AMC_Bike_16"]
    print("ok")


if __name__ == "__main__":
    demo() if sys.argv[1:] == ["demo"] else main(sys.argv[1:])
