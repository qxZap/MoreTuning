"""Move our attachments up the list, to just after the vanilla ones.

    python order.py                       # the headlights
    python order.py Attachment_Foo ...    # or named ones
    python order.py demo

Added rows land at the end of Items_AttachmentPart, which in a list of 600 odd
means nobody scrolls that far. This lifts the named ones to directly after the
last vanilla attachment, so they read as part of the normal catalogue rather
than as an afterthought, and does the same to the vendor's SellItems -- a row
that the vendor does not sell never appears at all, and the order it is sold in
is the order it shows up.

Both paks carry the table and the vendor, and _Premium_P sorts after _P, so
editing only the free one leaves the change invisible wherever both are
installed.
"""
import copy
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from pipeline import WORK, from_json, to_json  # noqa: E402
from reallights import HEADLIGHTS  # noqa: E402

OURS = "/Game/Objects/MoreAttachments/"


def _pak(name, *parts):
    return os.path.join(HERE, "..", name, "MotorTown", "Content", *parts)


PAKS = [(_pak(p, "DataAsset", "Items", "Items_AttachmentPart.uasset"),
         _pak(p, "Characters", "NPC", "Vendor_Garage.uasset"))
        for p in ("qxZap_satigt3_MoreAttachments_P",
                  "qxZap_satigt3_MoreAttachments_Premium_P")]


def is_ours(row):
    for prop in row["Value"]:
        if prop["Name"] == "AttachmentPartActorClass" and isinstance(prop.get("Value"), dict):
            package = prop["Value"]["AssetPath"].get("PackageName") or ""
            return package.startswith(OURS)
    return False


def last_vanilla(rows):
    """Index just past the final row the base game shipped."""
    for index in range(len(rows) - 1, -1, -1):
        if not is_ours(rows[index]):
            return index + 1
    return 0


def reorder(rows, wanted):
    """Lift wanted rows to just after the vanilla block, keeping their order."""
    picked = [r for name in wanted for r in rows if r["Name"] == name]
    if not picked:
        return 0
    for row in picked:
        rows.remove(row)
    at = last_vanilla(rows)
    rows[at:at] = picked
    return at


def resell(vendor, wanted, vanilla_keys):
    """Same idea for the vendor: sold right after the last vanilla item."""
    for export in vendor["Exports"]:
        for entry in export.get("Data") or []:
            if entry["Name"] != "SellItems":
                continue
            items = entry["Value"]
            key = lambda i: i.get("Value") if isinstance(i, dict) else i
            picked = [i for name in wanted for i in items if key(i) == name]
            for item in picked:
                items.remove(item)
            at = 0
            for index, item in enumerate(items):
                if key(item) in vanilla_keys:
                    at = index + 1
            if not picked:                      # never sold before -- add them
                template = items[0]
                picked = []
                for name in wanted:
                    fresh = copy.deepcopy(template)
                    if isinstance(fresh, dict):
                        fresh["Value"] = name
                    else:
                        fresh = name
                    picked.append(fresh)
            items[at:at] = picked
            for index, item in enumerate(items):
                if isinstance(item, dict) and "Name" in item:
                    item["Name"] = str(index)
            return at, len(items)
    return None, None


def build(path, asset, work, tag):
    js = os.path.join(work, tag + ".json")
    with open(js, "w", encoding="utf-8") as f:
        json.dump(asset, f, indent=1)
    built = from_json(js, os.path.join(work, tag + ".uasset"))
    for ext in (".uasset", ".uexp"):
        shutil.copy2(built[: -len(".uasset")] + ext, path.replace(".uasset", ext))


def main(wanted):
    work = os.path.join(WORK, "order")
    os.makedirs(work, exist_ok=True)
    for items_path, vendor_path in PAKS:
        if not os.path.isfile(items_path):
            continue
        tag = items_path.split(os.sep)[-6]
        table = json.load(open(to_json(items_path, os.path.join(work, tag + ".items.raw.json")),
                               encoding="utf-8"))
        rows = table["Exports"][0]["Table"]["Data"]
        vanilla_keys = {r["Name"] for r in rows if not is_ours(r)}
        at = reorder(rows, wanted)
        build(items_path, table, work, tag + "_Items_AttachmentPart")
        print(f"  {tag}: rows at {at} of {len(rows)}", end="")

        vendor = json.load(open(to_json(vendor_path, os.path.join(work, tag + ".vendor.raw.json")),
                                encoding="utf-8"))
        spot, total = resell(vendor, wanted, vanilla_keys)
        build(vendor_path, vendor, work, tag + "_Vendor_Garage")
        print(f", sold at {spot} of {total}")
    print("\nPack both MoreAttachments paks.")


def demo():
    def row(name, ours):
        package = OURS + name if ours else "/Game/Objects/VehicleAttachment/" + name
        return {"Name": name, "Value": [
            {"Name": "AttachmentPartActorClass",
             "Value": {"AssetPath": {"PackageName": package}}}]}

    rows = [row("Van1", False), row("Van2", False), row("Mine1", True),
            row("Head1", True), row("Mine2", True)]
    assert reorder(rows, ["Head1"]) == 2
    assert [r["Name"] for r in rows] == ["Van1", "Van2", "Head1", "Mine1", "Mine2"]
    assert reorder(rows, ["Nope"]) == 0, "unknown names change nothing"

    vendor = {"Exports": [{"Data": [{"Name": "SellItems", "Value": [
        {"Name": "0", "Value": "Van1"}, {"Name": "1", "Value": "Mine1"},
        {"Name": "2", "Value": "Head1"}]}]}]}
    at, total = resell(vendor, ["Head1"], {"Van1", "Van2"})
    sold = [i["Value"] for i in vendor["Exports"][0]["Data"][0]["Value"]]
    assert (at, total) == (1, 3) and sold == ["Van1", "Head1", "Mine1"], sold
    assert [i["Name"] for i in vendor["Exports"][0]["Data"][0]["Value"]] == ["0", "1", "2"]

    missing = {"Exports": [{"Data": [{"Name": "SellItems", "Value": [
        {"Name": "0", "Value": "Van1"}]}]}]}
    resell(missing, ["New1"], {"Van1"})
    assert [i["Value"] for i in missing["Exports"][0]["Data"][0]["Value"]] == ["Van1", "New1"], \
        "an item the vendor never sold has to be added, not silently skipped"
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main(sys.argv[1:] or HEADLIGHTS)
