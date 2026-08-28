"""Build the dedicated-server edition of MoreTuning.

Why this exists
---------------
A dedicated server cooks audio out. Its pak still carries the sound *assets* --
but only .uasset/.uexp stubs with no .ubulk payload, and only for the folders
vanilla ships: Truck, V8, v12, Bike, I4Sport, 2Stroke, Electric, V6Sport,
Backfire.

MoreTuning's engines hard-import cues under Cars/Parts/Engine/Sound/<custom>/ --
N14, C18, d13, x15, LS3, vr6 and eighty more. None of those packages exist on a
server, so the import fails, the MHEngineDataAsset fails to load, and the engine
is listed in the shop but does not work. That is the bug this fixes.

What it builds
--------------
The same tables and the same engines with the same stats, but every sound
reference repointed at a cue the server already ships, and no custom audio in
the pak at all. 66 MB becomes about 1 MB.

Sound is client-side presentation, so nothing about the simulation changes.
Players keep the full mod and hear the real engines; the server only has to
agree about which parts exist and what they do.

    python ServerBuild/run.py            # build and report
    python ServerBuild/run.py --pack     # ...and write the pak
    python ServerBuild/run.py demo       # self-check
"""
import json
import io
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(REPO, "Rebase"))
from pipeline import to_json, from_json          # noqa: E402  (shared plumbing)

# --------------------------------------------------------------------------
# Config -- the things a game update moves
# --------------------------------------------------------------------------
REPAK = r"D:\MT\PakMerge\repak.exe"

# The dedicated server's own pak. This is the authority on what a server can
# resolve, so the build is validated against it rather than against a guess.
SERVER_PAKS = (r"D:\SteamLibrary\steamapps\common"
               r"\Motor Town Behind The Wheel - Dedicated Server\MotorTown\Content\Paks")
SERVER_PAK = os.path.join(SERVER_PAKS, "MotorTown-WindowsServer.pak")
AES_KEY = "0xD9633F9140D5494AE4A469BDA384896BD1B9644D50D281E64ECFF4900B8E8E80"

SOURCE = os.path.join(REPO, "qxZap_MoreTuning_P")
OUT_NAME = "qxZap_MoreTuning_Server_P"        # 'q' > 'm', so it mounts after the game pak
OUT = os.path.join(REPO, OUT_NAME)

# Everything under here is custom audio and is the whole reason for this build.
DROP = os.path.join("Cars", "Parts", "Engine", "Sound")
ENGINE_DIR = os.path.join("Cars", "Parts", "Engine")
WORK = os.path.join(HERE, "work")

# --------------------------------------------------------------------------
# Cues a dedicated server actually ships. Verified against SERVER_PAK on every
# run -- if an update drops one, the build stops rather than shipping a broken
# import.
# --------------------------------------------------------------------------
SND = "/Game/Cars/Parts/Engine/Sound"
TRUCK = SND + "/Truck/SC_Truck_05"          # heavy diesel
LIGHT_DIESEL = SND + "/Truck/SC_Truck_02"   # the lighter of the two truck cues
V8 = SND + "/V8/SC_V8Engine"
V12 = SND + "/v12/SC_V12Engine"
I4 = SND + "/I4Sport/SC_I4SportEngine"
BIKE = SND + "/Bike/Twin_650B"
TWO_STROKE = SND + "/2Stroke/SC_2StrokeEngine_Chainsaw"
ELECTRIC = SND + "/Electric/SC_ElectricMotor"
BACKFIRE = SND + "/Backfire/SC_Backfire"
JAKE = "/Game/Sounds/Vehicle/Brake/JakeBrake/SC_JakeBrake_01"
INTAKE = "/Game/Sounds/Vehicle/Intake/SC_Intake01"

# Properties whose replacement never depends on the engine.
FIXED = {"BackfireSound": BACKFIRE, "JakeBrakeSound": JAKE, "IntakeSound": INTAKE}

