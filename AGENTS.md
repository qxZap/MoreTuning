# AGENTS.md — working on MoreTuning

Motor Town mods. The mod folders (`qxZap_MoreTuning_P/`, …) are unpacked pak
trees; `repak` turns one into a `.pak` that drops into the game's `Paks` folder.
Everything else here is tooling that generates the `.uasset` files inside them.

## The tools, and which ones bite

| | |
|---|---|
| **UAssetGUI** | `D:\MT\UAssetGUI.exe` (**v1.1.1**). **Not** `.\UAssetGUI.exe` in this repo — that is v1.0.4 and writes an older JSON schema; anything it exports fails to build again under the current game. |
| **Mappings** | `MotorTown719` for game 0.7.19. UAssetGUI resolves the name against `%LOCALAPPDATA%\UAssetGUI\Mappings\*.usmap`. Dump a fresh one after every game update. |
| **Engine version** | `VER_UE5_4`. |
| **Packing** | `modp.bat <ModFolder>` — repak, then copy the pak into the game. |

```
D:\MT\UAssetGUI.exe tojson   <in.uasset> <out.json>   VER_UE5_4 MotorTown719
D:\MT\UAssetGUI.exe fromjson <in.json>   <out.uasset>           MotorTown719
```

Vanilla assets to diff against live in `D:\MT\Output\Exports\MotorTown\Content`
(FModel export of the current build).

### UAssetGUI fails silently. Always check.

It is a WinForms app. On error it writes **no output file, prints nothing, and
exits 0**. `subprocess.run(..., check=True)` will happily report success. The
only reliable test is whether the output file exists — and then whether reading
it back gives a `DataTableExport` rather than a `RawExport`. `RawExport` means
the parse failed (wrong usmap, or a malformed table) and the game will ignore
the rows.

Four things make it write nothing:

1. **An FName missing from the NameMap.** Every FName a row references must be
   in `NameMap`: row keys, enum values, struct types, gameplay tags, soft-path
   halves, and the `ArrayType`/`InnerType`/`ValueType` type names. Property
   *names* are not FNames here — unversioned assets get those from the usmap,
   which is why vanilla's NameMap has no `AirDragMultiplier` in it.
2. **A number-suffixed FName registered whole.** UE stores an FName as
   (base, number): `LSD_Clutch_2_100_40` is base `LSD_Clutch_2_100` plus 40, and
   only the base belongs in the map. Register the full string and the lookup
   misses. `EF6_4106` → `EF6`. A leading zero means it is *not* a number suffix,
   so `Cargos_01` stays whole.
3. **A duplicated property in a row.** Both part-row templates shipped with
   `BrakePower` twice; that alone killed the write.
4. **A property the current struct no longer has.** Diff a mod row's property
   names against a vanilla row before wondering why.

And one that fails *loudly nowhere*: `"ObjectPropertyData" in prop["$type"]` is
also true for `SoftObjectPropertyData`. Test the prefix, not the substring —
otherwise re-running a converter over an already-converted table silently
repoints every soft reference at `None`, and the file still builds fine.
`rebase.py` guards this by refusing to emit a table with fewer live references
than it read.

## What game 0.7.19 changed

Part references moved from **ObjectProperty** (a hard import, negative
`FPackageIndex`) to **SoftObjectProperty** (an `FSoftObjectPath` string):

```jsonc
// before                                    // after
{ "Name": "EngineAsset",                     { "Name": "EngineAsset",
  "$type": "…ObjectPropertyData…",             "$type": "…SoftObjectPropertyData…",
  "Value": -14 }                               "Value": { "AssetPath": {
                                                  "PackageName": "/Game/Cars/Parts/Engine/Kart_10HP",
                                                  "AssetName": "Kart_10HP" } } }
```

Affected: `EngineAsset`, `TransmissionAsset`, `LSDAsset` on `VehiclePartRow`,
and `TirePhysicsDataAsset` / `TirePhysicsDataAsset_BikeRear` inside
`MTVehiclePartTire`. Do not hardcode that list — read it off the current vanilla
table (`Rebase/rebase.py: soft_property_names`), because the next update will
convert something else.

