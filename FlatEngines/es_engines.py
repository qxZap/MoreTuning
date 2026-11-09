# engine-sim scripts for MoreTuning's engines, generated from a spec table (the Carrera GT, cgtv10, keeps its own
# hand-made script). Each spec is the real engine: bore x stroke, compression, layout and bank angle, firing order and
# which bank each cylinder sits on (that, through each bank's own exhaust, is what makes a crossplane V8 burble and a
# flat-plane one scream), idle and rev limit. What is not published is scaled from the Carrera GT script: valve flow
# with bore area, runners and plenum with displacement, masses with size; boost scales the intake flow.
#   Two-strokes (Detroit 71/92 series) fire every revolution, which engine-sim's four-stroke cycle cannot: each real
#   cylinder is two model cylinders on the same bank, 360 deg apart -- the firing rhythm, which is what is heard, is exact.
#   Diesels are spark engines at diesel compression with a short fast burn: engine-sim models no compression ignition.
# Writes assets/engines/moretuning/gen/<name>.mr and the entry assets/mt_gen_<name>.mr; es_steps renders from those.
#   python -I es_engines.py [name ...]      python -I es_engines.py demo
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = r"D:\MT\engine-sim\assets"

# layout: ("inline",) | ("v", angle) | ("flat",). banks: per cylinder number, "A"/"B" (A at +angle/2).
# fo: firing order. strokes: 4 or 2. boost: bar over atmospheric (scales intake flow). ir: impulse response.
# cam: (duration at 50 thou, lift mm, intake centre, exhaust centre).
def odd_a(n): return {c: "A" if c % 2 else "B" for c in range(1, n + 1)}
def half_a(n): return {c: "A" if c <= n // 2 else "B" for c in range(1, n + 1)}
CAR_CAM, HOT_CAM, DIESEL_CAM = (230, 15.9, 90, 112), (262, 14.5, 106, 114), (205, 12.0, 112, 112)
SPECS = {
    # type1, hemi426: minimal_muffling_01 since 2026-11-08 -- mild_exhaust_0 / _02 left one low tone, nothing above 1-2 kHz ("buzzing", "dull")
    "type1":    dict(kind="car", cyl=4, layout=("flat",), banks={1: "A", 2: "A", 3: "B", 4: "B"}, fo=[1, 4, 3, 2], bore=85.5, stroke=69, cr=7.5, idle=900, top=4500, ir="minimal_muffling_01", cam=(220, 9.5, 108, 112)),
    "4age":     dict(kind="car", cyl=4, layout=("inline",), fo=[1, 3, 4, 2], bore=81, stroke=77, cr=9.4, idle=900, top=7600, ir="minimal_muffling_01", cam=CAR_CAM),
    "4g63t":    dict(kind="car", cyl=4, layout=("inline",), fo=[1, 3, 4, 2], bore=85, stroke=88, cr=8.8, idle=850, top=7000, boost=1.4, ir="minimal_muffling_01", cam=CAR_CAM),
    "rs3five":  dict(kind="car", cyl=5, layout=("inline",), fo=[1, 2, 4, 5, 3], bore=82.5, stroke=92.8, cr=10.0, idle=850, top=7000, boost=1.4, ir="minimal_muffling_01", cam=CAR_CAM),
    "s65":      dict(kind="car", cyl=8, layout=("v", 90), banks=half_a(8), fo=[1, 5, 4, 8, 6, 3, 7, 2], bore=92, stroke=75.2, cr=12.0, idle=850, top=8400, ir="minimal_muffling_01", cam=CAR_CAM),
    "voodoo":   dict(kind="car", cyl=8, layout=("v", 90), banks=half_a(8), fo=[1, 5, 4, 8, 3, 7, 2, 6], bore=94, stroke=93, cr=12.0, idle=850, top=8250, ir="minimal_muffling_01", cam=CAR_CAM),
    "sbc350":   dict(kind="car", cyl=8, layout=("v", 90), banks=odd_a(8), fo=[1, 8, 4, 3, 6, 5, 7, 2], bore=101.6, stroke=88.4, cr=10.0, idle=750, top=5600, ir="minimal_muffling_02", cam=HOT_CAM),
    "hemi426":  dict(kind="car", cyl=8, layout=("v", 90), banks=odd_a(8), fo=[1, 8, 4, 3, 6, 5, 7, 2], bore=108, stroke=95.25, cr=10.25, idle=800, top=6000, ir="minimal_muffling_01", cam=(276, 14.0, 110, 114)),
    "12v":      dict(kind="pickup", cyl=6, layout=("inline",), fo=[1, 5, 3, 6, 2, 4], bore=102, stroke=120, cr=17.5, idle=750, top=3000, boost=1.4, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "vp44":     dict(kind="pickup", cyl=6, layout=("inline",), fo=[1, 5, 3, 6, 2, 4], bore=102, stroke=120, cr=17.2, idle=750, top=3200, boost=1.4, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "cummins67": dict(kind="pickup", cyl=6, layout=("inline",), fo=[1, 5, 3, 6, 2, 4], bore=107, stroke=124, cr=17.3, idle=750, top=3200, boost=2.2, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "ps60":     dict(kind="pickup", cyl=8, layout=("v", 90), banks=odd_a(8), fo=[1, 2, 7, 3, 4, 5, 6, 8], bore=95, stroke=105, cr=18.0, idle=700, top=3800, boost=2.0, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "ntc400":   dict(kind="truck", cyl=6, layout=("inline",), fo=[1, 5, 3, 6, 2, 4], bore=140, stroke=152, cr=14.5, idle=600, top=2300, boost=1.6, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "isx15":    dict(kind="truck", cyl=6, layout=("inline",), fo=[1, 5, 3, 6, 2, 4], bore=137, stroke=169, cr=17.0, idle=600, top=2100, boost=2.6, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "c16":      dict(kind="truck", cyl=6, layout=("inline",), fo=[1, 5, 3, 6, 2, 4], bore=137, stroke=172, cr=16.0, idle=600, top=2200, boost=2.5, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "macke6":   dict(kind="truck", cyl=6, layout=("inline",), fo=[1, 5, 3, 6, 2, 4], bore=124, stroke=165, cr=15.0, idle=600, top=2100, boost=1.6, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "mp8":      dict(kind="truck", cyl=6, layout=("inline",), fo=[1, 5, 3, 6, 2, 4], bore=131, stroke=158, cr=17.0, idle=600, top=2100, boost=2.5, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "6ct":      dict(kind="truck", cyl=6, layout=("inline",), fo=[1, 5, 3, 6, 2, 4], bore=114, stroke=135, cr=17.3, idle=650, top=2500, boost=1.9, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "series60": dict(kind="truck", cyl=6, layout=("inline",), fo=[1, 5, 3, 6, 2, 4], bore=130, stroke=160, cr=16.5, idle=600, top=2100, boost=2.4, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "cat3406e": dict(kind="truck", cyl=6, layout=("inline",), fo=[1, 5, 3, 6, 2, 4], bore=137, stroke=165, cr=16.25, idle=650, top=2100, boost=2.4, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "macke9":   dict(kind="truck", cyl=8, layout=("v", 90), banks=odd_a(8), fo=[1, 5, 4, 8, 6, 3, 7, 2], bore=139.7, stroke=133.4, cr=15.0, idle=600, top=2100, boost=2.2, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "om502":    dict(kind="truck", cyl=8, layout=("v", 90), banks=half_a(8), fo=[1, 5, 4, 2, 6, 3, 7, 8], bore=130, stroke=150, cr=17.25, idle=600, top=2000, boost=2.5, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    # Detroit two-strokes: V engines at 63.5 deg, banks alternate in the firing order
    "dd671":    dict(kind="truck", cyl=6, layout=("inline",), fo=[1, 5, 3, 6, 2, 4], bore=108, stroke=127, cr=17.0, idle=500, top=2300, strokes=2, boost=0.5, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "dd871":    dict(kind="truck", cyl=8, layout=("v", 63.5), banks=half_a(8), fo=[1, 7, 3, 8, 4, 6, 2, 5], bore=108, stroke=127, cr=17.0, idle=500, top=2300, strokes=2, boost=0.5, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "8v92":     dict(kind="truck", cyl=8, layout=("v", 63.5), banks=half_a(8), fo=[1, 7, 3, 8, 4, 6, 2, 5], bore=123, stroke=127, cr=17.0, idle=550, top=2100, strokes=2, boost=1.2, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "dd1271":   dict(kind="truck", cyl=12, layout=("v", 63.5), banks=half_a(12), fo=[1, 9, 5, 12, 3, 8, 6, 10, 2, 11, 4, 7], bore=108, stroke=127, cr=17.0, idle=500, top=2300, strokes=2, boost=0.5, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
    "dd1671":   dict(kind="truck", cyl=16, layout=("v", 63.5), banks=half_a(16), fo=[1, 15, 7, 11, 3, 13, 5, 9, 2, 16, 8, 12, 4, 14, 6, 10], bore=108, stroke=127, cr=17.0, idle=500, top=2300, strokes=2, boost=0.5, diesel=True, ir="minimal_muffling_02", cam=DIESEL_CAM),
}
REF_CC = 573.0  # the Carrera GT's cylinder, which every unpublished number is scaled from
CALIB = os.path.join(HERE, "es_idle.json")  # per engine: how far the idle air passage is open (calibrate_idle)


def idle_gap(name):
    import json
    try:
        return json.load(open(CALIB)).get(name, 0.002)
    except (OSError, ValueError):
        return 0.002


def cylinders(s):
    """[(model cylinder, bank 'A'/'B', firing angle deg)] -- a two-stroke cylinder becomes two, 360 deg apart."""
    n, strokes = s["cyl"], s.get("strokes", 4)
    banks = s.get("banks") or {c: "A" for c in range(1, n + 1)}
    step = (720.0 if strokes == 4 else 360.0) / n
    out = []
    for pos, c in enumerate(s["fo"]):
        out.append((c, banks[c], pos * step))
        if strokes == 2:
            out.append((c, banks[c], pos * step + 360.0))
    return out


def bank_angles(s):
    lay = s["layout"]
    if lay[0] == "inline":
        return {"A": 0.0}
    v = 180.0 if lay[0] == "flat" else float(lay[1])
    return {"A": v / 2, "B": -v / 2}


def journals(s):
    """Rod journal angle per model cylinder: firing at F on a bank at angle a needs the pin at F - (a0 - a) mod 360
    (a0 = bank A's angle; checked against the Carrera GT script, whose bank B fires v_angle after bank A on the same pin)."""
    ang = bank_angles(s)
    a0 = ang["A"]
    return [((f - (a0 - ang[b])) % 360.0, i) for i, (c, b, f) in enumerate(cylinders(s))]


def simfreq(s):
    """Two-strokes (twice the model cylinders) burn unevenly at a low rate -- lower orders 12-20 dB over the firing
    tone at 6.7-15 kHz, gone at 140 steps per firing at the rev limit (200 for the V12/V16). Four-strokes keep the
    Carrera GT's kind of rate, which renders them cleanly."""
    if s.get("strokes", 4) == 2:
        return int((140 if s["cyl"] <= 8 else 200) * s["top"] / 60 * s["cyl"])
    return max(6500, int(s["top"] / 60 * 2 * s["cyl"] * 6))


def script(name, s, gap=None):
    cyls = cylinders(s)
    ang = bank_angles(s)
    two = s.get("strokes", 4) == 2
    cyl_cc = math.pi / 4 * (s["bore"] / 10) ** 2 * (s["stroke"] / 10) * (2 if two else 1)  # a two-stroke breathes twice a cycle
    disp_l = math.pi / 4 * (s["bore"] / 10) ** 2 * (s["stroke"] / 10) * s["cyl"] / 1000
    scale = cyl_cc / REF_CC
    boost = 1 + s.get("boost", 0.0)
    chamber = math.pi / 4 * (s["bore"] / 10) ** 2 * (s["stroke"] / 10) / (s["cr"] - 1)
    flow_att = 2.4 * (s["bore"] / 98.0) ** 2 * boost
    model_disp = disp_l * (2 if two else 1)
    rod = 1.65 * s["stroke"]
    truck = s["kind"] == "truck"
    dur, lift, ic, ec = s["cam"]
    top, idle = s["top"], s["idle"]
    diesel = s.get("diesel", False)
    # journals, shared where two cylinders land on the same pin
    js, jidx = [], []
    for a, i in journals(s):
        for k, b in enumerate(js):
            if abs((a - b + 180) % 360 - 180) < 0.01:
                jidx.append(k); break
        else:
            js.append(a); jidx.append(len(js) - 1)
    L = []
    w = L.append
    w(f"// {name}: generated by MoreTuning FlatEngines/es_engines.py -- do not edit, change the spec there.")
    w('import "engine_sim.mr"\n\nunits units()\nconstants constants()\nimpulse_response_library ir_lib()\n')
    w("private node wires {")
    for i in range(len(cyls)):
        w(f"    output wire{i + 1}: ignition_wire();")
    w("}\n")
    w(f"""private node gen_head {{
    input intake_camshaft;
    input exhaust_camshaft;
    input flip_display: false;
    alias output __out: head;
    function intake_flow(50 * units.thou)
    intake_flow""")
    for lft, fl in ((0, 0), (50, 58), (100, 103), (150, 156), (200, 214), (250, 249), (300, 268), (350, 280), (400, 280), (450, 281)):
        w(f"        .add_flow_sample({lft}, {fl * flow_att:.2f})")
    w("    function exhaust_flow(50 * units.thou)\n    exhaust_flow")
    for lft, fl in ((0, 0), (50, 37), (100, 72), (150, 113), (200, 160), (250, 196), (300, 222), (350, 235), (400, 245), (450, 246)):
        w(f"        .add_flow_sample({lft}, {fl * flow_att / boost:.2f})")
    w(f"""    generic_cylinder_head head(
        chamber_volume: {chamber:.2f} * units.cc,
        intake_runner_volume: {149.6 * scale:.1f} * units.cc,
        intake_runner_cross_section_area: {1.75 * math.sqrt(scale):.3f} * units.inch * {1.75 * math.sqrt(scale):.3f} * units.inch,
        exhaust_runner_volume: {50.0 * scale:.1f} * units.cc,
        exhaust_runner_cross_section_area: {2.5 * math.sqrt(scale):.3f} * units.inch * {2.5 * math.sqrt(scale):.3f} * units.inch,
        intake_port_flow: intake_flow,
        exhaust_port_flow: exhaust_flow,
        valvetrain: standard_valvetrain(intake_camshaft: intake_camshaft, exhaust_camshaft: exhaust_camshaft),
        flip_display: flip_display
    )
}}
""")
    w("private node gen_camshaft {\n    input intake_lobe_profile;\n    input exhaust_lobe_profile;")
    w(f"    input intake_lobe_center: {ic} * units.deg;\n    input exhaust_lobe_center: {ec} * units.deg;\n    input base_radius: 0.9 * units.inch;")
    for b in ang:
        w(f"    output intake_cam_{b}: _intake_cam_{b};\n    output exhaust_cam_{b}: _exhaust_cam_{b};")
    w("    camshaft_parameters params(advance: 0 * units.deg, base_radius: base_radius)")
    for b in ang:
        w(f"    camshaft _intake_cam_{b}(params, lobe_profile: intake_lobe_profile)\n    camshaft _exhaust_cam_{b}(params, lobe_profile: exhaust_lobe_profile)")
    w("    label rot360(360 * units.deg)")
    for b in ang:
        ex = "".join(f"\n        .add_lobe(rot360 - exhaust_lobe_center + {f:.3f} * units.deg)" for c, bb, f in cyls if bb == b)
        it = "".join(f"\n        .add_lobe(rot360 + intake_lobe_center + {f:.3f} * units.deg)" for c, bb, f in cyls if bb == b)
        w(f"    _exhaust_cam_{b}{ex}\n    _intake_cam_{b}{it}")
    w("}\n")
    crank_lb = 40 * (model_disp / 5.7) ** 0.7
    fly_lb = (90 if truck else 35 if s["kind"] == "pickup" else 15) * max(1.0, model_disp / 5.7) ** 0.3
    piston_g = 100 * (s["bore"] / 98) ** 3
    w(f"""public node gen_engine {{
    alias output __out: engine;
    engine engine(
        name: "{name}",
        starter_torque: {max(100, 25 * model_disp * s["cr"] / 10):.0f} * units.lb_ft,
        starter_speed: {(160 if truck else 200)} * units.rpm,
        redline: {top} * units.rpm,
        throttle_gamma: 2.0,
        fuel: fuel(max_turbulence_effect: {(20.0 if diesel else 10.0)}, max_dilution_effect: 20.0,
                   burning_efficiency_randomness: {(0.35 if diesel else 0.25)}, max_burning_efficiency: {(0.85 if diesel else 0.9)}),
        hf_gain: 0.01,
        noise: 1.0,
        jitter: 0.1,
        simulation_frequency: {simfreq(s)}
    )
    wires wires()
    label stroke({s["stroke"]} * units.mm)
    label bore({s["bore"]} * units.mm)
    label rod_length({rod:.1f} * units.mm)
    label rod_mass({50 * (s["bore"] / 98) ** 3:.0f} * units.g)
    label compression_height(1.0 * units.inch)
    label crank_mass({crank_lb:.1f} * units.lb)
    label flywheel_mass({fly_lb:.1f} * units.lb)
    label flywheel_radius({(9.0 if truck else 6.5)} * units.inch)
    crankshaft c0(
        throw: stroke / 2,
        flywheel_mass: flywheel_mass,
        mass: crank_mass,
        friction_torque: {(12.0 if truck else 4.0 if s["kind"] == "pickup" else 0.0)} * units.lb_ft,
        moment_of_inertia: disk_moment_of_inertia(mass: crank_mass, radius: stroke)
            + disk_moment_of_inertia(mass: flywheel_mass, radius: flywheel_radius)
            + disk_moment_of_inertia(mass: 1 * units.kg, radius: 1.0 * units.cm),
        position_x: 0.0,
        position_y: 0.0,
        tdc: {90 + ang["A"]:.3f} * units.deg
    )""")
    for k, a in enumerate(js):
        w(f"    rod_journal rj{k}(angle: {a:.3f} * units.deg)")
    w("    c0" + "".join(f"\n        .add_rod_journal(rj{k})" for k in range(len(js))))
    w(f"""    piston_parameters piston_params(mass: {piston_g:.0f} * units.g, compression_height: compression_height, wrist_pin_position: 0.0, displacement: 0.0)
    connecting_rod_parameters cr_params(mass: rod_mass, moment_of_inertia: rod_moment_of_inertia(mass: rod_mass, length: rod_length),
        center_of_mass: 0.0, length: rod_length)
    intake intake(
        plenum_volume: {1.325 * model_disp / 5.7:.3f} * units.L,
        plenum_cross_section_area: {20.0 * math.sqrt(model_disp / 5.7):.1f} * units.cm2,
        intake_flow_rate: k_carb({1750.0 * model_disp / 5.7 * boost:.1f}),
        runner_flow_rate: k_carb({350.0 * scale * boost:.1f}),
        runner_length: 4.0 * units.inch,
        idle_flow_rate: k_carb(0.0),
        idle_throttle_plate_position: {1 - (idle_gap(name) if gap is None else gap):.6f},
        velocity_decay: 0.5
    )
    exhaust_system_parameters es_params(
        outlet_flow_rate: k_carb({3500.0 * model_disp / 5.7 * boost:.1f}),
        primary_tube_length: {(70.0 if truck else 50.0)} * units.inch,
        primary_flow_rate: k_carb({1750.0 * model_disp / 5.7 * boost:.1f}),
        velocity_decay: 1.0
    )""")
    for k, b in enumerate(ang):
        w(f"    exhaust_system exhaust{b}(es_params, audio_volume: 2.0, length: {(160 if truck else 100) + 0.5 * k} * units.inch, impulse_response: ir_lib.{s['ir']})")
    w(f"    cylinder_bank_parameters bank_params(bore: bore, deck_height: stroke / 2 + rod_length + compression_height)")
    for b, a in ang.items():
        w(f"    cylinder_bank b{b}(bank_params, angle: {a:.3f} * units.deg)")
    for b in ang:
        body = ""
        for i, (c, bb, f) in enumerate(cyls):
            if bb != b:
                continue
            att = 0.75 + 0.35 * ((i * 7919) % 11) / 10  # each cylinder a little different, as in the hand-made script
            body += (f"\n        .add_cylinder(piston: piston(piston_params, blowby: k_28inH2O(0.0)), connecting_rod: connecting_rod(cr_params),"
                     f" rod_journal: rj{jidx[i]}, intake: intake, exhaust_system: exhaust{b}, ignition_wire: wires.wire{i + 1},"
                     f" sound_attenuation: {att:.2f}, primary_length: {1 + (i % 5)} * units.cm)")
        body += (f"\n        .set_cylinder_head(gen_head(intake_camshaft: camshaft.intake_cam_{b}, exhaust_camshaft: camshaft.exhaust_cam_{b}"
                 + (", flip_display: true" if b == "A" and len(ang) > 1 else "") + "))")
        w(f"    b{b}{body}")
    w("    engine" + "".join(f"\n        .add_cylinder_bank(b{b})" for b in ang))
    w("    engine.add_crankshaft(c0)")
    w(f"""    harmonic_cam_lobe intake_lobe(duration_at_50_thou: {dur} * units.deg, gamma: 1.1, lift: {lift} * units.mm, steps: 100)
    harmonic_cam_lobe exhaust_lobe(duration_at_50_thou: {dur} * units.deg, gamma: 1.1, lift: {lift} * units.mm, steps: 100)
    gen_camshaft camshaft(intake_lobe_profile: intake_lobe, exhaust_lobe_profile: exhaust_lobe)
    function timing_curve({max(top // 2, 500)} * units.rpm)
    timing_curve""")
    lo_t, hi_t = (14, 22) if diesel else (12, 38)
    for r, t in ((0, lo_t), (max(top // 2, 500), hi_t), (top, hi_t), (2 * top, hi_t), (3 * top, hi_t)):
        w(f"        .add_sample({r} * units.rpm, {t} * units.deg)")
    w(f"    ignition_module ignition_module(timing_curve: timing_curve, rev_limit: {top} * units.rpm, limiter_duration: 0.1)")
    w("    ignition_module" + "".join(f"\n        .connect_wire(wires.wire{i + 1}, {f:.3f} * units.deg)" for i, (c, b, f) in enumerate(cyls)))
    w("    engine.add_ignition_module(ignition_module)\n}\n")
    w("""private node gen_vehicle {
    alias output __out: vehicle(mass: 1500 * units.kg, drag_coefficient: 0.3, cross_sectional_area: (72 * units.inch) * (50 * units.inch),
        diff_ratio: 3.42, tire_radius: 10 * units.inch, rolling_resistance: 200 * units.N);
}
private node gen_transmission {
    alias output __out: transmission(max_clutch_torque: 2000 * units.lb_ft).add_gear(3.23).add_gear(2.19).add_gear(1.61).add_gear(1.23).add_gear(0.97).add_gear(0.8);
}
public node main {
    set_engine(gen_engine())
    set_vehicle(gen_vehicle())
    set_transmission(gen_transmission())
}""")
    return "\n".join(L) + "\n"


def write(name, gap=None, tag=""):
    s = SPECS[name]
    d = os.path.join(ASSETS, "engines", "moretuning", "gen")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, f"{name}{tag}.mr"), "w").write(script(name, s, gap))
    entry = f"mt_gen_{name}{tag}.mr"
    open(os.path.join(ASSETS, entry), "w").write(f'import "engine_sim.mr"\nimport "themes/default.mr"\nimport "engines/moretuning/gen/{name}{tag}.mr"\n\nuse_default_theme()\nmain()\n')
    return entry


def free_idle(name, gap):
    """rpm the engine settles at with the throttle shut and the idle passage `gap` open (es-render start mode)."""
    import subprocess, tempfile, numpy as np
    entry = write(name, gap, tag="_cal")
    es = r"D:\MT\engine-sim\build"
    with tempfile.TemporaryDirectory() as t:
        thr, out = os.path.join(t, "thr.csv"), os.path.join(t, "cal.wav")
        open(thr, "w").write("0,0\n99,0")
        subprocess.run([os.path.join(es, "Release", "es-render.exe"), f"../assets/{entry}", out, "start", thr, "6", "0.4", "1.8"],
                       cwd=es, capture_output=True, timeout=3000, env=dict(os.environ, ES_JITTER="0.05"))
        log = np.loadtxt(out + ".rpm.csv", delimiter=",")
    return float(log[log[:, 0] > 4.5, 1].mean())


def calibrate_idle(name, steps=8):
    """Bisect the idle passage (log scale) until the engine idles at its own idle rpm on its own. Scaling the intake
    with size and boost left the diesels holding 160-230 Nm at idle and the trucks running away after a start."""
    import math
    want = SPECS[name]["idle"]
    lo, hi = math.log(1e-5), math.log(0.05)
    best = None
    for _ in range(steps):
        mid = (lo + hi) / 2
        rpm = free_idle(name, math.exp(mid))
        if best is None or abs(rpm - want) < abs(best[1] - want):
            best = (math.exp(mid), rpm)
        if rpm < want:
            lo = mid
        else:
            hi = mid
    for f in (os.path.join(ASSETS, "engines", "moretuning", "gen", f"{name}_cal.mr"), os.path.join(ASSETS, f"mt_gen_{name}_cal.mr")):
        if os.path.exists(f):
            os.remove(f)
    return name, best[0], best[1]


if __name__ == "__main__":
    if sys.argv[1:] == ["demo"]:
        # the Carrera GT's own layout reproduced: 68 deg V10, bank B fires 68 deg after A on the same pin
        cgt = dict(kind="car", cyl=10, layout=("v", 68), banks=odd_a(10), fo=[1, 2, 3, 4, 7, 8, 9, 10, 5, 6], bore=98, stroke=76, cr=12, idle=1000, top=8400, ir="minimal_muffling_01", cam=CAR_CAM)
        cgt["fo"] = [1, 2, 3, 4, 7, 8, 9, 10, 5, 6]
        cs = cylinders(cgt)
        assert len({round(f, 3) for c, b, f in cs}) == 10
        # a two-stroke six fires every 60 deg: 12 model events evenly spaced over the cycle
        ds = sorted(f for c, b, f in cylinders(SPECS["dd671"]))
        assert all(abs((b - a) - 60) < 1e-9 for a, b in zip(ds, ds[1:])), ds
        # crossplane V8: 4 distinct pins; flat-plane: 2
        def pins(s): return len({round(a, 2) for a, i in journals(s)})
        assert pins(SPECS["sbc350"]) == 4 and pins(SPECS["voodoo"]) == 2, (pins(SPECS["sbc350"]), pins(SPECS["voodoo"]))
        print("demo ok")
    elif sys.argv[1:2] == ["calibrate"]:
        import json
        from concurrent.futures import ThreadPoolExecutor
        names = sys.argv[2:] or list(SPECS)
        try:
            cal = json.load(open(CALIB))
        except (OSError, ValueError):
            cal = {}
        with ThreadPoolExecutor(8) as ex:
            for n, gap, rpm in ex.map(calibrate_idle, names):
                cal[n] = gap
                print(f"{n}: idle passage {gap:.6f} -> free idle {rpm:.0f} rpm (want {SPECS[n]['idle']})", flush=True)
        json.dump(cal, open(CALIB, "w"), indent=1)
    else:
        for n in sys.argv[1:] or SPECS:
            print(n, "->", write(n))
