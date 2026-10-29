"""Teh's Engine Sound Pack on 0.7.20, as DataTableFramework channel Ch0004.

    python TehEngines/run.py [path\\to\\Z_TehsEngineSoundPack_P.pak]

His pak is 16 new engines (part assets, torque curves, sounds) plus a whole
Engines table -- a frozen 0.7.18 copy of vanilla's 36 rows with his 16 on top.
That copy is what broke: 0.7.19 changed the row format, and it would also hide
every engine vanilla has added since. So the assets are carried over untouched
(re-serialized where a class layout moved -- Rebase/reserialize.py) and only his 16 rows ship, rebased
onto 0.7.20, in his own channel.

The table was built with a 0.7.18 usmap; MotorTown718P1 is the newest that
parses it (0.7.19's reads it as a RawExport).
"""
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

SOURCE_PAK = r"E:\MT\0.7.18NOW\Z_TehsEngineSoundPack_P.pak"
SOURCE_MAPPINGS = "MotorTown718P1"
REPAK = r"D:\MT\PakMerge\repak.exe"  # his pak is Oodle-compressed
DEST = os.path.join(REPO, "Z_TehsEngineSoundPack_P", "MotorTown", "Content")
CHANNEL = 4


def main(argv):
    pak = argv[0] if argv else SOURCE_PAK
    src = os.path.join(WORK, "teh", "src")
    shutil.rmtree(src, ignore_errors=True)
    subprocess.run([REPAK, "unpack", "-q", "-f", "-o", src, pak], check=True)
    content = os.path.join(src, "MotorTown", "Content")

    theirs = channels.framework.load(to_json(table_path(content, "Engines"),
                                             os.path.join(WORK, "teh", "Engines.old.json"),
                                             SOURCE_MAPPINGS))
    merged, kept, added = rebase(channels.vanilla("Engines"), theirs)
    rows = channels.rows_of(merged)[kept:]

    shutil.rmtree(os.path.join(REPO, "Z_TehsEngineSoundPack_P"), ignore_errors=True)
    shutil.copytree(os.path.join(content, "Cars"), os.path.join(DEST, "Cars"))
    # His assets were cooked against 0.7.18; re-cook any whose class layout moved.
    subprocess.run([sys.executable, os.path.join(REPO, "Rebase", "reserialize.py"),
                    SOURCE_MAPPINGS, DEST], check=True)
    channels.ship(channels.framework.make_channel(merged, channels.COMP, CHANNEL, rows),
                  CHANNEL, DEST, "Teh's engines")
    dropped = len(channels.rows_of(theirs)) - added
    print(f"  {added} engines; his {dropped} copies of vanilla rows dropped -- vanilla's own load")


if __name__ == "__main__":
    main(sys.argv[1:])
