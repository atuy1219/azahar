from pathlib import Path

path = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
text = path.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 ARM PC trace patch marker not found: {label}")
    text = text.replace(old, new, 1)


if "debug.azahar.yw2_arm_trace" not in text:
    patch_once(
        "#include <csignal>\n#include <cstring>\n",
        "#include <atomic>\n"
        "#include <csignal>\n"
        "#include <cstring>\n"
        "#include <string>\n"
        "#ifdef ANDROID\n"
        "#include <sys/system_properties.h>\n"
        "#endif\n",
        "YW2 ARM trace includes",
    )

    patch_once(
        "#include \"common/assert.h\"\n",
        "#include \"common/assert.h\"\n"
        "#include \"common/logging/log.h\"\n",
        "YW2 ARM trace logging include",
    )

    patch_once(
        "namespace Core {\n\n",
        r'''namespace Core {

namespace {

bool YW2ArmTraceEnabled() {
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

bool YW2Read8(Memory::MemorySystem& memory, u32 addr, u8& value) {
    if (addr == 0) {
        return false;
    }
    const u8* ptr = memory.GetPointer(addr);
    if (ptr == nullptr) {
        return false;
    }
    value = *ptr;
    return true;
}

bool YW2Read32(Memory::MemorySystem& memory, u32 addr, u32& value) {
    u8 b0 = 0;
    u8 b1 = 0;
    u8 b2 = 0;
    u8 b3 = 0;
    if (!YW2Read8(memory, addr, b0) || !YW2Read8(memory, addr + 1, b1) ||
        !YW2Read8(memory, addr + 2, b2) || !YW2Read8(memory, addr + 3, b3)) {
        value = 0;
        return false;
    }
    value = static_cast<u32>(b0) | (static_cast<u32>(b1) << 8) |
            (static_cast<u32>(b2) << 16) | (static_cast<u32>(b3) << 24);
    return true;
}

u8 YW2Read8Or(Memory::MemorySystem& memory, u32 addr, u8 fallback = 0xff) {
    u8 value = fallback;
    YW2Read8(memory, addr, value);
    return value;
}

u32 YW2Read32Or(Memory::MemorySystem& memory, u32 addr, u32 fallback = 0) {
    u32 value = fallback;
    YW2Read32(memory, addr, value);
    return value;
}

void YW2AppendHexByte(std::string& out, u8 value) {
    static constexpr char hex[] = "0123456789ABCDEF";
    out.push_back(hex[value >> 4]);
    out.push_back(hex[value & 0x0f]);
}

std::string YW2HexDump(Memory::MemorySystem& memory, u32 addr, u32 length) {
    std::string out;
    const u32 dump_len = length > 32 ? 32 : length;
    for (u32 i = 0; i < dump_len; ++i) {
        if (i != 0) {
            out.push_back(' ');
        }
        u8 value = 0;
        if (YW2Read8(memory, addr + i, value)) {
            YW2AppendHexByte(out, value);
        } else {
            out += "??";
        }
    }
    return out;
}

std::string YW2ByteList(Memory::MemorySystem& memory, u32 addr, u32 count) {
    std::string out;
    const u32 dump_count = count > 12 ? 12 : count;
    for (u32 i = 0; i < dump_count; ++i) {
        if (i != 0) {
            out.push_back(' ');
        }
        u8 value = 0;
        if (YW2Read8(memory, addr + i, value)) {
            YW2AppendHexByte(out, value);
        } else {
            out += "??";
        }
    }
    if (count > dump_count) {
        out += " ...";
    }
    return out;
}

const char* YW2TargetName(u32 target) {
    switch (target) {
    case 0x0034661c:
        return "protocol_pump";
    case 0x00343d94:
        return "packet_dispatch";
    case 0x0034ef84:
        return "process_update_dispatch";
    case 0x0034d4f8:
        return "session_update_parse";
    case 0x0034e9d4:
        return "session_update_parse_alt";
    case 0x0034c328:
        return "process_update_main";
    case 0x0034d058:
        return "update_session_counter";
    case 0x0034eee8:
        return "process_update_reset";
    default:
        return "unknown";
    }
}

int YW2TargetIndex(u32 target) {
    switch (target) {
    case 0x0034661c:
        return 0;
    case 0x00343d94:
        return 1;
    case 0x0034ef84:
        return 2;
    case 0x0034d4f8:
        return 3;
    case 0x0034e9d4:
        return 4;
    case 0x0034c328:
        return 5;
    case 0x0034d058:
        return 6;
    case 0x0034eee8:
        return 7;
    default:
        return -1;
    }
}

u32 YW2MatchTraceTarget(u32 pc) {
    const u32 normalized = pc & ~u32{1};
    switch (normalized) {
    case 0x0034661c:
    case 0x00343d94:
    case 0x0034ef84:
    case 0x0034d4f8:
    case 0x0034e9d4:
    case 0x0034c328:
    case 0x0034d058:
    case 0x0034eee8:
        return normalized;
    default:
        return 0;
    }
}

void YW2LogPacket(Memory::MemorySystem& memory, const char* label, u32 packet, u32 length) {
    const u8 p0 = YW2Read8Or(memory, packet + 0);
    const u8 p1 = YW2Read8Or(memory, packet + 1);
    const u8 p2 = YW2Read8Or(memory, packet + 2);
    const u32 seq = YW2Read32Or(memory, packet + 4);
    const u8 p8 = YW2Read8Or(memory, packet + 8);
    const u8 p9 = YW2Read8Or(memory, packet + 9);
    const u8 p10 = YW2Read8Or(memory, packet + 10);
    const u8 p11 = YW2Read8Or(memory, packet + 11);
    const u32 dump_len = length == 0 ? 16 : (length > 32 ? 32 : length);
    LOG_WARNING(Core_ARM11,
                "(YW2 PKT) {} packet=0x{:08X} len={} p0=0x{:02X} p1={} p2={} seq_raw=0x{:08X} p8=0x{:02X} p9=0x{:02X} p10=0x{:02X} p11=0x{:02X} is20={} dump={}",
                label, packet, length, p0, p1, p2, seq, p8, p9, p10, p11, p0 == 0x20,
                YW2HexDump(memory, packet, dump_len));
}

void YW2LogJob(Memory::MemorySystem& memory, const char* label, u32 job) {
    const u32 capacity = YW2Read32Or(memory, job + 0x6c);
    const u32 node_ids_ptr = YW2Read32Or(memory, job + 0x74);
    const u32 status_ptr = YW2Read32Or(memory, job + 0x8c);
    const u32 count = YW2Read32Or(memory, job + 0x88);
    const u32 state = YW2Read32Or(memory, job + 0x2c);
    const u32 seq = YW2Read32Or(memory, job + 0xa0);
    const u8 a4 = YW2Read8Or(memory, job + 0xa4, 0);
    const u8 a5 = YW2Read8Or(memory, job + 0xa5, 0);
    const u8 a6 = YW2Read8Or(memory, job + 0xa6, 0);
    const std::string nodes = count <= 12 ? YW2ByteList(memory, node_ids_ptr, count) : "skip";
    const std::string statuses = count <= 12 ? YW2ByteList(memory, status_ptr, count) : "skip";
    LOG_WARNING(Core_ARM11,
                "(YW2 SESSION) {} job=0x{:08X} state=0x{:08X} cap={} count={} seq=0x{:08X} a4={} a5={} a6={} node_ptr=0x{:08X} nodes=[{}] status_ptr=0x{:08X} sts=[{}] frag={:02X} {:02X} {:02X} {:02X} {:02X} {:02X}",
                label, job, state, capacity, count, seq, a4, a5, a6, node_ids_ptr, nodes,
                status_ptr, statuses, YW2Read8Or(memory, job + 0x80), YW2Read8Or(memory, job + 0x81),
                YW2Read8Or(memory, job + 0x82), YW2Read8Or(memory, job + 0x83),
                YW2Read8Or(memory, job + 0x84), YW2Read8Or(memory, job + 0x85));
}

void YW2TraceArmPC(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u32 trace_pc) {
    const u32 target = YW2MatchTraceTarget(trace_pc);
    if (target == 0) {
        return;
    }

    const int index = YW2TargetIndex(target);
    static std::atomic<u64> counters[8]{};
    const u64 hit_count = index >= 0 ? ++counters[index] : 1;

    const u32 r0 = cpu.GetReg(0);
    const u32 r1 = cpu.GetReg(1);
    const u32 r2 = cpu.GetReg(2);
    const u32 r3 = cpu.GetReg(3);
    const u32 lr = cpu.GetReg(14);
    const u32 cpu_pc = cpu.GetPC();

    u8 dispatch_packet0 = 0xff;
    if (target == 0x00343d94) {
        u32 payload = 0;
        if (YW2Read32(memory, r1, payload)) {
            dispatch_packet0 = YW2Read8Or(memory, payload);
        }
    }

    const bool force_log = target == 0x00343d94 && dispatch_packet0 == 0x20;
    if (!force_log && hit_count > 200 && (hit_count % 1000) != 0) {
        return;
    }

    LOG_WARNING(Core_ARM11,
                "(YW2 ARM) translate {} target=0x{:08X} trace_pc=0x{:08X} cpu_pc=0x{:08X} count={} r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X} lr=0x{:08X}",
                YW2TargetName(target), target, trace_pc, cpu_pc, hit_count, r0, r1, r2, r3, lr);

    switch (target) {
    case 0x0034661c:
        LOG_WARNING(Core_ARM11,
                    "(YW2 SESSION) protocol_pump r0=0x{:08X} f38=0x{:08X} f3c=0x{:08X} f48=0x{:08X} f4c=0x{:08X}",
                    r0, YW2Read32Or(memory, r0 + 0x38), YW2Read32Or(memory, r0 + 0x3c),
                    YW2Read32Or(memory, r0 + 0x48), YW2Read32Or(memory, r0 + 0x4c));
        break;
    case 0x00343d94: {
        u32 payload = 0;
        u32 length = 0;
        u32 sender_word = 0;
        u32 tail = 0;
        const bool desc_ok = YW2Read32(memory, r1 + 0, payload) && YW2Read32(memory, r1 + 4, length) &&
                             YW2Read32(memory, r1 + 8, sender_word) && YW2Read32(memory, r1 + 12, tail);
        LOG_WARNING(Core_ARM11,
                    "(YW2 PKT) 343d94 desc=0x{:08X} ok={} payload=0x{:08X} len={} sender_low=0x{:02X} desc2=0x{:08X} desc3=0x{:08X}",
                    r1, desc_ok, payload, length, sender_word & 0xff, sender_word, tail);
        if (payload != 0) {
            YW2LogPacket(memory, "343d94", payload, length);
        }
        break;
    }
    case 0x0034ef84:
        YW2LogJob(memory, "ef84_translate", r0);
        YW2LogPacket(memory, "ef84", r1, r2);
        break;
    case 0x0034d4f8:
        YW2LogJob(memory, "d4f8_translate", r0);
        YW2LogPacket(memory, "d4f8", r1, 32);
        break;
    case 0x0034e9d4:
        YW2LogJob(memory, "e9d4_translate", r0);
        YW2LogPacket(memory, "e9d4", r1, r2);
        break;
    case 0x0034c328:
        YW2LogJob(memory, "c328_translate", r0);
        break;
    case 0x0034d058:
        YW2LogJob(memory, "d058_translate", r0);
        break;
    case 0x0034eee8:
        YW2LogJob(memory, "eee8_translate", r0);
        break;
    default:
        break;
    }
}

} // namespace

''',
        "YW2 ARM trace helpers",
    )

patch_once(
    "    std::optional<std::uint32_t> MemoryReadCode(VAddr vaddr) override {\n"
    "        return memory.Read32OrNullopt(vaddr);\n"
    "    }\n",
    "    std::optional<std::uint32_t> MemoryReadCode(VAddr vaddr) override {\n"
    "        if (YW2ArmTraceEnabled()) [[unlikely]] {\n"
    "            YW2TraceArmPC(parent, memory, vaddr);\n"
    "        }\n"
    "        return memory.Read32OrNullopt(vaddr);\n"
    "    }\n",
    "YW2 ARM trace code translation hook",
)

path.write_text(text)
print("Patched Dynarmic YW2 ARM PC translation trace")
