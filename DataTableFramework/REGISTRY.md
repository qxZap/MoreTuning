# Registry

Every table the DataTable Framework lists, generated from `DataTableFramework/registry.json` by `registry_doc.py`. Within a table, later entries win a same-named row: vanilla first, then these in order.

**36 mod tables** in 5 composites, from **11 authors**, plus **32 reserved car slots**.

## By table

### VehicleParts (22)

| # | Table | Author | Mod |
|---|---|---|---|
| 1 | `/Game/DataAsset/VehicleParts/Wheels_PT` | Proxy | TechWheels / WheelSizeUnlimited |
| 2 | `/Game/HX8/OverlordParts/DT_HX8_LegacyParts` | Austin | Overlord HX8 |
| 3 | `/Game/HX8/OverlordParts/DT_Overlord_GarageParts` | Austin | Overlord HX8 |
| 4 | `/Game/HX8/ExhaustTipsR135/DT_HX8_ExhaustTips` | Austin | Overlord HX8 |
| 5 | `/Game/HX8/WinchR137/DT_HX8_Winch100T` | Austin | Overlord HX8 |
| 6 | `/Game/HX8/AeroR164/DT_HX8_RearAero` | Austin | Overlord HX8 |
| 7 | `/Game/HX8/FifthWheelsR186/DT_HX8_FifthWheels` | Austin | Overlord HX8 |
| 8 | `/Game/HX8/EngineAestheticR200/DT_HX8_EngineAesthetic` | Austin | Overlord HX8 |
| 9 | `/Game/HX8/TowUpgradeR253/DT_HX8_TowUpgrade` | Austin | Overlord HX8 |
| 10 | `/Game/DataAsset/VehicleParts/VehicleParts_MoreTuning` | qxZap | MoreTuning (own rows, Motor Works, vehicle gates stripped) |
| 11 | `/Game/DataAsset/VehicleParts/VehicleParts_MoreTuningNoLimits` | qxZap | MoreTuning No Limits (after MoreTuning: overrides its rows) |
| 12 | `/Game/DataAsset/VehicleParts/VehicleParts_MoreTuningCarbon` | qxZap | MoreTuning Carbon (after No Limits) |
| 13 | `/Game/DataAsset/VehicleParts/VehicleParts_TehEngines` | Teh | Engine Sound Pack (0.7.20 port by qxZap) |
| 14 | `/Game/DataAsset/VehicleParts/VehicleParts_AMCTires` | AMC | Tires (0.7.20 port by qxZap) |
| 15 | `/Game/DataAsset/VehicleParts/VehicleParts_SuspensionExpansion` | Suspension Expansion | Suspension Expansion (0.7.20 port by qxZap) |
| 16 | `/Game/RakMods/HeavyHaulPack/Parts/Engine/RHHP_Engines` | Rak | Heavy Haul Pack |
| 17 | `/Game/RakMods/HeavyHaulPack/Parts/Tires/RHHP_Tires` | Rak | Heavy Haul Pack |
| 18 | `/Game/RakMods/HeavyHaulPack/Parts/Transmissions/RHHP_Transmissions` | Rak | Heavy Haul Pack |
| 19 | `/Game/RakMods/HeavyHaulPack/Parts/RHHP_Parts` | Rak | Heavy Haul Pack |
| 20 | `/Game/RakMods/HeavyHaulPack/Parts/RHHP_Misc` | Rak | Heavy Haul Pack |
| 21 | `/Game/DataAsset/VehicleParts/VehicleParts_Biceps` | qxZap/sati | Biceps |
| 22 | `/Game/DataAsset/VehicleParts/VehicleParts_BoaterTown` | qxZap | Boater Town: Beyond the Waves (boat winches, propellers; built by the Arini session) |

### Cargos (3)

| # | Table | Author | Mod |
|---|---|---|---|
| 1 | `/Game/DataAsset/Cargos_Proxy` | Proxy | Oversize Cargo |
| 2 | `/Game/DataAsset/Cargos_Arini` | qxZap | Arini island (new_cargos rows) |
| 3 | `/Game/DataAsset/Cargos_CapitalistEconomy` | qxZap | Capitalist Economy (vanilla rows, stacking on, no volume discount) |

### Items (4)

| # | Table | Author | Mod |
|---|---|---|---|
| 1 | `/Game/DataAsset/Items/Items_MajasDetailWorks` | Maja | Detail Works |
| 2 | `/Game/DataAsset/Items/Items_SlidesAttachments` | SlideZone | Slide Industries Attachments |
| 3 | `/Game/DataAsset/Items/Items_SlidesDashboards` | SlideZone | Slide Industries Attachments |
| 4 | `/Game/DataAsset/Items/Items_MoreAttachments` | qxZap & satigt3 | MoreAttachments (free and premium share it) |

### CharacterBodyParts (2)

