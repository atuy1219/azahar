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

# a32_ir_emitter.h is normally compiled inside the Dynarmic target, whose private
# include paths contain mcl. The YW2 instrumentation includes that header from
# citra_core, so expose only the required mcl include directory to citra_core.
include_line = (
    '    target_include_directories(citra_core PRIVATE '
    '"${CMAKE_SOURCE_DIR}/externals/dynarmic/externals/mcl/include")\n'
)
if include_line not in cmake_text:
    marker = "    target_link_libraries(citra_core PRIVATE dynarmic)\n"
    if marker not in cmake_text:
        raise RuntimeError(
            "YW2 exact execution build fix: Dynarmic target link marker not found"
        )
    cmake_text = cmake_text.replace(marker, marker + include_line, 1)

ARM_PATH.write_text(arm_text)
CMAKE_PATH.write_text(cmake_text)
print("Applied YW2 exact execution trace build dependency and IR immediate fix")
