from pathlib import Path
import re


ARM_PATH = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
NWM_PATH = Path("src/core/hle/service/nwm/nwm_uds.cpp")
COMM_HEADER_PATH = Path("src/core/yw2_comm_write_watch.h")
TRACE_HEADER_PATH = Path("src/core/yw2_destroy_timeout_trace.h")

arm_text = ARM_PATH.read_text()
nwm_text = NWM_PATH.read_text()
comm_header_text = COMM_HEADER_PATH.read_text()

if "YW2DestroyTimeoutTrace::Record" in arm_text:
    print("Skipped YW2 DestroyNetwork timeout history trace: already present")
    raise SystemExit(0)


def patch_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"YW2 DestroyNetwork trace marker not found: {label}")
    return text.replace(old, new, 1)


# The callback points into the helper thread's stack. Clear it as soon as that thread exits so
# later instrumentation cannot read released guest memory.
comm_header_text = patch_once(
    comm_header_text,
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

# The previous implementation read callback_arg+9/+10 for every guest write. Read those bytes
# only when the write is actually relevant to the communication watch.
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
        f"YW2 DestroyNetwork trace expected 8 callback flag read sites, found {flag_read_count}"
    )
arm_text = arm_text.replace(old_flag_reads, new_flag_reads)

TRACE_HEADER_PATH.write_text(
    r'''#pragma once

#include <array>
#include <atomic>
#include <cstddef>
#include <mutex>

#include "common/common_types.h"

namespace Core::YW2DestroyTimeoutTrace {

inline constexpr std::size_t Capacity = 64;

struct Entry {
    u64 sequence{};
    u64 ticks{};
    u32 core{};
    u32 runtime_pc{};
    u32 guest_pc{};
    std::array<u32, 15> regs{};
};

struct Snapshot {
    std::array<Entry, Capacity> entries{};
    std::size_t count{};
};

inline std::mutex ring_mutex;
inline std::array<Entry, Capacity> ring{};
inline u64 next_sequence{};
inline std::size_t ring_count{};
inline std::atomic<bool> active{false};

inline u32 NormalizeGuestPc(u32 runtime_pc) {
    const u32 normalized = runtime_pc & ~u32{1};
    if (normalized >= 0x00364000 && normalized < 0x00367000) {
        return normalized - 0x00050000;
    }
    return normalized;
}

inline bool IsTargetPc(u32 guest_pc) {
    return guest_pc >= 0x00314000 && guest_pc < 0x00317000;
}

inline void Start() {
    std::scoped_lock lock(ring_mutex);
    ring = {};
    next_sequence = 0;
    ring_count = 0;
    active.store(true, std::memory_order_release);
}

inline void Record(u32 core, u64 ticks, u32 runtime_pc,
                   const std::array<u32, 15>& regs) {
    if (!active.load(std::memory_order_acquire)) {
        return;
    }

    const u32 guest_pc = NormalizeGuestPc(runtime_pc);
    if (!IsTargetPc(guest_pc)) {
        return;
    }

    std::scoped_lock lock(ring_mutex);
    if (!active.load(std::memory_order_relaxed)) {
        return;
    }

    const u64 sequence = ++next_sequence;
    Entry& entry = ring[static_cast<std::size_t>((sequence - 1) % Capacity)];
    entry.sequence = sequence;
    entry.ticks = ticks;
    entry.core = core;
    entry.runtime_pc = runtime_pc;
    entry.guest_pc = guest_pc;
    entry.regs = regs;
    if (ring_count < Capacity) {
        ++ring_count;
    }
}

inline Snapshot StopAndSnapshot() {
    active.store(false, std::memory_order_release);
    std::scoped_lock lock(ring_mutex);

    Snapshot snapshot;
    snapshot.count = ring_count;
    if (ring_count == 0) {
        return snapshot;
    }

    const std::size_t first =
        static_cast<std::size_t>((next_sequence - ring_count) % Capacity);
    for (std::size_t index = 0; index < ring_count; ++index) {
        snapshot.entries[index] = ring[(first + index) % Capacity];
    }
    return snapshot;
}

} // namespace Core::YW2DestroyTimeoutTrace
'''
)

arm_text = patch_once(
    arm_text,
    '#include "core/core.h"\n',
    '#include "core/core.h"\n#include "core/yw2_destroy_timeout_trace.h"\n',
    "ARM include",
)

