"""Lab: Items channel Ch0050 -- the item rows of the lab parts, each with one
color+metallic+roughness paint slot (the vanilla antenna's) on its painted mesh
slot. Overrides MoreAttachments' Ch0001 rows for those parts. A clone of Ch0001
cut down to those rows, so its NameMap/Imports already hold everything; the only
new FName is a mesh slot name ("Palette").

Proven in game on 0.7.20 -- the recipe to fold into MoreAttachments/channel.py.
Run after paint_and_lamps.py and light_sections.py, then modp.bat zzLab_DuroPaint_P.
"""
import copy, json, os, subprocess

SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Rebase", "work", "lab")
os.makedirs(SP, exist_ok=True)
UAG = r"D:\MT\UAssetGUI.exe"
CH0001 = r"D:\MT\MoreTuning\qxZap_satigt3_MoreAttachments_P\MotorTown\Content\DataTableFramework\Items\Ch0001.uasset"
SRC = os.path.join(SP, "ma_ch0001.json")
LABROOT = r"D:\MT\MoreTuning\zzLab_DuroPaint_P\MotorTown\Content\DataTableFramework\Items"
OUT_JSON = os.path.join(SP, "Ch0050.json")
OUT_UASSET = os.path.join(LABROOT, "Ch0050.uasset")

subprocess.run([UAG, "tojson", CH0001, SRC, "VER_UE5_4", "MotorTown720T1"], check=True)
t = json.load(open(SRC, encoding="utf-8"))
dt = t["Exports"][0]
rows = dt["Table"]["Data"]

# the proven working slot from the antenna (color + metallic + roughness)
antenna = next(r for r in rows if r["Name"] == "Attachment_Antenna_01")
tmpl = next(p for p in antenna["Value"] if p["Name"] == "AttachmentPaintSlots")["Value"]

# painted slot per part: the Duro copies paint "Palette" (swapped to M_Gray),
# the Zydro rear bumpers their own M_Body "Body_01"
PAINT_SLOT = {"Duro_FrontBumper": "Palette", "Zydro_RearBumper": "Body_01"}
duro = [r for r in rows if any(k in r["Name"] for k in PAINT_SLOT)]
assert len(duro) == 7, [r["Name"] for r in duro]
for r in duro:
    slot = copy.deepcopy(tmpl)
    msn = next(p for p in slot[0]["Value"] if p["Name"] == "MaterialSlotName")
    msn["Value"] = next(v for k, v in PAINT_SLOT.items() if k in r["Name"])
    ap = next(p for p in r["Value"] if p["Name"] == "AttachmentPaintSlots")
    ap["Value"] = slot

dt["Table"]["Data"] = duro                       # ship only the 4 probe rows
if "Palette" not in t["NameMap"]:
    t["NameMap"].append("Palette")
t["NameMap"] = ["Ch0050" if n == "Ch0001" else n for n in t["NameMap"]]
dt["ObjectName"] = "Ch0050"

json.dump(t, open(OUT_JSON, "w", encoding="utf-8"), indent=1)
os.makedirs(LABROOT, exist_ok=True)
subprocess.run([UAG, "fromjson", OUT_JSON, OUT_UASSET, "MotorTown720T1"], check=True)
assert os.path.isfile(OUT_UASSET), "UAssetGUI wrote nothing"

# read back: must be a DataTableExport, not RawExport
chk = os.path.join(SP, "Ch0050.check.json")
subprocess.run([UAG, "tojson", OUT_UASSET, chk, "VER_UE5_4", "MotorTown720T1"], check=True)
back = json.load(open(chk, encoding="utf-8"))
e = back["Exports"][0]
assert "DataTableExport" in e["$type"], "RawExport -- parse failed"
got = back["Exports"][0]["Table"]["Data"]
assert len(got) == 7 and e["ObjectName"] == "Ch0050"
for r in got:
    v = next(p for p in r["Value"] if p["Name"] == "AttachmentPaintSlots")["Value"]
    msn = next(p for p in v[0]["Value"] if p["Name"] == "MaterialSlotName")["Value"]
    assert msn == next(v for k, v in PAINT_SLOT.items() if k in r["Name"]), (r["Name"], msn)
print("OK: Ch0050 built,", [(r["Name"], ) for r in got], "->", OUT_UASSET)
