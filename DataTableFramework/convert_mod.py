"""Turn the tables a mod adds to a composite into DataTableFramework channels.

    python DataTableFramework/convert_mod.py <mod Content dir> <Composite>=<n>:<Table>[,<Table>...] ...
    python DataTableFramework/convert_mod.py demo

For each composite the named tables (found anywhere under the Content dir) become
one channel file, <Content>/DataTableFramework/<Composite>/Ch<n> -- one mod, one
channel file per composite, every source's hard references grafted across, and a
row name defined twice is an error. The source tables are then deleted from the
tree. Row names are kept: saves and vendors key on them.

Then: drop any copy of the composite itself from the tree, claim the channel
numbers in registry.json, and repack. A copy of the composite still in the tree
is reported, not deleted -- that is a decision about someone else's mod.
"""
import copy
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Rebase"))
from pipeline import WORK, register_names, to_json  # noqa: E402
from rebase import fname_base, fnames_in, graft_imports  # noqa: E402

_spec = importlib.util.spec_from_file_location("dtframework", os.path.join(HERE, "run.py"))
framework = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(framework)


def parse_spec(arg):
    """"Items=2:Items_A,Items_B" -> ("Items", 2, ["Items_A", "Items_B"])."""
    comp, rest = arg.split("=", 1)
    n, tables = rest.split(":", 1)
    names = [t for t in tables.split(",") if t]
    if not comp or not names or not 1 <= int(n) <= 1000:
        raise ValueError(f"bad spec {arg!r}")
    return comp, int(n), names


def find(content, name):
    hits = [os.path.join(d, f) for d, _, fs in os.walk(content) for f in fs if f == name + ".uasset"]
    if len(hits) != 1:
        sys.exit(f"FAIL: {name}.uasset found {len(hits)} times under {content}")
    return hits[0]


def combine(parts):
    """One table from [(source table, rows)]: the first source's imports, every other's grafted in."""
    base, rows = copy.deepcopy(parts[0][0]), copy.deepcopy(parts[0][1])
    for source, more in parts[1:]:
        more = copy.deepcopy(more)
        grafted = graft_imports(base, source["Imports"], more)
        register_names(base, [fname_base(e[k]) for e in grafted for k in ("ObjectName", "ClassPackage", "ClassName")])
        rows += more
    names = [r["Name"] for r in rows]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        sys.exit(f"FAIL: rows defined twice in one channel: {dupes[:10]}")
    return base, rows


def convert(content, comp, n, names):
    work = os.path.join(WORK, "convert_mod")
    os.makedirs(work, exist_ok=True)
    parts, files = [], []
    for name in names:
        path = find(content, name)
        t = framework.load(to_json(path, os.path.join(work, name + ".json")))
        if not t["Exports"][0]["$type"].startswith("UAssetAPI.ExportTypes.DataTableExport"):
            sys.exit(f"FAIL: {name} reads as {t['Exports'][0]['$type']} -- wrong mappings, or not a DataTable")
        parts.append((t, t["Exports"][0]["Table"]["Data"]))
        files.append(path)
    table, rows = combine(parts)
    ch = framework.make_channel(table, comp, n, rows)
    register_names(ch, [x for r in rows for x in fnames_in(r)])
    framework.write_channel(ch, comp, n, content)  # exits unless it reads back as a DataTable with every row
    for path in files:
        for ext in (".uasset", ".uexp", ".ubulk"):
            if os.path.isfile(path[:-7] + ext):
                os.remove(path[:-7] + ext)
    print(f"  {comp}/{framework.channel(n)}: {len(rows)} rows from {', '.join(names)}")
    left = [os.path.join(d, f) for d, _, fs in os.walk(content) for f in fs if f == comp + ".uasset"]
    if left:
        print(f"  NOTE: a copy of the {comp} composite is still in the tree: {left}")


def demo():
    assert parse_spec("Items=2:Items_A,Items_B") == ("Items", 2, ["Items_A", "Items_B"])
    for bad in ("Items=0:A", "Items=2:", "=2:A"):
        try:
            parse_spec(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["demo"]:
        demo()
    elif len(sys.argv) < 3:
        sys.exit(__doc__)
    else:
        for spec in sys.argv[2:]:
            convert(sys.argv[1], *parse_spec(spec))
