"""Search tags in the description of every MoreTuning engine.

    python EngineTags/run.py        after Rebase/channels.py, which rewrites the table

The row's VehicleTypes is emptied so any engine fits anything, which leaves the game
nothing to sort by. So the description carries it: "Tags: Truck". Search Box reads that
line for its Cars / Trucks / Bikes checkboxes, and a player can read it in the garage.

tags.json is the list to edit by hand: row name -> tags. A row missing from it is filled
in once from its name, and then stays as written. The asset's EngineType is no help:
most mod engines leave it unset.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(REPO, "Rebase"))
from pipeline import MOD, WORK, from_json, name_property, to_json  # noqa: E402

TABLE = os.path.join(MOD, "DataAsset", "VehicleParts", "VehicleParts_MoreTuning.uasset")
TAGS = os.path.join(HERE, "tags.json")


def engine_package(row):
    for p in row["Value"]:
        if p["Name"] == "EngineAsset":
            path = p.get("Value", {}).get("AssetPath", {}) if isinstance(p.get("Value"), dict) else {}
            package = path.get("PackageName")
            return package if package and package.startswith("/") else None  # the field is on every row
    return None


BIKES = r"bike|scooter|cbr600|hayabusa|999r|bandit|gpproto|harley|panigale|^r750|sportster|sv650|zzr1400"
TRUCKS = (r"^bus_|duty|heavymachine|^truck_|^c18_|catc12|cummins_x15|dd16|dd20|dd471|dv27k|detroiddd16|^n14_"
          r"|paccar|scania|volvod1|weichai|teslasemi")


def guess(name):
    n = name.lower()
    return "Bike" if re.search(BIKES, n) else "Truck" if re.search(TRUCKS, n) else "Car"


def main():
    tags = json.load(open(TAGS, encoding="utf-8")) if os.path.exists(TAGS) else {}
    src = os.path.join(WORK, "enginetags.json")
    table = json.load(open(to_json(TABLE, src), encoding="utf-8"))
    rows = table["Exports"][0]["Table"]["Data"]
    done = 0
    for row in rows:
        package = engine_package(row)
        if not package:
            continue
        tag = tags.setdefault(row["Name"], guess(row["Name"]))
        text = name_property("Tags: " + tag)
        for i, p in enumerate(row["Value"]):
            if p["Name"] == "Desciption":
                row["Value"][i] = {**p, **text, "Name": "Desciption"}
                done += 1
    with open(src, "w", encoding="utf-8") as f:
        json.dump(table, f)
    from_json(src, TABLE)
    back = json.load(open(to_json(TABLE, os.path.join(WORK, "enginetags.check.json")), encoding="utf-8"))
    if "DataTableExport" not in back["Exports"][0]["$type"]:
        sys.exit("reads back raw")
    with open(TAGS, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(tags.items())), f, indent=1)
    counts = {}
    for t in tags.values():
        counts[t] = counts.get(t, 0) + 1
    print(f"{done} of {len(rows)} rows tagged: {counts}")


if __name__ == "__main__":
    main()