add_ticks_pattern = re.compile(r"(    void AddTicks\(std::uint64_t ticks\) override \{\n)")
add_ticks_insert = '''        if (YW2CommExecTraceEnabled()) [[unlikely]] {
            std::array<u32, 15> regs{};
            for (u32 reg = 0; reg <= 14; ++reg) {
                regs[reg] = parent.GetReg(reg);
            }
            YW2DestroyTimeoutTrace::Record(parent.GetID(), ticks, parent.GetPC(), regs);
        }
'''
arm_text, add_ticks_count = add_ticks_pattern.subn(
    lambda match: match.group(1) + add_ticks_insert,
    arm_text,
    count=1,
)
if add_ticks_count != 1:
    raise RuntimeError(
        f"YW2 DestroyNetwork trace expected one AddTicks marker, found {add_ticks_count}"
    )

nwm_text = patch_once(
    nwm_text,
    '#include "core/memory.h"\n',
    '#include "core/memory.h"\n#include "core/yw2_destroy_timeout_trace.h"\n',
    "NWM include",
)

begin_pattern = re.compile(
    r"(Result NWM_UDS::BeginHostingNetwork\(std::span<const u8> network_info_buffer,\n"
    r"\s+std::vector<u8> passphrase\) \{\n)"
)
nwm_text, begin_count = begin_pattern.subn(
    lambda match: match.group(1) + "    Core::YW2DestroyTimeoutTrace::Start();\n",
    nwm_text,
    count=1,
)
if begin_count != 1:
    raise RuntimeError(
        f"YW2 DestroyNetwork trace expected one BeginHostingNetwork marker, found {begin_count}"
    )

destroy_pattern = re.compile(
    r"(void NWM_UDS::DestroyNetwork\(Kernel::HLERequestContext& ctx\) \{\n)"
)
destroy_insert = '''    const auto history = Core::YW2DestroyTimeoutTrace::StopAndSnapshot();
    if (history.count != 0) {
        auto& cpu = system.GetRunningCore();
        const u32 runtime_pc = cpu.GetPC();
        const u32 guest_pc = Core::YW2DestroyTimeoutTrace::NormalizeGuestPc(runtime_pc);
        LOG_WARNING(Service_NWM,
                    "(YW2 DESTROY TRACE) history_count={} runtime_pc=0x{:08X} "
                    "guest_pc=0x{:08X} r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} "
                    "r3=0x{:08X} r4=0x{:08X} r5=0x{:08X} r6=0x{:08X} "
                    "r7=0x{:08X} r8=0x{:08X} r9=0x{:08X} r10=0x{:08X} "
                    "r11=0x{:08X} r12=0x{:08X} sp=0x{:08X} lr=0x{:08X}",
                    history.count, runtime_pc, guest_pc, cpu.GetReg(0), cpu.GetReg(1),
                    cpu.GetReg(2), cpu.GetReg(3), cpu.GetReg(4), cpu.GetReg(5),
                    cpu.GetReg(6), cpu.GetReg(7), cpu.GetReg(8), cpu.GetReg(9),
                    cpu.GetReg(10), cpu.GetReg(11), cpu.GetReg(12), cpu.GetReg(13),
                    cpu.GetReg(14));
        for (std::size_t index = 0; index < history.count; ++index) {
            const auto& entry = history.entries[index];
            LOG_WARNING(Service_NWM,
                        "(YW2 DESTROY HISTORY) index={} seq={} ticks={} core={} "
                        "runtime_pc=0x{:08X} guest_pc=0x{:08X} "
                        "r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X} "
                        "r4=0x{:08X} r5=0x{:08X} r6=0x{:08X} r7=0x{:08X} "
                        "r8=0x{:08X} r9=0x{:08X} r10=0x{:08X} r11=0x{:08X} "
                        "r12=0x{:08X} sp=0x{:08X} lr=0x{:08X}",
                        index, entry.sequence, entry.ticks, entry.core, entry.runtime_pc,
                        entry.guest_pc, entry.regs[0], entry.regs[1], entry.regs[2],
                        entry.regs[3], entry.regs[4], entry.regs[5], entry.regs[6],
                        entry.regs[7], entry.regs[8], entry.regs[9], entry.regs[10],
                        entry.regs[11], entry.regs[12], entry.regs[13], entry.regs[14]);
        }
    }

'''
nwm_text, destroy_count = destroy_pattern.subn(
    lambda match: match.group(1) + destroy_insert,
    nwm_text,
    count=1,
)
if destroy_count != 1:
    raise RuntimeError(
        f"YW2 DestroyNetwork trace expected one DestroyNetwork declaration, found {destroy_count}"
    )

ARM_PATH.write_text(arm_text)
NWM_PATH.write_text(nwm_text)
COMM_HEADER_PATH.write_text(comm_header_text)
print("Applied YW2 freed-callback cleanup and DestroyNetwork timeout history trace")
