// Optional ARM11/PICA/FS trace for the Linux Azahar build.
#pragma once
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdlib>
#include <initializer_list>
#include <mutex>
#include <string>
#include <string_view>
#include <fcntl.h>
#include <time.h>
#include <unistd.h>
#include <sys/syscall.h>
namespace YWTrace {
inline std::atomic<std::uint64_t> sequence{0};
inline std::atomic<std::uint64_t> blob_bytes{0};
inline std::mutex file_mutex;
inline int file_fd = -2;
inline bool Enabled() {
    const char* path = std::getenv("YW_TRACE_LOG");
    if (!path || !*path) return false;
    const char* gate = std::getenv("YW_TRACE_GATE");
    return !gate || !*gate || ::access(gate, F_OK) == 0;
}
inline std::uint64_t NowNs() {
    timespec ts{};
    ::clock_gettime(CLOCK_MONOTONIC, &ts);
    return std::uint64_t(ts.tv_sec) * 1000000000ull + ts.tv_nsec;
}
inline std::string Escape(std::string_view s) {
    std::string out;
    for (char c : s.substr(0, 2048)) {
        switch (c) {
        case '"': out += "\\\""; break;
        case '\\': out += "\\\\"; break;
        case '\n': out += "\\n"; break;
        case '\r': out += "\\r"; break;
        case '\t': out += "\\t"; break;
        default: if (static_cast<unsigned char>(c) < 32) out += '?'; else out += c;
        }
    }
    return out;
}
inline void Emit(std::string_view kind, std::initializer_list<std::uint64_t> args = {},
                 std::string_view detail = {}) {
    if (!Enabled()) return;
    auto ns = NowNs();
    auto id = sequence.fetch_add(1, std::memory_order_relaxed);
    std::string line = "{\"ns\":" + std::to_string(ns)
        + ",\"seq\":" + std::to_string(id)
        + ",\"tid\":" + std::to_string(::syscall(SYS_gettid))
        + ",\"kind\":\"" + Escape(kind) + "\",\"v\":[";
    bool first = true;
    for (auto v : args) {
        if (!first) line += ',';
        first = false;
        line += std::to_string(v);
    }
    line += "]";
    if (!detail.empty()) line += ",\"text\":\"" + Escape(detail) + '"';
    line += "}\n";
    std::lock_guard<std::mutex> lock(file_mutex);
    if (file_fd == -2) {
        file_fd = ::open(std::getenv("YW_TRACE_LOG"), O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0644);
    }
    if (file_fd >= 0) (void)::write(file_fd, line.data(), line.size());
}
inline bool ClaimStep() {
    if (!Enabled()) return false;
    static std::atomic<std::uint64_t> remaining{[] {
        const char* s = std::getenv("YW_TRACE_SINGLE_STEP_BUDGET");
        return s ? std::min<std::uint64_t>(std::strtoull(s, nullptr, 10), 1000000ull) : 0ull;
    }()};
    auto n = remaining.load(std::memory_order_relaxed);
    while (n && !remaining.compare_exchange_weak(n, n - 1, std::memory_order_relaxed)) {}
    return n != 0;
}
inline void CmdList(std::uint64_t addr, const void* data, std::uint64_t size) {
    Emit("pica_cmdlist", {addr, size});
    if (!Enabled() || !data || !size || size > 131072) return;
    const char* dir = std::getenv("YW_TRACE_BLOB_DIR");
    if (!dir || !*dir) return;
    auto prev = blob_bytes.fetch_add(size, std::memory_order_relaxed);
    if (prev + size > 33554432ull) return;
    auto id = sequence.fetch_add(1, std::memory_order_relaxed);
    std::string filename = std::string(dir) + "/cmd_" + std::to_string(::getpid())
        + "_" + std::to_string(id) + ".bin";
    int fd = ::open(filename.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0644);
    if (fd < 0) return;
    ssize_t result = ::write(fd, data, static_cast<size_t>(size));
    ::close(fd);
    if (result == static_cast<ssize_t>(size)) Emit("pica_payload", {addr, size, id}, filename);
}
} // namespace YWTrace
