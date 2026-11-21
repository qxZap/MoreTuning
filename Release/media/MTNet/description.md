# MTNet

## Short description

Change the game's own settings from an in-game panel: economy, winch, cargo stacking and more, with ready-made templates. It can also cut the game's background reporting traffic for a smoother frame rate.

## Long description

MTNet is now a plugin. The old version was a separate program you ran next to the game; this one starts with the game, and there's nothing else to run.

### Disclaimer

MTNet changes the game the same way any mod does, just from a panel instead of a pak. Use it responsibly and don't spoil the game for other players.

### What you get

- A control panel: press Ctrl+F9 in game to open it in your browser.
- Console variables: see the settings the game is running with, change them, or add any of the game's 2,500+ variables from a searchable list.
- Templates, ready-made sets of settings that apply in one click:
  - Economy x2, x4, x5, x10, x20 and x100: bus, cargo, limo, taxi, tow and police patrol pay, autopilot XP, drift XP and race rewards.
  - Turbo Winch: faster, stronger winches.
  - Johnny Silverhand: much stronger pushing on foot.
  - Cargo Stack Unlimited: stack cargo higher and heavier, and get paid for the full weight.
- Your own templates: a template is a small JSON file in MotorTown\Binaries\Win64\mt_net_templates. Copy one, change the values, and it shows up in the panel. Sharing a template with a friend means sending them that file.
- Fewer background requests: by default MTNet answers the game's reporting calls (events, logs, playtime, vehicle and character uploads) itself, so they never go out to the server. You can switch each one on or off live on the panel's Network page, which also lists every request the game makes and how long the server takes to answer.
- Traffic dump: set Dump=1 under [MTNet] in mt_net.ini and every exchange with the game's servers is saved whole to plugins\logs\MTNet\traffic. Those files hold your login headers, so never share them as they are.
- Reset: one button puts every setting back to the game's defaults.

### What you need

- Plugin Loader (its own download).

### Install

1. In Steam, right-click Motor Town > Manage > Browse local files.
2. Drag the MotorTown folder from this download into that window and let it merge.

Settings are in MotorTown\Binaries\Win64\plugins\mt_net.ini, created on first launch. Disabled=1 under [General] turns the plugin off.

Upgrading from the old MTNet: remove the old program and its pak. The plugin replaces both.

### Multiplayer

Settings take effect in single player and on a server you host. Leave MTNet off on a dedicated server (Disabled=1).
