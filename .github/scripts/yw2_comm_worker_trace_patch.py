from pathlib import Path


# Apply after yw2_arm_pc_trace_patch.py and
# yw2_arm_pc_trace_runtime_fix_patch.py.  This deliberately uses Dynarmic's
# runtime block-boundary callback and never switches ARM_Dynarmic::Run() to
# jit->Step().
path = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
text = path.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 communication trace patch marker not found: {label}")
    text = text.replace(old, new, 1)


if "debug.azahar.yw2_comm_trace" not in text:
    patch_once(
        "void YW2TraceArmPC(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u32 trace_pc) {\n",
        r'''bool YW2CommTraceEnabled() {
#ifdef ANDROID
    char value[PROP_VALUE_MAX] = {};
    if (__system_property_get("debug.azahar.yw2_comm_trace", value) <= 0) {
        return false;
    }
    return std::strcmp(value, "0") != 0 && std::strcmp(value, "false") != 0 &&
           std::strcmp(value, "off") != 0;
#else
    return false;
#endif
}

u32 YW2CanonicalCommTarget(u32 pc) {
    const u32 normalized = pc & ~u32{1};
    switch (normalized) {
    case 0x00244ca4:
    case 0x00294ca4:
        return 0x00244ca4;
    case 0x00244cfc:
    case 0x00294cfc:
        return 0x00244cfc;
    case 0x00244e24:
    case 0x00294e24:
        return 0x00244e24;
    case 0x00244ec8:
    case 0x00294ec8:
        return 0x00244ec8;
    case 0x00244f4c:
    case 0x00294f4c:
        return 0x00244f4c;
    case 0x00339994:
    case 0x00389994:
        return 0x00339994;
    case 0x00339d8c:
    case 0x00389d8c:
        return 0x00339d8c;
    case 0x0033b06c:
    case 0x0038b06c:
        return 0x0033b06c;
    case 0x0033b070:
    case 0x0038b070:
        return 0x0033b070;
    case 0x0033b8bc:
    case 0x0038b8bc:
        return 0x0033b8bc;
    case 0x0033bb00:
    case 0x0038bb00:
        return 0x0033bb00;
    case 0x0033bb2c:
    case 0x0038bb2c:
        return 0x0033bb2c;
    case 0x0033bb30:
    case 0x0038bb30:
        return 0x0033bb30;
    case 0x0033c0a0:
    case 0x0038c0a0:
        return 0x0033c0a0;
    default:
        return 0;
    }
}

void YW2LogWorkerOwner(Memory::MemorySystem& memory, const char* label, u32 owner) {
    const u32 worker = YW2Read32Or(memory, owner + 0x2a70);
    LOG_WARNING(Core_ARM11,
                "(YW2 COMM) {} owner=0x{:08X} enable_2a6f={} packet_flag_2a8d={} "
                "worker=0x{:08X} worker_active={}",
                label, owner, YW2Read8Or(memory, owner + 0x2a6f),
                YW2Read8Or(memory, owner + 0x2a8d), worker,
                worker != 0 ? YW2Read8Or(memory, worker + 0x3eec) : 0xff);
}

void YW2LogSessionError(Memory::MemorySystem& memory, const char* label, u32 object) {
    LOG_WARNING(Core_ARM11,
                "(YW2 COMM) {} object=0x{:08X} state34={} error_e4=0x{:08X} "
                "detail_e8=0x{:08X} source88=0x{:08X}",
                label, object, YW2Read8Or(memory, object + 0x34),
                YW2Read32Or(memory, object + 0xe4),
                YW2Read32Or(memory, object + 0xe8),
                YW2Read32Or(memory, object + 0x88));
}

void YW2TraceCommPC(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u32 trace_pc) {
    const u32 target = YW2CanonicalCommTarget(trace_pc);
    if (target == 0) {
        return;
    }

    static std::atomic<u64> hit_count{};
    const u64 count = ++hit_count;
    if (count > 256 && (count % 5000) != 0) {
        return;
    }

    const u32 r0 = cpu.GetReg(0);
    const u32 r1 = cpu.GetReg(1);
    const u32 r2 = cpu.GetReg(2);
    const u32 r3 = cpu.GetReg(3);
    const u32 r4 = cpu.GetReg(4);
    const u32 lr = cpu.GetReg(14);
    LOG_WARNING(Core_ARM11,
                "(YW2 COMM) runtime target=0x{:08X} trace_pc=0x{:08X} cpu_pc=0x{:08X} "
                "count={} r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X} "
                "r4=0x{:08X} lr=0x{:08X}",
                target, trace_pc, cpu.GetPC(), count, r0, r1, r2, r3, r4, lr);

    switch (target) {
    case 0x0033b8bc:
        YW2LogWorkerOwner(memory, "FUN_0033b8bc entry", r0);
        break;
    case 0x0033bb00:
        YW2LogWorkerOwner(memory, "FUN_0033b8bc worker gate", r4);
        break;
    case 0x0033bb2c:
        YW2LogWorkerOwner(memory, "FUN_00339994 call before", r4);
        break;
    case 0x0033bb30:
        YW2LogWorkerOwner(memory, "FUN_00339994 call after", r4);
        LOG_WARNING(Core_ARM11, "(YW2 COMM) FUN_00339994 return r0=0x{:08X}", r0);
        break;
    case 0x0033b06c:
        YW2LogWorkerOwner(memory, "participate FUN_00339994 call before", r4);
        break;
    case 0x0033b070:
        YW2LogWorkerOwner(memory, "participate FUN_00339994 call after", r4);
        LOG_WARNING(Core_ARM11, "(YW2 COMM) participate FUN_00339994 return r0=0x{:08X}", r0);
        break;
    case 0x00339994:
        LOG_WARNING(Core_ARM11,
                    "(YW2 COMM) FUN_00339994 entry worker=0x{:08X} active={} r1=0x{:08X} "
                    "r2=0x{:08X} r3=0x{:08X}",
                    r0, YW2Read8Or(memory, r0 + 0x3eec), r1, r2, r3);
        break;
    case 0x00339d8c:
        LOG_WARNING(Core_ARM11,
                    "(YW2 COMM) FUN_00339d8c entry worker=0x{:08X} callback=0x{:08X} "
                    "arg=0x{:08X} active={}",
                    r0, r1, r2, YW2Read8Or(memory, r0 + 0x3eec));
        break;
    case 0x0033c0a0:
        LOG_WARNING(Core_ARM11,
                    "(YW2 COMM) FUN_0033c0a0 entry r0=0x{:08X} r1=0x{:08X} "
                    "r2=0x{:08X} r3=0x{:08X}",
                    r0, r1, r2, r3);
        break;
    case 0x00244ca4:
        YW2LogSessionError(memory, "FUN_00244ca4 entry", r1);
        break;
    case 0x00244cfc:
        YW2LogSessionError(memory, "FUN_00244ca4 error write #1", r4);
        break;
    case 0x00244e24:
        YW2LogSessionError(memory, "FUN_00244ca4 error write #2", r4);
        break;
    case 0x00244ec8:
        LOG_WARNING(Core_ARM11,
                    "(YW2 COMM) FUN_00244ec8 entry arg=0x{:08X} arg0=0x{:08X} ok9={} fail10={}",
                    r0, YW2Read32Or(memory, r0), YW2Read8Or(memory, r0 + 9),
                    YW2Read8Or(memory, r0 + 10));
        break;
    case 0x00244f4c:
        LOG_WARNING(Core_ARM11,
                    "(YW2 COMM) FUN_00244ec8 exit arg=0x{:08X} arg0=0x{:08X} ok9={} fail10={}",
                    r4, YW2Read32Or(memory, r4), YW2Read8Or(memory, r4 + 9),
                    YW2Read8Or(memory, r4 + 10));
        break;
    default:
        break;
    }
}

void YW2TraceArmPC(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u32 trace_pc) {
''',
        "communication trace helpers",
    )

    patch_once(
        '''    void AddTicks(std::uint64_t ticks) override {
        parent.GetTimer().AddTicks(ticks);
    }
''',
        '''    void AddTicks(std::uint64_t ticks) override {
        if (YW2CommTraceEnabled()) [[unlikely]] {
            // Dynarmic calls this while guest register state is synchronized at
            // an executed basic-block boundary.  Unlike MemoryReadCode(), this
            // is a runtime observation rather than a translation-time probe.
            YW2TraceCommPC(parent, memory, parent.GetPC());
        }
        parent.GetTimer().AddTicks(ticks);
    }
''',
        "communication runtime block-boundary hook",
    )


path.write_text(text)
print("Applied non-Step YW2 communication worker trace patch")
