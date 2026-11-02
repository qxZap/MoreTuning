"""Stop MoreTuning's engines cooking.

    python EngineCooling/run.py          # every engine asset the mod ships
    python EngineCooling/run.py --dry    # show the numbers, change nothing
    python EngineCooling/run.py demo     # self-check

Heat is HeatingPower, cooling is CoolingEfficiency, both on an engine asset's
EngineProperty. Vanilla's best cooling is 1.52, and most of its engines leave both
unset. Ours make far more power on the same radiators, with HeatingPower up to 1.21.

So: HeatingPower at most HEAT, CoolingEfficiency at least COOL. Electric motors have
no use for either. Rerunnable: an engine already there is left alone.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
sys.path.insert(0, os.path.join(HERE, "..", "FuelRealism"))
from pipeline import MOD, WORK, from_json, to_json  # noqa: E402
import run as fuel  # noqa: E402

HEAT = 1.0
COOL = 2.5


def engine_fields(asset):
    for export in asset["Exports"]:
        for prop in export.get("Data") or []:
            if isinstance(prop, dict) and prop["Name"] == "EngineProperty":
                return prop["Value"]
    return None


def number(field):
    v = field.get("Value")
    return 0.0 if isinstance(v, str) else float(v or 0)


def retune(fields):
    """The new numbers in place. True if anything moved. Electric motors stay as they are."""
    by = {f["Name"]: f for f in fields if isinstance(f, dict)}
    if "MotorMaxPower" in by and number(by["MotorMaxPower"]) > 0:
        return False
    moved = False
    if "HeatingPower" in by and number(by["HeatingPower"]) > HEAT:
        by["HeatingPower"]["Value"] = HEAT
        moved = True
    if "CoolingEfficiency" in by:
        if number(by["CoolingEfficiency"]) < COOL:
            by["CoolingEfficiency"]["Value"] = COOL
            moved = True
        return moved
    # Unversioned: a property goes where the struct declares it, right after HeatingPower.
    before = by.get("HeatingPower") or by.get("FuelConsumption")
    if before is None:
        return moved
    new = dict(before)
    new["Name"] = "CoolingEfficiency"
    new["Value"] = COOL
    fields.insert(fields.index(before) + 1, new)
    return True


def main(dry=False):
    work = os.path.join(WORK, "cooling")
    os.makedirs(work, exist_ok=True)
    table = json.load(open(to_json(fuel.TABLES[0], os.path.join(work, "engines.json")), encoding="utf-8"))
    done, changed = set(), 0
    for row in fuel.engine_rows(table):
        package = fuel.asset_of(row)
        if not package or package in done:
            continue
        done.add(package)
        rel = package.replace("/Game/", "").split("/")
        source = os.path.join(MOD, *rel) + ".uasset"
        if not os.path.isfile(source):
            continue
        stem = os.path.basename(source)[: -len(".uasset")]
        js = to_json(source, os.path.join(os.path.dirname(source), stem + ".cool.json"))
        asset = json.load(open(js, encoding="utf-8"))
        fields = engine_fields(asset)
        if fields is None or not retune(fields) or dry:
            changed += 1 if fields is not None and dry else 0
            os.remove(js)
            continue
        json.dump(asset, open(js, "w", encoding="utf-8"), indent=1)
        built = from_json(js, os.path.join(os.path.dirname(source), stem + ".cool.uasset"))
        for ext in (".uasset", ".uexp"):
            shutil.copy2(built[: -len(".uasset")] + ext, os.path.join(MOD, *rel) + ext)
            os.remove(built[: -len(".uasset")] + ext)
        os.remove(js)
        changed += 1
    print(f"{changed} of {len(done)} engines changed")


def demo():
    hot = [{"Name": "FuelConsumption", "Value": 90.0}, {"Name": "HeatingPower", "Value": 1.21}, {"Name": "BlipThrottle", "Value": 0.5}]
    assert retune(hot) and [f["Name"] for f in hot] == ["FuelConsumption", "HeatingPower", "CoolingEfficiency", "BlipThrottle"]
    assert hot[1]["Value"] == HEAT and hot[2]["Value"] == COOL
    assert not retune(hot), "a second run must change nothing"
    motor = [{"Name": "MotorMaxPower", "Value": 300.0}, {"Name": "HeatingPower", "Value": 1.2}]
    assert not retune(motor) and motor[1]["Value"] == 1.2
    print("demo ok")


if __name__ == "__main__":
    if "demo" in sys.argv:
        demo()
    else:
        main("--dry" in sys.argv)
