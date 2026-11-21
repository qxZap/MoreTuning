"""CB Radio's pak (qxZap_CBRadio_P): the handheld radio item, sold at the tech store.

    python CBRadio/build.py          build into qxZap_CBRadio_P
    python CBRadio/build.py demo     self-check

The CB Radio plugin (D:\\MTLiveMap\\mt_loader\\plugins\\cb_radio.cpp) lets you talk on foot only while you hold this
item (MTCharacter.Net_HoldingItem.ItemKey == CB_Handheld). A player's own inventory is not reflected, the item in
the hand is (2026-11-21), so holding it is the check -- and it shows: the character holds a walkie-talkie.

The row is a copy of Text_01_A (the generic holdable, IT_Common_Cargo, which shows the row's StaticMesh) with the
one-hand hold of the Super Flashlight, the game's own walkie-talkie mesh and radio icon. It ships as the mod's own table,
Items_CBRadio, adopted in DataTableFramework/registry.json (the framework lists registered tables, not channels: an
Items/Ch0019 file was never seen in game, 11-21). Vendor_TechStore gets it
appended; no installed mod ships that vendor (Detail Works ships Car Supply, MoreAttachments the Garage).

What a shop sells in game is NOT the vendor blueprint's list: it is baked into RawAssets/ItemSellers_Jeju_World.json
(FMTBakedItemSellerData, one entry per seller with its map location), so the pak ships that file with CB_Handheld added
to every tech store (the sellers that sell Furniture_Laptop_01). Found 11-21 after the item never showed up. The file is
pulled from the installed game's pak, so a game update that rebakes it needs this rerun; no other mod ships it (checked).
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(REPO, "Rebase"))
from pipeline import VANILLA, WORK, from_json, register_names, to_json  # noqa: E402
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("channels", os.path.join(REPO, "Rebase", "channels.py"))
channels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(channels)
framework = channels.framework

PAK = os.path.join(REPO, "qxZap_CBRadio_P", "MotorTown", "Content")
CHANNEL = "/Game/DataAsset/Items/Items_CBRadio"  # adopted by the framework (registry.json); it lists no channels
KEY = "CB_Handheld"
NAME = "Ham Radio"
PRICE = 1500
SCALE = 0.7
PITCH = -90.0  # in the hand, as the flare
# The radio's own hand actor (11-21): the generic one is cargo (MTCargo: it could be set down anywhere, "built") and
# its default model is the letter A, which the preview showed. IT_HamRadio is the tire repair kit's actor -- a plain
# Actor, a root and a mesh -- with the walkie-talkie in it and the hold the user asked for: half as big again, 5 cm
# lower in the palm, tilted 15 degrees.
ACTOR = "/Game/Objects/Item/IT_HamRadio"
ACTOR_SCALE = 1.05      # 0.7 x 1.5
ACTOR_LOCATION = (0.0, 0.0, -5.0)   # cm, along the radio: down into the palm
ACTOR_ROTATION = (0.0, 0.0, 15.0)   # pitch, yaw, roll: the tilt
MESH = "/Game/Models/PolygonPoliceStation/Meshes/Props/SM_Prop_WalkieTalkie_01"
ICON = "/Game/UI/Icons/CBRadio/Ham_Radio"  # our own, drawn in the game's icon style (CBRadio/ham_icon.html -> Ham_Radio.png)
ICON_COOKED = r"D:\MT\SoundCook\MTEngineSounds\Saved\Cooked\Windows\MTEngineSounds\Content\UI\Icons\CBRadio"  # icon_import.py + cook
VENDOR = os.path.join("Characters", "NPC", "Vendor_TechStore.uasset")
TEXT = "UAssetAPI.PropertyTypes.Objects.TextPropertyData"
W = os.path.join(WORK, "cbradio")


def load(path, tag):
    os.makedirs(W, exist_ok=True)
    return json.load(open(to_json(path, os.path.join(W, tag + ".json")), encoding="utf-8"))


def prop(row, name):
    return next(p for p in row["Value"] if p["Name"] == name)


def soft(row, name, package):
    a = prop(row, name)["Value"]["AssetPath"]
    a["PackageName"], a["AssetName"] = package, package.rsplit("/", 1)[1]


def literal(row, text):
    """Every display-name field as a literal: a copied row would read the donor's string table entry."""
    def walk(n):
        if isinstance(n, dict):
            if n.get("$type", "").startswith(TEXT):
                n.update(HistoryType="None", Namespace=None, Value=None, TableId=None, Flags=0, CultureInvariantString=text)
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    for name in ("ItemName", "ItemNameAndNumber", "ItemNameTexts"):
        walk(prop(row, name))


