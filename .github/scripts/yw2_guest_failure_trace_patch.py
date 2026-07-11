from pathlib import Path

ARM_PATH = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
arm_text = ARM_PATH.read_text()


def patch_arm(old: str, new: str, label: str) -> None:
    global arm_text
    if old not in arm_text:
        raise RuntimeError(f"YW2 guest failure ARM marker not found: {label}")
    arm_text = arm_text.replace(old, new, 1)


if "guest_worker_body" not in arm_text:
    patch_arm(
        '''    default:
        return "unknown";
    }
}

int YW2WorkerTargetIndex''',
        '''    default:
        if (target >= 0x00244ec8 && target < 0x00245100) {
            return "guest_worker_body";
        }
        return "unknown";
    }
}

int YW2WorkerTargetIndex''',
        "guest worker target name range",
    )

    patch_arm(
        '''    case 0x005e7eec:
        return 22;
    default:
        return -1;
''',
        '''    case 0x005e7eec:
        return 22;
    case 0x0012e424:
        return 24;
    case 0x0012e428:
        return 25;
    case 0x00205290:
        return 26;
    case 0x00205294:
        return 27;
    case 0x00205298:
        return 28;
    case 0x0020529c:
        return 29;
    case 0x002052a0:
        return 30;
    case 0x002052a4:
        return 31;
    case 0x002052a8:
        return 32;
    case 0x002052ac:
        return 33;
    case 0x002052b0:
        return 34;
    case 0x00261edc:
        return 35;
    case 0x00261ee0:
        return 36;
    case 0x00261ee4:
        return 37;
    default:
        if (target >= 0x00244ec8 && target < 0x00245100) {
            return 23;
        }
        return -1;
''',
        "guest worker target indexes",
    )

    patch_arm(
        '''    case 0x005e7eec:
    case 0x00337680:
''',
        '''    case 0x005e7eec:
    case 0x0012e424:
    case 0x0012e428:
    case 0x00205290:
    case 0x00205294:
    case 0x00205298:
    case 0x0020529c:
    case 0x002052a0:
    case 0x002052a4:
    case 0x002052a8:
    case 0x002052ac:
    case 0x002052b0:
    case 0x00261edc:
    case 0x00261ee0:
    case 0x00261ee4:
    case 0x00337680:
''',
        "guest worker exact target matcher",
    )

    patch_arm(
        '''    default:
        return 0;
    }
}

void YW2TraceWorkerBusyPC''',
        '''    default:
        if (normalized >= 0x00244ec8 && normalized < 0x00245100) {
            return normalized;
        }
        return 0;
    }
}

void YW2TraceWorkerBusyPC''',
        "guest worker target range matcher",
    )

    patch_arm(
        '''    static std::atomic<u64> counters[23]{};
''',
        '''    static std::atomic<u64> counters[38]{};
''',
        "guest worker counter size",
    )

    ARM_PATH.write_text(arm_text)
    print("Applied YW2 guest function and post-wait ARM trace patch")
else:
    print("Skipped YW2 guest function and post-wait ARM trace patch: already present")


SVC_PATH = Path("src/core/hle/kernel/svc.cpp")
svc_text = SVC_PATH.read_text()


def patch_svc(old: str, new: str, label: str) -> None:
    global svc_text
    if old not in svc_text:
        raise RuntimeError(f"YW2 guest failure SVC marker not found: {label}")
    svc_text = svc_text.replace(old, new, 1)


