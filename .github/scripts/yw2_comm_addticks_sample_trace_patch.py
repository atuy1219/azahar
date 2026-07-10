from pathlib import Path


# Apply after yw2_comm_worker_trace_patch.py. This records the PCs that
# Dynarmic actually exposes through AddTicks(), restricted to communication
# code neighborhoods to avoid flooding logcat.
path = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
text = path.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 AddTicks sample trace marker not found: {label}")
    text = text.replace(old, new, 1)


if "(YW2 COMM PC SAMPLE)" not in text:
    patch_once(
        "void YW2TraceCommPC(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u32 trace_pc) {\n",
        r'''bool YW2CommSampleRange(u32 pc) {
    const u32 normalized = pc & ~u32{1};
    return (normalized >= 0x00244000 && normalized < 0x00246000) ||
           (normalized >= 0x00294000 && normalized < 0x00296000) ||
           (normalized >= 0x00339000 && normalized < 0x0033d000) ||
           (normalized >= 0x00389000 && normalized < 0x0038d000);
}

void YW2TraceCommAddTicksSample(ARM_Dynarmic& cpu, u64 ticks) {
    const u32 pc = cpu.GetPC();
    if (!YW2CommSampleRange(pc)) {
        return;
    }

    static std::atomic<u64> sample_count{};
    const u64 count = ++sample_count;
    if (count > 512 && (count % 5000) != 0) {
        return;
    }

    LOG_WARNING(Core_ARM11,
                "(YW2 COMM PC SAMPLE) count={} ticks={} pc=0x{:08X} r0=0x{:08X} "
                "r1=0x{:08X} r2=0x{:08X} r3=0x{:08X} r4=0x{:08X} "
                "sp=0x{:08X} lr=0x{:08X}",
                count, ticks, pc, cpu.GetReg(0), cpu.GetReg(1), cpu.GetReg(2),
                cpu.GetReg(3), cpu.GetReg(4), cpu.GetReg(13), cpu.GetReg(14));
}

void YW2TraceCommPC(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u32 trace_pc) {
''',
        "AddTicks PC sample helper",
    )

    patch_once(
        '''            YW2TraceCommPC(parent, memory, parent.GetPC());
''',
        '''            YW2TraceCommAddTicksSample(parent, ticks);
            YW2TraceCommPC(parent, memory, parent.GetPC());
''',
        "AddTicks PC sample call",
    )

    path.write_text(text)
    print("Applied YW2 AddTicks communication PC sample trace patch")
else:
    print("Skipped YW2 AddTicks communication PC sample trace patch: already present")
