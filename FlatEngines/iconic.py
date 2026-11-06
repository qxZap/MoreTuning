# More iconic engines nobody in the mod set has yet, as enginesound configs in two loads like diesels.py.
# A firing pattern is the bank of each cylinder in firing order (L/R) and its offset in the 720-degree
# cycle; headers per bank set how the pulses meet, which is most of an engine's voice.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engines import cyl, engine
from diesels import stack, STRAIGHT, TRUCK_MUFFLER, MODERN


def pattern(banks, header_l, header_r, ign, piston, ign_time, exh_alpha, overrun, offsets=None, intake=0.0020):
    n = len(banks)
    if overrun:  # off the fuel: little combustion, the pistons pumping
        ign, piston = ign * 0.08, piston * 0.55
    offs = offsets or [i / n for i in range(n)]
    return [cyl(offs[i], 0.00040 + 0.00003 * (i % 3), intake, header_l if b == "L" else header_r,
                ign, piston, ign_time, exh_alpha) for i, b in enumerate(banks)]


def spec(banks, idle, top, hl, hr, ign, piston, ign_time, exh_alpha, args, petrol=True, intake=0.0020, offsets=None, **extra):
    d = {"on": pattern(banks, hl, hr, ign, piston, ign_time, exh_alpha, False, offsets, intake),
         "off": pattern(banks, hl, hr, ign, piston, ign_time, exh_alpha, True, offsets, intake),
         "args": args, "idle": idle, "top": top, "petrol": petrol,
         "turbo": 0.0, "blower": False, "jake": False, "clatter": 0.0, "vtec": 0, "bov": False, "lope": 0.0, "crackle": petrol}
    d.update(extra)
    return d


I4 = "LLLL"            # inline: one bank
I5 = "LLLLL"
I6 = "LLLLLL"
CROSS_V8 = "LRRLRLLR"  # 1-8-4-3-6-5-7-2 with odd cylinders on the left: the uneven bank pulses = burble
FLAT_V8 = "LRLRLRLR"   # flat-plane: banks alternate, each bank an even four
V10 = "LRLRLRLRLR"
V6 = "LRLRLR"
SPORT = [(0.00022, 0.06), (0.00016, 0.05)]
ROAD = [(0.00030, 0.08), (0.00024, 0.08), (0.00018, 0.07)]

