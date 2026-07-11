from pathlib import Path

path = Path("src/core/hle/service/nwm/nwm_uds.cpp")
text = path.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 destroy/dummy patch marker not found: {label}")
    text = text.replace(old, new, 1)


patch_once(
    "#include <algorithm>\n"
    "#include <cstring>\n",
    "#include <algorithm>\n"
    "#include <cstring>\n"
    "#ifdef ANDROID\n"
    "#include <sys/system_properties.h>\n"
    "#endif\n",
    "Android system property include",
)

patch_once(
    "// The Host has always dest_node_id 1\n"
    "constexpr u16 HostDestNodeId = 1;\n\n",
    "// The Host has always dest_node_id 1\n"
    "constexpr u16 HostDestNodeId = 1;\n\n"
    "namespace {\n\n"
    "u32 GetYW2TraceLevel() {\n"
    "#ifdef ANDROID\n"
    "    char enabled[PROP_VALUE_MAX] = {};\n"
    "    if (__system_property_get(\"debug.azahar.yw2_trace\", enabled) > 0) {\n"
    "        if (std::strcmp(enabled, \"0\") == 0 || std::strcmp(enabled, \"false\") == 0 ||\n"
    "            std::strcmp(enabled, \"off\") == 0) {\n"
    "            return 0;\n"
    "        }\n"
    "    }\n\n"
    "    char level[PROP_VALUE_MAX] = {};\n"
    "    if (__system_property_get(\"debug.azahar.yw2_trace_level\", level) <= 0) {\n"
    "        return 1;\n"
    "    }\n"
    "    if (std::strcmp(level, \"0\") == 0 || std::strcmp(level, \"off\") == 0) {\n"
    "        return 0;\n"
    "    }\n"
    "    if (std::strcmp(level, \"basic\") == 0) {\n"
    "        return 1;\n"
    "    }\n"
    "    if (std::strcmp(level, \"uds\") == 0) {\n"
    "        return 2;\n"
    "    }\n"
    "    if (std::strcmp(level, \"packet\") == 0) {\n"
    "        return 3;\n"
    "    }\n"
    "    if (std::strcmp(level, \"all\") == 0) {\n"
    "        return 4;\n"
    "    }\n"
    "    return 1;\n"
    "#else\n"
    "    return 0;\n"
    "#endif\n"
    "}\n\n"
    "bool YW2TraceEnabled(u32 level = 1) {\n"
    "    return GetYW2TraceLevel() >= level;\n"
    "}\n\n"
    "bool YW2DummyNodeEnabled() {\n"
    "#ifdef ANDROID\n"
    "    char value[PROP_VALUE_MAX] = {};\n"
    "    if (__system_property_get(\"debug.azahar.yw2_dummy_node\", value) <= 0) {\n"
    "        return false;\n"
    "    }\n"
    "    return std::strcmp(value, \"0\") != 0 && std::strcmp(value, \"false\") != 0 &&\n"
    "           std::strcmp(value, \"off\") != 0;\n"
    "#else\n"
    "    return false;\n"
    "#endif\n"
    "}\n\n"
    "bool YW2DummyPacketEnabled() {\n"
    "#ifdef ANDROID\n"
    "    char value[PROP_VALUE_MAX] = {};\n"
    "    if (__system_property_get(\"debug.azahar.yw2_dummy_packet\", value) <= 0) {\n"
    "        return false;\n"
    "    }\n"
    "    return std::strcmp(value, \"0\") != 0 && std::strcmp(value, \"false\") != 0 &&\n"
    "           std::strcmp(value, \"off\") != 0;\n"
    "#else\n"
    "    return false;\n"
    "#endif\n"
    "}\n\n"
    "bool YW2StatusPulseEnabled() {\n"
    "#ifdef ANDROID\n"
    "    char value[PROP_VALUE_MAX] = {};\n"
    "    if (__system_property_get(\"debug.azahar.yw2_status_pulse\", value) <= 0) {\n"
    "        return false;\n"
    "    }\n"
    "    return std::strcmp(value, \"0\") != 0 && std::strcmp(value, \"false\") != 0 &&\n"
    "           std::strcmp(value, \"off\") != 0;\n"
    "#else\n"
    "    return false;\n"
    "#endif\n"
    "}\n\n"
    "u32 YW2ByteAt(const std::vector<u8>& data, std::size_t index) {\n"
    "    return index < data.size() ? data[index] : 0;\n"
    "}\n\n"
    "} // namespace\n\n",
    "YW2 runtime trace helper",
)

