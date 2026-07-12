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
    print("Skipped YW2 worker timeout range trace: already present")
    raise SystemExit(0)


def patch_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"YW2 worker timeout range trace marker not found: {label}")
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

# Read callback bytes only for communication writes. This avoids dereferencing released callback
# state after the helper thread exits.
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
        f"YW2 worker timeout range trace expected 8 callback flag read sites, found {flag_read_count}"
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

inline constexpr std::size_t Capacity = 512;
inline constexpr u32 InvalidValue = 0xFFFFFFFFU;

struct Observation {
    u64 ticks{};
    u32 runtime_pc{};
    std::array<u32, 15> regs{};
    u32 r0_active8{InvalidValue};
    u32 r0_active32{InvalidValue};
    u32 room{};
    u32 room_worker{};
    u32 room_active8{InvalidValue};
    u32 room_active32{InvalidValue};
    u32 stop_2ed8{InvalidValue};
    u32 stop_2edc{InvalidValue};
    u32 stop_2ee0{InvalidValue};
    std::array<u32, 8> stack_words{};
};

struct Entry {
    u64 sequence{};
    u64 hit_count{1};
    u32 core{};
    u32 static_pc{};
    Observation first{};
    Observation last{};
};

struct Snapshot {
    std::array<Entry, Capacity> entries{};
    std::size_t count{};
    u32 start_pc{};
};

inline std::mutex ring_mutex;
inline std::array<Entry, Capacity> ring{};
inline u64 next_sequence{};
inline std::size_t ring_count{};
inline u32 trace_start_pc{};
inline std::atomic<bool> active{false};

inline u32 NormalizeRuntimePc(u32 runtime_pc) {
    return runtime_pc & ~u32{1};
}

inline bool InRange(u32 pc, u32 first, u32 last) {
    return pc >= first && pc <= last;
}

inline bool IsRoomFlowPc(u32 pc) {
    return InRange(pc, 0x0033B880, 0x0033BB40);
}

inline bool IsWorkerControlPc(u32 pc) {
    return InRange(pc, 0x00339980, 0x00339EB0);
}

inline bool IsWorkerStopPc(u32 pc) {
    return InRange(pc, 0x00339C60, 0x00339D30);
}

inline bool IsPacketLoopPc(u32 pc) {
    return InRange(pc, 0x0033C080, 0x0033C180);
}

inline bool IsDestroyWrapperPc(u32 pc) {
    return InRange(pc, 0x00364D00, 0x00364D80);
}

inline bool IsNwmWrapperPc(u32 pc) {
    return InRange(pc, 0x003660C0, 0x00366120);
}

inline bool IsTargetPc(u32 pc) {
    return IsRoomFlowPc(pc) || IsWorkerControlPc(pc) || IsPacketLoopPc(pc) ||
           IsDestroyWrapperPc(pc) || IsNwmWrapperPc(pc);
}

inline const char* TargetName(u32 pc) {
    switch (pc) {
    case 0x0033B8BC:
        return "room_setup";
    case 0x0033BAF4:
    case 0x0033BAFC:
        return "post_begin_host";
    case 0x0033BB00:
        return "post_channel";
    case 0x0033BB2C:
        return "worker_gate_call_before";
    case 0x00339994:
        return "worker_busy_gate";
    case 0x0033BB30:
        return "worker_gate_call_after";
    case 0x00339C90:
        return "worker_stop";
    case 0x00339D8C:
        return "worker_start";
    case 0x0033C0A0:
        return "packet_loop";
    case 0x00364D20:
        return "destroy_wrapper";
    case 0x003660E8:
        return "destroy_ipc_wrapper";
    case 0x00366100:
        return "destroy_ipc";
    default:
        break;
    }

    if (IsRoomFlowPc(pc)) {
        return "room_flow_range";
    }
    if (IsWorkerControlPc(pc)) {
        return "worker_control_range";
    }
    if (IsPacketLoopPc(pc)) {
        return "packet_loop_range";
    }
    if (IsDestroyWrapperPc(pc)) {
        return "destroy_wrapper_range";
    }
    if (IsNwmWrapperPc(pc)) {
        return "nwm_wrapper_range";
    }
    return "unknown";
}

