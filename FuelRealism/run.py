"""Make engines drink like their real counterparts.

    python run.py            # every engine the mod ships a table for
    python run.py --dry      # show the numbers, change nothing
    python run.py demo       # self-check

Fuel burn comes from `FuelConsumption` on an engine asset's EngineProperty,
scaled by a global per-class figure in DefaultMotorTownBalance.ini
(Small/Medium 0.04, Large 0.08). Vanilla sets FuelConsumption to the engine's
horsepower, near enough exactly, for all 36 of them.

That has two problems.

The first is that it makes every engine equally efficient per horsepower. A
Euro VI truck diesel and a carburettored petrol V8 are about 40% apart on
brake specific fuel consumption, and vanilla has them identical, so no amount of
choosing the right engine ever pays off at the pump.

The second is the absolute level. MoreTuning's own engines have always used
hp/3, so vanilla engines burn three times as much as ours for the same power --
swapping a modded engine for a stock one of the same output triples your fuel
bill, which is nobody's intent.

So: FuelConsumption = hp * efficiency * SCALE. The efficiency figures below are
BSFC ratios against a modern naturally aspirated petrol, and SCALE puts
everything on the level our engines already used.

ponytail: SCALE is the one number that sets absolute thirst. The relative
figures are physics and should not need touching; this one is a calibration
against the game's own units, which are not documented anywhere, so it wants a
tank measured in game rather than a better argument.
"""
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from pipeline import MOD, VANILLA, WORK, from_json, to_json  # noqa: E402

TABLE = os.path.join("DataAsset", "VehicleParts", "Engines.uasset")
SCALE = 1.0 / 3.0

# Brake specific fuel consumption relative to a modern petrol NA at ~280 g/kWh.
# Lower burns less per horsepower.
TRUCK_DIESEL = 0.75          # Euro VI and similar, ~210 g/kWh
OLD_DIESEL = 0.86            # mechanical injection, ~240
CAR_DIESEL = 0.82            # common rail passenger, ~230
PETROL_NA = 1.00             # the reference
PETROL_TURBO = 1.04          # ~290
PETROL_OLD_V8 = 1.18         # carburettor era, ~330
TWO_STROKE = 1.50            # ~420

# Names are unreliable for this -- half the truck engines here are called after
# their maker and nothing else -- but revs are not. Nothing that pulls a lorry
# spins past about 3000rpm, and nothing petrol stops that low.
DIESEL_RPM = 3500

ELECTRIC = r"electric"
SMALL_2T = r"kart|scooter|bike_i2"
OLD_MECHANICAL = r"n14|3406|8v92|v149|dv27|detroit|series60|c18|cat"
DIESEL_NAME = r"tdi|cdi|hdi|dci|jtd|d4d|diesel|duramax|powerstroke|cummins|volvod|scania|paccar|weichai|dd\d"
OLD_V8_NAME = r"smallblock|bigblock|hemi|coyote|windsor|v12_|ferrari|muscle"
TURBO_NAME = r"turbo|tfsi|tsi|gti|2jz|rb2|sr20|4g63|ej2|k20|barra|amg|koenigsegg"

# The digits before HP. A few of ours run the model number straight into it --
# CATC12490HP is a C12 making 490, not a 12490 -- so an over-long run keeps its
# last three digits, which is the power in every case here.
HP = re.compile(r"(\d+)\s*HP", re.I)


def horsepower(key):
    """Engines are named for their output; that is the honest source for it."""
    found = HP.search(key)
    if not found:
        return None
    digits = found.group(1)
    return int(digits[-3:] if len(digits) > 4 else digits)


def efficiency(key, rpm=None):
    """How much fuel this burns per horsepower, against a modern petrol NA."""
    if re.search(ELECTRIC, key, re.I):
        return None
    if re.search(SMALL_2T, key, re.I):
        return TWO_STROKE
    if rpm is not None and rpm <= DIESEL_RPM:
        return OLD_DIESEL if re.search(OLD_MECHANICAL, key, re.I) else TRUCK_DIESEL
    if re.search(DIESEL_NAME, key, re.I):
        return CAR_DIESEL
    if re.search(OLD_V8_NAME, key, re.I):
        return PETROL_OLD_V8
    if re.search(TURBO_NAME, key, re.I):
        return PETROL_TURBO
    return PETROL_NA


def consumption(key, rpm=None, scale=SCALE):
    """New FuelConsumption for an engine, or None to leave it alone."""
    power = horsepower(key)
    eff = efficiency(key, rpm)
    if power is None or eff is None:
        return None
    return round(power * eff * scale, 1)


def engine_rows(table):
    for export in table["Exports"]:
        if export.get("Table"):
            return export["Table"]["Data"]
    return []


def asset_of(row):
    for prop in row["Value"]:
        if prop["Name"] == "EngineAsset" and isinstance(prop.get("Value"), dict):
            return prop["Value"]["AssetPath"].get("PackageName")
    return None


def max_rpm(asset):
    for export in asset["Exports"]:
        for prop in export.get("Data") or []:
            if not isinstance(prop, dict) or prop["Name"] != "EngineProperty":
                continue
            for field in prop["Value"]:
                if isinstance(field, dict) and field["Name"] == "MaxRPM":
                    v = field.get("Value")
                    return 0.0 if isinstance(v, str) else float(v or 0)
    return None


