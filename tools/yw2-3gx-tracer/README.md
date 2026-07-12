# YW2 Safe Probe 3GX

This project is built from PabloMK7's `CTRPluginFramework-BlankTemplate`.

Version 0.3.0 is intentionally non-invasive. It installs no hooks and performs no writes to game code or game memory. It only reads the current Title ID, process text range, and instruction words around the candidate addresses used by the previous tracer.

## Recovery from the previous build

If the game hangs while loading a save, remove or rename the old `default.3gx` from the title's Luma3DS plugin directory and relaunch the game. Runtime hooks do not persist after the process exits.

## Usage

1. Replace the old plugin with `YW2RuntimeTrace.3gx` from this build.
2. Launch the game and confirm that the save loads normally.
3. Open the CTRPF menu.
4. Select **Safety status**. It should show `Hooks: disabled` and `Writes to game code: none`.
5. Select **Dump target map (safe)** once.
6. Copy `yw2_target_probe_XXXXXXXX.csv` from the plugin's 3GX directory.

The CSV contains:

- current Title ID
- process text start and end
- five ARM instruction words around every candidate address

This probe is used to determine whether the addresses from the analyzed CIA match the executable running on the real console before code hooks are reintroduced.
