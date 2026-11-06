# New engines with synthesised sounds: stats

Real figures are from memory of published specs. Check them before shipping. In-game values use the
rule of three against engines already in the game:

- Cars: torque x 9,560 per real Nm (LS3 9,794, 2JZ 9,321), price $125 per hp (LS3, 2JZ, Hemi 392, RB26 all exactly 125).
- Pickup diesels: torque x 10,000 per Nm (59 Cummins), $125 per hp (Duramax 445 hp = $55,625).
- Trucks and buses: torque x 12,000 per Nm (C18 12,175, N14 11,874), $166.67 per hp (N14, C18, DD16, C12, DD 4-71).

Sound: `FlatEngines/` (see COOKED.md once cooked). Stock turbo is what to match the turbo part to.

| Row | Engine | Class | HP | Nm | Rev limit | kg | Stock turbo | MaxTorque | Price |
|---|---|---|---:|---:|---:|---:|---|---:|---:|
| type1 | VW Type 1 1600 (Beetle) | car | 50 | 108 | 4500 | 115 | - | 1,032,480 | $6,250 |
| 4age | Toyota 4A-GE 16V (AE86) | car | 128 | 149 | 7600 | 120 | - | 1,424,440 | $16,000 |
| 4g63t | Mitsubishi 4G63T (Evo IX) | car | 286 | 392 | 7000 | 170 | TD05HRA, ~1.4 bar | 3,747,520 | $35,750 |
| rs3five | Audi 2.5 TFSI (RS3 8Y) | car | 400 | 500 | 7000 | 160 | single turbo, ~1.4 bar | 4,780,000 | $50,000 |
| s65 | BMW S65 4.0 V8 (E92 M3) | car | 414 | 400 | 8400 | 202 | - | 3,824,000 | $51,750 |
| voodoo | Ford Voodoo 5.2 flat-plane (GT350) | car | 526 | 582 | 8250 | 200 | - | 5,563,920 | $65,750 |
| cgtv10 | Porsche Carrera GT 5.7 V10 | car | 612 | 590 | 8400 | 214 | - | 5,640,400 | $76,500 |
| sbc350 | Chevrolet small-block 350 (ZZ4) | car | 355 | 549 | 5600 | 260 | - | 5,248,440 | $44,375 |
| hemi426 | Chrysler 426 Street Hemi | car | 425 | 664 | 6000 | 350 | - | 6,347,840 | $53,125 |
| 12v | Cummins 5.9 12-valve P-pump | pickup | 215 | 597 | 3000 | 500 | Holset HX35W, ~1.4 bar | 5,970,000 | $26,875 |
| vp44 | Cummins 5.9 VP44 24-valve | pickup | 245 | 685 | 3200 | 500 | Holset HY35W, ~1.4 bar | 6,850,000 | $30,625 |
| cummins67 | Cummins 6.7 (2019 HO) | pickup | 400 | 1356 | 3200 | 520 | Holset VGT, ~2.2 bar | 13,560,000 | $50,000 |
| ps60 | Ford 6.0 Power Stroke | pickup | 325 | 773 | 3800 | 440 | Garrett VGT, ~2.0 bar | 7,730,000 | $40,625 |
| ntc400 | Cummins NTC 400 Big Cam | truck | 400 | 1559 | 2300 | 1300 | Holset, ~1.6 bar | 18,708,000 | $66,668 |
| isx15 | Cummins ISX15 500 | truck | 500 | 2508 | 2100 | 1320 | Holset VGT, ~2.5 bar | 30,096,000 | $83,335 |
| isx15 | Cummins ISX15 600 | truck | 600 | 2779 | 2100 | 1320 | Holset VGT, ~2.7 bar | 33,348,000 | $100,002 |
| c16 | CAT C16 550 | truck | 550 | 2508 | 2200 | 1300 | CAT, ~2.4 bar | 30,096,000 | $91,668 |
| c16 | CAT C16 600 | truck | 600 | 2508 | 2200 | 1300 | CAT, ~2.6 bar | 30,096,000 | $100,002 |
| macke6 | Mack E6 350 | truck | 350 | 1735 | 2100 | 1100 | ~1.6 bar | 20,820,000 | $58,334 |
| mp8 | Mack MP8 505 | truck | 505 | 2386 | 2100 | 1200 | VGT, ~2.5 bar | 28,632,000 | $84,168 |
| 6ct | Cummins 6CT 8.3 240 (bus) | truck | 240 | 908 | 2500 | 610 | Holset, ~1.6 bar | 10,896,000 | $40,001 |
| 6ct | Cummins 6CT 8.3 300 (bus) | truck | 300 | 1085 | 2500 | 610 | Holset, ~1.8 bar | 13,020,000 | $50,001 |
| 6ct | Cummins 6CT 8.3 350 (bus) | truck | 350 | 1288 | 2500 | 610 | Holset, ~2.0 bar | 15,456,000 | $58,334 |
| 6ct | Cummins 6CT 8.3 400 (bus) | truck | 400 | 1458 | 2500 | 610 | Holset, ~2.2 bar | 17,496,000 | $66,668 |
| dd671 | Detroit 6-71 two-stroke | truck | 238 | 827 | 2300 | 900 | - (Roots blower) | 9,924,000 | $39,667 |
| dd871 | Detroit 8-71 two-stroke V8 | truck | 318 | 1125 | 2300 | 1050 | - (Roots blower) | 13,500,000 | $53,001 |
| dd1271 | Detroit 12-71 two-stroke V12 | truck | 475 | 1681 | 2300 | 1500 | - (Roots blower) | 20,172,000 | $79,168 |
| dd1671 | Detroit 16-71 two-stroke V16 | truck | 635 | 2237 | 2300 | 1900 | - (Roots blower) | 26,844,000 | $105,835 |
| series60 | Detroit Series 60 14L | truck | 515 | 2237 | 2100 | 1200 | Garrett, ~2.3 bar | 26,844,000 | $85,835 |
| cat3406e | CAT 3406E 475 | truck | 475 | 2237 | 2100 | 1300 | ~2.2 bar | 26,844,000 | $79,168 |
| macke9 | Mack E9 V8 500 | truck | 500 | 2373 | 2100 | 1450 | ~2.2 bar | 28,476,000 | $83,335 |
| om502 | Mercedes OM502 LA V8 (Actros) | truck | 630 | 3000 | 1900 | 1150 | twin turbo, ~2.5 bar | 36,000,000 | $105,002 |
| 8v92 | Detroit 8V92TA two-stroke V8 | truck | 450 | 1830 | 2100 | 1150 | turbo + Roots blower | 21,960,000 | $75,002 |
