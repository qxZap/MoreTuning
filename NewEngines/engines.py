"""What to add to the engine list, and the rules the existing list already follows.

Everything here was read back off the shipped table rather than invented -- the
cost and level formulas reproduce the existing rows, so new engines land in the
same economy. See AGENTS.md.

    cost                      level requirement
    bike    HP * 187.5        CL_Driver = cost / 300
    car     HP * 125          CL_Driver = HP / 13.2
    racer   bespoke           CL_Racer  = HP / 50
    truck   HP * 166.67       CL_Truck  = HP / 5.4

Torque is the rule of three off a reference engine that already sounds and
drives right, so power lands where it should:

    MaxTorque = ref.MaxTorque * (HP / ref.HP) * (ref.MaxRPM / MaxRPM)
"""

# Reference engines to scale from: (asset, HP, MaxRPM, MaxTorque, Inertia, Fuel)
REFS = {
    "truck": ("CumminsX15x605", 605, 2300.0, 30668788.0, 47000.0, 195.0),
    "car":   ("50coyote",       460, 6500.0,  6117020.0,  5000.0, 140.0),
    "v12":   ("F120A",          471, 7000.0,  6130109.0,  6000.0, 239.0),
    "f1":    ("HONDAV10F1",    1050, 21000.0, 4461674.0,  1000.0, 475.0),
}


def torque(ref, hp, rpm):
    _, ref_hp, ref_rpm, ref_torque, _, _ = REFS[ref]
    return round(ref_torque * (hp / ref_hp) * (ref_rpm / rpm))


def cost(family, hp):
    return round(hp * {"bike": 187.5, "car": 125, "truck": 500 / 3}[family])


def level(family, hp, price=None):
    """(class, level) -- the existing rows' own rule for each tier."""
    if family == "bike":
        return "CL_Driver", max(1, round(cost("bike", hp) / 300))
    if family == "car":
        return "CL_Driver", max(1, round(hp / 13.2))
    if family == "racer":
        return "CL_Racer", max(1, round(hp / 50))
    return "CL_Truck", max(1, round(hp / 5.4))


