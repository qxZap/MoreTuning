# WheelWorkshop

Wheels in every size, built against whatever wheel mods are installed.

    python run.py                 # what it would build, and how big
    python run.py --build         # build it
    python run.py --build Maja    # only sources whose name matches
    python run.py demo            # self-check

## Configuration

Everything lives at the top of `run.py`, not in the environment, so a game
update is one edit:

| | |
|---|---|
| `UASSETGUI`, `REPAK` | tool paths |
| `MAPPINGS` | `MotorTown719` — bump this on a game update |
| `ENGINE_VERSION` | `VER_UE5_4` |
| `GAME_PAKS`, `GAME_EXPORT` | where the game and its extracted files are |
| `SCALE_MIN/MAX/STEP` | 0.5x to 2.0x in 10% steps |
| `RIMS` | which rims to offer in every size, or `None` for all 93 |
| `SKIP_SOURCES` | mods that ship a wheel table but are not wheel mods |

## Why one pak per source

Several mods ship their own `Wheels` table and only the last one loaded is used,
so a single build would silently delete whichever it did not know about. Every
installed source is found and gets its own pak, built from that source's table,
so its rims survive alongside the sized ones. Install the one matching your
setup.

Output is named `zzzz_` deliberately. Load order is by filename and last wins,
and ASCII puts every lowercase letter after every uppercase one, so a `ZZZ_`
prefix loses to `qxZap_MoreTuning_yCarbon_P` and to `zzzProxyTechWheels`.

## How the resizing works

A wheel mesh is a 1 metre circle and the vehicle scales it, so size is not a
property anywhere -- it is the geometry.

* **Vertices.** The render data is an opaque blob, but a position buffer inside
  it is a stride of 12, a vertex count, then that many packed float triples. A
  stride of 12 also occurs by chance, so a candidate is only accepted if the
  coordinates reproduce the mesh's own stated bounds. Then every position is
  multiplied.
* **Bounds.** Scaled by the same factor, because the collision follows them.
  Bounds alone move the collision and leave the wheel drawing at its old size;
  vertices alone leave it floating.
* **The export is renamed** to match its package, or the row resolves to nothing.
* **Meshes are hard `ObjectProperty` imports**, not soft paths. A soft path does
  not write at all.

Only the game's own rims are resized. A mod's rim is that mod's to ship.
