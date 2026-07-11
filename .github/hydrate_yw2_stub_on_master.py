from pathlib import Path
import re


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"YW2 master hydration marker not found: {label}")
    return text.replace(old, new, 1)


# Preserve the latest master's Android/network implementation and add only the
# build controls that the YW2 diagnostic workflow needs.
gradle_path = Path("src/android/app/build.gradle.kts")
gradle = gradle_path.read_text()

if "fun csvEnv(" not in gradle:
    gradle = replace_once(
        gradle,
        'val abiFilter = listOf("arm64-v8a", "x86_64")\n',
        '''fun csvEnv(name: String, defaultValue: String): List<String> =
    (System.getenv(name) ?: defaultValue)
        .split(',')
        .map { it.trim() }
        .filter { it.isNotEmpty() }

val abiFilter = csvEnv("ANDROID_ABI_FILTERS", "arm64-v8a,x86_64")
val cmakeTargets = csvEnv("ANDROID_CMAKE_TARGETS", "")
val skipVulkanValidationLayers = System.getenv("SKIP_VULKAN_VALIDATION_LAYERS") == "1"
''',
        "ABI filter declaration",
    )

if "targets(*cmakeTargets.toTypedArray())" not in gradle:
    pattern = re.compile(
        r'(?P<svc_indent>\s*)"-DENABLE_GDBSTUB=OFF"(?P<comment>[^\n]*)\n'
        r'(?P<close_indent>\s*)\)\n'
    )
    match = pattern.search(gradle)
    if match is None:
        raise RuntimeError("YW2 master hydration marker not found: CMake arguments")
    svc_indent = match.group("svc_indent")
    close_indent = match.group("close_indent")
    comment = match.group("comment")
    replacement = (
        f'{svc_indent}"-DENABLE_GDBSTUB=OFF",{comment}\n'
        f"{close_indent})\n"
        f"{close_indent}if (cmakeTargets.isNotEmpty()) {{\n"
        f"{close_indent}    targets(*cmakeTargets.toTypedArray())\n"
        f"{close_indent}}}\n"
    )
    gradle = gradle[: match.start()] + replacement + gradle[match.end() :]

if "if (!skipVulkanValidationLayers)" not in gradle:
    gradle = replace_once(
        gradle,
        '''tasks.named("preBuild") {
    dependsOn(unzipVulkanValidationLayers)
}
''',
        '''tasks.named("preBuild") {
    if (!skipVulkanValidationLayers) {
        dependsOn(unzipVulkanValidationLayers)
    }
}
''',
        "Vulkan validation preBuild task",
    )

gradle_path.write_text(gradle)


# Keep the established workflow workaround for generated setting-key validation.
config_path = Path("src/android/app/src/main/jni/config.cpp")
config = config_path.read_text()
start = config.find("void Config::Reload() {")
if start < 0:
    raise RuntimeError("YW2 master hydration marker not found: Config::Reload")
load_ini = config.find(
    "    LoadINI(DefaultINI::android_config_default_file_content);", start
)
if load_ini < 0:
    raise RuntimeError("YW2 master hydration marker not found: Config::Reload LoadINI")

replacement = '''void Config::Reload() {
    for (auto key = Settings::Keys::keys_array.begin(); key != Settings::Keys::keys_array.end();
         ++key) {
        const auto key_declaration_string = std::string(*key) + " =";
        bool is_omitted = false;
        for (const auto& omitted_key : DefaultINI::android_config_omitted_keys) {
            if (std::string(omitted_key) == std::string(*key)) {
                is_omitted = true;
                break;
            }
        }
        if (!is_omitted &&
            std::string(DefaultINI::android_config_default_file_content)
                    .find(key_declaration_string) == std::string::npos) {
            ASSERT_MSG(false,
                       "Validation of default config content (jni/default_ini.h) failed: Missing "
                       "declaration for key '{}'",
                       *key);
        }
    }
'''
config_path.write_text(config[:start] + replacement + config[load_ini:])

print("Hydrated buildable YW2 stub payload on the latest master source tree")
