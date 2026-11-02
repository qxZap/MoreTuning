"""Player downloads: one zip per mod, laid out to drop onto the game folder.

    python release.py          # -> dist\*.zip, from the .pak files built at the repo root

Steam's Manage > Browse local files opens the game root (...\\common\\Motor Town).
Each zip holds MotorTown\\Content\\Paks\\<paks> from that root, so installing is:
open that folder, drag the zip's MotorTown folder in, choose Replace.

Every zip carries the DataTableFramework pak too. Each mod works alone (it ships
its own composite copy), but two mods on the same table knock each other's copies
out without it -- and asking players to install a compat pack themselves is one
thing too many. Copies of it are identical, so overwriting one with another is
harmless.
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist")
FRAMEWORK = "AAAA_DataTableFramework_99_P.pak"
PAKS = "MotorTown/Content/Paks/"

RELEASES = {
    "DataTableFramework": [],
    "MoreTuning": ["qxZap_MoreTuning_P.pak"],
    "MoreTuning_NoLimits": ["qxZap_MoreTuning_P.pak", "qxZap_MoreTuning_xNoLimits_P.pak"],
    "MoreTuning_Carbon": ["qxZap_MoreTuning_P.pak", "qxZap_MoreTuning_yCarbon_P.pak"],
    "MoreAttachments": ["qxZap_satigt3_MoreAttachments_P.pak"],
    "MoreAttachments_Premium": ["qxZap_satigt3_MoreAttachments_P.pak",
                                "qxZap_satigt3_MoreAttachments_Premium_P.pak"],
    "TehsEngineSoundPack": ["Z_TehsEngineSoundPack_P.pak"],
    "SuspensionExpansion": ["Z_SuspensionExpansion_P.pak"],
}

INSTALL = """HOW TO INSTALL ({name})

1. In Steam, right-click Motor Town > Manage > Browse local files.
   A folder opens (it ends in ...\\common\\Motor Town).
2. Drag the MotorTown folder from this zip into that window.
3. If Windows asks, choose "Replace the files in the destination".

That's it. To uninstall, delete these files from MotorTown\\Content\\Paks:
{files}
(Keep {framework} if any other mod you use needs it.)
"""


def build(name, paks):
    files = [FRAMEWORK] + paks
    missing = [f for f in files if not os.path.isfile(os.path.join(HERE, f))]
    if missing:
        sys.exit(f"{name}: build these first: {missing}")
    out = os.path.join(DIST, name + ".zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(HERE, f), PAKS + f)
        z.writestr("HOW_TO_INSTALL.txt", INSTALL.format(
            name=name, framework=FRAMEWORK, files="\n".join("  " + f for f in files)))
    return out


def demo():
    with zipfile.ZipFile(build("DataTableFramework", [])) as z:
        names = z.namelist()
    assert names[0] == PAKS + FRAMEWORK, names
    assert "HOW_TO_INSTALL.txt" in names
    print("ok")


if __name__ == "__main__":
    os.makedirs(DIST, exist_ok=True)
    if sys.argv[1:] == ["demo"]:
        demo()
    else:
        for name, paks in RELEASES.items():
            out = build(name, paks)
            print(f"  {os.path.basename(out):32} {os.path.getsize(out) // 1024:>7} KB")