patch_once(
    "void SendPacket(Network::WifiPacket& packet) {\n"
    "    if (auto room_member = Network::GetRoomMember().lock()) {\n",
    "void SendPacket(Network::WifiPacket& packet) {\n"
    "    if (YW2TraceEnabled(3)) {\n"
    "        LOG_WARNING(Service_NWM,\n"
    "                    \"(YW2 TRACE) SendPacket type={} channel={} size={} dest={:02X}:{:02X}:{:02X}:{:02X}:{:02X}:{:02X}\",\n"
    "                    static_cast<u32>(packet.type), static_cast<u32>(packet.channel),\n"
    "                    packet.data.size(), static_cast<u32>(packet.destination_address[0]),\n"
    "                    static_cast<u32>(packet.destination_address[1]),\n"
    "                    static_cast<u32>(packet.destination_address[2]),\n"
    "                    static_cast<u32>(packet.destination_address[3]),\n"
    "                    static_cast<u32>(packet.destination_address[4]),\n"
    "                    static_cast<u32>(packet.destination_address[5]));\n"
    "        if (packet.channel == 11 && packet.data.size() == 435) {\n"
    "            LOG_WARNING(Service_NWM,\n"
    "                        \"(YW2 TRACE) SendPacket channel11_435 head={:02X} {:02X} {:02X} {:02X} \"\n"
    "                        \"{:02X} {:02X} {:02X} {:02X} {:02X} {:02X} {:02X} {:02X} {:02X} \"\n"
    "                        \"{:02X} {:02X} {:02X} off2C={:02X} {:02X} {:02X} {:02X} \"\n"
    "                        \"off48={:02X} {:02X} {:02X} {:02X} off54={:02X} {:02X} {:02X} {:02X} \"\n"
    "                        \"tail={:02X} {:02X} {:02X} {:02X}\",\n"
    "                        YW2ByteAt(packet.data, 0), YW2ByteAt(packet.data, 1),\n"
    "                        YW2ByteAt(packet.data, 2), YW2ByteAt(packet.data, 3),\n"
    "                        YW2ByteAt(packet.data, 4), YW2ByteAt(packet.data, 5),\n"
    "                        YW2ByteAt(packet.data, 6), YW2ByteAt(packet.data, 7),\n"
    "                        YW2ByteAt(packet.data, 8), YW2ByteAt(packet.data, 9),\n"
    "                        YW2ByteAt(packet.data, 10), YW2ByteAt(packet.data, 11),\n"
    "                        YW2ByteAt(packet.data, 12), YW2ByteAt(packet.data, 13),\n"
    "                        YW2ByteAt(packet.data, 14), YW2ByteAt(packet.data, 15),\n"
    "                        YW2ByteAt(packet.data, 0x2C), YW2ByteAt(packet.data, 0x2D),\n"
    "                        YW2ByteAt(packet.data, 0x2E), YW2ByteAt(packet.data, 0x2F),\n"
    "                        YW2ByteAt(packet.data, 0x48), YW2ByteAt(packet.data, 0x49),\n"
    "                        YW2ByteAt(packet.data, 0x4A), YW2ByteAt(packet.data, 0x4B),\n"
    "                        YW2ByteAt(packet.data, 0x54), YW2ByteAt(packet.data, 0x55),\n"
    "                        YW2ByteAt(packet.data, 0x56), YW2ByteAt(packet.data, 0x57),\n"
    "                        YW2ByteAt(packet.data, packet.data.size() - 4),\n"
    "                        YW2ByteAt(packet.data, packet.data.size() - 3),\n"
    "                        YW2ByteAt(packet.data, packet.data.size() - 2),\n"
    "                        YW2ByteAt(packet.data, packet.data.size() - 1));\n"
    "        }\n"
    "    }\n"
    "    if (auto room_member = Network::GetRoomMember().lock()) {\n",
    "SendPacket generic trace",
)

