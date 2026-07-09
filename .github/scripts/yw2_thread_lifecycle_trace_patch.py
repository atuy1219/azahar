from pathlib import Path

SVC_PATH = Path("src/core/hle/kernel/svc.cpp")
text = SVC_PATH.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 thread lifecycle trace marker not found: {label}")
    text = text.replace(old, new, 1)


if "(YW2 THREAD) CreateThread" not in text:
    patch_once(
        '''    return current_process->handle_table.Create(out_handle, std::move(thread));
''',
        '''    const Result handle_result = current_process->handle_table.Create(out_handle, std::move(thread));
    if (entry_point == 0x0012E3E4 || entry_point == 0x0020528C ||
        entry_point == 0x0013F8C4 || entry_point == 0x005E7EEC) {
        LOG_WARNING(Kernel_SVC,
                    "(YW2 THREAD) CreateThread name={} entry=0x{:08X} arg=0x{:08X} "
                    "stack=0x{:08X} priority=0x{:08X} processor={} handle=0x{:08X} "
                    "caller_pc=0x{:08X} caller_lr=0x{:08X}",
                    name, entry_point, arg, stack_top, priority, processor_id, *out_handle,
                    system.GetRunningCore().GetPC(), system.GetRunningCore().GetReg(14));
    }
    return handle_result;
''',
        "CreateThread return",
    )

    patch_once(
        '''void SVC::ExitThread() {
    LOG_TRACE(Kernel_SVC, "called, pc=0x{:08X}", system.GetRunningCore().GetPC());

    kernel.GetCurrentThreadManager().ExitCurrentThread();
    system.PrepareReschedule();
}
''',
        '''void SVC::ExitThread() {
    LOG_TRACE(Kernel_SVC, "called, pc=0x{:08X}", system.GetRunningCore().GetPC());

    Thread* current_thread = kernel.GetCurrentThreadManager().GetCurrentThread();
    const std::string thread_name = current_thread ? current_thread->GetName() : std::string("<null>");
    const u32 pc = system.GetRunningCore().GetPC();
    const u32 lr = system.GetRunningCore().GetReg(14);
    const u32 sp = system.GetRunningCore().GetReg(13);
    if (thread_name.find("0012E3E4") != std::string::npos || pc == 0x0012E3E4 ||
        lr == 0x0012E3E4 || lr == 0x0020528C || lr == 0x0013F8C4 || lr == 0x005E7EEC) {
        LOG_WARNING(Kernel_SVC,
                    "(YW2 THREAD) ExitThread name={} pc=0x{:08X} lr=0x{:08X} sp=0x{:08X}",
                    thread_name, pc, lr, sp);
    }

    kernel.GetCurrentThreadManager().ExitCurrentThread();
    system.PrepareReschedule();
}
''',
        "ExitThread body",
    )

    SVC_PATH.write_text(text)
    print("Applied YW2 thread lifecycle trace patch")
else:
    print("Skipped YW2 thread lifecycle trace patch: already present")
