from pathlib import Path

path = Path("src/core/hle/kernel/svc.cpp")
text = path.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 SVC wait trace patch marker not found: {label}")
    text = text.replace(old, new, 1)


if "debug.azahar.yw2_svc_wait_trace" not in text:
    patch_once(
        "#include <chrono>\n#include <fmt/format.h>\n",
        "#include <chrono>\n"
        "#include <cstring>\n"
        "#ifdef ANDROID\n"
        "#include <sys/system_properties.h>\n"
        "#endif\n"
        "#include <fmt/format.h>\n",
        "SVC wait trace includes",
    )

    patch_once(
        "namespace Kernel {\n\n",
        "namespace Kernel {\n\n"
        "namespace {\n\n"
        "bool YW2SvcWaitTraceEnabled() {\n"
        "#ifdef ANDROID\n"
        "    char value[PROP_VALUE_MAX] = {};\n"
        "    if (__system_property_get(\"debug.azahar.yw2_svc_wait_trace\", value) <= 0) {\n"
        "        return false;\n"
        "    }\n"
        "    return std::strcmp(value, \"0\") != 0 && std::strcmp(value, \"false\") != 0 &&\n"
        "           std::strcmp(value, \"off\") != 0;\n"
        "#else\n"
        "    return false;\n"
        "#endif\n"
        "}\n\n"
        "} // namespace\n\n",
        "SVC wait trace property helper",
    )

patch_once(
    "    void WakeUp(ThreadWakeupReason reason, std::shared_ptr<Thread> thread,\n"
    "                std::shared_ptr<WaitObject> object) {\n\n"
    "        if (reason == ThreadWakeupReason::Timeout) {\n",
    "    void WakeUp(ThreadWakeupReason reason, std::shared_ptr<Thread> thread,\n"
    "                std::shared_ptr<WaitObject> object) {\n\n"
    "        if (YW2SvcWaitTraceEnabled()) {\n"
    "            if (object) {\n"
    "                LOG_WARNING(Kernel_SVC,\n"
    "                            \"(YW2 WAIT) WakeUp sync reason={} tid={} object={}:{} do_output={}\",\n"
    "                            static_cast<u32>(reason), thread ? thread->GetThreadId() : 0,\n"
    "                            object->GetTypeName(), object->GetName(), do_output);\n"
    "            } else {\n"
    "                LOG_WARNING(Kernel_SVC,\n"
    "                            \"(YW2 WAIT) WakeUp sync reason={} tid={} object=<null> do_output={}\",\n"
    "                            static_cast<u32>(reason), thread ? thread->GetThreadId() : 0,\n"
    "                            do_output);\n"
    "            }\n"
    "        }\n\n"
    "        if (reason == ThreadWakeupReason::Timeout) {\n",
    "SVC_SyncCallback wake trace",
)

patch_once(
    "    void WakeUp(ThreadWakeupReason reason, std::shared_ptr<Thread> thread,\n"
    "                std::shared_ptr<WaitObject> object) {\n\n"
    "        ASSERT(thread->status == ThreadStatus::WaitSynchAny);\n",
    "    void WakeUp(ThreadWakeupReason reason, std::shared_ptr<Thread> thread,\n"
    "                std::shared_ptr<WaitObject> object) {\n\n"
    "        if (YW2SvcWaitTraceEnabled()) {\n"
    "            if (object) {\n"
    "                LOG_WARNING(Kernel_SVC, \"(YW2 WAIT) WakeUp ipc reason={} tid={} object={}:{}\",\n"
    "                            static_cast<u32>(reason), thread ? thread->GetThreadId() : 0,\n"
    "                            object->GetTypeName(), object->GetName());\n"
    "            } else {\n"
    "                LOG_WARNING(Kernel_SVC, \"(YW2 WAIT) WakeUp ipc reason={} tid={} object=<null>\",\n"
    "                            static_cast<u32>(reason), thread ? thread->GetThreadId() : 0);\n"
    "            }\n"
    "        }\n\n"
    "        ASSERT(thread->status == ThreadStatus::WaitSynchAny);\n",
    "SVC_IPCCallback wake trace",
)

