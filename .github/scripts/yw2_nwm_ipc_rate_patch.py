from pathlib import Path

path = Path("src/core/hle/service/nwm/nwm_uds.cpp")
text = path.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 NWM IPC/rate patch marker not found: {label}")
    text = text.replace(old, new, 1)


def patch_optional(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        print(f"skip optional marker: {label}")
        return
    text = text.replace(old, new, 1)


if "bool YW2NwmIpcTraceEnabled()" not in text:
    patch_once(
        "u32 YW2ByteAt(const std::vector<u8>& data, std::size_t index) {\n",
        "bool YW2NwmIpcTraceEnabled() {\n"
        "#ifdef ANDROID\n"
        "    char value[PROP_VALUE_MAX] = {};\n"
        "    if (__system_property_get(\"debug.azahar.yw2_nwm_ipc_trace\", value) <= 0) {\n"
        "        return false;\n"
        "    }\n"
        "    return std::strcmp(value, \"0\") != 0 && std::strcmp(value, \"false\") != 0 &&\n"
        "           std::strcmp(value, \"off\") != 0;\n"
        "#else\n"
        "    return false;\n"
        "#endif\n"
        "}\n\n"
        "u32 YW2ByteAt(const std::vector<u8>& data, std::size_t index) {\n",
        "NWM IPC property helper",
    )

if "bool YW2StatusQuietHostEnabled()" not in text:
    patch_once(
        "u32 YW2ByteAt(const std::vector<u8>& data, std::size_t index) {\n",
        "bool YW2StatusQuietHostEnabled() {\n"
        "#ifdef ANDROID\n"
        "    char value[PROP_VALUE_MAX] = {};\n"
        "    if (__system_property_get(\"debug.azahar.yw2_status_quiet_host\", value) <= 0) {\n"
        "        return false;\n"
        "    }\n"
        "    return std::strcmp(value, \"0\") != 0 && std::strcmp(value, \"false\") != 0 &&\n"
        "           std::strcmp(value, \"off\") != 0;\n"
        "#else\n"
        "    return false;\n"
        "#endif\n"
        "}\n\n"
        "u32 YW2ByteAt(const std::vector<u8>& data, std::size_t index) {\n",
        "YW2 quiet host status property helper",
    )

quiet_status_patch_applied = False
quiet_status_base = (
    "    ConnectionStatus cs_out = connection_status;\n\n"
    "    // Reset the bitmask of changed nodes after each call to this\n"
)
quiet_status_base_new = (
    "    ConnectionStatus cs_out = connection_status;\n"
    "    if (YW2StatusQuietHostEnabled() &&\n"
    "        cs_out.status == NetworkStatus::ConnectedAsHost && cs_out.network_node_id == 1 &&\n"
    "        cs_out.total_nodes == 1 && cs_out.node_bitmask == 0x1 && cs_out.changed_nodes != 0) {\n"
    "        LOG_WARNING(Service_NWM,\n"
    "                    \"(YW2 TRACE) Quiet host GetConnectionStatus changed=0x{:X}->0 reason={}->0\",\n"
    "                    static_cast<u32>(cs_out.changed_nodes),\n"
    "                    static_cast<u32>(cs_out.status_change_reason));\n"
    "        cs_out.changed_nodes = 0;\n"
    "        cs_out.status_change_reason = NetworkStatusChangeReason::None;\n"
    "    }\n\n"
    "    // Reset the bitmask of changed nodes after each call to this\n"
)
if quiet_status_base in text:
    text = text.replace(quiet_status_base, quiet_status_base_new, 1)
    quiet_status_patch_applied = True

quiet_status_traced = (
    "                static_cast<u16>(cs_out.nodes[4]), static_cast<u16>(cs_out.nodes[5]),\n"
    "                static_cast<u16>(cs_out.nodes[6]), static_cast<u16>(cs_out.nodes[7]));\n\n"
    "    // Reset the bitmask of changed nodes after each call to this\n"
)
quiet_status_traced_new = (
    "                static_cast<u16>(cs_out.nodes[4]), static_cast<u16>(cs_out.nodes[5]),\n"
    "                static_cast<u16>(cs_out.nodes[6]), static_cast<u16>(cs_out.nodes[7]));\n"
    "    if (YW2StatusQuietHostEnabled() &&\n"
    "        cs_out.status == NetworkStatus::ConnectedAsHost && cs_out.network_node_id == 1 &&\n"
    "        cs_out.total_nodes == 1 && cs_out.node_bitmask == 0x1 && cs_out.changed_nodes != 0) {\n"
    "        LOG_WARNING(Service_NWM,\n"
    "                    \"(YW2 TRACE) Quiet host GetConnectionStatus changed=0x{:X}->0 reason={}->0\",\n"
    "                    static_cast<u32>(cs_out.changed_nodes),\n"
    "                    static_cast<u32>(cs_out.status_change_reason));\n"
    "        cs_out.changed_nodes = 0;\n"
    "        cs_out.status_change_reason = NetworkStatusChangeReason::None;\n"
    "    }\n\n"
    "    // Reset the bitmask of changed nodes after each call to this\n"
)
if not quiet_status_patch_applied and quiet_status_traced in text:
    text = text.replace(quiet_status_traced, quiet_status_traced_new, 1)
    quiet_status_patch_applied = True

if not quiet_status_patch_applied:
    raise RuntimeError("YW2 quiet host GetConnectionStatus marker not found")

# Rate-limit periodic beacon SendPacket logs while preserving non-beacon packet logs.
patch_optional(
    "void SendPacket(Network::WifiPacket& packet) {\n"
    "    if (YW2TraceEnabled(3)) {\n",
    "void SendPacket(Network::WifiPacket& packet) {\n"
    "    static u64 yw2_sendpacket_trace_count = 0;\n"
    "    const u64 yw2_sendpacket_trace_hit = ++yw2_sendpacket_trace_count;\n"
    "    const bool yw2_sendpacket_trace_this =\n"
    "        yw2_sendpacket_trace_hit <= 3 || (yw2_sendpacket_trace_hit % 10) == 0 ||\n"
    "        !(packet.channel == 11 && packet.data.size() == 435);\n"
    "    if (YW2TraceEnabled(3) && yw2_sendpacket_trace_this) {\n",
    "rate-limit SendPacket trace",
)

patch_optional(
    "    packet.channel = network_channel;\n\n"
    "    SendPacket(packet);\n",
    "    packet.channel = network_channel;\n"
    "    static u64 yw2_beacon_trace_count = 0;\n"
    "    const u64 yw2_beacon_trace_hit = ++yw2_beacon_trace_count;\n"
    "    const bool yw2_beacon_trace_this =\n"
    "        yw2_beacon_trace_hit <= 3 || (yw2_beacon_trace_hit % 10) == 0;\n\n"
    "    SendPacket(packet);\n",
    "beacon trace rate state",
)

patch_optional(
    "        if (YW2TraceEnabled(2)) {\n"
    "            LOG_WARNING(Service_NWM,\n"
    "                        \"(YW2 TRACE) Beacon self-loopback channel={} size={} tx={:02X}:{:02X}:{:02X}:{:02X}:{:02X}:{:02X}\",\n",
    "        if (YW2TraceEnabled(2) && yw2_beacon_trace_this) {\n"
    "            LOG_WARNING(Service_NWM,\n"
    "                        \"(YW2 TRACE) Beacon self-loopback channel={} size={} tx={:02X}:{:02X}:{:02X}:{:02X}:{:02X}:{:02X}\",\n",
    "rate-limit self-loopback log",
)

patch_optional(
    "            if (YW2TraceEnabled(2)) {\n"
    "                LOG_WARNING(Service_NWM,\n"
    "                            \"(YW2 TRACE) Bind event pulse binds={} signaled={} status={} self={} total={}\",\n",
    "            if (YW2TraceEnabled(2) && yw2_beacon_trace_this) {\n"
    "                LOG_WARNING(Service_NWM,\n"
    "                            \"(YW2 TRACE) Bind event pulse binds={} signaled={} status={} self={} total={}\",\n",
    "rate-limit bind pulse log",
)


def add_ipc(func: str, cmd: str, name: str) -> None:
    marker = f"void NWM_UDS::{func}(Kernel::HLERequestContext& ctx) {{\n"
    log = (
        marker
        + "    if (YW2NwmIpcTraceEnabled()) {\n"
        + "        const u32 yw2_ipc_pc = system.GetRunningCore().GetPC();\n"
        + "        const u32 yw2_ipc_lr = system.GetRunningCore().GetReg(14);\n"
        + "        const u32 yw2_ipc_ghidra_pc =\n"
        + "            yw2_ipc_pc >= 0x50000 ? yw2_ipc_pc - 0x50000 : yw2_ipc_pc;\n"
        + "        const u32 yw2_ipc_ghidra_lr =\n"
        + "            yw2_ipc_lr >= 0x50000 ? yw2_ipc_lr - 0x50000 : yw2_ipc_lr;\n"
        + "        LOG_WARNING(Service_NWM,\n"
        + f"                    \"(YW2 IPC) enter cmd={cmd} name={name} status={{}} initialized={{}} binds={{}} pc=0x{{:08X}} lr=0x{{:08X}} gpc=0x{{:08X}} glr=0x{{:08X}}\",\n"
        + "                    static_cast<u32>(connection_status.status), initialized.load(),\n"
        + "                    channel_data.size(), yw2_ipc_pc, yw2_ipc_lr, yw2_ipc_ghidra_pc,\n"
        + "                    yw2_ipc_ghidra_lr);\n"
        + "    }\n"
    )
    patch_optional(marker, log, f"ipc {name}")


entries = [
    ("InitializeDeprecated", "0x0001", "InitializeDeprecated"),
    ("Shutdown", "0x0003", "Shutdown"),
    ("BeginHostingNetworkDeprecated", "0x0004", "BeginHostingNetworkDeprecated"),
    ("EjectClient", "0x0005", "EjectClient"),
    ("EjectSpectators", "0x0006", "EjectSpectators"),
    ("UpdateNetworkAttribute", "0x0007", "UpdateNetworkAttribute"),
    ("DestroyNetwork", "0x0008", "DestroyNetwork"),
    ("ConnectToNetworkDeprecated", "0x0009", "ConnectToNetworkDeprecated"),
    ("DisconnectNetwork", "0x000A", "DisconnectNetwork"),
    ("GetConnectionStatus", "0x000B", "GetConnectionStatus"),
    ("GetNodeInformation", "0x000D", "GetNodeInformation"),
    ("DecryptBeaconData", "0x000E/0x001F", "DecryptBeaconData"),
    ("RecvBeaconBroadcastData", "0x000F", "RecvBeaconBroadcastData"),
    ("SetApplicationData", "0x0010", "SetApplicationData"),
    ("GetApplicationData", "0x0011", "GetApplicationData"),
    ("Bind", "0x0012", "Bind"),
    ("Unbind", "0x0013", "Unbind"),
    ("PullPacket", "0x0014", "PullPacket"),
    ("SendTo", "0x0017", "SendTo"),
    ("GetChannel", "0x001A", "GetChannel"),
    ("InitializeWithVersion", "0x001B", "InitializeWithVersion"),
    ("BeginHostingNetwork", "0x001D", "BeginHostingNetwork"),
    ("ConnectToNetwork", "0x001E", "ConnectToNetwork"),
    ("SetProbeResponseParam", "0x0021", "SetProbeResponseParam"),
]

for entry in entries:
    add_ipc(*entry)

path.write_text(text)
print("Applied YW2 NWM IPC trace, quiet host status, and beacon rate-limit patch")
