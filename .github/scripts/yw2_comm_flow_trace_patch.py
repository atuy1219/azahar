from pathlib import Path


ARM_PATH = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
SVC_PATH = Path("src/core/hle/kernel/svc.cpp")
HEADER_PATH = Path("src/core/yw2_comm_write_watch.h")

arm_text = ARM_PATH.read_text()
svc_text = SVC_PATH.read_text()
header_text = HEADER_PATH.read_text()


def patch_arm(old: str, new: str, label: str) -> None:
    global arm_text
    if old not in arm_text:
        raise RuntimeError(f"YW2 communication flow trace ARM marker not found: {label}")
    arm_text = arm_text.replace(old, new, 1)


def patch_svc(old: str, new: str, label: str) -> None:
    global svc_text
    if old not in svc_text:
        raise RuntimeError(f"YW2 communication flow trace SVC marker not found: {label}")
    svc_text = svc_text.replace(old, new, 1)


if "inline std::atomic<bool> flow_active" not in header_text:
    header_text = header_text.replace(
        '''inline std::atomic<u32> callback_arg{};

inline void SetCallbackArg(u32 value) {
    callback_arg.store(value, std::memory_order_release);
}

inline u32 GetCallbackArg() {
    return callback_arg.load(std::memory_order_acquire);
}
''',
        '''inline std::atomic<u32> callback_arg{};
inline std::atomic<u32> flow_processor{};
inline std::atomic<u64> flow_generation{};
inline std::atomic<bool> flow_active{};

inline void SetCallbackArg(u32 value) {
    callback_arg.store(value, std::memory_order_release);
}

inline u32 GetCallbackArg() {
    return callback_arg.load(std::memory_order_acquire);
}

inline void StartFlow(u32 value, u32 processor) {
    callback_arg.store(value, std::memory_order_release);
    flow_processor.store(processor, std::memory_order_release);
    flow_generation.fetch_add(1, std::memory_order_acq_rel);
    flow_active.store(true, std::memory_order_release);
}

inline void StopFlow() {
    flow_active.store(false, std::memory_order_release);
}

inline bool FlowActive() {
    return flow_active.load(std::memory_order_acquire);
}

inline u32 FlowProcessor() {
    return flow_processor.load(std::memory_order_acquire);
}

inline u64 FlowGeneration() {
    return flow_generation.load(std::memory_order_acquire);
}
''',
        1,
    )
    if "inline std::atomic<bool> flow_active" not in header_text:
        raise RuntimeError("YW2 communication flow trace header marker not found")
    HEADER_PATH.write_text(header_text)

if "StartFlow(callback_arg" not in svc_text:
    patch_svc(
        "            Core::YW2CommWriteWatch::SetCallbackArg(callback_arg);\n",
        "            Core::YW2CommWriteWatch::StartFlow(callback_arg, processor_id);\n",
        "target thread flow start",
    )

    patch_svc(
        '''                        system.GetRunningCore().GetReg(0), system.GetRunningCore().GetReg(4),
                        pc, lr);
        }
''',
        '''                        system.GetRunningCore().GetReg(0), system.GetRunningCore().GetReg(4),
                        pc, lr);
            Core::YW2CommWriteWatch::StopFlow();
        }
''',
        "target thread flow stop",
    )

if "debug.azahar.yw2_comm_flow_trace" not in arm_text:
    patch_arm(
        "void YW2TraceCommPC(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u32 trace_pc) {\n",
        r'''bool YW2CommFlowTraceEnabled() {
#ifdef ANDROID
    char value[PROP_VALUE_MAX] = {};
    if (__system_property_get("debug.azahar.yw2_comm_flow_trace", value) <= 0) {
        return false;
    }
    return std::strcmp(value, "0") != 0 && std::strcmp(value, "false") != 0 &&
           std::strcmp(value, "off") != 0;
#else
    return false;
#endif
}

const char* YW2CommFlowRegion(u32 pc) {
    const u32 normalized = pc & ~u32{1};
    if (normalized >= 0x0012e3e4 && normalized <= 0x0012e430) {
        return "thread_wrapper";
    }
    if ((normalized >= 0x00244ec8 && normalized < 0x00244f50) ||
        (normalized >= 0x00294ec8 && normalized < 0x00294f50)) {
        return "target_244ec8";
    }
    return "callee_or_other";
}

void YW2TraceCommFlow(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u64 ticks) {
    if (!YW2CommFlowTraceEnabled() || !YW2CommWriteWatch::FlowActive() ||
        cpu.GetID() != YW2CommWriteWatch::FlowProcessor()) {
        return;
    }

    const u32 core = cpu.GetID() < 4 ? cpu.GetID() : 0;
    static u64 seen_generation[4]{};
    static u64 counts[4]{};
    static u32 last_pc[4]{};
    const u64 generation = YW2CommWriteWatch::FlowGeneration();
    if (seen_generation[core] != generation) {
        seen_generation[core] = generation;
        counts[core] = 0;
        last_pc[core] = 0xffffffffU;
    }

    const u32 pc = cpu.GetPC();
    if (pc == last_pc[core]) {
        return;
    }
    last_pc[core] = pc;
    const u64 count = ++counts[core];
    if (count > 1024) {
        return;
    }

    const u32 callback_arg = YW2CommWriteWatch::GetCallbackArg();
    LOG_WARNING(Core_ARM11,
                "(YW2 COMM FLOW) generation={} count={} core={} ticks={} region={} "
                "pc=0x{:08X} callback_arg=0x{:08X} ok9={} fail10={} "
                "r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X} "
                "r4=0x{:08X} r5=0x{:08X} r6=0x{:08X} r7=0x{:08X} "
                "r8=0x{:08X} r9=0x{:08X} r10=0x{:08X} r11=0x{:08X} "
                "r12=0x{:08X} sp=0x{:08X} lr=0x{:08X}",
                generation, count, core, ticks, YW2CommFlowRegion(pc), pc, callback_arg,
                callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 9) : 0xff,
                callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 10) : 0xff,
                cpu.GetReg(0), cpu.GetReg(1), cpu.GetReg(2), cpu.GetReg(3), cpu.GetReg(4),
                cpu.GetReg(5), cpu.GetReg(6), cpu.GetReg(7), cpu.GetReg(8), cpu.GetReg(9),
                cpu.GetReg(10), cpu.GetReg(11), cpu.GetReg(12), cpu.GetReg(13), cpu.GetReg(14));
}

void YW2TraceCommPC(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u32 trace_pc) {
''',
        "communication flow helpers",
    )

    patch_arm(
        '''    void AddTicks(std::uint64_t ticks) override {
        if (YW2CommTraceEnabled()) [[unlikely]] {
''',
        '''    void AddTicks(std::uint64_t ticks) override {
        if (YW2CommFlowTraceEnabled()) [[unlikely]] {
            YW2TraceCommFlow(parent, memory, ticks);
        }
        if (YW2CommTraceEnabled()) [[unlikely]] {
''',
        "communication flow AddTicks call",
    )

ARM_PATH.write_text(arm_text)
SVC_PATH.write_text(svc_text)
print("Applied lightweight YW2 target-thread communication flow trace patch")
