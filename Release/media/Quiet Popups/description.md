# Quiet Popups

## Short description

No more clicking away "Invalid vehicle type" pop-ups when a save holds vehicles from a mod you removed.

## Long description

A save with vehicles from a mod that is no longer installed, or not updated yet, opens one "Invalid vehicle type" pop-up per vehicle every time it loads. With a big fleet that is dozens of clicks. Quiet Popups closes them for you. Every other message is shown as before.

### What you get

- The "Invalid vehicle type" and "This vehicle type is not supported" pop-ups close by themselves.
- Other pop-ups are left alone.
- Your own phrases: add the text of any other pop-up you don't want to see.

### What you need

- Plugin Loader (its own download).

### Install

1. In Steam, right-click Motor Town > Manage > Browse local files.
2. Drag the MotorTown folder from this download into that window and let it merge.

Settings are in MotorTown\Binaries\Win64\plugins\quiet_popups.ini, created on first launch. To set your own phrases, add a [QuietPopups] section with a Words line: it lists the phrases that close a pop-up, separated by |, any case (default: invalid vehicle|vehicle type is not supported). Disabled=1 under [General] turns the plugin off.

### Good to know

The vehicles themselves are still missing: the plugin only stops the pop-ups. Reinstall the mod they came from to get them back.