patch_once(
    "    LOG_TRACE(Kernel_SVC, \"called handle=0x{:08X}({}:{}), nanoseconds={}\", handle,\n"
    "              object->GetTypeName(), object->GetName(), nano_seconds);\n\n"
    "    if (object->ShouldWait(thread)) {\n",
    "    LOG_TRACE(Kernel_SVC, \"called handle=0x{:08X}({}:{}), nanoseconds={}\", handle,\n"
    "              object->GetTypeName(), object->GetName(), nano_seconds);\n\n"
    "    const bool yw2_wait_trace = YW2SvcWaitTraceEnabled();\n"
    "    const bool yw2_should_wait = object->ShouldWait(thread);\n"
    "    if (yw2_wait_trace) {\n"
    "        LOG_WARNING(Kernel_SVC,\n"
    "                    \"(YW2 WAIT) WaitSynchronization1 enter tid={} pc=0x{:08X} handle=0x{:08X} object={}:{} timeout={} should_wait={}\",\n"
    "                    thread ? thread->GetThreadId() : 0, system.GetRunningCore().GetPC(), handle,\n"
    "                    object->GetTypeName(), object->GetName(), nano_seconds, yw2_should_wait);\n"
    "    }\n\n"
    "    if (yw2_should_wait) {\n",
    "WaitSynchronization1 entry trace",
)

patch_once(
    "        // Note: The output of this SVC will be set to ResultSuccess if the thread\n"
    "        // resumes due to a signal in its wait objects.\n"
    "        // Otherwise we retain the default value of timeout.\n"
    "        return ResultTimeout;\n"
    "    }\n\n"
    "    object->Acquire(thread);\n"
    "    return ResultSuccess;\n",
    "        // Note: The output of this SVC will be set to ResultSuccess if the thread\n"
    "        // resumes due to a signal in its wait objects.\n"
    "        // Otherwise we retain the default value of timeout.\n"
    "        if (yw2_wait_trace) {\n"
    "            LOG_WARNING(Kernel_SVC,\n"
    "                        \"(YW2 WAIT) WaitSynchronization1 block tid={} handle=0x{:08X} timeout={}\",\n"
    "                        thread ? thread->GetThreadId() : 0, handle, nano_seconds);\n"
    "        }\n"
    "        return ResultTimeout;\n"
    "    }\n\n"
    "    object->Acquire(thread);\n"
    "    if (yw2_wait_trace) {\n"
    "        LOG_WARNING(Kernel_SVC,\n"
    "                    \"(YW2 WAIT) WaitSynchronization1 ready tid={} handle=0x{:08X} object={}:{}\",\n"
    "                    thread ? thread->GetThreadId() : 0, handle, object->GetTypeName(),\n"
    "                    object->GetName());\n"
    "    }\n"
    "    return ResultSuccess;\n",
    "WaitSynchronization1 block/ready trace",
)

patch_once(
    "    using ObjectPtr = std::shared_ptr<WaitObject>;\n"
    "    std::vector<ObjectPtr> objects(handle_count);\n\n"
    "    for (int i = 0; i < handle_count; ++i) {\n"
    "        Handle handle = memory.Read32(handles_address + i * sizeof(Handle));\n"
    "        auto object = kernel.GetCurrentProcess()->handle_table.Get<WaitObject>(handle);\n"
    "        R_UNLESS(object, ResultInvalidHandle);\n"
    "        objects[i] = object;\n"
    "    }\n\n"
    "    if (wait_all) {\n",
    "    using ObjectPtr = std::shared_ptr<WaitObject>;\n"
    "    std::vector<ObjectPtr> objects(handle_count);\n"
    "    std::array<Handle, 8> yw2_first_handles{};\n\n"
    "    for (int i = 0; i < handle_count; ++i) {\n"
    "        Handle handle = memory.Read32(handles_address + i * sizeof(Handle));\n"
    "        if (i < static_cast<int>(yw2_first_handles.size())) {\n"
    "            yw2_first_handles[i] = handle;\n"
    "        }\n"
    "        auto object = kernel.GetCurrentProcess()->handle_table.Get<WaitObject>(handle);\n"
    "        R_UNLESS(object, ResultInvalidHandle);\n"
    "        objects[i] = object;\n"
    "    }\n\n"
    "    const bool yw2_wait_trace = YW2SvcWaitTraceEnabled();\n"
    "    if (yw2_wait_trace) {\n"
    "        LOG_WARNING(Kernel_SVC,\n"
    "                    \"(YW2 WAIT) WaitSynchronizationN enter tid={} pc=0x{:08X} count={} wait_all={} timeout={} handles={:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X}\",\n"
    "                    thread ? thread->GetThreadId() : 0, system.GetRunningCore().GetPC(),\n"
    "                    handle_count, wait_all, nano_seconds, yw2_first_handles[0],\n"
    "                    yw2_first_handles[1], yw2_first_handles[2], yw2_first_handles[3],\n"
    "                    yw2_first_handles[4], yw2_first_handles[5], yw2_first_handles[6],\n"
    "                    yw2_first_handles[7]);\n"
    "    }\n\n"
    "    if (wait_all) {\n",
    "WaitSynchronizationN entry trace",
)

