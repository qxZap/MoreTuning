# MoreTuning

Motor Town tuning mods and the tooling that builds them.

`qxZap_MoreTuning_P` is the main mod: extra engines, transmissions, LSDs, aero
and tuning parts, with vehicle and licence requirements stripped.
`qxZap_MoreTuning_xNoLimits_P` drops the per-car lock so any aero part or
headlight fits any vehicle. `qxZap_MoreTuning_yCarbon_P` adds carbon-fibre
variants of the body parts. `ZZb_qxZap_MoreTuning_yWheelWorksCarbon_P` is the
compat pak for Maja's Mo Wheel Works: her wheel table plus our carbon variants,
mounted after both. The other `*_P` folders are companion/variant mods. Each is an unpacked pak tree;
`modp.bat <ModFolder>` packs one with `repak` and copies it into the game.

## Requires Maja's Motor Works

MoreTuning is built on **Maja's Motor Works** and ships its content — install it
too. Without it you lose the parts it adds (the trailer hitch hook and two
winches) and the tuning it applies to the vanilla tables.

## Current state - game 0.7.19

0.7.19 changed how part tables reference their assets (hard imports -> soft
object paths), which broke every table the mod ships. All of them have been
migrated and verified:

| Table | Rows | |
|---|---|---|
| Engines | 163 | 36 vanilla + 127 mod |
| Transmissions | 122 | 23 vanilla + 99 mod |
| LSD | 7 | 6 vanilla + 1 mod |
| AeroParts | 394 | 387 vanilla + 7 mod |
| VehicleParts0 | 320 | 45 vanilla + 275 mod |
| License x3 | 10 | vanilla, requirements stripped |

The NoLimits pak carries AeroParts 394 rows and Headlights 6, every vehicle
restriction removed. The carbon pak carries AeroParts 780 rows (386 carbon),
Wheels 186 (93 carbon), Headlights 12 (6 carbon).

The part `.uasset` files themselves were unaffected.

## Rebuilding after a game update

1. Export the new build with FModel to `D:\MT\Output\Exports`.
2. Dump a fresh `.usmap` into `%LOCALAPPDATA%\UAssetGUI\Mappings\`, then in
   `Rebase/rebuild.py` set `CURRENT_MAPPINGS` to it and `PREVIOUS_MAPPINGS` to
   the one the mod folder was last built with.
3. Run the three row tools **in order** - each undoes part of the previous one
   if run out of sequence:

   ```
   python Rebase/rebuild.py            # rebase onto the new vanilla
   python Rebase/compat.py             # fold Maja's Motor Works in
   python RemoveReq/run.py             # strip vehicle/licence requirements
   python RemoveReq/run.py --nolimits  # any body part on any car -> xNoLimits pak
   python CarbonParts/run.py           # carbon variants -> yCarbon pak
   python CarbonParts/run.py --wheelworks   # Maja Wheel Works compat -> ZZb pak
   ```

4. `modp.bat` each of `qxZap_MoreTuning_P`, `qxZap_MoreTuning_xNoLimits_P`,
   `qxZap_MoreTuning_yCarbon_P`, `ZZb_qxZap_MoreTuning_yWheelWorksCarbon_P`. Pak names set load order (alphabetical, last
   wins), which is what the `x`/`y` prefixes are for.

Adding parts rather than migrating:

- Transmissions - add an entry to `TransmissionGenerator/tras_s.json`, run
  `transmissions.bat`.
- EV engines - add an entry to `ElectricMotors/motors.json`, run
  `ElectricMotors/run.py`.

`AGENTS.md` has the details: which UAssetGUI build to use, why it fails without
saying anything, and the FName rules that decide whether a table loads at all.

## Install

Drop the `.pak` into `...\Motor Town\MotorTown\Content\Paks`.
