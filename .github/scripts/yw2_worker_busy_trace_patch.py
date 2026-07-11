from pathlib import Path
import re

ARM_PATH = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
arm_text = ARM_PATH.read_text()


def patch_once_arm(old: str, new: str, label: str) -> None:
    global arm_text
    if old not in arm_text:
        raise RuntimeError(f"YW2 worker busy trace ARM marker not found: {label}")
    arm_text = arm_text.replace(old, new, 1)


if "debug.azahar.yw2_worker_busy_trace" not in arm_text:
    patch_once_arm(
        """bool YW2ArmTraceEnabled() {
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
""",
        """bool YW2ArmTraceEnabled() {
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

bool YW2WorkerBusyTraceEnabled() {
#ifdef ANDROID
    char value[PROP_VALUE_MAX] = {};
    if (__system_property_get("debug.azahar.yw2_worker_busy_trace", value) <= 0) {
        return false;
    }
    return std::strcmp(value, "0") != 0 && std::strcmp(value, "false") != 0 &&
           std::strcmp(value, "off") != 0;
#else
    return false;
#endif
}
""",
        "worker busy property helper",
    )

    patch_once_arm(
        """} // namespace

""",
        r"""const char* YW2WorkerTargetName(u32 target) {
    switch (target) {
    case 0x0012e3e4:
        return "thread_entry_candidate";
    case 0x002055ac:
        return "thread_wait_check";
    case 0x00337680:
        return "post_channel_wait_80";
    case 0x003376c0:
        return "post_channel_wait_c0";
    case 0x003376f0:
        return "post_channel_wait_f0";
    case 0x00337744:
        return "destroy_branch";
    case 0x0033807c:
        return "connection_status_update_7c";
    case 0x0033809c:
        return "connection_status_event_wait";
    case 0x003380b0:
        return "connection_status_wait_b0";
    case 0x003380d0:
        return "connection_status_wait_d0";
    case 0x0033bd24:
        return "post_channel_callback";
    case 0x0033bd54:
        return "post_channel_return";
    case 0x00339994:
        return "worker_busy_gate";
    case 0x00339d8c:
        return "worker_start";
    case 0x00339c90:
        return "worker_stop";
    case 0x0033c0a0:
        return "packet_loop";
    case 0x0033b8bc:
        return "room_setup";
    case 0x0033727c:
        return "host_setup";
    case 0x00364d20:
        return "destroy_wrapper";
    case 0x003660e8:
        return "destroy_ipc_wrapper";
    default:
        return "unknown";
    }
}

int YW2WorkerTargetIndex(u32 target) {
    switch (target) {
    case 0x0012e3e4:
        return 0;
    case 0x002055ac:
        return 1;
    case 0x00337680:
        return 2;
    case 0x003376c0:
        return 3;
    case 0x003376f0:
        return 4;
    case 0x00337744:
        return 5;
    case 0x0033807c:
        return 6;
    case 0x0033809c:
        return 7;
    case 0x003380b0:
        return 8;
    case 0x003380d0:
        return 9;
    case 0x0033bd24:
        return 10;
    case 0x0033bd54:
        return 11;
    case 0x00339994:
        return 12;
    case 0x00339d8c:
        return 13;
    case 0x00339c90:
        return 14;
    case 0x0033c0a0:
        return 15;
    case 0x0033b8bc:
        return 16;
    case 0x0033727c:
        return 17;
    case 0x00364d20:
        return 18;
    case 0x003660e8:
        return 19;
    default:
        return -1;
    }
}

u32 YW2MatchWorkerTarget(u32 pc) {
    const u32 normalized = pc & ~u32{1};
    switch (normalized) {
    case 0x0012e3e4:
    case 0x002055ac:
    case 0x00337680:
    case 0x003376c0:
    case 0x003376f0:
    case 0x00337744:
    case 0x0033807c:
    case 0x0033809c:
    case 0x003380b0:
    case 0x003380d0:
    case 0x0033bd24:
    case 0x0033bd54:
    case 0x00339994:
    case 0x00339d8c:
    case 0x00339c90:
    case 0x0033c0a0:
    case 0x0033b8bc:
    case 0x0033727c:
    case 0x00364d20:
    case 0x003660e8:
        return normalized;
    default:
        return 0;
    }
}

void YW2TraceWorkerBusyPC(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u32 trace_pc) {
    const u32 target = YW2MatchWorkerTarget(trace_pc);
    if (target == 0) {
        return;
    }

    const int index = YW2WorkerTargetIndex(target);
    static std::atomic<u64> counters[20]{};
    const u64 hit_count = index >= 0 ? ++counters[index] : 1;

    const u32 r0 = cpu.GetReg(0);
    const u32 r1 = cpu.GetReg(1);
    const u32 r2 = cpu.GetReg(2);
    const u32 r3 = cpu.GetReg(3);
    const u32 r4 = cpu.GetReg(4);
    const u32 r5 = cpu.GetReg(5);
    const u32 sp = cpu.GetReg(13);
    const u32 lr = cpu.GetReg(14);
    const u32 cpu_pc = cpu.GetPC();

    const u32 r0_busy = YW2Read32Or(memory, r0 + 0x3eec, 0xffffffff);
    const u32 r1_busy = YW2Read32Or(memory, r1 + 0x3eec, 0xffffffff);
    const u32 r2_busy = YW2Read32Or(memory, r2 + 0x3eec, 0xffffffff);

    const u32 sp00 = YW2Read32Or(memory, sp + 0x00, 0xffffffff);
    const u32 sp04 = YW2Read32Or(memory, sp + 0x04, 0xffffffff);
    const u32 sp08 = YW2Read32Or(memory, sp + 0x08, 0xffffffff);
    const u32 sp0c = YW2Read32Or(memory, sp + 0x0c, 0xffffffff);
    const u32 sp10 = YW2Read32Or(memory, sp + 0x10, 0xffffffff);
    const u32 sp14 = YW2Read32Or(memory, sp + 0x14, 0xffffffff);

    u32 room_worker = 0;
    u32 room_worker_busy = 0xffffffff;
    if (target == 0x0033b8bc || target == 0x0033727c || target == 0x00337680 ||
        target == 0x003376c0 || target == 0x003376f0 || target == 0x00337744 ||
        target == 0x0033807c || target == 0x0033809c || target == 0x003380b0 ||
        target == 0x003380d0 || target == 0x0033bd24 || target == 0x0033bd54 ||
        target == 0x00364d20) {
        room_worker = YW2Read32Or(memory, r0 + 0x2a70, 0);
        room_worker_busy = YW2Read32Or(memory, room_worker + 0x3eec, 0xffffffff);
    }

    LOG_WARNING(Core_ARM11,
                "(YW2 WORKER) {} target=0x{:08X} trace_pc=0x{:08X} cpu_pc=0x{:08X} count={} "
                "r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X} r4=0x{:08X} r5=0x{:08X} "
                "sp=0x{:08X} lr=0x{:08X} r0_busy=0x{:08X} r1_busy=0x{:08X} r2_busy=0x{:08X} "
                "room_worker=0x{:08X} room_busy=0x{:08X} stack=0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X}",
                YW2WorkerTargetName(target), target, trace_pc, cpu_pc, hit_count, r0, r1, r2, r3,
                r4, r5, sp, lr, r0_busy, r1_busy, r2_busy, room_worker, room_worker_busy,
                sp00, sp04, sp08, sp0c, sp10, sp14);
}

} // namespace

""",
        "worker busy helpers before anonymous namespace close",
    )

    patch_once_arm(
        """    std::optional<std::uint32_t> MemoryReadCode(VAddr vaddr) override {
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
""",
        """    std::optional<std::uint32_t> MemoryReadCode(VAddr vaddr) override {
        const bool yw2_arm_trace = YW2ArmTraceEnabled();
        const bool yw2_worker_trace = YW2WorkerBusyTraceEnabled();
        if (yw2_arm_trace || yw2_worker_trace) [[unlikely]] {
            if (yw2_arm_trace) {
                static std::atomic<u64> yw2_code_probe_count{};
                const u64 probe_count = ++yw2_code_probe_count;
                if (probe_count <= 20 || (probe_count % 10000) == 0) {
                    LOG_WARNING(Core_ARM11,
                                "(YW2 ARM) enabled code_probe count={} vaddr=0x{:08X} cpu_pc=0x{:08X}",
                                probe_count, vaddr, parent.GetPC());
                }
                YW2TraceArmPC(parent, memory, vaddr);
            }
            if (yw2_worker_trace) {
                YW2TraceWorkerBusyPC(parent, memory, vaddr);
            }
        }
        return memory.Read32OrNullopt(vaddr);
    }
""",
        "MemoryReadCode worker busy hook",
    )

