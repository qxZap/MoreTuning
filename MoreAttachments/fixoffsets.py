"""Give every built attachment actor its own mesh's offset back.

The bug
-------
A vehicle part mesh is not modelled around the origin -- it sits where it
belongs on the car, hundreds of centimetres out. To hang one on an attachment
point the actor pushes the mesh component back by exactly that much, so the
build sets

    Mesh.RelativeLocation = -ExtendedBounds.Origin

Some shipped actors carry `(131.33, 0.00, -126.62)` instead, whatever their
mesh. That is -Origin of `/Game/Cars/Models/Neo/RearSpoiler_01`, the actor the
templates were cloned from: they were built while the templates still had the
donor's real numbers where the substitution sentinels belong. Those parts hang
in mid-air, offset by the difference between their mesh and a Neo spoiler.

Why it did not fix itself
-------------------------
`migrate_templates.py` put the sentinels back, so anything built since is
correct -- but `run.py` has `CREATE_ACTORS = False` and `DELTA_ONLY_ACTORS =
True`, so an actor that already exists is never rebuilt. The fix landed in the
templates and never reached the assets.

This repairs the assets in place. Only `Mesh.RelativeLocation` is touched: the
SpotLight in these actors carries the same wrong value but `lightsout.py` left
it at Intensity 0, so it lights nothing and moving it would change nothing.

    python MoreAttachments/fixoffsets.py          # report what is wrong
    python MoreAttachments/fixoffsets.py --fix    # repair it
    python MoreAttachments/fixoffsets.py demo     # self-check
"""
import json
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(REPO, "Rebase"))
from pipeline import to_json, from_json, VANILLA      # noqa: E402

ACTORS = os.path.join(REPO, "qxZap_satigt3_MoreAttachments_P", "MotorTown",
                      "Content", "Objects", "MoreAttachments")
MOD_CONTENT = os.path.join(REPO, "qxZap_satigt3_MoreAttachments_P", "MotorTown", "Content")
WORK = os.path.join(HERE, "work", "offsets")

# Anything under a centimetre is the float noise of a round trip, not a mistake.
TOLERANCE = 0.01


def origin_of(mesh_json):
    """The mesh's ExtendedBounds Origin -- the value the build negates.

    A zero Origin is not stored: unversioned properties skip defaults, so a mesh
    already modelled around the origin lists only BoxExtent and SphereRadius.
    That is a real answer of (0,0,0), not a missing one -- returning None there
    would quietly excuse the actors that need an offset of exactly zero.
    """
    found = {}
    seen = False

    def walk(node):
        if isinstance(node, dict):
            value = node.get("Value")
            if node.get("Name") in ("Origin", "BoxExtent") and isinstance(value, dict) \
                    and "X" in value:
                found[node["Name"]] = tuple(
                    0.0 if isinstance(value[k], str) else float(value[k]) for k in "XYZ")
            else:
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for export in mesh_json["Exports"]:
        for row in export.get("Data") or []:
            if isinstance(row, dict) and row.get("Name") == "ExtendedBounds":
                seen = True
                walk(row["Value"])
    if "Origin" in found:
        return found["Origin"]
    return (0.0, 0.0, 0.0) if seen else None


def mesh_property(doc):
    """(mesh package, the RelativeLocation property dict) for one actor.

    The mesh comes off the component's StaticMesh property rather than off the
    import list -- an actor imports its materials too, and the material has no
    bounds to compare against.
    """
    imps = doc.get("Imports") or []

    def package_of(idx):
        outer = imps[-idx - 1]["OuterIndex"]
        return imps[-outer - 1]["ObjectName"] if outer < 0 else None

    mesh = prop = None
    for export in doc["Exports"]:
        if not str(export.get("ObjectName", "")).startswith("Mesh_GEN"):
            continue
        for entry in export.get("Data") or []:
            if not isinstance(entry, dict):
                continue
            if entry.get("Name") == "RelativeLocation":
                prop = entry
            elif entry.get("Name") == "StaticMesh" and isinstance(entry.get("Value"), int) \
                    and entry["Value"] < 0:
                mesh = package_of(entry["Value"])
    return mesh, prop


def mesh_file(package):
    rel = os.path.join(*package[len("/Game/"):].split("/")) + ".uasset"
    for root in (VANILLA, MOD_CONTENT):
        path = os.path.join(root, rel)
        if os.path.exists(path):
            return path
    return None


