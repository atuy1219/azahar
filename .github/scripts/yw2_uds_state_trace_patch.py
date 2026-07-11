from pathlib import Path

path = Path("src/core/hle/service/nwm/nwm_uds.cpp")
text = path.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 state trace patch marker not found: {label}")
    text = text.replace(old, new, 1)


patch_once(
    "        connection_status.status = NetworkStatus::NotConnected;\n"
    "        node_info.clear();\n"
    "        node_info.push_back(current_node);\n"
    "        channel_data.clear();\n",
    "        connection_status.status = NetworkStatus::NotConnected;\n"
    "        node_info.clear();\n"
    "        node_info.push_back(current_node);\n"
    "        channel_data.clear();\n"
    "        LOG_WARNING(Service_NWM,\n"
    "                    \"(YW2 TRACE) Initialize reset status={} current_node={} node_info={}\",\n"
    "                    static_cast<u32>(connection_status.status),\n"
    "                    static_cast<u16>(current_node.network_node_id), node_info.size());\n",
    "Initialize status trace",
)

patch_once(
    "    ConnectionStatus cs_out = connection_status;\n\n"
    "    // Reset the bitmask of changed nodes after each call to this\n",
    "    ConnectionStatus cs_out = connection_status;\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) GetConnectionStatus status={} self={} total={} max={} \"\n"
    "                \"node_bitmask=0x{:X} changed=0x{:X} reason={} \"\n"
    "                \"nodes={} {} {} {} {} {} {} {}\",\n"
    "                static_cast<u32>(cs_out.status), static_cast<u16>(cs_out.network_node_id),\n"
    "                static_cast<u32>(cs_out.total_nodes), static_cast<u32>(cs_out.max_nodes),\n"
    "                static_cast<u32>(cs_out.node_bitmask), static_cast<u32>(cs_out.changed_nodes),\n"
    "                static_cast<u32>(cs_out.status_change_reason),\n"
    "                static_cast<u16>(cs_out.nodes[0]), static_cast<u16>(cs_out.nodes[1]),\n"
    "                static_cast<u16>(cs_out.nodes[2]), static_cast<u16>(cs_out.nodes[3]),\n"
    "                static_cast<u16>(cs_out.nodes[4]), static_cast<u16>(cs_out.nodes[5]),\n"
    "                static_cast<u16>(cs_out.nodes[6]), static_cast<u16>(cs_out.nodes[7]));\n\n"
    "    // Reset the bitmask of changed nodes after each call to this\n",
    "GetConnectionStatusHLE trace",
)

patch_once(
    "ResultVal<std::shared_ptr<Kernel::Event>> NWM_UDS::Initialize(\n"
    "    u32 sharedmem_size, const NodeInfo& node, u16 version,\n"
    "    std::shared_ptr<Kernel::SharedMemory> sharedmem) {\n\n"
    "    current_node = node;\n",
    "ResultVal<std::shared_ptr<Kernel::Event>> NWM_UDS::Initialize(\n"
    "    u32 sharedmem_size, const NodeInfo& node, u16 version,\n"
    "    std::shared_ptr<Kernel::SharedMemory> sharedmem) {\n\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) Initialize request sharedmem_size=0x{:X} version=0x{:X} \"\n"
    "                \"node_id={} username0=0x{:X}\",\n"
    "                sharedmem_size, version, static_cast<u16>(node.network_node_id),\n"
    "                static_cast<u16>(node.username[0]));\n"
    "    current_node = node;\n",
    "Initialize request trace",
)

patch_once(
    "std::pair<ResultStatus, std::shared_ptr<Kernel::Event>> NWM_UDS::BindHLE(u32 bind_node_id,\n"
    "                                                                         u32 recv_buffer_size,\n"
    "                                                                         u8 data_channel,\n"
    "                                                                         u16 network_node_id) {\n"
    "    if (data_channel == 0 || bind_node_id == 0) {\n",
    "std::pair<ResultStatus, std::shared_ptr<Kernel::Event>> NWM_UDS::BindHLE(u32 bind_node_id,\n"
    "                                                                         u32 recv_buffer_size,\n"
    "                                                                         u8 data_channel,\n"
    "                                                                         u16 network_node_id) {\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) BindHLE request bind=0x{:X} recv_size=0x{:X} channel={} node={}\",\n"
    "                bind_node_id, recv_buffer_size, static_cast<u8>(data_channel),\n"
    "                static_cast<u16>(network_node_id));\n"
    "    if (data_channel == 0 || bind_node_id == 0) {\n",
    "BindHLE request trace",
)

