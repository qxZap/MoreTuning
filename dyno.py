import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# =============================================================================
#  PASTE YOUR UASSETAPI VALUES HERE
# =============================================================================
PARAMS = {
    # --- Core physics (required) ---
    "MaxTorque":              23000000.0,   # Internal sim torque
    "MaxRPM":                 2600.0,
    "FrictionCoulombCoeff":   3000000.0,   # Static friction
    "FrictionViscosityCoeff": 7000.0,      # Dynamic friction (scales with RPM)

    # --- Real-world reference (used to scale sim units → Nm / HP) ---
    "KnownHP":  466.4,
    "KnownNM":  2237.6,

    # --- Extra info (displayed in title / annotations, not used in math) ---
    "StarterTorque":     3000000.0,
    "StarterRPM":        1500.0,
    "Inertia":           90000.0,
    "FuelType":          "Diesel",
    "EngineType":        "Large",
    "FuelConsumption":   370.0,            # L/h
    "MaxJakeBrakeStep":  3,
    "IdleThrottle":      0.017,
}
# =============================================================================

N = 1000   # curve resolution — increase for smoother, decrease if slow

# --- Build RPM axis ---
rpm = np.linspace(0, PARAMS["MaxRPM"], N)

# --- Net torque: gross minus static + dynamic friction ---
net_torque_raw = (
    PARAMS["MaxTorque"]
    - PARAMS["FrictionCoulombCoeff"]
    - PARAMS["FrictionViscosityCoeff"] * rpm
)
net_torque_raw = np.maximum(net_torque_raw, 0)

# --- Internal power (sim units) ---
power_raw = net_torque_raw * rpm

# --- Scale to real-world units ---
peak_raw_torque = np.max(net_torque_raw)
peak_raw_power  = np.max(power_raw)

nm_scale = PARAMS["KnownNM"] / peak_raw_torque
hp_scale = PARAMS["KnownHP"] / peak_raw_power

torque_nm = net_torque_raw * nm_scale
hp        = power_raw      * hp_scale

# --- Peak detection ---
peak_hp_idx     = np.argmax(hp)
peak_torque_idx = np.argmax(torque_nm)

peak_hp         = hp[peak_hp_idx]
peak_hp_rpm     = rpm[peak_hp_idx]
peak_torque_nm  = torque_nm[peak_torque_idx]
peak_torque_rpm = rpm[peak_torque_idx]

# --- Console summary ---
print("=" * 40)
print(f"  {PARAMS['EngineType']} {PARAMS['FuelType']} Engine")
print("=" * 40)
print(f"  Peak Torque : {peak_torque_nm:.1f} Nm  @ {peak_torque_rpm:.0f} RPM")
print(f"  Peak Power  : {peak_hp:.1f} HP    @ {peak_hp_rpm:.0f} RPM")
print(f"  Redline     : {PARAMS['MaxRPM']:.0f} RPM")
print(f"  Inertia     : {PARAMS['Inertia']}")
print(f"  Fuel use    : {PARAMS['FuelConsumption']} L/h")
print(f"  Jake brake  : {PARAMS['MaxJakeBrakeStep']} steps")
print("=" * 40)

# =============================================================================
#  PLOT
# =============================================================================
fig, ax1 = plt.subplots(figsize=(12, 6))
fig.patch.set_facecolor("#1a1a2e")
ax1.set_facecolor("#16213e")

COLOR_TORQUE = "#f97316"   # orange
COLOR_HP     = "#3b82f6"   # blue
COLOR_GRID   = "#2a2a4a"
COLOR_TEXT   = "#e2e8f0"

# --- Torque curve ---
ax1.plot(rpm, torque_nm, color=COLOR_TORQUE, linewidth=2.5, label="Torque (Nm)", zorder=3)
ax1.set_xlabel("Engine RPM", color=COLOR_TEXT, fontsize=11)
ax1.set_ylabel("Torque (Nm)", color=COLOR_TORQUE, fontsize=11)
ax1.tick_params(axis="y", labelcolor=COLOR_TORQUE)
ax1.tick_params(axis="x", labelcolor=COLOR_TEXT)
ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:.0f}"))

# Peak torque marker
ax1.axvline(peak_torque_rpm, color=COLOR_TORQUE, linewidth=0.8, linestyle="--", alpha=0.5)
ax1.annotate(
    f"{peak_torque_nm:.0f} Nm\n@ {peak_torque_rpm:.0f} RPM",
    xy=(peak_torque_rpm, peak_torque_nm),
    xytext=(peak_torque_rpm - 350, peak_torque_nm - 100),
    color=COLOR_TORQUE,
    fontsize=9,
    arrowprops=dict(arrowstyle="->", color=COLOR_TORQUE, lw=1.2),
)

# --- HP curve (second axis) ---
ax2 = ax1.twinx()
ax2.plot(rpm, hp, color=COLOR_HP, linewidth=2.5, label="Power (HP)", zorder=3)
ax2.set_ylabel("Horsepower (HP)", color=COLOR_HP, fontsize=11)
ax2.tick_params(axis="y", labelcolor=COLOR_HP)
ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:.0f}"))
ax2.set_facecolor("none")

# Peak HP marker
ax2.axvline(peak_hp_rpm, color=COLOR_HP, linewidth=0.8, linestyle="--", alpha=0.5)
ax2.annotate(
    f"{peak_hp:.0f} HP\n@ {peak_hp_rpm:.0f} RPM",
    xy=(peak_hp_rpm, peak_hp),
    xytext=(peak_hp_rpm + 80, peak_hp - 60),
    color=COLOR_HP,
    fontsize=9,
    arrowprops=dict(arrowstyle="->", color=COLOR_HP, lw=1.2),
)

# --- Grid and styling ---
ax1.grid(True, color=COLOR_GRID, linewidth=0.6, zorder=0)
for spine in ax1.spines.values():
    spine.set_edgecolor("#334155")
for spine in ax2.spines.values():
    spine.set_edgecolor("#334155")

# --- Title and legend ---
plt.title(
    f"Dyno — {PARAMS['EngineType']} {PARAMS['FuelType']}  "
    f"| {peak_hp:.0f} HP / {peak_torque_nm:.0f} Nm",
    color=COLOR_TEXT,
    fontsize=13,
    pad=12,
)

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
legend = ax1.legend(
    lines1 + lines2,
    labels1 + labels2,
    loc="lower right",
    facecolor="#1e293b",
    edgecolor="#334155",
    labelcolor=COLOR_TEXT,
    fontsize=10,
)

plt.tight_layout()
# plt.savefig("dyno_output.png", dpi=150, bbox_inches="tight")
plt.show()