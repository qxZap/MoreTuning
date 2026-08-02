"""Sanity-check a built part table: python verify.py <table_roundtrip.json> [content_dir ...]

Reads UAssetGUI `tojson` output of a table you just built and asserts the things
that silently go wrong: the export parsed as a DataTable at all, no leftover
hard imports of part assets, every asset reference is a soft path, and -- if any
Content dirs are given (pass both the mod's and the game export's) -- that every
referenced package exists in one of them.
"""
import json
import os
import sys

ASSET_REF_PROPS = ("EngineAsset", "TransmissionAsset", "LSDAsset")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    content_roots = sys.argv[2:]

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    export = data["Exports"][0]
    if not export["$type"].startswith("UAssetAPI.ExportTypes.DataTableExport"):
        sys.exit(f"FAIL {path}: parsed as {export['$type'].split(',')[0]}, not a DataTable")

    rows = export["Table"]["Data"]
    problems = []
    refs = set()
    for row in rows:
        for prop in row["Value"]:
            if prop["Name"] not in ASSET_REF_PROPS:
                continue
            if not prop["$type"].startswith("UAssetAPI.PropertyTypes.Objects.SoftObjectPropertyData"):
                problems.append(f"{row['Name']}.{prop['Name']} is still a hard {prop['$type'].split(',')[0].split('.')[-1]}")
                continue
            package = prop["Value"]["AssetPath"]["PackageName"]
            if package and package != "None":
                refs.add(package)

    # Only Engine/Transmission/LSD moved to soft refs -- vanilla still hard-imports
    # meshes under the other Cars/Parts folders, so don't flag those.
    soft_folders = ("/Game/Cars/Parts/Engine/", "/Game/Cars/Parts/Transmission/", "/Game/Cars/Parts/LSD/")
    stray = [i["ObjectName"] for i in data["Imports"]
             if str(i["ObjectName"]).startswith(soft_folders)]
    if stray:
        problems.append(f"{len(stray)} leftover hard part imports, e.g. {stray[:3]}")

    missing = []
    for package in sorted(refs):
        if not package.startswith("/Game/") or not content_roots:
            continue
        rel = package[len("/Game/"):].replace("/", os.sep) + ".uasset"
        if not any(os.path.isfile(os.path.join(root, rel)) for root in content_roots):
            missing.append(package)

    print(f"{os.path.basename(path)}: {len(rows)} rows, {len(refs)} distinct part assets, "
          f"{len(data['Imports'])} imports")
    for problem in problems:
        print("  FAIL", problem)
    for package in missing:
        print("  MISSING asset:", package)
    if problems or missing:
        sys.exit(1)
    print("  ok")


if __name__ == "__main__":
    main()
