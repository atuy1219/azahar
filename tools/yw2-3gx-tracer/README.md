# YW2 Runtime Trace 3GX

This project is built from PabloMK7's `CTRPluginFramework-BlankTemplate` and overlays a Yo-kai Watch 2 runtime tracer.

## Version 0.4.1

- ring buffer set to 8192 records, double the original 4096 capacity
- fixes the CTRPF `BMP Error: Error while allocating required space` startup failure seen with 16384 records
- complete 38-column CSV rows are written in smaller formatting chunks
- save dialog reports stored, total, and dropped record counts
- all menu actions remain one-shot callbacks

The 8192-record buffer occupies about 1.16 MiB. At a 5 ms high-frequency hook rate it stores roughly 41 seconds before wrapping.

## Usage

1. Launch the game without starting the trace.
2. Load the save and wait until the Busters hub is fully usable.
3. Open the CTRPF menu and select **Start trace** immediately before creating the room.
4. Create the room, choose the enemy and character, and proceed to gameplay.
5. As soon as gameplay begins, select **Stop and save trace**.
6. Copy `yw2_trace_XXXXXXXX.csv` from the plugin's 3GX directory.

Do not start the trace before the save has finished loading. The target hooks are intended only for the analyzed game build and should be active for the shortest practical interval.

The CSV records selected control-flow addresses, r0-r12, stack pointer, callback LR, recovered game LR, eight stack words, thread ID, timestamp, and worker/active-field candidates derived from r0 and r4.