| # | Table | Author | Mod |
|---|---|---|---|
| 1 | `/Game/DataAsset/CharacterBody/CharacterBodyParts_Slides` | SlideZone | Slide Industries Attachments |
| 2 | `/Game/DataAsset/CharacterBody/CharacterBodyParts_Biceps` | qxZap/sati | Biceps |

### Vehicles (5)

| # | Table | Author | Mod |
|---|---|---|---|
| 1 | `/Game/DataAsset/Vehicles/Vehicles_Arini` | qxZap | Arini island (changed + added vehicle rows, incl. Crany and Goliath4-DB from Vehicles_Deprecated) |
| 2 | `/Game/DataAsset/Vehicles/Vehicles_VehicleLabs` | qxZap | VehicleLabs (fuel pumps, bulk economy, removable body parts; D:/MTLiveMap/vehicle_mod/tables.py). After Arini: it carries Arini's rows with its own changes on top, so it must win |
| 3 | `/Game/RPMTech/DataAsset/RPMTech_Vehicle` | Rak | RPMTech vehicles |
| 4 | `/Game/DataAsset/Vehicles/Vehicles_Biceps` | qxZap | Biceps (standalone car, row C0100_Biceps; built by the Arini session) |
| 5 | `/Game/DataAsset/Vehicles/Vehicles_BoaterTown` | qxZap | Boater Town: Beyond the Waves (C0700_Tugboat, C0701_ContainerShip; built by the Arini session) |

## By author

### Proxy (2)

- **VehicleParts** `/Game/DataAsset/VehicleParts/Wheels_PT` -- TechWheels / WheelSizeUnlimited
- **Cargos** `/Game/DataAsset/Cargos_Proxy` -- Oversize Cargo

### Austin (8)

- **VehicleParts** `/Game/HX8/OverlordParts/DT_HX8_LegacyParts` -- Overlord HX8
- **VehicleParts** `/Game/HX8/OverlordParts/DT_Overlord_GarageParts` -- Overlord HX8
- **VehicleParts** `/Game/HX8/ExhaustTipsR135/DT_HX8_ExhaustTips` -- Overlord HX8
- **VehicleParts** `/Game/HX8/WinchR137/DT_HX8_Winch100T` -- Overlord HX8
- **VehicleParts** `/Game/HX8/AeroR164/DT_HX8_RearAero` -- Overlord HX8
- **VehicleParts** `/Game/HX8/FifthWheelsR186/DT_HX8_FifthWheels` -- Overlord HX8
- **VehicleParts** `/Game/HX8/EngineAestheticR200/DT_HX8_EngineAesthetic` -- Overlord HX8
- **VehicleParts** `/Game/HX8/TowUpgradeR253/DT_HX8_TowUpgrade` -- Overlord HX8

### qxZap (10)

- **VehicleParts** `/Game/DataAsset/VehicleParts/VehicleParts_MoreTuning` -- MoreTuning (own rows, Motor Works, vehicle gates stripped)
- **VehicleParts** `/Game/DataAsset/VehicleParts/VehicleParts_MoreTuningNoLimits` -- MoreTuning No Limits (after MoreTuning: overrides its rows)
- **VehicleParts** `/Game/DataAsset/VehicleParts/VehicleParts_MoreTuningCarbon` -- MoreTuning Carbon (after No Limits)
- **VehicleParts** `/Game/DataAsset/VehicleParts/VehicleParts_BoaterTown` -- Boater Town: Beyond the Waves (boat winches, propellers; built by the Arini session)
- **Cargos** `/Game/DataAsset/Cargos_Arini` -- Arini island (new_cargos rows)
- **Cargos** `/Game/DataAsset/Cargos_CapitalistEconomy` -- Capitalist Economy (vanilla rows, stacking on, no volume discount)
- **Vehicles** `/Game/DataAsset/Vehicles/Vehicles_Arini` -- Arini island (changed + added vehicle rows, incl. Crany and Goliath4-DB from Vehicles_Deprecated)
- **Vehicles** `/Game/DataAsset/Vehicles/Vehicles_VehicleLabs` -- VehicleLabs (fuel pumps, bulk economy, removable body parts; D:/MTLiveMap/vehicle_mod/tables.py). After Arini: it carries Arini's rows with its own changes on top, so it must win
- **Vehicles** `/Game/DataAsset/Vehicles/Vehicles_Biceps` -- Biceps (standalone car, row C0100_Biceps; built by the Arini session)
- **Vehicles** `/Game/DataAsset/Vehicles/Vehicles_BoaterTown` -- Boater Town: Beyond the Waves (C0700_Tugboat, C0701_ContainerShip; built by the Arini session)

### Teh (1)

- **VehicleParts** `/Game/DataAsset/VehicleParts/VehicleParts_TehEngines` -- Engine Sound Pack (0.7.20 port by qxZap)

