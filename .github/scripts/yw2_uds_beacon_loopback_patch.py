from pathlib import Path

path = Path("src/core/hle/service/nwm/nwm_uds.cpp")
text = path.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 beacon loopback patch marker not found: {label}")
    text = text.replace(old, new, 1)


if "bool YW2SelfLoopbackEnabled()" not in text:
    patch_once(
        "u32 YW2ByteAt(const std::vector<u8>& data, std::size_t index) {\n",
        "bool YW2SelfLoopbackEnabled() {\n"
        "#ifdef ANDROID\n"
        "    char value[PROP_VALUE_MAX] = {};\n"
        "    if (__system_property_get(\"debug.azahar.yw2_self_loopback\", value) <= 0) {\n"
        "        return false;\n"
        "    }\n"
        "    return std::strcmp(value, \"0\") != 0 && std::strcmp(value, \"false\") != 0 &&\n"
        "           std::strcmp(value, \"off\") != 0;\n"
        "#else\n"
        "    return false;\n"
        "#endif\n"
        "}\n\n"
        "bool YW2BindPulseEnabled() {\n"
        "#ifdef ANDROID\n"
        "    char value[PROP_VALUE_MAX] = {};\n"
        "    if (__system_property_get(\"debug.azahar.yw2_bind_pulse\", value) <= 0) {\n"
        "        return false;\n"
        "    }\n"
        "    return std::strcmp(value, \"0\") != 0 && std::strcmp(value, \"false\") != 0 &&\n"
        "           std::strcmp(value, \"off\") != 0;\n"
        "#else\n"
        "    return false;\n"
        "#endif\n"
        "}\n\n"
        "u32 YW2ByteAt(const std::vector<u8>& data, std::size_t index) {\n",
        "YW2 self-loopback and bind-pulse property helpers",
    )
elif "bool YW2BindPulseEnabled()" not in text:
    patch_once(
        "u32 YW2ByteAt(const std::vector<u8>& data, std::size_t index) {\n",
        "bool YW2BindPulseEnabled() {\n"
        "#ifdef ANDROID\n"
        "    char value[PROP_VALUE_MAX] = {};\n"
        "    if (__system_property_get(\"debug.azahar.yw2_bind_pulse\", value) <= 0) {\n"
        "        return false;\n"
        "    }\n"
        "    return std::strcmp(value, \"0\") != 0 && std::strcmp(value, \"false\") != 0 &&\n"
        "           std::strcmp(value, \"off\") != 0;\n"
        "#else\n"
        "    return false;\n"
        "#endif\n"
        "}\n\n"
        "u32 YW2ByteAt(const std::vector<u8>& data, std::size_t index) {\n",
        "YW2 bind-pulse property helper",
    )

patch_once(
    "    SendPacket(packet);\n\n"
    "    if (YW2StatusPulseEnabled()) {\n",
    "    SendPacket(packet);\n\n"
    "    if (YW2SelfLoopbackEnabled() && packet.channel == 11 && packet.data.size() == 435) {\n"
    "        Network::WifiPacket loopback_packet = packet;\n"
    "        loopback_packet.transmitter_address = GetMacAddress();\n"
    "        HandleBeaconFrame(loopback_packet);\n"
    "        if (YW2TraceEnabled(2)) {\n"
    "            LOG_WARNING(Service_NWM,\n"
    "                        \"(YW2 TRACE) Beacon self-loopback channel={} size={} tx={:02X}:{:02X}:{:02X}:{:02X}:{:02X}:{:02X}\",\n"
    "                        static_cast<u32>(loopback_packet.channel), loopback_packet.data.size(),\n"
    "                        static_cast<u32>(loopback_packet.transmitter_address[0]),\n"
    "                        static_cast<u32>(loopback_packet.transmitter_address[1]),\n"
    "                        static_cast<u32>(loopback_packet.transmitter_address[2]),\n"
    "                        static_cast<u32>(loopback_packet.transmitter_address[3]),\n"
    "                        static_cast<u32>(loopback_packet.transmitter_address[4]),\n"
    "                        static_cast<u32>(loopback_packet.transmitter_address[5]));\n"
    "        }\n"
    "    }\n\n"
    "    if (YW2BindPulseEnabled()) {\n"
    "        std::scoped_lock lock{connection_status_mutex, system.Kernel().GetHLELock()};\n"
    "        if (connection_status.status == NetworkStatus::ConnectedAsHost) {\n"
    "            std::size_t signaled = 0;\n"
    "            for (auto& entry : channel_data) {\n"
    "                if (entry.second.event) {\n"
    "                    entry.second.event->Signal();\n"
    "                    ++signaled;\n"
    "                }\n"
    "            }\n"
    "            if (YW2TraceEnabled(2)) {\n"
    "                LOG_WARNING(Service_NWM,\n"
    "                            \"(YW2 TRACE) Bind event pulse binds={} signaled={} status={} self={} total={}\",\n"
    "                            channel_data.size(), signaled,\n"
    "                            static_cast<u32>(connection_status.status),\n"
    "                            static_cast<u16>(connection_status.network_node_id),\n"
    "                            static_cast<u32>(connection_status.total_nodes));\n"
    "            }\n"
    "        }\n"
    "    }\n\n"
    "    if (YW2StatusPulseEnabled()) {\n",
    "BeaconBroadcastCallback self-loopback and bind pulse",
)

path.write_text(text)
print("Applied YW2 UDS beacon self-loopback and bind-pulse patch")

extra_patch = Path(".github/scripts/yw2_nwm_ipc_rate_patch.py")
if extra_patch.exists():
    exec(extra_patch.read_text(), {"__name__": "__main__"})

desktop_env_patch = Path(".github/scripts/yw2_desktop_env_patch.py")
if desktop_env_patch.exists():
    exec(desktop_env_patch.read_text(), {"__name__": "__main__"})
