# Flat-4 (EJ-style, unequal-length headers) and flat-6 (911-style) configs for enginesound.
# crank_offset is the firing point in the 720-degree cycle as 0..1, listed in firing order.
import os, sys

def wg(delay, alpha, beta):
    return f"(chamber0:(samples:(delay:{delay},),),chamber1:(samples:(delay:{delay},),),alpha:{alpha},beta:{beta},)"

def cyl(offset, exhaust, intake, extractor, ign=1.45, piston=3.9, ign_time=0.085, exh_alpha=0.95):
    return ("(" f"crank_offset:{offset},"
            f"exhaust_waveguide:{wg(exhaust, exh_alpha, 0.06)},"
            f"intake_waveguide:{wg(intake, 0.80, -0.30)},"
            f"extractor_waveguide:{wg(extractor, 0, 0.018)},"
            "intake_open_refl:0.012,intake_closed_refl:0.80,exhaust_open_refl:-0.011,"
            f"exhaust_closed_refl:{exh_alpha},piston_motion_factor:{piston},ignition_factor:{ign},ignition_time:{ign_time},)")

def engine(cyls, intake_vol, exhaust_vol, vib, straight, straight_alpha, elements, noise, fluct):
    els = ",".join(wg(d, 0, b) for d, b in elements)
    return ("(" f"rpm:1000,intake_volume:{intake_vol},exhaust_volume:{exhaust_vol},engine_vibrations_volume:{vib},"
            f"cylinders:[{','.join(cyls)}],"
            f"intake_noise_factor:{noise},intake_noise_lp:(delay:0.0013,),engine_vibration_filter:(delay:0.00026,),"
            f"muffler:(straight_pipe:{wg(straight, straight_alpha, -0.24)},muffler_elements:[{els}],),"
            f"intake_valve_shift:0.018,exhaust_valve_shift:0.18,crankshaft_fluctuation:{fluct},crankshaft_fluctuation_lp:(delay:0.04,),)")

# Flat-4, firing 1-3-2-4 = right, right, left, left. The right bank's headers are a lot longer, so its
# two pulses reach the collector late and bunched: the uneven beat that makes the boxer rumble.
IR, IL = float(os.environ.get("IR4","1.75")), float(os.environ.get("IL4","1.20"))
R, L = float(os.environ.get("R4","0.0042")), float(os.environ.get("L4","0.0010"))
flat4 = engine(
    [cyl(0.00, 0.00042, 0.0021, R, ign=IR), cyl(0.25, 0.00046, 0.0021, R * 1.06, ign=IR),
     cyl(0.50, 0.00040, 0.0021, L, ign=IL), cyl(0.75, 0.00044, 0.0021, L * 0.94, ign=IL)],
    intake_vol=0.22, exhaust_vol=0.72, vib=0.05, straight=0.0034, straight_alpha=0.18,
    elements=[(0.00031, 0.09), (0.00027, 0.09), (0.00019, 0.08), (0.00015, 0.07)], noise=0.18, fluct=0.06)

# Flat-6, firing 1-6-2-4-3-5 every 120 degrees, banks alternate. Near-equal three-into-one headers per
# bank, a short free-flowing muffler and more intake: smooth low down, a hard metallic wail up top.
B1, B2 = 0.00062, 0.00066
flat6 = engine(
    [cyl(i / 6, 0.00030 + 0.00002 * (i % 3), 0.0017, B1 if i % 2 == 0 else B2, ign=1.25, piston=3.6, ign_time=0.07, exh_alpha=0.93)
     for i in range(6)],
    intake_vol=float(os.environ.get("IV6","0.22")), exhaust_vol=0.75, vib=0.04, straight=0.0022, straight_alpha=0.14,
    elements=[(0.00019, 0.05), (0.00014, 0.05), (0.00011, 0.04)], noise=float(os.environ.get("N6","0.10")), fluct=0.02)

open(sys.argv[1] + "/flat4.esc", "w").write(flat4)
open(sys.argv[1] + "/flat6.esc", "w").write(flat6)
print("ok")
