"""After a game update: pull vanilla straight from the game's pak and rebuild the framework from it. One command.

    python DataTableFramework/update.py            pull, rebuild, pack
    python DataTableFramework/update.py --install  ... and copy both paks into the game (only with the game closed)
    python DataTableFramework/update.py --scan     ... also look for composites in folders nothing lists yet
    python DataTableFramework/update.py demo

1. Pull: repak with the game's AES key (MT_AES_KEY, from D:\\MTLiveMap\\mt_paths.py or the environment -- the pak opens
   with it, no FModel needed) unpacks DataAsset, GameMode and every folder the last build's manifest
   (composites.json) found a composite or a composite's parent in. --scan also reads every .uasset in the pak, a few
   hundred at a time, for a CompositeDataTable an update added elsewhere.
2. Refresh the vanilla export (pipeline.VANILLA, D:\\MT\\Output\\Exports): files that changed are copied in, and the
   previous copies go to D:\\MT\\Output\\_backup_<date>\\ first. Prints what changed.
3. Rebuild: run.py (every composite: vanilla parents + adopted tables + rtwin's slots), gameresource.py (Decals
   redirect + Arini's world map), dealers.py (DriveGameModeBP with the 32 dealer slot nodes; no stubs ship). Each reads vanilla fresh, so a
   changed GameResource or game mode is never shipped stale -- the framework outranks vanilla and would mask it.
4. Pack AAAA_DataTableFramework_99_P (the one framework pak); --install copies it into Paks.
"""
import datetime
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "Rebase"))
from pipeline import VANILLA  # noqa: E402

GAME = r"D:\SteamLibrary\steamapps\common\Motor Town\MotorTown"
GAME_PAK = os.path.join(GAME, "Content", "Paks", "MotorTown-Windows.pak")
REPAK = r"D:\MTLiveMap\tools\repak.exe"  # 0.2.2 with oo2core next to it: opens the game's Oodle pak
PACKER = r"D:\MT\PakMerge\repak.exe"
PAKS = ["AAAA_DataTableFramework_99_P"]  # the Slots stub pak is gone (dealers.py)
ALWAYS = ["MotorTown/Content/DataAsset", "MotorTown/Content/GameMode"]
CHUNK = 150  # -i paths per repak call: well under Windows' command-line limit


def aes_key():
    if os.environ.get("MT_AES_KEY"):
        return os.environ["MT_AES_KEY"]
    sys.path.insert(0, r"D:\MTLiveMap")
    from mt_paths import MT_AES_KEY
    return MT_AES_KEY


def repak(*args, check=True):
    r = subprocess.run([REPAK, "-a", aes_key(), *args], capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"FAIL: repak {args[0]}: {r.stderr.strip()[-300:]}")
    return r.stdout


def folders():
    """Pak folders to pull: always DataAsset and GameMode, plus every folder holding a known composite."""
    out = list(ALWAYS)
    man = os.path.join(HERE, "composites.json")
    for e in json.load(open(man, encoding="utf-8")) if os.path.isfile(man) else []:
        for p in [e["path"]] + e.get("vanilla_parents", []):
            d = "MotorTown/Content/" + p[len("/Game/"):].rsplit("/", 1)[0] if p.count("/") > 2 else "MotorTown/Content"
            if d not in out and not any(d.startswith(a + "/") for a in out):
                out.append(d)
    return out