# --- the new engines -------------------------------------------------------
#
# sound   folder under Cars/Parts/Engine/Sound (waves come from the cooked project)
# cue     which stock cue to clone: "truck" (Truck_04_* + jake) or "car" (idle/mid/high)
# pitch   cue PitchMultiplier -- below 1.0 reads as more displacement
# volume  cue VolumeMultiplier -- stock cues sit at 0.5
# after   the row this one slots in behind, so the list stays grouped
#
# The LS family is one wave set voiced five ways: an LS6 is a smaller-bore LS3
# and sits slightly brighter, an LS7 is 7.0 litres and sits lower and louder,
# the blown LSA/LS9 lower still.
ENGINES = [
    # --- truck diesels, in among the other big straight-sixes ---------------
    dict(key="N14_370HP", name="Cummins N14 370HP", sound="N14", cue="truck",
         family="truck", hp=370, rpm=2100.0, inertia=50000.0, mass=1180.0,
         after="PACCARxMXx13x455HP"),
    dict(key="N14_435HP", name="Cummins N14 435HP", sound="N14", cue="truck",
         family="truck", hp=435, rpm=2100.0, inertia=50000.0, mass=1200.0,
         after="N14_370HP"),
    dict(key="N14_525HP", name="Cummins N14 525HP Red Top", sound="N14", cue="truck",
         family="truck", hp=525, rpm=2100.0, inertia=52000.0, mass=1220.0,
         after="N14_435HP"),
    dict(key="N14_525HPs", name="Cummins N14 525HP Straight Pipe", sound="N14", cue="truck",
         family="truck", hp=525, rpm=2100.0, inertia=52000.0, mass=1210.0,
         volume=0.575, extra_cost=10000, after="N14_525HP"),

    dict(key="C18_550HP", name="CAT C18 550HP", sound="C18", cue="truck",
         family="truck", hp=550, rpm=2100.0, inertia=60000.0, mass=1400.0,
         after="N14_525HPs"),
    dict(key="C18_650HP", name="CAT C18 650HP", sound="C18", cue="truck",
         family="truck", hp=650, rpm=2100.0, inertia=62000.0, mass=1430.0,
         after="C18_550HP"),
    dict(key="C18_800HP", name="CAT C18 ACERT 800HP", sound="C18", cue="truck",
         family="truck", hp=800, rpm=2100.0, inertia=65000.0, mass=1460.0,
         after="C18_650HP"),
    dict(key="C18_800HPs", name="CAT C18 ACERT 800HP Straight Pipe", sound="C18", cue="truck",
         family="truck", hp=800, rpm=2100.0, inertia=65000.0, mass=1450.0,
         volume=0.575, extra_cost=10000, after="C18_800HP"),

    # A 4-71 is a 4.6 litre four out of a 1940s bus. It belongs at the bottom
    # of the truck list, not with the modern iron.
    dict(key="DD471_130HP", name="Detroit Diesel 4-71 130HP", sound="DD471", cue="truck",
         family="truck", hp=130, rpm=2200.0, inertia=15000.0, mass=680.0,
         pitch=1.08, after="CATC12490HP"),

    # Two-stroke V16 and V20 marine/genset blocks. Priced against DV27K, which
    # is the existing "absurd" tier, not against a road engine.
    dict(key="DD16V149_1800HP", name="Detroit Diesel 16V-149TI 1800HP", sound="DD16V149",
         cue="truck", family="truck", hp=1800, rpm=2100.0, inertia=120000.0, mass=2900.0,
         pitch=0.92, volume=0.55, price=2800000, lvl=("CL_Truck", 480),
         after="DV27K1500HP"),
    dict(key="DD20V149_2500HP", name="Detroit Diesel 20V-149TI 2500HP", sound="DD20V149",
         cue="truck", family="truck", hp=2500, rpm=2100.0, inertia=150000.0, mass=3600.0,
         pitch=0.88, volume=0.575, price=6500000, lvl=("CL_Truck", 900),
         after="DD16V149_1800HP"),

    # --- car petrol --------------------------------------------------------
    dict(key="VR6_190HP", name="VW VR6 2.8 190HP", sound="vr6", cue="car",
         family="car", hp=190, rpm=6000.0, inertia=3800.0, mass=165.0,
         after="SR20DET"),
    dict(key="VR6_240HP", name="VW VR6 3.2 240HP", sound="vr6", cue="car",
         family="car", hp=240, rpm=6500.0, inertia=4000.0, mass=172.0,
         pitch=0.98, after="VR6_190HP"),
    dict(key="VR6T_400HP", name="VW VR6 Turbo 400HP", sound="vr6", cue="car",
         family="car", hp=400, rpm=6500.0, inertia=4200.0, mass=185.0,
         pitch=0.96, volume=0.55, after="VR6_240HP"),

    dict(key="LS6_405HP", name="Chevy LS6 5.7 405HP", sound="LS3", cue="car",
         family="car", hp=405, rpm=6000.0, inertia=4800.0, mass=200.0,
         pitch=1.06, after="L86"),
    dict(key="LS3_430HP", name="Chevy LS3 6.2 430HP", sound="LS3", cue="car",
         family="car", hp=430, rpm=6600.0, inertia=5000.0, mass=205.0,
         after="LS6_405HP"),
    dict(key="LS7_505HP", name="Chevy LS7 7.0 505HP", sound="LS3", cue="car",
         family="car", hp=505, rpm=7000.0, inertia=5200.0, mass=210.0,
         pitch=0.94, volume=0.55, after="LS3_430HP"),
    dict(key="LSA_556HP", name="Chevy LSA 6.2 Supercharged 556HP", sound="LS3", cue="car",
         family="car", hp=556, rpm=6100.0, inertia=5400.0, mass=225.0,
         pitch=0.97, volume=0.55, after="LS7_505HP"),
    dict(key="LS9_638HP", name="Chevy LS9 6.2 Supercharged 638HP", sound="LS3", cue="car",
         family="car", hp=638, rpm=6500.0, inertia=5600.0, mass=232.0,
         pitch=0.92, volume=0.575, after="LSA_556HP"),

    dict(key="S702_618HP", name="BMW S70/2 V12 618HP", sound="S702", cue="car",
         family="car", ref="v12", hp=618, rpm=7400.0, inertia=6000.0, mass=266.0,
         after="S63B44B"),
    dict(key="S702GTR_680HP", name="BMW S70/2 GTR V12 680HP", sound="S702", cue="car",
         family="racer", ref="v12", hp=680, rpm=7500.0, inertia=6000.0, mass=252.0,
         price=340000, volume=0.575, after="S702_618HP"),

    # --- race engines, in with the other exotics ---------------------------
    dict(key="L98T_1000HP", name="Lotus 98T 1.5 V6 Turbo 1000HP", sound="l98t", cue="car",
         family="racer", ref="f1", hp=1000, rpm=12500.0, inertia=1400.0, mass=145.0,
         price=1150000, after="laferrariV12"),
    dict(key="F138_750HP", name="Ferrari F138 2.4 V8 750HP", sound="f138", cue="car",
         family="racer", ref="f1", hp=750, rpm=18000.0, inertia=950.0, mass=95.0,
         price=980000, after="L98T_1000HP"),
    dict(key="L125S1_950HP", name="Lotus T125 Exos 950HP", sound="l125s1", cue="car",
         family="racer", ref="f1", hp=950, rpm=18000.0, inertia=1000.0, mass=105.0,
         price=1180000, after="F138_750HP"),
    dict(key="SF23_1000HP", name="Ferrari SF-23 1.6 V6 Hybrid 1000HP", sound="sf23", cue="car",
         family="racer", ref="f1", hp=1000, rpm=15000.0, inertia=1100.0, mass=130.0,
         price=1450000, after="L125S1_950HP"),
]