def handheld(items):
    rows = {r["Name"]: r for r in items["Exports"][0]["Table"]["Data"]}
    row = copy.deepcopy(rows["Text_01_A"])
    hold = rows["SuperFlashlight"]  # held like a flashlight: one hand, in the hotbar
    row["Name"] = KEY
    for k in ("HoldableSocketName", "HoldableItemSocketName", "bHoldingOffsetUsingItemBounds", "bUseHandIK",
              "HandIKType", "bUseCargoHoldingPose", "bHoldOnlyItem", "bSpawnActorOnDrop", "bCrosshairModeForDropping"):
        prop(row, k)["Value"] = copy.deepcopy(prop(hold, k)["Value"])
    prop(row, "ItemType")["Value"] = prop(hold, "ItemType")["Value"]  # a tool, not furniture
    prop(row, "bIsPersistence")["Value"] = False
    # the donor's building is the letter A sign: the item's preview showed that, not our mesh (11-22)
    prop(row, "BuildingKey")["Value"] = "None"
    prop(row, "Cost")["Value"] = PRICE
    soft(row, "StaticMesh", MESH)
    h = prop(row, "HoldableActorClass")["Value"]["AssetPath"]
    h["PackageName"], h["AssetName"] = ACTOR, "IT_HamRadio_C"   # our own hand actor (see ACTOR)
    # the donor's look goes: its icon-atlas material painted the radio as the letter A, and its 3x scale made a 39 cm
    # model (antenna up) 1.2 m tall in the hand (11-21). 0.7 = about 27 cm, a real handheld.
    m = prop(row, "Material")["Value"]["AssetPath"]
    m["PackageName"], m["AssetName"] = "None", "None"
    prop(row, "Materials")["Value"] = []
    for v in prop(row, "StaticMeshScale")["Value"]:
        v["Value"].update(X=SCALE, Y=SCALE, Z=SCALE)
    # in the hand (11-21: it lay in the palm, into the sleeve): stood up like the flare (Pitch -90) and held by its
    # middle, not its base (offset by bounds); carried, never dropped or placed -- the generic actor's drop is the
    # furniture placement ("I can build it somewhere")
    hold_rot = copy.deepcopy(prop(rows["Flare_01"], "DefaultHoldingRotation"))
    hold_rot["Value"][0]["Value"].update(Pitch=PITCH, Yaw="+0", Roll="+0")
    row["Value"][[p["Name"] for p in row["Value"]].index("DefaultHoldingRotation")] = hold_rot
    prop(row, "bHoldingOffsetUsingItemBounds")["Value"] = True
    for k in ("bDropable", "bSpawnActorOnDrop", "bCrosshairModeForDropping", "bThrowable"):
        prop(row, k)["Value"] = False
    soft(row, "IconTexture", ICON)
    literal(row, NAME)
    return row


RAW = "MotorTown/Content/RawAssets/ItemSellers_Jeju_World.json"


def sellers():
    """The game's baked shop lists with the handheld at every tech store -> (json text, stores changed)."""
    import subprocess
    sys.path.insert(0, r"D:\MTLiveMap")
    from mt_paths import MT_AES_KEY
    game = r"D:\SteamLibrary\steamapps\common\Motor Town\MotorTown\Content\Paks\MotorTown-Windows.pak"
    raw = subprocess.run([r"D:\MTLiveMap\tools\repak.exe", "--aes-key", MT_AES_KEY, "get", game, RAW],
                         capture_output=True, check=True).stdout
    data = json.loads(raw)
    n = 0
    for sel in data["Sellers"]:
        items = sel.get("sellItems", [])
        if "Furniture_Laptop_01" in items and KEY not in items:
            items.append(KEY)
            n += 1
    return json.dumps(data, indent=2), n


