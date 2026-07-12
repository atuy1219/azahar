#include <3ds.h>
#include <CTRPluginFramework.hpp>

#include <algorithm>
#include <array>
#include <string>
#include <vector>

namespace CTRPluginFramework {
namespace {

constexpr u32 kInvalid = 0xFFFFFFFFu;
constexpr u32 kCapacity = 8192;
constexpr u32 kStackWords = 8;
constexpr u64 kWaitF0SampleIntervalMs = 100;

constexpr u32 kMarkerTraceStart = 0xFFF00001u;
constexpr u32 kMarkerRoomCreated = 0xFFF00002u;
constexpr u32 kMarkerEnemySelected = 0xFFF00003u;
constexpr u32 kMarkerCharacterPreviewAuto = 0xFFF00004u;
constexpr u32 kMarkerGameplayStarted = 0xFFF00006u;

constexpr u32 kCharacterPreviewIdle = 0;
constexpr u32 kCharacterPreviewWaitForDeparture = 1;
constexpr u32 kCharacterPreviewWaitForReturn = 2;
constexpr u32 kCharacterPreviewComplete = 3;

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
    u32 job_4c;
    u32 job_88;
    u32 job_a0;
    u32 job_a4;
    u32 packet_ptr;
    u32 packet_len;
    u32 packet_header;
    u32 packet_seq;
};

struct Target {
    u32 address;
    const char *name;
};

static const Target kTargets[] = {
    {0x0032C9B0, "create_session_job"},
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
    {0x0034661C, "session_protocol_pump"},
    {0x00343D94, "session_packet_dispatch"},
    {0x00349B3C, "process_join_request"},
    {0x0034EF84, "session_update_dispatch"},
    {0x0034D4F8, "session_update_parse"},
    {0x0034E9D4, "session_update_parse_alt"},
    {0x0034D860, "session_update_apply"},
    {0x0034C328, "session_update_main"},
    {0x0034D058, "session_count_mirror"},
};

static std::array<TraceRecord, kCapacity> g_records{};
static volatile u32 g_next_sequence = 0;
static volatile bool g_recording = false;
static bool g_hooks_attempted = false;
static bool g_session_active = false;
static std::vector<Hook> g_hooks;
static std::array<HookResult, sizeof(kTargets) / sizeof(kTargets[0])> g_hook_results{};

static std::array<u32, 13> g_last_regs{};
static u32 g_last_sp = 0;
static u32 g_last_callback_lr = 0;
static u32 g_last_game_lr = 0;

static u64 g_last_wait_f0_tick = 0;
static u32 g_last_wait_f0_signature = 0;
static volatile u32 g_wait_f0_seen = 0;
static volatile u32 g_wait_f0_saved = 0;

static volatile u32 g_protocol_baseline_r9 = 0;
static volatile u32 g_protocol_last_nonzero_r9 = 0;
static volatile u32 g_character_preview_state = kCharacterPreviewIdle;
static volatile u32 g_character_preview_auto_markers = 0;

static const char *TargetName(u32 pc) {
    switch (pc) {
    case kMarkerTraceStart:
        return "MARK_trace_start";
    case kMarkerRoomCreated:
        return "MARK_room_created";
    case kMarkerEnemySelected:
        return "MARK_enemy_selected";
    case kMarkerCharacterPreviewAuto:
        return "MARK_character_preview_auto";
    case kMarkerGameplayStarted:
        return "MARK_gameplay_started";
    default:
        break;
    }

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

static bool IsSessionJobPc(u32 pc) {
    switch (pc) {
    case 0x0032C9B0:
    case 0x00349B3C:
    case 0x0034EF84:
    case 0x0034D4F8:
    case 0x0034E9D4:
    case 0x0034D860:
    case 0x0034C328:
    case 0x0034D058:
        return true;
    default:
        return false;
    }
}

static void FillDerivedFields(TraceRecord &record) {
    const u32 r0 = record.regs[0];
    const u32 r1 = record.regs[1];
    const u32 r2 = record.regs[2];

    record.r0_plus_2a70 = Read32Safe(r0 + 0x2A70u);
    record.r4_plus_2a70 = Read32Safe(record.regs[4] + 0x2A70u);
    record.r0_active8 = Read8Safe(r0 + 0x3EECu);
    record.r4_active8 = Read8Safe(record.regs[4] + 0x3EECu);
    record.r0_inline_active8 = Read8Safe(r0 + 0x2A70u + 0x3EECu);
    record.r4_inline_active8 = Read8Safe(record.regs[4] + 0x2A70u + 0x3EECu);
    record.r0_pointer_active8 =
        record.r0_plus_2a70 != kInvalid ? Read8Safe(record.r0_plus_2a70 + 0x3EECu) : kInvalid;
    record.r4_pointer_active8 =
        record.r4_plus_2a70 != kInvalid ? Read8Safe(record.r4_plus_2a70 + 0x3EECu) : kInvalid;

    record.job_4c = kInvalid;
    record.job_88 = kInvalid;
    record.job_a0 = kInvalid;
    record.job_a4 = kInvalid;
    record.packet_ptr = kInvalid;
    record.packet_len = kInvalid;
    record.packet_header = kInvalid;
    record.packet_seq = kInvalid;

    if (IsSessionJobPc(record.pc)) {
        record.job_4c = Read32Safe(r0 + 0x4Cu);
        record.job_88 = Read32Safe(r0 + 0x88u);
        record.job_a0 = Read32Safe(r0 + 0xA0u);
        record.job_a4 = Read8Safe(r0 + 0xA4u);
    }

    if (record.pc == 0x00343D94u) {
        record.packet_ptr = Read32Safe(r1);
        record.packet_len = Read32Safe(r1 + 4u);
    } else if (record.pc == 0x0034EF84u || record.pc == 0x0034D4F8u ||
               record.pc == 0x0034E9D4u) {
        record.packet_ptr = r1;
        record.packet_len = r2;
    }

    if (record.packet_ptr != kInvalid) {
        record.packet_header = Read32Safe(record.packet_ptr);
        record.packet_seq = Read32Safe(record.packet_ptr + 4u);
    }
}

static void SaveLastContext(u32 *frame, u32 callback_lr, u32 game_lr) {
    for (u32 index = 0; index < 13; ++index)
        g_last_regs[index] = frame[index];
    g_last_sp = reinterpret_cast<u32>(frame + 14);
    g_last_callback_lr = callback_lr;
    g_last_game_lr = game_lr;
}

static void InitializeRecord(TraceRecord &record, u32 sequence, u32 pc) {
    record = {};
    const u64 tick = osGetTime();
    record.sequence = sequence;
    record.tick_hi = static_cast<u32>(tick >> 32);
    record.tick_lo = static_cast<u32>(tick);
    record.thread_id = 0;
    svcGetThreadId(&record.thread_id, CUR_THREAD_HANDLE);
    record.pc = pc;
}

static void PushMarker(u32 marker_pc) {
    if (!g_session_active)
        return;

    const u32 sequence = __sync_fetch_and_add(&g_next_sequence, 1u);
    TraceRecord &record = g_records[sequence % kCapacity];
    InitializeRecord(record, sequence, marker_pc);

    for (u32 index = 0; index < 13; ++index)
        record.regs[index] = g_last_regs[index];
    record.sp = g_last_sp;
    record.callback_lr = g_last_callback_lr;
    record.game_lr = g_last_game_lr;

    for (u32 index = 0; index < kStackWords; ++index)
        record.stack[index] = Read32Safe(record.sp + index * sizeof(u32));

    FillDerivedFields(record);
}

static void ObserveSessionProtocolPump(u32 pc, u32 *frame) {
    if (pc != 0x0034661Cu)
        return;

    const u32 pointer = frame[9];
    if (!LooksLikeGuestPointer(pointer))
        return;

    if (g_protocol_baseline_r9 == 0) {
        g_protocol_baseline_r9 = pointer;
        g_protocol_last_nonzero_r9 = pointer;
        return;
    }

    const u32 previous = g_protocol_last_nonzero_r9;
    g_protocol_last_nonzero_r9 = pointer;

    if (g_character_preview_state == kCharacterPreviewWaitForDeparture) {
        if (previous == g_protocol_baseline_r9 && pointer != g_protocol_baseline_r9)
            g_character_preview_state = kCharacterPreviewWaitForReturn;
        return;
    }

    if (g_character_preview_state == kCharacterPreviewWaitForReturn &&
        pointer == g_protocol_baseline_r9 && previous != 0 &&
        previous != g_protocol_baseline_r9) {
        g_character_preview_state = kCharacterPreviewComplete;
        __sync_fetch_and_add(&g_character_preview_auto_markers, 1u);
        PushMarker(kMarkerCharacterPreviewAuto);
    }
}

static u32 WaitF0Signature(u32 *frame) {
    return frame[0] ^ (frame[2] * 0x45D9F3Bu) ^ (frame[4] * 0x119DE1F3u) ^
           (frame[5] * 0x3449u) ^ (frame[9] << 16) ^ frame[10];
}

static bool ShouldRecordWaitF0(u32 *frame) {
    __sync_fetch_and_add(&g_wait_f0_seen, 1u);

    const u64 now = osGetTime();
    const u32 signature = WaitF0Signature(frame);
    if (g_last_wait_f0_tick == 0 || signature != g_last_wait_f0_signature ||
        now - g_last_wait_f0_tick >= kWaitF0SampleIntervalMs) {
        g_last_wait_f0_tick = now;
        g_last_wait_f0_signature = signature;
        __sync_fetch_and_add(&g_wait_f0_saved, 1u);
        return true;
    }
    return false;
}

extern "C" void YW2TraceHookHandler(u32 *frame) {
    if (!g_recording)
        return;

    const u32 pc = HookContext::GetCurrent().targetAddress;
    const u32 callback_lr = frame[13];
    const u32 game_lr = Read32Safe(callback_lr + 0x10u);
    SaveLastContext(frame, callback_lr, game_lr);

    if (pc == 0x003376F0u && !ShouldRecordWaitF0(frame))
        return;

    const u32 sequence = __sync_fetch_and_add(&g_next_sequence, 1u);
    TraceRecord &record = g_records[sequence % kCapacity];
    InitializeRecord(record, sequence, pc);

    for (u32 index = 0; index < 13; ++index)
        record.regs[index] = frame[index];

    record.sp = reinterpret_cast<u32>(frame + 14);
    record.callback_lr = callback_lr;
    record.game_lr = game_lr;

    for (u32 index = 0; index < kStackWords; ++index)
        record.stack[index] = Read32Safe(record.sp + index * sizeof(u32));

    FillDerivedFields(record);
    ObserveSessionProtocolPump(pc, frame);
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
    g_wait_f0_seen = 0;
    g_wait_f0_saved = 0;
    g_last_wait_f0_tick = 0;
    g_last_wait_f0_signature = 0;
    g_protocol_baseline_r9 = 0;
    g_protocol_last_nonzero_r9 = 0;
    g_character_preview_state = kCharacterPreviewIdle;
    g_character_preview_auto_markers = 0;
    g_last_regs.fill(0);
    g_last_sp = 0;
    g_last_callback_lr = 0;
    g_last_game_lr = 0;
    for (auto &record : g_records)
        record = {};
}

static bool InstallHooks(void) {
    DisableHooks();
    ClearTrace();
    g_hooks_attempted = true;

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
    g_session_active = any_success;
    return any_success;
}

static std::string BuildHookStatus(void) {
    if (!g_hooks_attempted)
        return "Not attempted yet. Select Start trace first.";

    std::string text;
    for (u32 index = 0; index < sizeof(kTargets) / sizeof(kTargets[0]); ++index) {
        text += Utils::Format("%08X %-28s %s\n", kTargets[index].address,
                              kTargets[index].name, HookResultName(g_hook_results[index]));
    }
    return text;
}

static std::string FormatTraceRecord(const TraceRecord &record) {
    std::string line = Utils::Format("%u,%08X,%08X,%u,%08X,%s", record.sequence,
                                     record.tick_hi, record.tick_lo, record.thread_id,
                                     record.pc, TargetName(record.pc));

    line += Utils::Format(",%08X,%08X,%08X,%08X,%08X,%08X", record.regs[0],
                          record.regs[1], record.regs[2], record.regs[3], record.regs[4],
                          record.regs[5]);
    line += Utils::Format(",%08X,%08X,%08X,%08X,%08X,%08X", record.regs[6],
                          record.regs[7], record.regs[8], record.regs[9], record.regs[10],
                          record.regs[11]);
    line += Utils::Format(",%08X,%08X,%08X,%08X", record.regs[12], record.sp,
                          record.callback_lr, record.game_lr);
    line += Utils::Format(",%08X,%08X,%08X,%08X,%08X,%08X", record.stack[0],
                          record.stack[1], record.stack[2], record.stack[3], record.stack[4],
                          record.stack[5]);
    line += Utils::Format(",%08X,%08X,%08X,%08X", record.stack[6], record.stack[7],
                          record.r0_plus_2a70, record.r4_plus_2a70);
    line += Utils::Format(",%08X,%08X,%08X,%08X,%08X,%08X", record.r0_active8,
                          record.r4_active8, record.r0_inline_active8,
                          record.r4_inline_active8, record.r0_pointer_active8,
                          record.r4_pointer_active8);
    line += Utils::Format(",%08X,%08X,%08X,%08X,%08X,%08X,%08X,%08X", record.job_4c,
                          record.job_88, record.job_a0, record.job_a4, record.packet_ptr,
                          record.packet_len, record.packet_header, record.packet_seq);
    return line;
}

static bool SaveTrace(std::string &saved_path) {
    const u32 total = g_next_sequence;
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
        "r4_inline_active8,r0_pointer_active8,r4_pointer_active8,"
        "job_4c,job_88,job_a0,job_a4,packet_ptr,packet_len,packet_header,packet_seq");

    for (u32 sequence = first; sequence < total; ++sequence) {
        const TraceRecord &record = g_records[sequence % kCapacity];
        if (record.sequence != sequence)
            continue;
        file.WriteLine(FormatTraceRecord(record));
    }

    file.Flush();
    file.Close();
    return true;
}

static void StartTrace(MenuEntry *) {
    if (g_session_active) {
        OSD::Notify("YW2 trace is already running");
        return;
    }

    if (InstallHooks()) {
        PushMarker(kMarkerTraceStart);
        OSD::Notify(Color::Lime << "YW2 trace started (F0 sampled every 100 ms)");
    } else {
        MessageBox("YW2 trace", "No hook could be installed. Check Hook status.")();
    }
}

static void MarkPhase(u32 marker, const char *text) {
    if (!g_session_active) {
        OSD::Notify("Start trace before adding phase markers");
        return;
    }
    PushMarker(marker);
    OSD::Notify(text);
}

static void MarkRoomCreated(MenuEntry *) {
    g_protocol_baseline_r9 = 0;
    g_protocol_last_nonzero_r9 = 0;
    g_character_preview_state = kCharacterPreviewIdle;
    MarkPhase(kMarkerRoomCreated, "Marked: room created");
}

static void MarkEnemySelected(MenuEntry *) {
    MarkPhase(kMarkerEnemySelected, "Marked: enemy selected");
    if (g_session_active) {
        g_character_preview_state = kCharacterPreviewWaitForDeparture;
        g_protocol_last_nonzero_r9 = g_protocol_baseline_r9;
    }
}

static void StopAndSaveTrace(MenuEntry *) {
    if (!g_session_active) {
        MessageBox("YW2 trace", "Trace is not running. Select Start trace first.")();
        return;
    }

    PushMarker(kMarkerGameplayStarted);
    DisableHooks();
    svcSleepThread(20 * 1000 * 1000LL);

    const u32 total = g_next_sequence;
    const u32 stored = std::min(total, kCapacity);
    const u32 dropped = total > kCapacity ? total - kCapacity : 0;
    const u32 f0_seen = g_wait_f0_seen;
    const u32 f0_saved = g_wait_f0_saved;
    const u32 f0_skipped = f0_seen > f0_saved ? f0_seen - f0_saved : 0;

    std::string path;
    if (SaveTrace(path)) {
        MessageBox(
            "YW2 trace saved",
            Utils::Format(
                "3gxDir:/%s\nstored=%u total=%u dropped=%u\nF0 seen=%u saved=%u skipped=%u\nauto character+preview=%u baseline_r9=%08X",
                path.c_str(), stored, total, dropped, f0_seen, f0_saved, f0_skipped,
                static_cast<u32>(g_character_preview_auto_markers),
                static_cast<u32>(g_protocol_baseline_r9)))();
    } else {
        MessageBox("YW2 trace", "Failed to write the trace file.")();
    }
    g_session_active = false;
}

static void ClearTraceMenu(MenuEntry *) {
    if (g_session_active) {
        MessageBox("YW2 trace", "Stop the active trace before clearing the buffer.")();
        return;
    }
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
    g_session_active = false;
}

void InitMenu(PluginMenu &menu) {
    menu += new MenuEntry(
        "Start trace", nullptr, StartTrace,
        "Start after the save and Busters hub are loaded, immediately before room creation.");
    menu += new MenuEntry("Mark: room created", nullptr, MarkRoomCreated);
    menu += new MenuEntry(
        "Mark: enemy selected", nullptr, MarkEnemySelected,
        "Arms automatic character-selection and preview detection from protocol r9 transitions.");
    menu += new MenuEntry(
        "Stop and save at gameplay start", nullptr, StopAndSaveTrace,
        "Adds a gameplay-start marker, disables hooks, and writes one CSV.");
    menu += new MenuEntry("Clear trace buffer", nullptr, ClearTraceMenu);
    menu += new MenuEntry("Hook status", nullptr, ShowHookStatus,
                          "Shows the result of the most recent hook installation attempt.");
}

int main(void) {
    PluginMenu *menu = new PluginMenu(
        "YW2 Runtime Trace", 0, 5, 1,
        "Runtime tracer for room/member and character-selection timing analysis.\n"
        "Mark room creation and enemy selection; character+preview is detected automatically.");
    menu->SynchronizeWithFrame(true);
    InitMenu(*menu);
    menu->Run();
    delete menu;
    return 0;
}

} // namespace CTRPluginFramework
