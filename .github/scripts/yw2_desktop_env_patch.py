from pathlib import Path


FALSE_VALUES = ("0", "false", "off")


def replace_function(text: str, signature_prefix: str, replacement: str) -> tuple[str, bool]:
    start = text.find(signature_prefix)
    if start < 0:
        return text, False

    brace = text.find("{", start)
    if brace < 0:
        raise RuntimeError(f"function brace not found: {signature_prefix}")

    depth = 0
    end = None
    for i in range(brace, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise RuntimeError(f"function end not found: {signature_prefix}")

    return text[:start] + replacement + text[end:], True


def ensure_include(text: str, include_line: str) -> str:
    if include_line in text:
        return text
    if "#include <cstring>\n" in text:
        return text.replace("#include <cstring>\n", "#include <cstring>\n" + include_line, 1)
    return include_line + text


def enabled_helper_body(name: str, android_property: str, env_var: str) -> str:
    return (
        f"bool {name}() {{\n"
        "#ifdef ANDROID\n"
        "    char value[PROP_VALUE_MAX] = {};\n"
        f"    if (__system_property_get(\"{android_property}\", value) > 0) {{\n"
        "        return std::strcmp(value, \"0\") != 0 && std::strcmp(value, \"false\") != 0 &&\n"
        "               std::strcmp(value, \"off\") != 0;\n"
        "    }\n"
        "#endif\n"
        f"    if (const char* value = std::getenv(\"{env_var}\")) {{\n"
        "        return std::strcmp(value, \"0\") != 0 && std::strcmp(value, \"false\") != 0 &&\n"
        "               std::strcmp(value, \"off\") != 0;\n"
        "    }\n"
        "    return false;\n"
        "}"
    )


def trace_level_body() -> str:
    return (
        "u32 GetYW2TraceLevel() {\n"
        "#ifdef ANDROID\n"
        "    char android_enabled[PROP_VALUE_MAX] = {};\n"
        "    if (__system_property_get(\"debug.azahar.yw2_trace\", android_enabled) > 0) {\n"
        "        if (std::strcmp(android_enabled, \"0\") == 0 ||\n"
        "            std::strcmp(android_enabled, \"false\") == 0 ||\n"
        "            std::strcmp(android_enabled, \"off\") == 0) {\n"
        "            return 0;\n"
        "        }\n"
        "    }\n\n"
        "    char android_level[PROP_VALUE_MAX] = {};\n"
        "    if (__system_property_get(\"debug.azahar.yw2_trace_level\", android_level) > 0) {\n"
        "        if (std::strcmp(android_level, \"0\") == 0 || std::strcmp(android_level, \"off\") == 0) {\n"
        "            return 0;\n"
        "        }\n"
        "        if (std::strcmp(android_level, \"basic\") == 0) {\n"
        "            return 1;\n"
        "        }\n"
        "        if (std::strcmp(android_level, \"uds\") == 0) {\n"
        "            return 2;\n"
        "        }\n"
        "        if (std::strcmp(android_level, \"packet\") == 0) {\n"
        "            return 3;\n"
        "        }\n"
        "        if (std::strcmp(android_level, \"all\") == 0) {\n"
        "            return 4;\n"
        "        }\n"
        "        return 1;\n"
        "    }\n"
        "#endif\n\n"
        "    if (const char* enabled = std::getenv(\"AZAHAR_YW2_TRACE\")) {\n"
        "        if (std::strcmp(enabled, \"0\") == 0 || std::strcmp(enabled, \"false\") == 0 ||\n"
        "            std::strcmp(enabled, \"off\") == 0) {\n"
        "            return 0;\n"
        "        }\n"
        "    }\n"
        "    if (const char* level = std::getenv(\"AZAHAR_YW2_TRACE_LEVEL\")) {\n"
        "        if (std::strcmp(level, \"0\") == 0 || std::strcmp(level, \"off\") == 0) {\n"
        "            return 0;\n"
        "        }\n"
        "        if (std::strcmp(level, \"basic\") == 0) {\n"
        "            return 1;\n"
        "        }\n"
        "        if (std::strcmp(level, \"uds\") == 0) {\n"
        "            return 2;\n"
        "        }\n"
        "        if (std::strcmp(level, \"packet\") == 0) {\n"
        "            return 3;\n"
        "        }\n"
        "        if (std::strcmp(level, \"all\") == 0) {\n"
        "            return 4;\n"
        "        }\n"
        "        return 1;\n"
        "    }\n\n"
        "#ifdef ANDROID\n"
        "    return 1;\n"
        "#else\n"
        "    return 0;\n"
        "#endif\n"
        "}"
    )


def patch_nwm() -> None:
    path = Path("src/core/hle/service/nwm/nwm_uds.cpp")
    if not path.exists():
        return
    text = path.read_text()
    original = text
    text = ensure_include(text, "#include <cstdlib>\n")

    replacements = [
        ("u32 GetYW2TraceLevel()", trace_level_body()),
        (
            "bool YW2DummyNodeEnabled()",
            enabled_helper_body("YW2DummyNodeEnabled", "debug.azahar.yw2_dummy_node", "AZAHAR_YW2_DUMMY_NODE"),
        ),
        (
            "bool YW2DummyPacketEnabled()",
            enabled_helper_body("YW2DummyPacketEnabled", "debug.azahar.yw2_dummy_packet", "AZAHAR_YW2_DUMMY_PACKET"),
        ),
        (
            "bool YW2StatusPulseEnabled()",
            enabled_helper_body("YW2StatusPulseEnabled", "debug.azahar.yw2_status_pulse", "AZAHAR_YW2_STATUS_PULSE"),
        ),
        (
            "bool YW2SelfLoopbackEnabled()",
            enabled_helper_body("YW2SelfLoopbackEnabled", "debug.azahar.yw2_self_loopback", "AZAHAR_YW2_SELF_LOOPBACK"),
        ),
        (
            "bool YW2BindPulseEnabled()",
            enabled_helper_body("YW2BindPulseEnabled", "debug.azahar.yw2_bind_pulse", "AZAHAR_YW2_BIND_PULSE"),
        ),
        (
            "bool YW2NwmIpcTraceEnabled()",
            enabled_helper_body("YW2NwmIpcTraceEnabled", "debug.azahar.yw2_nwm_ipc_trace", "AZAHAR_YW2_NWM_IPC_TRACE"),
        ),
        (
            "bool YW2StatusQuietHostEnabled()",
            enabled_helper_body(
                "YW2StatusQuietHostEnabled",
                "debug.azahar.yw2_status_quiet_host",
                "AZAHAR_YW2_STATUS_QUIET_HOST",
            ),
        ),
    ]
    changed_names = []
    for signature, body in replacements:
        text, changed = replace_function(text, signature, body)
        if changed:
            changed_names.append(signature)

    if text != original:
        path.write_text(text)
        print(f"Applied YW2 desktop env patch to nwm_uds.cpp: {', '.join(changed_names)}")


def patch_svc() -> None:
    path = Path("src/core/hle/kernel/svc.cpp")
    if not path.exists():
        return
    text = path.read_text()
    original = text
    text = ensure_include(text, "#include <cstdlib>\n")
    text, changed = replace_function(
        text,
        "bool YW2SvcWaitTraceEnabled()",
        enabled_helper_body(
            "YW2SvcWaitTraceEnabled",
            "debug.azahar.yw2_svc_wait_trace",
            "AZAHAR_YW2_SVC_WAIT_TRACE",
        ),
    )
    if text != original:
        path.write_text(text)
        print(f"Applied YW2 desktop env patch to svc.cpp: YW2SvcWaitTraceEnabled={changed}")


patch_nwm()
patch_svc()
