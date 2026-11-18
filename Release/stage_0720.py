"""stage_0720.py -- every download of the 0.7.20 release, one folder each, ready to zip.

    python Release/stage_0720.py            build Documents\\MoreTuning 0720 (rerunnable: it starts clean)
    python Release/stage_0720.py demo       self-check of the layout table, no copying

The user, 2026-11-18: "place them each plugin, each mod, each everything. So I know exactly which
download should I have". So every download is its own folder, laid out to drop onto the game folder
(Steam > Manage > Browse local files): a mod brings MotorTown\\Content\\Paks\\<pak>, a plugin brings
MotorTown\\Binaries\\Win64\\version.dll (the loader) and plugins\\mt_plugin_<Name>.dll. Each folder has a
README.txt: what it is, what it needs, what it works with.

The split the user asked for: a vehicle is bought in the game from its MOD (the boats, the ships and
the helicopter come with Boater Town), and what makes it move is a PLUGIN, a separate download -- the
Sea plugin for anything on the water, the Helicopter plugin for the aircraft. A plugin that has its own
sounds or meshes ships that pak inside its own download (ECU Tuning, Suspension Tuning, Capitalist).

Sources: the paks as installed in the game (what has been tested), the plugins from the loader's
build output (mt_loader\\out, the same files tools\\deploy.py installs).
"""
import os
import shutil
import sys

GAME = r"D:\SteamLibrary\steamapps\common\Motor Town\MotorTown"
PAKS = os.path.join(GAME, "Content", "Paks")
LOADER_OUT = r"D:\MTLiveMap\mt_loader\out"
MTNET_TEMPLATES = r"D:\MTLiveMap\mt_loader\plugins\mt_net_templates"
DEST = os.path.join(os.path.expanduser("~"), "Documents", "MoreTuning 0720")

WIN64 = os.path.join("MotorTown", "Binaries", "Win64")
PAKDIR = os.path.join("MotorTown", "Content", "Paks")