def pull(dest, scan):
    dirs = folders()
    root_files = [d for d in dirs if d == "MotorTown/Content"]  # the content root itself: its own assets only
    dirs = [d for d in dirs if d != "MotorTown/Content"]
    entries = [l.strip() for l in repak("list", GAME_PAK).splitlines() if l.strip()]
    picks = list(dirs)
    if root_files:  # composites straight under /Game: those files, not the whole game
        picks += [e for e in entries if e.count("/") == 2 and e.startswith("MotorTown/Content/")]
    if scan:  # every .uasset outside the pulled folders, for a composite an update put somewhere new
        picks += [e for e in entries if e.endswith(".uasset") and not any(e.startswith(d + "/") for d in dirs)]
    for i in range(0, len(picks), CHUNK):
        args = []
        for p in picks[i:i + CHUNK]:
            args += ["-i", p]
        repak("unpack", GAME_PAK, "-o", dest, "-f", *args)
    if scan:  # keep a scanned folder only where a composite turned up, and pull its .uexp too
        from run import MARKER
        found = set()
        for dp, _, fs in os.walk(os.path.join(dest, "MotorTown", "Content")):
            for f in fs:
                if f.endswith(".uasset") and MARKER in open(os.path.join(dp, f), "rb").read():
                    rel = os.path.relpath(os.path.join(dp, f), dest).replace(os.sep, "/")
                    if not any(rel.startswith(d + "/") for d in dirs):
                        found.add(rel[: -len(".uasset")])
        for rel in sorted(found):
            print(f"  scan: new composite {rel}")
            repak("unpack", GAME_PAK, "-o", dest, "-f", "-i", rel + ".uasset", "-i", rel + ".uexp")
    return os.path.join(dest, "MotorTown", "Content")


def refresh(src):
    """Copy changed/new vanilla files into the export, backing up what they replace. Returns (changed, new)."""
    backup = os.path.join(os.path.dirname(os.path.dirname(VANILLA.rstrip("\\/"))), "_backup_" + datetime.date.today().isoformat(), "MotorTown", "Content")
    changed, new = [], []
    for dp, _, fs in os.walk(src):
        for f in fs:
            s = os.path.join(dp, f)
            rel = os.path.relpath(s, src)
            d = os.path.join(VANILLA, rel)
            if os.path.isfile(d) and filecmp.cmp(s, d, shallow=False):
                continue
            if os.path.isfile(d):
                b = os.path.join(backup, rel)
                os.makedirs(os.path.dirname(b), exist_ok=True)
                if not os.path.exists(b):
                    shutil.copy2(d, b)
                changed.append(rel)
            else:
                new.append(rel)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
    return changed, new


def step(script, work):
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, script)], cwd=ROOT, env=dict(os.environ, DTF_WORK=work))
    if r.returncode:
        sys.exit(f"FAIL: {script} exited {r.returncode}")


def main(argv):
    install, scan = "--install" in argv, "--scan" in argv
    with tempfile.TemporaryDirectory() as t:
        print("== pulling vanilla from", os.path.basename(GAME_PAK))
        src = pull(t, scan)
        changed, new = refresh(src)
    stems = lambda xs: sorted({os.path.splitext(x)[0].replace(os.sep, "/") for x in xs})
    print(f"   {len(stems(changed))} assets changed, {len(stems(new))} new since the last pull")
    for x in stems(changed):
        print("   changed:", x)
    for x in stems(new)[:20]:
        print("   new:", x)
    print("== rebuilding")
    work = os.path.join(ROOT, "Rebase", "work", f"fw_{os.getpid()}")  # this run's own scratch: no collisions
    for s in ("run.py", "gameresource.py", "dealers.py"):
        step(s, work)
    print("== packing")
    for p in PAKS:
        subprocess.run([PACKER, "pack", os.path.join(ROOT, p)], check=True, capture_output=True)
        print("  ", p + ".pak", os.path.getsize(os.path.join(ROOT, p + ".pak")), "bytes")
    if install:
        if "MotorTown-Win64-Shipping" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout:
            sys.exit("game running: not installed (close it and run with --install again)")
        for p in PAKS:
            shutil.copy2(os.path.join(ROOT, p + ".pak"), os.path.join(GAME, "Content", "Paks", p + ".pak"))
        print("   installed into", os.path.join(GAME, "Content", "Paks"))


if __name__ == "__main__":
    if sys.argv[1:] == ["demo"]:
        f = folders()
        assert f[:2] == ALWAYS and "MotorTown/Content/Characters/Voice" in f and "MotorTown/Content/UI/RichText" in f, f
        assert not any(d.startswith("MotorTown/Content/DataAsset/") for d in f), "DataAsset subfolders are pulled whole"
        print("demo ok:", f)
    else:
        main(sys.argv[1:])
