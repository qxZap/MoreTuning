# MoreTuning 2.9's planned diesels (docs/ENGINES_2.9.md), as enginesound configs, each in two loads:
# "on" (driving, hard diesel combustion) and "off" (overrun: little or no fuel, soft pulses).
# A two-stroke fires every revolution, so an N-cylinder Detroit is modelled as 2N pulses in the
# 720-degree cycle: the same firing frequency, which is what the ear hears.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engines import wg, cyl, engine


def stack(length_m):
    return length_m / 343.0  # a pipe's waveguide delay


def inline6(front, rear, ign, piston, ign_time=0.04, exh_alpha=0.94, overrun=False):
    if overrun:  # no fuel to speak of: the pistons pumping air, about 5 dB down and airier
        ign, piston = ign * 0.05, piston * 0.5
    # firing 1-5-3-6-2-4 every 120 degrees; front three and rear three manifolds meet at the turbo
    order = [1, 5, 3, 6, 2, 4]
    return [cyl(i / 6, 0.00060, 0.0026, front if c <= 3 else rear, ign, piston, ign_time, exh_alpha) for i, c in enumerate(order)]


def two_stroke(n, ign, piston, banks=1):
    # n cylinders firing once per revolution = 2n pulses per 720 degrees; V engines alternate banks
    return [cyl(i / (2 * n), 0.00050, 0.0020, 0.0009 if (banks == 1 or i % 2 == 0) else 0.0011, ign, piston, 0.05, 0.93)
            for i in range(2 * n)]


def build(cyls, intake, exhaust, vib, pipe_m, pipe_alpha, muffler, noise, fluct):
    return engine(cyls, intake, exhaust, vib, stack(pipe_m), pipe_alpha, muffler, noise, fluct)


STRAIGHT = [(0.00030, 0.04)]                                          # straight pipe / stack
TRUCK_MUFFLER = [(0.00045, 0.10), (0.00038, 0.10), (0.00030, 0.09)]
MODERN = [(0.00050, 0.12), (0.00042, 0.12), (0.00034, 0.11), (0.00026, 0.10)]  # DPF + muffler

# name: (on-load cylinders, off-load cylinders, build args, idle, max rpm, extras)
# extras: turbo (whistle 0..1), blower (Roots whine), jake (has an engine brake), clatter (injection tick)
def spec(cyl_fn, idle, top, args, turbo=0.0, blower=False, jake=True, clatter=0.5):
    return {"on": cyl_fn(1.0), "off": cyl_fn(-1.0), "args": args, "idle": idle, "top": top,
            "turbo": turbo, "blower": blower, "jake": jake, "clatter": clatter}

DIESELS = {
    "ntc400":   spec(lambda k: inline6(0.0013, 0.0010, 2.8, 6.0, overrun=k < 0), 600, 2300,
                     (0.10, 0.88, 0.13, 2.9, 0.20, STRAIGHT, 0.07, 0.07), turbo=0.5, clatter=0.7),
    "isx15":    spec(lambda k: inline6(0.0012, 0.0011, 2.2, 6.2, overrun=k < 0), 600, 2100,
                     (0.24, 0.55, 0.09, 2.6, 0.14, MODERN, 0.10, 0.03), turbo=1.0, clatter=0.35),
    "c16":      spec(lambda k: inline6(0.0016, 0.0009, 2.6, 6.3, overrun=k < 0), 650, 2200,
                     (0.14, 0.75, 0.11, 2.8, 0.18, TRUCK_MUFFLER, 0.08, 0.05), turbo=0.7, clatter=0.55),
    "macke6":   spec(lambda k: inline6(0.0012, 0.0012, 2.7, 6.4, ign_time=0.035, overrun=k < 0), 600, 2100,
                     (0.12, 0.80, 0.17, 2.7, 0.20, TRUCK_MUFFLER, 0.08, 0.08), turbo=0.5, clatter=0.75),
    "mp8":      spec(lambda k: inline6(0.0011, 0.0012, 2.2, 6.1, overrun=k < 0), 600, 2100,
                     (0.22, 0.58, 0.10, 2.4, 0.15, MODERN, 0.10, 0.03), turbo=0.9, clatter=0.35),
    "6ct":      spec(lambda k: inline6(0.0011, 0.0009, 2.5, 5.4, overrun=k < 0), 650, 2500,
                     (0.16, 0.70, 0.11, 1.4, 0.18, TRUCK_MUFFLER, 0.09, 0.05), turbo=0.6, clatter=0.55),
    "12v":      spec(lambda k: inline6(0.0010, 0.0008, 2.9, 5.0, ign_time=0.035, overrun=k < 0), 750, 3000,
                     (0.14, 0.78, 0.12, 1.6, 0.22, [(0.00026, 0.05)], 0.08, 0.06), turbo=0.6, jake=False, clatter=0.9),
    "vp44":     spec(lambda k: inline6(0.0010, 0.0009, 2.5, 5.0, overrun=k < 0), 750, 3200,
                     (0.18, 0.70, 0.10, 1.6, 0.20, [(0.00030, 0.07), (0.00024, 0.06)], 0.09, 0.04), turbo=0.7, jake=False, clatter=0.5),
    "dd671":    spec(lambda k: two_stroke(6, 2.4 * (1 if k > 0 else 0.35), 5.2), 500, 2300,
                     (0.20, 0.85, 0.12, 2.9, 0.22, STRAIGHT, 0.12, 0.05), blower=True, clatter=0.3),
    "dd871":    spec(lambda k: two_stroke(8, 2.4 * (1 if k > 0 else 0.35), 5.2, banks=2), 500, 2300,
                     (0.20, 0.85, 0.12, 2.9, 0.22, STRAIGHT, 0.12, 0.05), blower=True, clatter=0.3),
    "dd1271":   spec(lambda k: two_stroke(12, 2.3 * (1 if k > 0 else 0.35), 5.4, banks=2), 500, 2300,
                     (0.18, 0.85, 0.12, 3.0, 0.22, STRAIGHT, 0.12, 0.05), blower=True, clatter=0.25),
    "dd1671":   spec(lambda k: two_stroke(16, 2.3 * (1 if k > 0 else 0.35), 5.6, banks=2), 500, 2300,
                     (0.18, 0.85, 0.13, 3.0, 0.22, [(0.00034, 0.05)], 0.12, 0.05), blower=True, clatter=0.25),
}

if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    with open(f"{out}/anchors.txt", "w", newline="\n") as f:
        for name, d in DIESELS.items():
            for load in ("on", "off"):
                open(f"{out}/{name}_{load}.esc", "w").write(build(d[load], *d["args"]))
            r = d["idle"]
            while r < d["top"] + 150:
                for load in ("on", "off"):
                    f.write(f"{name}_{load} {r}\n")
                r += 150
    print(sum(1 for _ in open(f"{out}/anchors.txt")), "renders queued")
