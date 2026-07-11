from pathlib import Path

path = Path("src/core/hle/service/nwm/nwm_uds.cpp")
text = path.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 trace patch marker not found: {label}")
    text = text.replace(old, new, 1)


patch_once(
    "    SecureDataHeader secure_data;\n",
    "    SecureDataHeader secure_data{};\n",
    "zero-initialize PullPacket secure_data",
)

patch_once(
    "    std::vector<u8> input_buffer = rp.PopStaticBuffer();\n\n"
    "    IPC::RequestBuilder rb = rp.MakeBuilder(1, 0);\n",
    "    std::vector<u8> input_buffer = rp.PopStaticBuffer();\n"
    "    const auto request_byte_at = [&input_buffer](std::size_t index) -> u32 {\n"
    "        return index < input_buffer.size() ? input_buffer[index] : 0;\n"
    "    };\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) SendTo IPC dest_node_id={} data_channel={} data_size={} \"\n"
    "                \"flags=0x{:02X} buffer_size={} head={:02X} {:02X} {:02X} {:02X} \"\n"
    "                \"{:02X} {:02X} {:02X} {:02X}\",\n"
    "                dest_node_id, data_channel, data_size, flags, input_buffer.size(),\n"
    "                request_byte_at(0), request_byte_at(1), request_byte_at(2),\n"
    "                request_byte_at(3), request_byte_at(4), request_byte_at(5),\n"
    "                request_byte_at(6), request_byte_at(7));\n\n"
    "    IPC::RequestBuilder rb = rp.MakeBuilder(1, 0);\n",
    "SendTo IPC trace",
)

patch_once(
    "    ASSERT(input_buffer.size() >= data_size);\n"
    "    input_buffer.resize(data_size);\n\n"
    "    std::scoped_lock lock(connection_status_mutex);\n",
    "    ASSERT(input_buffer.size() >= data_size);\n"
    "    input_buffer.resize(data_size);\n"
    "    const auto payload_byte_at = [&input_buffer](std::size_t index) -> u32 {\n"
    "        return index < input_buffer.size() ? input_buffer[index] : 0;\n"
    "    };\n\n"
    "    std::scoped_lock lock(connection_status_mutex);\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) SendToHLE status={} self_node={} total_nodes={} dest={} \"\n"
    "                \"channel={} size={} flags=0x{:02X} head={:02X} {:02X} {:02X} {:02X} \"\n"
    "                \"{:02X} {:02X} {:02X} {:02X}\",\n"
    "                static_cast<u32>(connection_status.status),\n"
    "                static_cast<u16>(connection_status.network_node_id),\n"
    "                static_cast<u32>(connection_status.total_nodes), dest_node_id, data_channel,\n"
    "                data_size, flags, payload_byte_at(0), payload_byte_at(1), payload_byte_at(2),\n"
    "                payload_byte_at(3), payload_byte_at(4), payload_byte_at(5), payload_byte_at(6),\n"
    "                payload_byte_at(7));\n",
    "SendToHLE trace",
)

patch_once(
    "    const auto secure_data = ParseSecureDataHeader(packet.data);\n"
    "    std::scoped_lock lock{connection_status_mutex, system.Kernel().GetHLELock()};\n\n",
    "    const auto secure_data = ParseSecureDataHeader(packet.data);\n"
    "    std::scoped_lock lock{connection_status_mutex, system.Kernel().GetHLELock()};\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) HandleSecureDataPacket status={} self_node={} src={} dest={} \"\n"
    "                \"channel={} actual_size={} raw_size={} is_management={} binds={}\",\n"
    "                static_cast<u32>(connection_status.status),\n"
    "                static_cast<u16>(connection_status.network_node_id),\n"
    "                static_cast<u16>(secure_data.src_node_id),\n"
    "                static_cast<u16>(secure_data.dest_node_id),\n"
    "                static_cast<u8>(secure_data.data_channel),\n"
    "                static_cast<u32>(secure_data.GetActualDataSize()), packet.data.size(),\n"
    "                secure_data.is_management, channel_data.size());\n\n",
    "HandleSecureDataPacket entry trace",
)

patch_once(
    "    if (secure_data.src_node_id == connection_status.network_node_id) {\n"
    "        // Ignore packets that came from ourselves.\n"
    "        return;\n"
    "    }\n",
    "    if (secure_data.src_node_id == connection_status.network_node_id) {\n"
    "        LOG_WARNING(Service_NWM, \"(YW2 TRACE) Ignored SecureDataPacket from self node {}\",\n"
    "                    static_cast<u16>(secure_data.src_node_id));\n"
    "        // Ignore packets that came from ourselves.\n"
    "        return;\n"
    "    }\n",
    "SecureData self-ignore trace",
)

patch_once(
    "    if (channel_info == channel_data.end()) {\n"
    "        return;\n"
    "    }\n",
    "    if (channel_info == channel_data.end()) {\n"
    "        LOG_WARNING(Service_NWM,\n"
    "                    \"(YW2 TRACE) Ignored SecureDataPacket with unbound data_channel={}\",\n"
    "                    static_cast<u8>(secure_data.data_channel));\n"
    "        return;\n"
    "    }\n",
    "SecureData unbound-channel trace",
)