def wrong_by(location, origin):
    """How far this actor's offset is from the one its own mesh asks for."""
    want = tuple(-c for c in origin)
    return max(abs(a - b) for a, b in zip(want, location)), want


def main(fix=False):
    os.makedirs(WORK, exist_ok=True)
    actor_json = os.path.join(WORK, "actor.json")
    mesh_json = os.path.join(WORK, "mesh.json")
    names = sorted(f[:-len(".uasset")] for f in os.listdir(ACTORS)
                   if f.endswith(".uasset"))

    origins, bad, unreadable = {}, [], []
    for i, name in enumerate(names, 1):
        to_json(os.path.join(ACTORS, name + ".uasset"), actor_json)
        doc = json.load(io.open(actor_json, encoding="utf-8"))
        mesh, prop = mesh_property(doc)
        if mesh is None or prop is None:
            unreadable.append((name, "no mesh component"))
            continue
        if mesh not in origins:
            path = mesh_file(mesh)
            origins[mesh] = origin_of(json.load(io.open(
                to_json(path, mesh_json), encoding="utf-8"))) if path else None
        origin = origins[mesh]
        if origin is None:
            unreadable.append((name, "no ExtendedBounds on " + mesh))
            continue

        value = prop["Value"][0]["Value"]
        location = tuple(float(value[k]) for k in "XYZ")
        off, want = wrong_by(location, origin)
        if off < TOLERANCE:
            continue
        bad.append((name, mesh, location, want, off))
        if fix:
            for key, number in zip("XYZ", want):
                value[key] = number
            json.dump(doc, io.open(actor_json, "w", encoding="utf-8"), indent=2)
            from_json(actor_json, os.path.join(ACTORS, name + ".uasset"))
        if i % 50 == 0:
            print("  ...%d/%d  wrong so far %d" % (i, len(names), len(bad)), flush=True)

    verb = "repaired" if fix else "to repair"
    print("\n%d actors, %d %s, %d unreadable" % (len(names), len(bad), verb, len(unreadable)))
    for name, mesh, got, want, off in bad:
        print("  %-54s off by %8.1f" % (name, off))
        print("       mesh %s" % mesh)
        print("       had  (%9.2f,%9.2f,%9.2f)   now (%9.2f,%9.2f,%9.2f)" % (got + want))
    for name, why in unreadable:
        print("  !! %-54s %s" % (name, why))
    if bad and not fix:
        print("\n  run again with --fix to write these")
    return bad


def demo():
    # The real case: a Longhorn roof carrying the Neo spoiler's offset.
    neo = (131.33297729492188, 1.9073486328125e-06, -126.6209716796875)
    roof_origin = (62.11697959899902, -5.340576171875e-05, 332.97169494628906)
    off, want = wrong_by(neo, roof_origin)
    assert off > 100, "a roof wearing a spoiler's offset must read as wrong"
    assert want == tuple(-c for c in roof_origin), "the fix is the negated origin"

    # A correct actor must not be touched, sign included -- the bumper's origin
    # is negative and its offset positive.
    bumper_origin = (-501.63421630859375, -1.52587890625e-05, 59.92884159088135)
    built = (501.63421630859375, 1.52587890625e-05, -59.92884159088135)
    assert wrong_by(built, bumper_origin)[0] < TOLERANCE

    # Round-trip noise is not a mistake.
    assert wrong_by((1.0, 2.0, 3.0), (-1.0, -2.0, -3.005))[0] < TOLERANCE
    assert wrong_by((1.0, 2.0, 3.0), (-1.0, -2.0, -3.5))[0] > TOLERANCE

    # A mesh centred on the origin wants a zero offset, not a skipped one.
    assert wrong_by((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))[0] < TOLERANCE
    assert wrong_by(neo, (0.0, 0.0, 0.0))[0] > TOLERANCE

    # An omitted Origin means zero, and must not read as "cannot tell".
    bounds = {"Name": "ExtendedBounds",
              "Value": [{"Name": "BoxExtent",
                         "Value": [{"Name": "BoxExtent",
                                    "Value": {"X": 1.0, "Y": 2.0, "Z": 3.0}}]}]}
    assert origin_of({"Exports": [{"Data": [bounds]}]}) == (0.0, 0.0, 0.0),         "a mesh with no Origin entry is centred, not unknown"
    assert origin_of({"Exports": [{"Data": []}]}) is None,         "but a mesh with no ExtendedBounds at all is genuinely unknown"
    print("ok")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["demo"]:
        demo()
    else:
        main(fix="--fix" in args)
