"""Lab pak for the two framework questions, readable from one shop screen.

    Ch0001  C0001_FwProbeHorn   a NEW row        -> "FW PROBE NEW Ch0001", $11,111
    Ch0002  Horn_Horn_58a4b6e3  OVERRIDES vanilla -> "FW PROBE OVERRIDE Ch0002", $22,222

Both are copies of the generic horn, which fits every vehicle. Seeing the first
means channels add rows; seeing the second instead of the vanilla horn means a
later parent wins a same-named row. Builds zzFW_Probe_P.

    python DataTableFramework/probe.py
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from pipeline import VANILLA, name_property, to_json  # noqa: E402
from run import WORK, load, make_channel, write_channel  # noqa: E402

LAB = os.path.join(HERE, "..", "zzFW_Probe_P", "MotorTown", "Content")
HORN = "Horn_Horn_58a4b6e3"


def relabel(row, name, label, cost):
    row = copy.deepcopy(row)
    row["Name"] = name
    for i, p in enumerate(row["Value"]):
        if p["Name"] == "Name":
            row["Value"][i] = name_property(label)
        elif p["Name"] == "Cost":
            p["Value"] = cost
    return row


def main():
    os.makedirs(WORK, exist_ok=True)
    horns = load(to_json(os.path.join(VANILLA, "DataAsset", "VehicleParts", "Horns.uasset"),
                         os.path.join(WORK, "Horns.vanilla.json")))
    row = next(r for r in horns["Exports"][0]["Table"]["Data"] if r["Name"] == HORN)
    new = relabel(row, "C0001_FwProbeHorn", "FW PROBE NEW Ch0001", 11111)
    over = relabel(row, HORN, "FW PROBE OVERRIDE Ch0002", 22222)
    write_channel(make_channel(horns, "VehicleParts", 1, [new]), "VehicleParts", 1, LAB)
    write_channel(make_channel(horns, "VehicleParts", 2, [over]), "VehicleParts", 2, LAB)
    print("probe channels built ->", LAB)


if __name__ == "__main__":
    main()