patch_once(
    "        if (all_available) {\n"
    "            // We can acquire all objects right now, do so.\n"
    "            for (auto& object : objects)\n"
    "                object->Acquire(thread);\n"
    "            // Note: In this case, the `out` parameter is not set,\n"
    "            // and retains whatever value it had before.\n"
    "            return ResultSuccess;\n"
    "        }\n",
    "        if (all_available) {\n"
    "            // We can acquire all objects right now, do so.\n"
    "            for (auto& object : objects)\n"
    "                object->Acquire(thread);\n"
    "            // Note: In this case, the `out` parameter is not set,\n"
    "            // and retains whatever value it had before.\n"
    "            if (yw2_wait_trace) {\n"
    "                LOG_WARNING(Kernel_SVC, \"(YW2 WAIT) WaitSynchronizationN ready_all tid={} count={}\",\n"
    "                            thread ? thread->GetThreadId() : 0, handle_count);\n"
    "            }\n"
    "            return ResultSuccess;\n"
    "        }\n",
    "WaitSynchronizationN ready_all trace",
)

patch_once(
    "        // Note: The output of this SVC will be set to ResultSuccess if the thread resumes due to\n"
    "        // a signal in one of its wait objects.\n"
    "        return ResultTimeout;\n"
    "    } else {\n",
    "        // Note: The output of this SVC will be set to ResultSuccess if the thread resumes due to\n"
    "        // a signal in one of its wait objects.\n"
    "        if (yw2_wait_trace) {\n"
    "            LOG_WARNING(Kernel_SVC,\n"
    "                        \"(YW2 WAIT) WaitSynchronizationN block_all tid={} count={} timeout={}\",\n"
    "                        thread ? thread->GetThreadId() : 0, handle_count, nano_seconds);\n"
    "        }\n"
    "        return ResultTimeout;\n"
    "    } else {\n",
    "WaitSynchronizationN block_all trace",
)

patch_once(
    "        if (itr != objects.end()) {\n"
    "            // We found a ready object, acquire it and set the result value\n"
    "            WaitObject* object = itr->get();\n"
    "            object->Acquire(thread);\n"
    "            *out = static_cast<s32>(std::distance(objects.begin(), itr));\n"
    "            return ResultSuccess;\n"
    "        }\n",
    "        if (itr != objects.end()) {\n"
    "            // We found a ready object, acquire it and set the result value\n"
    "            WaitObject* object = itr->get();\n"
    "            object->Acquire(thread);\n"
    "            *out = static_cast<s32>(std::distance(objects.begin(), itr));\n"
    "            if (yw2_wait_trace) {\n"
    "                LOG_WARNING(Kernel_SVC,\n"
    "                            \"(YW2 WAIT) WaitSynchronizationN ready_any tid={} index={} object={}:{}\",\n"
    "                            thread ? thread->GetThreadId() : 0, *out, object->GetTypeName(),\n"
    "                            object->GetName());\n"
    "            }\n"
    "            return ResultSuccess;\n"
    "        }\n",
    "WaitSynchronizationN ready_any trace",
)

