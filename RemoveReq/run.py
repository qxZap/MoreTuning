"""Strip the "which vehicle can fit this" gates off a part table.

    python run.py                       # the tables MoreTuning ships stripped
    python run.py License Wheels        # just these
    python run.py --nolimits            # AeroParts + Headlights -> xNoLimits pak

Every row loses its vehicle restrictions, so any vehicle can buy any part -- and
for the License tables, any vehicle can buy any license. Reads each table from
the mod folder if it is already there (so this runs *after* Rebase/rebuild.py
and keeps the mod's own rows), otherwise straight from the vanilla export.

`--nolimits` is the same strip with `VehicleKeys` included, which is the gate
that ties a bumper or a headlight to one specific car -- that is what makes any
body part fit any vehicle, and it goes in its own pak because it is a much
bigger change than the rest.

Rerun this after every rebuild: rebase.py keeps vanilla's version of shared rows,
which puts the restrictions back.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Rebase"))
from pipeline import MOD, NOLIMITS, build_table, name_property  # noqa: E402

# Cleared on every row. Matches what the shipped tables actually had cleared --
# VehicleKeys is deliberately left alone here, the mod keeps those.
GATE_ARRAYS = ("VehicleTypes", "TruckClasses", "OverrideAllowedVehicleKeys")
GATE_QUERY = "VehicleRowGameplayTagQuery"

# Plus the per-car lock, for the pak whose whole point is removing it.
NOLIMIT_GATES = GATE_ARRAYS + ("VehicleKeys",)

# Engines is in here so a kart engine, a V20 or anything vanilla drops into any
# vehicle. The mod's own engine rows are already unrestricted; it is the vanilla
# rows the table is built on that carry VehicleTypes and TruckClasses.
TABLES = ["Engines", "License", "License_OversizeEscort", "License_OversizeEscort1",
          "VehicleParts0"]
NOLIMIT_TABLES = ["AeroParts", "Headlights"]


def clear_query(prop):
    """Empty a GameplayTagQuery in place rather than substituting a hand-built one,
    so the struct keeps whatever shape the current game uses."""
    changed = False
    for sub in prop.get("Value") or []:
        name, value = sub.get("Name"), sub.get("Value")
        if name in ("TagDictionary", "QueryTokenStream") and value:
            sub["Value"] = []
            changed = True
        elif name in ("UserDescription", "AutoDescription") and value is not None:
            sub["Value"] = None
            changed = True
    return changed


def strip_row(row, gates=GATE_ARRAYS):
    changed = False
    for prop in row["Value"]:
        if prop["Name"] in gates and prop.get("Value"):
            prop["Value"] = []
            changed = True
        elif prop["Name"] == GATE_QUERY:
            changed |= clear_query(prop)
    return changed


# A name that is nothing but a variant marker: "#1", " #12 ". Anything with a
# word in it -- "Dabo #1", "Type-A" -- already says which car it belongs to.
BARE_NUMBER = re.compile(r"^\s*#\d+\s*$")


def rename_numbered(row):
    """Give a part a name that means something outside its own car's menu.

    Most body parts are named just "#1", "#2" ... -- fine in vanilla, where only
    the one car they fit ever lists them, useless once every car does. The row
    key already carries the car and the variant (Vista_Bonnet_01), so use that.
    Parts that are already named, including a mod's own "Dabo #1", are left alone.
    """
    for prop in row["Value"]:
        if prop["Name"] != "Name":
            continue
        if not BARE_NUMBER.match(prop.get("CultureInvariantString") or ""):
            return False
        prop.clear()
        prop.update(name_property(row["Name"].replace("_", " ")))
        return True
    return False


def unlock_winches(rows):
    """Winches also lose VehicleKeys, so any winch fits any vehicle.

    VehicleKeys is left alone everywhere else on purpose -- it is what ties a
    bumper to the car it was modelled for. A winch is a bolt-on box with a rope,
    so the per-car lock buys nothing, and the heavy ones ship locked to a single
    truck. Everything else about them is already unrestricted.
    """
    freed = 0
    for row in rows:
        props = {p["Name"]: p for p in row["Value"]}
        if (props.get("PartType") or {}).get("Value") != "Winch":
            continue
        keys = props.get("VehicleKeys")
        if keys and keys.get("Value"):
            keys["Value"] = []
            freed += 1
    return freed


def stripper(gates, rename=False):
    def strip_requirements(rows, table):
        stripped = sum(strip_row(row, gates) for row in rows)
        print(f"  stripped {stripped} of {len(rows)} rows")
        freed = unlock_winches(rows)
        if freed:
            print(f"  unlocked {freed} winches from their per-vehicle keys")
        if rename:
            print(f"  renamed {sum(rename_numbered(row) for row in rows)} '#n' parts")
        return rows
    return strip_requirements


def main():
    args = sys.argv[1:]
    nolimits = "--nolimits" in args
    args = [a for a in args if a != "--nolimits"]

    gates = NOLIMIT_GATES if nolimits else GATE_ARRAYS
    dest = NOLIMITS if nolimits else MOD
    wanted = args or (NOLIMIT_TABLES if nolimits else TABLES)

    for name in wanted:
        build_table(name, stripper(gates, rename=nolimits), dest=dest)
    pak = "qxZap_MoreTuning_xNoLimits_P" if nolimits else "qxZap_MoreTuning_P"
    print(f"\nDone. Pack with: modp.bat {pak}")


def demo():
    row = {"Name": "TaxiLicense0", "Value": [
        {"Name": "VehicleTypes", "Value": [{"Value": "EMTVehicleType::Small"}]},
        {"Name": "VehicleKeys", "Value": [{"Value": "Terra"}]},
        {"Name": "VehicleRowGameplayTagQuery", "Value": [
            {"Name": "TokenStreamVersion", "Value": 0},
            {"Name": "QueryTokenStream", "Value": [1, 2, 3]},
            {"Name": "AutoDescription", "Value": " ALL( Vehicle.EV )"}]},
    ]}
    assert strip_row(row) is True
    by_name = {p["Name"]: p for p in row["Value"]}
    assert by_name["VehicleTypes"]["Value"] == []
    assert by_name["VehicleKeys"]["Value"] == [{"Value": "Terra"}]   # deliberately kept
    query = {s["Name"]: s["Value"] for s in by_name["VehicleRowGameplayTagQuery"]["Value"]}
    assert query["QueryTokenStream"] == [] and query["AutoDescription"] is None
    assert strip_row(row) is False, "second pass should be a no-op"

    numbered = {"Name": "Vista_Bonnet_01", "Value": [
        {"Name": "Name", "CultureInvariantString": "#1", "Namespace": "AeroParts",
         "HistoryType": "Base", "Value": "Vista_Bonnet_01_Name"}]}
    named = {"Name": "Voltex_Bumper_01", "Value": [
        {"Name": "Name", "CultureInvariantString": "Voltex Bumper", "Namespace": "AeroParts",
         "HistoryType": "Base", "Value": "Voltex_Bumper_01_Name"}]}
    prefixed = {"Name": "Dabo_01", "Value": [
        {"Name": "Name", "CultureInvariantString": "Dabo #1", "Namespace": None,
         "HistoryType": None, "Value": None}]}
    assert rename_numbered(numbered) is True
    assert rename_numbered(named) is False, "a real name must survive"
    assert rename_numbered(prefixed) is False, "a mod's own '<car> #n' must survive"
    prop = numbered["Value"][0]
    assert prop["CultureInvariantString"] == "Vista Bonnet 01"
    assert prop["Flags"] == "CultureInvariant" and prop["Namespace"] is None
    assert prop["Value"] is None, "the localisation key has to go, or it wins"
    assert rename_numbered(numbered) is False, "second pass should be a no-op"

    winch = {"Name": "Winch_Tow_05_MMW", "Value": [
        {"Name": "PartType", "Value": "Winch"},
        {"Name": "VehicleKeys", "Value": [{"Value": "GolimaRotator"}]}]}
    bumper = {"Name": "Terra_Bumper", "Value": [
        {"Name": "PartType", "Value": "FrontBumper"},
        {"Name": "VehicleKeys", "Value": [{"Value": "Terra"}]}]}
    assert unlock_winches([winch, bumper]) == 1
    assert winch["Value"][1]["Value"] == []
    assert bumper["Value"][1]["Value"] == [{"Value": "Terra"}], "only winches lose their keys"
    assert unlock_winches([winch, bumper]) == 0, "second pass should be a no-op"
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main()