patch_once(
    "        // Notify the application that the first node was set.\n"
    "        connection_status.changed_nodes |= 1;\n\n"
    "        network_info.host_mac_address = GetMacAddress();\n",
    "        // Notify the application that the first node was set.\n"
    "        connection_status.changed_nodes |= 1;\n\n"
    "        // YW2 probe: expose a synthetic peer so we can tell whether the game's\n"
    "        // session update job is driven by GetConnectionStatus node changes.\n"
    "        if (YW2DummyNodeEnabled() && network_info.max_nodes > 1) {\n"
    "            constexpr u16 DummyNodeId = 2;\n"
    "            NodeInfo dummy_node = current_node;\n"
    "            dummy_node.network_node_id = DummyNodeId;\n"
    "            node_info[DummyNodeId - 1] = dummy_node;\n"
    "            connection_status.nodes[DummyNodeId - 1] = DummyNodeId;\n"
    "            connection_status.node_bitmask |= 1 << (DummyNodeId - 1);\n"
    "            connection_status.changed_nodes |= 1 << (DummyNodeId - 1);\n"
    "            connection_status.total_nodes = 2;\n"
    "            network_info.total_nodes = 2;\n"
    "            LOG_WARNING(Service_NWM,\n"
    "                        \"(YW2 TRACE) BeginHostingNetwork dummy_node status={} self={} total={} \"\n"
    "                        \"max={} bitmask=0x{:X} changed=0x{:X} nodes={} {}\",\n"
    "                        static_cast<u32>(connection_status.status),\n"
    "                        static_cast<u16>(connection_status.network_node_id),\n"
    "                        static_cast<u32>(connection_status.total_nodes),\n"
    "                        static_cast<u32>(connection_status.max_nodes),\n"
    "                        static_cast<u32>(connection_status.node_bitmask),\n"
    "                        static_cast<u32>(connection_status.changed_nodes),\n"
    "                        static_cast<u16>(connection_status.nodes[0]),\n"
    "                        static_cast<u16>(connection_status.nodes[1]));\n"
    "        }\n\n"
    "        if (YW2DummyPacketEnabled()) {\n"
    "            constexpr u8 YW2BustersDataChannel = 243;\n"
    "            constexpr u16 DummyNodeId = 2;\n"
    "            auto channel = channel_data.find(YW2BustersDataChannel);\n"
    "            if (channel != channel_data.end()) {\n"
    "                const std::vector<u8> fake_payload = {0x00, 0x00, 0x03, 0x00};\n"
    "                channel->second.received_packets.emplace_back(\n"
    "                    GenerateDataPayload(fake_payload, YW2BustersDataChannel,\n"
    "                                        connection_status.network_node_id, DummyNodeId, 0));\n"
    "                channel->second.event->Signal();\n"
    "                LOG_WARNING(Service_NWM,\n"
    "                            \"(YW2 TRACE) BeginHostingNetwork injected dummy packet channel={} \"\n"
    "                            \"src={} dest={} payload={:02X} {:02X} {:02X} {:02X} queue={}\",\n"
    "                            static_cast<u32>(YW2BustersDataChannel), static_cast<u32>(DummyNodeId),\n"
    "                            static_cast<u16>(connection_status.network_node_id),\n"
    "                            static_cast<u32>(fake_payload[0]), static_cast<u32>(fake_payload[1]),\n"
    "                            static_cast<u32>(fake_payload[2]), static_cast<u32>(fake_payload[3]),\n"
    "                            channel->second.received_packets.size());\n"
    "            } else {\n"
    "                LOG_WARNING(Service_NWM,\n"
    "                            \"(YW2 TRACE) BeginHostingNetwork dummy packet skipped missing channel={}\",\n"
    "                            static_cast<u32>(YW2BustersDataChannel));\n"
    "            }\n"
    "        }\n\n"
    "        network_info.host_mac_address = GetMacAddress();\n",
    "BeginHostingNetwork dummy node injection",
)