if "(YW2 SVC POST)" not in svc_text:
    patch_svc(
        '''    const FunctionDef* info = GetSVCInfo(immediate);
    LOG_TRACE(Kernel_SVC, "calling {}", info->name);
''',
        '''    const u32 yw2_svc_entry_pc = system.GetRunningCore().GetPC();
    const u32 yw2_svc_r0 = system.GetRunningCore().GetReg(0);
    const u32 yw2_svc_r1 = system.GetRunningCore().GetReg(1);
    const u32 yw2_svc_r2 = system.GetRunningCore().GetReg(2);
    const u32 yw2_svc_r3 = system.GetRunningCore().GetReg(3);
    const u32 yw2_svc_r4 = system.GetRunningCore().GetReg(4);
    const u32 yw2_svc_r5 = system.GetRunningCore().GetReg(5);
    const u32 yw2_svc_r6 = system.GetRunningCore().GetReg(6);
    const u32 yw2_svc_r7 = system.GetRunningCore().GetReg(7);
    const u32 yw2_svc_r8 = system.GetRunningCore().GetReg(8);
    const u32 yw2_svc_r9 = system.GetRunningCore().GetReg(9);
    const u32 yw2_svc_r10 = system.GetRunningCore().GetReg(10);
    const u32 yw2_svc_r11 = system.GetRunningCore().GetReg(11);
    const u32 yw2_svc_r12 = system.GetRunningCore().GetReg(12);
    const u32 yw2_svc_sp = system.GetRunningCore().GetReg(13);
    const u32 yw2_svc_lr = system.GetRunningCore().GetReg(14);

    const FunctionDef* info = GetSVCInfo(immediate);
    LOG_TRACE(Kernel_SVC, "calling {}", info->name);
''',
        "CallSVC entry register capture",
    )

    patch_svc(
        '''    }
    system.perf_stats->EndSVCProcessing();
}
''',
        '''    }

    if (YW2SvcWaitTraceEnabled() && immediate == 0x24 && yw2_svc_entry_pc == 0x0020528C) {
        static u64 yw2_poll_count = 0;
        const u64 poll_count = ++yw2_poll_count;
        const auto process = kernel.GetCurrentProcess();
        const auto read32 = [&](u32 address) -> u32 {
            if (!process || !memory.IsValidVirtualAddress(*process, address)) {
                return 0xFFFFFFFFU;
            }
            return memory.Read32(address);
        };
        const auto dump_words = [&](u32 base, u32 count) {
            std::string output;
            for (u32 i = 0; i < count; ++i) {
                if (i != 0) {
                    output.push_back(',');
                }
                output += fmt::format("{:08X}", read32(base + i * 4));
            }
            return output;
        };
        LOG_WARNING(Kernel_SVC,
                    "(YW2 SVC POST) poll={} entry_pc=0x{:08X} exit_pc=0x{:08X} "
                    "r0_before=0x{:08X} r0_after=0x{:08X} r9_before=0x{:08X} "
                    "r9_after=0x{:08X} r1=0x{:08X} r4=0x{:08X} r5=0x{:08X} "
                    "r6=0x{:08X} r7=0x{:08X} r8=0x{:08X} r10=0x{:08X} "
                    "r11=0x{:08X} r12=0x{:08X} sp=0x{:08X} lr=0x{:08X}",
                    poll_count, yw2_svc_entry_pc, system.GetRunningCore().GetPC(), yw2_svc_r0,
                    system.GetRunningCore().GetReg(0), yw2_svc_r9,
                    system.GetRunningCore().GetReg(9), yw2_svc_r1, yw2_svc_r4, yw2_svc_r5,
                    yw2_svc_r6, yw2_svc_r7, yw2_svc_r8, yw2_svc_r10, yw2_svc_r11,
                    yw2_svc_r12, yw2_svc_sp, yw2_svc_lr);
        LOG_WARNING(Kernel_SVC,
                    "(YW2 SVC OBJECT) poll={} reg=r1 base=0x{:08X} words={}",
                    poll_count, yw2_svc_r1, dump_words(yw2_svc_r1 - 0x20, 40));
        LOG_WARNING(Kernel_SVC,
                    "(YW2 SVC OBJECT) poll={} reg=r5 base=0x{:08X} words={}",
                    poll_count, yw2_svc_r5, dump_words(yw2_svc_r5 - 0x20, 40));
        LOG_WARNING(Kernel_SVC,
                    "(YW2 SVC OBJECT) poll={} reg=r6 base=0x{:08X} words={}",
                    poll_count, yw2_svc_r6, dump_words(yw2_svc_r6 - 0x10, 20));
        LOG_WARNING(Kernel_SVC,
                    "(YW2 SVC OBJECT) poll={} reg=r7 base=0x{:08X} words={}",
                    poll_count, yw2_svc_r7, dump_words(yw2_svc_r7 - 0x10, 20));
        LOG_WARNING(Kernel_SVC,
                    "(YW2 SVC OBJECT) poll={} reg=r8 base=0x{:08X} words={}",
                    poll_count, yw2_svc_r8, dump_words(yw2_svc_r8 - 0x10, 20));
        LOG_WARNING(Kernel_SVC,
                    "(YW2 SVC OBJECT) poll={} reg=r11 base=0x{:08X} words={}",
                    poll_count, yw2_svc_r11, dump_words(yw2_svc_r11 - 0x10, 20));
        LOG_WARNING(Kernel_SVC,
                    "(YW2 SVC STACK) poll={} sp=0x{:08X} words={}",
                    poll_count, yw2_svc_sp, dump_words(yw2_svc_sp, 24));
    }
    system.perf_stats->EndSVCProcessing();
}
''',
        "CallSVC post-wait trace",
    )

