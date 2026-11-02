"""Maja's Motor Works, folded into MoreTuning as a rule rather than a copy.

    python Rebase/motorworks.py        # refresh old/0.7.19/motorworks_deltas.json

Her pak is whole tables -- frozen 0.7.19 copies of vanilla with her edits in
them. Shipping those again would undo every 0.7.20 balance change, so this
extracts only her edits: for each vanilla row, the properties her copy has that
0.7.19 vanilla did not. channels.py applies them onto 0.7.20 vanilla, so a row
she touched keeps her change and everything else is 0.7.20's.

Her 7 new rows (winches, TaxiLicense2, TrailerHitch_Hook) are already in
MoreTuning's own tables, and the hitch mesh ships in qxZap_MoreTuning_P.
Refresh this when she releases for a new game version.
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pipeline import REPO, WORK, table_path, to_json  # noqa: E402
from rebase import is_struct, reshape  # noqa: E402

THEIRS = os.path.join(REPO, "MajasMotorWorksV7.1-7.19_P", "MotorTown", "Content")
# 0.7.19 vanilla's VehicleParts tables, frozen in the repo: the MTLiveMap extract this
# used to read is refreshed to the current game by its own tool (it was, to 0.7.20).
BASELINE = os.path.join(HERE, "old", "0.7.19", "vanilla")
if os.path.isfile(table_path(BASELINE, "Horns")):  # a 0.7.20 table: this is not 0.7.19 any more
    sys.exit(f"FAIL: {BASELINE} holds 0.7.20 tables -- restore the 0.7.19 copy")
MAPPINGS = "MotorTown719"
DELTAS = os.path.join(HERE, "old", "0.7.19", "motorworks_deltas.json")
TABLES = ["AeroParts", "Engines", "Transmissions", "VehicleParts0", "Wheels"]
OBJECT = "UAssetAPI.PropertyTypes.Objects.ObjectPropertyData"


def import_path(imports, index):
    obj = imports[-index - 1]
    outer = imports[-obj["OuterIndex"] - 1]["ObjectName"] if obj["OuterIndex"] < 0 else ""
    return f"{outer}.{obj['ObjectName']}"


def portable(node, imports):
    """A property with its hard references spelled as asset paths, not import indices.

    Indices only mean something against one table's import list; her table and
    vanilla's number the same mesh differently. Spelled out, the two compare,
    and an edit can be re-pointed at the target table's own import.
    """
    if isinstance(node, dict):
        if node.get("$type", "").startswith(OBJECT) and isinstance(node.get("Value"), int)                 and node["Value"] < 0:
            return {**node, "Value": {"import": import_path(imports, node["Value"])}}
        return {k: portable(v, imports) for k, v in node.items() if k != "PropertyGuid"}
    if isinstance(node, list):
        return [portable(v, imports) for v in node]
    return node


def localise(node, imports, where):
    """portable() backwards, against the table the edit is applied to."""
    if isinstance(node, dict):
        ref = node.get("Value")
        if isinstance(ref, dict) and set(ref) == {"import"}:
            for i in range(len(imports)):
                if import_path(imports, -i - 1) == ref["import"]:
                    return {**node, "Value": -i - 1}
            sys.exit(f"{where}: {ref['import']} is not imported by the 0.7.20 table")
        return {k: localise(v, imports, where) for k, v in node.items()}
    if isinstance(node, list):
        return [localise(v, imports, where) for v in node]
    return node


def extract():
    deltas = {}
    for name in TABLES:
        load = lambda root, tag: json.load(open(to_json(  # noqa: E731
            table_path(root, name), os.path.join(WORK, f"{name}.{tag}.json"), MAPPINGS),
            encoding="utf-8"))
        theirs, base = load(THEIRS, "mw"), load(BASELINE, "vanilla719")
        vanilla = {r["Name"]: {p["Name"]: portable(p, base["Imports"]) for p in r["Value"]}
                   for r in base["Exports"][0]["Table"]["Data"]}
        table = {}
        for row in theirs["Exports"][0]["Table"]["Data"]:
            before = vanilla.get(row["Name"])
            if before is None:
                continue  # her own rows travel in MoreTuning's tables
            mine = (portable(p, theirs["Imports"]) for p in row["Value"])
            changed = {p["Name"]: p for p in mine if p != before.get(p["Name"])}
            if changed:
                table[row["Name"]] = changed
        deltas[name] = table
        print(f"  {name}: {len(table)} vanilla rows edited")
    with open(DELTAS, "w", encoding="utf-8") as f:
        json.dump(deltas, f, indent=1)


def load_deltas():
    with open(DELTAS, encoding="utf-8") as f:
        return json.load(f)


def apply(name, table, deltas):
    """Put her edits onto this (0.7.20 vanilla) table's rows in place; returns how many."""
    edits = deltas.get(name, {})
    n = 0
    for row in table["Exports"][0]["Table"]["Data"]:
        mine = edits.get(row["Name"])
        if not mine:
            continue
        for i, prop in enumerate(row["Value"]):
            theirs = mine.get(prop["Name"])
            if theirs is None:
                continue
            where = f"{name}.{row['Name']}.{prop['Name']}"
            theirs = localise(copy.deepcopy(theirs), table["Imports"], where)
            if is_struct(theirs) and is_struct(prop):
                theirs["Value"] = reshape(theirs["Value"], prop["Value"],
                                          f"{row['Name']}.{prop['Name']}")
            row["Value"][i] = theirs
        n += 1
    return n


def demo():
    mesh = {"$type": OBJECT + ", UAssetAPI", "Name": "Mesh", "Value": -1}
    hers = [{"ObjectName": "Winch_Body", "OuterIndex": -2}, {"ObjectName": "/Game/W", "OuterIndex": 0}]
    ours = [{"ObjectName": "/Game/W", "OuterIndex": 0}, {"ObjectName": "Winch_Body", "OuterIndex": -1}]
    spelled = portable(mesh, hers)
    assert spelled["Value"] == {"import": "/Game/W.Winch_Body"}
    assert localise(spelled, ours, "t")["Value"] == -2  # same mesh, our numbering
    table = {"Imports": ours, "Exports": [{"Table": {"Data": [{"Name": "Winch_02", "Value": [
        {"Name": "VehicleKeys", "Value": ["Vista"]}, {"Name": "Cost", "Value": 900}]}]}}]}
    assert apply("VehicleParts0", table, {"VehicleParts0": {"Winch_02": {
        "VehicleKeys": {"Name": "VehicleKeys", "Value": []}}}}) == 1
    assert table["Exports"][0]["Table"]["Data"][0]["Value"] == [
        {"Name": "VehicleKeys", "Value": []}, {"Name": "Cost", "Value": 900}]
    print("ok")


if __name__ == "__main__":
    demo() if sys.argv[1:] == ["demo"] else extract()
