from pathlib import Path
import re


ARM_PATH = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
RUNTIME_HEADER = Path("src/core/yw2_comm_write_watch.h")
DYNARMIC_SRC = Path("externals/dynarmic/src")

arm_text = ARM_PATH.read_text()
if not RUNTIME_HEADER.exists():
    raise RuntimeError("YW2 exact execution trace: shared runtime header not found")

if "(YW2 COMM EXEC)" in arm_text:
    print("Skipped exact YW2 communication execution trace patch: already present")
    raise SystemExit(0)


def find_supervisor_emitter():
    source_candidates = []
    for path in DYNARMIC_SRC.rglob("*"):
        if path.suffix not in {".cpp", ".h"}:
            continue
        text = path.read_text(errors="ignore")
        if "SVC" not in text and "Supervisor" not in text:
            continue
        for match in re.finditer(r"\bir\.([A-Za-z_]\w*)\s*\(([^;\n]*)\)\s*;", text):
            name = match.group(1)
            args = match.group(2)
            if "supervisor" in name.lower() or "svc" in name.lower():
                source_candidates.append((name, args, path))
    preferred = sorted(
        source_candidates,
        key=lambda item: (
            0 if item[0] == "CallSupervisor" else
            1 if "supervisor" in item[0].lower() else
            2,
            str(item[2]),
        ),
    )
    if not preferred:
        raise RuntimeError(
            "YW2 exact execution trace: could not find an A32 IR supervisor-call emitter"
        )
    method = preferred[0][0]

    header_candidates = []
    for path in DYNARMIC_SRC.rglob("*.h"):
        text = path.read_text(errors="ignore")
        if re.search(rf"\b{re.escape(method)}\s*\(", text):
            header_candidates.append(path)
    if not header_candidates:
        raise RuntimeError(
            f"YW2 exact execution trace: declaration header for ir.{method} not found"
        )
    header = sorted(
        header_candidates,
        key=lambda path: (
            0 if "frontend/A32" in path.as_posix() else 1,
            len(path.as_posix()),
        ),
    )[0]
    include_path = header.relative_to(DYNARMIC_SRC).as_posix()
    return method, include_path, preferred[0][2]


emitter_method, emitter_include, emitter_source = find_supervisor_emitter()
print(
    "YW2 exact execution trace: using "
    f"ir.{emitter_method} from {emitter_source} and <{emitter_include}>"
)


include_anchor = '#include <dynarmic/interface/A32/a32.h>\n'
if include_anchor not in arm_text:
    raise RuntimeError("YW2 exact execution trace: Dynarmic A32 include anchor not found")
arm_text = arm_text.replace(
    include_anchor,
    include_anchor + f'#include <{emitter_include}>\n',
    1,
)


class_anchor = "class DynarmicUserCallbacks final : public Dynarmic::A32::UserCallbacks {\n"
if class_anchor not in arm_text:
    raise RuntimeError("YW2 exact execution trace: callbacks class anchor not found")

