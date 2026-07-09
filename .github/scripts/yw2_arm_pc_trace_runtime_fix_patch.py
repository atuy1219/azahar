from pathlib import Path

path = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
text = path.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 ARM runtime fix marker not found: {label}")
    text = text.replace(old, new, 1)


patch_once(
    '''bool YW2ArmTraceEnabled() {
#ifdef ANDROID
    static const bool enabled = []() -> bool {
        char value[PROP_VALUE_MAX] = {};
        if (__system_property_get("debug.azahar.yw2_arm_trace", value) <= 0) {
            return false;
        }
        return std::strcmp(value, "0") != 0 && std::strcmp(value, "false") != 0 &&
               std::strcmp(value, "off") != 0;
    }();
    return enabled;
#else
    return false;
#endif
}
''',
    '''bool YW2ArmTraceEnabled() {
#ifdef ANDROID
    char value[PROP_VALUE_MAX] = {};
    if (__system_property_get("debug.azahar.yw2_arm_trace", value) <= 0) {
        return false;
    }
    return std::strcmp(value, "0") != 0 && std::strcmp(value, "false") != 0 &&
           std::strcmp(value, "off") != 0;
#else
    return false;
#endif
}
''',
    "dynamic property helper",
)

patch_once(
    '''    std::optional<std::uint32_t> MemoryReadCode(VAddr vaddr) override {
        if (YW2ArmTraceEnabled()) [[unlikely]] {
            YW2TraceArmPC(parent, memory, vaddr);
        }
        return memory.Read32OrNullopt(vaddr);
    }
''',
    '''    std::optional<std::uint32_t> MemoryReadCode(VAddr vaddr) override {
        if (YW2ArmTraceEnabled()) [[unlikely]] {
            static std::atomic<u64> yw2_code_probe_count{};
            const u64 probe_count = ++yw2_code_probe_count;
            if (probe_count <= 20 || (probe_count % 10000) == 0) {
                LOG_WARNING(Core_ARM11,
                            "(YW2 ARM) enabled code_probe count={} vaddr=0x{:08X} cpu_pc=0x{:08X}",
                            probe_count, vaddr, parent.GetPC());
            }
            YW2TraceArmPC(parent, memory, vaddr);
        }
        return memory.Read32OrNullopt(vaddr);
    }
''',
    "MemoryReadCode enabled probe",
)

path.write_text(text)
print("Applied YW2 ARM PC trace runtime fix patch")

# Apply worker-busy trace before the runtime alias patch. The alias patch rewrites the existing
# MemoryReadCode/YW2MatchTraceTarget text, so applying it first makes the worker patch markers stale.
worker_patch = Path(".github/scripts/yw2_worker_busy_trace_patch.py")
if worker_patch.exists():
    exec(worker_patch.read_text(), {"__name__": "__main__"})

connection_event_patch = Path(".github/scripts/yw2_nwm_connection_event_trace_patch.py")
if connection_event_patch.exists():
    exec(connection_event_patch.read_text(), {"__name__": "__main__"})

extra_patch = Path(".github/scripts/yw2_arm_runtime_alias_patch.py")
if extra_patch.exists():
    exec(extra_patch.read_text(), {"__name__": "__main__"})

# Do not chain yw2_arm_func_runtime_trace_patch.py here.
# Its Step-based runtime tracing can break SendSyncRequest/server-session assumptions.
