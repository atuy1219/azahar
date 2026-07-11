from pathlib import Path
import re

ARM_PATH = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
NWM_PATH = Path("src/core/hle/service/nwm/nwm_uds.cpp")
HEADER_PATH = Path("src/core/yw2_destroy_timeout_trace.h")

arm_text = ARM_PATH.read_text()
nwm_text = NWM_PATH.read_text()

if "YW2DestroyTimeoutTrace::Record" in arm_text:
    print("Skipped YW2 DestroyNetwork timeout history trace: already present")
    raise SystemExit(0)

HEADER_PATH.write_text('#pragma once\n\n#include <array>\n#include <atomic>\n#include <cstddef>\n#include <mutex>\n\n#include "common/common_types.h"\n\nnamespace Core::YW2DestroyTimeoutTrace {\n\ninline constexpr std::size_t Capacity = 64;\n\nstruct Entry {\n    u64 sequence{};\n    u64 ticks{};\n    u32 core{};\n    u32 runtime_pc{};\n    u32 guest_pc{};\n    std::array<u32, 15> regs{};\n};\n\nstruct Snapshot {\n    std::array<Entry, Capacity> entries{};\n    std::size_t count{};\n};\n\ninline std::mutex ring_mutex;\ninline std::array<Entry, Capacity> ring{};\ninline u64 next_sequence{};\ninline std::size_t ring_count{};\ninline std::atomic<bool> active{false};\n\ninline u32 NormalizeGuestPc(u32 runtime_pc) {\n    const u32 normalized = runtime_pc & ~u32{1};\n    if (normalized >= 0x00364000 && normalized < 0x00367000) {\n        return normalized - 0x00050000;\n    }\n    return normalized;\n}\n\ninline bool IsTargetPc(u32 guest_pc) {\n    return guest_pc >= 0x00314000 && guest_pc < 0x00317000;\n}\n\ninline void Start() {\n    std::scoped_lock lock(ring_mutex);\n    ring = {};\n    next_sequence = 0;\n    ring_count = 0;\n    active.store(true, std::memory_order_release);\n}\n\ninline void Record(u32 core, u64 ticks, u32 runtime_pc, const std::array<u32, 15>& regs) {\n    if (!active.load(std::memory_order_acquire)) {\n        return;\n    }\n\n    const u32 guest_pc = NormalizeGuestPc(runtime_pc);\n    if (!IsTargetPc(guest_pc)) {\n        return;\n    }\n\n    std::scoped_lock lock(ring_mutex);\n    if (!active.load(std::memory_order_relaxed)) {\n        return;\n    }\n\n    const u64 sequence = ++next_sequence;\n    Entry& entry = ring[static_cast<std::size_t>((sequence - 1) % Capacity)];\n    entry.sequence = sequence;\n    entry.ticks = ticks;\n    entry.core = core;\n    entry.runtime_pc = runtime_pc;\n    entry.guest_pc = guest_pc;\n    entry.regs = regs;\n    if (ring_count < Capacity) {\n        ++ring_count;\n    }\n}\n\ninline Snapshot StopAndSnapshot() {\n    active.store(false, std::memory_order_release);\n    std::scoped_lock lock(ring_mutex);\n\n    Snapshot snapshot;\n    snapshot.count = ring_count;\n    if (ring_count == 0) {\n        return snapshot;\n    }\n\n    const std::size_t first =\n        static_cast<std::size_t>((next_sequence - ring_count) % Capacity);\n    for (std::size_t index = 0; index < ring_count; ++index) {\n        snapshot.entries[index] = ring[(first + index) % Capacity];\n    }\n    return snapshot;\n}\n\n} // namespace Core::YW2DestroyTimeoutTrace\n')

arm_include = '#include "core/core.h"\n'
if arm_include not in arm_text:
    raise RuntimeError("YW2 DestroyNetwork trace: ARM include marker not found")
arm_text = arm_text.replace(arm_include, arm_include + '#include "core/yw2_destroy_timeout_trace.h"\n', 1)

add_ticks_pattern = re.compile(r"(    void AddTicks\(std::uint64_t ticks\) override \{\n)")
add_ticks_insert = '        if (YW2CommExecTraceEnabled()) [[unlikely]] {\n            std::array<u32, 15> regs{};\n            for (u32 reg = 0; reg <= 14; ++reg) {\n                regs[reg] = parent.GetReg(reg);\n            }\n            YW2DestroyTimeoutTrace::Record(parent.GetID(), ticks, parent.GetPC(), regs);\n        }\n'
arm_text, add_ticks_count = add_ticks_pattern.subn(lambda match: match.group(1) + add_ticks_insert, arm_text, count=1)
if add_ticks_count != 1:
    raise RuntimeError(f"YW2 DestroyNetwork trace: expected one AddTicks marker, found {add_ticks_count}")