Consequences:

- Vanilla `Engines.uasset` now has **7 imports**, not one per engine, and
  `CreateBeforeSerializationDependencies` is just `[-6]`. The old pattern of
  appending an asset import + a package import per part and pointing the row at
  the index is dead. Nothing to append, nothing to renumber.
- Part `.uasset` files themselves (`MHEngineDataAsset`, `MTTransmissionDataAsset`)
  are **unchanged** — the 128 engines and 99 transmissions in the mod still load.
  Only the tables that list them broke.
- Genuinely hard references still exist (aero/tire meshes, `QuadWheelMesh`), so
  a rebase still has to graft those imports across.

## Build order

The three row tools run in sequence, and the order matters:

```
python Rebase/rebuild.py         # 1. onto the new vanilla  (reverts stripping)
python Rebase/compat.py          # 2. fold Maja's Motor Works in  (see below)
python RemoveReq/run.py          # 3. strip vehicle gates   (re-applies it)
python RemoveReq/run.py --nolimits   # 4. any body part on any car -> xNoLimits pak
python CarbonParts/run.py        # 5. carbon twins -> yCarbon pak
python CarbonParts/run.py --wheelworks   # 6. Wheel Works compat -> ZZb pak
modp.bat qxZap_MoreTuning_P
modp.bat qxZap_MoreTuning_xNoLimits_P
modp.bat qxZap_MoreTuning_yCarbon_P
modp.bat ZZb_qxZap_MoreTuning_yWheelWorksCarbon_P
```

Step 2 has to come before 3-5: it writes into MoreTuning's own tables, and
everything after builds on them.

Pak names decide load order (alphabetical, last wins), which is what the `x` and
`y` prefixes are for: `_P` < `x`NoLimits < `y`Carbon. Each later pak's AeroParts
is built from the one before it, so overriding never loses rows.

**The sort is case-insensitive.** UE compares pak names with `FString::operator<`,
which is `Stricmp`, so lowercase does *not* beat uppercase. `qxZap_Wheels_P`
looks like it wins over `ZZb_qxZap_MoreTuning_yWheelWorksCarbon_P` under ASCII
and loses under the rule the game uses — that shipped, and a 152 KB carbon table
silently overrode 373 MB of resized wheels. Only the tell was odd: one of three
paks worked, and it was the one whose name won either way.

Check a name against the paks that ship the *same table*, comparing
case-insensitively, not against a list written from memory — the list is what
was wrong. `WheelWorkshop/run.py:check_order()` does it by reading the folder.

`rebuild.py` keeps *vanilla's* version of any row both sides have, which is what
picks up balance changes — and also what puts back every restriction RemoveReq
took out. So RemoveReq always runs after it, and CarbonParts after that, since
it builds on the finished AeroParts.

`Rebase/pipeline.py` is the shared plumbing: export → transform rows → build →
read back → `verify.py` → install. All three tools go through `build_table`,
which reads a table from the mod folder if it is already there and from the
vanilla export otherwise. Intermediates land in `Rebase/work/` (gitignored).

| | |
|---|---|
| `Rebase/rebase.py` | The 0.7.19 conversion. `python rebase.py demo` self-checks. |
| `Rebase/rebuild.py` | Table list, `CURRENT_MAPPINGS` / `PREVIOUS_MAPPINGS`. |
| `Rebase/verify.py` | DataTable parse, no stray hard part imports, every referenced package ships. |
| `Rebase/old/` | `*.pre719.json` snapshots of the tables as they were before the migration. Archive only — nothing builds from them. |

After a game update, set `CURRENT_MAPPINGS` to the new usmap and
`PREVIOUS_MAPPINGS` to the one the mod folder was last built with; between
updates they are the same and a rebuild is a no-op.

## Stripping requirements, and carbon parts

`RemoveReq/run.py` clears `VehicleTypes`, `TruckClasses`,
`OverrideAllowedVehicleKeys` and empties `VehicleRowGameplayTagQuery` on every
row, so any vehicle can fit any part — and any vehicle can buy any licence. It
leaves `VehicleKeys` alone; the shipped tables kept those. Default tables are the
three `License*` ones plus `VehicleParts0`.