patch_once(
    "        // Note: The output of this SVC will be set to ResultSuccess if the thread resumes due to a\n"
    "        // signal in one of its wait objects.\n"
    "        // Otherwise we retain the default value of timeout, and -1 in the out parameter\n"
    "        *out = -1;\n"
    "        return ResultTimeout;\n"
    "    }\n"
    "}\n\n"
    "static Result ReceiveIPCRequest",
    "        // Note: The output of this SVC will be set to ResultSuccess if the thread resumes due to a\n"
    "        // signal in one of its wait objects.\n"
    "        // Otherwise we retain the default value of timeout, and -1 in the out parameter\n"
    "        *out = -1;\n"
    "        if (yw2_wait_trace) {\n"
    "            LOG_WARNING(Kernel_SVC,\n"
    "                        \"(YW2 WAIT) WaitSynchronizationN block_any tid={} count={} timeout={}\",\n"
    "                        thread ? thread->GetThreadId() : 0, handle_count, nano_seconds);\n"
    "        }\n"
    "        return ResultTimeout;\n"
    "    }\n"
    "}\n\n"
    "static Result ReceiveIPCRequest",
    "WaitSynchronizationN block_any trace",
)

patch_once(
    "    using ObjectPtr = std::shared_ptr<WaitObject>;\n"
    "    std::vector<ObjectPtr> objects(handle_count);\n\n"
    "    std::shared_ptr<Process> current_process = kernel.GetCurrentProcess();\n\n"
    "    for (int i = 0; i < handle_count; ++i) {\n"
    "        Handle handle = memory.Read32(handles_address + i * sizeof(Handle));\n"
    "        auto object = current_process->handle_table.Get<WaitObject>(handle);\n"
    "        R_UNLESS(object, ResultInvalidHandle);\n"
    "        objects[i] = object;\n"
    "    }\n\n"
    "    // We are also sending a command reply.\n",
    "    using ObjectPtr = std::shared_ptr<WaitObject>;\n"
    "    std::vector<ObjectPtr> objects(handle_count);\n"
    "    std::array<Handle, 8> yw2_first_handles{};\n\n"
    "    std::shared_ptr<Process> current_process = kernel.GetCurrentProcess();\n\n"
    "    for (int i = 0; i < handle_count; ++i) {\n"
    "        Handle handle = memory.Read32(handles_address + i * sizeof(Handle));\n"
    "        if (i < static_cast<int>(yw2_first_handles.size())) {\n"
    "            yw2_first_handles[i] = handle;\n"
    "        }\n"
    "        auto object = current_process->handle_table.Get<WaitObject>(handle);\n"
    "        R_UNLESS(object, ResultInvalidHandle);\n"
    "        objects[i] = object;\n"
    "    }\n\n"
    "    const bool yw2_wait_trace = YW2SvcWaitTraceEnabled();\n"
    "    if (yw2_wait_trace) {\n"
    "        LOG_WARNING(Kernel_SVC,\n"
    "                    \"(YW2 WAIT) ReplyAndReceive enter tid={} pc=0x{:08X} count={} reply=0x{:08X} handles={:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X}\",\n"
    "                    kernel.GetCurrentThreadManager().GetCurrentThread()\n"
    "                        ? kernel.GetCurrentThreadManager().GetCurrentThread()->GetThreadId()\n"
    "                        : 0,\n"
    "                    system.GetRunningCore().GetPC(), handle_count, reply_target,\n"
    "                    yw2_first_handles[0], yw2_first_handles[1], yw2_first_handles[2],\n"
    "                    yw2_first_handles[3], yw2_first_handles[4], yw2_first_handles[5],\n"
    "                    yw2_first_handles[6], yw2_first_handles[7]);\n"
    "    }\n\n"
    "    // We are also sending a command reply.\n",
    "ReplyAndReceive entry trace",
)

