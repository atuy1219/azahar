from pathlib import Path
import re


ARM_PATH = Path("src/core/arm/dynarmic/arm_dynarmic.cpp")
CMAKE_PATH = Path("src/core/CMakeLists.txt")

arm_text = ARM_PATH.read_text()
cmake_text = CMAKE_PATH.read_text()

# PreCodeTranslationHook receives Dynarmic's A32 IREmitter. CallSupervisor accepts
# an IR::U32, not a host u32, so materialize the magic tag as an IR immediate.
imm_pattern = re.compile(
    r"(const u32 tag = YW2CommExecTagForPC\(pc\);\n"
    r"        if \(tag != 0\) \{\n"
    r"            ir\.[A-Za-z_]\w*)\(tag\);"
)
if "ir.CallSupervisor(ir.Imm32(tag));" not in arm_text:
    arm_text, replacements = imm_pattern.subn(r"\1(ir.Imm32(tag));", arm_text, count=1)
    if replacements != 1:
        raise RuntimeError(
            "YW2 exact execution build fix: supervisor emitter tag call not found"
        )

# a32_ir_emitter.h is normally compiled only inside Dynarmic. Dynarmic links
# merry::mcl privately, so its mcl include path is not propagated to citra_core.
# Link the same interface target instead of hard-coding a bundled include path;
# this works with either a discovered package or Dynarmic's bundled mcl.
fixed_link = "    target_link_libraries(citra_core PRIVATE dynarmic merry::mcl)\n"
if fixed_link not in cmake_text:
    marker = "    target_link_libraries(citra_core PRIVATE dynarmic)\n"
    if marker not in cmake_text:
        raise RuntimeError(
            "YW2 exact execution build fix: Dynarmic target link marker not found"
        )
    cmake_text = cmake_text.replace(marker, fixed_link, 1)

ARM_PATH.write_text(arm_text)
CMAKE_PATH.write_text(cmake_text)
print("Applied YW2 exact execution trace mcl dependency and IR immediate fix")
