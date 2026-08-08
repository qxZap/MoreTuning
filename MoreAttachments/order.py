"""Put named attachments at the front of the list, so they can be found.

    python order.py                       # the lamps
    python order.py Attachment_Foo ...    # or named ones
    python order.py demo

This is safe, and the reason is worth stating because an earlier version of this
file was deleted for being unsafe. Attachment rows carry no numeric id -- the
DataTable row name is the key, and that is what a save stores. Adding rows in an
update therefore does not disturb anyone's build, and neither does moving one.
Verified across every commit that touched the table: no row has ever been renamed
or removed here, which is the operation that would actually break a vehicle.

Both the table and the vendor's SellItems are reordered. The vendor is the one
that decides what shows up at all -- a row it does not sell never appears.

Both paks carry both files, and _Premium_P sorts after _P, so editing only the
free one leaves the change invisible wherever both are installed.
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


def _pak(name, *parts):
    return os.path.join(HERE, "..", name, "MotorTown", "Content", *parts)


PAKS = [(_pak(p, "DataAsset", "Items", "Items_AttachmentPart.uasset"),
         _pak(p, "Characters", "NPC", "Vendor_Garage.uasset"))
        for p in ("qxZap_satigt3_MoreAttachments_P",
                  "qxZap_satigt3_MoreAttachments_Premium_P")]


def to_front(items, wanted, key=lambda i: i):
    """Move the wanted entries to the front, keeping their given order."""
    picked = [i for name in wanted for i in items if key(i) == name]
    for item in picked:
        items.remove(item)
    items[:0] = picked
    return len(picked)


def reorder(rows, wanted):
    return to_front(rows, wanted, key=lambda r: r["Name"])


def resell(vendor, wanted):
    """Same for the vendor, adding anything it was not selling yet."""
    for export in vendor["Exports"]:
        for entry in export.get("Data") or []:
            if entry["Name"] != "SellItems":
                continue
            items = entry["Value"]
            key = lambda i: i.get("Value") if isinstance(i, dict) else i
            for name in wanted:
                if not any(key(i) == name for i in items):
                    fresh = copy.deepcopy(items[0])
                    if isinstance(fresh, dict):
                        fresh["Value"] = name
                    else:
                        fresh = name
                    items.append(fresh)
            moved = to_front(items, wanted, key=key)
            for index, item in enumerate(items):
                if isinstance(item, dict) and "Name" in item:
                    item["Name"] = str(index)
            return moved, len(items)
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
        rows = next(e["Table"]["Data"] for e in table["Exports"] if e.get("Table"))
        moved = reorder(rows, wanted)
        build(items_path, table, work, tag + "_Items_AttachmentPart")
        print(f"  {tag}: {moved} rows first of {len(rows)}", end="")

        vendor = json.load(open(to_json(vendor_path, os.path.join(work, tag + ".vendor.raw.json")),
                                encoding="utf-8"))
        sold, total = resell(vendor, wanted)
        build(vendor_path, vendor, work, tag + "_Vendor_Garage")
        print(f", {sold} sold first of {total}")
    print("\nPack both MoreAttachments paks.")


def demo():
    rows = [{"Name": n} for n in ("Van1", "Van2", "Head1", "Mine1", "Head2")]
    assert reorder(rows, ["Head1", "Head2"]) == 2
    assert [r["Name"] for r in rows] == ["Head1", "Head2", "Van1", "Van2", "Mine1"]
    assert reorder(rows, ["Nope"]) == 0, "unknown names change nothing"
    assert len(rows) == 5, "and lose nothing"

    vendor = {"Exports": [{"Data": [{"Name": "SellItems", "Value": [
        {"Name": "0", "Value": "Van1"}, {"Name": "1", "Value": "Head1"}]}]}]}
    sold, total = resell(vendor, ["Head1", "New1"])
    items = vendor["Exports"][0]["Data"][0]["Value"]
    assert (sold, total) == (2, 3)
    assert [i["Value"] for i in items] == ["Head1", "New1", "Van1"], \
        "an item the vendor never sold has to be added, not skipped"
    assert [i["Name"] for i in items] == ["0", "1", "2"], "array indices must renumber"
    assert resell(vendor, ["Head1", "New1"])[1] == 3, "rerunning must not duplicate"
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main(sys.argv[1:] or HEADLIGHTS)