patch_once(
    "    SendPacket(packet);\n\n"
    "    // Start broadcasting the network, send a beacon frame every 102.4ms.\n",
    "    SendPacket(packet);\n\n"
    "    if (YW2StatusPulseEnabled()) {\n"
    "        std::scoped_lock lock(connection_status_mutex);\n"
    "        if (connection_status.status == NetworkStatus::ConnectedAsHost) {\n"
    "            connection_status.changed_nodes |= connection_status.node_bitmask;\n"
    "            connection_status.status_change_reason =\n"
    "                NetworkStatusChangeReason::ConnectionEstablished;\n"
    "            connection_status_event->Signal();\n"
    "            if (YW2TraceEnabled(2)) {\n"
    "                LOG_WARNING(Service_NWM,\n"
    "                            \"(YW2 TRACE) Beacon status pulse status={} self={} total={} max={} \"\n"
    "                            \"bitmask=0x{:X} changed=0x{:X}\",\n"
    "                            static_cast<u32>(connection_status.status),\n"
    "                            static_cast<u16>(connection_status.network_node_id),\n"
    "                            static_cast<u32>(connection_status.total_nodes),\n"
    "                            static_cast<u32>(connection_status.max_nodes),\n"
    "                            static_cast<u32>(connection_status.node_bitmask),\n"
    "                            static_cast<u32>(connection_status.changed_nodes));\n"
    "            }\n"
    "        }\n"
    "    }\n\n"
    "    // Start broadcasting the network, send a beacon frame every 102.4ms.\n",
    "Beacon status pulse injection",
)

patch_once(
    "Result NWM_UDS::EjectClientHLE(u16 network_node_id) {\n"
    "    // The host can not be kicked.\n"
    "    if (network_node_id == 1) {\n"
    "        return Result(ErrorDescription::NotAuthorized, ErrorModule::UDS,\n"
    "                      ErrorSummary::WrongArgument, ErrorLevel::Usage);\n"
    "    }\n\n"
    "    std::scoped_lock lock(connection_status_mutex);\n"
    "    if (connection_status.status != NetworkStatus::ConnectedAsHost) {\n",
    "Result NWM_UDS::EjectClientHLE(u16 network_node_id) {\n"
    "    // The host can not be kicked.\n"
    "    if (network_node_id == 1) {\n"
    "        return Result(ErrorDescription::NotAuthorized, ErrorModule::UDS,\n"
    "                      ErrorSummary::WrongArgument, ErrorLevel::Usage);\n"
    "    }\n\n"
    "    std::scoped_lock lock(connection_status_mutex);\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) EjectClientHLE request node={} status={} self={} total={} max={} \"\n"
    "                \"bitmask=0x{:X} changed=0x{:X}\",\n"
    "                static_cast<u16>(network_node_id), static_cast<u32>(connection_status.status),\n"
    "                static_cast<u16>(connection_status.network_node_id),\n"
    "                static_cast<u32>(connection_status.total_nodes),\n"
    "                static_cast<u32>(connection_status.max_nodes),\n"
    "                static_cast<u32>(connection_status.node_bitmask),\n"
    "                static_cast<u32>(connection_status.changed_nodes));\n"
    "    if (connection_status.status != NetworkStatus::ConnectedAsHost) {\n",
    "EjectClientHLE trace",
)

patch_once(
    "void NWM_UDS::OnWifiPacketReceived(const Network::WifiPacket& packet) {\n"
    "    if (!initialized) {\n"
    "        return;\n"
    "    }\n",
    "void NWM_UDS::OnWifiPacketReceived(const Network::WifiPacket& packet) {\n"
    "    if (!initialized) {\n"
    "        return;\n"
    "    }\n"
    "    if (YW2TraceEnabled(3)) {\n"
    "        LOG_WARNING(Service_NWM,\n"
    "                    \"(YW2 TRACE) OnWifiPacketReceived type={} channel={} size={} tx={:02X}:{:02X}:{:02X}:{:02X}:{:02X}:{:02X}\",\n"
    "                    static_cast<u32>(packet.type), static_cast<u32>(packet.channel),\n"
    "                    packet.data.size(), static_cast<u32>(packet.transmitter_address[0]),\n"
    "                    static_cast<u32>(packet.transmitter_address[1]),\n"
    "                    static_cast<u32>(packet.transmitter_address[2]),\n"
    "                    static_cast<u32>(packet.transmitter_address[3]),\n"
    "                    static_cast<u32>(packet.transmitter_address[4]),\n"
    "                    static_cast<u32>(packet.transmitter_address[5]));\n"
    "    }\n",
    "OnWifiPacketReceived generic trace",
)

