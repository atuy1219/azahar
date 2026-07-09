from pathlib import Path
import re

NWM_PATH = Path("src/core/hle/service/nwm/nwm_uds.cpp")
text = NWM_PATH.read_text()

MARKER = "(YW2 NWM EVENT) connection_status_event"

if MARKER not in text:
    pattern = re.compile(r"(?m)^([ \t]*)connection_status_event->(Signal|Clear)\(\);\s*$")

    def replace_call(match: re.Match[str]) -> str:
        indent = match.group(1)
        action = match.group(2)
        return f'''{indent}LOG_WARNING(Service_NWM,
{indent}            "{MARKER} action={action} func={{}} status={{}} self={{}} total={{}} max={{}} "
{indent}            "bitmask=0x{{:X}} changed=0x{{:X}} reason={{}} binds={{}}",
{indent}            __func__, static_cast<u32>(connection_status.status),
{indent}            static_cast<u16>(connection_status.network_node_id),
{indent}            static_cast<u32>(connection_status.total_nodes),
{indent}            static_cast<u32>(connection_status.max_nodes),
{indent}            static_cast<u32>(connection_status.node_bitmask),
{indent}            static_cast<u32>(connection_status.changed_nodes),
{indent}            static_cast<u32>(connection_status.status_change_reason), channel_data.size());
{indent}connection_status_event->{action}();'''

    text, count = pattern.subn(replace_call, text)
    if count == 0:
        print("Skipped YW2 NWM connection_status_event Signal/Clear trace patch: no calls found")
    else:
        print(f"Applied YW2 NWM connection_status_event Signal/Clear trace patch: {count} call(s)")
else:
    print("Skipped YW2 NWM connection_status_event Signal/Clear trace patch: already present")

NWM_PATH.write_text(text)
