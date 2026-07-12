#include <3ds.h>
#include <CTRPluginFramework.hpp>

#include <array>
#include <string>

namespace CTRPluginFramework {
namespace {

constexpr u32 kTextBase = 0x00100000u;
constexpr u32 kInvalid = 0xFFFFFFFFu;

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

static u32 Read32Safe(u32 address) {
    u32 value = kInvalid;
    if (!Process::Read32(address, value))
        return kInvalid;
    return value;
}

static bool SaveTargetProbe(std::string &saved_path) {
    const u64 tick = osGetTime();
    saved_path = Utils::Format("yw2_target_probe_%08X.csv", static_cast<u32>(tick));

    File file;
    const int open_result =
        File::Open(file, saved_path, File::WRITE | File::CREATE | File::TRUNCATE);
    if (open_result != File::SUCCESS)
        return false;

    u64 program_id = 0;
    const Result apt_result = APT_GetProgramID(&program_id);
    const u32 text_size = Process::GetTextSize();

    file.WriteLine("record_type,key,value0,value1,value2,value3,value4,value5");
    file.WriteLine("meta,probe_version,00030000,,,,,");
    file.WriteLine(Utils::Format("meta,title_id,%08X,%08X,,,,", static_cast<u32>(program_id >> 32),
                                 static_cast<u32>(program_id)));
    file.WriteLine(Utils::Format("meta,apt_result,%08X,,,,,", static_cast<u32>(apt_result)));
    file.WriteLine(Utils::Format("meta,text_range,%08X,%08X,,,,", kTextBase,
                                 kTextBase + text_size));
    file.WriteLine("target,name,address,minus8,minus4,current,plus4,plus8");

    for (const auto &target : kTargets) {
        file.WriteLine(Utils::Format(
            "target,%s,%08X,%08X,%08X,%08X,%08X,%08X", target.name, target.address,
            Read32Safe(target.address - 8u), Read32Safe(target.address - 4u),
            Read32Safe(target.address), Read32Safe(target.address + 4u),
            Read32Safe(target.address + 8u)));
    }

    file.Flush();
    file.Close();
    return true;
}

static void DumpTargetMap(MenuEntry *) {
    std::string path;
    if (SaveTargetProbe(path)) {
        MessageBox("YW2 safe probe saved",
                   Utils::Format("3gxDir:/%s\nNo game code was modified.", path.c_str()))();
    } else {
        MessageBox("YW2 safe probe", "Failed to write the probe CSV.")();
    }
}

static void ShowSafetyStatus(MenuEntry *) {
    u64 program_id = 0;
    const Result result = APT_GetProgramID(&program_id);
    MessageBox(
        "YW2 safe probe",
        Utils::Format("Hooks: disabled\nWrites to game code: none\nTitle ID: %08X%08X\nAPT result: %08X\nText: %08X-%08X",
                      static_cast<u32>(program_id >> 32), static_cast<u32>(program_id),
                      static_cast<u32>(result), kTextBase, kTextBase + Process::GetTextSize()))();
}

} // namespace

void PatchProcess(FwkSettings &) {}
void OnProcessExit(void) {}

void InitMenu(PluginMenu &menu) {
    menu += new MenuEntry("Dump target map (safe)", nullptr, DumpTargetMap,
                          "Reads target instructions and saves one CSV. It installs no hooks and writes no game memory.");
    menu += new MenuEntry("Safety status", nullptr, ShowSafetyStatus,
                          "Shows the current Title ID and confirms that code hooks are disabled.");
}

int main(void) {
    PluginMenu *menu = new PluginMenu(
        "YW2 Safe Probe", 0, 3, 0,
        "Non-invasive address probe for Yo-kai Watch 2 communication analysis.\n"
        "This build does not install hooks or modify game code.");
    menu->SynchronizeWithFrame(true);
    InitMenu(*menu);
    menu->Run();
    delete menu;
    return 0;
}

} // namespace CTRPluginFramework