ARM_PATH.write_text(arm_text)


NWM_PATH = Path("src/core/hle/service/nwm/nwm_uds.cpp")
nwm_text = NWM_PATH.read_text()


def patch_once_nwm(old: str, new: str, label: str) -> None:
    global nwm_text
    if old not in nwm_text:
        raise RuntimeError(f"YW2 worker busy trace NWM marker not found: {label}")
    nwm_text = nwm_text.replace(old, new, 1)


def patch_regex_nwm(pattern: str, insertion: str, label: str) -> None:
    global nwm_text
    nwm_text, count = re.subn(pattern, lambda m: m.group(1) + insertion, nwm_text, count=1, flags=re.S)
    if count != 1:
        print(f"Skipped optional YW2 worker busy NWM regex patch: {label}")


if "(YW2 NWM) GetConnectionStatus after_clear" not in nwm_text:
    patch_once_nwm(
        """    connection_status.changed_nodes = 0;

    return cs_out;
""",
        """    connection_status.changed_nodes = 0;
    LOG_WARNING(Service_NWM,
                "(YW2 NWM) GetConnectionStatus after_clear status={} self={} total={} max={} "
                "bitmask=0x{:X} changed_ret=0x{:X} changed_now=0x{:X} reason={}",
                static_cast<u32>(cs_out.status), static_cast<u16>(cs_out.network_node_id),
                static_cast<u32>(cs_out.total_nodes), static_cast<u32>(cs_out.max_nodes),
                static_cast<u32>(cs_out.node_bitmask), static_cast<u32>(cs_out.changed_nodes),
                static_cast<u32>(connection_status.changed_nodes),
                static_cast<u32>(cs_out.status_change_reason));

    return cs_out;
""",
        "GetConnectionStatus post-clear trace",
    )

    patch_once_nwm(
        """    rb.Push(ResultSuccess);
    rb.Push(channel);

    LOG_DEBUG(Service_NWM, "called");
""",
        """    rb.Push(ResultSuccess);
    rb.Push(channel);

    LOG_WARNING(Service_NWM,
                "(YW2 NWM) GetChannel status={} connected={} channel={} changed=0x{:X} binds={}",
                static_cast<u32>(connection_status.status), is_connected, static_cast<u32>(channel),
                static_cast<u32>(connection_status.changed_nodes), channel_data.size());

    LOG_DEBUG(Service_NWM, "called");
""",
        "GetChannel trace",
    )

    patch_regex_nwm(
        r"(Result NWM_UDS::DestroyNetworkHLE\(\) \{.*?std::scoped_lock lock\(connection_status_mutex\);\n)",
        """    LOG_WARNING(Service_NWM,
                "(YW2 NWM) DestroyNetworkHLE before status={} self={} total={} max={} "
                "bitmask=0x{:X} changed=0x{:X} binds={}",
                static_cast<u32>(connection_status.status),
                static_cast<u16>(connection_status.network_node_id),
                static_cast<u32>(connection_status.total_nodes), static_cast<u32>(connection_status.max_nodes),
                static_cast<u32>(connection_status.node_bitmask),
                static_cast<u32>(connection_status.changed_nodes), channel_data.size());
""",
        "DestroyNetwork before trace",
    )

    patch_regex_nwm(
        r"(Result NWM_UDS::DestroyNetworkHLE\(\) \{.*?channel_data\.clear\(\);\n)",
        """    LOG_WARNING(Service_NWM,
                "(YW2 NWM) DestroyNetworkHLE after status={} self={} total={} max={} "
                "bitmask=0x{:X} changed=0x{:X} binds={}",
                static_cast<u32>(connection_status.status),
                static_cast<u16>(connection_status.network_node_id),
                static_cast<u32>(connection_status.total_nodes), static_cast<u32>(connection_status.max_nodes),
                static_cast<u32>(connection_status.node_bitmask),
                static_cast<u32>(connection_status.changed_nodes), channel_data.size());
""",
        "DestroyNetwork after trace",
    )

    patch_regex_nwm(
        r"(Common::Expected<int, ResultStatus> NWM_UDS::PullPacketHLE\(.*?if \(channel->second\.received_packets\.empty\(\)\) \{\n)",
        """        LOG_WARNING(Service_NWM,
                    "(YW2 NWM) PullPacket empty bind=0x{:X} channel={} status={} binds={} buff_size=0x{:X}",
                    bind_node_id, static_cast<u32>(channel->second.channel),
                    static_cast<u32>(connection_status.status), channel_data.size(), buff_size);
""",
        "PullPacket empty trace",
    )

NWM_PATH.write_text(nwm_text)
print("Applied YW2 worker busy and NWM teardown trace patch")
