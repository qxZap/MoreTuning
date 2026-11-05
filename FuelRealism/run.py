"""Make engines drink like their real counterparts.

    python run.py            # every engine the mod ships a table for
    python run.py --dry      # show the numbers, change nothing
    python run.py demo       # self-check

Fuel burn comes from `FuelConsumption` on an engine asset's EngineProperty,
scaled by a global per-class figure in DefaultMotorTownBalance.ini
(Small/Medium 0.04, Large 0.08). Vanilla sets FuelConsumption to the engine's
horsepower, near enough exactly, for all 36 of them.

The mod does not ship that ini: a Large engine's figure is halved here instead,
which is the same burn as Large at 0.04 and leaves the game's balance alone.
Only engine assets the mod already ships are touched; none is copied in.

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

# Where the engine rows are: ours for the mod's engines, vanilla's for the stock
# engine assets the mod overrides.
TABLES = [os.path.join(MOD, "DataAsset", "VehicleParts", "VehicleParts_MoreTuning.uasset"),
          os.path.join(VANILLA, "DataAsset", "VehicleParts", "Engines.uasset")]
# Balance ini class factor over Small/Medium's 0.04: Large is 0.08.
CLASS_FACTOR = {"Large": 2.0}
# Litres per hour at rated power, worked out rather than dialled in. Fuel flow
# is power times brake specific fuel consumption divided by fuel density:
#
#     L/h = kW * BSFC(g/kWh) / (1000 * density kg/L)
#
# so every figure below traces to a published engineering number and there is no
# free parameter left to fiddle. BSFC is the honest measure of an engine's
# thirst -- how much fuel it burns per unit of work -- and the spread between a
# Euro VI truck diesel and a carburettored V8 is about 40%, which vanilla had at
# zero.
#
# Sanity, since the numbers should be checkable: a 110hp TDI cruising at about a
# fifth of rated power comes out at 4.4 L/h, which at 100km/h is 4.4 L/100km. A
# real 1.9 TDI does about five.
PETROL_DENSITY = 0.745        # kg/L
DIESEL_DENSITY = 0.832
KW_PER_HP = 0.7457

# Brake specific fuel consumption in g/kWh, with the fuel it burns.
TRUCK_DIESEL = (205.0, DIESEL_DENSITY)   # Euro VI and similar
OLD_DIESEL = (240.0, DIESEL_DENSITY)     # mechanical injection
CAR_DIESEL = (230.0, DIESEL_DENSITY)     # common rail passenger
PETROL_NA = (280.0, PETROL_DENSITY)
PETROL_TURBO = (290.0, PETROL_DENSITY)
PETROL_OLD_V8 = (330.0, PETROL_DENSITY)  # carburettor era
TWO_STROKE = (420.0, PETROL_DENSITY)

# Names are unreliable for this -- half the truck engines here are called after
# their maker and nothing else -- but revs are not. Nothing that pulls a lorry
# spins past about 3000rpm, and nothing petrol stops that low.
DIESEL_RPM = 3500

# The EV-prefixed rows are electric too, and none of them says so.
ELECTRIC = r"electric|^EV[A-Z]"
SMALL_2T = r"kart|scooter|bike_i2"
OLD_MECHANICAL = r"n14|3406|8v92|v149|dv27|detroit|series60|c18|cat|ntc|macke6|12v"
DIESEL_NAME = r"tdi|cdi|hdi|dci|jtd|d4d|diesel|duramax|powerstroke|cummins|volvod|scania|paccar|weichai|dd\d"
OLD_V8_NAME = r"smallblock|bigblock|hemi|coyote|windsor|v12_|ferrari|muscle"
TURBO_NAME = r"turbo|tfsi|tsi|gti|2jz|rb2|sr20|4g63|ej2|k20|barra|amg|koenigsegg"

# The digits before HP. A few of ours run the model number straight into it --
# CATC12490HP is a C12 making 490, not a 12490 -- so an over-long run keeps its
# last three digits, which is the power in every case here.
HP = re.compile(r"(\d+)\s*HP", re.I)


# Not every engine says its power. Roughly half of the ones the mod adds are
# named after the engine and nothing else -- 13b, S54, bugattiW16 -- so the
# fallback works it out from the physics the asset does carry: peak torque and
# maximum revs. The factor is fitted against the 117 engines that do state a
# power, and it lands within 14% for half of them and 23% for nine in ten, which
# is close enough for a figure that fuel scales off linearly. It checks out
# against the real engines too: S54 comes out 324hp against a real 333, L86 408
# against 420, 13b 247 against 255.
POWER_FROM_TORQUE = 0.691


def estimate_hp(max_torque, max_rpm):
    if not max_torque or not max_rpm:
        return None
    newton_metres = max_torque / 10000.0
    kilowatts = newton_metres * max_rpm * 0.10472 / 1000.0
    return round(POWER_FROM_TORQUE * kilowatts / 0.7457)


def horsepower(key, max_torque=None, max_rpm=None):
    """Engines are named for their output; failing that, torque and revs say it."""
    found = HP.search(key)
    if found:
        digits = found.group(1)
        return int(digits[-3:] if len(digits) > 4 else digits)
    return estimate_hp(max_torque, max_rpm)


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


def litres_per_hour(hp, fuel):
    """What this engine burns flat out, from its power and how thirsty it is."""
    bsfc, density = fuel
    return hp * KW_PER_HP * bsfc / (1000.0 * density)


def consumption(key, rpm=None, torque=None, engine_type=None):
    """New FuelConsumption for an engine, or None to leave it alone."""
    power = horsepower(key, torque, rpm)
    fuel = efficiency(key, rpm)
    if power is None or fuel is None:
        return None
    return round(litres_per_hour(power, fuel) / CLASS_FACTOR.get(engine_type, 1.0), 1)


def engine_rows(table):
    for export in table["Exports"]:
        if export.get("Table"):
            return export["Table"]["Data"]
    return []


def asset_of(row):
    for prop in row["Value"]:
        if prop["Name"] == "EngineAsset" and isinstance(prop.get("Value"), dict):
            package = prop["Value"]["AssetPath"].get("PackageName")
            return None if package == "None" else package  # an empty soft path, not an engine
    return None


def engine_property(asset, name):
    for export in asset["Exports"]:
        for prop in export.get("Data") or []:
            if not isinstance(prop, dict) or prop["Name"] != "EngineProperty":
                continue
            for field in prop["Value"]:
                if isinstance(field, dict) and field["Name"] == name:
                    v = field.get("Value")
                    return 0.0 if isinstance(v, str) else float(v or 0)
    return None


def engine_type(asset):
    """Small / Medium / Large; unset is the enum default, Small."""
    for export in asset["Exports"]:
        for prop in export.get("Data") or []:
            if not isinstance(prop, dict) or prop["Name"] != "EngineProperty":
                continue
            for field in prop["Value"]:
                if isinstance(field, dict) and field["Name"] == "EngineType":
                    return str(field.get("Value")).split("::")[-1]
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
    rows = []
    for i, table_path in enumerate(TABLES):
        if not os.path.isfile(table_path):
            sys.exit(f"no engine table at {table_path}")
        table = json.load(open(to_json(table_path, os.path.join(work, f"engines{i}.json")),
                               encoding="utf-8"))
        rows += engine_rows(table)

    changed = skipped = missing = 0
    report = []
    done = set()
    for row in rows:
        key = str(row["Name"])
        package = asset_of(row)
        if not package or package in done:
            continue
        done.add(package)
        rel = package.replace("/Game/", "").split("/")
        source = os.path.join(MOD, *rel) + ".uasset"
        if not os.path.isfile(source):
            if not os.path.isfile(os.path.join(VANILLA, *rel) + ".uasset"):
                print(f"  {key}: no asset at {package}")
                missing += 1
            continue  # vanilla's own engine, not shipped: left to the game

        # Stage next to the source: UAssetGUI resolves siblings out of the folder
        # it reads from, so an asset moved somewhere lonely will not rebuild.
        stem = os.path.basename(source)[: -len(".uasset")]
        js = to_json(source, os.path.join(os.path.dirname(source), stem + ".fuel.json"))
        asset = json.load(open(js, encoding="utf-8"))
        value = consumption(key, max_rpm(asset),
                            torque=engine_property(asset, "MaxTorque"),
                            engine_type=engine_type(asset))
        if value is None:
            os.remove(js)
            skipped += 1
            continue
        moved, old = set_fuel(asset, value)
        report.append((key, old, value, engine_type(asset) or "Small"))
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

    print(f"{'engine':30}{'was':>9}{'now':>9}   class")
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

    assert efficiency("VolvoD17_600HP", rpm=2100) == TRUCK_DIESEL, "revs say diesel"
    assert efficiency("N14_370HP", rpm=2100) == OLD_DIESEL, "mechanical injection is thirstier"
    assert efficiency("SmallBlock_320HP", rpm=6500) == PETROL_OLD_V8
    assert efficiency("I4_50HP", rpm=6500) == PETROL_NA, "nothing matched, plain petrol"
    assert efficiency("19tdi_110HP", rpm=4500) == CAR_DIESEL
    assert efficiency("Electric_670HP", rpm=21000) is None

    # 110hp * 0.7457 kW/hp * 230 g/kWh / (1000 * 0.832 kg/L) = 22.7 L/h flat out
    assert abs(litres_per_hour(110, CAR_DIESEL) - 22.7) < 0.1
    assert litres_per_hour(100, TRUCK_DIESEL) < litres_per_hour(100, PETROL_OLD_V8),         "a modern truck diesel must beat a carburettored V8 on the same power"
    assert consumption("Electric_300HP", 19000) is None, "electricity is not fuel"
    assert consumption("SmallBlock_90HP", 6500) == 29.7
    assert consumption("SmallBlock_90HP", 6500, engine_type="Large") == 14.9,         "Large burns at 0.08, not the ini's old 0.04: half the figure, same fuel"
    assert engine_type({"Exports": [{"Data": [{"Name": "EngineProperty", "Value": [
        {"Name": "EngineType", "Value": "EMTEngineType::Large"}]}]}]}) == "Large"

    assert max_rpm({"Exports": [{"Data": [{"Name": "EngineProperty", "Value": [
        {"Name": "MaxRPM", "Value": 2100.0}]}]}]}) == 2100.0

    assert efficiency("EVTeslaSemi", rpm=12000) is None, "an EV is electric"
    assert efficiency("EVAlpineA290", rpm=9000) is None
    assert horsepower("S54") is None, "no name, no torque, no answer"
    assert horsepower("S54", 4170000, 8000) == 324, "torque and revs say it instead"
    assert horsepower("SmallBlock_90HP", 1400000, 6500) == 90, "the name still wins"
    assert consumption("13b", 9000, torque=2830000) is not None

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