patch_once(
    "    channel_data[data_channel] = {bind_node_id, data_channel, network_node_id, event};\n"
    "    return std::make_pair(ResultStatus::ResultSuccess, std::move(event));\n",
    "    channel_data[data_channel] = {bind_node_id, data_channel, network_node_id, event};\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) BindHLE success bind=0x{:X} channel={} node={} binds={} \"\n"
    "                \"status={} self={} total={}\",\n"
    "                bind_node_id, static_cast<u8>(data_channel), static_cast<u16>(network_node_id),\n"
    "                channel_data.size(), static_cast<u32>(connection_status.status),\n"
    "                static_cast<u16>(connection_status.network_node_id),\n"
    "                static_cast<u32>(connection_status.total_nodes));\n"
    "    return std::make_pair(ResultStatus::ResultSuccess, std::move(event));\n",
    "BindHLE success trace",
)

patch_once(
    "        std::memcpy(&network_info, network_info_buffer.data(), network_info_buffer.size());\n\n"
    "        // The real UDS module throws a fatal error if this assert fails.\n",
    "        std::memcpy(&network_info, network_info_buffer.data(), network_info_buffer.size());\n"
    "        LOG_WARNING(Service_NWM,\n"
    "                    \"(YW2 TRACE) BeginHostingNetwork request buffer_size={} passphrase_size={} \"\n"
    "                    \"max_nodes={} channel={} app_size={}\",\n"
    "                    network_info_buffer.size(), passphrase.size(),\n"
    "                    static_cast<u32>(network_info.max_nodes),\n"
    "                    static_cast<u32>(network_info.channel),\n"
    "                    static_cast<u32>(network_info.application_data_size));\n\n"
    "        // The real UDS module throws a fatal error if this assert fails.\n",
    "BeginHostingNetwork request trace",
)

patch_once(
    "        node_info[0] = current_node;\n\n"
    "        // If the game has a preferred channel, use that instead.\n",
    "        node_info[0] = current_node;\n"
    "        LOG_WARNING(Service_NWM,\n"
    "                    \"(YW2 TRACE) BeginHostingNetwork status status={} self={} total={} max={} \"\n"
    "                    \"bitmask=0x{:X} changed=0x{:X}\",\n"
    "                    static_cast<u32>(connection_status.status),\n"
    "                    static_cast<u16>(connection_status.network_node_id),\n"
    "                    static_cast<u32>(connection_status.total_nodes),\n"
    "                    static_cast<u32>(connection_status.max_nodes),\n"
    "                    static_cast<u32>(connection_status.node_bitmask),\n"
    "                    static_cast<u32>(connection_status.changed_nodes));\n\n"
    "        // If the game has a preferred channel, use that instead.\n",
    "BeginHostingNetwork status trace",
)

patch_once(
    "void NWM_UDS::StartConnectionSequence(const MacAddress& server) {\n"
    "    using Network::WifiPacket;\n"
    "    WifiPacket auth_request;\n"
    "    {\n"
    "        std::scoped_lock lock(connection_status_mutex);\n"
    "        connection_status.status = NetworkStatus::Connecting;\n\n"
    "        // TODO(Subv): Handle timeout.\n",
    "void NWM_UDS::StartConnectionSequence(const MacAddress& server) {\n"
    "    using Network::WifiPacket;\n"
    "    WifiPacket auth_request;\n"
    "    {\n"
    "        std::scoped_lock lock(connection_status_mutex);\n"
    "        connection_status.status = NetworkStatus::Connecting;\n"
    "        LOG_WARNING(Service_NWM,\n"
    "                    \"(YW2 TRACE) StartConnectionSequence status={} server_mac={:02X}:{:02X}:{:02X}:{:02X}:{:02X}:{:02X} \"\n"
    "                    \"channel={} conn_type={}\",\n"
    "                    static_cast<u32>(connection_status.status), static_cast<u8>(server[0]),\n"
    "                    static_cast<u8>(server[1]), static_cast<u8>(server[2]),\n"
    "                    static_cast<u8>(server[3]), static_cast<u8>(server[4]),\n"
    "                    static_cast<u8>(server[5]), static_cast<u32>(network_channel),\n"
    "                    static_cast<u32>(conn_type));\n\n"
    "        // TODO(Subv): Handle timeout.\n",
    "StartConnectionSequence trace",
)

patch_once(
    "void NWM_UDS::ConnectToNetworkHLE(NetworkInfo net_info, u8 connection_type,\n"
    "                                  std::vector<u8> passphrase) {\n"
    "    network_info = net_info;\n\n"
    "    conn_type = static_cast<ConnectionType>(connection_type);\n",
    "void NWM_UDS::ConnectToNetworkHLE(NetworkInfo net_info, u8 connection_type,\n"
    "                                  std::vector<u8> passphrase) {\n"
    "    network_info = net_info;\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) ConnectToNetworkHLE type={} passphrase_size={} max_nodes={} \"\n"
    "                \"total_nodes={} channel={} app_size={}\",\n"
    "                static_cast<u8>(connection_type), passphrase.size(),\n"
    "                static_cast<u32>(network_info.max_nodes),\n"
    "                static_cast<u32>(network_info.total_nodes),\n"
    "                static_cast<u32>(network_info.channel),\n"
    "                static_cast<u32>(network_info.application_data_size));\n\n"
    "    conn_type = static_cast<ConnectionType>(connection_type);\n",
    "ConnectToNetworkHLE trace",
)

