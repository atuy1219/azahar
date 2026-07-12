#include <3ds.h>
#include <CTRPluginFramework.hpp>

#include <algorithm>
#include <array>
#include <string>
#include <vector>

namespace CTRPluginFramework {
namespace {

constexpr u32 kInvalid = 0xFFFFFFFFu;
constexpr u32 kCapacity = 4096;
constexpr u32 kStackWords = 8;

struct TraceRecord {
    u32 sequence;
    u32 tick_hi;
    u32 tick_lo;
    u32 thread_id;
    u32 pc;
    u32 regs[13];
    u32 sp;
    u32 callback_lr;
    u32 game_lr;
    u32 stack[kStackWords];
    u32 r0_plus_2a70;
    u32 r4_plus_2a70;
    u32 r0_active8;
    u32 r4_active8;
    u32 r0_inline_active8;
    u32 r4_inline_active8;
    u32 r0_pointer_active8;
    u32 r4_pointer_active8;
};

struct Target {
    u32 address;
    const char *name;
};

static const Target kTargets[] = {
    {0x00337680, "post_channel_wait_80"},
    {0x003376C0, "post_channel_wait_c0"},
    {0x003376F0, "post_channel_wait_f0"},
    {0x00337744, "destroy_branch"},
    {0x0033807C, "connection_status_update"},
    {0x0033809C, "connection_status_event_wait"},
    {0x003380B0, "connection_status_wait_b0"},
    {0x003380D0, "connection_status_wait_d0"},
    {0x0033BD24, "post_channel_callback"},
    {0x0033BD54, "post_channel_return"},
    {0x0033BD94, "post_channel_failure"},
    {0x00364D20, "destroy_network_wrapper"},
    {0x0033B8BC, "room_create"},
    {0x0033BAF4, "begin_host_return_block"},
    {0x0033BB00, "get_channel_return_block"},
    {0x00339994, "worker_busy_gate"},
    {0x00339C90, "worker_stop"},
    {0x00339D8C, "worker_start"},
    {0x0033C0A0, "packet_loop"},
};

static std::array<TraceRecord, kCapacity> g_records{};
static volatile u32 g_next_sequence = 0;
static volatile bool g_recording = false;
static std::vector<Hook> g_hooks;
static std::array<HookResult, sizeof(kTargets) / sizeof(kTargets[0])> g_hook_results{};

static const char *TargetName(u32 pc) {
    for (const auto &target : kTargets) {
        if (target.address == pc)
            return target.name;
    }
    return "unknown";
}

static const char *HookResultName(HookResult result) {
    switch (result) {
    case HookResult::Success:
        return "Success";
    case HookResult::InvalidContext:
        return "InvalidContext";
    case HookResult::InvalidAddress:
        return "InvalidAddress";
    case HookResult::AddressAlreadyHooked:
        return "AddressAlreadyHooked";
    case HookResult::TooManyHooks:
        return "TooManyHooks";
    case HookResult::HookParamsError:
        return "HookParamsError";
    case HookResult::TargetInstructionCannotBeHandledAutomatically:
        return "PCRelativeInstruction";
    default:
        return "Unknown";
    }
}

static bool LooksLikeGuestPointer(u32 address) {
    return address >= 0x00100000u && address < 0x40000000u;
}

static u32 Read32Safe(u32 address) {
    if (!LooksLikeGuestPointer(address))
        return kInvalid;

    u32 value = kInvalid;
    if (!Process::Read32(address, value))
        return kInvalid;
    return value;
}

static u32 Read8Safe(u32 address) {
    const u32 word = Read32Safe(address & ~3u);
    if (word == kInvalid)
        return kInvalid;
    return (word >> ((address & 3u) * 8u)) & 0xFFu;
}

extern "C" void YW2TraceHookHandler(u32 *frame) {
    if (!g_recording)
        return;

    const u32 sequence = __sync_fetch_and_add(&g_next_sequence, 1u);
    TraceRecord &record = g_records[sequence % kCapacity];

    const u64 tick = osGetTime();
    record.sequence = sequence;
    record.tick_hi = static_cast<u32>(tick >> 32);
    record.tick_lo = static_cast<u32>(tick);
    record.thread_id = 0;
    svcGetThreadId(&record.thread_id, CUR_THREAD_HANDLE);
    record.pc = HookContext::GetCurrent().targetAddress;

    for (u32 index = 0; index < 13; ++index)
        record.regs[index] = frame[index];

    record.sp = reinterpret_cast<u32>(frame + 14);
    record.callback_lr = frame[13];
    // CTRPF default hooks call the callback through BLX. The original game LR is
    // restored from a literal four ARM words after the callback continuation.
    record.game_lr = Read32Safe(record.callback_lr + 0x10u);

    for (u32 index = 0; index < kStackWords; ++index)
        record.stack[index] = Read32Safe(record.sp + index * sizeof(u32));

    const u32 r0 = record.regs[0];
    const u32 r4 = record.regs[4];
    record.r0_plus_2a70 = Read32Safe(r0 + 0x2A70u);
    record.r4_plus_2a70 = Read32Safe(r4 + 0x2A70u);
    record.r0_active8 = Read8Safe(r0 + 0x3EECu);
    record.r4_active8 = Read8Safe(r4 + 0x3EECu);
    record.r0_inline_active8 = Read8Safe(r0 + 0x2A70u + 0x3EECu);
    record.r4_inline_active8 = Read8Safe(r4 + 0x2A70u + 0x3EECu);
    record.r0_pointer_active8 =
        record.r0_plus_2a70 != kInvalid ? Read8Safe(record.r0_plus_2a70 + 0x3EECu) : kInvalid;
    record.r4_pointer_active8 =
        record.r4_plus_2a70 != kInvalid ? Read8Safe(record.r4_plus_2a70 + 0x3EECu) : kInvalid;
}

extern "C" void __attribute__((naked)) YW2TraceHookStub(void) {
    __asm__ volatile(
        "stmdb sp!, {r0-r12, lr}\n"
        "mov r0, sp\n"
        "bl YW2TraceHookHandler\n"
        "ldmia sp!, {r0-r12, lr}\n"
        "bx lr\n");
}

static void DisableHooks(void) {
    g_recording = false;
    for (auto &hook : g_hooks)
        hook.Disable();
    g_hooks.clear();
}

static void ClearTrace(void) {
    g_next_sequence = 0;
    for (auto &record : g_records)
        record = {};
}

static bool InstallHooks(void) {
    DisableHooks();
    ClearTrace();

    g_hooks.reserve(sizeof(kTargets) / sizeof(kTargets[0]));
    bool any_success = false;
    for (u32 index = 0; index < sizeof(kTargets) / sizeof(kTargets[0]); ++index) {
        Hook hook;
        hook.Initialize(kTargets[index].address, reinterpret_cast<u32>(YW2TraceHookStub));
        const HookResult result = hook.Enable();
        g_hook_results[index] = result;
        if (result == HookResult::Success) {
            any_success = true;
            g_hooks.push_back(hook);
        }
    }

    g_recording = any_success;
    return any_success;
}

static std::string BuildHookStatus(void) {
    std::string text;
    for (u32 index = 0; index < sizeof(kTargets) / sizeof(kTargets[0]); ++index) {
        text += Utils::Format("%08X %-28s %s\n", kTargets[index].address,
                             kTargets[index].name, HookResultName(g_hook_results[index]));
    }
    return text;
}

static bool SaveTrace(std::string &saved_path) {
    const u32 total = g_next_sequence;
    const u32 count = std::min(total, kCapacity);
    const u32 first = total > kCapacity ? total - kCapacity : 0;

    saved_path = Utils::Format("yw2_trace_%08X.csv", static_cast<u32>(osGetTime()));
    File file;
    const int open_result =
        File::Open(file, saved_path, File::WRITE | File::CREATE | File::TRUNCATE);
    if (open_result != File::SUCCESS)
        return false;

    file.WriteLine(
        "seq,tick_hi,tick_lo,thread,pc,name,r0,r1,r2,r3,r4,r5,r6,r7,r8,r9,r10,r11,r12,"
        "sp,callback_lr,game_lr,stack0,stack1,stack2,stack3,stack4,stack5,stack6,stack7,"
        "r0_plus_2a70,r4_plus_2a70,r0_active8,r4_active8,r0_inline_active8,"
        "r4_inline_active8,r0_pointer_active8,r4_pointer_active8");

    for (u32 sequence = first; sequence < total; ++sequence) {
        const TraceRecord &record = g_records[sequence % kCapacity];
        if (record.sequence != sequence)
            continue;

        file.WriteLine(Utils::Format(
            "%u,%08X,%08X,%u,%08X,%s,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,"
            "%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,"
            "%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X",
            record.sequence, record.tick_hi, record.tick_lo, record.thread_id, record.pc,
            TargetName(record.pc), record.regs[0], record.regs[1], record.regs[2],
            record.regs[3], record.regs[4], record.regs[5], record.regs[6],
            record.regs[7], record.regs[8], record.regs[9], record.regs[10],
            record.regs[11], record.regs[12], record.sp, record.callback_lr,
            record.game_lr, record.stack[0], record.stack[1], record.stack[2], record.stack[3],
            record.stack[4], record.stack[5], record.stack[6], record.stack[7],
            record.r0_plus_2a70, record.r4_plus_2a70, record.r0_active8,
            record.r4_active8, record.r0_inline_active8, record.r4_inline_active8,
            record.r0_pointer_active8, record.r4_pointer_active8));
    }

    file.Flush();
    file.Close();
    return true;
}

static void StartTrace(MenuEntry *) {
    if (InstallHooks()) {
        OSD::Notify(Color::Lime << "YW2 trace started");
    } else {
        MessageBox("YW2 trace", "No hook could be installed. Check Hook status.")();
    }
}

static void StopAndSaveTrace(MenuEntry *) {
    DisableHooks();
    svcSleepThread(20 * 1000 * 1000LL);

    std::string path;
    if (SaveTrace(path)) {
        MessageBox("YW2 trace saved",
                   Utils::Format("3gxDir:/%s\nrecords=%u", path.c_str(),
                                 std::min(static_cast<u32>(g_next_sequence), kCapacity)))();
    } else {
        MessageBox("YW2 trace", "Failed to write the trace file.")();
    }
}

static void ClearTraceMenu(MenuEntry *) {
    ClearTrace();
    OSD::Notify("YW2 trace buffer cleared");
}

static void ShowHookStatus(MenuEntry *) {
    MessageBox("YW2 hook status", BuildHookStatus())();
}

} // namespace

void PatchProcess(FwkSettings &) {}

void OnProcessExit(void) {
    DisableHooks();
}

void InitMenu(PluginMenu &menu) {
    menu += new MenuEntry("Start trace", StartTrace,
                          "Installs hooks and clears the in-memory ring buffer.");
    menu += new MenuEntry("Stop and save trace", StopAndSaveTrace,
                          "Disables hooks and writes a CSV file in the 3GX directory.");
    menu += new MenuEntry("Clear trace buffer", ClearTraceMenu);
    menu += new MenuEntry("Hook status", ShowHookStatus,
                          "Shows which target instructions could be hooked safely.");
}

int main(void) {
    PluginMenu *menu = new PluginMenu(
        "YW2 Runtime Trace", 0, 1, 0,
        "Runtime tracer for Yo-kai Watch 2 communication state analysis.\n"
        "Start trace before creating a room, then stop and save after the error.");
    menu->SynchronizeWithFrame(true);
    InitMenu(*menu);
    menu->Run();
    delete menu;
    return 0;
}

} // namespace CTRPluginFramework
