from pathlib import Path
import re

PATH = Path("src/core/hle/service/nwm/nwm_uds.cpp")
text = PATH.read_text()

MARKER = "(YW2 NWM STATE)"

if MARKER not in text:
    status_pattern = re.compile(
        r"(?m)^([ \t]*)connection_status\.status = (NetworkStatus::[A-Za-z0-9_]+);\s*$"
    )

    def replace_status(match: re.Match[str]) -> str:
        indent, new_status = match.group(1), match.group(2)
        return f'''{indent}LOG_WARNING(Service_NWM,
{indent}            "{MARKER} status_write func={{}} old={{}} new={{}} self={{}} total={{}} max={{}} "
{indent}            "bitmask=0x{{:X}} changed=0x{{:X}} reason={{}} binds={{}}",
{indent}            __func__, static_cast<u32>(connection_status.status),
{indent}            static_cast<u32>({new_status}),
{indent}            static_cast<u16>(connection_status.network_node_id),
{indent}            static_cast<u32>(connection_status.total_nodes),
{indent}            static_cast<u32>(connection_status.max_nodes),
{indent}            static_cast<u32>(connection_status.node_bitmask),
{indent}            static_cast<u32>(connection_status.changed_nodes),
{indent}            static_cast<u32>(connection_status.status_change_reason), channel_data.size());
{indent}connection_status.status = {new_status};'''

    text, status_count = status_pattern.subn(replace_status, text)

    reset_pattern = re.compile(r"(?m)^([ \t]*)connection_status = \{\};\s*$")

    def replace_reset(match: re.Match[str]) -> str:
        indent = match.group(1)
        return f'''{indent}LOG_WARNING(Service_NWM,
{indent}            "{MARKER} reset_before func={{}} status={{}} self={{}} total={{}} max={{}} "
{indent}            "bitmask=0x{{:X}} changed=0x{{:X}} reason={{}} binds={{}}",
{indent}            __func__, static_cast<u32>(connection_status.status),
{indent}            static_cast<u16>(connection_status.network_node_id),
{indent}            static_cast<u32>(connection_status.total_nodes),
{indent}            static_cast<u32>(connection_status.max_nodes),
{indent}            static_cast<u32>(connection_status.node_bitmask),
{indent}            static_cast<u32>(connection_status.changed_nodes),
{indent}            static_cast<u32>(connection_status.status_change_reason), channel_data.size());
{indent}connection_status = {{}};
{indent}LOG_WARNING(Service_NWM,
{indent}            "{MARKER} reset_after func={{}} status={{}} self={{}} total={{}} max={{}} "
{indent}            "bitmask=0x{{:X}} changed=0x{{:X}} reason={{}} binds={{}}",
{indent}            __func__, static_cast<u32>(connection_status.status),
{indent}            static_cast<u16>(connection_status.network_node_id),
{indent}            static_cast<u32>(connection_status.total_nodes),
{indent}            static_cast<u32>(connection_status.max_nodes),
{indent}            static_cast<u32>(connection_status.node_bitmask),
{indent}            static_cast<u32>(connection_status.changed_nodes),
{indent}            static_cast<u32>(connection_status.status_change_reason), channel_data.size());'''

    text, reset_count = reset_pattern.subn(replace_reset, text)

    clear_pattern = re.compile(r"(?m)^([ \t]*)channel_data\.clear\(\);\s*$")

    def replace_clear(match: re.Match[str]) -> str:
        indent = match.group(1)
        return f'''{indent}LOG_WARNING(Service_NWM,
{indent}            "{MARKER} channel_clear_before func={{}} status={{}} binds={{}}",
{indent}            __func__, static_cast<u32>(connection_status.status), channel_data.size());
{indent}channel_data.clear();
{indent}LOG_WARNING(Service_NWM,
{indent}            "{MARKER} channel_clear_after func={{}} status={{}} binds={{}}",
{indent}            __func__, static_cast<u32>(connection_status.status), channel_data.size());'''

    text, clear_count = clear_pattern.subn(replace_clear, text)

    erase_pattern = re.compile(r"(?m)^([ \t]*)channel_data\.erase\(([^\n;]+)\);\s*$")

    def replace_erase(match: re.Match[str]) -> str:
        indent, argument = match.group(1), match.group(2)
        return f'''{indent}LOG_WARNING(Service_NWM,
{indent}            "{MARKER} channel_erase_before func={{}} status={{}} binds={{}}",
{indent}            __func__, static_cast<u32>(connection_status.status), channel_data.size());
{indent}channel_data.erase({argument});
{indent}LOG_WARNING(Service_NWM,
{indent}            "{MARKER} channel_erase_after func={{}} status={{}} binds={{}}",
{indent}            __func__, static_cast<u32>(connection_status.status), channel_data.size());'''

    text, erase_count = erase_pattern.subn(replace_erase, text)

    if status_count == 0 or reset_count == 0 or clear_count == 0:
        raise RuntimeError(
            "YW2 NWM state transition trace found insufficient markers: "
            f"status={status_count} reset={reset_count} clear={clear_count} erase={erase_count}"
        )

    PATH.write_text(text)
    print(
        "Applied YW2 NWM state transition trace patch: "
        f"status={status_count} reset={reset_count} clear={clear_count} erase={erase_count}"
    )
else:
    print("Skipped YW2 NWM state transition trace patch: already present")