nwm_include = '#include "core/memory.h"\n'
if nwm_include not in nwm_text:
    raise RuntimeError("YW2 DestroyNetwork trace: NWM include marker not found")
nwm_text = nwm_text.replace(nwm_include, nwm_include + '#include "core/yw2_destroy_timeout_trace.h"\n', 1)

begin_pattern = re.compile(r"(Result NWM_UDS::BeginHostingNetwork\(std::span<const u8> network_info_buffer,\n\s+std::vector<u8> passphrase\) \{\n)")
nwm_text, begin_count = begin_pattern.subn(lambda match: match.group(1) + '    Core::YW2DestroyTimeoutTrace::Start();\n', nwm_text, count=1)
if begin_count != 1:
    raise RuntimeError(f"YW2 DestroyNetwork trace: expected one BeginHostingNetwork marker, found {begin_count}")

destroy_anchor = 'void NWM_UDS::DestroyNetwork(Kernel::HLERequestContext& ctx) {\n    IPC::RequestParser rp(ctx);\n'
destroy_replacement = 'void NWM_UDS::DestroyNetwork(Kernel::HLERequestContext& ctx) {\n    const auto history = Core::YW2DestroyTimeoutTrace::StopAndSnapshot();\n    if (history.count != 0) {\n        auto& cpu = system.GetRunningCore();\n        const u32 runtime_pc = cpu.GetPC();\n        const u32 guest_pc = Core::YW2DestroyTimeoutTrace::NormalizeGuestPc(runtime_pc);\n        LOG_WARNING(Service_NWM,\n                    "(YW2 DESTROY TRACE) history_count={} runtime_pc=0x{:08X} "\n                    "guest_pc=0x{:08X} r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} "\n                    "r3=0x{:08X} r4=0x{:08X} r5=0x{:08X} r6=0x{:08X} "\n                    "r7=0x{:08X} r8=0x{:08X} r9=0x{:08X} r10=0x{:08X} "\n                    "r11=0x{:08X} r12=0x{:08X} sp=0x{:08X} lr=0x{:08X}",\n                    history.count, runtime_pc, guest_pc, cpu.GetReg(0), cpu.GetReg(1),\n                    cpu.GetReg(2), cpu.GetReg(3), cpu.GetReg(4), cpu.GetReg(5),\n                    cpu.GetReg(6), cpu.GetReg(7), cpu.GetReg(8), cpu.GetReg(9),\n                    cpu.GetReg(10), cpu.GetReg(11), cpu.GetReg(12), cpu.GetReg(13),\n                    cpu.GetReg(14));\n        for (std::size_t index = 0; index < history.count; ++index) {\n            const auto& entry = history.entries[index];\n            LOG_WARNING(Service_NWM,\n                        "(YW2 DESTROY HISTORY) index={} seq={} ticks={} core={} "\n                        "runtime_pc=0x{:08X} guest_pc=0x{:08X} "\n                        "r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X} "\n                        "r4=0x{:08X} r5=0x{:08X} r6=0x{:08X} r7=0x{:08X} "\n                        "r8=0x{:08X} r9=0x{:08X} r10=0x{:08X} r11=0x{:08X} "\n                        "r12=0x{:08X} sp=0x{:08X} lr=0x{:08X}",\n                        index, entry.sequence, entry.ticks, entry.core, entry.runtime_pc,\n                        entry.guest_pc, entry.regs[0], entry.regs[1], entry.regs[2],\n                        entry.regs[3], entry.regs[4], entry.regs[5], entry.regs[6],\n                        entry.regs[7], entry.regs[8], entry.regs[9], entry.regs[10],\n                        entry.regs[11], entry.regs[12], entry.regs[13], entry.regs[14]);\n        }\n    }\n\n    IPC::RequestParser rp(ctx);\n'
if destroy_anchor not in nwm_text:
    raise RuntimeError("YW2 DestroyNetwork trace: DestroyNetwork marker not found")
nwm_text = nwm_text.replace(destroy_anchor, destroy_replacement, 1)

ARM_PATH.write_text(arm_text)
NWM_PATH.write_text(nwm_text)
print("Applied YW2 DestroyNetwork pre-timeout PC ring-buffer trace")
