# Brief: DataTableFramework, MoreTuning on it, MoreAttachments for 0.7.20 — then a fitment plugin

You are the MoreTuning agent (`D:\MT\MoreTuning`, read its `AGENTS.md` first). This brief comes
from the MTLiveMap side (`D:\MTLiveMap`), where the island, Vehicle Labs and the Capitalist Economy
DLL live. Read it end to end before starting; it has two phases and a hard gate between them.

---

## Where things stand (28 Oct 2026)

- **Game: Motor Town 0.7.20+T1 (test branch).** Every mod is built for 0.7.19 and none load.
  All 29 mod paks were moved out of `Paks\` to
  `D:\SteamLibrary\steamapps\common\Motor Town\MotorTown\Content\_disabled_paks\pre_0.7.20\`
  (outside `Paks\`, because subfolders of `Paks\` DO mount). Rebuild from there; never move them
  back unrebuilt.
- **Mappings for 0.7.20 exist** — generated in-game by the Capitalist Economy DLL, no UE4SS:
  `D:\SteamLibrary\steamapps\common\Motor Town\MotorTown\Binaries\Win64\Mappings.usmap`
  (usmap v4, uncompressed, same format as `D:\MT\MotorTown719.usmap`).
  - The first dump had every ARRAY element type wrong; the fix is installed and the next game
    launch rewrites the file. **Before using it**, run
    `python D:\MTLiveMap\capitalist_economy\tools\compare_usmap.py D:\MT\MotorTown719.usmap "<that Mappings.usmap>"`.
    Expect "unknown-containing props: 0", ~2,177 of ~2,203 shared enums identical, and only genuine
    update differences. If arrays still show `UNKNOWN`, stop and tell the user.
  - Once verified, copy it to `D:\MT\MotorTown720T1.usmap` and use that name everywhere.
- Re-extract vanilla from the 0.7.20 pak before diffing anything; 0.7.19 extracts are stale.

### 0.7.20 changes that touch your mods (from the patch notes)
- **Horns are workshop parts** (49). **Wheel radius tuning per axle** (front/rear) in the garage,
  vanilla range 0.8–1.2. New wheel shop (23 wheels), Drover wheels fit cars/SUVs.
- **Attachments**: 5 antennas (01–04 paintable), attachment paint with metallic/roughness sliders,
  attachment placement now has rotation guides and a Reset for **position and rotation**. Fixed:
  "Attachments could inherit an incorrect scale from their parent vehicle".
- New vehicles with their own parts: **Duro** (bull bars, body parts, 12 truck wheels, gooseneck +
  bumper-pull hitch), **Lamas** (roof rack, exterior parts), Atlas 6x2 Flatbed, Tippa, Drover Van.
- Medium-duty 290HP engine. Off-centre body geometry fixed on Compacty, Dumpy, Maity, Mixi, Tronko.

---

## Rules carried over (each cost a broken release once)

1. **Never clone parts or ship whole `VehicleParts0` / `UtilityParts` copies.** A copy once erased
   278 MoreTuning rows. Add places and rows; don't re-ship tables you don't own.
2. **A rule is not a copy.** If a change is a rule (unlock, flag, strip a restriction), apply it to
   whatever copy wins at build time instead of shipping a frozen table. No Limits is the textbook
   case.
3. **Probe before pipeline.** Unknown mechanics: one change per launch in a lab pak, user confirms
   in game, then it goes into the build.
4. **Pak priority is the patch index first, then the filename** (`Foo_2_P` beats any `zzz_Foo_P`).
5. **Crash? Read `%LOCALAPPDATA%\MotorTown\Saved\Crashes\<newest>\CrashContext.runtime-xml`
   before theorising.**
6. **After renaming or moving a slot, test on a freshly bought/spawned vehicle** — saved vehicles
   keep their old parts and hide the result.
7. UAssetAPI parses a blueprint properly only beside its vanilla neighbours; Git Bash mangles
   `/Game/...` args unless `MSYS_NO_PATHCONV=1`.

---

## Phase 1 — three deliverables

### 1. DataTableFramework (new mod)

**Problem.** Composite DataTables (`VehicleParts`, `Vehicles`, and any other `CompositeDataTable`
the game ships) are a list of parent tables. Every mod that adds rows ships its own copy of the
composite to append one parent; only one copy wins, so every pair of such mods needs a compat.

**Design.** The framework ships each composite ONCE, with its vanilla parents plus **1000 empty
channel tables**, e.g. `/Game/DataTableFramework/<Composite>/Ch_0001 … Ch_1000`. A mod claims a
channel and ships only that channel's table — a path nobody else owns. N mods = N files, 0 compats.

Tasks:
- **Enumerate every composite** in the 0.7.20 content (search all DataTable assets whose export is
  a composite / has `ParentTables`). List them with their RowStruct and current parents.
- **Stubs must match each composite's RowStruct exactly**, generated, not hand-made, so a game
  update is a regeneration, not a rewrite.
- **Row-name prefix per channel** (`C0042_V8Turbo`) to avoid cross-channel key collisions.
- **Probe first, then scale.** Prototype with 10 channels on `VehicleParts`, verify in game, then
  measure what 1000 channels × N composites costs (file count, pak size, load time). If 1000 is a
  real load-time cost, report numbers and let the user decide; don't silently ship fewer.
- **Probe this hypothesis**: in a composite, a later parent's row with the SAME name as an earlier
  one overrides it ("last parent wins"). If true, channels can also OVERRIDE vanilla rows, not just
  add — which is how No Limits fits the framework. Channel order then = priority; document it.
- **Public registry**: one file listing channel → owner/mod, so two authors never collide.
  MoreTuning takes the first channels.
- Not for cargo: `Cargos` / `Cargos_01` are plain tables, not composites, and rows in both crash.

### 2. MoreTuning on the framework (MoreTuning, No Limits, Carbon)
- MoreTuning rows → its channel(s), shipping NO composite and NO vanilla table copies.
- **No Limits** → ideally an override channel (if the hypothesis holds) carrying only the rows it
  unlocks; otherwise a build-time rule. Report which.
- **Carbon** → its own channel with the `_Carbon` twins.
- Rebuild against 0.7.20 vanilla (new parts, horns as parts, new engines). Keep Maja's Motor Works
  and Mo Wheel Works compat handling per AGENTS.md, re-checked against their 0.7.20 versions if
  out; otherwise note what is blocked on them.

### 3. MoreAttachments for 0.7.20
- Rebuild on 0.7.20, and add attachments from the new content: Duro bull bars/body parts, Lamas
  roof rack/exterior parts, the antennas, anything new in `Items_AttachmentPart` or new meshes.
- Use the new attachment paint (metallic/roughness) where parts allow it.
- Re-check the scale-inheritance fix doesn't change how existing attachments sit.

### Gate
Hand the user a short test list (what to buy/fit/check per mod). **Phase 2 starts only after the
user confirms in game that all three work together.**

---

## Phase 2 — fitment plugin (after the gate)

**Goal:** players move and resize parts for their own fitment — offset (X/Y/Z), rotation, uniform
scale and per-axis scale (width/height/depth) — for bumpers, body parts, wheels, attachments.

Start with what the game now does natively, and extend it rather than replace it:
- **Attachments** already store a per-instance position + rotation (placement screen). Find where
  (save data? a struct on the vehicle?) and whether scale can ride along the same path.
- **Wheels** now have a per-axle radius. Find where it lives and where the 0.8–1.2 limit is set.
  The user wants **0.1–2.0** — if the range is data, it's a pak change; if it's code, say so.
- **Body parts** (bumpers etc.): find whether placement is socket-only or has an overridable
  transform. That decides between a data route and a native one.

Prefer data (pak) solutions. If a native plugin is genuinely required:
- It must **not** ship as another `version.dll` — the Capitalist Economy DLL already is one, and two
  can't coexist. Coordinate with the user (one shared loader, or merge into the existing one).
- `D:\MTLiveMap\capitalist_economy\src\dllmain.cpp` shows the working technique: object table and
  FName pool found by shape (no signatures), class fields resolved by reflection name, safe reads
  and writes. Reuse it instead of re-deriving.

Deliver Phase 2 as findings first (where each transform lives, what is reachable), then a probe
per part type, then the plugin.

---

## Also yours: the native plugin loader (`version.dll` framework)

Until now `version.dll` IS the Capitalist Economy mod (`D:\MTLiveMap\capitalist_economy\`): the game
exe imports `version.dll`, Windows loads it from `Binaries\Win64` first, and it forwards all 17
exports to `C:\Windows\System32\version.dll`. Only one file can have that name, so turn it into a
**loader framework** and make every native mod a plugin:

- `Binaries\Win64\version.dll` = the loader. It loads `Binaries\Win64\plugins\MT_plugin_<Name>.dll`
  -- that naming convention is the user's rule; any other file name is ignored -- in a defined
  order (alphabetical is fine, document it), with one log per plugin.
- **The loader owns everything invasive or shared; plugins only use it.** This is not optional:
  - **ProcessEvent hook, exactly once.** Capitalist Economy finds ProcessEvent's vtable index (79 on
    0.7.20) by its FunctionFlags tests and swaps every `.rdata` slot holding that address. A second
    plugin doing the same finds the slots already swapped, so one of them breaks or the game
    crashes. The loader hooks once and offers `RunOnGameThread(callback)` (game thread = the thread
    that ran `DllMain`) and a way to call a UFunction (`ProcessEvent(obj, func, parms)`).
  - **Engine discovery, done once and shared:** object table (`FUObjectArray`, stride 24), FName
    pool, UStruct/FField offsets, `FindObject`, field offset by name (walking supers). The working
    code is in `D:\MTLiveMap\capitalist_economy\src\dllmain.cpp`; lift it, don't rewrite it.
  - Reads/writes through SEH-guarded helpers, as in that file.
- A small C ABI for plugins (an exported `PluginInit(const Api*)`, versioned struct of function
  pointers) so plugins built separately keep working when the loader updates.
- Keep the `.usmap` export (`[Mappings] Export=1`) in the loader or as its own plugin; it is how the
  next game update gets mappings without UE4SS.
- **First adopter: Capitalist Economy**, split into `plugins\MT_plugin_CapitalistEconomy.dll` (cargo pay)
  and, if the user wants, `plugins\MT_plugin_VehicleDespawn.dll` (Ctrl+F10). Both are proven in game on 0.7.20 --
  the port must change their plumbing, not their behaviour. Re-test both in game after the port.
- The fitment plugin (Phase 2) is then just another plugin on this framework.
- Do the loader whenever it suits the phases, but before anyone ships the Capitalist Economy zip
  (`C:\Users\Milea\Downloads\CapitalistEconomy.zip` is on hold until the layout is final).
