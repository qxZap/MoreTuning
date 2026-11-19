"""registry_doc.py -- REGISTRY.md: every table the framework lists, by table and by author.

    python DataTableFramework/registry_doc.py [out.md]      default: REGISTRY.md next to registry.json
    python DataTableFramework/registry_doc.py demo

The listing is generated from registry.json, the file run.py builds the pak from, so the page and the pak
cannot disagree. Rerun it whenever a table is registered.
"""
import json
import os
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(HERE, "registry.json")

# The channel scheme of the first 0.7.20 build (Ch0001..Ch1000 per composite). Retired: the framework no
# longer ships channel parents or stubs, so a ChNNNN file is never read. Kept here because the user asked for
# the channels that were handed out; every one of them moved to an adopted table.
CHANNEL_HISTORY = [
    ("VehicleParts", "Ch0001", "qxZap - MoreTuning", "VehicleParts_MoreTuning"),
    ("VehicleParts", "Ch0002", "qxZap - MoreTuning No Limits", "VehicleParts_MoreTuningNoLimits"),
    ("VehicleParts", "Ch0003", "qxZap - MoreTuning Carbon", "VehicleParts_MoreTuningCarbon"),
    ("VehicleParts", "Ch0004", "Teh - Engine Sound Pack (port by qxZap)", "VehicleParts_TehEngines"),
    ("VehicleParts", "Ch0005", "Suspension Expansion (port by qxZap)", "VehicleParts_SuspensionExpansion"),
    ("Items", "Ch0001", "qxZap & satigt3 - MoreAttachments", "Items_MoreAttachments"),
]

# Reserved car slots (rtwin's ReservedVehicleFramework layout) that are spoken for.
SLOTS_TAKEN = {
    1: "Austin - Overlord HX8 1.0.2 (VehicleParts, Vehicles: Atlas 112, Decals)",
    32: "Austin - Overlord HX8 1.0.2 (VehicleParts: AusV tyre compounds)",
}


def author(label):
    """The author part of a registry label: 'Rak - Heavy Haul Pack' -> 'Rak'."""
    return label.split(" - ", 1)[0].strip() if " - " in label else label.split(" (", 1)[0].strip()


def mod(label):
    """The mod part: 'Rak - Heavy Haul Pack' -> 'Heavy Haul Pack'."""
    rest = label.split(" - ", 1)[1] if " - " in label else label
    return rest.strip()


def render(reg):
    adopted = reg.get("adopted", {})
    reserved = reg.get("reserved", {})
    out = ["# Registry", "",
           "Every table the DataTable Framework lists, generated from `DataTableFramework/registry.json` by "
           "`registry_doc.py`. Within a table, later entries win a same-named row: vanilla first, then these in order.",
           ""]

    total = sum(len(t) for t in adopted.values())
    authors = OrderedDict()
    for comp, tables in adopted.items():
        for path, label in tables.items():
            authors.setdefault(author(label), []).append((comp, path, mod(label)))
    out += [f"**{total} mod tables** in {len(adopted)} composites, from **{len(authors)} authors**, "
            f"plus **{reserved.get('slots', 0)} reserved car slots**.", ""]

    out += ["## By table", ""]
    for comp, tables in adopted.items():
        out += [f"### {comp} ({len(tables)})", "", "| # | Table | Author | Mod |", "|---|---|---|---|"]
        for i, (path, label) in enumerate(tables.items(), 1):
            out.append(f"| {i} | `{path}` | {author(label)} | {mod(label)} |")
        out.append("")

    out += ["## By author", ""]
    for who, rows in authors.items():
        out += [f"### {who} ({len(rows)})", ""]
        for comp, path, what in rows:
            out.append(f"- **{comp}** `{path}` -- {what}")
        out.append("")

    n = reserved.get("slots", 0)
    tables = reserved.get("tables", {})
    out += ["## Reserved car slots", "",
            f"rtwin's ReservedVehicleFramework layout: **Slot01 to Slot{n:02d}**. A car mod ships its own slot's tables at "
            "`/Game/ReservedRegistration/Slots/SlotNN/<table>`; the framework lists every slot after the adopted tables, "
            "with no stubs, and a slot whose car is not installed is skipped. The decal table works the same way "
            "(`SlotNN/DT_Decals`).", "",
            "Tables per slot: " + ", ".join(f"{k} -> `{v}`" for k, v in tables.items()) + ", Decals -> `DT_Decals`", "",
            "| Slot | Taken by |", "|---|---|"]
    for s in range(1, n + 1):
        out.append(f"| Slot{s:02d} | {SLOTS_TAKEN.get(s, 'free')} |")
    out.append("")

    out += ["## Channels (retired)", "",
            "The first 0.7.20 build handed out channels: `Ch0001` to `Ch1000` in each of the 14 composites "
            "(14,000 stubs), later channels winning. They were replaced by adopted tables, so the framework no longer "
            "ships channel stubs and a `ChNNNN` file is never read. Every channel that was handed out moved:", "",
            "| Composite | Channel | Was | Now listed as |", "|---|---|---|---|"]
    for comp, ch, who, now in CHANNEL_HISTORY:
        out.append(f"| {comp} | {ch} | {who} | `{now}` |")
    out += ["", "No channel is open for new mods: register your own table instead (see the README).", ""]
    return "\n".join(out)


def main():
    reg = json.load(open(REGISTRY, encoding="utf-8"))
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "REGISTRY.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(reg))
    print(f"wrote {path}")


def demo():
    reg = {"adopted": {"VehicleParts": {"/Game/A/T1": "Rak - Heavy Haul Pack", "/Game/A/T2": "qxZap - MoreTuning (own rows)"},
                       "Items": {"/Game/B/T3": "Rak - Heavy Haul Pack"}},
           "reserved": {"slots": 3, "tables": {"Vehicles": "DT_Vehicles"}}}
    md = render(reg)
    assert "**3 mod tables** in 2 composites, from **2 authors**" in md, md[:400]
    assert "### Rak (2)" in md and "| Slot01 | Austin - Overlord HX8" in md and "| Slot03 | free |" in md
    assert author("qxZap & satigt3 - MoreAttachments (free)") == "qxZap & satigt3"
    assert author("Suspension Expansion (0.7.20 port by qxZap)") == "Suspension Expansion"
    print("demo ok")


if __name__ == "__main__":
    demo() if sys.argv[1:] == ["demo"] else main()