def resolve(spec):
    """Fill in torque, cost and level from the rules unless the spec overrides."""
    out = dict(spec)
    out.setdefault("ref", "truck" if spec["family"] == "truck" else "car")
    out["torque"] = float(spec.get("torque") or torque(out["ref"], spec["hp"], spec["rpm"]))
    out["cost"] = spec.get("price") or cost(spec["family"], spec["hp"])
    out["cost"] += spec.get("extra_cost", 0)
    out["level"] = spec.get("lvl") or level(spec["family"], spec["hp"])
    out["fuel"] = float(spec.get("fuel") or round(spec["hp"] / 3))
    out["pitch"] = spec.get("pitch")
    out["volume"] = spec.get("volume")
    return out


if __name__ == "__main__":
    # The formulas have to reproduce rows that already ship, or the new engines
    # will not sit in the same economy.
    assert cost("car", 460) == 57500          # 50coyote
    assert cost("car", 707) == 88375          # HemiHellcat
    assert cost("truck", 600) == 100000       # Detroit DD16
    assert cost("truck", 770) == 128333       # Scania DC16 770
    assert cost("bike", 120) == 22500         # Honda CBR600rr
    assert level("car", 320) == ("CL_Driver", 24)     # 2JZ 320HP
    assert level("car", 707) == ("CL_Driver", 54)     # HemiHellcat
    assert level("racer", 1050) == ("CL_Racer", 21)   # Honda F1 V10
    assert level("racer", 1600) == ("CL_Racer", 32)   # Bugatti W16
    assert level("truck", 605) == ("CL_Truck", 112)   # Cummins X15 605
    assert level("truck", 800) == ("CL_Truck", 148)   # Weichai WP17H
    # rule of three against the engine it scales from
    assert torque("truck", 605, 2300.0) == 30668788
    assert torque("f1", 1050, 21000.0) == 4461674

    print(f"{'key':22} {'HP':>5} {'RPM':>7} {'MaxTorque':>12} {'cost':>9} {'level':>18}")
    for spec in ENGINES:
        e = resolve(spec)
        print(f"{e['key']:22} {e['hp']:5} {e['rpm']:7.0f} {e['torque']:12.0f} "
              f"{e['cost']:9} {e['level'][0] + ':' + str(e['level'][1]):>18}")
    print(f"\n{len(ENGINES)} engines")