REQ = ("1 Required", )
# (group folder, download name, paks, plugin dll or None, one-line what, needs, works with)
DOWNLOADS = [
    # ---- what everything else stands on ----
    ("1 Required", "Plugin Loader", [], "LOADER",
     "The loader every plugin runs on (version.dll). On its own it does nothing visible.",
     "Nothing.", "Every download in 3 Plugins needs it: install it once, then add the plugins you want."),
    ("1 Required", "DataTable Framework", ["AAAA_DataTableFramework_99_P.pak"], None,
     "Lets several mods add parts, vehicles and cargo side by side instead of overwriting each other.",
     "Nothing.", "Every mod in 2 Mods that adds parts, vehicles or cargo needs it."),

    # ---- mods: paks, bought and used in the game ----
    ("2 Mods", "MoreTuning", ["qxZap_MoreTuning_P.pak"], None,
     "The parts pack: engines, transmissions, turbos, brakes, Motor Works' parts and the cabin sound mix.",
     "DataTable Framework.", "ECU Tuning plugin reads its supercharger and turbo parts (optional)."),
    ("2 Mods", "MoreTuning - No Limits", ["qxZap_MoreTuning_xNoLimits_P.pak"], None,
     "Any bumper, body part or headlight on any vehicle (they will not always sit right).",
     "DataTable Framework, MoreTuning.", ""),
    ("2 Mods", "MoreTuning - Carbon", ["qxZap_MoreTuning_yCarbon_P.pak"], None,
     "Carbon twins of the body parts: half the mass, fit any vehicle.",
     "DataTable Framework, MoreTuning.", ""),
    ("2 Mods", "MoreAttachments", ["qxZap_satigt3_MoreAttachments_P.pak"], None,
     "Hundreds of car parts as attachments, with paint and working lamps.",
     "DataTable Framework.", "Attachment Tweaks plugin: per-section lamp control (optional)."),
    ("2 Mods", "MoreAttachments - Premium", ["qxZap_satigt3_MoreAttachments_Premium_P.pak"], None,
     "The premium set of MoreAttachments.",
     "DataTable Framework, MoreAttachments.", ""),
    ("2 Mods", "Suspension Expansion", ["Z_SuspensionExpansion_P.pak"], None,
     "57 suspension parts.",
     "DataTable Framework.", ""),
    ("2 Mods", "Tehs Engine Sound Pack", ["Z_TehsEngineSoundPack_P.pak"], None,
     "Teh's 16 engines with their own sounds.",
     "DataTable Framework.", ""),
    ("2 Mods", "Arini Map", ["qxZap_Arini_P.pak"], None,
     "The Arini island: roads, towns, delivery points, the harbours and their sea lanes.",
     "DataTable Framework.",
     "Boater Town (the boats that use the harbours). New name: enable it once in Mods [Review]."),
    ("2 Mods", "Arini Vehicles", ["Biceps_P.pak"], None,
     "Arini's vehicles.",
     "DataTable Framework.", "Arini Map."),
    ("2 Mods", "Crisp Sky", ["CrispSky_P.pak"], None,
     "A clearer, crisper sky.",
     "Nothing.", ""),
    ("2 Mods", "Boater Town", ["BoaterTown_P.pak"], None,
     "The boats, the ships and the helicopter, with their dealers and the harbour delivery points. "
     "They are bought here -- to drive them you need a plugin (see below).",
     "DataTable Framework, Arini Map.",
     "Sea plugin: drives and floats the boats and ships (without it they sit on land). "
     "Helicopter plugin: makes the helicopter fly. Boater Town plugin: harbour capacity."),

    # ---- plugins: one dll each (plus the loader), and its own pak if it has one ----
    ("3 Plugins", "Sea (boats and swimming)", [], "mt_plugin_Sea.dll",
     "Drives and floats every boat and ship on the game's own waves, and lets you swim.",
     "Plugin Loader.", "Boater Town mod: the boats themselves."),
    ("3 Plugins", "Helicopter", [], "mt_plugin_Helicopter.dll",
     "Makes the helicopter fly: W is the collective, steering yaws.",
     "Plugin Loader, Boater Town mod (the aircraft).", ""),
    ("3 Plugins", "Boater Town (plugin)", [], "mt_plugin_BoaterTown.dll",
     "Gives the harbour delivery points their capacity and cargo list.",
     "Plugin Loader, Boater Town mod, Arini Map.", ""),
    ("3 Plugins", "ECU Tuning", ["qxZap_ECUTuning_P.pak"], "mt_plugin_ECUTuning.dll",
     "Per-vehicle engine tuning in the garage: timing, fuel, boost, anti-lag; pops, bangs and flames. "
     "The pak is the turbo flutter and supercharger whine.",
     "Plugin Loader.", "MoreTuning (supercharger/turbo parts), Tehs Engine Sound Pack."),
    ("3 Plugins", "Suspension Tuning", ["qxZap_SuspensionVisuals_P.pak"], "mt_plugin_SuspensionTuning.dll",
     "Brakes & Suspension page: big brake kits, calipers and discs you can see and paint, per-axle "
     "suspension geometry. Off per car until you switch it on in the garage.",
     "Plugin Loader.", ""),
    ("3 Plugins", "Capitalist Economy", ["qxZap_CapitalistEconomy_P.pak"], "mt_plugin_CapitalistEconomy.dll",
     "Cargo pays by straight-line distance, real weight and size, and fragility.",
     "Plugin Loader.",
     "On a dedicated server it must be installed on the server too: the server pays."),
    ("3 Plugins", "Wheel Size Unlimited", [], "mt_plugin_WheelSizeUnlimited.dll",
     "Wheel radius and width tuning, and any wheel on any vehicle.",
     "Plugin Loader.", ""),
    ("3 Plugins", "Attachment Tweaks", [], "mt_plugin_AttachmentTweaks.dll",
     "Tools for any attachment: per-section lamp control, the placement clipboard.",
     "Plugin Loader.", "MoreAttachments."),
    ("3 Plugins", "Custom Plates", [], "mt_plugin_CustomPlates.dll",
     "License plates you design in the garage.",
     "Plugin Loader.", ""),
    ("3 Plugins", "Rear Cam", [], "mt_plugin_RearCam.dll",
     "A backup camera on the dashboard screen while reversing.",
     "Plugin Loader.", ""),
    ("3 Plugins", "Search Box", [], "mt_plugin_SearchBox.dll",
     "A search field on the garage part list, the decal picker and the vendor list.",
     "Plugin Loader.", ""),
    ("3 Plugins", "Smoke Factory", [], "mt_plugin_SmokeFactory.dll",
     "Longer-lasting, bigger, rising tyre smoke.",
     "Plugin Loader.", ""),
    ("3 Plugins", "Company Size Unlimited", [], "mt_plugin_CompanySizeUnlimited.dll",
     "More company vehicles.",
     "Plugin Loader.", ""),
    ("3 Plugins", "Vehicle Parker", [], "mt_plugin_VehicleParker.dll",
     "Ctrl+F10: every vehicle you own goes back to your list (campers stay).",
     "Plugin Loader.", ""),
    ("3 Plugins", "Quiet Popups", [], "mt_plugin_QuietPopups.dll",
     "Closes the 'Invalid vehicle type' pop-ups a save with missing mod vehicles opens.",
     "Plugin Loader.", ""),
    ("3 Plugins", "Time Keys", [], "mt_plugin_TimeKeys.dll",
     "Page Up sets the clock to noon, Page Down to midnight.",
     "Plugin Loader.", ""),
    ("3 Plugins", "Performance", [], "mt_plugin_Performance.dll",
     "A frame-rate governor: eases the heaviest work when the frame rate stays low.",
     "Plugin Loader.", ""),
    ("3 Plugins", "MTNet", [], "mt_plugin_MTNet.dll",
     "The in-game panel (Ctrl+F9) for server and console settings.",
     "Plugin Loader.", "Keep it off on a dedicated server."),
    ("3 Plugins", "Motortown Connect", [], "mt_plugin_MotortownConnect.dll",
     "The network side: direct IP connections.",
     "Plugin Loader.", ""),

    # ---- not for release: dev tools and held-back work, kept apart so they are not shipped by mistake ----
    ("4 Not for release", "Coordinates (dev)", [], "mt_plugin_Coordinates.dll",
     "Ctrl+F11 saves spots, #tp teleports. A tool for building the map.",
     "Plugin Loader.", ""),
    ("4 Not for release", "POI Teleport (dev)", [], "mt_plugin_POITeleport.dll",
     "#poi <name> goes to a saved point of interest. Reads plugins\\pois.txt.",
     "Plugin Loader.", ""),
    ("4 Not for release", "Swim animations (held back)", ["qxZap_Swim_P.pak"], None,
     "The swim montages. Held back: the game crashed when the swim played them; the Sea plugin ships "
     "with the animation off.",
     "Sea plugin.", ""),
]

