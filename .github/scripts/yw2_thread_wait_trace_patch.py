from pathlib import Path

ARM_PATH = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
text = ARM_PATH.read_text()


def patch_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"YW2 thread wait trace ARM marker not found: {label}")
    text = text.replace(old, new, 1)


if "thread_wait_check_real" not in text:
    patch_once(
        '''    case 0x002055ac:
        return "thread_wait_check";
''',
        '''    case 0x002055ac:
        return "thread_wait_check";
    case 0x0020528c:
        return "thread_wait_check_real";
    case 0x0013f8c4:
        return "thread_wait_alt";
    case 0x005e7eec:
        return "shutdown_thread_wait";
''',
        "target names",
    )

    patch_once(
        '''    case 0x003660e8:
        return 19;
    default:
        return -1;
''',
        '''    case 0x003660e8:
        return 19;
    case 0x0020528c:
        return 20;
    case 0x0013f8c4:
        return 21;
    case 0x005e7eec:
        return 22;
    default:
        return -1;
''',
        "target indexes",
    )

    patch_once(
        '''    case 0x002055ac:
    case 0x00337680:
''',
        '''    case 0x002055ac:
    case 0x0020528c:
    case 0x0013f8c4:
    case 0x005e7eec:
    case 0x00337680:
''',
        "target matcher",
    )

    patch_once(
        '''    static std::atomic<u64> counters[20]{};
''',
        '''    static std::atomic<u64> counters[23]{};
''',
        "counter size",
    )

    ARM_PATH.write_text(text)
    print("Applied YW2 thread wait PC trace patch")
else:
    print("Skipped YW2 thread wait PC trace patch: already present")
