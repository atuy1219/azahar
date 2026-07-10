from pathlib import Path

PATH = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
text = PATH.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 guest write watch marker not found: {label}")
    text = text.replace(old, new, 1)


if "debug.azahar.yw2_write_watch" not in text:
    patch_once(
        '''#include <cstring>
#include <string>
''',
        '''#include <cstdlib>
#include <cstring>
#include <string>
''',
        "cstdlib include",
    )

    patch_once(
        '''} // namespace

class DynarmicUserCallbacks final : public Dynarmic::A32::UserCallbacks {
''',
        r'''bool YW2WriteWatchEnabled() {
#ifdef ANDROID
    char value[PROP_VALUE_MAX] = {};
    if (__system_property_get("debug.azahar.yw2_write_watch", value) <= 0) {
        return false;
    }
    return std::strcmp(value, "0") != 0 && std::strcmp(value, "false") != 0 &&
           std::strcmp(value, "off") != 0;
#else
    return false;
#endif
}

u32 YW2WriteWatchAddress() {
#ifdef ANDROID
    char value[PROP_VALUE_MAX] = {};
    if (__system_property_get("debug.azahar.yw2_write_watch_addr", value) > 0) {
        char* end = nullptr;
        const unsigned long parsed = std::strtoul(value, &end, 0);
        if (end != value && *end == '\0' && parsed <= 0xFFFFFFFFUL) {
            return static_cast<u32>(parsed);
        }
    }
#endif
    return 0x088026A0;
}

bool YW2WriteWatchOverlaps(u32 address, u32 size) {
    if (!YW2WriteWatchEnabled() || size == 0) {
        return false;
    }
    const u32 watch = YW2WriteWatchAddress();
    const u64 begin = address;
    const u64 end = begin + size;
    return begin <= watch && static_cast<u64>(watch) < end;
}

void YW2LogWriteWatch(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u32 address, u64 value,
                      u32 size, u32 old_word, bool exclusive) {
    const u32 watch = YW2WriteWatchAddress();
    const u32 new_word = YW2Read32Or(memory, watch, 0xFFFFFFFFU);
    const u32 sp = cpu.GetReg(13);
    LOG_WARNING(Core_ARM11,
                "(YW2 WRITE WATCH) watch=0x{:08X} address=0x{:08X} size={} value=0x{:016X} "
                "old_word=0x{:08X} new_word=0x{:08X} exclusive={} pc=0x{:08X} lr=0x{:08X} "
                "r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X} r4=0x{:08X} "
                "r5=0x{:08X} r6=0x{:08X} r7=0x{:08X} r8=0x{:08X} r9=0x{:08X} "
                "r10=0x{:08X} r11=0x{:08X} r12=0x{:08X} sp=0x{:08X}",
                watch, address, size, value, old_word, new_word, exclusive, cpu.GetPC(),
                cpu.GetReg(14), cpu.GetReg(0), cpu.GetReg(1), cpu.GetReg(2), cpu.GetReg(3),
                cpu.GetReg(4), cpu.GetReg(5), cpu.GetReg(6), cpu.GetReg(7), cpu.GetReg(8),
                cpu.GetReg(9), cpu.GetReg(10), cpu.GetReg(11), cpu.GetReg(12), sp);
    LOG_WARNING(Core_ARM11,
                "(YW2 WRITE WATCH MEMORY) watch=0x{:08X} around={} stack={}", watch,
                YW2HexDump(memory, watch - 0x20, 64), YW2HexDump(memory, sp, 64));
}

} // namespace

class DynarmicUserCallbacks final : public Dynarmic::A32::UserCallbacks {
''',
        "write watch helpers",
    )

    patch_once(
        '''    void MemoryWrite8(VAddr vaddr, std::uint8_t value) override {
        memory.Write8(vaddr, value);
    }
    void MemoryWrite16(VAddr vaddr, std::uint16_t value) override {
        memory.Write16(vaddr, value);
    }
    void MemoryWrite32(VAddr vaddr, std::uint32_t value) override {
        memory.Write32(vaddr, value);
    }
    void MemoryWrite64(VAddr vaddr, std::uint64_t value) override {
        memory.Write64(vaddr, value);
    }

    bool MemoryWriteExclusive8(u32 vaddr, u8 value, u8 expected) override {
        return memory.WriteExclusive8(vaddr, value, expected);
    }
    bool MemoryWriteExclusive16(u32 vaddr, u16 value, u16 expected) override {
        return memory.WriteExclusive16(vaddr, value, expected);
    }
    bool MemoryWriteExclusive32(u32 vaddr, u32 value, u32 expected) override {
        return memory.WriteExclusive32(vaddr, value, expected);
    }
    bool MemoryWriteExclusive64(u32 vaddr, u64 value, u64 expected) override {
        return memory.WriteExclusive64(vaddr, value, expected);
    }
''',
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

    bool MemoryWriteExclusive8(u32 vaddr, u8 value, u8 expected) override {
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
        "memory write callbacks",
    )

    patch_once(
        '''    if (current_page_table) {
        config.page_table = &current_page_table->GetPointerArray();
    }
''',
        '''    if (current_page_table && !YW2WriteWatchEnabled()) {
        config.page_table = &current_page_table->GetPointerArray();
    } else if (YW2WriteWatchEnabled()) {
        LOG_WARNING(Core_ARM11,
                    "(YW2 WRITE WATCH) callback memory mode enabled watch=0x{:08X}",
                    YW2WriteWatchAddress());
    }
''',
        "disable direct page table writes while watching",
    )

    PATH.write_text(text)
    print("Applied YW2 guest memory write watch patch")
else:
    print("Skipped YW2 guest memory write watch patch: already present")
