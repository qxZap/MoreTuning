# Plugin Loader

## Short description

The loader every Motor Town plugin runs on. Install it once, then drop any plugin into the plugins folder beside it: plugins load in alphabetical order and never overwrite each other's settings.

## Long description

Motor Town has no built-in support for code mods. The Plugin Loader adds it: a single version.dll that the game loads on its own at startup, and that then loads every plugin you put in the plugins folder next to it. On its own it changes nothing you can see. It is what lets the plugins run.

### What you get

- One install for every plugin. Each plugin is a single file, plugins\mt_plugin_<Name>.dll, and the loader picks it up the next time you start the game.
- Plugins load in alphabetical order, the same order every time. Anything else in the plugins folder is ignored.
- One shared hook into the game, owned by the loader. Plugins go through it instead of each patching the game on their own, which is what lets several plugins run side by side without breaking each other.
- Settings that stay yours. Each plugin keeps its settings in plugins\<plugin>.ini, created on first launch. When two plugins share a settings file, each one only ever writes its own keys, and a value you typed by hand always wins over a plugin's default.

### Install

1. In Steam, right-click Motor Town > Manage > Browse local files.
2. Drag the MotorTown folder from this download into that window and let it merge.
3. Add the plugins you want the same way.

To remove it, delete MotorTown\Binaries\Win64\version.dll. To turn off one plugin, set Disabled=1 under [General] in its .ini file, or delete its .dll.

### Settings

The loader's own settings are in MotorTown\Binaries\Win64\mt_loader.ini, created on first launch.

- Logging=1 under [General] writes a log for the loader and every plugin, under plugins\logs. Logging is off by default, and then no log files are created.
- UnlockCheat under [CVars] is on by default. It lets the game take console variables that are normally locked to developers from your own ini files, which is what server and economy settings use. Set it to 0 to leave them locked.

### Linux and Steam Deck

Proton uses its own version.dll unless told otherwise. Add this to the game's Steam launch options:

WINEDLLOVERRIDES="version=n,b" %command%

### Antivirus warnings

Some scanners flag version.dll. It sits in the game folder under a Windows file's name and changes the running game, which is what a loader has to do and what a scanner is wary of. The loader makes no network connections, downloads nothing and runs no programs, and its full source is public. If yours flags it, exclude only the game's Binaries\Win64 folder. Do not turn your antivirus off.

### For mod makers

A plugin is a .dll that exports one function, PluginInit. It gets a versioned set of functions for reading the game, calling into it on the game thread, watching game functions, and reading and writing settings, documented in include\mt_plugin_api.h in the repository. After a game update, Export=1 under [Mappings] in mt_loader.ini writes a fresh mappings file the next time you load a save.