def actor():
    """IT_HamRadio: the repair kit's hand actor, renamed, with the walkie-talkie and its hold. -> its class path."""
    donor = load(os.path.join(VANILLA, "Objects", "Item", "IT_TireRepairKit.uasset"), "IT_TireRepairKit.vanilla")
    flare = load(os.path.join(VANILLA, "Objects", "Item", "IT_Flare.uasset"), "IT_Flare.vanilla")
    items = load(os.path.join(VANILLA, "DataAsset", "Items", "Items.uasset"), "Items.vanilla")
    j = copy.deepcopy(donor)
    old_pkg, new_pkg = "/Game/Objects/Item/IT_TireRepairKit", ACTOR
    old_mesh_pkg = "/Game/Models/PolygonMilitary/Meshes/Characters/Attachments/SM_Chr_Attach_Tool_02"
    ren = {old_pkg: new_pkg, "IT_TireRepairKit_C": "IT_HamRadio_C", "Default__IT_TireRepairKit_C": "Default__IT_HamRadio_C",
           old_mesh_pkg: MESH, "SM_Chr_Attach_Tool_02": MESH.rsplit("/", 1)[1]}
    j["NameMap"] = [ren.get(n, n) for n in j["NameMap"]]
    for imp in j["Imports"]:
        imp["ObjectName"] = ren.get(imp["ObjectName"], imp["ObjectName"])
    for e in j["Exports"]:
        if isinstance(e.get("ObjectName"), str):
            e["ObjectName"] = ren.get(e["ObjectName"], e["ObjectName"])
    if j.get("FolderName") == old_pkg:
        j["FolderName"] = new_pkg
    mesh = next(e for e in j["Exports"] if e.get("ObjectName") == "Mesh_GEN_VARIABLE")
    loc = copy.deepcopy(next(p for e in flare["Exports"] for p in e.get("Data") or []
                             if isinstance(p, dict) and p.get("Name") == "RelativeLocation"))
    loc["Value"][0]["Value"].update(X=ACTOR_LOCATION[0], Y=ACTOR_LOCATION[1], Z=ACTOR_LOCATION[2])
    rot = copy.deepcopy(prop(next(r for r in items["Exports"][0]["Table"]["Data"] if r["Name"] == "Flare_01"), "DefaultHoldingRotation"))
    rot["Name"] = "RelativeRotation"
    rot["Value"][0]["Name"] = "RelativeRotation"
    rot["Value"][0]["Value"].update(Pitch=ACTOR_ROTATION[0], Yaw=ACTOR_ROTATION[1], Roll=ACTOR_ROTATION[2])
    data = [p for p in mesh["Data"] if p.get("Name") not in ("RelativeLocation", "RelativeRotation")]
    at = next(i for i, p in enumerate(data) if p.get("Name") == "RelativeScale3D")
    data[at:at] = [loc, rot]
    for v in data[at + 2]["Value"]:
        v["Value"].update(X=ACTOR_SCALE, Y=ACTOR_SCALE, Z=ACTOR_SCALE)
    mesh["Data"] = data
    register_names(j, ["RelativeLocation", "RelativeRotation", "Vector", "Rotator"])
    src = os.path.join(W, "IT_HamRadio.json")
    json.dump(j, open(src, "w", encoding="utf-8"))
    dst = os.path.join(PAK, "Objects", "Item", "IT_HamRadio.uasset")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    out = from_json(src, dst)
    back = load(out, "IT_HamRadio.check")
    if any("RawExport" in e["$type"] for e in back["Exports"]) or len(back["Exports"]) != len(j["Exports"]):
        sys.exit("FAIL: IT_HamRadio reads back raw")
    m = next(e for e in back["Exports"] if e.get("ObjectName") == "Mesh_GEN_VARIABLE")
    got = {p["Name"]: p for p in m["Data"]}
    assert {"RelativeLocation", "RelativeRotation", "RelativeScale3D"} <= set(got), list(got)
    print(f"  actor: IT_HamRadio, mesh {MESH.rsplit('/', 1)[1]} x{ACTOR_SCALE}, {ACTOR_LOCATION} cm, {ACTOR_ROTATION} deg")
    return ACTOR + ".IT_HamRadio_C"


