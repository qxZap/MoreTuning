# MoreTuning 2.8

Updated for Motor Town 0.7.19.

## Fixed

- **Works again on 0.7.19.** The game changed how part tables reference their
  assets; every table in the mod had stopped loading. Engines, transmissions,
  LSDs, aero and tuning parts are all back.
- **Jake brakes are audible.** 90 engines had their sound cues wired to the
  wrong slots — the jake brake played nothing, the intake played the jake brake,
  and backfire played the intake.
- **Detroit 4-71 no longer stalls** the moment you start it.
- **RB26 no longer locks the driven wheels** when you lift off. Engine braking
  was up to 15x what it should be. Swept every engine for the same fault and
  retuned 17.
- **Allison 4700 RDS** had R and R2 the wrong way round.
- **Eaton Fuller RTLO-22918B** now uses the game's proper 18-speed shift model
  with range and splitter, instead of 18 sequential gears.

## New

25 engines.

- **Trucks** — Cummins N14 (370 / 435 / 525 Red Top), CAT C18 (550 / 650 / 800
  ACERT), Detroit Diesel 4-71. Straight-pipe versions of the N14 525 and C18 800.
- **Cars** — VW VR6 2.8 / 3.2 / Turbo, BMW S70/2 V12 and GTR.
- **LS family** — LS6, LS3, LS7, LSA, LS9.
- **Race** — Ferrari F138, Ferrari SF-23, Lotus 98T, Lotus T125 Exos. These need
  Racer level.
- **Silly** — Detroit Diesel 16V-149TI (1800hp) and 20V-149TI (2500hp). Two-stroke
  V16 and V20. Priced accordingly.

## Changed

- **Any engine fits any vehicle.** Vanilla engines still had their vehicle
  restrictions; they don't now. Kart engine in a semi if you want.
- **Licences have no vehicle requirements.**

## Other paks

- **xNoLimits** — any aero part or headlight on any car. Parts that were called
  "#1", "#2" now use real names, since every car lists all of them.
- **yCarbon** — carbon versions of the body parts.
- **ZZb WheelWorks Carbon** — compatibility pak for Maja's Mo Wheel Works.
  Install it if you run both, or the two mods overwrite each other's wheels.