if "(YW2 THREAD RESULT)" not in svc_text:
    patch_svc(
        '''        LOG_WARNING(Kernel_SVC,
                    "(YW2 THREAD) ExitThread name={} pc=0x{:08X} lr=0x{:08X} sp=0x{:08X}",
                    thread_name, pc, lr, sp);
    }

    kernel.GetCurrentThreadManager().ExitCurrentThread();
''',
        '''        LOG_WARNING(Kernel_SVC,
                    "(YW2 THREAD) ExitThread name={} pc=0x{:08X} lr=0x{:08X} sp=0x{:08X}",
                    thread_name, pc, lr, sp);
    }

    if (current_thread) {
        const auto process = kernel.GetCurrentProcess();
        const auto read32 = [&](u32 address) -> u32 {
            if (!process || !memory.IsValidVirtualAddress(*process, address)) {
                return 0xFFFFFFFFU;
            }
            return memory.Read32(address);
        };
        const u32 original_arg = current_thread->stack_top;
        const u32 guest_function = read32(original_arg + 0x08);
        if (guest_function == 0x00244EC8) {
            LOG_WARNING(Kernel_SVC,
                        "(YW2 THREAD RESULT) function=0x{:08X} entry=0x{:08X} arg=0x{:08X} "
                        "r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X} "
                        "r4=0x{:08X} r5=0x{:08X} r6=0x{:08X} r7=0x{:08X} "
                        "r8=0x{:08X} r9=0x{:08X} r10=0x{:08X} r11=0x{:08X} "
                        "r12=0x{:08X} sp=0x{:08X} lr=0x{:08X}",
                        guest_function, current_thread->entry_point, original_arg,
                        system.GetRunningCore().GetReg(0), system.GetRunningCore().GetReg(1),
                        system.GetRunningCore().GetReg(2), system.GetRunningCore().GetReg(3),
                        system.GetRunningCore().GetReg(4), system.GetRunningCore().GetReg(5),
                        system.GetRunningCore().GetReg(6), system.GetRunningCore().GetReg(7),
                        system.GetRunningCore().GetReg(8), system.GetRunningCore().GetReg(9),
                        system.GetRunningCore().GetReg(10), system.GetRunningCore().GetReg(11),
                        system.GetRunningCore().GetReg(12), sp, lr);
            LOG_WARNING(Kernel_SVC,
                        "(YW2 THREAD RESULT MEMORY) function=0x{:08X} arg=0x{:08X} words="
                        "0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},"
                        "0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},0x{:08X},"
                        "0x{:08X},0x{:08X},0x{:08X},0x{:08X}",
                        guest_function, original_arg, read32(original_arg - 0x10),
                        read32(original_arg - 0x0C), read32(original_arg - 0x08),
                        read32(original_arg - 0x04), read32(original_arg + 0x00),
                        read32(original_arg + 0x04), read32(original_arg + 0x08),
                        read32(original_arg + 0x0C), read32(original_arg + 0x10),
                        read32(original_arg + 0x14), read32(original_arg + 0x18),
                        read32(original_arg + 0x1C), read32(original_arg + 0x20),
                        read32(original_arg + 0x24), read32(original_arg + 0x28),
                        read32(original_arg + 0x2C), read32(original_arg + 0x30),
                        read32(original_arg + 0x34), read32(original_arg + 0x38),
                        read32(original_arg + 0x3C));
        }
    }

    kernel.GetCurrentThreadManager().ExitCurrentThread();
''',
        "candidate thread exit result",
    )

SVC_PATH.write_text(svc_text)
print("Applied YW2 guest failure SVC and thread result trace patch")