patch_once(
    "void NWM_UDS::RecvBeaconBroadcastData(Kernel::HLERequestContext& ctx) {\n"
    "    IPC::RequestParser rp(ctx);\n\n"
    "    u32 out_buffer_size = rp.Pop<u32>();\n",
    "void NWM_UDS::RecvBeaconBroadcastData(Kernel::HLERequestContext& ctx) {\n"
    "    IPC::RequestParser rp(ctx);\n\n"
    "    u32 out_buffer_size = rp.Pop<u32>();\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) RecvBeaconBroadcastData request out_buffer_size=0x{:X}\",\n"
    "                out_buffer_size);\n",
    "RecvBeaconBroadcastData request trace",
)

patch_once(
    "    auto beacons = GetReceivedBeacons(mac_address);\n\n"
    "    BeaconDataReplyHeader data_reply_header{};\n",
    "    auto beacons = GetReceivedBeacons(mac_address);\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) RecvBeaconBroadcastData scan mac={:02X}:{:02X}:{:02X}:{:02X}:{:02X}:{:02X} \"\n"
    "                \"wlan_comm_id=0x{:08X} id=0x{:08X} unk1=0x{:08X} unk2=0x{:08X} beacons={}\",\n"
    "                static_cast<u8>(mac_address[0]), static_cast<u8>(mac_address[1]),\n"
    "                static_cast<u8>(mac_address[2]), static_cast<u8>(mac_address[3]),\n"
    "                static_cast<u8>(mac_address[4]), static_cast<u8>(mac_address[5]), wlan_comm_id, id,\n"
    "                unk1, unk2, beacons.size());\n\n"
    "    BeaconDataReplyHeader data_reply_header{};\n",
    "RecvBeaconBroadcastData scan trace",
)

patch_once(
    "    data_reply_header.total_size = static_cast<u32>(cur_buffer_size);\n"
    "    out_buffer.Write(&data_reply_header, 0, sizeof(BeaconDataReplyHeader));\n",
    "    data_reply_header.total_size = static_cast<u32>(cur_buffer_size);\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) RecvBeaconBroadcastData reply total_entries={} total_size={} max_output={}\",\n"
    "                data_reply_header.total_entries, data_reply_header.total_size,\n"
    "                data_reply_header.max_output_size);\n"
    "    out_buffer.Write(&data_reply_header, 0, sizeof(BeaconDataReplyHeader));\n",
    "RecvBeaconBroadcastData reply trace",
)

patch_once(
    "    u16 network_node_id = rp.Pop<u16>();\n\n"
    "    if (!initialized) {\n",
    "    u16 network_node_id = rp.Pop<u16>();\n"
    "    LOG_WARNING(Service_NWM, \"(YW2 TRACE) GetNodeInformation request node={} initialized={}\",\n"
    "                static_cast<u16>(network_node_id), initialized.load());\n\n"
    "    if (!initialized) {\n",
    "GetNodeInformation request trace",
)

patch_once(
    "        if (!node) {\n"
    "            IPC::RequestBuilder rb = rp.MakeBuilder(1, 0);\n",
    "        if (!node) {\n"
    "            LOG_WARNING(Service_NWM, \"(YW2 TRACE) GetNodeInformation not_found node={}\",\n"
    "                        static_cast<u16>(network_node_id));\n"
    "            IPC::RequestBuilder rb = rp.MakeBuilder(1, 0);\n",
    "GetNodeInformation not-found trace",
)

patch_once(
    "        IPC::RequestBuilder rb = rp.MakeBuilder(11, 0);\n"
    "        rb.Push(ResultSuccess);\n",
    "        LOG_WARNING(Service_NWM,\n"
    "                    \"(YW2 TRACE) GetNodeInformation success node={} friend_seed=0x{:016X} username0=0x{:X}\",\n"
    "                    static_cast<u16>(node->network_node_id),\n"
    "                    static_cast<u64>(node->friend_code_seed), static_cast<u16>(node->username[0]));\n"
    "        IPC::RequestBuilder rb = rp.MakeBuilder(11, 0);\n"
    "        rb.Push(ResultSuccess);\n",
    "GetNodeInformation success trace",
)

