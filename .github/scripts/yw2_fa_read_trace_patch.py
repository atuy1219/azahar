from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"YW2 FA/FS read trace patch marker not found: {label}")
    return text.replace(old, new, 1)


TARGETS_CPP = (
    "struct YW2ReadTarget {\n"
    "    u64 offset;\n"
    "    u64 size;\n"
    "    const char* name;\n"
    "};\n\n"
    "constexpr YW2ReadTarget YW2_READ_TARGETS[] = {\n"
    "    {0x37715EE2ULL, 0x2AULL, \"comm_failed\"},\n"
    "    {0x37715F0DULL, 0x2AULL, \"connect_failed\"},\n"
    "    {0x37716378ULL, 0xB2ULL, \"comm_start_warning\"},\n"
    "    {0x37717DC5ULL, 0x31ULL, \"member_start_confirm\"},\n"
    "    {0x37717EA3ULL, 0x53ULL, \"four_member_start_confirm\"},\n"
    "};\n\n"
    "bool YW2RangesOverlap(u64 offset, std::size_t length, u64 target_offset, u64 target_size) {\n"
    "    if (length == 0 || target_size == 0) {\n"
    "        return false;\n"
    "    }\n\n"
    "    const u64 length64 = static_cast<u64>(length);\n"
    "    const u64 end = offset > std::numeric_limits<u64>::max() - length64\n"
    "                        ? std::numeric_limits<u64>::max()\n"
    "                        : offset + length64;\n"
    "    const u64 target_end = target_offset > std::numeric_limits<u64>::max() - target_size\n"
    "                               ? std::numeric_limits<u64>::max()\n"
    "                               : target_offset + target_size;\n\n"
    "    return offset < target_end && target_offset < end;\n"
    "}\n\n"
)


def patch_ivfc() -> None:
    path = Path("src/core/file_sys/ivfc_archive.cpp")
    text = path.read_text()

    if "debug.azahar.yw2_fa_read_trace" not in text:
        if "#include <cstdlib>" not in text:
            text = replace_once(
                text,
                "#include <cstring>\n",
                "#include <cstdlib>\n"
                "#include <cstring>\n"
                "#include <limits>\n"
                "#ifdef ANDROID\n"
                "#include <sys/system_properties.h>\n"
                "#endif\n",
                "FA read trace includes",
            )

        helper = (
            "namespace FileSys {\n\n"
            "namespace {\n\n"
            "bool YW2FaReadTraceEnabled() {\n"
            "#ifdef ANDROID\n"
            "    char value[PROP_VALUE_MAX] = {};\n"
            "    if (__system_property_get(\"debug.azahar.yw2_fa_read_trace\", value) > 0) {\n"
            "        return std::strcmp(value, \"0\") != 0 && std::strcmp(value, \"false\") != 0 &&\n"
            "               std::strcmp(value, \"off\") != 0;\n"
            "    }\n"
            "#endif\n\n"
            "    const char* env = std::getenv(\"AZAHAR_YW2_FA_READ_TRACE\");\n"
            "    return env != nullptr && std::strcmp(env, \"0\") != 0 &&\n"
            "           std::strcmp(env, \"false\") != 0 && std::strcmp(env, \"off\") != 0;\n"
            "}\n\n"
            + TARGETS_CPP +
            "void TraceYW2FaRead(u64 offset, std::size_t length, const char* backend) {\n"
            "    if (!YW2FaReadTraceEnabled()) {\n"
            "        return;\n"
            "    }\n\n"
            "    const u64 length64 = static_cast<u64>(length);\n"
            "    const u64 end = offset > std::numeric_limits<u64>::max() - length64\n"
            "                        ? std::numeric_limits<u64>::max()\n"
            "                        : offset + length64;\n\n"
            "    for (const auto& target : YW2_READ_TARGETS) {\n"
            "        if (!YW2RangesOverlap(offset, length, target.offset, target.size)) {\n"
            "            continue;\n"
            "        }\n\n"
            "        LOG_WARNING(Service_FS,\n"
            "                    \"(YW2 FA READ) backend={} hit={} read=[0x{:X},0x{:X}) len=0x{:X} target=[0x{:X},0x{:X})\",\n"
            "                    backend, target.name, offset, end, length64, target.offset,\n"
            "                    target.offset + target.size);\n"
            "    }\n"
            "}\n\n"
            "} // namespace\n\n"
        )
        text = replace_once(text, "namespace FileSys {\n\n", helper, "FA read trace helper")

    if 'TraceYW2FaRead(offset, length, "IVFCFile");' not in text:
        text = replace_once(
            text,
            "    LOG_TRACE(Service_FS, \"called offset={}, length={}\", offset, length);\n"
            "    return romfs_file->ReadFile(offset, length, buffer);\n",
            "    LOG_TRACE(Service_FS, \"called offset={}, length={}\", offset, length);\n"
            "    TraceYW2FaRead(offset, length, \"IVFCFile\");\n"
            "    return romfs_file->ReadFile(offset, length, buffer);\n",
            "IVFCFile::Read trace call",
        )

    if 'TraceYW2FaRead(offset, length, "IVFCFileInMemory");' not in text:
        text = replace_once(
            text,
            "    LOG_TRACE(Service_FS, \"called offset={}, length={}\", offset, length);\n"
            "    std::size_t read_length = (std::size_t)std::min((u64)length, data_size - offset);\n",
            "    LOG_TRACE(Service_FS, \"called offset={}, length={}\", offset, length);\n"
            "    TraceYW2FaRead(offset, length, \"IVFCFileInMemory\");\n"
            "    std::size_t read_length = (std::size_t)std::min((u64)length, data_size - offset);\n",
            "IVFCFileInMemory::Read trace call",
        )

    path.write_text(text)


