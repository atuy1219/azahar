from pathlib import Path

path = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
text = path.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 ARM function runtime trace marker not found: {label}")
    text = text.replace(old, new, 1)


helper_marker = "void YW2TraceArmPC(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u32 trace_pc) {\n"

if "bool YW2FuncTraceEnabled()" not in text:
    patch_once(
        helper_marker,
        r'''bool YW2FuncTraceEnabled() {
#ifdef ANDROID
    char value[PROP_VALUE_MAX] = {};
    if (__system_property_get("debug.azahar.yw2_func_trace", value) <= 0) {
        return false;
    }
    return std::strcmp(value, "0") != 0 && std::strcmp(value, "false") != 0 &&
           std::strcmp(value, "off") != 0;
#else
    return false;
#endif
}

u32 YW2CanonicalFuncTarget(u32 pc) {
    const u32 normalized = pc & ~u32{1};
    switch (normalized) {
    case 0x00339994:
    case 0x00389994:
        return 0x00339994;
    case 0x00339c90:
    case 0x00389c90:
        return 0x00339c90;
    case 0x00339d8c:
    case 0x00389d8c:
        return 0x00339d8c;
    case 0x0033c0a0:
    case 0x0038c0a0:
        return 0x0033c0a0;
    case 0x0033b8bc:
    case 0x0038b8bc:
        return 0x0033b8bc;
    case 0x00364d20:
    case 0x003b4d20:
        return 0x00364d20;
    default:
        return 0;
    }
}

void YW2TraceFuncRuntime(ARM_Dynarmic& cpu, Memory::MemorySystem& memory) {
    const u32 pc = cpu.GetPC();
    const u32 target = YW2CanonicalFuncTarget(pc);
    if (target == 0) {
        return;
    }

    const u32 lr = cpu.GetReg(14);
    const u32 sp = cpu.GetReg(13);
    const u32 r0 = cpu.GetReg(0);
    const u32 r1 = cpu.GetReg(1);
    const u32 r2 = cpu.GetReg(2);
    const u32 r3 = cpu.GetReg(3);

    switch (target) {
    case 0x00339994: {
        LOG_WARNING(Core_ARM11,
                    "(YW2 FUNC) gate_39994 enter pc=0x{:08X} lr=0x{:08X} obj=0x{:08X} active={} arg5=0x{:08X} sp=0x{:08X} sp4=0x{:08X} sp8=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X}",
                    pc, lr, r0, YW2Read8Or(memory, r0 + 0x3eec), YW2Read32Or(memory, sp), sp,
                    YW2Read32Or(memory, sp + 4), YW2Read32Or(memory, sp + 8), r1, r2, r3);
        break;
    }
    case 0x00339c90:
        LOG_WARNING(Core_ARM11,
                    "(YW2 FUNC) worker_stop_39c90 enter pc=0x{:08X} lr=0x{:08X} obj=0x{:08X} evt=0x{:08X} thread=0x{:08X} stop={} active={}",
                    pc, lr, r0, YW2Read32Or(memory, r0 + 0x2ed8),
                    YW2Read32Or(memory, r0 + 0x2edc), YW2Read8Or(memory, r0 + 0x2ee0),
                    YW2Read8Or(memory, r0 + 0x3eec));
        break;
    case 0x00339d8c:
        LOG_WARNING(Core_ARM11,
                    "(YW2 FUNC) worker_start_39d8c enter pc=0x{:08X} lr=0x{:08X} obj=0x{:08X} cb=0x{:08X} arg=0x{:08X} active={}",
                    pc, lr, r0, r1, r2, YW2Read8Or(memory, r0 + 0x3eec));
        break;
    case 0x0033c0a0:
        LOG_WARNING(Core_ARM11,
                    "(YW2 FUNC) packet_loop_33c0a0 enter pc=0x{:08X} lr=0x{:08X} r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X}",
                    pc, lr, r0, r1, r2, r3);
        break;
    case 0x0033b8bc: {
        const u32 worker = YW2Read32Or(memory, r0 + 0x2a70);
        LOG_WARNING(Core_ARM11,
                    "(YW2 FUNC) room_create_33b8bc enter pc=0x{:08X} lr=0x{:08X} room=0x{:08X} worker=0x{:08X} active={} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X}",
                    pc, lr, r0, worker, worker != 0 ? YW2Read8Or(memory, worker + 0x3eec) : 0xff,
                    r1, r2, r3);
        break;
    }
    case 0x00364d20:
        LOG_WARNING(Core_ARM11,
                    "(YW2 FUNC) destroy_wrap_364d20 enter pc=0x{:08X} lr=0x{:08X} r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X}",
                    pc, lr, r0, r1, r2, r3);
        break;
    }
}

void YW2TraceArmPC(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u32 trace_pc) {
''',
        "function runtime trace helpers",
    )

patch_once(
    '''void ARM_Dynarmic::Run() {
    ASSERT(memory.GetCurrentPageTable() == current_page_table);
    MICROPROFILE_SCOPE(ARM_Jit);
    if (break_flag) [[unlikely]] {
        return;
    }

    jit->Run();
}
''',
    '''void ARM_Dynarmic::Run() {
    ASSERT(memory.GetCurrentPageTable() == current_page_table);
    MICROPROFILE_SCOPE(ARM_Jit);
    if (break_flag) [[unlikely]] {
        return;
    }

    if (YW2FuncTraceEnabled()) [[unlikely]] {
        u32 step_count = 0;
        while (!break_flag && GetTimer().GetDowncount() > 0 && step_count < 100000) {
            YW2TraceFuncRuntime(*this, memory);
            jit->Step();
            ++step_count;
        }
        return;
    }

    jit->Run();
}
''',
    "step-loop runtime trace Run hook",
)

path.write_text(text)
print("Applied YW2 ARM function runtime trace patch")