helpers = r'''constexpr u32 YW2_COMM_EXEC_MAGIC_MASK = 0xFF0000;
constexpr u32 YW2_COMM_EXEC_MAIN = 0xF10000;
constexpr u32 YW2_COMM_EXEC_ALIAS = 0xF20000;
constexpr u32 YW2_COMM_EXEC_SPECIAL = 0xF30000;

bool YW2CommExecTraceEnabled() {
#ifdef ANDROID
    static const bool enabled = []() -> bool {
        char value[PROP_VALUE_MAX] = {};
        if (__system_property_get("debug.azahar.yw2_comm_exec_trace", value) <= 0) {
            return false;
        }
        return std::strcmp(value, "0") != 0 && std::strcmp(value, "false") != 0 &&
               std::strcmp(value, "off") != 0;
    }();
    return enabled;
#else
    return false;
#endif
}

u32 YW2CommExecTagForPC(u32 pc) {
    const u32 normalized = pc & ~u32{1};
    if (normalized >= 0x00244EC8 && normalized <= 0x00244F4C) {
        return YW2_COMM_EXEC_MAIN | (normalized - 0x00244EC8);
    }
    if (normalized >= 0x00294EC8 && normalized <= 0x00294F4C) {
        return YW2_COMM_EXEC_ALIAS | (normalized - 0x00294EC8);
    }
    switch (normalized) {
    case 0x0033BAFC:
        return YW2_COMM_EXEC_SPECIAL | 0x01;
    case 0x00339368:
        return YW2_COMM_EXEC_SPECIAL | 0x02;
    case 0x0033BB00:
        return YW2_COMM_EXEC_SPECIAL | 0x03;
    case 0x0012E420:
        return YW2_COMM_EXEC_SPECIAL | 0x04;
    case 0x002BEC3C:
        return YW2_COMM_EXEC_SPECIAL | 0x05;
    case 0x0012E424:
        return YW2_COMM_EXEC_SPECIAL | 0x06;
    default:
        return 0;
    }
}

bool YW2IsCommExecMagic(u32 swi) {
    const u32 group = swi & YW2_COMM_EXEC_MAGIC_MASK;
    return group == YW2_COMM_EXEC_MAIN || group == YW2_COMM_EXEC_ALIAS ||
           group == YW2_COMM_EXEC_SPECIAL;
}

u32 YW2CommExecPCFromTag(u32 swi) {
    const u32 group = swi & YW2_COMM_EXEC_MAGIC_MASK;
    if (group == YW2_COMM_EXEC_MAIN) {
        return 0x00244EC8 + (swi & 0xFFFF);
    }
    if (group == YW2_COMM_EXEC_ALIAS) {
        return 0x00294EC8 + (swi & 0xFFFF);
    }
    switch (swi & 0xFFFF) {
    case 0x01:
        return 0x0033BAFC;
    case 0x02:
        return 0x00339368;
    case 0x03:
        return 0x0033BB00;
    case 0x04:
        return 0x0012E420;
    case 0x05:
        return 0x002BEC3C;
    case 0x06:
        return 0x0012E424;
    default:
        return 0;
    }
}

const char* YW2CommExecKind(u32 swi) {
    const u32 group = swi & YW2_COMM_EXEC_MAGIC_MASK;
    if (group == YW2_COMM_EXEC_MAIN || group == YW2_COMM_EXEC_ALIAS) {
        return "target_244ec8_instruction";
    }
    switch (swi & 0xFFFF) {
    case 0x01:
        return "before_339368";
    case 0x02:
        return "entry_339368";
    case 0x03:
        return "return_339368";
    case 0x04:
        return "before_2bec3c";
    case 0x05:
        return "entry_2bec3c";
    case 0x06:
        return "return_2bec3c";
    default:
        return "unknown";
    }
}

bool YW2CommExecCurrentThreadMatches(ARM_Dynarmic& cpu) {
    if (!YW2CommWriteWatch::FlowActive() ||
        cpu.GetID() != YW2CommWriteWatch::FlowProcessor()) {
        return false;
    }
    const u32 stack_top = YW2CommWriteWatch::FlowStackTop();
    const u32 sp = cpu.GetReg(13);
    constexpr u32 stack_window = 0x4000;
    constexpr u32 stack_slack = 0x100;
    const u64 stack_low = stack_top >= stack_window ? stack_top - stack_window : 0;
    const u64 stack_high = static_cast<u64>(stack_top) + stack_slack;
    return stack_top != 0 && static_cast<u64>(sp) >= stack_low &&
           static_cast<u64>(sp) <= stack_high;
}

void YW2LogCommExec(ARM_Dynarmic& cpu, Memory::MemorySystem& memory, u32 swi) {
    if (!YW2CommExecTraceEnabled() || !YW2CommExecCurrentThreadMatches(cpu)) {
        return;
    }

    static std::atomic<u64> sequence{};
    const u64 seq = ++sequence;
    if (seq > 4096) {
        return;
    }

    const u32 traced_pc = YW2CommExecPCFromTag(swi);
    const u32 callback_arg = YW2CommWriteWatch::GetCallbackArg();
    const u32 r0 = cpu.GetReg(0);
    const u32 r1 = cpu.GetReg(1);
    const u32 r2 = cpu.GetReg(2);
    const u32 r3 = cpu.GetReg(3);
    const u32 sp = cpu.GetReg(13);
    const u32 lr = cpu.GetReg(14);
    LOG_WARNING(Core_ARM11,
                "(YW2 COMM EXEC) seq={} kind={} traced_pc=0x{:08X} runtime_pc=0x{:08X} "
                "swi=0x{:06X} callback_arg=0x{:08X} ok9={} fail10={} "
                "r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X} "
                "r4=0x{:08X} r5=0x{:08X} r6=0x{:08X} r7=0x{:08X} "
                "r8=0x{:08X} r9=0x{:08X} r10=0x{:08X} r11=0x{:08X} "
                "r12=0x{:08X} sp=0x{:08X} lr=0x{:08X}",
                seq, YW2CommExecKind(swi), traced_pc, cpu.GetPC(), swi, callback_arg,
                callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 9) : 0xff,
                callback_arg != 0 ? YW2Read8Or(memory, callback_arg + 10) : 0xff,
                r0, r1, r2, r3, cpu.GetReg(4), cpu.GetReg(5), cpu.GetReg(6),
                cpu.GetReg(7), cpu.GetReg(8), cpu.GetReg(9), cpu.GetReg(10),
                cpu.GetReg(11), cpu.GetReg(12), sp, lr);

    if ((swi & YW2_COMM_EXEC_MAGIC_MASK) == YW2_COMM_EXEC_SPECIAL) {
        LOG_WARNING(Core_ARM11,
                    "(YW2 COMM EXEC MEMORY) seq={} kind={} traced_pc=0x{:08X} "
                    "r0_mem={} r1_mem={} callback_mem={} stack={}",
                    seq, YW2CommExecKind(swi), traced_pc,
                    YW2HexDump(memory, r0, 32), YW2HexDump(memory, r1, 32),
                    callback_arg != 0 ? YW2HexDump(memory, callback_arg - 0x10, 48)
                                      : std::string("none"),
                    YW2HexDump(memory, sp, 48));
    }
}

'''