patch_once(
    "    u16 bitmask = rp.Pop<u16>();\n"
    "    u8 flag = rp.Pop<u8>();\n\n"
    "    auto res = UpdateNetworkAttributeHLE(bitmask, flag);\n",
    "    u16 bitmask = rp.Pop<u16>();\n"
    "    u8 flag = rp.Pop<u8>();\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) UpdateNetworkAttribute bitmask=0x{:X} flag=0x{:X}\",\n"
    "                static_cast<u16>(bitmask), static_cast<u8>(flag));\n\n"
    "    auto res = UpdateNetworkAttributeHLE(bitmask, flag);\n",
    "UpdateNetworkAttribute trace",
)

patch_once(
    "Result NWM_UDS::DestroyNetworkHLE() {\n"
    "    // Unschedule the beacon broadcast event.\n"
    "    system.CoreTiming().UnscheduleEvent(beacon_broadcast_event, 0);\n\n"
    "    // Only a host can destroy\n"
    "    std::scoped_lock lock(connection_status_mutex);\n"
    "    if (connection_status.status != NetworkStatus::ConnectedAsHost) {\n",
    "Result NWM_UDS::DestroyNetworkHLE() {\n"
    "    // Unschedule the beacon broadcast event.\n"
    "    system.CoreTiming().UnscheduleEvent(beacon_broadcast_event, 0);\n\n"
    "    // Only a host can destroy\n"
    "    std::scoped_lock lock(connection_status_mutex);\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) DestroyNetworkHLE before status={} self={} total={} max={} \"\n"
    "                \"bitmask=0x{:X} changed=0x{:X}\",\n"
    "                static_cast<u32>(connection_status.status),\n"
    "                static_cast<u16>(connection_status.network_node_id),\n"
    "                static_cast<u32>(connection_status.total_nodes),\n"
    "                static_cast<u32>(connection_status.max_nodes),\n"
    "                static_cast<u32>(connection_status.node_bitmask),\n"
    "                static_cast<u32>(connection_status.changed_nodes));\n"
    "    if (connection_status.status != NetworkStatus::ConnectedAsHost) {\n",
    "DestroyNetworkHLE before trace",
)

patch_once(
    "    connection_status.status = NetworkStatus::NotConnected;\n"
    "    connection_status.network_node_id = tmp_node_id;\n"
    "    node_map.clear();\n"
    "    connection_status_event->Signal();\n",
    "    connection_status.status = NetworkStatus::NotConnected;\n"
    "    connection_status.network_node_id = tmp_node_id;\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) DestroyNetworkHLE after status={} self={} total={} max={} \"\n"
    "                \"bitmask=0x{:X} changed=0x{:X}\",\n"
    "                static_cast<u32>(connection_status.status),\n"
    "                static_cast<u16>(connection_status.network_node_id),\n"
    "                static_cast<u32>(connection_status.total_nodes),\n"
    "                static_cast<u32>(connection_status.max_nodes),\n"
    "                static_cast<u32>(connection_status.node_bitmask),\n"
    "                static_cast<u32>(connection_status.changed_nodes));\n"
    "    node_map.clear();\n"
    "    connection_status_event->Signal();\n",
    "DestroyNetworkHLE after trace",
)

patch_once(
    "void NWM_UDS::DestroyNetwork(Kernel::HLERequestContext& ctx) {\n"
    "    IPC::RequestParser rp(ctx);\n\n"
    "    auto res = DestroyNetworkHLE();\n",
    "void NWM_UDS::DestroyNetwork(Kernel::HLERequestContext& ctx) {\n"
    "    IPC::RequestParser rp(ctx);\n"
    "    LOG_WARNING(Service_NWM, \"(YW2 TRACE) DestroyNetwork IPC called\");\n\n"
    "    auto res = DestroyNetworkHLE();\n",
    "DestroyNetwork IPC trace",
)

