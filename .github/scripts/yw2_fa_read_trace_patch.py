from pathlib import Path


def patch_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"YW2 FA/FS read trace patch marker not found: {label}")
    return text.replace(old, new, 1)


# Low-level RomFS backend read overlap trace. This confirms whether a RomFS read covers the
# target strings.
ivfc_path = Path("src/core/file_sys/ivfc_archive.cpp")
ivfc_text = ivfc_path.read_text()

if "debug.azahar.yw2_fa_read_trace" not in ivfc_text:
    if "#include <cstdlib>" not in ivfc_text:
        ivfc_text = patch_once(
            ivfc_text,
            "#include <cstring>\n",
            "#include <cstdlib>\n"
            "#include <cstring>\n"
            "#include <limits>\n"
            "#ifdef ANDROID\n"
            "#include <sys/system_properties.h>\n"
            "#endif\n",
            "FA read trace includes",
        )

    ivfc_text = patch_once(
        ivfc_text,
        "namespace FileSys {\n\n",
        "namespace FileSys {\n\n"
        "namespace {\n\n"
        "bool YW2FaReadTraceEnabled() {\n"
        "#ifdef ANDROID\n"
        "    char value[PROP_VALUE_MAX] = {};\n"
        "    if (__system_property_get(\"debug.azahar.yw2_fa_read_trace\", value) > 0) {\n"
        "        return std::strcmp(value, \"0\") != 0 && std::strcmp(value, \"false\") != 0 &&\n"
        "               std::strcmp(value, \"off\") != 0;\n"
        "    }\n"
        "#endif\n"
        "\n"
        "    const char* env = std::getenv(\"AZAHAR_YW2_FA_READ_TRACE\");\n"
        "    return env != nullptr && std::strcmp(env, \"0\") != 0 &&\n"
        "           std::strcmp(env, \"false\") != 0 && std::strcmp(env, \"off\") != 0;\n"
        "}\n\n"
        "struct YW2FaReadTarget {\n"
        "    u64 offset;\n"
        "    u64 size;\n"
        "    const char* name;\n"
        "};\n\n"
        "constexpr YW2FaReadTarget YW2_FA_READ_TARGETS[] = {\n"
        "    {0x37715EE2ULL, 0x2AULL, \"comm_failed\"},\n"
        "    {0x37715F0DULL, 0x2AULL, \"connect_failed\"},\n"
        "    {0x37716378ULL, 0xB2ULL, \"comm_start_warning\"},\n"
        "    {0x37717DC5ULL, 0x31ULL, \"member_start_confirm\"},\n"
        "    {0x37717EA3ULL, 0x53ULL, \"four_member_start_confirm\"},\n"
        "};\n\n"
        "bool YW2RangesOverlap(u64 offset, std::size_t length, u64 target_offset, u64 target_size) {\n"
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
        "void TraceYW2FaRead(u64 offset, std::size_t length, const char* backend) {\n"
        "    if (!YW2FaReadTraceEnabled()) {\n"
        "        return;\n"
        "    }\n"
        "\n"
        "    const u64 length64 = static_cast<u64>(length);\n"
        "    const u64 end = offset > std::numeric_limits<u64>::max() - length64\n"
        "                        ? std::numeric_limits<u64>::max()\n"
        "                        : offset + length64;\n"
        "\n"
        "    for (const auto& target : YW2_FA_READ_TARGETS) {\n"
        "        if (!YW2RangesOverlap(offset, length, target.offset, target.size)) {\n"
        "            continue;\n"
        "        }\n"
        "\n"
        "        LOG_WARNING(Service_FS,\n"
        "                    \"(YW2 FA READ) backend={} hit={} read=[0x{:X},0x{:X}) len=0x{:X} target=[0x{:X},0x{:X})\",\n"
        "                    backend, target.name, offset, end, length64, target.offset,\n"
        "                    target.offset + target.size);\n"
        "    }\n"
        "}\n\n"
        "} // namespace\n\n",
        "FA read trace helper",
    )

ivfc_text = patch_once(
    ivfc_text,
    "    LOG_TRACE(Service_FS, \"called offset={}, length={}\", offset, length);\n"
    "    return romfs_file->ReadFile(offset, length, buffer);\n",
    "    LOG_TRACE(Service_FS, \"called offset={}, length={}\", offset, length);\n"
    "    TraceYW2FaRead(offset, length, \"IVFCFile\");\n"
    "    return romfs_file->ReadFile(offset, length, buffer);\n",
    "IVFCFile::Read trace call",
)

ivfc_text = patch_once(
    ivfc_text,
    "    LOG_TRACE(Service_FS, \"called offset={}, length={}\", offset, length);\n"
    "    std::size_t read_length = (std::size_t)std::min((u64)length, data_size - offset);\n",
    "    LOG_TRACE(Service_FS, \"called offset={}, length={}\", offset, length);\n"
    "    TraceYW2FaRead(offset, length, \"IVFCFileInMemory\");\n"
    "    std::size_t read_length = (std::size_t)std::min((u64)length, data_size - offset);\n",
    "IVFCFileInMemory::Read trace call",
)

ivfc_path.write_text(ivfc_text)

# HLE FS::File::Read caller-context trace. This logs the guest thread PC/LR when the same
# target offsets are requested through FS IPC, which helps locate the guest-side preload caller.
fs_path = Path("src/core/hle/service/fs/file.cpp")
fs_text = fs_path.read_text()

if "debug.azahar.yw2_fs_read_trace" not in fs_text:
    fs_text = patch_once(
        fs_text,
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

    fs_text = patch_once(
        fs_text,
        "#include \"core/hle/kernel/server_session.h\"\n",
        "#include \"core/hle/kernel/server_session.h\"\n"
        "#include \"core/hle/kernel/thread.h\"\n",
        "FS read trace thread include",
    )

    fs_text = patch_once(
        fs_text,
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

fs_text = patch_once(
    fs_text,
    "    const bool allows_cache_reads = backend->AllowsCachedReads();\n\n"
    "    // Conventional reading if the backend does not support cache.\n",
    "    const bool allows_cache_reads = backend->AllowsCachedReads();\n"
    "    const bool yw2_cache_ready = allows_cache_reads ? backend->CacheReady(offset, length) : false;\n"
    "    TraceYW2FsRead(*this, ctx, offset, length, yw2_cache_ready, allows_cache_reads);\n\n"
    "    // Conventional reading if the backend does not support cache.\n",
    "FS read trace call after adjusted offset",
)

fs_text = patch_once(
    fs_text,
    "    async_data->cache_ready = backend->CacheReady(offset, length);\n",
    "    async_data->cache_ready = yw2_cache_ready;\n",
    "reuse FS read cache_ready result",
)

fs_path.write_text(fs_text)

print("Patched YW2 FA read trace")
print("Patched YW2 FS read caller trace")