def set_fuel(asset, value):
    """Write FuelConsumption on the EngineProperty. True if it moved."""
    for export in asset["Exports"]:
        for prop in export.get("Data") or []:
            if not isinstance(prop, dict) or prop["Name"] != "EngineProperty":
                continue
            for field in prop["Value"]:
                if isinstance(field, dict) and field["Name"] == "FuelConsumption":
                    old = field.get("Value")
                    old = 0.0 if isinstance(old, str) else float(old or 0)
                    if abs(old - value) < 0.05:
                        return False, old
                    field["Value"] = value
                    return True, old
    return False, None


def main(dry=False):
    work = os.path.join(WORK, "fuel")
    os.makedirs(work, exist_ok=True)
    table_path = os.path.join(MOD, TABLE)
    if not os.path.isfile(table_path):
        sys.exit(f"no engine table at {table_path} -- run the Rebase build first")
    table = json.load(open(to_json(table_path, os.path.join(work, "engines.json")),
                           encoding="utf-8"))

    changed = skipped = missing = 0
    report = []
    for row in engine_rows(table):
        key = str(row["Name"])
        package = asset_of(row)
        if not package:
            continue
        rel = package.replace("/Game/", "").split("/")
        ours = os.path.join(MOD, *rel) + ".uasset"
        source = ours if os.path.isfile(ours) else os.path.join(VANILLA, *rel) + ".uasset"
        if not os.path.isfile(source):
            print(f"  {key}: no asset at {package}")
            missing += 1
            continue

        # Stage next to the source: UAssetGUI resolves siblings out of the folder
        # it reads from, so an asset moved somewhere lonely will not rebuild.
        stem = os.path.basename(source)[: -len(".uasset")]
        js = to_json(source, os.path.join(os.path.dirname(source), stem + ".fuel.json"))
        asset = json.load(open(js, encoding="utf-8"))
        value = consumption(key, max_rpm(asset))
        if value is None:
            os.remove(js)
            skipped += 1
            continue
        moved, old = set_fuel(asset, value)
        report.append((key, old, value, "ours" if source == ours else "vanilla"))
        if not moved:
            os.remove(js)
            continue
        if dry:
            os.remove(js)
            changed += 1
            continue

        json.dump(asset, open(js, "w", encoding="utf-8"), indent=1)
        built = from_json(js, os.path.join(os.path.dirname(source), stem + ".fuel.uasset"))
        target = os.path.join(MOD, *rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        for ext in (".uasset", ".uexp"):
            shutil.copy2(built[: -len(".uasset")] + ext, target + ext)
            os.remove(built[: -len(".uasset")] + ext)
        os.remove(js)
        changed += 1

    print(f"{'engine':30}{'was':>9}{'now':>9}   source")
    for key, old, new, where in report:
        print(f"{key:30}{old:9.1f}{new:9.1f}   {where}")
    print(f"\n{changed} engines retuned, {skipped} left alone (electric or unnamed), "
          f"{missing} missing")
    print("Pack with: modp.bat qxZap_MoreTuning_P")


def demo():
    assert horsepower("SmallBlock_90HP") == 90
    assert horsepower("N14_525HPs") == 525
    assert horsepower("DefaultBody") is None, "not every row names a power"

    assert horsepower("CATC12490HP") == 490, "a C12 making 490, not a 12490"
    assert horsepower("KoenigseggHV8tt2300HP") == 2300, "four digits is a real number"

    assert efficiency("VolvoD17_600HP", rpm=2100) == 0.75, "revs say diesel, name need not"
    assert efficiency("N14_370HP", rpm=2100) == 0.86, "an old mechanical diesel is thirstier"
    assert efficiency("SmallBlock_320HP", rpm=6500) == 1.18
    assert efficiency("I4_50HP", rpm=6500) == 1.00, "nothing matched, plain petrol"
    assert efficiency("19tdi_110HP", rpm=4500) == 0.82
    assert efficiency("Electric_670HP", rpm=21000) is None

    assert consumption("SmallBlock_90HP", 6500) == 35.4
    assert consumption("Electric_300HP", 19000) is None, "electricity is not fuel"
    assert consumption("KartEngine_10HP", 9000) == 5.0
    assert consumption("HeavyDuty_440HP", 2900, scale=1.0) == 330.0, "scale is the only knob"

    assert max_rpm({"Exports": [{"Data": [{"Name": "EngineProperty", "Value": [
        {"Name": "MaxRPM", "Value": 2100.0}]}]}]}) == 2100.0

    asset = {"Exports": [{"Data": [
        {"Name": "EngineProperty", "Value": [
            {"Name": "MaxRPM", "Value": 6500.0},
            {"Name": "FuelConsumption", "Value": 90.0}]}]}]}
    moved, old = set_fuel(asset, 35.4)
    assert moved is True and old == 90.0
    got = {f["Name"]: f["Value"] for f in asset["Exports"][0]["Data"][0]["Value"]}
    assert got["FuelConsumption"] == 35.4
    assert got["MaxRPM"] == 6500.0, "nothing but the fuel figure may move"
    assert set_fuel(asset, 35.4)[0] is False, "second pass should be a no-op"
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main(dry="--dry" in sys.argv)
