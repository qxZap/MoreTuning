"""Cooked swim anims -> qxZap_Swim_P, patched to the game's skeleton, then checked.

    python ship.py

1. Copies /Game/Swim/Anims from the cook project. The stand-in skeleton (and its mesh) is never copied: shipping it
   would replace the game's SK_MTCharacter.
2. Every AnimationAsset stores its skeleton's GUID; the stand-in's is swapped for the game's (read off the vanilla
   skeleton) so nothing treats the anims as foreign.
3. A looping montage's section loops when NextSectionName names itself (the one-shots keep None); UE's Python cannot reach CompositeSections, so it is
   set in the cooked montage with UAssetGUI.
4. Reads every shipped asset back (UAssetGUI fails silently, so: output exists, NormalExport, imports point at the
   game's skeleton and ACL settings, the GUID is the game's, montage slot/section as intended).
"""
import base64, json, os, shutil, subprocess, sys

UAG = r"D:\MT\UAssetGUI.exe"
MAP = "MotorTown20261112"
COOKED = r"D:\MT\SwimCook\SwimAnims\Saved\Cooked\Windows\SwimAnims\Content"
VANILLA_SKEL = r"D:\MT\Output\Exports\MotorTown\Content\Characters\Models\Skeletons\SK_MTCharacter.uasset"
OUT = r"D:\MT\MoreTuning\qxZap_Swim_P\MotorTown\Content\Swim\Anims"
WORK = r"D:\MT\SwimCook\ship"
SKEL_PATH = "/Game/Characters/Models/Skeletons/SK_MTCharacter"
KEYS = json.load(open(r"D:\MT\SwimCook\keys.json"))      # swim_anim.py export: names, lengths, which ones loop
ANIMS = list(KEYS)


def tojson(uasset, out):
    if os.path.exists(out): os.remove(out)
    subprocess.run([UAG, "tojson", uasset, out, "VER_UE5_4", MAP])
    if not os.path.exists(out): sys.exit("UAssetGUI could not read " + uasset)
    return json.load(open(out, encoding="utf-8"))


def fromjson(js, uasset):
    for ext in (".uasset", ".uexp"):
        p = uasset[:-7] + ext
        if os.path.exists(p): os.remove(p)
    subprocess.run([UAG, "fromjson", js, uasset, MAP])
    if not os.path.exists(uasset): sys.exit("UAssetGUI could not write " + uasset)


def main():
    os.makedirs(WORK, exist_ok=True)
    sk = tojson(VANILLA_SKEL, os.path.join(WORK, "vanilla_skel.json"))
    sk_extras = base64.b64decode(next(e for e in sk["Exports"] if e["ObjectName"] == "SK_MTCharacter")["Extras"])
    game_guid = sk_extras[-22:-6]           # the skeleton's Guid, followed by 6 trailing bytes (as in vanilla)
    ch = tojson(VANILLA_SKEL.replace(r"Models\Skeletons\SK_MTCharacter", r"Animations\Chicken_Dance"), os.path.join(WORK, "chicken.json"))
    assert base64.b64decode(ch["Exports"][0]["Extras"])[:16] == game_guid, "game skeleton GUID not where expected"

    if os.path.isdir(OUT): shutil.rmtree(OUT)
    os.makedirs(OUT)
    for f in os.listdir(os.path.join(COOKED, "Swim", "Anims")):
        shutil.copy2(os.path.join(COOKED, "Swim", "Anims", f), OUT)

    for a in ANIMS:
        ua = os.path.join(OUT, a + ".uasset")
        d = tojson(ua, os.path.join(WORK, a + ".json"))
        old = base64.b64decode(d["Exports"][0]["Extras"])[:16]
        uexp = ua[:-7] + ".uexp"; b = open(uexp, "rb").read()
        assert b.count(old) == 1, (a, b.count(old))
        open(uexp, "wb").write(b.replace(old, game_guid))

        um = os.path.join(OUT, a + "_Montage.uasset"); js = os.path.join(WORK, a + "_Montage.json")
        m = tojson(um, js)
        e = m["Exports"][0]
        e["Extras"] = base64.b64encode(game_guid).decode()
        sec = next(p for p in e["Data"] if p["Name"] == "CompositeSections")["Value"][0]["Value"]
        if KEYS[a]["loop"]:
            nxt = next(p for p in sec if p["Name"] == "NextSectionName")
            nxt["Value"] = next(p for p in sec if p["Name"] == "SectionName")["Value"]
        json.dump(m, open(js, "w", encoding="utf-8"))
        fromjson(js, um)
    verify(game_guid)


def verify(game_guid):
    for a in ANIMS:
        d = tojson(os.path.join(OUT, a + ".uasset"), os.path.join(WORK, a + ".check.json"))
        e = d["Exports"][0]
        assert "NormalExport" in e["$type"], e["$type"]
        assert base64.b64decode(e["Extras"])[:16] == game_guid, a
        imps = {(i["ObjectName"], i["ClassName"]) for i in d["Imports"]}
        assert (SKEL_PATH, "Package") in imps and ("SK_MTCharacter", "Skeleton") in imps, a
        assert ("/ACLPlugin/ACLAnimBoneCompressionSettings", "Package") in imps, a
        length = next(p["Value"] for p in e["Data"] if p["Name"] == "SequenceLength")

        m = tojson(os.path.join(OUT, a + "_Montage.uasset"), os.path.join(WORK, a + "_Montage.check.json"))
        e = m["Exports"][0]
        assert "NormalExport" in e["$type"] and base64.b64decode(e["Extras"]) == game_guid, a
        props = {p["Name"]: p for p in e["Data"]}
        sec = {p["Name"]: p.get("Value") for p in props["CompositeSections"]["Value"][0]["Value"]}
        slot = {p["Name"]: p.get("Value") for p in props["SlotAnimTracks"]["Value"][0]["Value"]}
        assert sec["SectionName"] == "Default" and sec["NextSectionName"] == ("Default" if KEYS[a]["loop"] else None), sec
        assert slot["SlotName"] == "DefaultSlot", slot
        imps = {(i["ObjectName"], i["ClassName"]) for i in m["Imports"]}
        assert ("/Game/Swim/Anims/" + a, "Package") in imps and (SKEL_PATH, "Package") in imps, a
        print("ok  /Game/Swim/Anims/%s_Montage.%s_Montage  %.2f s, slot DefaultSlot, %s" % (a, a, float(length), "loops" if KEYS[a]["loop"] else "one-shot"))
    print("shipped to", OUT)


if __name__ == "__main__":
    main()