inline void EnsureStarted(u32 start_pc) {
    if (active.load(std::memory_order_acquire)) {
        return;
    }

    std::scoped_lock lock(ring_mutex);
    if (active.load(std::memory_order_relaxed)) {
        return;
    }

    ring = {};
    next_sequence = 0;
    ring_count = 0;
    trace_start_pc = start_pc;
    active.store(true, std::memory_order_release);
}

inline bool SameState(const Observation& lhs, const Observation& rhs) {
    return lhs.r0_active8 == rhs.r0_active8 && lhs.r0_active32 == rhs.r0_active32 &&
           lhs.room == rhs.room && lhs.room_worker == rhs.room_worker &&
           lhs.room_active8 == rhs.room_active8 &&
           lhs.room_active32 == rhs.room_active32 && lhs.stop_2ed8 == rhs.stop_2ed8 &&
           lhs.stop_2edc == rhs.stop_2edc && lhs.stop_2ee0 == rhs.stop_2ee0;
}

inline void Record(Entry entry) {
    if (!active.load(std::memory_order_acquire) || !IsTargetPc(entry.static_pc)) {
        return;
    }

    std::scoped_lock lock(ring_mutex);
    if (!active.load(std::memory_order_relaxed)) {
        return;
    }

    if (ring_count != 0) {
        Entry& previous = ring[static_cast<std::size_t>((next_sequence - 1) % Capacity)];
        if (previous.static_pc == entry.static_pc && SameState(previous.last, entry.first)) {
            previous.last = entry.first;
            ++previous.hit_count;
            return;
        }
    }

    const u64 sequence = ++next_sequence;
    entry.sequence = sequence;
    entry.last = entry.first;
    ring[static_cast<std::size_t>((sequence - 1) % Capacity)] = entry;
    if (ring_count < Capacity) {
        ++ring_count;
    }
}

inline Snapshot StopAndSnapshot() {
    active.store(false, std::memory_order_release);
    std::scoped_lock lock(ring_mutex);

    Snapshot snapshot;
    snapshot.count = ring_count;
    snapshot.start_pc = trace_start_pc;
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
            const u32 runtime_pc = parent.GetPC();
            const u32 static_pc =
                YW2DestroyTimeoutTrace::NormalizeRuntimePc(runtime_pc);

            if (YW2DestroyTimeoutTrace::IsTargetPc(static_pc)) {
                YW2DestroyTimeoutTrace::EnsureStarted(static_pc);

                YW2DestroyTimeoutTrace::Entry entry;
                entry.core = parent.GetID();
                entry.static_pc = static_pc;
                auto& observation = entry.first;
                observation.ticks = ticks;
                observation.runtime_pc = runtime_pc;
                for (u32 reg = 0; reg <= 14; ++reg) {
                    observation.regs[reg] = parent.GetReg(reg);
                }

                const auto looks_like_guest_pointer = [](u32 address) {
                    return address >= 0x00100000U && address < 0x40000000U;
                };
                const auto read32 = [&](u32 address, u32 fallback) {
                    if (!looks_like_guest_pointer(address)) {
                        return fallback;
                    }
                    return memory.Read32OrNullopt(address).value_or(fallback);
                };
                const auto read8 = [&](u32 address, u32 fallback) {
                    if (!looks_like_guest_pointer(address)) {
                        return fallback;
                    }
                    const u32 aligned = address & ~u32{3};
                    const auto word = memory.Read32OrNullopt(aligned);
                    if (!word) {
                        return fallback;
                    }
                    return (*word >> ((address & 3U) * 8U)) & 0xFFU;
                };

                const u32 r0 = observation.regs[0];
                const u32 r4 = observation.regs[4];
                const u32 sp = observation.regs[13];

                if (YW2DestroyTimeoutTrace::IsWorkerControlPc(static_pc) ||
                    YW2DestroyTimeoutTrace::IsPacketLoopPc(static_pc)) {
                    observation.r0_active8 =
                        read8(r0 + 0x3EEC, YW2DestroyTimeoutTrace::InvalidValue);
                    observation.r0_active32 =
                        read32(r0 + 0x3EEC, YW2DestroyTimeoutTrace::InvalidValue);
                }

                if (YW2DestroyTimeoutTrace::IsRoomFlowPc(static_pc)) {
                    const u32 r4_worker = read32(r4 + 0x2A70, 0);
                    const u32 r0_worker = read32(r0 + 0x2A70, 0);
                    if (looks_like_guest_pointer(r4_worker)) {
                        observation.room = r4;
                        observation.room_worker = r4_worker;
                    } else if (looks_like_guest_pointer(r0_worker)) {
                        observation.room = r0;
                        observation.room_worker = r0_worker;
                    } else if (static_pc >= 0x0033BA00 && looks_like_guest_pointer(r4)) {
                        observation.room = r4;
                    } else if (looks_like_guest_pointer(r0)) {
                        observation.room = r0;
                    }
                } else if (YW2DestroyTimeoutTrace::IsDestroyWrapperPc(static_pc) &&
                           looks_like_guest_pointer(r0)) {
                    observation.room = r0;
                }

                if (observation.room != 0 && observation.room_worker == 0) {
                    observation.room_worker = read32(observation.room + 0x2A70, 0);
                }
                if (looks_like_guest_pointer(observation.room_worker)) {
                    observation.room_active8 = read8(
                        observation.room_worker + 0x3EEC,
                        YW2DestroyTimeoutTrace::InvalidValue);
                    observation.room_active32 = read32(
                        observation.room_worker + 0x3EEC,
                        YW2DestroyTimeoutTrace::InvalidValue);
                }

                if (YW2DestroyTimeoutTrace::IsWorkerStopPc(static_pc) &&
                    looks_like_guest_pointer(r0)) {
                    observation.stop_2ed8 =
                        read32(r0 + 0x2ED8, YW2DestroyTimeoutTrace::InvalidValue);
                    observation.stop_2edc =
                        read32(r0 + 0x2EDC, YW2DestroyTimeoutTrace::InvalidValue);
                    observation.stop_2ee0 =
                        read32(r0 + 0x2EE0, YW2DestroyTimeoutTrace::InvalidValue);
                }

                for (u32 index = 0; index < observation.stack_words.size(); ++index) {
                    observation.stack_words[index] = read32(
                        sp + index * sizeof(u32),
                        YW2DestroyTimeoutTrace::InvalidValue);
                }

                YW2DestroyTimeoutTrace::Record(entry);
            }
        }
