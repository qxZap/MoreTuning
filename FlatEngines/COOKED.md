# Cooked engine sounds (FlatEngines -> qxZap_MoreTuning_P)

28 new engines, cooked as the game's own per-rpm engine sound (`MTEngineSoundDataAsset`), not as SoundCues.
Since 2026-11-06 all 28 are **real exterior recordings looped ping-pong** (`FlatEngines\recompose\`). The
synthesised loops (in game: quiet, a constant "bee") and the first recorded pilot (short chained grains: a
rhythmic "buzz, buzz" twice a second, and 10-20 dB too quiet) are both gone; their history is further down.

## Recorded sounds, ping-pong (`FlatEngines\recompose\`)

```
cd D:\MT\MoreTuning\FlatEngines\recompose
python -I recompose.py demo                       # self-check on a synthetic engine
python -I recompose.py fetch <key> <yt id>...     # audio only, 48 kHz mono -> src\<key>\, meta.txt
python -I recompose.py analyse <key>              # the segment each step would use (writes nothing)
python -I recompose.py build <key>...             # wavs -> D:\MT\SoundCook\wav\MT_<key>\, levels.json, preview\<key>.mp3
```

Then cook. First delete `D:\MT\SoundCook\MTEngineSounds\Saved\Cooked\Windows\MTEngineSounds\Content\Cars\Parts\Engine\Sound\MT_*`
(a dropped step must leave no stale cooked wave), then run steps 4-8 of Recook below (`ue_import.py`, Cook,
`copy_cooked.py`, `make_data.py`, `loudness.py verify`). Steps 1-3 (`layers.py`, `prep_wavs.py`) are the synth
route; `prep_wavs.py` keeps any `levels.json` entry with `"source": "recording"`, and all 28 are now. Run the
verify as `python -I -c "import sys; sys.path.insert(0, r'D:\MT\MoreTuning\FlatEngines\cook'); import loudness; loudness.verify()"`
(`-I` drops the script folder from the path, so `import buzz` fails otherwise). `build` exits with "no usable
recording" for an engine with fewer than 3 steps and then writes nothing for it -- clear its wav folder by hand
so stale loops are not cooked.

The recipe is the user's: from a real recording take the stretch where the rpm is **as stable as possible** and
loop it forward then reversed. The ends match by construction, so there is no seam and no rhythmic repeat of a
short loop. Per step:

1. **rpm track** per clip: STFT (0.25 s, 50 ms hop, at 8 kHz), whitened, subharmonic summation of 8 firing
   harmonics, Viterbi with a cost on pitch jumps. Firing rate = rpm/60 x cyl/2 with the .esc cylinder count
   (Detroits are modelled there as twice their cylinders).
2. **Candidates**: every run of track frames within 12 % of the step rpm (within 6 % = "found", else "fill");
   inside a run, the steadiest window of 1-3 s (length only breaks ties). Rejected: weak track, firing comb under
   3 dB over the noise between its teeth (speech, music, wind), clipped, an octave off (four-stroke half-order
   test), buzz (`buzz.overtone_ratio`) over +3.5 dB, under 1 s, or **rpm spread over +-3 %**.
3. **Choice: rpm stability first.** Spread = half the 5-95 % range of the tracked rpm over the window, as +- % of
   its median. Score = -400 x spread + 0.3 x length (s, up to 3) + comb contrast / 15 + salience / 10 - 3 x warp,
   so +-1 % of spread outweighs everything else. A wander that the pitch bend straightens still sounds wobbly once
   reversed. The clip that covers most steps gets a small tie-break bonus, so the character holds where it can.
4. **Steps thinned** from the synth's candidate list: idle-most and top-most first, then the rest by score, at
   least 1000 rpm apart (petrol) or 300 (diesel), and never the same stretch (overlapping in time) for two steps,
   which would only be the game's own pitching. A step with no segment is left out; the game pitches between the
   steps it has (`CrossfadeRPMRange` = the smallest step gap, `make_data.py`).
5. **Loop** = the segment time-warped so its firing rate is exactly the step's (pitch bend), then forward +
   reversed (`pingpong`: g + g[-2:0:-1], which wraps back to g[0] the way the reversed run arrives there). The
   resampler's 10 ms edges are trimmed first so the turnarounds are clean. Loops are 2-6.5 s.
6. **Layers**: `Exhaust` = the loop, 25 Hz high-pass. `Engine` = the same loop low-passed at 1.2 kHz,
   **zero-phase** (4th-order Butterworth run forward and back; with its phase shift it partly cancelled the
   exhaust), -4 dB. It measures 4-10 dB under the exhaust in LUFS.
7. **Level**: the exhaust layer is set to its class target at the step's place in the engine's whole rev range
   (the synth step list, not just the kept steps), both layers get the same gain, soft limiter above -6 dBFS,
   peaks under -1 dBFS, repeated until the exhaust is within 0.05 dB. `build` asserts 0.3 dB.

### Level targets (exhaust layer, LUFS at idle / mid / high of the rev range)

| class | target | the user's own SoundCue engines (cooked waves decoded, medians) |
|---|---|---|
| car | -15.5 / -13.5 / -12.5 | LS3, 2jz, 392, 50coyote, L86, GM572, 81bb, lt7, rb26, S63B44B, amg, hv8, kg8, 707: -15.3 / -13.5 / -11.8 |
| pickup (12v, vp44, cummins67, ps60) | -17.0 / -15.0 / -14.5 | 59cummins, 66duramax, 73powerstroke, LightDiesel, 65detroit: -18.5 / -15.0 / -15.1 |
| truck | -17.0 / -15.0 / -14.0 | C18, N14, x15, d13, mx13, dc16, detroit, fh, catc12, DD471: -19.1 / -15.2 / -14.4, plus Truck_04_Exhaust -14.1 |

Those cues scale by 0.5 (SC_LS3_430HP, SC_C18_550HP) or 0.25 (SC_LightDiesel) and back up with rpm/throttle
modulators of up to 3-4x, so the file level is the comparable number. `MasterVolume` on our assets stays at
default. The old targets (vanilla MidDuty/V6Sport EngineSoundData, `ref_lufs.json`, below) were 10-20 dB too
quiet next to those engines. `loudness.py verify` checks each cooked pair against `levels.json` row[1] (the pair
loudness `build` measured), and the buzz on the exhaust layer and the pair -- not on the engine layer alone,
which in the 1.5-6 kHz band of the measure is only its low-pass skirt and reads +5 dB whatever the recording.

### Clips

Searched with `yt-dlp ytsearch` (exterior, straight pipe, idle/rev, pulling, dyno), 20 s - 8 min clips. **Read
the titles**: a search for one engine returns its rivals, compilations, sims and product videos, and the comb and
octave tests cannot tell a 16V71 from a 12V71 or a Mercedes S65 V12 from a BMW S65 V8 (both happened). Clips set
aside are in `src\<key>\excluded\` with the reason in `why.txt`; credits for the used ones in `recompose\SOURCES.md`.

### Result (2026-11-06, cooked waves decoded back)

Every cooked pair within 0.10 dB of `levels.json`; buzz max over all steps +3.7 dB (ps60 1450). Per step, the clip,
time, spread and warp are in `cook\levels.json` (row: rpm, pair want, pair got, peak dBFS, buzz, found/fill,
warp %, loop s, exhaust target, exhaust got, engine layer, `clip t0-t1s@rpm +-spread`). Not yet heard in game.

| engine | class | steps kept | loops | worst spread | exhaust LUFS idle .. top | engine layer | buzz max | clips |
|---|---|---|---|---|---|---|---|---|
| rs3five | car | 850, 2350, 3350, 4350, 5850, 7350 | 2.0-5.9 s | +-2.1 % | -15.5 .. -12.5 | -19.7 .. -18.3 | +2.7 dB | 5 |
| s65 | car | 850, 2350, 8350 | 2.0-3.6 s | +-1.8 % | -15.5 .. -12.8 | -19.5 .. -14.7 | +0.5 dB | 3 |
| voodoo | car | 850, 1850, 3850 | 2.3-5.5 s | +-2.7 % | -15.5 .. -13.9 | -19.6 .. -18.1 | +1.9 dB | 3 |
| cgtv10 | car | 1000, 2000, 3000, 4000, 8000 | 2.1-6.4 s | +-2.9 % | -15.5 .. -12.6 | -19.6 .. -17.2 | +2.9 dB | 5 |
| sbc350 | car | 750, 1750, 2750, 5750 | 2.3-4.0 s | +-1.1 % | -15.5 .. -12.6 | -24.8 .. -15.3 | +0.9 dB | 4 |
| hemi426 | car | 800, 2300, 3300, 4300 | 2.3-3.8 s | +-2.0 % | -15.5 .. -13.2 | -19.6 .. -18.9 | +3.4 dB | 3 |
| 4age | car | 1400, 2900, 3900, 5400, 6400, 7900 | 2.3-6.5 s | +-1.2 % | -15.2 .. -12.5 | -23.7 .. -16.9 | +2.5 dB | 3 |
| 4g63t | car | 1350, 2350, 3350, 4350, 5350 | 2.3-4.9 s | +-0.8 % | -15.2 .. -13.1 | -21.8 .. -21.8 | +1.5 dB | 2 |
| series60 | truck | 600, 900, 1350, 1650 | 2.7-6.0 s | +-0.3 % | -17.0 .. -14.6 | -21.2 .. -19.1 | +0.5 dB | 3 |
| cat3406e | truck | 650, 950, 1250, 1550, 1850, 2150 | 2.0-5.8 s | +-1.5 % | -17.0 .. -14.0 | -21.0 .. -21.4 | +1.5 dB | 4 |
| macke9 | truck | 600, 900, 1200, 1500, 1800 | 2.2-6.2 s | +-2.1 % | -17.0 .. -14.4 | -21.9 .. -19.9 | +0.4 dB | 4 |
| om502 | truck | 600, 900, 1200, 1500, 1800 | 2.0-5.9 s | +-1.1 % | -17.0 .. -14.4 | -24.5 .. -19.1 | +2.9 dB | 3 |
| 8v92 | truck | 550, 1000, 1300, 1900 | 2.1-6.2 s | +-0.0 % | -17.0 .. -14.4 | -21.6 .. -18.8 | +2.0 dB | 3 |
| cummins67 | pickup | 750, 1050, 1350, 1650, 1950, 2250, 3300 | 2.0-2.8 s | +-2.1 % | -17.0 .. -14.5 | -21.5 .. -24.3 | +3.4 dB | 4 |
| ps60 | pickup | 700, 1000, 1450, 1750, 2050, 2500, 2800, 3250, 3850 | 2.1-5.9 s | +-2.1 % | -17.0 .. -14.5 | -24.6 .. -22.8 | +3.7 dB | 5 |
| ntc400 | truck | 600, 1050, 1650, 1950, 2400 | 2.5-6.2 s | +-0.3 % | -17.0 .. -14.0 | -22.3 .. -21.7 | +1.7 dB | 4 |
| isx15 | truck | 600, 900, 1350, 1800, 2100 | 2.2-3.2 s | +-1.1 % | -17.0 .. -14.0 | -22.6 .. -18.1 | +0.8 dB | 2 |
| c16 | truck | 650, 1250, 1700 | 2.2-4.8 s | +-0.8 % | -17.0 .. -14.7 | -21.4 .. -20.8 | +0.5 dB | 2 |
| macke6 | truck | 750, 1050, 1350, 1800 | 2.7-2.9 s | +-0.6 % | -16.6 .. -14.4 | -22.6 .. -23.1 | +0.9 dB | 2 |
| mp8 | truck | 600, 900, 1200, 1500, 1950 | 2.0-2.7 s | +-2.1 % | -17.0 .. -14.3 | -27.8 .. -19.0 | +1.6 dB | 4 |
| 6ct | truck | 650, 950, 1400, 2000, 2450 | 2.0-6.0 s | +-0.5 % | -17.0 .. -14.2 | -23.5 .. -21.7 | +1.1 dB | 3 |
| 12v | pickup | 750, 1050, 1500, 1800, 2100 | 2.0-5.8 s | +-1.4 % | -17.0 .. -14.9 | -21.5 .. -19.2 | +1.1 dB | 4 |
| vp44 | pickup | 750, 1050, 1350 | 2.5-2.7 s | +-1.7 % | -17.0 .. -16.1 | -21.2 .. -20.4 | +0.8 dB | 3 |
| dd671 | truck | 650, 1100, 1400, 1700, 2000 | 2.1-6.4 s | +-2.5 % | -16.7 .. -14.3 | -21.1 .. -18.4 | +3.5 dB | 4 |
| dd871 | truck | 500, 950, 1250, 1850 | 2.2-6.4 s | +-1.3 % | -17.0 .. -14.5 | -21.3 .. -18.6 | +1.1 dB | 2 |
| dd1271 | truck | 500, 950, 1250 | 3.2-6.0 s | +-0.3 % | -17.0 .. -15.3 | -25.2 .. -23.2 | -0.6 dB | 1 |
| dd1671 | truck | 500, 800, 1100, 2300 | 2.3-4.6 s | +-1.9 % | -17.0 .. -14.0 | -21.1 .. -18.1 | +2.9 dB | 3 |
| type1 | car | 900, 2900, 4500 | 2.4-4.6 s | +-0.3 % | -15.5 .. -12.5 | -16.7 .. -18.2 | +1.8 dB | 3 |

Gaps the game pitches across (no steady recording passed): sbc350 2750 -> 5750, s65 2350 -> 8350, voodoo top 3850
(limit 8250), cgtv10 4000 -> 8000, hemi426 top 4300 (limit 6000), vp44 top 1350 (limit 3200), c16 top 1700
(limit 2200), dd1271 top 1250 (limit 2300), dd871 1250 -> 1850, dd1671 1100 -> 2300, 8v92 top 1900.

## The synth, and the chained-grain pilot (history)

The sections from "Buzz" on describe the synth that shipped first. The pilot after it (sbc350, 12v, cat3406e)
chained several grains per step into 0.5-3 s loops closed with a 30 ms crossfade (seam correlation >= 0.3),
levelled to the vanilla targets; in game every 0.5-0.9 s loop read as a rhythmic buzz and all were far too quiet.
Its `levels.json` is `cook\work\levels.chain.json`, the synth's `cook\work\levels.synth.json` (still the source of
the candidate step lists).

## How the game plays an engine

`MHEngineDataAsset` has two ways (read off `MotorTown721T1.usmap`):

- `EnginesSound` -> a **SoundCue**. Older engines (V8, I4Sport, Truck_04/05, Teh's pack). The cue
  reads three parameters the game sets on it: `RPM` (float, rpm), `Throttle` (float 0..1) and
  `Starter` (bool). Crossfades are `SoundNodeParamCrossFade` on `RPM`, pitch is
  `SoundNodeModulatorContinuous` on `RPM`, throttle only scales volume. No load/overrun parameter.
- `EngineSoundData` -> an **`MTEngineSoundDataAsset`** (`/Script/MotorTown`), played natively by
  `MTEngineSoundComponent` (one audio component per layer, `EngineAudioComponents` /
  `ExhaustAudioComponents`). Used by vanilla's newer engines: `MediumDuty_290HP/330HP`
  (`Truck/MidDuty_02`, `MidDuty_03`), `V6Sport_200HP/400HP/DOHC_200HP` (`V6Sport_02..04`).
  Those engine assets leave `EnginesSound` unset.

`MTEngineSoundDataAsset` (all properties; unset ones are serialised as default):

| property | type | vanilla |
|---|---|---|
| `RPMSources` | array of `MTEngineSoundRPMSource { RPM: float, EngineSound: SoundWave, ExhaustSound: SoundWave }` | 5-6 steps |
| `CrossfadeRPMRange` | float | 500 in all five |
| `CrossfadePower` | float | 1.5 in V6Sport_04, default elsewhere |
| `MasterVolume`, `EngineVolumeMultiplier`, `ExhaustVolumeMultiplier` | float | never set |
| `MinPitch`, `MaxPitch` | float | never set |
| `IdleEngineRatio`, `IdleExhaustRatio` | float | 0.83 engine in V6Sport_04, default elsewhere |
| `StarterMotorSound` | SoundWave | `/Game/Cars/Parts/Engine/Sound/Starter` |

`ExhaustSound` may be null (V6Sport_04 has engine layers only). There is no load or overrun
layer, so only on-load renders are used. The layer waves themselves are plain SoundWaves with
`bLooping`, `SoundClassObject = /Game/Sounds/Class_Engine` and
`AttenuationSettings = /Game/Sounds/EngineSoundAttenuation` (vanilla `MidDuty_02/1000rpm_Exhaust`);
with no cue in between, those two references are what put the sound in the engine class (volume
slider, cabin mix) and give it 3D falloff, so ours carry the same two.

## What ours are

Per engine, in `qxZap_MoreTuning_P\MotorTown\Content\Cars\Parts\Engine\Sound\MT_<engine>\`:

- `MT_<engine>_EngineSoundData` (`/Game/Cars/Parts/Engine/Sound/MT_<engine>/MT_<engine>_EngineSoundData`)
  -- the asset an engine part points its `EngineSoundData` at. Everything else at vanilla's
  defaults like 4 of the 5 vanilla sets; `CrossfadeRPMRange` = our step spacing (see below);
  starter = vanilla's `Starter`.
- `MT_<engine>_<rpm>rpm_Engine` / `MT_<engine>_<rpm>rpm_Exhaust` (.uasset/.uexp/.ubulk), one pair per
  rpm step. Mono, 48 kHz, 3.0 s seamless loops, BINKA. Names end in a word, not digits, so no FName
  number suffix anywhere.

The engine layer is the synth's intake + mechanical paths (`exhaust_volume:0`), the exhaust layer
its exhaust path only (`intake_volume:0`, `engine_vibrations_volume:0`). Rendered separately they
sum back to the full render (correlation 0.999 on 4age 4400 rpm).

**Hooking one up** (later, with the part asset): set `EngineSoundData` to the import of
`MT_<engine>_EngineSoundData` (class `MTEngineSoundDataAsset`, package
`/Game/Cars/Parts/Engine/Sound/MT_<engine>/MT_<engine>_EngineSoundData`) and leave `EnginesSound`
null, as vanilla's V6Sport_400HP does. `EngineSounds/run.py` notes the sound slots are shifted
by one in MoreTuning's older engine assets -- check the slot by name, not position.

## Recook

```
D:\MT\MoreTuning\FlatEngines\cook\cook.bat
```

runs, in order (each step can be run alone from `FlatEngines\cook`):

1. `python layers.py` -- writes `FlatEngines\layers\cfg\<engine>_engine.esc` / `_exhaust.esc` from the
   on-load configs (`iconic\cfg\<e>_on.esc`, `diesel\cfg\<e>_on.esc`, `cfg2\type1.esc`) with the
   anti-buzz settings, and renders the missing/stale layers into `layers\anchors\` with
   `enginesound.linux` in Docker:
   `docker run --rm -v D:/MT/MoreTuning/FlatEngines:/w -v D:/MT/MoreTuning/FlatEngines/enginesound.linux:/b/enginesound rust:1 bash /w/layers/render.sh`
   (flags as `render3.sh`: `-h -r <rpm> -l 3+cf/2 -f 240/rpm -w 1.2 -v 1`, same rpm steps as the
   existing anchors). A changed config deletes that engine's renders.
2. `python loudness.py refs` (only if `ref_lufs.json` is missing) -- decodes the references.
3. `python prep_wavs.py` -- firing turbulence, buzz check, loudness levelling, 16-bit PCM into
   `D:\MT\SoundCook\wav\MT_<engine>\`; writes `cook\levels.json`. Exits non-zero if any loop still buzzes.
4. Import: `"D:\Program Files\Epic Games\UE_5.5\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" D:\MT\SoundCook\MTEngineSounds\MTEngineSounds.uproject -run=pythonscript -script=D:\MT\MoreTuning\FlatEngines\cook\ue_import.py -unattended -nosplash -nullrhi`
5. Cook: same exe and project, `-run=Cook -TargetPlatform=Windows -unversioned -unattended -nosplash`
   (exactly the commandlet the user's own `sunete` project runs from the editor's Cook Content).
6. `python copy_cooked.py` -- copies `Saved\Cooked\Windows\MTEngineSounds\Content\Cars\Parts\Engine\Sound\MT_*`
   into the mod and checks every wave (see Verification).
7. `python make_data.py` -- builds the `MTEngineSoundDataAsset`s from vanilla
   `Truck/MidDuty_02/EngineSoundData` as template, writes them with UAssetGUI `fromjson`, reads them back.
8. `python loudness.py verify` -- decodes every shipped wave and checks loudness and buzz.

### The cook project

`D:\MT\SoundCook\MTEngineSounds\` is a minimal UE 5.5 project made for this, not the user's
`C:\Users\Milea\Documents\Unreal Projects\sunete` (left untouched). It carries sunete's
`DefaultEngine.ini` (same audio settings: 48 kHz, BINKA, `SoundCueCookQualityIndex=-1`) with
three render-only changes to keep the cook short (SM5 only, no ray tracing, no distance fields),
`bCookAll=True`, and `PythonScriptPlugin` enabled. Two editor-side details:

- A commandlet creates no audio device, so the BINKA decoder the importer needs is never
  registered; `ue_import.py` loads `BinkAudioDecoder` itself.
- `/Game/Sounds/Class_Engine` and `/Game/Sounds/EngineSoundAttenuation` exist in that project only as
  stand-ins (attenuation set to vanilla's values), so the cooked waves import them by path and the
  game resolves its own. `copy_cooked.py` copies only `Cars/Parts/Engine/Sound/MT_*`: the stand-ins
  must never ship.

UE 5.5 output is fine for this 5.4 game: a cooked unversioned package carries no engine version
(`ue4 0 / ue5 0`, legacy -8), and the SoundWave export of a 5.5-cooked wave is byte-for-byte the
same layout as vanilla's and as `QX_Flutter_Shot` (same 136-byte BINKA platform-data block).
Contrary to the "Cooking sounds" note in AGENTS.md, cooking new SoundWaves works.

## Buzz ("bee")

The synthesised loops had firing overtones standing far above the noise between them in
1.5-6 kHz. Two fixes, both in the pipeline:

1. Every layer config gets `crankshaft_fluctuation:0.3` (was 0.02-0.12) and
   `intake_noise_factor` 0.45 on petrol engines, 0.15 on diesels (`layers.py`).
2. Firing turbulence after rendering (`buzz.turbulence`): band-passed noise (1.2-9 kHz,
   2nd-order Butterworth) under an envelope with a random-strength pulse (uniform 0.5-1.5) per
   firing event, 1.2 ms decay, mixed at 0.3x the layer's RMS. Firing rate = rpm/60 x cylinders/2
   with the cylinder count from the .esc (the Detroit two-strokes are modelled there as twice their
   cylinders on a four-stroke cycle, so the same formula gives their real rate). Built circularly
   with the pulse grid offset half a period from the seam, so loops stay seamless (seam step under
   the 99.9th percentile of sample-to-sample steps in all 758 files). A layer that still measures
   over +4 dB gets more (0.4-1.2x); the steps where that happened are listed below.

Measure (`buzz.overtone_ratio`): FFT of 2 s, mean power within 8 % (of the firing frequency) of a
firing harmonic vs mean power more than 25 % away, 1.5-6 kHz. Reproduces the measurements it was
specified with: s65 5850 rpm base +15.5 dB, with the recipe +2.6 dB. Limit +4 dB per layer and
for the pair.

## Loudness (synth; recorded engines: see Level targets above)

References are vanilla's own `MTEngineSoundDataAsset` waves -- the same playback path as ours, and
all of them leave every volume multiplier at default, as ours do, so matching file loudness
matches in-game loudness. Decoded with FModel's `vgmstream-cli` (`D:\MT\Output\.data`): the BINKA
stream is the 0x1C-byte header inlined in the `.uexp` followed by the `.ubulk`; our own cooked
wave decodes back at correlation 0.999 and within 0.01 dB of its source. LUFS is ITU-R BS.1770-4
integrated (`loudness.lufs`, within 0.02 dB of ffmpeg's `ebur128`).

Per step the level of the pair (engine + exhaust summed) is set to the class reference at that
point of the engine's rpm span (idle = lowest step, high = top step, linear between, never falling
with rpm); both layers of a step get the same gain, so their synthesised balance is kept. A step
whose peaks would pass -1 dBFS is soft-limited above -6 dBFS and made up again.

### Reference levels (vanilla EngineSoundData waves, LUFS)

| set | class | step: engine / exhaust layer | pair at idle / mid / high of its span |
|---|---|---|---|
| MidDuty_02 | diesel | 560: -27.06 / -28.65, 1000: -22.44 / -18.89, 1500: -24.14 / -19.22, 2000: -22.14 / -19.88, 3000: -13.75 / -15.79 | -24.8 / -17.9 / -11.6 |
| MidDuty_03 | diesel | 795: -25.7 / -29.42, 1070: -22.77 / -29.51, 1410: -16.52 / -27.46, 1755: -17.15 / -21.02, 1940: -17.43 / -18.31, 2130: -16.73 / -16.46 | -24.2 / -16.1 / -13.6 |
| V6Sport_02 | petrol | 1040: -31.89 / -34.35, 1500: -22.36 / -, 1540: - / -26.14, 2000: -13.75 / -20.89, 3000: -19.62 / -13.83, 5320: -23.03 / -31.32 | -29.9 / -13.6 / -22.4 |
| V6Sport_03 | petrol | 880: -41.83 / -32.73, 2010: - / -16.02, 3000: -18.79 / -, 3060: - / -17.16, 3480: -14.68 / -, 3780: - / -16.36, 4540: - / -14.11, 5280: - / -13.53 | -32.2 / -14.6 / -11.1 |
| V6Sport_04 | petrol | 1000: -36.89 / -, 2000: -29.89 / -, 3000: -23.61 / -, 4000: -19.05 / -, 5000: -14.36 / -, 6000: -12.81 / - | -36.9 / -21.3 / -12.8 |

Class targets (mean of its sets, made non-decreasing): **diesel** idle -24.5, mid -17.0, high -12.6 LUFS; **petrol** idle -33.0, mid -16.5, high -15.4 LUFS. Vanilla has no pickup-diesel EngineSoundData set, so the pickup diesels (cummins67, ps60, 6ct, 12v, vp44) use the truck-diesel curve.

For the record (not used as targets; their cues add volume modulators of up to 3-5x on top): vanilla cue loops `Chevy_V8_hot_rod_car_-_short_looping_sou` -37.89, `Chevy_V8_hot_rod_car_-_short_looping_sou` -13.53, `Chevy_V8_hot_rod_car_-_short_looping_sou` -15.62, `482826-Mazda_Miata_MX5_NBFL_1_0k` -37.25, `482874-Mazda_Miata_MX5_NBFL_1_6k` -9.79, `Ferrari_275_V12_Idle` -39.72, `Ferrari_275_V12_High` -20.0, `Truck_04_Idle` -29.45, `Truck_04_Mid` -26.01, `Truck_04_High` -25.08, `Truck_05_Idle` -38.26, `Truck_05_High` -27.4; source WAVs next to mod sounds `boxer4_high.wav` -12.57, `rft_idle.wav` -14.36, `rft_mid.wav` -9.59, `high (2).wav` -10.68, `idle (3).wav` -14.09.

## Per engine (synth, superseded 2026-11-06)

Cue / data asset path is `/Game/Cars/Parts/Engine/Sound/MT_<engine>/MT_<engine>_EngineSoundData`. Levels and buzz are measured on the **cooked** waves decoded back (`levels_cooked.json`); buzz is the worst of engine layer, exhaust layer and pair over all steps.

| engine | class | cyl (.esc) | rpm steps | range | CrossfadeRPMRange | idle LUFS | mid LUFS | high LUFS | worst miss | buzz max | turbulence raised above 0.3x (rpm: engine, exhaust) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rs3five | petrol | 5 | 14 | 850-7350 | 500 | -33.1 | -16.4 | -15.4 | 0.10 dB | +2.3 dB | - |
| s65 | petrol | 8 | 17 | 850-8850 | 500 | -33.1 | -16.5 | -15.4 | 0.10 dB | +4.0 dB | 7850: 1.0, 0.3; 8350: 1.2, 0.3; 8850: 1.0, 0.3 |
| voodoo | petrol | 8 | 16 | 850-8350 | 500 | -33.1 | -16.4 | -15.5 | 0.11 dB | +3.8 dB | 7850: 0.8, 0.4; 8350: 0.6, 0.3 |
| cgtv10 | petrol | 10 | 16 | 1000-8500 | 500 | -33.1 | -16.4 | -15.4 | 0.06 dB | +3.9 dB | 6000: 0.3, 0.4; 6500: 0.3, 0.4; 7500: 0.3, 0.4; 8000: 0.3, 0.4 |
| sbc350 | petrol | 8 | 11 | 750-5750 | 500 | -33.1 | -16.5 | -15.4 | 0.05 dB | +1.3 dB | - |
| hemi426 | petrol | 8 | 12 | 800-6300 | 500 | -33.1 | -16.4 | -15.4 | 0.06 dB | +0.9 dB | - |
| 4age | petrol | 4 | 15 | 900-7900 | 500 | -33.1 | -16.5 | -15.5 | 0.07 dB | +1.8 dB | - |
| 4g63t | petrol | 4 | 14 | 850-7350 | 500 | -33.0 | -16.4 | -15.4 | 0.03 dB | +0.7 dB | - |
| series60 | diesel | 6 | 11 | 600-2100 | 150 | -24.5 | -17.0 | -12.7 | 0.05 dB | +1.4 dB | - |
| cat3406e | diesel | 6 | 11 | 650-2150 | 150 | -24.5 | -17.0 | -12.7 | 0.06 dB | +1.1 dB | - |
| macke9 | diesel | 8 | 11 | 600-2100 | 150 | -24.5 | -17.0 | -12.6 | 0.04 dB | +1.5 dB | - |
| om502 | diesel | 8 | 11 | 600-2100 | 150 | -24.5 | -17.0 | -12.6 | 0.03 dB | +1.2 dB | - |
| 8v92 | diesel | 16 | 12 | 550-2200 | 150 | -24.5 | -16.6 | -12.6 | 0.04 dB | +0.4 dB | - |
| cummins67 | diesel | 6 | 18 | 750-3300 | 150 | -24.5 | -16.8 | -12.6 | 0.02 dB | +1.2 dB | - |
| ps60 | diesel | 8 | 22 | 700-3850 | 150 | -24.5 | -16.8 | -12.7 | 0.05 dB | +1.5 dB | - |
| ntc400 | diesel | 6 | 13 | 600-2400 | 150 | -24.5 | -17.0 | -12.7 | 0.08 dB | +1.4 dB | - |
| isx15 | diesel | 6 | 11 | 600-2100 | 150 | -24.5 | -17.0 | -12.6 | 0.03 dB | +0.9 dB | - |
| c16 | diesel | 6 | 12 | 650-2300 | 150 | -24.5 | -16.6 | -12.7 | 0.07 dB | +1.0 dB | - |
| macke6 | diesel | 6 | 11 | 600-2100 | 150 | -24.5 | -17.0 | -12.7 | 0.04 dB | +1.3 dB | - |
| mp8 | diesel | 6 | 11 | 600-2100 | 150 | -24.5 | -17.0 | -12.6 | 0.03 dB | +1.1 dB | - |
| 6ct | diesel | 6 | 14 | 650-2600 | 150 | -24.5 | -16.7 | -12.6 | 0.05 dB | +1.1 dB | - |
| 12v | diesel | 6 | 16 | 750-3000 | 150 | -24.4 | -16.7 | -12.6 | 0.03 dB | +1.4 dB | - |
| vp44 | diesel | 6 | 18 | 750-3300 | 150 | -24.5 | -16.8 | -12.6 | 0.02 dB | +0.9 dB | - |
| dd671 | diesel | 12 | 13 | 500-2300 | 150 | -24.5 | -17.0 | -12.6 | 0.02 dB | +0.9 dB | - |
| dd871 | diesel | 16 | 13 | 500-2300 | 150 | -24.5 | -17.0 | -12.6 | 0.02 dB | +0.9 dB | - |
| dd1271 | diesel | 24 | 13 | 500-2300 | 150 | -24.5 | -17.0 | -12.6 | 0.02 dB | +0.8 dB | - |
| dd1671 | diesel | 32 | 13 | 500-2300 | 150 | -24.5 | -17.0 | -12.6 | 0.02 dB | +0.5 dB | - |
| type1 | petrol | 4 | 10 | 900-4500 | 400 | -33.1 | -16.4 | -15.4 | 0.06 dB | +1.0 dB | - |

Total: 28 engines, 379 rpm steps, 758 waves + 28 EngineSoundData, 47 MB.

## Not yet known / to check in game

- `CrossfadeRPMRange` is set to our step spacing (150 diesel, 400-500 petrol); vanilla uses 500 on
  200-1000 rpm spacing. If the native crossfade does not normalise its weights, 500 on our 150 rpm
  steps would stack several layers and play louder than measured, which is why it is not 500.
  Untested in game; it is one float per asset (`make_data.py`).
- How the game applies `IdleEngineRatio` / `IdleExhaustRatio` and throttle to the layers is native
  code; ours leave them at default like 4 of 5 vanilla sets. The idle steps match vanilla idle
  steps, so they should sit where vanilla's do, but that is a file-level match, not heard.
- The petrol idle reference (-33 LUFS) is vanilla's: its V6 idles are very quiet. Ours follow it.

## For the exhaust layers on the 63 existing sets

Same pipeline: render `_engine`/`_exhaust` variants of each config (`layers.py`, `ZERO`), deburr and
level (`prep_wavs.py` -- references and targets come from `ref_lufs.json`/`loudness.band_targets`),
import + cook in `D:\MT\SoundCook\MTEngineSounds`, `copy_cooked.py`, then an `MTEngineSoundDataAsset`
per set (`make_data.py`, template `Truck/MidDuty_02/EngineSoundData`). `SOURCES` in `prep_wavs.py`
is the engine list.
