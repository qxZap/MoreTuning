"""Re-serialize cooked assets whose class layout the game update changed.

    python Rebase/reserialize.py <old_mappings>[,<older>...] <folder> [<folder> ...]
    python Rebase/reserialize.py demo

Unversioned properties are written by index into the class's property list
(super classes first). When an update removes or inserts a property anywhere
but the end, every later index shifts and the asset reads back wrong -- 0.7.20
dropped MTInteractableComponent.bUseServerOnPreInteraction, which turned the
interactable on all 713 MoreAttachments actors into a RawExport.

So: diff the two usmaps, find every class whose flattened property list is no
longer a prefix-extension of the old one, and round-trip only the assets that
export one of those classes -- read with the old usmap, drop properties that no
longer exist, write with the new one, and check nothing reads back raw.
Assets with no affected class (meshes, textures, sounds) are left byte-for-byte.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, r"D:\MTLiveMap\capitalist_economy\tools")
from pipeline import CURRENT_MAPPINGS, WORK, from_json, to_json  # noqa: E402

MAPPINGS_DIR = os.path.join(os.environ["LOCALAPPDATA"], "UAssetGUI", "Mappings")


def flat(structs, name):
    out = []
    chain = []
    while name in structs:
        chain.append(name)
        name = structs[name][0]
    for cls in reversed(chain):  # super first, as UE serializes
        out += [p[1] for p in structs[cls][1]]
    return out


def shifted(old, new):
    """Classes whose serialized layout moved -> {class: names that no longer exist}.

    A class is affected when its own property indices moved, or when any struct it
    holds (directly, in an array, map or set) is affected -- that struct's bytes
    are inside the class's export, so they misread just the same.
    """
    out = {}
    for name in new:
        if name not in old:
            continue
        a, b = flat(old, name), flat(new, name)
        if b[:len(a)] != a:
            out[name] = set(a) - set(b)
    grew = True
    while grew:
        grew = False
        for name in new:
            if name in out or name not in old:
                continue
            chain, k = [], name
            while k in new:
                chain.append(k)
                k = new[k][0]
            types = " ".join(p[2] for c in chain for p in new[c][1])
            if any(f"Struct<{s}>" in types for s in out):
                out[name] = set()
                grew = True
    return out


def classes_of(table):
    imports = table["Imports"]
    return {imports[-e["ClassIndex"] - 1]["ObjectName"] for e in table["Exports"]
            if isinstance(e.get("ClassIndex"), int) and e["ClassIndex"] < 0}


def raw_count(table):
    return sum(e["$type"].startswith("UAssetAPI.ExportTypes.RawExport") for e in table["Exports"])


def drop(table, gone):
    n = 0
    for e in table["Exports"]:
        data = e.get("Data")
        if isinstance(data, list):
            keep = [p for p in data if p.get("Name") not in gone]
            n += len(data) - len(keep)
            e["Data"] = keep
    return n


def split_autoshift(props):
    """0.7.20: MHTransmissionProperty.AutoShiftComportRPM -> _Gasoline + _Diesel.

    Vanilla's own boxes say how: an old value of 2500 or less was a diesel
    figure and went to _Diesel, with _Gasoline at 3500; anything higher went to
    _Gasoline, with _Diesel at 2300.
    """
    old = next((p for p in props if p.get("Name") == "AutoShiftComportRPM"), None)
    if old is None:
        return props
    rpm = old["Value"]
    rpm = float(rpm) if not isinstance(rpm, str) else 0.0
    gas, diesel = (3500.0, rpm) if rpm <= 2500 else (rpm, 2300.0)
    out = []
    for p in props:
        if p is old:
            for suffix, v in (("_Gasoline", gas), ("_Diesel", diesel)):
                q = dict(old)
                q.update(Name="AutoShiftComportRPM" + suffix, Value=v, IsZero=False)
                out.append(q)
        else:
            out.append(p)
    return out


# Fields an update renamed or split: struct property name -> rewrite of its fields.
FIELD_MIGRATIONS = {"TransmissionProperty": split_autoshift}


def migrate_fields(node):
    if isinstance(node, dict):
        fix = FIELD_MIGRATIONS.get(node.get("Name"))
        if fix and isinstance(node.get("Value"), list):
            node["Value"] = fix(node["Value"])
        for v in node.values():
            migrate_fields(v)
    elif isinstance(node, list):
        for v in node:
            migrate_fields(v)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run(old_mappings, folders):
    """old_mappings: tried in order per asset -- a mod folder can hold assets last
    built against different game versions."""
    import compare_usmap
    _, new = compare_usmap.parse(os.path.join(MAPPINGS_DIR, CURRENT_MAPPINGS + ".usmap"))
    layouts = []
    for m in old_mappings.split(","):
        _, old = compare_usmap.parse(os.path.join(MAPPINGS_DIR, m + ".usmap"))
        layouts.append((m, shifted(old, new)))
        print(f"{len(layouts[-1][1])} classes changed layout {m} -> {CURRENT_MAPPINGS}")
    work = os.path.join(WORK, "reserialize")
    os.makedirs(work, exist_ok=True)
    done = skipped = 0
    failed = []
    for folder in folders:
        for dirpath, _, files in os.walk(folder):
            for f in sorted(files):
                if not f.endswith(".uasset"):
                    continue
                path = os.path.join(dirpath, f)
                for m, moved in layouts:
                    before = load(to_json(path, os.path.join(work, "old.json"), m))
                    if not raw_count(before):
                        break
                else:
                    # Raw under every older usmap but clean under the current one:
                    # already re-serialized by an earlier run.
                    if not raw_count(load(to_json(path, os.path.join(work, "new.json")))):
                        skipped += 1
                    else:
                        failed.append(f"{path}: raw under every one of {old_mappings}")
                    continue
                hit = classes_of(before) & set(moved)
                if not hit:
                    # Trust the diff, but check it: untouched must read no worse.
                    now = load(to_json(path, os.path.join(work, "new.json")))
                    if raw_count(now) > raw_count(before):
                        failed.append(f"{path}: reads raw under {CURRENT_MAPPINGS} but no class "
                                      f"of {sorted(classes_of(before))} changed layout")
                    skipped += 1
                    continue
                gone = set().union(*(moved[c] for c in hit))
                migrate_fields(before)
                drop(before, gone)
                src = os.path.join(work, "fixed.json")
                with open(src, "w", encoding="utf-8") as fh:
                    json.dump(before, fh)
                out = os.path.join(work, "fixed.uasset")
                from_json(src, out)
                after = load(to_json(out, os.path.join(work, "check.json")))
                if raw_count(after) or len(after["Exports"]) != len(before["Exports"]):
                    failed.append(f"{path}: still reads raw under {CURRENT_MAPPINGS}")
                    continue
                for ext in (".uasset", ".uexp"):
                    shutil.copy2(out[:-len(".uasset")] + ext, path[:-len(".uasset")] + ext)
                done += 1
                print(f"  {done} re-serialized ({f}: {sorted(hit)})", end="\r")
    print(f"\n{done} re-serialized, {skipped} untouched, {len(failed)} failed")
    for line in failed:
        print("  FAIL", line)
    if failed:
        sys.exit(1)


def demo():
    old = {"Base": (None, [(0, "A", "Int")]),
           "Comp": ("Base", [(0, "Keep", "Int"), (1, "Gone", "Bool"), (2, "Tail", "Int")]),
           "Grown": ("Base", [(0, "X", "Int")])}
    new = {"Base": (None, [(0, "A", "Int")]),
           "Comp": ("Base", [(0, "Keep", "Int"), (1, "Tail", "Int")]),
           "Grown": ("Base", [(0, "X", "Int"), (1, "Y", "Int")])}
    assert flat(old, "Comp") == ["A", "Keep", "Gone", "Tail"]
    assert shifted(old, new) == {"Comp": {"Gone"}}, "appending at the end is not a shift"
    old["Holder"] = (None, [(0, "C", "Struct<Comp>")])
    new["Holder"] = (None, [(0, "C", "Struct<Comp>")])
    assert "Holder" in shifted(old, new), "holding a shifted struct is a shift"
    for rpm, want in ((2000.0, (3500.0, 2000.0)), (5000.0, (5000.0, 2300.0))):
        out = split_autoshift([{"Name": "Type"}, {"Name": "AutoShiftComportRPM", "Value": rpm}])
        assert [p["Name"] for p in out] == ["Type", "AutoShiftComportRPM_Gasoline", "AutoShiftComportRPM_Diesel"]
        assert (out[1]["Value"], out[2]["Value"]) == want
    t = {"Exports": [{"Data": [{"Name": "Keep"}, {"Name": "Gone"}]}]}
    assert drop(t, {"Gone"}) == 1 and t["Exports"][0]["Data"] == [{"Name": "Keep"}]
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["demo"]:
        demo()
    elif len(sys.argv) < 3:
        sys.exit(__doc__)
    else:
        run(sys.argv[1], sys.argv[2:])
