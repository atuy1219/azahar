from pathlib import Path


ARM_PATH = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
SVC_PATH = Path("src/core/hle/kernel/svc.cpp")
HEADER_PATH = Path("src/core/yw2_comm_write_watch.h")

arm_text = ARM_PATH.read_text()
svc_text = SVC_PATH.read_text()


def patch_arm(old: str, new: str, label: str) -> None:
    global arm_text
    if old not in arm_text:
        raise RuntimeError(f"YW2 dynamic communication write trace ARM marker not found: {label}")
    arm_text = arm_text.replace(old, new, 1)


def patch_svc(old: str, new: str, label: str) -> None:
    global svc_text
    if old not in svc_text:
        raise RuntimeError(f"YW2 dynamic communication write trace SVC marker not found: {label}")
    svc_text = svc_text.replace(old, new, 1)


HEADER_PATH.write_text(
    '''#pragma once

#include <atomic>
#include "common/common_types.h"

namespace Core::YW2CommWriteWatch {

inline std::atomic<u32> callback_arg{};

inline void SetCallbackArg(u32 value) {
    callback_arg.store(value, std::memory_order_release);
}

inline u32 GetCallbackArg() {
    return callback_arg.load(std::memory_order_acquire);
}

} // namespace Core::YW2CommWriteWatch
'''
)

if "(YW2 COMM WRITE) registered" not in svc_text:
    patch_svc(
        '#include "core/core_timing.h"\n',
        '#include "core/core_timing.h"\n#include "core/yw2_comm_write_watch.h"\n',
        "SVC shared watch include",
    )

    patch_svc(
        '''            const u32 callback_arg = target_at_4 ? yw2_read32(arg + 0x08)
                                                 : yw2_read32(arg + 0x0C);
            LOG_WARNING(Kernel_SVC,
''',
        '''            const u32 callback_arg = target_at_4 ? yw2_read32(arg + 0x08)
                                                 : yw2_read32(arg + 0x0C);
            Core::YW2CommWriteWatch::SetCallbackArg(callback_arg);
            LOG_WARNING(Kernel_SVC,
                        "(YW2 COMM WRITE) registered callback_arg=0x{:08X} "
                        "flag9=0x{:08X} flag10=0x{:08X}",
                        callback_arg, callback_arg + 9, callback_arg + 10);
            LOG_WARNING(Kernel_SVC,
''',
        "CreateThread dynamic callback registration",
    )