NOT_OURS = [
    ("MajasDecalPackV4.4_P.pak", "Maja's Decal Pack"),
    ("MajasDetailWorksV4-7.20_P.pak", "Maja's Detail Works"),
    ("MajasMoWheelWorksV6-7.20_P.pak", "Maja's Mo Wheel Works"),
    ("Slides_Attachments_P.pak", "Slides Attachments"),
    ("VehicleLabs_1_P.pak", "VehicleLabs"),
    ("Wormhole720_P.pak", "Wormhole (check whether it is ours)"),
]

INSTALL = """HOW TO INSTALL
1. In Steam, right-click Motor Town > Manage > Browse local files.
2. Drag the MotorTown folder from this download into that window and let it merge.
"""


def readme(name, what, needs, works, files):
    lines = [name, "=" * len(name), "", what, "", "NEEDS: " + needs]
    if works:
        lines += ["WORKS WITH: " + works]
    lines += ["", "FILES:"] + ["  " + f for f in files] + ["", INSTALL]
    return "\n".join(lines)


def plan():
    """Each download: (folder, [(source, relative destination)], readme text)."""
    out = []
    for group, name, paks, dll, what, needs, works in DOWNLOADS:
        folder = os.path.join(group, name)
        files = []
        for p in paks:
            files.append((os.path.join(PAKS, p), os.path.join(PAKDIR, p)))
        if dll == "LOADER":
            files.append((os.path.join(LOADER_OUT, "version.dll"), os.path.join(WIN64, "version.dll")))
        elif dll:   # the plugin alone: the loader is its own download, which every plugin needs
            files.append((os.path.join(LOADER_OUT, "plugins", dll), os.path.join(WIN64, "plugins", dll)))
        if dll == "mt_plugin_MTNet.dll" and os.path.isdir(MTNET_TEMPLATES):
            for f in sorted(os.listdir(MTNET_TEMPLATES)):
                if f.endswith(".json"):
                    files.append((os.path.join(MTNET_TEMPLATES, f), os.path.join(WIN64, "mt_net_templates", f)))
        out.append((folder, files, readme(name, what, needs, works, [d for _, d in files])))
    return out


