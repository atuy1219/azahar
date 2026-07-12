# YW2 Runtime Trace 3GX

This project is built from PabloMK7's `CTRPluginFramework-BlankTemplate` and overlays a Yo-kai Watch 2 runtime tracer.

## Version 0.5.0

- keeps the 8192-record ring buffer used by v0.4.1
- samples `0x003376F0` at most once every 100 ms unless its key register signature changes
- reports total, saved, and skipped `0x003376F0` hits when saving
- adds manual phase markers for room creation, enemy selection, character selection, and preview visibility
- automatically adds a gameplay-start marker when **Stop and save at gameplay start** is selected
- adds grounded session and participant update hooks identified from the Ghidra analysis
- extends CSV rows with job/session fields and packet header data

## Added session targets

- `0x0032C9B0` CreateSessionJob
- `0x0034661C` session protocol queue pump
- `0x00343D94` packet dispatcher
- `0x00349B3C` ProcessJoinRequestJob
- `0x0034EF84` session update dispatcher
- `0x0034D4F8` normal session update parser
- `0x0034E9D4` alternate session update parser
- `0x0034D860` staged participant update apply
- `0x0034C328` session participant update loop
- `0x0034D058` participant count mirror

The parser-related rows include `job_4c`, `job_88`, `job_a0`, `job_a4`, `packet_ptr`, `packet_len`, `packet_header`, and `packet_seq`.

## Usage

1. Launch the game without starting the trace.
2. Load the save and wait until the Busters hub is fully usable.
3. Select **Start trace** immediately before creating the room.
4. After room creation, select **Mark: room created**.
5. After choosing the enemy, select **Mark: enemy selected**.
6. After choosing the character, select **Mark: character selected**.
7. When the character preview is visible, select **Mark: preview visible**.
8. Proceed to gameplay and immediately select **Stop and save at gameplay start**.
9. Copy `yw2_trace_XXXXXXXX.csv` from the plugin's 3GX directory.

Do not start the trace before the save has finished loading. A model-loader hook is not included yet because its exact address has not been verified; the manual preview marker provides a safe timing boundary without guessing an address.
