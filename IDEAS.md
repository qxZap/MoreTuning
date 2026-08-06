# Ideas not built yet

Parked for later. Each one has what was already checked, so the next go does not
start from scratch.

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
