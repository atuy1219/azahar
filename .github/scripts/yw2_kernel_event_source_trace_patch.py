from pathlib import Path

PATH = Path("src/core/hle/kernel/event.cpp")
text = PATH.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 kernel event trace marker not found: {label}")
    text = text.replace(old, new, 1)


if "(YW2 KERNEL EVENT)" not in text:
    patch_once(
        '#include "common/assert.h"\n',
        '#include "common/assert.h"\n#include "common/logging/log.h"\n',
        "logging include",
    )

    patch_once(
        '''void Event::Signal() {
    signaled = true;
    WakeupAllWaitingThreads();
}

void Event::Clear() {
    signaled = false;
}
''',
        '''void Event::Signal() {
    if (name == "NWM::connection_status_event") {
        const auto caller = reinterpret_cast<std::uintptr_t>(__builtin_return_address(0));
        const auto& waiters = GetWaitingThreads();
        LOG_WARNING(Kernel_SVC,
                    "(YW2 KERNEL EVENT) action=Signal name={} signaled_before={} reset_type={} "
                    "waiters={} caller=0x{:016X}",
                    name, signaled, static_cast<u32>(reset_type), waiters.size(), caller);
        for (std::size_t i = 0; i < waiters.size() && i < 8; ++i) {
            const auto& waiter = waiters[i];
            LOG_WARNING(Kernel_SVC,
                        "(YW2 KERNEL EVENT) waiter index={} tid={} name={} status={}", i,
                        waiter ? waiter->GetThreadId() : 0,
                        waiter ? waiter->GetName() : std::string("<null>"),
                        waiter ? static_cast<u32>(waiter->status) : 0xFFFFFFFFU);
        }
    }
    signaled = true;
    WakeupAllWaitingThreads();
}

void Event::Clear() {
    if (name == "NWM::connection_status_event") {
        const auto caller = reinterpret_cast<std::uintptr_t>(__builtin_return_address(0));
        LOG_WARNING(Kernel_SVC,
                    "(YW2 KERNEL EVENT) action=Clear name={} signaled_before={} reset_type={} "
                    "waiters={} caller=0x{:016X}",
                    name, signaled, static_cast<u32>(reset_type), GetWaitingThreads().size(), caller);
    }
    signaled = false;
}
''',
        "Event Signal/Clear",
    )

    PATH.write_text(text)
    print("Applied YW2 kernel event source trace patch")
else:
    print("Skipped YW2 kernel event source trace patch: already present")
