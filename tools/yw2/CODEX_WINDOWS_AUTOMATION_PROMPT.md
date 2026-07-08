# Codex prompt: YW2 Windows automation loop

You are working on `atuy1219/azahar`, branch `test/yw2-blasters-stub`.

Goal: debug Yo-kai Watch 2 / Busters local-wireless room launch failure in Azahar.

## Current confirmed behavior

- Room creation reaches `BeginHostingNetwork` and `GetChannel` successfully.
- The game keeps sending beacon packets.
- `PullPacket`, `SendTo`, `RecvBeaconBroadcastData`, and `HandleSecureData` are not called before the failure.
- The user presses the final "proceed/next" button.
- About 3 seconds after the button press, the game calls `DestroyNetwork` from guest LR `0x00364D54`.
- This is not a room-creation timeout. It is a post-button / loading-phase failure.
- Do not use intrusive Dynarmic `jit->Step()` runtime tracing. It caused `server_session.cpp:100` assertion / SIGTRAP.

## Current known Ghidra anchors

Use raw LR directly in Ghidra for these NWM IPC caller traces. Do not subtract `0x50000`.

```text
GetChannel       lr=0x003645DC
BeginHosting     lr=0x00364A50
SetProbeResponse lr=0x00364A30
DestroyNetwork   lr=0x00364D54
GetConnStatus    lr=0x003651B0
Bind             lr=0x003658D0
Unbind           lr=0x00365E64
Shutdown         lr=0x00365AB4
```

Important functions:

```text
FUN_0033b8bc  room create path
FUN_0033727c  BeginHostingNetwork -> GetChannel path
FUN_00339994  worker active/busy gate, checks worker+0x3eec
FUN_00339d8c  worker start, sets worker+0x3eec = 1
FUN_00339c90  worker stop, clears worker+0x3eec = 0
FUN_0033c0a0  packet-loop worker
FUN_00364d20  DestroyNetwork wrapper
FUN_0033807c  GetConnectionStatus-driven update path
```

## Desktop trace configuration

On Windows/Linux builds, use environment variables rather than Android system properties:

```powershell
$env:AZAHAR_YW2_NWM_IPC_TRACE="1"
$env:AZAHAR_YW2_TRACE_LEVEL="all"
$env:AZAHAR_YW2_SELF_LOOPBACK="1"
$env:AZAHAR_YW2_BIND_PULSE="0"
$env:AZAHAR_YW2_STATUS_QUIET_HOST="0"
$env:AZAHAR_YW2_DUMMY_NODE="0"
$env:AZAHAR_YW2_DUMMY_PACKET="0"
$env:AZAHAR_YW2_STATUS_PULSE="0"
$env:AZAHAR_YW2_SVC_WAIT_TRACE="0"
```

For SVC wait probing, enable only for a focused run:

```powershell
$env:AZAHAR_YW2_SVC_WAIT_TRACE="1"
```

## Windows helper

Use:

```powershell
py -m pip install pyautogui pillow
py tools/yw2/windows_next_button_runner.py --next-x <x> --next-y <y> --azahar-log <path-to-azahar-log>
```

The helper:

- writes `BEFORE_PRESS_NEXT`, `AFTER_PRESS_NEXT`, and `AFTER_WAIT_WINDOW` markers
- clicks the configured coordinate
- captures screenshots before/after
- tails a specified Azahar log and keeps only relevant YW2/NWM/SVC lines

If the helper cannot find Azahar's log path, run Azahar manually and point `--azahar-log` at the actual log file. Do not guess; ask the user or search the filesystem.

## Codex loop

For each iteration:

1. Pull the latest branch.
2. Check whether the patch scripts apply cleanly.
3. Build only what is needed.
4. Run or inspect the latest focused log under `logs/yw2_windows/` or the user-provided log.
5. Compare the interval from `BEFORE_PRESS_NEXT` / `AFTER_PRESS_NEXT` to `DestroyNetwork`.
6. Identify the smallest safe additional trace or static patch.
7. Avoid runtime `jit->Step()` tracing.
8. Prefer HLE IPC trace, SVC wait trace, static Ghidra-guided analysis, or non-invasive logging.
9. Commit and push one small change.
10. Summarize:
    - changed files
    - exact hypothesis tested
    - exact command/env to run next
    - what result would confirm or reject the hypothesis

## High-priority next checks

- Confirm desktop `AZAHAR_YW2_*` env vars actually enable NWM IPC and SVC wait logs.
- If Windows build reproduces the Android behavior, treat it as core/HLE issue rather than Android lifecycle issue.
- If Windows build does not reproduce, compare Android-only timing, event, and thread behavior.
- The failure is post-button and pre-NWM-packet-API. Focus on waits/events/tasks between button press and `DestroyNetwork`, not on `PullPacket` internals first.
