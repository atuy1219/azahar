from pathlib import Path


# Apply after yw2_thread_lifecycle_trace_patch.py and
# yw2_guest_failure_trace_patch.py. This records the generic thread trampoline
# payload directly in SVC CreateThread/ExitThread, independent of Dynarmic PC
# sampling.
path = Path("src/core/hle/kernel/svc.cpp")
text = path.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 direct communication thread trace marker not found: {label}")
    text = text.replace(old, new, 1)


if "(YW2 COMM THREAD) CreateThread" not in text:
    patch_once(
        '''    if (entry_point == 0x0012E3E4 || entry_point == 0x0020528C ||
        entry_point == 0x0013F8C4 || entry_point == 0x005E7EEC) {
        LOG_WARNING(Kernel_SVC,
                    "(YW2 THREAD) CreateThread name={} entry=0x{:08X} arg=0x{:08X} "
                    "stack=0x{:08X} priority=0x{:08X} processor={} handle=0x{:08X} "
                    "caller_pc=0x{:08X} caller_lr=0x{:08X}",
                    name, entry_point, arg, stack_top, priority, processor_id, *out_handle,
                    system.GetRunningCore().GetPC(), system.GetRunningCore().GetReg(14));
    }
    return handle_result;
''',
        '''    if (entry_point == 0x0012E3E4 || entry_point == 0x0020528C ||
        entry_point == 0x0013F8C4 || entry_point == 0x005E7EEC) {
        LOG_WARNING(Kernel_SVC,
                    "(YW2 THREAD) CreateThread name={} entry=0x{:08X} arg=0x{:08X} "
                    "stack=0x{:08X} priority=0x{:08X} processor={} handle=0x{:08X} "
                    "caller_pc=0x{:08X} caller_lr=0x{:08X}",
                    name, entry_point, arg, stack_top, priority, processor_id, *out_handle,
                    system.GetRunningCore().GetPC(), system.GetRunningCore().GetReg(14));
    }
    if (entry_point == 0x0012E3E4) {
        const auto process = kernel.GetCurrentProcess();
        const auto read8 = [&](u32 address) -> u8 {
            if (!process || !memory.IsValidVirtualAddress(*process, address)) {
                return 0xFF;
            }
            return memory.Read8(address);
        };
        const auto read32 = [&](u32 address) -> u32 {
            if (!process || !memory.IsValidVirtualAddress(*process, address)) {
                return 0xFFFFFFFFU;
            }
            return memory.Read32(address);
        };
        const u32 function_at_4 = read32(arg + 0x04);
        const u32 function_at_8 = read32(arg + 0x08);
        const bool target_at_4 = function_at_4 == 0x00244EC8 || function_at_4 == 0x00294EC8;
        const bool target_at_8 = function_at_8 == 0x00244EC8 || function_at_8 == 0x00294EC8;
        if (target_at_4 || target_at_8) {
            const u32 callback_arg = target_at_4 ? read32(arg + 0x08) : read32(arg + 0x0C);
            LOG_WARNING(Kernel_SVC,
                        "(YW2 COMM THREAD) CreateThread wrapper_arg=0x{:08X} "
                        "function4=0x{:08X} function8=0x{:08X} callback_arg=0x{:08X} "
                        "arg0=0x{:08X} ok9={} fail10={} words="
                        "0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X}",
                        arg, function_at_4, function_at_8, callback_arg,
                        read32(callback_arg), read8(callback_arg + 9), read8(callback_arg + 10),
                        read32(arg + 0x00), read32(arg + 0x04), read32(arg + 0x08),
                        read32(arg + 0x0C), read32(arg + 0x10));
        }
    }
    return handle_result;
''',
        "CreateThread trampoline payload",
    )

    patch_once(
        '''        const u32 original_arg = current_thread->stack_top;
        const u32 guest_function = read32(original_arg + 0x08);
        if (guest_function == 0x00244EC8) {
''',
        '''        const auto read8 = [&](u32 address) -> u8 {
            if (!process || !memory.IsValidVirtualAddress(*process, address)) {
                return 0xFF;
            }
            return memory.Read8(address);
        };
        const u32 original_arg = current_thread->stack_top;
        const u32 function_at_4 = read32(original_arg + 0x04);
        const u32 function_at_8 = read32(original_arg + 0x08);
        const bool target_at_4 = function_at_4 == 0x00244EC8 || function_at_4 == 0x00294EC8;
        const bool target_at_8 = function_at_8 == 0x00244EC8 || function_at_8 == 0x00294EC8;
        const u32 guest_function = target_at_4 ? function_at_4 : function_at_8;
        const u32 callback_arg = target_at_4 ? read32(original_arg + 0x08)
                                             : read32(original_arg + 0x0C);
        if (target_at_4 || target_at_8) {
            LOG_WARNING(Kernel_SVC,
                        "(YW2 COMM THREAD) ExitThread wrapper_base=0x{:08X} "
                        "function4=0x{:08X} function8=0x{:08X} callback_arg=0x{:08X} "
                        "arg0=0x{:08X} ok9={} fail10={} r0=0x{:08X} r4=0x{:08X} "
                        "pc=0x{:08X} lr=0x{:08X}",
                        original_arg, function_at_4, function_at_8, callback_arg,
                        read32(callback_arg), read8(callback_arg + 9), read8(callback_arg + 10),
                        system.GetRunningCore().GetReg(0), system.GetRunningCore().GetReg(4), pc, lr);
''',
        "ExitThread trampoline payload",
    )

    path.write_text(text)
    print("Applied direct YW2 communication thread lifecycle trace patch")
else:
    print("Skipped direct YW2 communication thread lifecycle trace patch: already present")
