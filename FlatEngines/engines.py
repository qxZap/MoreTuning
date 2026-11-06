# The engines, after their real counterparts, as enginesound configs.
# crank_offset = firing point in the 720-degree cycle as 0..1, listed in firing order.
import os, sys

def wg(delay, alpha, beta):
    return f"(chamber0:(samples:(delay:{delay},),),chamber1:(samples:(delay:{delay},),),alpha:{alpha},beta:{beta},)"

def cyl(offset, exhaust, intake, extractor, ign, piston, ign_time, exh_alpha):
    return ("(" f"crank_offset:{offset},"
            f"exhaust_waveguide:{wg(exhaust, exh_alpha, 0.06)},intake_waveguide:{wg(intake, 0.80, -0.30)},"
            f"extractor_waveguide:{wg(extractor, 0, 0.018)},"
            "intake_open_refl:0.012,intake_closed_refl:0.80,exhaust_open_refl:-0.011,"
            f"exhaust_closed_refl:{exh_alpha},piston_motion_factor:{piston},ignition_factor:{ign},ignition_time:{ign_time},)")

def engine(cyls, intake_vol, exhaust_vol, vib, straight, straight_alpha, elements, noise, fluct):
    els = ",".join(wg(d, 0, b) for d, b in elements)
    return ("(" f"rpm:1000,intake_volume:{intake_vol},exhaust_volume:{exhaust_vol},engine_vibrations_volume:{vib},"
            f"cylinders:[{','.join(cyls)}],intake_noise_factor:{noise},intake_noise_lp:(delay:0.0013,),"
            f"engine_vibration_filter:(delay:0.00026,),"
            f"muffler:(straight_pipe:{wg(straight, straight_alpha, -0.24)},muffler_elements:[{els}],),"
            f"intake_valve_shift:0.018,exhaust_valve_shift:0.18,crankshaft_fluctuation:{fluct},crankshaft_fluctuation_lp:(delay:0.04,),)")

def boxer4(R, L, ignR, ignL, piston=3.9, ign_time=0.085, exh_alpha=0.95, intake=0.0021):
    # firing 1-3-2-4 = right, right, left, left
    return [cyl(0.00, 0.00042, intake, R, ignR, piston, ign_time, exh_alpha), cyl(0.25, 0.00046, intake, R * 1.06, ignR, piston, ign_time, exh_alpha),
            cyl(0.50, 0.00040, intake, L, ignL, piston, ign_time, exh_alpha), cyl(0.75, 0.00044, intake, L * 0.94, ignL, piston, ign_time, exh_alpha)]

def boxer6(B1, B2, ign, piston, ign_time, exh_alpha, intake=0.0017):
    # firing 1-6-2-4-3-5 every 120 degrees, banks alternate
    return [cyl(i / 6, 0.00030 + 0.00002 * (i % 3), intake, B1 if i % 2 == 0 else B2, ign, piston, ign_time, exh_alpha) for i in range(6)]

# name: (config, idle rpm, redline, petrol)
ENGINES = {
    "ej25": (engine(boxer4(0.0042, 0.0010, 1.75, 1.20), 0.22, 0.72, 0.05, 0.0034, 0.18,
                    [(0.00031, 0.09), (0.00027, 0.09), (0.00019, 0.08), (0.00015, 0.07)], 0.18, 0.06), 800, 6800, True),
    "fa20": (engine(boxer4(0.0016, 0.0016, 1.5, 1.45, ign_time=0.08), 0.32, 0.62, 0.04, 0.0028, 0.15,
                    [(0.00028, 0.08), (0.00022, 0.08), (0.00016, 0.07), (0.00012, 0.06)], 0.20, 0.03), 750, 7400, True),
    "type1": (engine(boxer4(0.0007, 0.0007, 1.1, 1.05, piston=4.6, ign_time=0.09, exh_alpha=0.90, intake=0.0026), 0.25, 0.60, 0.11, 0.0012, 0.35,
                     [(0.00022, 0.12)], 0.26, 0.12), 900, 4500, True),
    "gt3": (engine(boxer6(0.00062, 0.00066, 1.25, 3.5, 0.06, 0.93, intake=0.0015), 0.34, 0.70, 0.03, 0.0016, 0.12,
                   [(0.00017, 0.05), (0.00012, 0.04)], 0.14, 0.02), 950, 9000, True),
    "993": (engine(boxer6(0.00070, 0.00078, 1.40, 3.8, 0.075, 0.92), 0.22, 0.78, 0.07, 0.0026, 0.20,
                   [(0.00021, 0.06), (0.00016, 0.06), (0.00012, 0.05)], 0.12, 0.05), 850, 6700, True),
    # Ford 7.3 Power Stroke: cross-plane V8, firing 1-2-7-3-4-5-6-8 = R L R R L R L L, both banks into one
    # turbo (the turbine softens the pulses), a big straight pipe, diesel combustion (hard, early, short).
    "powerstroke": (engine([cyl(i / 8, 0.00055, 0.0024, 0.0014 if b == "R" else 0.0010, 2.6, 5.5, 0.04, 0.94)
                            for i, b in enumerate("RLRRLRLL")], 0.16, 0.66, 0.13, 0.0042, 0.22,
                           [(0.00035, 0.10), (0.00030, 0.10), (0.00024, 0.09)], 0.08, 0.05), 700, 3300, False),
}

if __name__ == "__main__":
    os.makedirs(sys.argv[1], exist_ok=True)
    for name, (cfg, idle, red, _) in ENGINES.items():
        open(f"{sys.argv[1]}/{name}.esc", "w").write(cfg)
    # anchor list for the renderer: name rpm
    with open(f"{sys.argv[1]}/anchors.txt", "w", newline="\n") as f:
        for name, (_, idle, red, _) in ENGINES.items():
            step = 200 if red < 4000 else 400 if red < 7000 else 500
            r = idle
            while r < red + step: f.write(f"{name} {r}\n"); r += step
    print(sum(1 for _ in open(f"{sys.argv[1]}/anchors.txt")), "anchors")