def patch_fs_file() -> None:
    path = Path("src/core/hle/service/fs/file.cpp")
    text = path.read_text()

    if "debug.azahar.yw2_fs_read_trace" not in text:
        text = replace_once(
            text,
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
        text = replace_once(
            text,
            "#include \"core/core.h\"\n",
            "#include \"core/core.h\"\n"
            "#include \"core/memory.h\"\n",
            "FS read trace memory include",
        )
        text = replace_once(
            text,
            "#include \"core/hle/kernel/server_session.h\"\n",
            "#include \"core/hle/kernel/server_session.h\"\n"
            "#include \"core/hle/kernel/thread.h\"\n",
            "FS read trace thread include",
        )

        helper = (
            "namespace Service::FS {\n\n"
            "namespace {\n\n"
            "bool YW2FsReadTraceEnabled() {\n"
            "#ifdef ANDROID\n"
            "    char value[PROP_VALUE_MAX] = {};\n"
            "    if (__system_property_get(\"debug.azahar.yw2_fs_read_trace\", value) > 0) {\n"
            "        return std::strcmp(value, \"0\") != 0 && std::strcmp(value, \"false\") != 0 &&\n"
            "               std::strcmp(value, \"off\") != 0;\n"
            "    }\n"
            "#endif\n\n"
            "    const char* env = std::getenv(\"AZAHAR_YW2_FS_READ_TRACE\");\n"
            "    return env != nullptr && std::strcmp(env, \"0\") != 0 &&\n"
            "           std::strcmp(env, \"false\") != 0 && std::strcmp(env, \"off\") != 0;\n"
            "}\n\n"
            + TARGETS_CPP +
            "u32 YW2ReadWord(VAddr addr) {\n"
            "    if (addr == 0) {\n"
            "        return 0xFFFFFFFF;\n"
            "    }\n"
            "    const auto value = Core::System::GetInstance().Memory().Read32OrNullopt(addr);\n"
            "    return value ? *value : 0xFFFFFFFF;\n"
            "}\n\n"
            "void TraceYW2PtrDump(const char* label, u32 base) {\n"
            "    if (base == 0 || base == 0xFFFFFFFF) {\n"
            "        return;\n"
            "    }\n"
            "    const u32 w00 = YW2ReadWord(base + 0x00);\n"
            "    const u32 w04 = YW2ReadWord(base + 0x04);\n"
            "    const u32 w08 = YW2ReadWord(base + 0x08);\n"
            "    const u32 w0C = YW2ReadWord(base + 0x0C);\n"
            "    const u32 w10 = YW2ReadWord(base + 0x10);\n"
            "    const u32 w14 = YW2ReadWord(base + 0x14);\n"
            "    const u32 w18 = YW2ReadWord(base + 0x18);\n"
            "    const u32 w1C = YW2ReadWord(base + 0x1C);\n"
            "    LOG_WARNING(Service_FS,\n"
            "                \"(YW2 FS PTR) {} base=0x{:08X} words={:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X}\",\n"
            "                label, base, w00, w04, w08, w0C, w10, w14, w18, w1C);\n"
            "}\n\n"
            "void TraceYW2FsRead(const File& file, Kernel::HLERequestContext& ctx, u64 offset,\n"
            "                    std::size_t length, bool cache_ready, bool allows_cache_reads) {\n"
            "    if (!YW2FsReadTraceEnabled()) {\n"
            "        return;\n"
            "    }\n\n"
            "    const u64 length64 = static_cast<u64>(length);\n"
            "    const u64 end = offset > std::numeric_limits<u64>::max() - length64\n"
            "                        ? std::numeric_limits<u64>::max()\n"
            "                        : offset + length64;\n"
            "    auto thread = ctx.ClientThread();\n"
            "    const u32 tid = thread ? thread->GetThreadId() : 0;\n"
            "    const u32 pc = thread ? thread->context.GetProgramCounter() : 0;\n"
            "    const u32 lr = thread ? thread->context.GetLinkRegister() : 0;\n"
            "    const u32 sp = thread ? thread->context.GetStackPointer() : 0;\n"
            "    const u32 r0 = thread ? thread->context.cpu_registers[0] : 0;\n"
            "    const u32 r1 = thread ? thread->context.cpu_registers[1] : 0;\n"
            "    const u32 r2 = thread ? thread->context.cpu_registers[2] : 0;\n"
            "    const u32 r3 = thread ? thread->context.cpu_registers[3] : 0;\n"
            "    const u32 r4 = thread ? thread->context.cpu_registers[4] : 0;\n"
            "    const u32 r5 = thread ? thread->context.cpu_registers[5] : 0;\n"
            "    const u32 r6 = thread ? thread->context.cpu_registers[6] : 0;\n"
            "    const u32 r7 = thread ? thread->context.cpu_registers[7] : 0;\n"
            "    const u32 r8 = thread ? thread->context.cpu_registers[8] : 0;\n"
            "    const u32 r9 = thread ? thread->context.cpu_registers[9] : 0;\n"
            "    const u32 r10 = thread ? thread->context.cpu_registers[10] : 0;\n"
            "    const u32 r11 = thread ? thread->context.cpu_registers[11] : 0;\n"
            "    const u32 r12 = thread ? thread->context.cpu_registers[12] : 0;\n"
            "    const u32 s00 = YW2ReadWord(sp + 0x00);\n"
            "    const u32 s04 = YW2ReadWord(sp + 0x04);\n"
            "    const u32 s08 = YW2ReadWord(sp + 0x08);\n"
            "    const u32 s0C = YW2ReadWord(sp + 0x0C);\n"
            "    const u32 s10 = YW2ReadWord(sp + 0x10);\n"
            "    const u32 s14 = YW2ReadWord(sp + 0x14);\n"
            "    const u32 s18 = YW2ReadWord(sp + 0x18);\n"
            "    const u32 s1C = YW2ReadWord(sp + 0x1C);\n"
            "    bool dumped_ptrs = false;\n\n"
            "    for (const auto& target : YW2_READ_TARGETS) {\n"
            "        if (!YW2RangesOverlap(offset, length, target.offset, target.size)) {\n"
            "            continue;\n"
            "        }\n\n"
            "        LOG_WARNING(Service_FS,\n"
            "                    \"(YW2 FS READ) hit={} tid={} pc=0x{:08X} lr=0x{:08X} sp=0x{:08X} read=[0x{:X},0x{:X}) len=0x{:X} target=[0x{:X},0x{:X}) cache_ready={} allows_cache={} regs={:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} stack={:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} file={}\",\n"
            "                    target.name, tid, pc, lr, sp, offset, end, length64, target.offset,\n"
            "                    target.offset + target.size, cache_ready, allows_cache_reads, r0, r1, r2,\n"
            "                    r3, r4, r5, r6, r7, r8, r9, r10, r11, r12, s00, s04, s08, s0C,\n"
            "                    s10, s14, s18, s1C, file.GetName());\n"
            "        if (!dumped_ptrs) {\n"
            "            TraceYW2PtrDump(\"r3\", r3);\n"
            "            TraceYW2PtrDump(\"r4\", r4);\n"
            "            TraceYW2PtrDump(\"r6\", r6);\n"
            "            TraceYW2PtrDump(\"s00\", s00);\n"
            "            TraceYW2PtrDump(\"s08\", s08);\n"
            "            TraceYW2PtrDump(\"s0C\", s0C);\n"
            "            dumped_ptrs = true;\n"
            "        }\n"
            "    }\n"
            "}\n\n"
            "} // namespace\n\n"
        )
        text = replace_once(text, "namespace Service::FS {\n\n", helper, "FS read trace helper")

    if "TraceYW2FsRead(*this, ctx, offset, length" not in text:
        text = replace_once(
            text,
            "    const bool allows_cache_reads = backend->AllowsCachedReads();\n\n"
            "    // Conventional reading if the backend does not support cache.\n",
            "    const bool allows_cache_reads = backend->AllowsCachedReads();\n"
            "    const bool yw2_cache_ready = allows_cache_reads ? backend->CacheReady(offset, length) : false;\n"
            "    TraceYW2FsRead(*this, ctx, offset, length, yw2_cache_ready, allows_cache_reads);\n\n"
            "    // Conventional reading if the backend does not support cache.\n",
            "FS read trace call after adjusted offset",
        )

    if "async_data->cache_ready = yw2_cache_ready;" not in text:
        text = replace_once(
            text,
            "    async_data->cache_ready = backend->CacheReady(offset, length);\n",
            "    async_data->cache_ready = yw2_cache_ready;\n",
            "reuse FS read cache_ready result",
        )

    path.write_text(text)


patch_ivfc()
patch_fs_file()
print("Patched YW2 FA read trace")
print("Patched YW2 FS read caller pointer dump trace")
