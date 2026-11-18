"""The framework's GameResource and Decals composite: rtwin's slot decals, and the one GameResource every mod can share.

Vanilla Decals (/Game/DataAsset/Decals) is a plain DataTable, so nothing can add rows to it the way the framework adds
mod tables to the 14 composites. GameResource names the table the game reads; the framework's copy points Decals at
/Game/DataTableFramework/Decals/Decals, a composite of vanilla Decals and rtwin's Slot01..32 DT_Decals (registry
"reserved" style: listed, not stubbed -- a missing parent is skipped).

The framework's GameResource is vanilla's with only that redirect: its world map stays vanilla. (18-19 Nov it carried
Arini's world map bounds, and every player without the Arini Map saw the roads shifted on the map -- the 19 Nov report.)
Arini's bounds (DriveMaps[0].WorldMap WorldMapLocation and WorldMapSize, from Arini's patch file, which worldmap_align.py
rewrites on every map build, else from the installed qxZap_Arini_P.pak) go into the Arini Map's own override pak,
ARINI_OVERRIDE: the framework's GameResource plus those bounds, chunk 100 so it outranks the framework's 99.

    python DataTableFramework/gameresource.py          python DataTableFramework/gameresource.py demo
"""
import copy
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run  # noqa: E402
from run import MOD, WORK, add_import, imp, load, props, save, add_parents  # noqa: E402
from pipeline import VANILLA, from_json, register_names, to_json  # noqa: E402

DECALS = "/Game/DataTableFramework/Decals/Decals"
SLOTS = 32
TEMPLATE_COMPOSITE = "Buffs"  # a small vanilla composite to build the Decals composite on
ARINI_PATCH = r"D:\MTLiveMap\dtf_patches\gameresource_worldmap.json"
ARINI_PAK = r"D:\SteamLibrary\steamapps\common\Motor Town\MotorTown\Content\Paks\qxZap_Arini_P.pak"  # renamed from Arini_P.pak, 18 Nov
REPAK = r"D:\MT\PakMerge\repak.exe"
ARINI_OVERRIDE = os.path.join(os.path.dirname(HERE), "qxZap_Arini_WorldMap_100_P")  # mounts above AAAA_DataTableFramework_99_P


def prop(data, name):
    return next(p for p in data if p.get("Name") == name)


def worldmap(gr):
    """DriveMaps[0].WorldMap's property list."""
    maps = prop(gr["Exports"][0]["Data"], "DriveMaps")["Value"]
    return prop(maps[0]["Value"], "WorldMap")["Value"]


def arini_worldmap():
    """Arini's WorldMapLocation and WorldMapSize properties: their patch file, else the installed qxZap_Arini_P.pak."""
    if os.path.isfile(ARINI_PATCH):
        return json.load(open(ARINI_PATCH, encoding="utf-8")), ARINI_PATCH
    if not os.path.isfile(ARINI_PAK):
        sys.exit(f"FAIL: no Arini world map: neither {ARINI_PATCH} nor {ARINI_PAK}")
    with tempfile.TemporaryDirectory() as t:
        subprocess.run([REPAK, "unpack", "-i", "MotorTown/Content/DataAsset/GameResource.*", "-o", t, ARINI_PAK],
                       check=True, capture_output=True)
        src = os.path.join(t, "MotorTown", "Content", "DataAsset", "GameResource.uasset")
        gr = load(to_json(src, os.path.join(WORK, "arini_gameresource.json")))
    wm = worldmap(gr)
    return {p["Name"]: p for p in wm if p["Name"] in ("WorldMapLocation", "WorldMapSize")}, ARINI_PAK


def patch_worldmap(gr, values):
    wm = worldmap(gr)
    for i, p in enumerate(wm):
        if p["Name"] in values:
            v = values[p["Name"]]
            if isinstance(v, dict) and "$type" in v:  # a whole property, copied from Arini's GameResource
                wm[i] = copy.deepcopy(v)
            elif isinstance(v, dict):  # {"X":..,"Y":..} from the patch file
                vec = p["Value"][0]["Value"] if isinstance(p["Value"], list) else p["Value"]  # struct -> its vector
                for k, x in v.items():
                    vec[k] = x
            else:
                p["Value"] = v
    missing = {"WorldMapLocation", "WorldMapSize"} - {p["Name"] for p in wm}
    assert not missing, missing


def redirect_decals(gr):
    """Point GameResource's Decals at the framework's composite (the import and its package)."""
    e = gr["Exports"][0]
    i = prop(e["Data"], "Decals")["Value"]
    obj = gr["Imports"][-i - 1]
    pkg = gr["Imports"][-obj["OuterIndex"] - 1]
    assert pkg["ObjectName"] == "/Game/DataAsset/Decals" and obj["ClassName"] == "DataTable", (pkg, obj)
    pkg["ObjectName"], obj["ObjectName"], obj["ClassName"] = DECALS, DECALS.rsplit("/", 1)[1], "CompositeDataTable"
    register_names(gr, [DECALS, "CompositeDataTable"])
    gr["Generations"][0]["NameCount"] = len(gr["NameMap"])