def icon():
    """The cooked icon into the pak, checked: it reads back as a texture, not raw."""
    import shutil
    dst = os.path.join(PAK, "UI", "Icons", "CBRadio")
    os.makedirs(dst, exist_ok=True)
    for ext in (".uasset", ".uexp"):
        shutil.copy2(os.path.join(ICON_COOKED, "Ham_Radio" + ext), dst)
    back = load(os.path.join(dst, "Ham_Radio.uasset"), "Ham_Radio.check")
    if any("RawExport" in e["$type"] for e in back["Exports"]):
        sys.exit("FAIL: the cooked icon reads back raw")
    print("  icon: Ham_Radio", [e["$type"].split(".")[-1].split(",")[0] for e in back["Exports"]])


def build():
    import shutil
    shutil.rmtree(os.path.join(PAK, "DataTableFramework"), ignore_errors=True)  # the old channel file
    items = load(os.path.join(VANILLA, "DataAsset", "Items", "Items.uasset"), "Items.vanilla")
    row = handheld(items)
    # built on a PLAIN table: Items itself is a CompositeDataTable, and a table made from it was a composite too --
    # it kept no rows of its own, so the game never had the handheld (11-21, the shop check: not in the item list)
    plain = load(os.path.join(VANILLA, "DataAsset", "Items", "Items_Etc.uasset"), "Items_Etc.vanilla")
    table = framework.make_table(plain, CHANNEL, [row])
    cls = table["Imports"][-table["Exports"][0]["ClassIndex"] - 1]["ObjectName"]
    if cls != "DataTable":
        sys.exit(f"FAIL: Items_CBRadio would be a {cls}, not a DataTable")
    icon()
    actor()
    channels.ship(table, CHANNEL, PAK, "CB Radio")

    vendor = load(os.path.join(VANILLA, VENDOR), "Vendor_TechStore.vanilla")
    sell = next(p["Value"] for e in vendor["Exports"] for p in e.get("Data") or []
                if isinstance(p, dict) and p.get("Name") == "SellItems")
    if KEY not in [x["Value"] for x in sell]:
        entry = copy.deepcopy(sell[-1])
        entry["Name"], entry["Value"] = str(len(sell)), KEY
        sell.append(entry)
    register_names(vendor, [KEY])
    src = os.path.join(W, "Vendor_TechStore.json")
    json.dump(vendor, open(src, "w", encoding="utf-8"))
    os.makedirs(os.path.dirname(os.path.join(PAK, VENDOR)), exist_ok=True)
    out = from_json(src, os.path.join(PAK, VENDOR))
    back = load(out, "Vendor_TechStore.check")
    if any("RawExport" in e["$type"] for e in back["Exports"]):
        sys.exit("FAIL: Vendor_TechStore reads back raw")
    print(f"  Vendor_TechStore: {len(sell)} items, the last {sell[-1]['Value']}")
    text, n = sellers()
    if not n:
        sys.exit("FAIL: no tech store in ItemSellers_Jeju_World.json")
    out = os.path.join(PAK, *RAW.split("/")[2:])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(text)
    print(f"  ItemSellers_Jeju_World.json: {KEY} at {n} tech store(s)")


def demo():
    items = load(os.path.join(VANILLA, "DataAsset", "Items", "Items.uasset"), "Items.vanilla")
    row = handheld(items)
    assert row["Name"] == KEY and prop(row, "Cost")["Value"] == PRICE
    assert prop(row, "StaticMesh")["Value"]["AssetPath"]["AssetName"] == "SM_Prop_WalkieTalkie_01"
    assert prop(row, "BuildingKey")["Value"] == "None", "no building: the donor's is the letter A"
    assert prop(row, "HoldableSocketName")["Value"] == "Hand_R_Hold"
    assert prop(row, "Material")["Value"]["AssetPath"]["PackageName"] == "None", "no icon-atlas material"
    assert prop(row, "StaticMeshScale")["Value"][0]["Value"]["X"] == SCALE
    assert prop(row, "DefaultHoldingRotation")["Value"][0]["Value"]["Pitch"] == PITCH and not prop(row, "bDropable")["Value"]
    assert NAME in json.dumps(prop(row, "ItemNameTexts")) and "StringTableEntry" not in json.dumps(prop(row, "ItemNameTexts"))
    assert len([p["Name"] for p in row["Value"]]) == len({p["Name"] for p in row["Value"]}), "a property twice"
    print("ok")


if __name__ == "__main__":
    demo() if sys.argv[1:] == ["demo"] else build()
