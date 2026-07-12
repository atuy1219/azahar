# YW2 Runtime Trace 3GX

This project is built from PabloMK7's `CTRPluginFramework-BlankTemplate` and overlays a Yo-kai Watch 2 runtime tracer.

## Version 0.5.1

- keeps the 8192-record ring buffer
- samples `0x003376F0` at most once every 100 ms unless its key register signature changes
- retains the room-created and enemy-selected manual markers
- removes the separate character-selected and preview-visible manual markers
- automatically records `MARK_character_preview_auto` when the session protocol `r9` pointer leaves its post-room baseline after the enemy marker and then returns to that baseline
- automatically adds a gameplay-start marker when **Stop and save at gameplay start** is selected
- reports the automatic marker count and detected baseline `r9` pointer in the save dialog

Character selection and preview display are treated as one event. The automatic marker is inserted from the game-side protocol hook, so opening the CTRPF menu no longer pauses the game at that phase.

## Usage

1. Launch the game without starting the trace.
2. Load the save and wait until the Busters hub is fully usable.
3. Select **Start trace** immediately before creating the room.
4. After room creation, select **Mark: room created**.
5. After choosing the enemy, select **Mark: enemy selected**.
6. Choose the character normally. Do not open the plugin menu; the combined character-selection/preview event is detected automatically.
7. Proceed to gameplay and immediately select **Stop and save at gameplay start**.
8. Copy `yw2_trace_XXXXXXXX.csv` from the plugin's 3GX directory.

The observed normal-flow signature was a non-zero `r9` transition from the post-room baseline to a selection-context pointer and back. This detector is empirical and the resulting CSV should still be checked for `MARK_character_preview_auto`.