# Which vanilla cue an engine should fall back to, read off its own EnginesSound
# path, most specific first. The custom folders are named after the real engine
# ("lamboV12", "Bike/hayabusa", "x15"), so the path says more about what it is
# than the cue file inside it does -- those are clone leftovers and routinely
# say SC_V8Engine on a V12.
BY_KEYWORD = (
    ("lightdiesel", LIGHT_DIESEL),
    ("2stroke", TWO_STROKE),
    ("electric", ELECTRIC),
    ("/bike/", BIKE),
    ("truck", TRUCK),
    ("diesel", TRUCK),
    ("v12", V12),
    ("i4sport", I4),
)

# Folders to look in when refining the fallback -- see engine_cue().
CUE_FOLDER = {TRUCK: "Truck", LIGHT_DIESEL: "Truck", V8: "V8", V12: "v12",
              I4: "I4Sport", BIKE: "Bike", TWO_STROKE: "2Stroke",
              ELECTRIC: "Electric"}


# --------------------------------------------------------------------------
# What the server can resolve
# --------------------------------------------------------------------------
def server_packages(refresh=False):
    """Every /Game package inside the dedicated server's pak.

    Cached: listing a 1.5 GB encrypted pak takes a few seconds and only changes
    when the game does.
    """
    cache = os.path.join(WORK, "server_packages.txt")
    if not refresh and os.path.exists(cache):
        return set(io.open(cache, encoding="utf-8").read().split())
    if not os.path.exists(SERVER_PAK):
        sys.exit("no dedicated server pak at " + SERVER_PAK)
    out = subprocess.run([REPAK, "--aes-key", AES_KEY, "list", SERVER_PAK],
                         capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit("could not read the server pak: " + out.stderr.strip()[:200])
    head, tail = "MotorTown/Content/", ".uasset"
    pkgs = {"/Game/" + e[len(head):-len(tail)].replace("\\", "/")
            for e in out.stdout.split()
            if e.startswith(head) and e.endswith(tail)}
    os.makedirs(WORK, exist_ok=True)
    io.open(cache, "w", encoding="utf-8").write("\n".join(sorted(pkgs)))
    return pkgs


# --------------------------------------------------------------------------
# Rewriting one engine
# --------------------------------------------------------------------------
def package_of(doc, idx):
    """The Package import a given import sits under, as (position, entry)."""
    imps = doc["Imports"]
    outer = imps[-idx - 1]["OuterIndex"]
    return (-outer - 1, imps[-outer - 1]) if outer < 0 else (None, None)


def engine_cue(old_pkg, has_jake, have):
    """The vanilla cue that best matches one engine.

    A jake brake is the giveaway for a truck: N14, C18 and the rest are named
    after the engine, not the sound, so no keyword in the path says "diesel".
    Nothing else in the game fits one.
    """
    low = old_pkg.lower()
    cue = V8                                         # the general-purpose noise
    for word, pick in BY_KEYWORD:
        if word in low:
            cue = pick
            break
    else:
        if has_jake:
            cue = TRUCK
    # The mod borrows vanilla cues into its own folders (d13/SC_Truck_04), so if
    # that exact cue lives in the folder we landed on, keep the one it chose.
    same = SND + "/" + CUE_FOLDER[cue] + "/" + old_pkg.rsplit("/", 1)[-1]
    return same if same in have else cue


def replacement(prop, old_pkg, have, cue=V8):
    """Where a sound property should point on a server, or None to leave it.

    `have` is the set of packages the server ships, so the rules never guess at
    what exists -- they only choose between things it has.
    """
    if old_pkg in have:
        return None                                  # already fine
    if prop in FIXED:
        return FIXED[prop]
    if prop != "EnginesSound":
        return ""                                    # unknown sound -> null it
    return cue


def register(doc, name):
    if name and name not in doc["NameMap"]:
        doc["NameMap"].append(name)
    return name


def fix_engine(path, have, mine):
    """Repoint one engine's sound imports. Returns a list of (prop, old, new)."""
    work_json = os.path.join(WORK, "engine.json")
    to_json(path, work_json)
    doc = json.load(io.open(work_json, encoding="utf-8"))
    imps = doc["Imports"]

    # A package import shared by two cues cannot be repointed two ways. It does
    # not happen today; if an update makes it happen, stop rather than corrupt.
    users = {}
    for i, imp in enumerate(imps):
        if imp["OuterIndex"] < 0:
            users.setdefault(-imp["OuterIndex"] - 1, []).append(i)

    sounds = []
    for exp in doc["Exports"]:
        for prop in exp.get("Data", []):
            name, val = prop.get("Name", ""), prop.get("Value")
            if not name.endswith("Sound") or not isinstance(val, int) or val >= 0:
                continue
            pos, pkg = package_of(doc, val)
            if pkg is not None:
                sounds.append((prop, name, val, pos, pkg))

    # Pick the engine's cue before touching anything: it depends on the whole
    # asset, because the jake brake is what tells a truck from a car.
    engine = next((s for s in sounds if s[1] == "EnginesSound"), None)
    cue = engine_cue(engine[4]["ObjectName"],
                     any(s[1] == "JakeBrakeSound" for s in sounds),
                     have) if engine else V8

    # What each package import is used for, so the walk below knows which rule
    # applies to it.
    by_pos = {}
    for prop, name, val, pos, pkg in sounds:
        if len(users.get(pos, [])) > 1:
            sys.exit(os.path.basename(path) + ": package " + pkg["ObjectName"] +
                     " is shared by several imports -- cannot repoint safely")
        by_pos[pos] = (prop, name, val)

    # Walk every import, not only the ones a property points at. Cloning leaves
    # dead sound imports behind -- 812/SC_V12Engine sits in 21 engines that do
    # not use it -- and the linker resolves the whole import table, not just the
    # parts something reads.
    changed = []
    for pos, pkg in enumerate(imps):
        if pkg["ClassName"] != "Package" or pkg["ObjectName"] in have:
            continue
        if pkg["ObjectName"] in mine or not pkg["ObjectName"].startswith("/Game/"):
            continue
        prop, name, val = by_pos.get(pos, (None, "", None))
        new = replacement(name, pkg["ObjectName"], have, cue) if prop else cue
        changed.append((name or "(unused import)", pkg["ObjectName"], new or "(null)"))
        if not new:                                  # nothing sensible to play
            prop["Value"] = 0
            new = cue                                # but the import must resolve
        pkg["ObjectName"] = register(doc, new)
        for child in users.get(pos, []):
            imps[child]["ObjectName"] = register(doc, new.rsplit("/", 1)[-1])

    # The check that matters, done where the parsed asset is already in hand:
    # after this, nothing the linker resolves can be missing on a server.
    dangling = [i["ObjectName"] for i in imps
                if i["ClassName"] == "Package"
                and i["ObjectName"].startswith("/Game/")
                and i["ObjectName"] not in have and i["ObjectName"] not in mine]
    if dangling:
        sys.exit(os.path.basename(path) + " still imports " + ", ".join(dangling))

    if changed:
        json.dump(doc, io.open(work_json, "w", encoding="utf-8"), indent=2)
        from_json(work_json, path)
    return changed


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------
def copy_tree():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(SOURCE, OUT,
                    ignore=lambda d, names: names if DROP in d else [])
    dead = os.path.join(OUT, "MotorTown", "Content", DROP)
    if os.path.isdir(dead):                          # copytree still makes it
        shutil.rmtree(dead)


def packages_here():
    """Every /Game package this build itself ships."""
    root = os.path.join(OUT, "MotorTown", "Content")
    out = set()
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.endswith(".uasset"):
                rel = os.path.relpath(os.path.join(dirpath, f), root)[: -len(".uasset")]
                out.add("/Game/" + rel.replace(os.sep, "/"))
    return out


def build(pack=False):
    os.makedirs(WORK, exist_ok=True)
    have = server_packages()
    for cue in (TRUCK, LIGHT_DIESEL, V8, V12, I4, BIKE, TWO_STROKE, ELECTRIC,
                BACKFIRE, JAKE, INTAKE):
        if cue not in have:
            sys.exit("the server no longer ships " + cue + " -- pick a new fallback")
    print("server ships %d packages\n" % len(have))

    copy_tree()
    mine = packages_here()
    engine_root = os.path.join(OUT, "MotorTown", "Content", ENGINE_DIR)
    engines = sorted(f for f in os.listdir(engine_root) if f.endswith(".uasset"))
    touched = 0
    for i, f in enumerate(engines, 1):
        changed = fix_engine(os.path.join(engine_root, f), have, mine)
        if changed:
            touched += 1
            print("  [%3d/%d] %s" % (i, len(engines), f[:-7]))
            for prop, old, new in changed:
                print("           %-16s %-34s -> %s"
                      % (prop, old.split("/Sound/")[-1], new.split("/")[-1]))
    print("\n  %d of %d engines repointed at server cues" % (touched, len(engines)))

    print("  every engine import resolves on the server -- checked as each was built")

    size = sum(os.path.getsize(os.path.join(dp, f))
               for dp, _, fs in os.walk(OUT) for f in fs)
    print("  %.1f MB of content" % (size / 1048576.0))
    if pack:
        pak = os.path.join(REPO, OUT_NAME + ".pak")
        subprocess.run([REPAK, "pack", OUT, pak], check=True, capture_output=True)
        print("  packed %s.pak (%.1f MB)" % (OUT_NAME, os.path.getsize(pak) / 1048576.0))


# --------------------------------------------------------------------------
def demo():
    have = {SND + "/Truck/SC_Truck_04", TRUCK, V8, V12, BIKE, LIGHT_DIESEL,
            BACKFIRE, JAKE, INTAKE, SND + "/V6Sport/V6Sport_02/EngineSoundData"}

    # The one that drove the design: a Cummins N14 is named after the engine, so
    # no word in its path says truck. The jake brake is what gives it away.
    assert engine_cue(SND + "/N14/SC_N14_370HP", True, have) == TRUCK
    assert engine_cue(SND + "/N14/SC_N14_370HP", False, have) == V8
    # A vanilla cue borrowed into a custom folder is kept as-is.
    assert engine_cue(SND + "/d13/SC_Truck_04", True, have) == SND + "/Truck/SC_Truck_04"
    # The folder name beats the cue file, which is a clone leftover and lies.
    assert engine_cue(SND + "/laferrariV12/SC_V8Engine", False, have) == V12
    assert engine_cue(SND + "/GM572/SC_V8Engine", False, have) == V8,         "a big-block V8 must not inherit V12 from some other reference"
    assert engine_cue(SND + "/Bike/hayabusa", False, have) == BIKE
    assert engine_cue(SND + "/30tdi/SC_LightDiesel", True, have) == LIGHT_DIESEL,         "a light diesel stays light even though it carries a jake brake"

    # Already fine, and already-vanilla cues must not be touched.
    assert replacement("EnginesSound", TRUCK, have) is None
    assert replacement("EnginesSound", SND + "/V6Sport/V6Sport_02/EngineSoundData",
                       have) is None
    assert replacement("EnginesSound", SND + "/N14/SC_N14_370HP", have, TRUCK) == TRUCK
    # Fixed properties ignore the engine entirely.
    assert replacement("JakeBrakeSound", SND + "/N14/jake/SC_JakeBrake_01", have) == JAKE
    assert replacement("BackfireSound", SND + "/gone/SC_Backfire", have) == BACKFIRE
    # A sound with no rule is nulled, not pointed somewhere wrong.
    assert replacement("SuperchargerSound",
                       "/Game/Cars/Parts/Engine/GenericSounds/SC_X", have) == ""
    print("ok")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["demo"]:
        demo()
    else:
        build(pack="--pack" in args)
