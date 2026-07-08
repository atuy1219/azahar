from pathlib import Path

path = Path("src/core/hle/service/fs/file.cpp")
text = path.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 FS read trace patch marker not found: {label}")
    text = text.replace(old, new, 1)


if "debug.azahar.yw2_fs_read_trace" not in text:
    patch_once(
        "#include <boost/serialization/unique_ptr.hpp>\n",
        "#include <cstdlib>\n"
        "#include <cstring>\n"
        "#include <limits>\n"
        "#ifdef ANDROID\n"
        "#include <sys/system_properties.h>\n"
        "#endif\n"
        "#include <boost/serialization/unique_ptr.hpp>\n",
        "FS read trace includes",
    )

    patch_once(
        "#include \"core/hle/kernel/server_session.h\"\n",
        "#include \"core/hle/kernel/server_session.h\"\n"
        "#include \"core/hle/kernel/thread.h\"\n",
        "FS read trace thread include",
    )

    patch_once(
        "namespace Service::FS {\n\n",
        "namespace Service::FS {\n\n"
        "namespace {\n\n"
        "bool YW2FsReadTraceEnabled() {\n"
        "#ifdef ANDROID\n"
        "    char value[PROP_VALUE_MAX] = {};\n"
        "    if (__system_property_get(\"debug.azahar.yw2_fs_read_trace\", value) > 0) {\n"
        "        return std::strcmp(value, \"0\") != 0 && std::strcmp(value, \"false\") != 0 &&\n"
        "               std::strcmp(value, \"off\") != 0;\n"
        "    }\n"
        "#endif\n"
        "\n"
        "    const char* env = std::getenv(\"AZAHAR_YW2_FS_READ_TRACE\");\n"
        "    return env != nullptr && std::strcmp(env, \"0\") != 0 &&\n"
        "           std::strcmp(env, \"false\") != 0 && std::strcmp(env, \"off\") != 0;\n"
        "}\n\n"
        "struct YW2FsReadTarget {\n"
        "    u64 offset;\n"
        "    u64 size;\n"
        "    const char* name;\n"
        "};\n\n"
        "constexpr YW2FsReadTarget YW2_FS_READ_TARGETS[] = {\n"
        "    {0x37715EE2ULL, 0x2AULL, \"comm_failed\"},\n"
        "    {0x37715F0DULL, 0x2AULL, \"connect_failed\"},\n"
        "    {0x37716378ULL, 0xB2ULL, \"comm_start_warning\"},\n"
        "    {0x37717DC5ULL, 0x31ULL, \"member_start_confirm\"},\n"
        "    {0x37717EA3ULL, 0x53ULL, \"four_member_start_confirm\"},\n"
        "};\n\n"
        "bool YW2FsRangesOverlap(u64 offset, std::size_t length, u64 target_offset, u64 target_size) {\n"
        "    if (length == 0 || target_size == 0) {\n"
        "        return false;\n"
        "    }\n"
        "\n"
        "    const u64 length64 = static_cast<u64>(length);\n"
        "    const u64 end = offset > std::numeric_limits<u64>::max() - length64\n"
        "                        ? std::numeric_limits<u64>::max()\n"
        "                        : offset + length64;\n"
        "    const u64 target_end = target_offset > std::numeric_limits<u64>::max() - target_size\n"
        "                               ? std::numeric_limits<u64>::max()\n"
        "                               : target_offset + target_size;\n"
        "\n"
        "    return offset < target_end && target_offset < end;\n"
        "}\n\n"
        "void TraceYW2FsRead(const File& file, Kernel::HLERequestContext& ctx, u64 offset,\n"
        "                    std::size_t length, bool cache_ready, bool allows_cache_reads) {\n"
        "    if (!YW2FsReadTraceEnabled()) {\n"
        "        return;\n"
        "    }\n"
        "\n"
        "    const u64 length64 = static_cast<u64>(length);\n"
        "    const u64 end = offset > std::numeric_limits<u64>::max() - length64\n"
        "                        ? std::numeric_limits<u64>::max()\n"
        "                        : offset + length64;\n"
        "    auto thread = ctx.ClientThread();\n"
        "    const u32 tid = thread ? thread->GetThreadId() : 0;\n"
        "    const u32 pc = thread ? thread->context.GetProgramCounter() : 0;\n"
        "    const u32 lr = thread ? thread->context.GetLinkRegister() : 0;\n"
        "\n"
        "    for (const auto& target : YW2_FS_READ_TARGETS) {\n"
        "        if (!YW2FsRangesOverlap(offset, length, target.offset, target.size)) {\n"
        "            continue;\n"
        "        }\n"
        "\n"
        "        LOG_WARNING(Service_FS,\n"
        "                    \"(YW2 FS READ) hit={} tid={} pc=0x{:08X} lr=0x{:08X} read=[0x{:X},0x{:X}) len=0x{:X} target=[0x{:X},0x{:X}) cache_ready={} allows_cache={} file={}\",\n"
        "                    target.name, tid, pc, lr, offset, end, length64, target.offset,\n"
        "                    target.offset + target.size, cache_ready, allows_cache_reads, file.GetName());\n"
        "    }\n"
        "}\n\n"
        "} // namespace\n\n",
        "FS read trace helper",
    )

patch_once(
    "    const bool allows_cache_reads = backend->AllowsCachedReads();\n\n"
    "    // Conventional reading if the backend does not support cache.\n",
    "    const bool allows_cache_reads = backend->AllowsCachedReads();\n"
    "    const bool yw2_cache_ready = allows_cache_reads ? backend->CacheReady(offset, length) : false;\n"
    "    TraceYW2FsRead(*this, ctx, offset, length, yw2_cache_ready, allows_cache_reads);\n\n"
    "    // Conventional reading if the backend does not support cache.\n",
    "FS read trace call after adjusted offset",
)

patch_once(
    "    async_data->cache_ready = backend->CacheReady(offset, length);\n",
    "    async_data->cache_ready = yw2_cache_ready;\n",
    "reuse FS read cache_ready result",
)

path.write_text(text)
print("Patched YW2 FS read trace")
