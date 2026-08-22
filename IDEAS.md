# Ideas not built yet

Parked for later. Each one has what was already checked, so the next go does not
start from scratch.

## Wheels with a configurable size — investigated, needs the editor

There is no way to scale a wheel from data. Not a missing feature to find: the
game has no concept of wheel size at all.

**A wheel part is meshes and nothing else.** The `Wheels` table has 93 rows, and
the `Wheel` struct on each is `LeftWheelMesh`, `RightWheelMesh`, the two DRW
variants, the two rear variants and `QuadWheelMesh`. No scale, no radius, no
width. `WheelSpacer` sits next to it and only pushes the wheel outward.

**Nothing else in the path carries a size either.** `MTTirePhysicsParams` is
friction, springs, damping, wear, load and rolling resistance — no radius. And
the names `WheelRadius`, `TireRadius` and `WheelWidth` do not exist anywhere in
the 0.7.19 mappings, so the game never names one.

**The tire profile numbers are naming only.** KM1-65, KM4-30, KM2-15 read like
sidewall profiles but nothing geometric changes between them — 65 to 15 moves
StaticMu 1.1 to 1.5 and stiffens the springs, and that is the whole difference.

**There is no actor to hang a scale on.** This is the difference from
attachments: an attachment row points at `AttachmentPartActorClass`, so it has a
blueprint, which is why `AttachmentScaleMin`/`Max` and in-game scaling work. A
wheel row points straight at meshes, so there is no component whose
`RelativeScale3D` could be set and no blueprint to add one to.

So the only route is a scaled mesh: duplicate the wheel mesh in the UE project
at 1.1 or 1.2, cook it, and add `Wheels` rows pointing at the scaled copies —
the same path the MTMapAddon attachments took, and the mod does not ship
`Wheels.uasset` yet so it would be taking that table.

**Every wheel mesh in the game is a 1 metre circle.** Measured all 91: the
smallest is 98.8cm across and the largest 100.3cm, a spread of 1.5cm on wheels
that in game are visibly anything from a kart to a mining truck. They are
normalised on purpose, and that is the whole explanation for everything above --
the *vehicle* scales the wheel to its own size, which is why any rim fits any car
and looks right on it, and why no part, tire or table needs a size field.

So a scaled mesh probably does nothing useful: either the vehicle rescales it
back, or it renders oversized against a physics radius that did not move. That is
the failure mode to expect, not the exception.

`TireCollisionCylinderMesh` looked like a way in and is not: zero content assets
reference it, the same shape as `MTWinchComponent`.

**The cheap confirmation needs no build at all.** With xNoLimits installed any rim
already fits any vehicle. Put a kart or small-car rim on a truck. If it comes out
truck-sized, the vehicle is doing the scaling and wheel size cannot be a part
property -- idea closed. If it comes out a metre across on a truck, the mesh
drives it and scaled meshes would work.

**Test one before doing ninety.** Since no radius exists in the data, the game
must work it out from the mesh at runtime. If it does, a scaled mesh scales the
physics with it. If instead the radius is fixed per vehicle, the wheel will grow
visually and sit wrong against the ground. One wheel at 1.1 answers that, and it
decides whether the whole idea is worth it.

## Winches as attachments — tried hard, does not work

The goal was winches you bolt on like any other attachment, so you could hang
twenty off a bike. Three builds, three crashes. **Do not try this again without
new information** — what follows is why, so nobody re-runs it.

`MTWinchComponent` was added to an attachment blueprint as an SCS node. Every
structural objection was found and fixed, and it still crashes:

- the four export dependency arrays were the donor component's, so the package
  declared it needed `MTLightControlComponent` while its class said
  `MTWinchComponent` — that mismatch is what "corrupt data found" means
- the node was in `RootNodes`. The mappings say `MTWinchComponent` derives from
  `StaticMeshComponent`, so it is a *scene* component and must be parented; it
  was moved under the actor's own scene node
- the template renames ran in the wrong order, leaving the package called
  `Attachment_qxWinch` with a class named after the donor's mesh

With all three fixed and the component shipping completely unconfigured — no
`Net_WinchPartKey`, nothing — it still crashes. That last run is the one that
matters: there was no configuration left to blame.

**The tell was there from the start: `MTWinchComponent` appears in zero content
assets.** `MTInteractableComponent` appears in 1102, `MTLightControlComponent`
in 48, and both are used as SCS nodes exactly the way this was. A component
meant to be authored gets authored somewhere. This one never is, in the game or
in any installed mod. It is spawned by the vehicle, and its state is
vehicle-shaped: `CachedAttachedVehicle`, `Net_WinchPartSlot`, `Server_Winches`.

Worth knowing anyway, from the mappings (`scratchpad/props.py` reads them):

| | |
|---|---|
| `MTWinchComponent : StaticMeshComponent` | 20 properties |
| `PartRow` | it carries its own row, so force and length need no part entry |
| `InteractableComponent`, `AxleMeshComponent`, `HookMeshComponent`, `CableComponent` | sub-components it drives, all null when authored by hand |
| `PickupWinchHook`, `PickupWinchController`, `AttachWinch`, `CutWinchCable` | the interaction types — grab the hook, grab the remote |

What would change the answer: the game shipping a winch component in a content
asset, or an `MTInteractableComponent` interaction type that starts a winch
without one. Neither exists in 0.7.19.

### The other route, which does work but was not wanted