`--nolimits` adds `VehicleKeys` to that set and writes AeroParts + Headlights
into `qxZap_MoreTuning_xNoLimits_P`. `VehicleKeys` is the per-car lock, so
clearing it is what lets any bumper or headlight go on any vehicle — the meshes
will not always sit right, which is why it is a separate pak.

It also renames every part whose display name is just `#1`, `#2`… Those come
from the game's string tables (namespace `AeroParts`, key `Vista_Bonnet_01_Name`)
and read fine in vanilla, where only the one car that fits them ever lists them;
with the lock gone every car lists all of them and the menu is a wall of `#1`.
The row key already carries car and variant, so the name becomes
`Vista Bonnet 01`. Parts with a real name (`Voltex Bumper`, `Type-A`) have no `#`
and are left as they are.

To change a name you must replace the whole property with
`pipeline.name_property` — a culture-invariant literal with `Namespace` and the
key `Value` set to null. Editing `CultureInvariantString` alone does nothing:
that field is only the fallback source string, and the string-table lookup wins.

`CarbonParts/run.py` adds a `<id>_Carbon` twin per row at half the mass and
650c/kg, into `qxZap_MoreTuning_yCarbon_P`. Carbon body kits are meant to fit
anything, so unlike RemoveReq it also clears `VehicleKeys` — on the originals as
well as the twins, which is what the shipped pak did. It carries the `#n` rename
too: it sorts after xNoLimits and overrides the same tables, so without it
packing carbon would put the `#1` names back. Both tools are rerunnable;
CarbonParts drops existing `_Carbon` rows before regenerating.

### Maja's Motor Works is a hard dependency

MoreTuning is built on Motor Works and ships its content, deliberately: it sends
people to the mod this one is founded on. `Rebase/compat.py` folds its
AeroParts, Engines, Transmissions and VehicleParts0 into MoreTuning's own tables
— its rows win where both touch the same part, MoreTuning's extra rows go on
top, and the vehicle gates are re-stripped because the merge hands its rows back.

Without it, `qxZap_MoreTuning_P` sorts after `MajasMotorWorks…` and discards its
tables whole, so the parts it adds vanish — `TrailerHitch_Hook`, `Winch_06_MMW`
and `Winch_Tow_05_MMW` among them. That reads in game as the winches being
broken.

This is why the merge goes *into* MoreTuning rather than a separate pak: a pak
mounting after MoreTuning also mounts after xNoLimits and yCarbon and would
override them, costing the carbon body parts. Merged in, those two are built
from the merged tables and inherit it.

Refresh its tables from its pak — no FModel needed:

```
D:\MT\PakMerge\repak.exe unpack -o <dir> "<Paks>\MajasMotorWorksV7.1-7.19_P.pak"
```

then copy `DataAsset/VehicleParts/*` into `MajasMotorWorksV7.1-7.19_P/MotorTown/Content/`.

### repak and Oodle

repak refuses Oodle-compressed paks with "failed to fetch oodle" unless
`oo2core_9_win64.dll` sits **next to its own exe** — not the working directory,
not PATH. `D:\MT\PakMerge\repak.exe` has it, and its SHA-256 matches the one the
loader expects (`6f5d41a7…f457`), so that copy works offline. Use it for any
mod pak. The game's own `MotorTown-Windows.pak` is AES-encrypted on top of that
and the key files in `D:\MT\aes` are empty, so vanilla still has to come from an
FModel export.

### Maja's Mo Wheel Works compat

`CarbonParts/run.py --wheelworks` builds `ZZb_qxZap_MoreTuning_yWheelWorksCarbon_P`
from her Wheels table instead of vanilla. Her table is **not** just an unlock —
it repoints all 93 rows at her replacement meshes and adds colour slots (84 rows)
and decal slots (75). Our vanilla-based carbon Wheels mounts after hers and would
throw all of that away, so the compat exists to put the carbon twins on top of
*her* rows and mount last.

