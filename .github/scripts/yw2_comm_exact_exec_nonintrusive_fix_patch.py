from pathlib import Path


path = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
text = path.read_text()

if "YW2CommExecPointerDump" in text:
    print("Skipped non-intrusive YW2 exact execution trace fix: already present")
    raise SystemExit(0)


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 exact execution non-intrusive fix marker not found: {label}")
    text = text.replace(old, new, 1)


# Do not instrument every instruction in FUN_00244EC8. In particular, 0x00244F18 is a
# hot polling/back-edge point; injecting CallSupervisor there changes scheduling and can
# prevent the helper thread from making progress. Keep only sparse execution checkpoints.
patch_once(
    '''    if (normalized >= 0x00244EC8 && normalized <= 0x00244F4C) {
        return YW2_COMM_EXEC_MAIN | (normalized - 0x00244EC8);
    }
    if (normalized >= 0x00294EC8 && normalized <= 0x00294F4C) {
        return YW2_COMM_EXEC_ALIAS | (normalized - 0x00294EC8);
    }
''',
    '''    switch (normalized) {
    case 0x00244EC8:
        return YW2_COMM_EXEC_MAIN | 0x0000;
    case 0x00244F10:
        return YW2_COMM_EXEC_MAIN | 0x0048;
    case 0x00244F14:
        return YW2_COMM_EXEC_MAIN | 0x004C;
    case 0x00244F1C:
        return YW2_COMM_EXEC_MAIN | 0x0054;
    case 0x00244F24:
        return YW2_COMM_EXEC_MAIN | 0x005C;
    case 0x00244F2C:
        return YW2_COMM_EXEC_MAIN | 0x0064;
    case 0x00244F34:
        return YW2_COMM_EXEC_MAIN | 0x006C;
    case 0x00244F3C:
        return YW2_COMM_EXEC_MAIN | 0x0074;
    case 0x00244F44:
        return YW2_COMM_EXEC_MAIN | 0x007C;
    case 0x00244F48:
        return YW2_COMM_EXEC_MAIN | 0x0080;
    case 0x00244F4C:
        return YW2_COMM_EXEC_MAIN | 0x0084;
    case 0x00294EC8:
        return YW2_COMM_EXEC_ALIAS | 0x0000;
    case 0x00294F10:
        return YW2_COMM_EXEC_ALIAS | 0x0048;
    case 0x00294F14:
        return YW2_COMM_EXEC_ALIAS | 0x004C;
    case 0x00294F1C:
        return YW2_COMM_EXEC_ALIAS | 0x0054;
    case 0x00294F24:
        return YW2_COMM_EXEC_ALIAS | 0x005C;
    case 0x00294F2C:
        return YW2_COMM_EXEC_ALIAS | 0x0064;
    case 0x00294F34:
        return YW2_COMM_EXEC_ALIAS | 0x006C;
    case 0x00294F3C:
        return YW2_COMM_EXEC_ALIAS | 0x0074;
    case 0x00294F44:
        return YW2_COMM_EXEC_ALIAS | 0x007C;
    case 0x00294F48:
        return YW2_COMM_EXEC_ALIAS | 0x0080;
    case 0x00294F4C:
        return YW2_COMM_EXEC_ALIAS | 0x0084;
    default:
        break;
    }
''',
    "sparse FUN_00244EC8 checkpoints",
)


# Avoid treating small integer results such as r0=0 or r1=3 as guest pointers. Limit
# optional dumps to the normal user-memory range used by this process/thread.
patch_once(
    '''void YW2LogCommExec(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u32 swi) {
''',
    '''std::string YW2CommExecPointerDump(Memory::MemorySystem& memory, u32 address,
                                      u32 length) {
    if (address < 0x08000000 || address >= 0x20000000) {
        return "not_guest_pointer";
    }
    return YW2HexDump(memory, address, length);
}

void YW2LogCommExec(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u32 swi) {
''',
    "safe guest pointer dump helper",
)

patch_once(
    '''                    YW2HexDump(memory, r0, 32), YW2HexDump(memory, r1, 32),
                    callback_arg != 0 ? YW2HexDump(memory, callback_arg - 0x10, 48)
                                      : std::string("none"),
                    YW2HexDump(memory, sp, 48));
''',
    '''                    YW2CommExecPointerDump(memory, r0, 32),
                    YW2CommExecPointerDump(memory, r1, 32),
                    callback_arg != 0
                        ? YW2CommExecPointerDump(memory, callback_arg - 0x10, 48)
                        : std::string("none"),
                    YW2CommExecPointerDump(memory, sp, 48));
''',
    "guarded special-call memory dumps",
)

path.write_text(text)
print("Applied non-intrusive YW2 exact execution trace checkpoints and pointer guards")