patch_once(
    "    thread->wakeup_callback = std::make_shared<SVC_IPCCallback>(system);\n\n"
    "    system.PrepareReschedule();\n\n"
    "    // Note: The output of this SVC will be set to ResultSuccess if the thread resumes due to a\n",
    "    thread->wakeup_callback = std::make_shared<SVC_IPCCallback>(system);\n\n"
    "    if (yw2_wait_trace) {\n"
    "        LOG_WARNING(Kernel_SVC, \"(YW2 WAIT) ReplyAndReceive block tid={} count={} reply=0x{:08X}\",\n"
    "                    thread ? thread->GetThreadId() : 0, handle_count, reply_target);\n"
    "    }\n\n"
    "    system.PrepareReschedule();\n\n"
    "    // Note: The output of this SVC will be set to ResultSuccess if the thread resumes due to a\n",
    "ReplyAndReceive block trace",
)

patch_once(
    "    LOG_TRACE(Kernel_SVC, \"called handle=0x{:08X}, address=0x{:08X}, type=0x{:08X}, value=0x{:08X}\",\n"
    "              handle, address, type, value);\n\n"
    "    std::shared_ptr<AddressArbiter> arbiter =\n",
    "    LOG_TRACE(Kernel_SVC, \"called handle=0x{:08X}, address=0x{:08X}, type=0x{:08X}, value=0x{:08X}\",\n"
    "              handle, address, type, value);\n\n"
    "    if (YW2SvcWaitTraceEnabled()) {\n"
    "        Thread* thread = kernel.GetCurrentThreadManager().GetCurrentThread();\n"
    "        LOG_WARNING(Kernel_SVC,\n"
    "                    \"(YW2 WAIT) ArbitrateAddress enter tid={} pc=0x{:08X} handle=0x{:08X} address=0x{:08X} type=0x{:08X} value=0x{:08X} timeout={}\",\n"
    "                    thread ? thread->GetThreadId() : 0, system.GetRunningCore().GetPC(), handle,\n"
    "                    address, type, value, nanoseconds);\n"
    "    }\n\n"
    "    std::shared_ptr<AddressArbiter> arbiter =\n",
    "ArbitrateAddress entry trace",
)

patch_once(
    "    // TODO(Subv): Identify in which specific cases this call should cause a reschedule.\n"
    "    system.PrepareReschedule();\n"
    "    return res;\n"
    "}\n\n"
    "void SVC::Break",
    "    // TODO(Subv): Identify in which specific cases this call should cause a reschedule.\n"
    "    if (YW2SvcWaitTraceEnabled()) {\n"
    "        Thread* thread = kernel.GetCurrentThreadManager().GetCurrentThread();\n"
    "        LOG_WARNING(Kernel_SVC, \"(YW2 WAIT) ArbitrateAddress return tid={} address=0x{:08X}\",\n"
    "                    thread ? thread->GetThreadId() : 0, address);\n"
    "    }\n"
    "    system.PrepareReschedule();\n"
    "    return res;\n"
    "}\n\n"
    "void SVC::Break",
    "ArbitrateAddress return trace",
)

patch_once(
    "void SVC::SleepThread(s64 nanoseconds) {\n"
    "    LOG_TRACE(Kernel_SVC, \"called nanoseconds={}\", nanoseconds);\n\n"
    "    ThreadManager& thread_manager = kernel.GetCurrentThreadManager();\n",
    "void SVC::SleepThread(s64 nanoseconds) {\n"
    "    LOG_TRACE(Kernel_SVC, \"called nanoseconds={}\", nanoseconds);\n\n"
    "    if (YW2SvcWaitTraceEnabled() && nanoseconds != 0) {\n"
    "        Thread* thread = kernel.GetCurrentThreadManager().GetCurrentThread();\n"
    "        LOG_WARNING(Kernel_SVC, \"(YW2 WAIT) SleepThread tid={} pc=0x{:08X} ns={}\",\n"
    "                    thread ? thread->GetThreadId() : 0, system.GetRunningCore().GetPC(),\n"
    "                    nanoseconds);\n"
    "    }\n\n"
    "    ThreadManager& thread_manager = kernel.GetCurrentThreadManager();\n",
    "SleepThread trace",
)

path.write_text(text)
print("Applied YW2 SVC wait trace patch")
