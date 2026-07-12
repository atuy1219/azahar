# YW2 Runtime Trace 3GX

This project is built from PabloMK7's `CTRPluginFramework-BlankTemplate` and overlays a Yo-kai Watch 2 runtime tracer.

## Usage

1. Place the resulting `YW2RuntimeTrace.3gx` in the Luma3DS plugin directory for the target title.
2. Launch the game and open the CTRPF menu.
3. Select **Start trace** immediately before creating a local wireless room.
4. Reproduce the communication error once.
5. Select **Stop and save trace**.
6. Copy `yw2_trace_XXXXXXXX.csv` from the plugin's 3GX directory.

The tracer records selected control-flow addresses, r0-r12, stack pointer, callback LR, eight stack words, thread ID, timestamp, and worker/active-field candidates derived from r0 and r4.

## Targets

- `0x00337680`, `0x003376C0`, `0x003376F0`, `0x00337744`
- `0x0033807C`, `0x0033809C`, `0x003380B0`, `0x003380D0`
- `0x0033BD24`, `0x0033BD54`, `0x0033BD94`
- `0x00364D20`
- Previous worker-path candidates around `0x00339994` and `0x0033B8BC`

Use **Hook status** after starting the tracer. PC-relative instructions are intentionally rejected rather than patched unsafely.