Refreshing her table when she updates: FModel-export
`MotorTown/Content/DataAsset/VehicleParts/Wheels.uasset` + `.uexp` from her pak
to `MajasMoWheelWorksV5.1-7.19_P/MotorTown/Content/DataAsset/VehicleParts/`
(rename the folder to match her version). `repak` cannot do this — her pak is
Oodle-compressed and repak 0.2.2's loader wants to fetch a DLL from an online
index; the `oo2core_9_win64.dll` copies under `D:\MT` are a different build and
it ignores them.

**Export into that folder, not into `D:\MT\Output\Exports`** — an FModel export
clears its output directory, which will wipe the vanilla tables everything else
is built from. This has bitten twice: once taking out
`DataAsset/VehicleParts/`, once taking out all of `DataAsset/` except the two
files being exported. If a tool suddenly reports "could not read vanilla ..." or
silently stops rebasing, check that folder first.

Empty a `GameplayTagQuery` in place rather than substituting a hand-built struct
— the result then matches an unrestricted vanilla row exactly, whatever shape the
current game uses.

The vanilla `License.uasset` in the export was edited in place at one point;
`License.uasset.bak` next to it is the pristine copy. RemoveReq reads vanilla
directly, so make sure that file is the real thing.

## Generators

Both follow the same shape: fresh vanilla table as the base, a row template, one
`.uasset` per part, rows appended with soft paths and their FNames registered.

| | |
|---|---|
| `TransmissionGenerator/` | `tras_s.json` (99 boxes) → `run.py` → `Transmissions.json` + `new_trans/*.uasset`. Driven by `transmissions.bat`, which builds the table and moves everything into the mod. |
| `ElectricMotors/` | `motors.json` (EV entries) → `run.py` → `Engines.json`, on top of `EnginesIN.json`. |

`EnginesIN.json` is the mod's engine table **minus** the EV rows the script adds
— regenerate it from `Rebase/work/Engines.json` after a game update, dropping
rows whose name starts with `EV`. There is no generator for the other ~90 mod
engines any more (`NewEnginesFramework/run.py` is empty in git), so that table is
only maintainable by rebasing.

Templates (`NEW_TRANSMISSION.json`, `NEW_ENGINE.json`, `Electric_670HP.json`,
`tranmission_part.json`) are rebased vanilla assets/rows. Regenerate them from a
current vanilla export rather than hand-patching; `.pre719` copies of the old
ones are next to them.

### Transmission `Type` vs `ClutchType`

Two separate enums, and vanilla sets both where it matters:

- `ClutchType` (`EMTTransmissionClutchType`): `MultiPlateClutch`, `TorqueConvertorV2`
- `Type` (`EMTTransmissionType`): `CVT`, `EatonFuller13`, `EatonFuller18`

`Type` is what gives a box its shift model — the range + splitter handling on the
Eaton twin-countershaft gearboxes. Leave it unset and an 18-speed is just 18
sequential gears. Set it with `"type": "EatonFuller18"` on the entry in
`tras_s.json`. The gear list has to match vanilla's layout for it: reverses, `N`,
two crawlers, then eight L/H splits (23 entries, `DefaultGearIndex` 4).

## MoreAttachments

### `Items_AttachmentPart` is keyed by row name, not by position

Rows carry no numeric id. The DataTable row name *is* the key — `Attachment_
ZinoHeadlight_03` — and that is what a save stores. This is why the game can add
attachments in an update without repainting everyone's vehicles, and it is worth
knowing before panicking about order the way this repo once did.

So **removing or renaming a row is the breaking change**, not moving one. A row
that disappears takes it off every vehicle wearing it. Adding is free; reordering
is cosmetic.

Verified rather than assumed, and the checking is the useful part: read the row
names out of the table at every commit that touched it and compare sets, not
positions. Across this repo's whole history no row has ever been removed or
renamed — the 0.7.19 migration added 46 and dropped none — with one exception,
the `Attachment_qxWinch` test row, which shipped briefly and was then deleted.

Reordering was still reverted, because a diff nobody can justify is not worth
carrying, and menu position is a vendor concern.

### Cloning a row drags the donor's name with it