patch_once(
    "    static constexpr std::chrono::nanoseconds UDSConnectionTimeout{5000000000};\n\n"
    "    connection_event = ctx.SleepClientThread(\"uds::ConnectToNetwork\", UDSConnectionTimeout,\n",
    "    static constexpr std::chrono::nanoseconds UDSConnectionTimeout{5000000000};\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) ConnectToNetwork sleep command_id=0x{:X} type={} timeout_ns={}\",\n"
    "                command_id, static_cast<u8>(connection_type), UDSConnectionTimeout.count());\n\n"
    "    connection_event = ctx.SleepClientThread(\"uds::ConnectToNetwork\", UDSConnectionTimeout,\n",
    "ConnectToNetwork sleep trace",
)

patch_once(
    "        if (reason == Kernel::ThreadWakeupReason::Timeout) {\n"
    "            LOG_ERROR(Service_NWM, \"timed out when trying to connect to UDS server\");\n",
    "        if (reason == Kernel::ThreadWakeupReason::Timeout) {\n"
    "            LOG_WARNING(Service_NWM,\n"
    "                        \"(YW2 TRACE) ConnectToNetwork wake timeout command_id=0x{:X}\",\n"
    "                        command_id);\n"
    "            LOG_ERROR(Service_NWM, \"timed out when trying to connect to UDS server\");\n",
    "ConnectToNetwork timeout trace",
)

patch_once(
    "        rb.Push(ResultSuccess);\n"
    "        LOG_DEBUG(Service_NWM, \"connection sequence finished\");\n",
    "        rb.Push(ResultSuccess);\n"
    "        LOG_WARNING(Service_NWM,\n"
    "                    \"(YW2 TRACE) ConnectToNetwork wake success command_id=0x{:X}\",\n"
    "                    command_id);\n"
    "        LOG_DEBUG(Service_NWM, \"connection sequence finished\");\n",
    "ConnectToNetwork success trace",
)

patch_once(
    "    switch (packet.type) {\n"
    "    case Network::WifiPacket::PacketType::Beacon:\n",
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) OnWifiPacketReceived type={} channel={} data_size={} status={}\",\n"
    "                static_cast<u32>(packet.type), static_cast<u32>(packet.channel),\n"
    "                packet.data.size(), static_cast<u32>(connection_status.status));\n"
    "    switch (packet.type) {\n"
    "    case Network::WifiPacket::PacketType::Beacon:\n",
    "OnWifiPacketReceived trace",
)

patch_once(
    "void NWM_UDS::SetProbeResponseParam(Kernel::HLERequestContext& ctx) {\n"
    "    IPC::RequestParser rp(ctx);\n\n"
    "    u32 param1 = rp.Pop<u32>();\n"
    "    u32 param2 = rp.Pop<u32>();\n\n"
    "    LOG_WARNING(Service_NWM, \"(STUBBED) SetProbeResponseParam called, param1=0x{:08X}, param2=0x{:08X}\", param1, param2);\n\n"
    "    if (connection_status_event) {\n",
    "void NWM_UDS::SetProbeResponseParam(Kernel::HLERequestContext& ctx) {\n"
    "    IPC::RequestParser rp(ctx);\n\n"
    "    u32 param1 = rp.Pop<u32>();\n"
    "    u32 param2 = rp.Pop<u32>();\n\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) SetProbeResponseParam param1=0x{:08X} param2=0x{:08X} \"\n"
    "                \"status={} self={} total={} max={} bitmask=0x{:X} changed=0x{:X} reason={}\",\n"
    "                param1, param2, static_cast<u32>(connection_status.status),\n"
    "                static_cast<u16>(connection_status.network_node_id),\n"
    "                static_cast<u32>(connection_status.total_nodes),\n"
    "                static_cast<u32>(connection_status.max_nodes),\n"
    "                static_cast<u32>(connection_status.node_bitmask),\n"
    "                static_cast<u32>(connection_status.changed_nodes),\n"
    "                static_cast<u32>(connection_status.status_change_reason));\n\n"
    "    if (connection_status_event) {\n",
    "SetProbeResponseParam state trace",
)

path.write_text(text)
print("Applied YW2 UDS state trace patch")