arm_text = arm_text.replace(class_anchor, helpers + class_anchor, 1)


read_code_anchor = '''    std::optional<std::uint32_t> MemoryReadCode(VAddr vaddr) override {
'''
if read_code_anchor not in arm_text:
    raise RuntimeError("YW2 exact execution trace: MemoryReadCode anchor not found")

hook = f'''    void PreCodeTranslationHook(bool /*is_thumb*/, VAddr pc,
                                Dynarmic::A32::IREmitter& ir) override {{
        if (!YW2CommExecTraceEnabled()) {{
            return;
        }}
        const u32 tag = YW2CommExecTagForPC(pc);
        if (tag != 0) {{
            ir.{emitter_method}(tag);
        }}
    }}

'''
arm_text = arm_text.replace(read_code_anchor, hook + read_code_anchor, 1)


svc_anchor = '''    void CallSVC(std::uint32_t swi) override {
        svc_context.CallSVC(swi);
    }
'''
if svc_anchor not in arm_text:
    raise RuntimeError("YW2 exact execution trace: CallSVC anchor not found")
svc_replacement = '''    void CallSVC(std::uint32_t swi) override {
        if (YW2IsCommExecMagic(swi)) {
            YW2LogCommExec(parent, memory, swi);
            return;
        }
        svc_context.CallSVC(swi);
    }
'''
arm_text = arm_text.replace(svc_anchor, svc_replacement, 1)

ARM_PATH.write_text(arm_text)
print("Applied exact YW2 communication instruction and call-boundary trace patch")
