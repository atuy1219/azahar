from pathlib import Path

PATH = Path("src/core/hle/kernel/svc.cpp")
text = PATH.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 SVC context/memory trace marker not found: {label}")
    text = text.replace(old, new, 1)


if "(YW2 WAIT CONTEXT)" not in text:
    patch_once(
        '''    const bool yw2_wait_trace = YW2SvcWaitTraceEnabled();
    const bool yw2_should_wait = object->ShouldWait(thread);
    if (yw2_wait_trace) {
''',
        '''    const bool yw2_wait_trace = YW2SvcWaitTraceEnabled();
    const bool yw2_should_wait = object->ShouldWait(thread);
    const u32 yw2_wait_pc = system.GetRunningCore().GetPC();
    if (yw2_wait_trace && yw2_wait_pc == 0x0020528C) {
        const auto yw2_process = kernel.GetCurrentProcess();
        const auto yw2_read32 = [&](u32 address) -> u32 {
            if (!yw2_process || !memory.IsValidVirtualAddress(*yw2_process, address)) {
                return 0xFFFFFFFFU;
            }
            return memory.Read32(address);
        };
        const u32 r0 = system.GetRunningCore().GetReg(0);
        const u32 r1 = system.GetRunningCore().GetReg(1);
        const u32 r2 = system.GetRunningCore().GetReg(2);
        const u32 r3 = system.GetRunningCore().GetReg(3);
        const u32 r4 = system.GetRunningCore().GetReg(4);
        const u32 r5 = system.GetRunningCore().GetReg(5);
        const u32 r6 = system.GetRunningCore().GetReg(6);
        const u32 r7 = system.GetRunningCore().GetReg(7);
        const u32 r8 = system.GetRunningCore().GetReg(8);
        const u32 r9 = system.GetRunningCore().GetReg(9);
        const u32 r10 = system.GetRunningCore().GetReg(10);
        const u32 r11 = system.GetRunningCore().GetReg(11);
        const u32 r12 = system.GetRunningCore().GetReg(12);
        const u32 sp = system.GetRunningCore().GetReg(13);
        const u32 lr = system.GetRunningCore().GetReg(14);
        LOG_WARNING(Kernel_SVC,
                    "(YW2 WAIT CONTEXT) pc=0x{:08X} tid={} handle=0x{:08X} timeout={} "
                    "should_wait={} r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X} "
                    "r4=0x{:08X} r5=0x{:08X} r6=0x{:08X} r7=0x{:08X} r8=0x{:08X} "
                    "r9=0x{:08X} r10=0x{:08X} r11=0x{:08X} r12=0x{:08X} sp=0x{:08X} lr=0x{:08X}",
                    yw2_wait_pc, thread ? thread->GetThreadId() : 0, handle, nano_seconds,
                    yw2_should_wait, r0, r1, r2, r3, r4, r5, r6, r7, r8, r9, r10, r11, r12,
                    sp, lr);
        LOG_WARNING(Kernel_SVC,
                    "(YW2 WAIT MEMORY) r0=0x{:08X},0x{:08X} r1=0x{:08X},0x{:08X} "
                    "r2=0x{:08X},0x{:08X} r3=0x{:08X},0x{:08X} r4=0x{:08X},0x{:08X} "
                    "r5=0x{:08X},0x{:08X} stack=0x{:08X},0x{:08X},0x{:08X},0x{:08X},"
                    "0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X}",
                    yw2_read32(r0), yw2_read32(r0 + 4), yw2_read32(r1), yw2_read32(r1 + 4),
                    yw2_read32(r2), yw2_read32(r2 + 4), yw2_read32(r3), yw2_read32(r3 + 4),
                    yw2_read32(r4), yw2_read32(r4 + 4), yw2_read32(r5), yw2_read32(r5 + 4),
                    yw2_read32(sp + 0x00), yw2_read32(sp + 0x04), yw2_read32(sp + 0x08),
                    yw2_read32(sp + 0x0C), yw2_read32(sp + 0x10), yw2_read32(sp + 0x14),
                    yw2_read32(sp + 0x18), yw2_read32(sp + 0x1C), yw2_read32(sp + 0x20),
                    yw2_read32(sp + 0x24), yw2_read32(sp + 0x28), yw2_read32(sp + 0x2C));
    }
    if (yw2_wait_trace) {
''',
        "WaitSynchronization1 target context",
    )

if "(YW2 THREAD ARG)" not in text:
    patch_once(
        '''    if (entry_point == 0x0012E3E4 || entry_point == 0x0020528C ||
        entry_point == 0x0013F8C4 || entry_point == 0x005E7EEC) {
        LOG_WARNING(Kernel_SVC,
''',
        '''    if (entry_point == 0x0012E3E4 || entry_point == 0x0020528C ||
        entry_point == 0x0013F8C4 || entry_point == 0x005E7EEC) {
        const auto yw2_read32 = [&](u32 address) -> u32 {
            if (!current_process || !memory.IsValidVirtualAddress(*current_process, address)) {
                return 0xFFFFFFFFU;
            }
            return memory.Read32(address);
        };
        LOG_WARNING(Kernel_SVC,
''',
        "CreateThread safe memory reader",
    )

    patch_once(
        '''                    name, entry_point, arg, stack_top, priority, processor_id, *out_handle,
                    system.GetRunningCore().GetPC(), system.GetRunningCore().GetReg(14));
    }
''',
        '''                    name, entry_point, arg, stack_top, priority, processor_id, *out_handle,
                    system.GetRunningCore().GetPC(), system.GetRunningCore().GetReg(14));
        LOG_WARNING(Kernel_SVC,
                    "(YW2 THREAD ARG) entry=0x{:08X} arg=0x{:08X} words="
                    "0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},"
                    "0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},"
                    "0x{:08X},0x{:08X},0x{:08X},0x{:08X}",
                    entry_point, arg, yw2_read32(arg - 0x10), yw2_read32(arg - 0x0C),
                    yw2_read32(arg - 0x08), yw2_read32(arg - 0x04), yw2_read32(arg + 0x00),
                    yw2_read32(arg + 0x04), yw2_read32(arg + 0x08), yw2_read32(arg + 0x0C),
                    yw2_read32(arg + 0x10), yw2_read32(arg + 0x14), yw2_read32(arg + 0x18),
                    yw2_read32(arg + 0x1C), yw2_read32(arg + 0x20), yw2_read32(arg + 0x24),
                    yw2_read32(arg + 0x28), yw2_read32(arg + 0x2C), yw2_read32(arg + 0x30),
                    yw2_read32(arg + 0x34), yw2_read32(arg + 0x38), yw2_read32(arg + 0x3C));
    }
''',
        "CreateThread arg dump",
    )

PATH.write_text(text)
print("Applied YW2 SVC context and memory trace patch")