Three times now, in three tables. A row's display name is a string table lookup,
not a string: clone the row and every copy resolves to the donor's entry, so
fifteen sizes of a rim all read "Tavan" and 138 attachments all read "Round
Light 01". Setting the obvious field does not help either, because the field the
UI reads is usually not the one called `Name`.

    Items_AttachmentPart   the shop reads ItemNameTexts.Texts, not ItemName
    Wheels                 the shop reads Name2.Texts, and Name is empty
    engines                Name, and NewEngines already does it correctly

The fix is the same everywhere and it is what the engine rows already do: clear
the lookup and put the string in directly.

    HistoryType  StringTableEntry -> None
    TableId      /Game/.../SomeTable -> None
    Value        the key -> None
    Flags        -> CultureInvariant
    CultureInvariantString -> the text you want

Set it in every name field the row has rather than guessing which one is read.
And a cloned *asset* has the same problem in a different shape: its export keeps
the donor's object name, so package.object disagrees and the row resolves to
nothing at all -- that one shows up as a part with no stats.

### An attachment actor, and what makes a lamp work

An attachment is a `BlueprintGeneratedClass` actor with an SCS carrying
`DefaultSceneRoot`, `Scene`, a `StaticMeshComponent`, a `SpotLightComponent`,
`MTLightControlComponent` and `MTInteractableComponent`. All 585 carry all of it,
because they all come from one template.

What separates a working lamp from a dead one is **`InteractionParams`** on the
interactable: `ToggleLight`, `ChangeLightMode`, `ChangeLightColor`. Without them
a light cannot be switched, so it can only sit on — which is why every painted
part used to glow. It is not `MTLightControlComponent.LightIntensity`; vanilla's
own light attachments set nothing at all on that component.

The donor to copy is the game's own, `Objects/VehicleAttachment/Light_01..15` —
first party and already 0.7.19, so nothing to migrate. They differ a lot: 5 to
200 lumens, `AttenuationRadius` unset to 1500. `Light_05` is the bright one and
is what `LIGHT_PROFILE.json` is harvested from. `Light_01` reads as a glow
because it sets no attenuation radius at all and falls back to 1000.

Enum entries are FNames. `ToggleLight` has to reach the NameMap or the write
drops the interactions silently — `reallights.names_in` collects enum and name
property *values*, not just property names.

### Mesh offset vs light offset

Car part meshes are authored in **vehicle space** — a Zino headlight's geometry
sits at X=199 because that is where it lives on the car. `run.py`'s
`get_x_bounding` reads `ExtendedBounds.Origin` and the actor shifts the mesh
component by `-origin` so the geometry lands on the attachment point.

That offset must **not** be given to a light. A spot light is a point with no
geometry to cancel, so the same number just moves the lamp two metres behind and
half a metre under the car. They share a sentinel in the old templates and that
was the bug. Mesh gets `-0.96961..3`, the lamp gets `-0.96971..3`, filled with
the mesh's half depth so the beam starts at the lens face.

`migrate_templates.py` re-derives templates from a *built* actor, whose offsets
are one Neo spoiler's real numbers, so every migration silently ate the
sentinels. It now puts them back — check they survive after any regeneration.

### Which parts are lamps is a question for the mesh

A mesh section painted `M_HeadLight` is a lamp; anything else is trim. That is
how `Micky_Light_L` — a wheel arch cover with nothing but `M_Palette` — stays
dark without being on a hand-kept list. `ACTOR_TEMPLATE_LIGHT.json` is picked on
that basis at generation time, and `reallights.py` uses the same test when
repairing built actors, so the two cannot drift.

## Conventions

- Windows paths are absolute and machine-specific throughout. That is deliberate;
  this is a one-machine toolchain, not a distributable.
- Non-trivial scripts carry a `demo` self-check (`python rebase.py demo`,
  `RemoveReq/run.py demo`, `CarbonParts/run.py demo`). Run them before a build.
- Back up a template before regenerating it (`*.pre719` here).
- Anything that changes row order in a table players have already built against
  is a breaking change to their saves, not a cosmetic one. Verify order against
  an earlier commit rather than assuming a change was positional-safe.
- Row tools take table names as arguments and default to their own list. None of
  them use `input.json`/`output.json` any more — that dance is gone.