def index_text(downloads):
    lines = ["MoreTuning -- the 0.7.20 release", "================================", "",
             "Every folder is one download, laid out to drop onto the game folder.",
             "1 Required          what everything else stands on",
             "2 Mods              paks: parts, vehicles, the map -- bought and used in the game",
             "3 Plugins           what makes things work: each one needs the Plugin Loader (1 Required)",
             "4 Not for release   dev tools and held-back work, kept apart on purpose",
             "",
             "A vehicle is bought from its MOD; a PLUGIN makes it move. The boats, ships and helicopter",
             "come with the Boater Town mod; the Sea plugin drives the boats, the Helicopter plugin flies it.",
             ""]
    group = None
    for folder, files, _ in downloads:
        g, n = folder.split(os.sep, 1)
        if g != group:
            group = g
            lines += ["", g, "-" * len(g)]
        size = sum(os.path.getsize(s) for s, _ in files if os.path.exists(s))
        lines.append(f"  {n:34} {size / 1048576:9.1f} MB")
    lines += ["", "NOT OURS -- installed here, but not part of this release (players get them from their authors):"]
    lines += [f"  {label}  ({pak})" for pak, label in NOT_OURS]
    return "\n".join(lines) + "\n"


def build():
    downloads = plan()
    missing = [s for _, files, _ in downloads for s, _ in files if not os.path.exists(s)]
    if missing:
        sys.exit("FAIL: missing sources:\n  " + "\n  ".join(missing))
    if os.path.isdir(DEST):
        shutil.rmtree(DEST)
    for folder, files, text in downloads:
        root = os.path.join(DEST, folder)
        for src, rel in files:
            dst = os.path.join(root, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        with open(os.path.join(root, "README.txt"), "w", encoding="utf-8", newline="\r\n") as f:
            f.write(text)
        print(f"  {folder}: {len(files)} file(s)")
    with open(os.path.join(DEST, "README.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(index_text(downloads))
    print(f"{len(downloads)} downloads in {DEST}")


def demo():
    names = [d[1] for d in DOWNLOADS]
    assert len(names) == len(set(names)), "a download name is used twice"
    paks = [p for d in DOWNLOADS for p in d[2]]
    assert len(paks) == len(set(paks)), "a pak is in two downloads"
    dlls = [d[3] for d in DOWNLOADS if d[3] and d[3] != "LOADER"]
    assert len(dlls) == len(set(dlls)), "a plugin is in two downloads"
    assert not set(paks) & {p for p, _ in NOT_OURS}, "someone else's pak is in a download"
    for folder, files, _ in plan():
        if not folder.endswith("Plugin Loader"):
            assert not any(r.endswith("version.dll") for _, r in files), folder + " carries the loader"
        assert files, folder + " is empty"
        assert all(r.startswith("MotorTown" + os.sep) for _, r in files), folder + " is not a drop-in MotorTown tree"
    print("demo ok")


if __name__ == "__main__":
    demo() if sys.argv[1:] == ["demo"] else build()
