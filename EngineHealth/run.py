"""Pull engine friction back inside the range vanilla ships, so engines idle.

    python run.py           # report and fix
    python run.py --dry     # report only
    python run.py demo      # self-check

Two things go wrong when an engine asset is cloned from a bigger or smaller one
and only its torque gets rescaled:

  stalling      FrictionCoulombCoeff is constant drag. If it is large next to
                what the engine makes at idle throttle, the engine cannot hold
                idle and dies the moment you start it. The Detroit 4-71 was at
                44% of its own torque -- twice the worst vanilla ever ships.

  engine braking  FrictionViscosityCoeff is drag proportional to speed. Too
                much and lifting off dumps the whole drivetrain, locking the
                driven wheels. The RB26s were at 8-15x their torque at redline,
                against a vanilla maximum of 4x.

The limits are read off the vanilla engines at runtime rather than hardcoded --
those demonstrably idle, so whatever they do is by definition in range. Vanilla
picks its friction to suit IdleThrottle, so the stalling limit is taken per
IdleThrottle group; the braking limit is the highest any vanilla car engine uses.

Only ever reduces friction, and only on engines that are out of range.
"""
import glob
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from pipeline import MOD, VANILLA, WORK, from_json, to_json  # noqa: E402

MOD_ENGINES = os.path.join(MOD, "Cars", "Parts", "Engine")
VANILLA_ENGINES = os.path.join(VANILLA, "Cars", "Parts", "Engine")

# Engines whose friction is a rounding error (bikes, karts, EVs) are a different
# animal -- vanilla runs them at huge viscous drag and no coulomb at all.
FRICTION_FLOOR = 1.0

# Race engines rev past anything vanilla has, and their drag is deliberate.
BRAKING_EXEMPT_RPM = 12000


def specs(path, cache):
    name = os.path.splitext(os.path.basename(path))[0]
    js = os.path.join(cache, name + ".json")
    if not os.path.exists(js):
        to_json(path, js)
    with open(js, "r", encoding="utf-8") as f:
        asset = json.load(f)
    block = [p for p in asset["Exports"][0].get("Data", []) if p["Name"] == "EngineProperty"]
    if not block:
        return None
    props = {q["Name"]: q for q in block[0]["Value"]}
    if not (props.get("MaxTorque") or {}).get("Value"):
        return None
    return dict(name=name, path=path, json=js, asset=asset, props=props)


def value(s, name, default=0.0):
    prop = s["props"].get(name)
    return prop["Value"] if prop and isinstance(prop.get("Value"), (int, float)) else default


def friction_pct(s):
    return value(s, "FrictionCoulombCoeff") / value(s, "MaxTorque", 1.0) * 100


def braking_pct(s):
    return (value(s, "FrictionViscosityCoeff") * value(s, "MaxRPM")
            / value(s, "MaxTorque", 1.0) * 100)


def idle_group(s):
    idle = (s["props"].get("IdleThrottle") or {}).get("Value")
    return round(idle, 5) if isinstance(idle, float) else None


def limits(vanilla):
    """(stall limit per idle group, one braking limit) from the vanilla engines."""
    stall, braking = {}, 0.0
    for s in vanilla:
        if friction_pct(s) < FRICTION_FLOOR:
            continue
        key = idle_group(s)
        stall[key] = max(stall.get(key, 0.0), friction_pct(s))
        braking = max(braking, braking_pct(s))
    return stall, braking


def main():
    dry = "--dry" in sys.argv
    cache_v = os.path.join(WORK, "health", "vanilla")
    cache_m = os.path.join(WORK, "health", "mod")
    for d in (cache_v, cache_m):
        os.makedirs(d, exist_ok=True)

    vanilla = [s for s in (specs(p, cache_v)
                           for p in sorted(glob.glob(os.path.join(VANILLA_ENGINES, "*.uasset"))))
               if s]
    if not vanilla:
        sys.exit(f"no vanilla engines in {VANILLA_ENGINES} -- re-export with FModel")
    stall_limit, braking_limit = limits(vanilla)
    print(f"vanilla envelope from {len(vanilla)} engines:")
    for key, cap in sorted(stall_limit.items(), key=lambda kv: -(kv[0] or 0)):
        print(f"   IdleThrottle {str(key):>8}: friction <= {cap:5.2f}% of torque")
    print(f"   engine braking          : viscous <= {braking_limit:5.0f}% of torque at redline\n")

    fallback = stall_limit[min(stall_limit, key=lambda k: k if k else 1)]
    fixed = []
    for path in sorted(glob.glob(os.path.join(MOD_ENGINES, "*.uasset"))):
        s = specs(path, cache_m)
        if not s or friction_pct(s) < FRICTION_FLOOR:
            continue
        cap = stall_limit.get(idle_group(s), fallback)
        changes = []

        if "FrictionCoulombCoeff" in s["props"] and friction_pct(s) > cap * 1.02:
            before = friction_pct(s)
            s["props"]["FrictionCoulombCoeff"]["Value"] = float(
                round(value(s, "MaxTorque") * cap / 100))
            changes.append(f"friction {before:5.1f}% -> {cap:5.2f}%")

        if ("FrictionViscosityCoeff" in s["props"]
                and value(s, "MaxRPM") < BRAKING_EXEMPT_RPM
                and braking_pct(s) > braking_limit * 1.02):
            before = braking_pct(s)
            s["props"]["FrictionViscosityCoeff"]["Value"] = round(
                value(s, "MaxTorque") * braking_limit / 100 / value(s, "MaxRPM"))
            changes.append(f"braking {before:6.0f}% -> {braking_limit:4.0f}%")

        if changes:
            fixed.append((s["name"], changes))
            if not dry:
                rewrite(s)

    for name, changes in fixed:
        print(f"  {name:26} {' | '.join(changes)}")
    print(f"\n{len(fixed)} engines {'would be' if dry else ''} retuned")
    if not dry and fixed:
        print("Rebuild is not needed -- the table points at these by soft path. Just pack.")


def rewrite(s):
    out = os.path.join(WORK, "health", "out")
    os.makedirs(out, exist_ok=True)
    src = os.path.join(out, s["name"] + ".json")
    with open(src, "w", encoding="utf-8") as f:
        json.dump(s["asset"], f, indent=1)
    built = from_json(src, os.path.join(out, s["name"] + ".uasset"))
    for ext in (".uasset", ".uexp"):
        shutil.copy2(built[:-len(".uasset")] + ext,
                     os.path.join(MOD_ENGINES, s["name"] + ext))


def demo():
    def engine(torque, coulomb, visc, rpm, idle):
        return {"props": {
            "MaxTorque": {"Value": torque}, "FrictionCoulombCoeff": {"Value": coulomb},
            "FrictionViscosityCoeff": {"Value": visc}, "MaxRPM": {"Value": rpm},
            "IdleThrottle": {"Value": idle}}}

    small = engine(800000, 200000, 500, 6500, 0.005)      # vanilla I4_50HP
    assert abs(friction_pct(small) - 25.0) < 0.01
    assert abs(braking_pct(small) - 406.25) < 0.01
    assert idle_group(small) == 0.005

    stall, braking = limits([small, engine(5000000, 500000, 1000, 6500, 0.0017)])
    assert stall[0.005] == 25.0 and stall[0.0017] == 10.0
    assert abs(braking - 406.25) < 0.01, braking

    # an engine with no friction at all must not drag the limits down
    stall2, _ = limits([small, engine(1000000, 100, 300, 14000, 0.005)])
    assert stall2[0.005] == 25.0
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main()