patch_once(
    "    if (channel_info->second.network_node_id != BroadcastNetworkNodeId &&\n"
    "        channel_info->second.network_node_id != secure_data.src_node_id) {\n"
    "        return;\n"
    "    }\n",
    "    if (channel_info->second.network_node_id != BroadcastNetworkNodeId &&\n"
    "        channel_info->second.network_node_id != secure_data.src_node_id) {\n"
    "        LOG_WARNING(Service_NWM,\n"
    "                    \"(YW2 TRACE) Ignored SecureDataPacket from src={} for bind node={} channel={}\",\n"
    "                    static_cast<u16>(secure_data.src_node_id),\n"
    "                    static_cast<u16>(channel_info->second.network_node_id),\n"
    "                    static_cast<u8>(secure_data.data_channel));\n"
    "        return;\n"
    "    }\n",
    "SecureData bind-node mismatch trace",
)

patch_once(
    "    // Add the received packet to the data queue.\n"
    "    channel_info->second.received_packets.emplace_back(packet.data);\n\n"
    "    // Signal the data event. We can do this directly because we locked hle_lock\n",
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) Queue SecureDataPacket channel={} queue_before={} src={} dest={}\",\n"
    "                static_cast<u8>(secure_data.data_channel),\n"
    "                channel_info->second.received_packets.size(),\n"
    "                static_cast<u16>(secure_data.src_node_id),\n"
    "                static_cast<u16>(secure_data.dest_node_id));\n"
    "    // Add the received packet to the data queue.\n"
    "    channel_info->second.received_packets.emplace_back(packet.data);\n\n"
    "    // Signal the data event. We can do this directly because we locked hle_lock\n",
    "SecureData queue trace",
)

patch_once(
    "    IPC::RequestBuilder rb = rp.MakeBuilder(3, 2);\n\n"
    "    rb.Push(ResultSuccess);\n",
    "    const auto output_byte_at = [&output_buffer](std::size_t index) -> u32 {\n"
    "        return index < output_buffer.size() ? output_buffer[index] : 0;\n"
    "    };\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) PullPacket result bind_node_id=0x{:X} size={} src={} \"\n"
    "                \"head={:02X} {:02X} {:02X} {:02X} {:02X} {:02X} {:02X} {:02X}\",\n"
    "                bind_node_id, *ret, static_cast<u16>(secure_data.src_node_id),\n"
    "                output_byte_at(0), output_byte_at(1), output_byte_at(2), output_byte_at(3),\n"
    "                output_byte_at(4), output_byte_at(5), output_byte_at(6), output_byte_at(7));\n\n"
    "    IPC::RequestBuilder rb = rp.MakeBuilder(3, 2);\n\n"
    "    rb.Push(ResultSuccess);\n",
    "PullPacket result trace",
)

patch_once(
    "    if (channel->second.received_packets.empty()) {\n"
    "        output_buffer.resize(buff_size);\n"
    "        return int(0);\n"
    "    }\n",
    "    if (channel->second.received_packets.empty()) {\n"
    "        LOG_WARNING(Service_NWM,\n"
    "                    \"(YW2 TRACE) PullPacketHLE empty bind_node_id=0x{:X} channel={} \"\n"
    "                    \"bound_node={} buff_size={} max_out={}\",\n"
    "                    bind_node_id, static_cast<u8>(channel->second.channel),\n"
    "                    static_cast<u16>(channel->second.network_node_id), buff_size,\n"
    "                    max_out_buff_size);\n"
    "        output_buffer.resize(buff_size);\n"
    "        return int(0);\n"
    "    }\n",
    "PullPacketHLE empty trace",
)

patch_once(
    "    // Write the actual data.\n"
    "    std::memcpy(output_buffer.data(),\n"
    "                next_packet.data() + sizeof(LLCHeader) + sizeof(SecureDataHeader), data_size);\n\n"
    "    channel->second.received_packets.pop_front();\n",
    "    // Write the actual data.\n"
    "    std::memcpy(output_buffer.data(),\n"
    "                next_packet.data() + sizeof(LLCHeader) + sizeof(SecureDataHeader), data_size);\n"
    "    const auto pulled_byte_at = [&output_buffer](std::size_t index) -> u32 {\n"
    "        return index < output_buffer.size() ? output_buffer[index] : 0;\n"
    "    };\n"
    "    LOG_WARNING(Service_NWM,\n"
    "                \"(YW2 TRACE) PullPacketHLE data bind_node_id=0x{:X} channel={} src={} dest={} \"\n"
    "                \"size={} queue_before_pop={} head={:02X} {:02X} {:02X} {:02X} {:02X} {:02X} \"\n"
    "                \"{:02X} {:02X}\",\n"
    "                bind_node_id, static_cast<u8>(secure_data.data_channel),\n"
    "                static_cast<u16>(secure_data.src_node_id),\n"
    "                static_cast<u16>(secure_data.dest_node_id), data_size,\n"
    "                channel->second.received_packets.size(), pulled_byte_at(0), pulled_byte_at(1),\n"
    "                pulled_byte_at(2), pulled_byte_at(3), pulled_byte_at(4), pulled_byte_at(5),\n"
    "                pulled_byte_at(6), pulled_byte_at(7));\n\n"
    "    channel->second.received_packets.pop_front();\n",
    "PullPacketHLE data trace",
)

path.write_text(text)
print("Applied YW2 UDS trace patch")
