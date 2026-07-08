from pathlib import Path
import re

path = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
text = path.read_text()

new_match = r'''u32 YW2MatchTraceTarget(u32 pc) {
    const u32 normalized = pc & ~u32{1};
    switch (normalized) {
    case 0x0034661c:
    case 0x0039661c:
        return 0x0034661c;
    case 0x00343d94:
    case 0x00393d94:
        return 0x00343d94;
    case 0x0034ef84:
    case 0x0039ef84:
        return 0x0034ef84;
    case 0x0034d4f8:
    case 0x0039d4f8:
        return 0x0034d4f8;
    case 0x0034e9d4:
    case 0x0039e9d4:
        return 0x0034e9d4;
    case 0x0034c328:
    case 0x0039c328:
        return 0x0034c328;
    case 0x0034d058:
    case 0x0039d058:
        return 0x0034d058;
    case 0x0034eee8:
    case 0x0039eee8:
        return 0x0034eee8;
    default:
        return 0;
    }
}

void YW2LogPacket'''

text, n = re.subn(
    r'u32 YW2MatchTraceTarget\(u32 pc\) \{.*?\n\}\n\nvoid YW2LogPacket',
    new_match,
    text,
    count=1,
    flags=re.S,
)
if n != 1:
    raise RuntimeError("failed to patch YW2MatchTraceTarget runtime aliases")

text = text.replace(
    "if (probe_count <= 20 || (probe_count % 10000) == 0) {",
    "if (probe_count <= 20 || (probe_count % 50000) == 0) {",
    1,
)

path.write_text(text)
print("Applied YW2 ARM runtime address alias patch")
