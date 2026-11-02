"""Read-only survey: what every MoreAttachments actor's mesh needs for 0.7.20 paint + lights.

    python MoreAttachments/lab/survey.py      # -> Rebase/work/lab/survey.json + a summary

Per actor: the mesh it renders (read from the actor's name table -- its StaticMesh
import), and each mesh slot classified:
  paint    M_Body-family: paintable as it is, one colour channel per slot (Body 1, Body 2..)
  palette  M_Palette / textured: not paintable -- needs a mesh copy with the slot on M_Gray
  lamp     a car light material -> a light section, by function (from the slot name)
  trim     glass, chrome, anything else: left alone
Nothing is written to the mod.
"""
import json, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "Rebase"))
from paint import mesh_materials, paintable_material  # noqa: E402

MA = os.path.join(HERE, "..", "..", "qxZap_satigt3_MoreAttachments_P", "MotorTown", "Content")
ACTORS = os.path.join(MA, "Objects", "MoreAttachments")
VANILLA = r"D:\MT\Output\Exports\MotorTown\Content"
OUT = os.path.join(HERE, "..", "..", "Rebase", "work", "lab", "survey.json")

LAMPS = {"M_HeadLight", "M_TailLight", "M_TurnSignalLight", "M_ReverseLight", "M_SideMarkerLight"}
NOT_PAINT = ("Glass", "Mirror", "Chrome", "Light", "Lamp", "Emissive")


def section(slot, material):
    """A lamp slot's section name: "LeftSignalLight" -> "Left Signal", "HeadLight_HighBeam" -> "High Beam"."""
    s = slot.replace("_", "")
    for key, name in (("LeftSignal", "Left Signal"), ("RightSignal", "Right Signal"), ("HighBeam", "High Beam"),
                      ("Brake", "Brake Light"), ("Reverse", "Reverse Light"), ("SideMarker", "Side Marker"),
                      ("Tail", "Tail Light"), ("HeadLight", "Headlight"), ("Signal", "Signal")):
        if key.lower() in s.lower():
            return name
    return {"M_TailLight": "Tail Light", "M_TurnSignalLight": "Signal", "M_ReverseLight": "Reverse Light",
            "M_SideMarkerLight": "Side Marker", "M_HeadLight": "Headlight"}[material]


def classify(slot, material, package):
    if material in LAMPS:
        return "lamp"
    if any(w.lower() in (slot or "").lower() or w.lower() in (material or "").lower() for w in NOT_PAINT):
        return "trim"
    if paintable_material(package, (VANILLA, MA)):
        return "paint"
    return "palette" if material and ("Palette" in material or material.startswith(("MI_", "M_"))) else "trim"


def actor_mesh(path):
    """The StaticMesh package an actor renders: a /Game/ path in its name table that is a mesh."""
    data = open(path, "rb").read()
    for pkg in dict.fromkeys(m.decode() for m in re.findall(rb"/Game/[A-Za-z0-9_/]+", data)):
        if "/Materials/" in pkg or pkg.startswith("/Game/Objects/MoreAttachments"):
            continue
        if mesh_materials(pkg, (VANILLA, MA)):
            return pkg
    return None


def main():
    rows, need = {}, Counter()
    actors = sorted(f[:-7] for f in os.listdir(ACTORS) if f.endswith(".uasset"))
    for i, name in enumerate(actors, 1):
        mesh = actor_mesh(os.path.join(ACTORS, name + ".uasset"))
        slots = [(s, m, classify(s, m, k)) for s, m, k in mesh_materials(mesh, (VANILLA, MA))] if mesh else []
        kinds = Counter(k for _, _, k in slots)
        lamps = [section(s, m) for s, m, k in slots if k == "lamp"]
        rows[name] = {"mesh": mesh, "slots": slots, "paint": kinds["paint"], "palette": kinds["palette"],
                      "lamps": sorted(set(lamps))}
        if i % 100 == 0:
            print(f"  {i}/{len(actors)}", flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rows, open(OUT, "w", encoding="utf-8"), indent=1)

    n = len(rows)
    nomesh = [a for a, r in rows.items() if not r["mesh"]]
    paint = Counter(min(r["paint"], 3) for r in rows.values() if r["mesh"])
    copy = [a for a, r in rows.items() if r["mesh"] and not r["paint"] and r["palette"]]
    lamp_parts = [a for a, r in rows.items() if r["lamps"]]
    multi = [a for a, r in rows.items() if len(r["lamps"]) > 1]
    print(f"\n{n} attachment actors, {len(set(r['mesh'] for r in rows.values() if r['mesh']))} distinct meshes")
    print(f"  no mesh found: {len(nomesh)}  {nomesh[:8]}")
    print(f"  car-paint slots per part: " + ", ".join(f"{k if k < 3 else '3+'}: {v}" for k, v in sorted(paint.items())))
    print(f"  palette-only (need a mesh copy on M_Gray): {len(copy)}")
    print(f"  with lamp sections: {len(lamp_parts)}, of which with 2+ sections (plugin): {len(multi)}")
    print("  lamp sections: " + ", ".join(f"{k} {v}" for k, v in Counter(l for r in rows.values() for l in r["lamps"]).most_common()))
    print("  examples with 2+ paint slots: " + ", ".join(a for a, r in rows.items() if r["paint"] >= 2)[:300])
    print("  examples with 2+ lamp sections: " + ", ".join(f"{a}{r['lamps']}" for a, r in list((a, rows[a]) for a in multi)[:6]))


if __name__ == "__main__":
    main()