ICONIC = {
    # cars                 banks  idle top   hl       hr       ign  pist ign_t exh_a  (intake, exhaust, vib, pipe m, pipe a, muffler, noise, fluct)
    "f20c":     spec(I4, 900, 9000, 0.0016, 0.0016, 1.4, 3.3, 0.07, 0.93, (0.40, 0.60, 0.03, 1.0, 0.12, SPORT, 0.16, 0.02), vtec=6000, intake=0.0014),
    "k20":      spec(I4, 850, 8600, 0.0017, 0.0017, 1.4, 3.4, 0.07, 0.93, (0.36, 0.62, 0.03, 1.1, 0.13, ROAD, 0.15, 0.02), vtec=5800, intake=0.0015),
    "4age":     spec(I4, 900, 7600, 0.0019, 0.0019, 1.3, 3.5, 0.08, 0.93, (0.48, 0.55, 0.04, 1.0, 0.14, ROAD, 0.22, 0.03), intake=0.0011),
    "4g63t":    spec(I4, 850, 7000, 0.0013, 0.0013, 1.6, 3.8, 0.08, 0.94, (0.24, 0.70, 0.04, 1.3, 0.16, ROAD, 0.14, 0.04), turbo=0.8, bov=True),
    "vr38":     spec(V6, 800, 7100, 0.0011, 0.0012, 1.5, 3.7, 0.075, 0.93, (0.22, 0.62, 0.03, 1.2, 0.14, ROAD, 0.12, 0.02), turbo=0.9, bov=True),
    "rs3five":  spec(I5, 850, 7000, 0.0014, 0.0014, 1.6, 3.7, 0.075, 0.94, (0.24, 0.74, 0.04, 1.3, 0.17, SPORT, 0.13, 0.04), turbo=0.6, bov=True),
    "s65":      spec(CROSS_V8, 850, 8400, 0.0010, 0.0010, 1.4, 3.5, 0.07, 0.93, (0.40, 0.66, 0.03, 1.2, 0.14, SPORT, 0.18, 0.02), intake=0.0013),
    "voodoo":   spec(FLAT_V8, 850, 8250, 0.0012, 0.0012, 1.5, 3.6, 0.07, 0.93, (0.30, 0.72, 0.03, 1.2, 0.15, SPORT, 0.14, 0.03)),
    "cgtv10":   spec(V10, 1000, 8400, 0.0009, 0.0009, 1.3, 3.3, 0.06, 0.92, (0.36, 0.70, 0.03, 0.9, 0.12, [(0.00016, 0.04)], 0.15, 0.02), intake=0.0012),
    "sbc350":   spec(CROSS_V8, 750, 5600, 0.0018, 0.0012, 1.8, 4.2, 0.09, 0.95, (0.22, 0.80, 0.06, 1.6, 0.20, ROAD, 0.16, 0.10), lope=0.06),
    "hemi426":  spec(CROSS_V8, 800, 6000, 0.0019, 0.0013, 1.9, 4.4, 0.09, 0.95, (0.24, 0.82, 0.06, 1.7, 0.20, ROAD, 0.17, 0.08), lope=0.04),
    # diesels
    "series60": spec(I6, 600, 2100, 0.0013, 0.0011, 2.6, 6.2, 0.04, 0.94, (0.14, 0.78, 0.11, 2.9, 0.18, TRUCK_MUFFLER, 0.08, 0.05), petrol=False, turbo=0.7, jake=True, clatter=0.5),
    "cat3406e": spec(I6, 650, 2100, 0.0015, 0.0010, 2.7, 6.4, 0.04, 0.94, (0.12, 0.85, 0.12, 2.9, 0.20, [(0.00034, 0.05)], 0.08, 0.05), petrol=False, turbo=0.6, jake=True, clatter=0.6),
    "macke9":   spec(CROSS_V8, 600, 2100, 0.0014, 0.0011, 2.6, 6.0, 0.04, 0.94, (0.12, 0.84, 0.13, 2.9, 0.20, TRUCK_MUFFLER, 0.08, 0.06), petrol=False, turbo=0.5, jake=True, clatter=0.55),
    "om502":    spec(CROSS_V8, 600, 2000, 0.0012, 0.0012, 2.3, 6.0, 0.04, 0.94, (0.20, 0.62, 0.10, 2.2, 0.16, MODERN, 0.10, 0.03), petrol=False, turbo=0.8, clatter=0.35),
    "8v92":     spec("LR" * 8, 550, 2100, 0.0009, 0.0011, 2.4, 5.2, 0.05, 0.93, (0.20, 0.84, 0.12, 2.9, 0.22, STRAIGHT, 0.12, 0.05), petrol=False, blower=True, turbo=0.4, jake=True, clatter=0.3),
    "cummins67": spec(I6, 750, 3200, 0.0010, 0.0009, 2.4, 5.2, 0.04, 0.94, (0.20, 0.60, 0.10, 1.6, 0.16, MODERN, 0.10, 0.03), petrol=False, turbo=0.9, clatter=0.4),
    "ps60":     spec(CROSS_V8, 700, 3800, 0.0011, 0.0011, 2.4, 5.0, 0.04, 0.94, (0.18, 0.66, 0.11, 1.6, 0.18, ROAD, 0.10, 0.04), petrol=False, turbo=1.0, clatter=0.5),
}
# two-stroke 8V92: 8 cylinders firing every revolution = 16 pulses in the 720-degree cycle
PULSES_PER_REV = {"8v92": 8}

if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    with open(f"{out}/anchors.txt", "w", newline="\n") as f:
        for name, d in ICONIC.items():
            for load in ("on", "off"):
                open(f"{out}/{name}_{load}.esc", "w").write(engine(d[load], *d["args"][:3], stack(d["args"][3]), *d["args"][4:]))
            step = 150 if d["top"] < 4000 else 500
            r = d["idle"]
            while r < d["top"] + step:
                for load in ("on", "off"):
                    f.write(f"{name}_{load} {r}\n")
                r += step
    print(sum(1 for _ in open(f"{out}/anchors.txt")), "renders queued")