patch_once(
    "ResultStatus NWM_UDS::DisconnectNetworkHLE() {\n"
    "    using Network::WifiPacket;\n"
    "    WifiPacket deauth;\n"
    "    {\n"
    "        std::scoped_lock lock(connection_status_mutex);\n"
    "        if (connection_status.status == NetworkStatus::ConnectedAsHost) {\n",
    "ResultStatus NWM_UDS::DisconnectNetworkHLE() {\n"
    "    using Network::WifiPacket;\n"
    "    WifiPacket deauth;\n"
    "    {\n"
    "        std::scoped_lock lock(connection_status_mutex);\n"
    "        LOG_WARNING(Service_NWM,\n"
    "                    \"(YW2 TRACE) DisconnectNetworkHLE before status={} self={} total={} max={} \"\n"
    "                    \"bitmask=0x{:X} changed=0x{:X}\",\n"
    "                    static_cast<u32>(connection_status.status),\n"
    "                    static_cast<u16>(connection_status.network_node_id),\n"
    "                    static_cast<u32>(connection_status.total_nodes),\n"
    "                    static_cast<u32>(connection_status.max_nodes),\n"
    "                    static_cast<u32>(connection_status.node_bitmask),\n"
    "                    static_cast<u32>(connection_status.changed_nodes));\n"
    "        if (connection_status.status == NetworkStatus::ConnectedAsHost) {\n",
    "DisconnectNetworkHLE before trace",
)

patch_once(
    "            connection_status.status = NetworkStatus::ConnectedAsHost;\n"
    "            connection_status.network_node_id = tmp_node_id;\n"
    "            node_map.clear();\n"
    "            return ResultStatus::DisconError_CalledAsHost;\n",
    "            connection_status.status = NetworkStatus::ConnectedAsHost;\n"
    "            connection_status.network_node_id = tmp_node_id;\n"
    "            LOG_WARNING(Service_NWM,\n"
    "                        \"(YW2 TRACE) DisconnectNetworkHLE host_result status={} self={} total={} \"\n"
    "                        \"max={} bitmask=0x{:X} changed=0x{:X}\",\n"
    "                        static_cast<u32>(connection_status.status),\n"
    "                        static_cast<u16>(connection_status.network_node_id),\n"
    "                        static_cast<u32>(connection_status.total_nodes),\n"
    "                        static_cast<u32>(connection_status.max_nodes),\n"
    "                        static_cast<u32>(connection_status.node_bitmask),\n"
    "                        static_cast<u32>(connection_status.changed_nodes));\n"
    "            node_map.clear();\n"
    "            return ResultStatus::DisconError_CalledAsHost;\n",
    "DisconnectNetworkHLE host result trace",
)

patch_once(
    "        connection_status.status = NetworkStatus::NotConnected;\n"
    "        connection_status.network_node_id = tmp_node_id;\n"
    "        node_map.clear();\n"
    "        connection_status_event->Signal();\n",
    "        connection_status.status = NetworkStatus::NotConnected;\n"
    "        connection_status.network_node_id = tmp_node_id;\n"
    "        LOG_WARNING(Service_NWM,\n"
    "                    \"(YW2 TRACE) DisconnectNetworkHLE after status={} self={} total={} max={} \"\n"
    "                    \"bitmask=0x{:X} changed=0x{:X}\",\n"
    "                    static_cast<u32>(connection_status.status),\n"
    "                    static_cast<u16>(connection_status.network_node_id),\n"
    "                    static_cast<u32>(connection_status.total_nodes),\n"
    "                    static_cast<u32>(connection_status.max_nodes),\n"
    "                    static_cast<u32>(connection_status.node_bitmask),\n"
    "                    static_cast<u32>(connection_status.changed_nodes));\n"
    "        node_map.clear();\n"
    "        connection_status_event->Signal();\n",
    "DisconnectNetworkHLE after trace",
)

patch_once(
    "void NWM_UDS::DisconnectNetwork(Kernel::HLERequestContext& ctx) {\n"
    "    LOG_DEBUG(Service_NWM, \"disconnecting from network\");\n",
    "void NWM_UDS::DisconnectNetwork(Kernel::HLERequestContext& ctx) {\n"
    "    LOG_WARNING(Service_NWM, \"(YW2 TRACE) DisconnectNetwork IPC called\");\n"
    "    LOG_DEBUG(Service_NWM, \"disconnecting from network\");\n",
    "DisconnectNetwork IPC trace",
)

