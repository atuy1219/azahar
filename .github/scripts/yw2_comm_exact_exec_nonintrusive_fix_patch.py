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


# Do not instrument every instruction in FUN_00244EC8. Supervisor callbacks at hot
# polling/control-flow points such as 0x00244F18 and 0x00244F34 can repeatedly resume at
# the same guest PC and prevent the helper thread from making progress. Keep only the
# checkpoints that were observed to complete without stalling.
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
    default:
        break;
    }
''',
    "safe FUN_00244EC8 checkpoints",
)


# 0x0012E420 is the call-site control-flow instruction before FUN_002BEC3C. Injecting a
# supervisor callback there can perturb the call itself. Record only the callee entry and
# the return site at 0x0012E424.
patch_once(
    '''    case 0x0012E420:
        return YW2_COMM_EXEC_SPECIAL | 0x04;
    case 0x002BEC3C:
        return YW2_COMM_EXEC_SPECIAL | 0x05;
''',
    '''    case 0x002BEC3C:
        return YW2_COMM_EXEC_SPECIAL | 0x05;
''',
    "remove pre-2BEC3C control-flow checkpoint",
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
print("Applied reduced YW2 exact execution trace checkpoints and pointer guards")