if "(YW2 COMM WRITE) kind=" not in arm_text:
    patch_arm(
        '#include "core/core.h"\n',
        '#include "core/core.h"\n#include "core/yw2_comm_write_watch.h"\n',
        "ARM shared watch include",
    )

    patch_arm(
        '''} // namespace

class DynarmicUserCallbacks final : public Dynarmic::A32::UserCallbacks {
''',
        r'''bool YW2CommDynamicFlagOverlaps(u32 address, u32 size) {
    if (!YW2CommTraceEnabled() || size == 0) {
        return false;
    }
    const u32 callback_arg = YW2CommWriteWatch::GetCallbackArg();
    if (callback_arg == 0) {
        return false;
    }
    const u64 begin = address;
    const u64 end = begin + size;
    const u64 flag9 = static_cast<u64>(callback_arg) + 9;
    const u64 flag10 = static_cast<u64>(callback_arg) + 10;
    return (begin <= flag9 && flag9 < end) || (begin <= flag10 && flag10 < end);
}

bool YW2CommDynamicShouldLog(u32 address, u64 value, u32 size) {
    return YW2CommDynamicFlagOverlaps(address, size) ||
           (YW2CommTraceEnabled() && size == sizeof(u32) &&
            static_cast<u32>(value) == 0x80000013U);
}

void YW2LogDynamicCommWrite(ARM_Dynarmic& cpu, Memory::MemorySystem& memory,
                            u32 address, u64 value, u32 size, u32 old_word,
                            u8 old9, u8 old10, bool exclusive) {
    const u32 callback_arg = YW2CommWriteWatch::GetCallbackArg();
    const bool flag_write = YW2CommDynamicFlagOverlaps(address, size);
    const bool result_write = size == sizeof(u32) && static_cast<u32>(value) == 0x80000013U;
    const u32 aligned = address & ~u32{3};
    const u32 new_word = YW2Read32Or(memory, aligned, 0xFFFFFFFFU);
    const u8 new9 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 9) : 0xFF;
    const u8 new10 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 10) : 0xFF;
    const char* kind = flag_write && result_write ? "flags+result" :
                       flag_write ? "flags" : "result";
    const u32 sp = cpu.GetReg(13);
    LOG_WARNING(Core_ARM11,
                "(YW2 COMM WRITE) kind={} callback_arg=0x{:08X} address=0x{:08X} "
                "size={} value=0x{:016X} aligned=0x{:08X} old_word=0x{:08X} "
                "new_word=0x{:08X} old9={} new9={} old10={} new10={} exclusive={} "
                "pc=0x{:08X} lr=0x{:08X} r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} "
                "r3=0x{:08X} r4=0x{:08X} r5=0x{:08X} r6=0x{:08X} r7=0x{:08X} "
                "r8=0x{:08X} r9=0x{:08X} r10=0x{:08X} r11=0x{:08X} "
                "r12=0x{:08X} sp=0x{:08X}",
                kind, callback_arg, address, size, value, aligned, old_word, new_word,
                old9, new9, old10, new10, exclusive, cpu.GetPC(), cpu.GetReg(14),
                cpu.GetReg(0), cpu.GetReg(1), cpu.GetReg(2), cpu.GetReg(3), cpu.GetReg(4),
                cpu.GetReg(5), cpu.GetReg(6), cpu.GetReg(7), cpu.GetReg(8), cpu.GetReg(9),
                cpu.GetReg(10), cpu.GetReg(11), cpu.GetReg(12), sp);
    if (callback_arg != 0) {
        LOG_WARNING(Core_ARM11,
                    "(YW2 COMM WRITE MEMORY) callback_arg=0x{:08X} around={} stack={}",
                    callback_arg, YW2HexDump(memory, callback_arg - 0x20, 64),
                    YW2HexDump(memory, sp, 64));
    }
}

} // namespace

class DynarmicUserCallbacks final : public Dynarmic::A32::UserCallbacks {
''',
        "dynamic communication write helpers",
    )

    patch_arm(
        '''    void MemoryWrite8(VAddr vaddr, std::uint8_t value) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) : 0;
        memory.Write8(vaddr, value);
        if (watch) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, false);
        }
    }
    void MemoryWrite16(VAddr vaddr, std::uint16_t value) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) : 0;
        memory.Write16(vaddr, value);
        if (watch) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, false);
        }
    }
    void MemoryWrite32(VAddr vaddr, std::uint32_t value) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) : 0;
        memory.Write32(vaddr, value);
        if (watch) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, false);
        }
    }
    void MemoryWrite64(VAddr vaddr, std::uint64_t value) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) : 0;
        memory.Write64(vaddr, value);
        if (watch) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, false);
        }
    }
''',
        '''    void MemoryWrite8(VAddr vaddr, std::uint8_t value) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const bool comm_watch = YW2CommDynamicShouldLog(vaddr, value, sizeof(value));
        const u32 aligned = vaddr & ~u32{3};
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) :
                            comm_watch ? YW2Read32Or(memory, aligned, 0xFFFFFFFFU) : 0;
        const u32 callback_arg = YW2CommWriteWatch::GetCallbackArg();
        const u8 old9 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 9) : 0xFF;
        const u8 old10 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 10) : 0xFF;
        memory.Write8(vaddr, value);
        if (watch) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, false);
        }
        if (comm_watch) {
            YW2LogDynamicCommWrite(parent, memory, vaddr, value, sizeof(value), old_word,
                                   old9, old10, false);
        }
    }
    void MemoryWrite16(VAddr vaddr, std::uint16_t value) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const bool comm_watch = YW2CommDynamicShouldLog(vaddr, value, sizeof(value));
        const u32 aligned = vaddr & ~u32{3};
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) :
                            comm_watch ? YW2Read32Or(memory, aligned, 0xFFFFFFFFU) : 0;
        const u32 callback_arg = YW2CommWriteWatch::GetCallbackArg();
        const u8 old9 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 9) : 0xFF;
        const u8 old10 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 10) : 0xFF;
        memory.Write16(vaddr, value);
        if (watch) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, false);
        }
        if (comm_watch) {
            YW2LogDynamicCommWrite(parent, memory, vaddr, value, sizeof(value), old_word,
                                   old9, old10, false);
        }
    }
    void MemoryWrite32(VAddr vaddr, std::uint32_t value) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const bool comm_watch = YW2CommDynamicShouldLog(vaddr, value, sizeof(value));
        const u32 aligned = vaddr & ~u32{3};
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) :
                            comm_watch ? YW2Read32Or(memory, aligned, 0xFFFFFFFFU) : 0;
        const u32 callback_arg = YW2CommWriteWatch::GetCallbackArg();
        const u8 old9 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 9) : 0xFF;
        const u8 old10 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 10) : 0xFF;
        memory.Write32(vaddr, value);
        if (watch) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, false);
        }
        if (comm_watch) {
            YW2LogDynamicCommWrite(parent, memory, vaddr, value, sizeof(value), old_word,
                                   old9, old10, false);
        }
    }
    void MemoryWrite64(VAddr vaddr, std::uint64_t value) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const bool comm_watch = YW2CommDynamicShouldLog(vaddr, value, sizeof(value));
        const u32 aligned = vaddr & ~u32{3};
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) :
                            comm_watch ? YW2Read32Or(memory, aligned, 0xFFFFFFFFU) : 0;
        const u32 callback_arg = YW2CommWriteWatch::GetCallbackArg();
        const u8 old9 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 9) : 0xFF;
        const u8 old10 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 10) : 0xFF;
        memory.Write64(vaddr, value);
        if (watch) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, false);
        }
        if (comm_watch) {
            YW2LogDynamicCommWrite(parent, memory, vaddr, value, sizeof(value), old_word,
                                   old9, old10, false);
        }
    }
''',
        "normal memory write callbacks",
    )

    patch_arm(
        '''    bool MemoryWriteExclusive8(u32 vaddr, u8 value, u8 expected) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) : 0;
        const bool success = memory.WriteExclusive8(vaddr, value, expected);
        if (watch && success) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, true);
        }
        return success;
    }
    bool MemoryWriteExclusive16(u32 vaddr, u16 value, u16 expected) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) : 0;
        const bool success = memory.WriteExclusive16(vaddr, value, expected);
        if (watch && success) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, true);
        }
        return success;
    }
    bool MemoryWriteExclusive32(u32 vaddr, u32 value, u32 expected) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) : 0;
        const bool success = memory.WriteExclusive32(vaddr, value, expected);
        if (watch && success) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, true);
        }
        return success;
    }
    bool MemoryWriteExclusive64(u32 vaddr, u64 value, u64 expected) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) : 0;
        const bool success = memory.WriteExclusive64(vaddr, value, expected);
        if (watch && success) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, true);
        }
        return success;
    }
''',
        '''    bool MemoryWriteExclusive8(u32 vaddr, u8 value, u8 expected) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const bool comm_watch = YW2CommDynamicShouldLog(vaddr, value, sizeof(value));
        const u32 aligned = vaddr & ~u32{3};
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) :
                            comm_watch ? YW2Read32Or(memory, aligned, 0xFFFFFFFFU) : 0;
        const u32 callback_arg = YW2CommWriteWatch::GetCallbackArg();
        const u8 old9 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 9) : 0xFF;
        const u8 old10 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 10) : 0xFF;
        const bool success = memory.WriteExclusive8(vaddr, value, expected);
        if (watch && success) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, true);
        }
        if (comm_watch && success) {
            YW2LogDynamicCommWrite(parent, memory, vaddr, value, sizeof(value), old_word,
                                   old9, old10, true);
        }
        return success;
    }
    bool MemoryWriteExclusive16(u32 vaddr, u16 value, u16 expected) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const bool comm_watch = YW2CommDynamicShouldLog(vaddr, value, sizeof(value));
        const u32 aligned = vaddr & ~u32{3};
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) :
                            comm_watch ? YW2Read32Or(memory, aligned, 0xFFFFFFFFU) : 0;
        const u32 callback_arg = YW2CommWriteWatch::GetCallbackArg();
        const u8 old9 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 9) : 0xFF;
        const u8 old10 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 10) : 0xFF;
        const bool success = memory.WriteExclusive16(vaddr, value, expected);
        if (watch && success) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, true);
        }
        if (comm_watch && success) {
            YW2LogDynamicCommWrite(parent, memory, vaddr, value, sizeof(value), old_word,
                                   old9, old10, true);
        }
        return success;
    }
    bool MemoryWriteExclusive32(u32 vaddr, u32 value, u32 expected) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const bool comm_watch = YW2CommDynamicShouldLog(vaddr, value, sizeof(value));
        const u32 aligned = vaddr & ~u32{3};
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) :
                            comm_watch ? YW2Read32Or(memory, aligned, 0xFFFFFFFFU) : 0;
        const u32 callback_arg = YW2CommWriteWatch::GetCallbackArg();
        const u8 old9 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 9) : 0xFF;
        const u8 old10 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 10) : 0xFF;
        const bool success = memory.WriteExclusive32(vaddr, value, expected);
        if (watch && success) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, true);
        }
        if (comm_watch && success) {
            YW2LogDynamicCommWrite(parent, memory, vaddr, value, sizeof(value), old_word,
                                   old9, old10, true);
        }
        return success;
    }
    bool MemoryWriteExclusive64(u32 vaddr, u64 value, u64 expected) override {
        const bool watch = YW2WriteWatchOverlaps(vaddr, sizeof(value));
        const bool comm_watch = YW2CommDynamicShouldLog(vaddr, value, sizeof(value));
        const u32 aligned = vaddr & ~u32{3};
        const u32 old_word = watch ? YW2Read32Or(memory, YW2WriteWatchAddress(), 0xFFFFFFFFU) :
                            comm_watch ? YW2Read32Or(memory, aligned, 0xFFFFFFFFU) : 0;
        const u32 callback_arg = YW2CommWriteWatch::GetCallbackArg();
        const u8 old9 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 9) : 0xFF;
        const u8 old10 = callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 10) : 0xFF;
        const bool success = memory.WriteExclusive64(vaddr, value, expected);
        if (watch && success) {
            YW2LogWriteWatch(parent, memory, vaddr, value, sizeof(value), old_word, true);
        }
        if (comm_watch && success) {
            YW2LogDynamicCommWrite(parent, memory, vaddr, value, sizeof(value), old_word,
                                   old9, old10, true);
        }
        return success;
    }
''',
        "exclusive memory write callbacks",
    )

    patch_arm(
        '''    if (current_page_table && !YW2WriteWatchEnabled()) {
        config.page_table = &current_page_table->GetPointerArray();
    } else if (YW2WriteWatchEnabled()) {
        LOG_WARNING(Core_ARM11,
                    "(YW2 WRITE WATCH) callback memory mode enabled watch=0x{:08X}",
                    YW2WriteWatchAddress());
    }
''',
        '''    const bool yw2_callback_memory_mode =
        YW2WriteWatchEnabled() || YW2CommTraceEnabled();
    if (current_page_table && !yw2_callback_memory_mode) {
        config.page_table = &current_page_table->GetPointerArray();
    } else if (yw2_callback_memory_mode) {
        LOG_WARNING(Core_ARM11,
                    "(YW2 COMM WRITE) callback memory mode enabled fixed_watch={} "
                    "comm_trace={} watch=0x{:08X}",
                    YW2WriteWatchEnabled(), YW2CommTraceEnabled(), YW2WriteWatchAddress());
    }
''',
        "callback memory mode",
    )

ARM_PATH.write_text(arm_text)
SVC_PATH.write_text(svc_text)
print("Applied YW2 dynamic callback flag and result write trace patch")
