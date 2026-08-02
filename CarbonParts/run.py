"""Add a carbon-fibre variant of every body part, into the yCarbon mod.

    python run.py                       # AeroParts, Headlights, Wheels
    python run.py Wheels                # just this one
    python run.py --wheelworks          # Maja's Wheels + carbon -> ZZb compat pak

Each row gets a `<id>_Carbon` twin at half the mass and a price set by that mass
(650c per remaining kg). Both the original and the twin lose their vehicle
restrictions -- carbon body kits are meant to fit anything, which is what the
shipped pak already did.

The carbon pak replaces the whole table, so it is built on top of MoreTuning's
own copy where there is one (AeroParts) and on vanilla otherwise. Run it after
Rebase/rebuild.py and RemoveReq.

`--wheelworks` builds the same thing on top of Maja's Mo Wheel Works instead of
vanilla. Her Wheels table is not just an unlock: it repoints every row at her
replacement meshes and adds colour slots and decal slots. Overriding it with a
vanilla-based table throws all of that away, hence a separate pak that mounts
after both. Refresh her table with FModel when she updates -- see AGENTS.md.
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
sys.path.insert(0, os.path.join(HERE, "..", "RemoveReq"))
from pipeline import (CARBON, WHEELWORKS, WHEELWORKS_CARBON, build_table,  # noqa: E402
                      name_property, register_names, table_path)
from rebase import fnames_in  # noqa: E402
from run import rename_numbered, strip_row  # noqa: E402  (RemoveReq/run.py)

TABLES = ["AeroParts", "Headlights", "Wheels"]

# Carbon parts fit anything, so unlike RemoveReq this also drops VehicleKeys.
GATES = ("VehicleTypes", "TruckClasses", "VehicleKeys", "OverrideAllowedVehicleKeys")

SUFFIX = "_Carbon"


def price_and_weight(weight):
    return 10 + round(weight / 2 * 650), round(weight / 2, 1)


def carbon_twin(row):
    """A carbon copy of a row, or None if it has no mass to halve."""
    twin = copy.deepcopy(row)
    twin["Name"] = row["Name"] + SUFFIX

    props = {p["Name"]: p for p in twin["Value"]}
    # UAssetAPI writes float zero as the string "+0", which is truthy -- check the
    # number, not the field. A massless row (the No_* removal parts) gets no twin.
    mass = props.get("MassKg", {}).get("Value")
    mass = mass if isinstance(mass, (int, float)) else 0.0
    if "Cost" not in props or not mass:
        return None

    price, weight = price_and_weight(mass)
    props["MassKg"]["Value"] = float(weight)
    props["Cost"]["Value"] = price
    if "Name" in props:
        props["Name"].clear()
        props["Name"].update(name_property(row["Name"].replace("_", " ") + " Carbon"))
    strip_row(twin, GATES)
    return twin


def add_carbon(rows, table):
    rows = [r for r in rows if not r["Name"].endswith(SUFFIX)]  # rerunnable
    # This pak sorts after xNoLimits and overrides the same table, so it has to
    # carry the "#1" -> "Vista Bonnet 01" rename too or it undoes it.
    renamed = sum(rename_numbered(row) for row in rows)
    twins = [t for t in (carbon_twin(r) for r in rows) if t]
    for row in rows:
        strip_row(row, GATES)

    names = []
    for twin in twins:
        names += [twin["Name"], *fnames_in(twin)]
    register_names(table, names)

    print(f"  {len(rows)} rows + {len(twins)} carbon variants, {renamed} '#n' renamed")
    return rows + twins


def main():
    args = sys.argv[1:]
    if "--wheelworks" in args:
        # Never silently fall back to vanilla here -- that would quietly ship a
        # "compat" pak that undoes the mod it is supposed to be compatible with.
        if not os.path.isfile(table_path(WHEELWORKS, "Wheels")):
            sys.exit(f"missing {table_path(WHEELWORKS, 'Wheels')}\n"
                     f"Export Wheels.uasset/.uexp from Maja's pak with FModel first.")
        build_table("Wheels", add_carbon, source=WHEELWORKS, dest=WHEELWORKS_CARBON)
        print("\nDone. Pack with: modp.bat ZZb_qxZap_MoreTuning_yWheelWorksCarbon_P")
        return

    for name in args or TABLES:
        build_table(name, add_carbon, dest=CARBON)
    print("\nDone. Pack with: modp.bat qxZap_MoreTuning_yCarbon_P")


def demo():
    row = {"Name": "RearWing_A", "Value": [
        {"Name": "Name", "CultureInvariantString": "Rear Wing A", "Value": "abc"},
        {"Name": "Cost", "Value": 500},
        {"Name": "MassKg", "Value": 5.0},
        {"Name": "VehicleKeys", "Value": [{"Value": "Terra"}]},
    ]}
    massless = {"Name": "No_Bonnet", "Value": [{"Name": "Cost", "Value": 0},
                                               {"Name": "MassKg", "Value": 0}]}
    table = {"NameMap": ["RearWing_A"], "NamesReferencedFromExportDataCount": 1}
    out = add_carbon([copy.deepcopy(row), massless], table)

    assert [r["Name"] for r in out] == ["RearWing_A", "No_Bonnet", "RearWing_A_Carbon"]
    twin = {p["Name"]: p for p in out[-1]["Value"]}
    assert twin["MassKg"]["Value"] == 2.5
    assert twin["Cost"]["Value"] == 10 + round(2.5 * 650)
    assert twin["Name"]["CultureInvariantString"] == "RearWing A Carbon"
    assert twin["VehicleKeys"]["Value"] == []          # carbon fits anything
    assert {p["Name"]: p for p in out[0]["Value"]}["VehicleKeys"]["Value"] == []
    assert "RearWing_A_Carbon" in table["NameMap"]

    # rerunning must not stack _Carbon_Carbon rows
    again = add_carbon(out, table)
    assert [r["Name"] for r in again] == [r["Name"] for r in out]
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main()