### AMC (1)

- **VehicleParts** `/Game/DataAsset/VehicleParts/VehicleParts_AMCTires` -- Tires (0.7.20 port by qxZap)

### Suspension Expansion (1)

- **VehicleParts** `/Game/DataAsset/VehicleParts/VehicleParts_SuspensionExpansion` -- Suspension Expansion (0.7.20 port by qxZap)

### Rak (6)

- **VehicleParts** `/Game/RakMods/HeavyHaulPack/Parts/Engine/RHHP_Engines` -- Heavy Haul Pack
- **VehicleParts** `/Game/RakMods/HeavyHaulPack/Parts/Tires/RHHP_Tires` -- Heavy Haul Pack
- **VehicleParts** `/Game/RakMods/HeavyHaulPack/Parts/Transmissions/RHHP_Transmissions` -- Heavy Haul Pack
- **VehicleParts** `/Game/RakMods/HeavyHaulPack/Parts/RHHP_Parts` -- Heavy Haul Pack
- **VehicleParts** `/Game/RakMods/HeavyHaulPack/Parts/RHHP_Misc` -- Heavy Haul Pack
- **Vehicles** `/Game/RPMTech/DataAsset/RPMTech_Vehicle` -- RPMTech vehicles

### qxZap/sati (2)

- **VehicleParts** `/Game/DataAsset/VehicleParts/VehicleParts_Biceps` -- Biceps
- **CharacterBodyParts** `/Game/DataAsset/CharacterBody/CharacterBodyParts_Biceps` -- Biceps

### Maja (1)

- **Items** `/Game/DataAsset/Items/Items_MajasDetailWorks` -- Detail Works

### SlideZone (3)

- **Items** `/Game/DataAsset/Items/Items_SlidesAttachments` -- Slide Industries Attachments
- **Items** `/Game/DataAsset/Items/Items_SlidesDashboards` -- Slide Industries Attachments
- **CharacterBodyParts** `/Game/DataAsset/CharacterBody/CharacterBodyParts_Slides` -- Slide Industries Attachments

### qxZap & satigt3 (1)

- **Items** `/Game/DataAsset/Items/Items_MoreAttachments` -- MoreAttachments (free and premium share it)

## Reserved car slots

rtwin's ReservedVehicleFramework layout: **Slot01 to Slot32**. A car mod ships its own slot's tables at `/Game/ReservedRegistration/Slots/SlotNN/<table>`; the framework lists every slot after the adopted tables, with no stubs, and a slot whose car is not installed is skipped. The decal table works the same way (`SlotNN/DT_Decals`).

Tables per slot: Vehicles -> `DT_Vehicles`, VehicleParts -> `DT_VehicleParts`, Decals -> `DT_Decals`

| Slot | Taken by |
|---|---|
| Slot01 | qxZap - Suspension Tuning (Big Brake Kits, VehicleParts only) |
| Slot02 | free |
| Slot03 | free |
| Slot04 | free |
| Slot05 | free |
| Slot06 | free |
| Slot07 | free |
| Slot08 | free |
| Slot09 | free |
| Slot10 | free |
| Slot11 | free |
| Slot12 | free |
| Slot13 | free |
| Slot14 | free |
| Slot15 | free |
| Slot16 | free |
| Slot17 | free |
| Slot18 | free |
| Slot19 | free |
| Slot20 | free |
| Slot21 | free |
| Slot22 | free |
| Slot23 | free |
| Slot24 | free |
| Slot25 | free |
| Slot26 | free |
| Slot27 | free |
| Slot28 | free |
| Slot29 | free |
| Slot30 | free |
| Slot31 | free |
| Slot32 | free |

## Channels (retired)

The first 0.7.20 build handed out channels: `Ch0001` to `Ch1000` in each of the 14 composites (14,000 stubs), later channels winning. They were replaced by adopted tables, so the framework no longer ships channel stubs and a `ChNNNN` file is never read. Every channel that was handed out moved:

| Composite | Channel | Was | Now listed as |
|---|---|---|---|
| VehicleParts | Ch0001 | qxZap - MoreTuning | `VehicleParts_MoreTuning` |
| VehicleParts | Ch0002 | qxZap - MoreTuning No Limits | `VehicleParts_MoreTuningNoLimits` |
| VehicleParts | Ch0003 | qxZap - MoreTuning Carbon | `VehicleParts_MoreTuningCarbon` |
| VehicleParts | Ch0004 | Teh - Engine Sound Pack (port by qxZap) | `VehicleParts_TehEngines` |
| VehicleParts | Ch0005 | Suspension Expansion (port by qxZap) | `VehicleParts_SuspensionExpansion` |
| Items | Ch0001 | qxZap & satigt3 - MoreAttachments | `Items_MoreAttachments` |

No channel is open for new mods: register your own table instead (see the README).