'''
arm_text, add_ticks_count = add_ticks_pattern.subn(
    lambda match: match.group(1) + add_ticks_insert,
    arm_text,
    count=1,
)
if add_ticks_count != 1:
    raise RuntimeError(
        f"YW2 worker timeout range trace expected one AddTicks marker, found {add_ticks_count}"
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
    lambda match: match.group(1)
    + "    Core::YW2DestroyTimeoutTrace::EnsureStarted(0x003660D0);\n",
    nwm_text,
    count=1,
)
if begin_count != 1:
    raise RuntimeError(
        f"YW2 worker timeout range trace expected one BeginHostingNetwork marker, found {begin_count}"
    )

destroy_pattern = re.compile(
    r"(void NWM_UDS::DestroyNetwork\(Kernel::HLERequestContext& ctx\) \{\n)"
)
destroy_insert = '''    const auto history = Core::YW2DestroyTimeoutTrace::StopAndSnapshot();
    if (history.count != 0) {
        auto& cpu = system.GetRunningCore();
        const u32 runtime_pc = cpu.GetPC();
        const u32 static_pc =
            Core::YW2DestroyTimeoutTrace::NormalizeRuntimePc(runtime_pc);
        LOG_WARNING(Service_NWM,
                    "(YW2 WORKER TRACE) history_count={} capacity={} start_pc=0x{:08X} "
                    "runtime_pc=0x{:08X} static_pc=0x{:08X} "
                    "r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X} "
                    "r4=0x{:08X} r5=0x{:08X} r6=0x{:08X} r7=0x{:08X} "
                    "r8=0x{:08X} r9=0x{:08X} r10=0x{:08X} r11=0x{:08X} "
                    "r12=0x{:08X} sp=0x{:08X} lr=0x{:08X}",
                    history.count, Core::YW2DestroyTimeoutTrace::Capacity,
                    history.start_pc, runtime_pc, static_pc,
                    cpu.GetReg(0), cpu.GetReg(1), cpu.GetReg(2), cpu.GetReg(3),
                    cpu.GetReg(4), cpu.GetReg(5), cpu.GetReg(6), cpu.GetReg(7),
                    cpu.GetReg(8), cpu.GetReg(9), cpu.GetReg(10), cpu.GetReg(11),
                    cpu.GetReg(12), cpu.GetReg(13), cpu.GetReg(14));
        for (std::size_t index = 0; index < history.count; ++index) {
            const auto& entry = history.entries[index];
            const auto& first = entry.first;
            const auto& last = entry.last;
            LOG_WARNING(Service_NWM,
                        "(YW2 WORKER HISTORY) index={} seq={} hits={} core={} target={} "
                        "static_pc=0x{:08X} first_ticks={} last_ticks={} "
                        "first_runtime_pc=0x{:08X} last_runtime_pc=0x{:08X} "
                        "first_r0_active8=0x{:08X} last_r0_active8=0x{:08X} "
                        "first_r0_active32=0x{:08X} last_r0_active32=0x{:08X} "
                        "first_room=0x{:08X} last_room=0x{:08X} "
                        "first_worker=0x{:08X} last_worker=0x{:08X} "
                        "first_room_active8=0x{:08X} last_room_active8=0x{:08X} "
                        "first_room_active32=0x{:08X} last_room_active32=0x{:08X} "
                        "first_stop=0x{:08X},0x{:08X},0x{:08X} "
                        "last_stop=0x{:08X},0x{:08X},0x{:08X}",
                        index, entry.sequence, entry.hit_count, entry.core,
                        Core::YW2DestroyTimeoutTrace::TargetName(entry.static_pc),
                        entry.static_pc, first.ticks, last.ticks,
                        first.runtime_pc, last.runtime_pc,
                        first.r0_active8, last.r0_active8,
                        first.r0_active32, last.r0_active32,
                        first.room, last.room, first.room_worker, last.room_worker,
                        first.room_active8, last.room_active8,
                        first.room_active32, last.room_active32,
                        first.stop_2ed8, first.stop_2edc, first.stop_2ee0,
                        last.stop_2ed8, last.stop_2edc, last.stop_2ee0);
            LOG_WARNING(Service_NWM,
                        "(YW2 WORKER HISTORY) FIRST index={} "
                        "r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X} "
                        "r4=0x{:08X} r5=0x{:08X} r6=0x{:08X} r7=0x{:08X} "
                        "r8=0x{:08X} r9=0x{:08X} r10=0x{:08X} r11=0x{:08X} "
                        "r12=0x{:08X} sp=0x{:08X} lr=0x{:08X} "
                        "stack=0x{:08X},0x{:08X},0x{:08X},0x{:08X},"
                        "0x{:08X},0x{:08X},0x{:08X},0x{:08X}",
                        index, first.regs[0], first.regs[1], first.regs[2],
                        first.regs[3], first.regs[4], first.regs[5],
                        first.regs[6], first.regs[7], first.regs[8],
                        first.regs[9], first.regs[10], first.regs[11],
                        first.regs[12], first.regs[13], first.regs[14],
                        first.stack_words[0], first.stack_words[1],
                        first.stack_words[2], first.stack_words[3],
                        first.stack_words[4], first.stack_words[5],
                        first.stack_words[6], first.stack_words[7]);
            LOG_WARNING(Service_NWM,
                        "(YW2 WORKER HISTORY) LAST index={} "
                        "r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X} "
                        "r4=0x{:08X} r5=0x{:08X} r6=0x{:08X} r7=0x{:08X} "
                        "r8=0x{:08X} r9=0x{:08X} r10=0x{:08X} r11=0x{:08X} "
                        "r12=0x{:08X} sp=0x{:08X} lr=0x{:08X} "
                        "stack=0x{:08X},0x{:08X},0x{:08X},0x{:08X},"
                        "0x{:08X},0x{:08X},0x{:08X},0x{:08X}",
                        index, last.regs[0], last.regs[1], last.regs[2],
                        last.regs[3], last.regs[4], last.regs[5],
                        last.regs[6], last.regs[7], last.regs[8],
                        last.regs[9], last.regs[10], last.regs[11],
                        last.regs[12], last.regs[13], last.regs[14],
                        last.stack_words[0], last.stack_words[1],
                        last.stack_words[2], last.stack_words[3],
                        last.stack_words[4], last.stack_words[5],
                        last.stack_words[6], last.stack_words[7]);
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
        f"YW2 worker timeout range trace expected one DestroyNetwork declaration, found {destroy_count}"
    )

ARM_PATH.write_text(arm_text)
NWM_PATH.write_text(nwm_text)
COMM_HEADER_PATH.write_text(comm_header_text)
print("Applied YW2 freed-callback cleanup and compressed worker timeout range trace")
