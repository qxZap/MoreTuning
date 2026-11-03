# Hosting MoreTuning on a dedicated server

**Private working notes.** The MoreTuning repo has a public remote; nothing
here is committed or pushed without a deliberate decision.

A modded client cannot join a vanilla dedicated server, and it cannot join a
*modded* one either unless the server carries the same data. This is what
that takes, measured on Motor Town 0.7.20+T2 (B1143).

---

## 1. Why the client paks cannot just be copied over

Motor Town cooks its content twice, and the two are not interchangeable.
Dropping a client pak on a server gives you a server that **exits with code
3** before it ever logs anything.

The same pak, stripped of its art, loads fine. The distinction is sharp:

| pak content | server result |
|---|---|
| everything (tables + sounds + meshes) | **exit code 3**, no log output |
| tables and part definitions, **sounds excluded** | starts, reaches `Session created!` |

The crash report names the reason exactly:

```
LowLevelFatalError [File:...AsyncLoading.cpp] [Line: 3561]
SoundWave /Game/Cars/Parts/Engine/Sound/Bike/sportster1200/4_1000_Mid_Exhaust:
  Serial size mismatch: Got 62, Expected 134
```

A client-cooked `SoundWave` is serialized differently from the server's, and the
mismatch is fatal rather than a warning. **MoreTuning's own pak carries 985
sound files** (and 360 of the 683 assets in it), so the sounds are the whole
problem -- and they are also why the client's hash still differs from the
server's afterwards.

The strip tool lives in the MTLiveMap repo and was extended for this:

```bat
python server_safe_pak.py "<client Paks>\qxZap_MoreTuning_P.pak" ^
    --keep "DataTableFramework,Cars/Parts" --exclude "Sound" ^
    --out "<server Paks>\zzzz_MoreTuning_ServerSafe_P.pak"
```

| pak | keep | exclude | result |
|---|---|---|---|
| `qxZap_MoreTuning_P.pak` | `DataTableFramework,Cars/Parts` | `Sound` | 683 → 322 assets, 66 MB → 1 MB |
| `AAAA_DataTableFramework_P.pak` | `DataTableFramework` | – | 14025 → 14000 assets (ship whole: it is all tables) |
| `qxZap_MoreTuning_xNoLimits_P.pak` | `DataTableFramework` | – | 1 asset (the `VehicleParts` channel) |
| `qxZap_MoreTuning_yCarbon_P.pak` | `DataTableFramework` | – | 1 asset |
| `Z_SuspensionExpansion_P.pak` | `DataTableFramework` | – | 1 asset |
| `Z_TehsEngineSoundPack_P.pak` | `DataTableFramework,Cars/Parts` | `Sound` | 94 → 25 assets -- **it carries 16 engines, not just audio** |

Two of these are easy to get wrong:

- **`Z_TehsEngineSoundPack_P.pak` is not just sounds.** It carries Teh's 16
  engines in the `VehicleParts` channel (Ch0004). Skip it and the server's
  vehicle table is missing those rows.
- **The framework pak must be whole.** Its `DataTableFramework/**` holds all
  14000 channel files *and* the composites (`VehicleParts`, `Vehicles`,
  `Items`, `Cargos`, `Emotes`, `CharacterBodyParts`, `Buildings`, `Buffs`, the
  four `DT_Voice_*`, `HelpText`, `RichImageAll2`). The stripped version of it
  was missing six composites and made the client's `Items` hash differ too.
  Its name starts with `AAAA_` on purpose: it has to mount first.

## 2. The balance ini

None. MoreTuning no longer ships `DefaultMotorTownBalance.ini`; the lower fuel
burn of its large engines is in the engine assets themselves (`FuelRealism/run.py`
halves `FuelConsumption` on Large engines instead of setting
`LargeEngineFuelConsumption` to 0.04). The server runs its vanilla ini.

## 3. The server's config

```json
"bAllowModdedVehicle": true,
"GameDataValidation": {
  "bAllowVehicleAndPartsMismatch": true,
  "bAllowCargoMismatch": true,
  "bAllowItemMismatch": true,
  "bAllowConsoleVariableMismatch": true,
  "bAllowBalanceTableMismatch": true
}
```

`bAllowVehicleAndPartsMismatch` is the *table* check (the client's vehicle and
parts tables against the server's). `bAllowModdedVehicle` is the *vehicle*
check (the vehicle the player spawns). Both are needed for a modded client.

**`bAllowBalanceTableMismatch: false` makes a server unjoinable for anyone.**
Client-vanilla and server-vanilla balance tables differ in the payment rows
(`NavigatedTowRequestPaymentPer1Km` 500 vs 1000, `VehicleDeliveryPaymentPer1Km`
500 vs 1000), so a vanilla client is refused too. Measured:
with the client's balance patched back to vanilla, the balance category still
differed. Leave it `true`.

### More than 100 players

`MaxPlayers` in the json is clamped to 100, and the clamp is a plain console
variable, not a cheat one. Two settings, no plugin (tested 2026-11-03, B1147,
`GameSession.MaxPlayers` read back as 200):

- `MotorTown\Config\UserEngine.ini`, `[ConsoleVariables]`: `mh.netMaxPlayerCount=200`
  (the clamp, default 100).
- The launch line: `Jeju_World?listen?MaxPlayers=200` (the engine's own session limit,
  which the json does not reach), plus `"MaxPlayers": 200` in the json.

Not tested: an actual 101st player, what the server list shows, and whether the
game's per-player systems hold up past 100.

## 4. Verify, in this order

1. The server must reach **`Session created!`**. A wrong pak here does not
   error -- it runs forever and never appears in a listing.
2. The client joins, with the usual "these game data differ" warning. That
   warning is expected and harmless: the client still has the 360 sound assets
   the server cannot carry, so the hash differs even though the *data* matches.
3. The modded vehicle spawns and drives. The server's own log is the proof:
   it prints the row id it resolved the vehicle from.

   ```
   vanilla server:  Player entered vehicle. … Vehicle=Fortem(1068262)
   modded server:   Player entered vehicle. … Vehicle=Fortem(1103752)
   ```

   The id changed, so the server resolved the vehicle out of **MoreTuning's**
   table, not the vanilla one.

4. Attachments and cargo ride the same way: the `Items` channel
   (`qxZap_satigt3_MoreAttachments_P.pak`, `DataTableFramework/Items/Ch0001`)
   has to be on the server too, or the server has no rows for the attachment
   items.

## 5. What is left over

The client's dialog keeps listing `Vehicles / Parts` as differing, because the
client has 360 sound assets under `Cars/Parts/Engine/Sound/` that the server
cannot have. Removing that last difference needs a **WindowsServer cook** of
the mod's sound assets -- client-cooked ones are fatal on the server, and the
mod author is the only one who can cook them for the server target.

That also means: a client whose data differs from the server's in any category
the server disallows is refused **by the client, before it connects** (the
server log shows `players=0 conns=0`, no connection at all). That check is the
game's own, and it lives in native code.