patch_once(
    "void NWM_UDS::EjectSpectators(Kernel::HLERequestContext& ctx) {\n"
    "    IPC::RequestParser rp(ctx);\n\n"
    "    LOG_WARNING(Service_NWM, \"(STUBBED) called\");\n",
    "void NWM_UDS::EjectSpectators(Kernel::HLERequestContext& ctx) {\n"
    "    IPC::RequestParser rp(ctx);\n\n"
    "    LOG_WARNING(Service_NWM, \"(YW2 TRACE) EjectSpectators IPC called\");\n",
    "EjectSpectators trace",
)

patch_once(
    "    const std::vector<u8> application_data = rp.PopStaticBuffer();\n"
    "    ASSERT(application_data.size() == size);\n\n"
    "    LOG_DEBUG(Service_NWM, \"called\");\n",
    "    const std::vector<u8> application_data = rp.PopStaticBuffer();\n"
    "    ASSERT(application_data.size() == size);\n"
    "    const auto app_byte_at = [&application_data](std::size_t index) -> u32 {\n"
    "        return index < application_data.size() ? application_data[index] : 0;\n"
    "    };\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) SetApplicationData size={} buffer_size={} head={:02X} {:02X} {:02X} {:02X} \"\n"
    "                \"{:02X} {:02X} {:02X} {:02X}\",\n"
    "                size, application_data.size(), app_byte_at(0), app_byte_at(1), app_byte_at(2),\n"
    "                app_byte_at(3), app_byte_at(4), app_byte_at(5), app_byte_at(6), app_byte_at(7));\n\n"
    "    LOG_DEBUG(Service_NWM, \"called\");\n",
    "SetApplicationData trace",
)

patch_once(
    "    u32 input_size = rp.Pop<u32>();\n"
    "    u8 appdata_size = network_info.application_data_size;\n\n"
    "    IPC::RequestBuilder rb = rp.MakeBuilder(2, 2);\n",
    "    u32 input_size = rp.Pop<u32>();\n"
    "    u8 appdata_size = network_info.application_data_size;\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) GetApplicationData input_size={} appdata_size={} status={} total={} bitmask=0x{:X}\",\n"
    "                input_size, static_cast<u8>(appdata_size), static_cast<u32>(connection_status.status),\n"
    "                static_cast<u32>(connection_status.total_nodes),\n"
    "                static_cast<u32>(connection_status.node_bitmask));\n\n"
    "    IPC::RequestBuilder rb = rp.MakeBuilder(2, 2);\n",
    "GetApplicationData trace",
)

patch_once(
    "    const std::vector<u8> encrypted_data0_buffer = rp.PopStaticBuffer();\n"
    "    const std::vector<u8> encrypted_data1_buffer = rp.PopStaticBuffer();\n\n"
    "    LOG_DEBUG(Service_NWM, \"called\");\n",
    "    const std::vector<u8> encrypted_data0_buffer = rp.PopStaticBuffer();\n"
    "    const std::vector<u8> encrypted_data1_buffer = rp.PopStaticBuffer();\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) DecryptBeaconData network_size={} enc0_size={} enc1_size={}\",\n"
    "                network_struct_buffer.size(), encrypted_data0_buffer.size(),\n"
    "                encrypted_data1_buffer.size());\n\n"
    "    LOG_DEBUG(Service_NWM, \"called\");\n",
    "DecryptBeaconData request trace",
)

patch_once(
    "    const std::size_t num_nodes = net_info.max_nodes;\n\n"
    "    std::vector<NodeInfo> nodes;\n",
    "    const std::size_t num_nodes = net_info.max_nodes;\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) DecryptBeaconData net total={} max={} channel={} app_size={} wlan=0x{:08X}\",\n"
    "                static_cast<u32>(net_info.total_nodes), static_cast<u32>(net_info.max_nodes),\n"
    "                static_cast<u32>(net_info.channel), static_cast<u32>(net_info.application_data_size),\n"
    "                static_cast<u32>(net_info.wlan_comm_id));\n\n"
    "    std::vector<NodeInfo> nodes;\n",
    "DecryptBeaconData net trace",
)

path.write_text(text)
print("Applied YW2 UDS destroy/dummy patch")
