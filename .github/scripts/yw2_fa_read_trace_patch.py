from pathlib import Path

path = Path("src/core/file_sys/ivfc_archive.cpp")
text = path.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 FA read trace patch marker not found: {label}")
    text = text.replace(old, new, 1)


if "debug.azahar.yw2_fa_read_trace" not in text:
    if "#include <cstdlib>" not in text:
        patch_once(
            "#include <cstring>\n",
            "#include <cstdlib>\n"
            "#include <cstring>\n"
            "#include <limits>\n"
            "#ifdef ANDROID\n"
            "#include <sys/system_properties.h>\n"
            "#endif\n",
            "FA read trace includes",
        )

    patch_once(
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

patch_once(
    "    LOG_TRACE(Service_FS, \"called offset={}, length={}\", offset, length);\n"
    "    return romfs_file->ReadFile(offset, length, buffer);\n",
    "    LOG_TRACE(Service_FS, \"called offset={}, length={}\", offset, length);\n"
    "    TraceYW2FaRead(offset, length, \"IVFCFile\");\n"
    "    return romfs_file->ReadFile(offset, length, buffer);\n",
    "IVFCFile::Read trace call",
)

patch_once(
    "    LOG_TRACE(Service_FS, \"called offset={}, length={}\", offset, length);\n"
    "    std::size_t read_length = (std::size_t)std::min((u64)length, data_size - offset);\n",
    "    LOG_TRACE(Service_FS, \"called offset={}, length={}\", offset, length);\n"
    "    TraceYW2FaRead(offset, length, \"IVFCFileInMemory\");\n"
    "    std::size_t read_length = (std::size_t)std::min((u64)length, data_size - offset);\n",
    "IVFCFileInMemory::Read trace call",
)

path.write_text(text)
print("Patched YW2 FA read trace")
