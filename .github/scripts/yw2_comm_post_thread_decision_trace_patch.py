from pathlib import Path


ARM_PATH = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
HEADER_PATH = Path("src/core/yw2_comm_write_watch.h")

arm_text = ARM_PATH.read_text()
header_text = HEADER_PATH.read_text()

if "YW2TracePostThreadDecisionWrite" in arm_text:
    print("Skipped YW2 post-thread decision trace fix: already present")
    raise SystemExit(0)


def patch_arm_once(old: str, new: str, label: str) -> None:
    global arm_text
    if old not in arm_text:
        raise RuntimeError(f"YW2 post-thread decision trace ARM marker not found: {label}")
    arm_text = arm_text.replace(old, new, 1)


def patch_header_once(old: str, new: str, label: str) -> None:
    global header_text
    if old not in header_text:
        raise RuntimeError(f"YW2 post-thread decision trace header marker not found: {label}")
    header_text = header_text.replace(old, new, 1)


# The callback points into the helper thread's stack. Once that thread exits the stack is
# released, so retaining the address makes later instrumentation read freed guest memory.
patch_header_once(
    '''inline void StopFlow() {
    flow_active.store(false, std::memory_order_release);
}
''',
    '''inline void StopFlow() {
    flow_active.store(false, std::memory_order_release);
    callback_arg.store(0, std::memory_order_release);
    flow_processor.store(0, std::memory_order_release);
    flow_stack_top.store(0, std::memory_order_release);
}
''',
    "clear callback state when target thread exits",
)


# The old flag bytes are needed only for writes that actually overlap the callback flags or
# carry the watched result value. Do not read callback_arg+9/+10 on every guest write.
old_flag_reads = '''        const u32 callback_arg = YW2CommWriteWatch::GetCallbackArg();
        const u8 old9 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 9) : 0xFF;
        const u8 old10 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 10) : 0xFF;
'''
new_flag_reads = '''        const u32 callback_arg =
            comm_watch ? YW2CommWriteWatch::GetCallbackArg() : 0;
        const u8 old9 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 9) : 0xFF;
        const u8 old10 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 10) : 0xFF;
'''
flag_read_count = arm_text.count(old_flag_reads)
if flag_read_count != 8:
    raise RuntimeError(
        f"YW2 post-thread decision trace expected 8 callback flag read sites, found {flag_read_count}"
    )
arm_text = arm_text.replace(old_flag_reads, new_flag_reads)


# Record only register/write-state changes at the two post-thread decision PCs. This helper
# performs no guest-memory reads, so it cannot recreate the freed-callback access problem.
# Use a uniquely named property helper here instead of forward-declaring
# YW2CommExecTraceEnabled(). The exact-execution patch defines that function later in a
# different anonymous-namespace scope, and a forward declaration here makes calls ambiguous.
patch_arm_once(
    "bool YW2CommDynamicFlagOverlaps(u32 address, u32 size) {\n",
    r'''bool YW2PostThreadDecisionTraceEnabled() {
#ifdef ANDROID
    char value[PROP_VALUE_MAX] = {};
    if (__system_property_get("debug.azahar.yw2_comm_exec_trace", value) <= 0) {
        return false;
    }
    return std::strcmp(value, "0") != 0 && std::strcmp(value, "false") != 0 &&
           std::strcmp(value, "off") != 0;
#else
    return false;
#endif
}

void YW2TracePostThreadDecisionWrite(ARM_Dynarmic& cpu, u32 address, u64 value, u32 size) {
    if (!YW2PostThreadDecisionTraceEnabled() || YW2CommWriteWatch::FlowGeneration() == 0 ||
        YW2CommWriteWatch::FlowActive()) {
        return;
    }

    const u32 pc = cpu.GetPC() & ~u32{1};
    int index = -1;
    const char* decision = "unknown";
    if (pc == 0x001208D8) {
        index = 0;
        decision = "decision_1208d8";
    } else if (pc == 0x00120A7C) {
        index = 1;
        decision = "decision_120a7c";
    } else {
        return;
    }

    u64 fingerprint = 1469598103934665603ULL;
    const auto mix = [&fingerprint](u64 part) {
        fingerprint ^= part;
        fingerprint *= 1099511628211ULL;
    };
    mix(address);
    mix(value);
    mix(size);
    for (u32 reg = 0; reg <= 14; ++reg) {
        mix(cpu.GetReg(reg));
    }

    static std::atomic<u64> counts[2]{};
    static std::atomic<u64> last_fingerprints[2]{};
    const u64 count = ++counts[index];
    const u64 previous = last_fingerprints[index].exchange(fingerprint);
    const bool changed = previous != fingerprint;
    if (!changed && count > 8 && (count % 256) != 0) {
        return;
    }

    LOG_WARNING(Core_ARM11,
                "(YW2 COMM EXEC) kind=post_thread_decision_write decision={} count={} "
                "changed={} pc=0x{:08X} address=0x{:08X} size={} value=0x{:016X} "
                "r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X} "
                "r4=0x{:08X} r5=0x{:08X} r6=0x{:08X} r7=0x{:08X} "
                "r8=0x{:08X} r9=0x{:08X} r10=0x{:08X} r11=0x{:08X} "
                "r12=0x{:08X} sp=0x{:08X} lr=0x{:08X}",
                decision, count, changed, pc, address, size, value, cpu.GetReg(0),
                cpu.GetReg(1), cpu.GetReg(2), cpu.GetReg(3), cpu.GetReg(4), cpu.GetReg(5),
                cpu.GetReg(6), cpu.GetReg(7), cpu.GetReg(8), cpu.GetReg(9), cpu.GetReg(10),
                cpu.GetReg(11), cpu.GetReg(12), cpu.GetReg(13), cpu.GetReg(14));
}

bool YW2CommDynamicFlagOverlaps(u32 address, u32 size) {
''',
    "post-thread decision write helper",
)


for bits, cpp_type in (
    (8, "std::uint8_t"),
    (16, "std::uint16_t"),
    (32, "std::uint32_t"),
    (64, "std::uint64_t"),
):
    patch_arm_once(
        f'''    void MemoryWrite{bits}(VAddr vaddr, {cpp_type} value) override {{
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
''',
        f'''    void MemoryWrite{bits}(VAddr vaddr, {cpp_type} value) override {{
        YW2TracePostThreadDecisionWrite(parent, vaddr, value, sizeof(value));
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
''',
        f"MemoryWrite{bits} post-thread decision trace",
    )

ARM_PATH.write_text(arm_text)
HEADER_PATH.write_text(header_text)
print("Applied YW2 freed-callback cleanup and post-thread decision write trace")
