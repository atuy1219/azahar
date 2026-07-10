from pathlib import Path


# Apply after yw2_thread_lifecycle_trace_patch.py and
# yw2_guest_failure_trace_patch.py. This records the generic thread trampoline
# payload directly in SVC CreateThread/ExitThread, independent of Dynarmic PC
# sampling. Use small, stable anchors rather than replacing whole log blocks.
path = Path("src/core/hle/kernel/svc.cpp")
text = path.read_text()


if "(YW2 COMM THREAD) CreateThread" not in text:
    create_marker = "(YW2 THREAD) CreateThread"
    return_anchor = "    return handle_result;\n"
    create_pos = text.find(create_marker)
    if create_pos < 0:
        raise RuntimeError("YW2 direct communication trace: CreateThread trace marker not found")
    return_pos = text.find(return_anchor, create_pos)
    if return_pos < 0:
        raise RuntimeError("YW2 direct communication trace: CreateThread return anchor not found")

    create_trace = r'''    if (entry_point == 0x0012E3E4) {
        const auto process = kernel.GetCurrentProcess();
        const auto yw2_read8 = [&](u32 address) -> u8 {
            if (!process || !memory.IsValidVirtualAddress(*process, address)) {
                return 0xFF;
            }
            return memory.Read8(address);
        };
        const auto yw2_read32 = [&](u32 address) -> u32 {
            if (!process || !memory.IsValidVirtualAddress(*process, address)) {
                return 0xFFFFFFFFU;
            }
            return memory.Read32(address);
        };
        const u32 function_at_4 = yw2_read32(arg + 0x04);
        const u32 function_at_8 = yw2_read32(arg + 0x08);
        const bool target_at_4 = function_at_4 == 0x00244EC8 || function_at_4 == 0x00294EC8;
        const bool target_at_8 = function_at_8 == 0x00244EC8 || function_at_8 == 0x00294EC8;
        if (target_at_4 || target_at_8) {
            const u32 callback_arg = target_at_4 ? yw2_read32(arg + 0x08)
                                                 : yw2_read32(arg + 0x0C);
            LOG_WARNING(Kernel_SVC,
                        "(YW2 COMM THREAD) CreateThread wrapper_arg=0x{:08X} "
                        "function4=0x{:08X} function8=0x{:08X} callback_arg=0x{:08X} "
                        "arg0=0x{:08X} ok9={} fail10={} words="
                        "0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X}",
                        arg, function_at_4, function_at_8, callback_arg,
                        yw2_read32(callback_arg), yw2_read8(callback_arg + 9),
                        yw2_read8(callback_arg + 10), yw2_read32(arg + 0x00),
                        yw2_read32(arg + 0x04), yw2_read32(arg + 0x08),
                        yw2_read32(arg + 0x0C), yw2_read32(arg + 0x10));
        }
    }
'''
    text = text[:return_pos] + create_trace + text[return_pos:]

    exit_anchor = "        const u32 original_arg = current_thread->stack_top;\n"
    result_pos = text.find("(YW2 THREAD RESULT)")
    if result_pos < 0:
        raise RuntimeError("YW2 direct communication trace: thread result marker not found")
    exit_pos = text.find(exit_anchor, result_pos)
    if exit_pos < 0:
        raise RuntimeError("YW2 direct communication trace: original_arg anchor not found")
    exit_insert_pos = exit_pos + len(exit_anchor)

    exit_trace = r'''        const auto yw2_read8 = [&](u32 address) -> u8 {
            if (!process || !memory.IsValidVirtualAddress(*process, address)) {
                return 0xFF;
            }
            return memory.Read8(address);
        };
        const u32 yw2_function_at_4 = read32(original_arg + 0x04);
        const u32 yw2_function_at_8 = read32(original_arg + 0x08);
        const bool yw2_target_at_4 =
            yw2_function_at_4 == 0x00244EC8 || yw2_function_at_4 == 0x00294EC8;
        const bool yw2_target_at_8 =
            yw2_function_at_8 == 0x00244EC8 || yw2_function_at_8 == 0x00294EC8;
        if (yw2_target_at_4 || yw2_target_at_8) {
            const u32 yw2_callback_arg =
                yw2_target_at_4 ? read32(original_arg + 0x08) : read32(original_arg + 0x0C);
            LOG_WARNING(Kernel_SVC,
                        "(YW2 COMM THREAD) ExitThread wrapper_base=0x{:08X} "
                        "function4=0x{:08X} function8=0x{:08X} callback_arg=0x{:08X} "
                        "arg0=0x{:08X} ok9={} fail10={} r0=0x{:08X} r4=0x{:08X} "
                        "pc=0x{:08X} lr=0x{:08X}",
                        original_arg, yw2_function_at_4, yw2_function_at_8,
                        yw2_callback_arg, read32(yw2_callback_arg),
                        yw2_read8(yw2_callback_arg + 9), yw2_read8(yw2_callback_arg + 10),
                        system.GetRunningCore().GetReg(0), system.GetRunningCore().GetReg(4),
                        pc, lr);
        }
'''
    text = text[:exit_insert_pos] + exit_trace + text[exit_insert_pos:]

    path.write_text(text)
    print("Applied direct YW2 communication thread lifecycle trace patch")
else:
    print("Skipped direct YW2 communication thread lifecycle trace patch: already present")