The garage offers `EMTVehiclePartSlot::Winch0` only when the vehicle's body mesh
has a static mesh socket literally named `Winch0` — socket name is slot name,
the same way `Utility0` gates the fuel tank slot. 12 vehicles ship one; adding
one to the rest is a verified working change (UAssetGUI round-trips a body mesh
byte-for-byte, and the socket is just a name plus a vector). Measured off the
bodies that have both, a winch sits at **1.07x the trailer hitch's distance from
centre, mirrored to the front, at 1.4x its height**.

Rejected on purpose: it means shipping ~70 whole vehicle body meshes (~70 MB),
which collides with every car mod and breaks on any game update that touches a
body. It also is not the idea — the point was attachments, not sockets.

## Extra fuel tanks as a part — prototyped, reverted

Built and tested in game, then backed out of MoreTuning to keep the release
clean. `FuelTanks/run.py` still builds it; nothing is shipped. What it proved:

**They work.** A fuel tank is a `VehiclePartRow` with `FuelTank.FuelLiter` set
and a mesh on `Aero.Mesh`. No new part type, no actor, no blueprint.

**They have to be in `UtilityParts`.** The Utility slot reads that table only —
rows added to `VehicleParts0` never appear in the list, however well formed.
Nothing else ships `UtilityParts` (checked every installed pak, vanilla mods
included), so MoreTuning taking it is uncontested.

**There is no transform on the row.** `MTVehiclePartAero` is only `Mesh`,
`SkelealMesh`, `bUseCustomSocket`, `CustomSocketName`, `ComponentTags` and
`AttachParentComponentName`. Nothing can be rotated, scaled or offset from the
row — the mesh lands at the slot in its own orientation, so *which mesh you pick
is the whole of the look*.

**Pick meshes by shape.** The stock `FuelTank_01` is 51 x 69 x 46 cm: it lies
down, wider than tall. Upright barrels (`SM_barrel_2` 72x72x106,
`SM_Prop_Rusted_Drum_01` 70x71x105) stand on end in a slot shaped for a lying
tank and read as stretched. The refinery *stacks* are barrels on their sides —
`SM_Refinery_OilBarrel_Stack_01` at 127x142x86 is the closest proportional match
to the stock tank in the game.

**Rate capacity off the mesh.** The stock tank is 100 L in a 163 L bounding box,
so ~0.61 litres per box litre. Deriving capacity that way stops a barrel the size
of the stock tank being labelled 900 L; it gave 60 / 284 / 673 / 951 / 1075 L.

**Still open:** placement. The stacks sit outward but do not fit neatly, and with
no transform on the row the only lever left is `CustomSocketName` — some utility
parts set it, the stock tank does not. Worth trying before anything else.

## Extra fuel tanks — the original idea

Fuelling options tied to what each vehicle can carry: a vehicle that can take an
extra tank gets one as a buyable part, and bigger vehicles get bigger, uglier
ones — a truck ends up hauling a barrel rather than a tidy tank.

**The game already supports this and ships nothing using it.** From the 0.7.19
mappings and tables:

| | |
|---|---|
| `EMTVehiclePartType::FuelTank` | the part type exists |
| `MTVehiclePartFuelTank` | the struct, with a `FuelLiter` field |
| `FuelTank` | already a property on every `VehiclePartRow` — currently `FuelLiter +0` everywhere |
| `FuelTankCapacityInLiter` | the vehicle-side capacity |
| `/Game/Cars/Parts/Utility/FuelTank_01` | a fuel tank mesh, already in the game |

No vanilla row anywhere uses `PartType: FuelTank` — the 26 part types in use are
bumpers, spoilers, tires, winches and so on. So this is adding rows to a slot the
game understands but leaves empty, not fighting it.

`UtilityParts.uasset` is probably where they belong: it sits alongside the other
part tables and MoreTuning does not ship it yet, so there is no conflict to
resolve. `Cars/Parts/Utility` holds `FuelTank_01`, `Inventory_01`, `Inventory_02`
and `Inventory_Small_01` — the inventory parts are the closest working example of
a utility part to copy the shape from.

### Meshes

The interesting half. Rather than one tank mesh scaled up and down, reuse what the
game already has, the way MoreAttachments does — the mesh is a soft reference on
the row, so anything in the pak is fair game:

- `/Game/Cars/Parts/Utility/FuelTank_01` — the stock one, for cars
- `/Game/Env/Meshes/Refinery/SM_Refinery_OilBarrel_04` … `_06` and `_Pallet_01`
- `/Game/AssetsvilleTown/Meshes/StreetProps/SM_barrel_2`, `SM_barrel_3`
- `/Game/PolygonFarm/Meshes/Props/SM_Prop_Rusted_Drum_01`
- `/Game/Objects/Item/IT_Jerrycan` — for the small end

54 barrel-ish meshes exist in total, so there is plenty to pick from for a tier
that goes jerrycan → tank → drum → refinery barrel → barrel on a pallet.

### Open questions

- Does the game place the mesh from a socket, or does the part need an actor like
  the attachments do? If it needs an actor, `NewEngines`/`MoreAttachments` already
  have the cloning pattern for it.
- Does `FuelLiter` add to `FuelTankCapacityInLiter` or replace it?
- Which vehicles should be allowed one — this is the "tied to the capability of
  each vehicle" part, and `VehicleKeys` / `VehicleTypes` are the levers, the same
  ones RemoveReq strips. Worth deciding whether this part type stays gated when
  everything else is not.
