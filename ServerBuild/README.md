# MoreTuning, server edition

A dedicated server needs MoreTuning's part tables, but the full mod does not
work there. This builds the version that does: same parts, same stats, no custom
audio, 1 MB instead of 66.

    python ServerBuild/run.py            # build and report
    python ServerBuild/run.py --pack     # ...and write the pak
    python ServerBuild/run.py demo       # self-check

Copy `qxZap_MoreTuning_Server_P.pak` into the server's `MotorTown/Content/Paks`.
It sorts after `MotorTown-WindowsServer.pak` on `q` > `m`, which is all it has
to beat.

## What was actually wrong

Not "the sounds are heavy". One import per engine.

A vanilla engine and a MoreTuning engine are the same file: same 11 imports,
same properties, same layout. The single difference is where `EnginesSound`
points.

| | `EnginesSound` import | on the server? |
|---|---|---|
| vanilla `HeavyDuty_440HP` | `Sound/Truck/SC_Truck_05` | yes |
| ours `N14_370HP` | `Sound/N14/SC_N14_370HP` | no |

The server cooks audio *payload* out but keeps the sound **assets** — stub
`.uasset`/`.uexp` with no `.ubulk` — for the folders vanilla ships: Truck, V8,
v12, Bike, I4Sport, 2Stroke, Electric, V6Sport, Backfire. So vanilla's imports
resolve. Ours name `N14`, `C18`, `d13`, `x15`, `LS3`, `vr6` and eighty more
folders the server has never heard of, the `MHEngineDataAsset` fails to load,
and the engine is listed in the shop but does not work.

That is why the vanilla engines are fine and only the added ones break, and it
is why this build ships no audio at all: nothing needed one.

## What it does

Repoints every sound import at a cue the server already has. 115 of 185 engines
need it; the other 70 already used vanilla cues.

`EnginesSound` is chosen from the engine's own sound folder, because those are
named after the engine (`lamboV12`, `Bike/hayabusa`, `x15`) while the cue file
inside is a clone leftover that routinely says `SC_V8Engine` on a V12. A jake
brake is the giveaway for a truck — `N14` and `C18` say nothing about being
diesels, and nothing else in the game carries one. Failing all that, V8.

`JakeBrakeSound`, `BackfireSound` and `IntakeSound` go to the vanilla cue for
each. A sound property with no rule is nulled rather than pointed somewhere
wrong.

Nothing else is touched: 10 engines were compared property by property against
the client mod and only sound properties differ.

## The checks

Two, because two different things can go wrong.

`server_packages()` reads the dedicated server's own pak (encrypted, hence the
AES key) and that set is the authority — the rules never assume a cue exists,
they only choose among cues the server actually ships. If an update drops one of
the fallbacks the build stops instead of shipping a broken import.

`fix_engine()` then checks, per engine, that no `Package` import is left
pointing outside that set. Earlier this was a byte scan over the built tree and
it failed the build on strings that resolve to nothing: every engine carries
dead `NameMap` entries from cloning — `812/SC_V12Engine` sits in 21 engines that
never import it. A name is not a reference. Only the import table is.

## Notes

- `xNoLimits` and `yCarbon` reference nothing the server lacks, so they go on a
  server unmodified.
- `MoreAttachments` does not: it names ~32 packages the server has no copy of.
  Same class of problem, not fixed here.
- Clients keep the full mod and hear the real engines. Sound is client-side, so
  the server only has to agree about which parts exist and what they do.
- The AES key in `run.py` is the game's pak key. Move it out if this repo ever
  goes public.