def decals_composite():
    """A composite with vanilla Decals' row struct, no rows of its own (the game rebuilds a composite from its
    parents on load -- how every framework parent's rows reach the game), parents vanilla Decals + the slots."""
    van = load(to_json(os.path.join(VANILLA, "DataAsset", "Decals.uasset"), os.path.join(WORK, "Decals.vanilla.json")))
    struct = imp(van, props(van["Exports"][0])["RowStruct"]["Value"])
    table, _ = run.composite(TEMPLATE_COMPOSITE)
    table = copy.deepcopy(table)
    e = table["Exports"][0]
    rs = props(e)["RowStruct"]
    old = table["Imports"][-rs["Value"] - 1]
    old["ObjectName"] = struct["ObjectName"]  # same class (ScriptStruct) and package (/Script/MotorTown)
    assert table["Imports"][-old["OuterIndex"] - 1]["ObjectName"] == imp(van, struct["OuterIndex"])["ObjectName"]
    e["Table"]["Data"] = []
    # parents: replace the template's with vanilla Decals, then the slots
    plist = props(e)["ParentTables"]["Value"]
    first = table["Imports"][-plist[0]["Value"] - 1]
    table["Imports"][-first["OuterIndex"] - 1]["ObjectName"] = "/Game/DataAsset/Decals"
    first["ObjectName"], first["ClassName"] = "Decals", "DataTable"
    del plist[1:]
    add_parents(table, [f"/Game/ReservedRegistration/Slots/Slot{i:02d}/DT_Decals" for i in range(1, SLOTS + 1)])
    name = DECALS.rsplit("/", 1)[1]
    table["FolderName"] = DECALS
    e["ObjectName"] = name
    register_names(table, [DECALS, name, struct["ObjectName"], "/Game/DataAsset/Decals", "Decals", "DataTable"])
    table["Generations"][0]["NameCount"] = len(table["NameMap"])
    return table, struct["ObjectName"]


def write(table, package, tag):
    src = os.path.join(WORK, f"{tag}.json")
    save(table, src)
    out = os.path.join(MOD, *package[len("/Game/"):].split("/")) + ".uasset"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    built = from_json(src, out)
    return load(to_json(built, os.path.join(WORK, f"{tag}.check.json")))


def main():
    os.makedirs(WORK, exist_ok=True)
    table, struct = decals_composite()
    back = write(table, DECALS, "Decals.framework")
    assert run.is_composite(back) and run.parents(back)[0] == "/Game/DataAsset/Decals" and len(run.parents(back)) == SLOTS + 1, run.parents(back)[:3]
    print(f"  Decals composite: {struct}, vanilla Decals + {SLOTS} slots")
    vanilla = load(to_json(os.path.join(VANILLA, "DataAsset", "GameResource.uasset"), os.path.join(WORK, "GameResource.vanilla.json")))
    plain = {p["Name"]: p.get("Value") for p in worldmap(vanilla) if p["Name"] in ("WorldMapLocation", "WorldMapSize")}
    gr = copy.deepcopy(vanilla)
    redirect_decals(gr)
    back = write(gr, "/Game/DataAsset/GameResource", "GameResource.framework")
    check(back)
    got = {p["Name"]: p.get("Value") for p in worldmap(back) if p["Name"] in ("WorldMapLocation", "WorldMapSize")}
    assert json.dumps(got, default=str) == json.dumps(plain, default=str), "the framework's world map must stay vanilla"
    print(f"  GameResource: Decals -> {DECALS}; world map vanilla")
    # Arini Map's override: the same GameResource with Arini's bounds
    values, src = arini_worldmap()
    gr = copy.deepcopy(vanilla)
    patch_worldmap(gr, values)
    redirect_decals(gr)
    save(gr, os.path.join(WORK, "GameResource.arini.json"))
    out = os.path.join(ARINI_OVERRIDE, "MotorTown", "Content", "DataAsset", "GameResource.uasset")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    back = load(to_json(from_json(os.path.join(WORK, "GameResource.arini.json"), out), os.path.join(WORK, "GameResource.arini.check.json")))
    check(back)
    got = {p["Name"]: p.get("Value") for p in worldmap(back) if p["Name"] in ("WorldMapLocation", "WorldMapSize")}
    assert json.dumps(got, default=str) != json.dumps(plain, default=str), "Arini's override carries vanilla bounds"
    if os.path.exists(ARINI_OVERRIDE + ".pak"):
        os.remove(ARINI_OVERRIDE + ".pak")  # repak does not overwrite
    subprocess.run([REPAK, "pack", ARINI_OVERRIDE, ARINI_OVERRIDE + ".pak"], check=True, stdout=subprocess.DEVNULL)
    print(f"  Arini override {os.path.basename(ARINI_OVERRIDE)}.pak: world map from {os.path.basename(src)}")


def check(back):
    assert back["Exports"][0]["$type"].startswith("UAssetAPI.ExportTypes.NormalExport"), back["Exports"][0]["$type"]
    d = prop(back["Exports"][0]["Data"], "Decals")["Value"]
    assert back["Imports"][-d - 1]["ClassName"] == "CompositeDataTable"


if __name__ == "__main__":
    if sys.argv[1:] == ["demo"]:
        gr = {"Imports": [{"ObjectName": "/Game/DataAsset/Decals", "OuterIndex": 0, "ClassName": "Package"},
                          {"ObjectName": "Decals", "OuterIndex": -1, "ClassName": "DataTable"}],
              "NameMap": [], "NamesReferencedFromExportDataCount": 0, "Generations": [{"NameCount": 0}],
              "Exports": [{"Data": [{"Name": "Decals", "Value": -2}]}]}
        redirect_decals(gr)
        assert gr["Imports"][0]["ObjectName"] == DECALS and gr["Imports"][1]["ClassName"] == "CompositeDataTable"
        print("demo ok")
    else:
        main()
