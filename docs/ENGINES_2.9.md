# MoreTuning 2.9 engine plan

Stats for the engines planned for 2.9, ready for when sounds are found. Figures come from memory
of published specs, not checked against a source, so confirm them before they ship.

`MaxTorque` in an engine asset is newton-metres times 10,000. `MaxRPM` is the rev limit, a little
over the rated speed. All of these are `FuelType` Diesel. Every engine takes `HeatingPower` 1.0 and
`CoolingEfficiency` 2.5 (`EngineCooling/run.py`).

Variants are listed where the engine shipped in several ratings, as with the X15 entries.

## Trucks

| Engine | Row name | HP | ft-lb | Nm | MaxTorque | Rated RPM | MaxRPM | Type |
|---|---|---|---:|---:|---:|---:|---:|---|
| Cummins NTC 14L (Big Cam) | CumminsNTC_400HP | 400 | 1150 | 1559 | 15590000 | 2100 | 2300 | Large |
| Cummins ISX15 | CumminsISX15_500HP | 500 | 1850 | 2508 | 25080000 | 1800 | 2100 | Large |
| Cummins ISX15 (top rating) | CumminsISX15_600HP | 600 | 2050 | 2779 | 27790000 | 1800 | 2100 | Large |
| CAT C16 | CatC16_550HP | 550 | 1850 | 2508 | 25080000 | 1800 | 2100 | Large |
| CAT C16 (top rating) | CatC16_600HP | 600 | 1850 | 2508 | 25080000 | 2000 | 2200 | Large |
| Mack E6 11L | MackE6_350HP | 350 | 1280 | 1735 | 17350000 | 1800 | 2100 | Large |
| Mack MP8 13L | MackMP8_505HP | 505 | 1760 | 2386 | 23860000 | 1800 | 2100 | Large |

## Cummins 8.3 (6CT), for buses

Range given for the plan: 240-400 hp, 670-1075 ft-lb.

| Engine | Row name | HP | ft-lb | Nm | MaxTorque | Rated RPM | MaxRPM | Type |
|---|---|---|---:|---:|---:|---:|---:|---|
| Cummins 6CT 240 | Cummins6CT_240HP | 240 | 670 | 908 | 9080000 | 2200 | 2500 | Medium |
| Cummins 6CT 300 | Cummins6CT_300HP | 300 | 800 | 1085 | 10850000 | 2200 | 2500 | Medium |
| Cummins 6CT 350 | Cummins6CT_350HP | 350 | 950 | 1288 | 12880000 | 2200 | 2500 | Medium |
| Cummins 6CT 400 | Cummins6CT_400HP | 400 | 1075 | 1458 | 14580000 | 2200 | 2500 | Medium |

The two middle ratings are interpolated from the plan's range.

## Detroit Diesel 71 series (two-stroke)

These rev high for their era and make peak torque early, so give them a flat curve. Two-strokes
want their own sound more than any other entry here.

| Engine | Row name | HP | ft-lb | Nm | MaxTorque | Rated RPM | MaxRPM | Type |
|---|---|---|---:|---:|---:|---:|---:|---|
| DD 6-71 (inline 6, 7.0L) | DD671_238HP | 238 | 610 | 827 | 8270000 | 2100 | 2300 | Medium |
| DD 8-71 (V8, 9.3L) | DD871_318HP | 318 | 830 | 1125 | 11250000 | 2100 | 2300 | Medium |
| DD 12-71 (V12, 14L) | DD1271_475HP | 475 | 1240 | 1681 | 16810000 | 2100 | 2300 | Large |
| DD 16-71 (V16, 18.6L) | DD1671_635HP | 635 | 1650 | 2237 | 22370000 | 2100 | 2300 | Large |

## Cummins 5.9

| Engine | Row name | HP | ft-lb | Nm | MaxTorque | Rated RPM | MaxRPM | Type |
|---|---|---|---:|---:|---:|---:|---:|---|
| 12 valve (P-pump, 6BT) | Cummins12V_215HP | 215 | 440 | 597 | 5970000 | 2500 | 3000 | Medium |
| VP44 (24 valve) | CumminsVP44_245HP | 245 | 505 | 685 | 6850000 | 2700 | 3200 | Medium |

The mod's existing `59cummins` sits at 827 Nm and 3400 RPM, well above these stock figures. So
these two read as stock engines, and `59cummins` is the built one.

## Fix shifter naming

Still to look at. It needs an example of a name that is wrong.
