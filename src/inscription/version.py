from __future__ import annotations

INSCRIPTION_VERSION = "0.63.0.dev0"
LANGUAGE_VERSION = "v0.63"
INTERFACE_JSON_FORMAT = "inscription-interface-v1"
C_HEADER_FORMAT = "inscription-c-header-v1"
RELEASE_FORMAT = "inscription-release-v1"
PACKAGE_MANIFEST_FORMAT = "package-ins-v1"
BUILD_SCRIPT_FORMAT = "build-ins-v1"
REQUIRED_LLVM_MAJOR = 22


def version_payload() -> dict[str, object]:
    return {
        "inscription_version": INSCRIPTION_VERSION,
        "language_version": LANGUAGE_VERSION,
        "required_llvm_major": REQUIRED_LLVM_MAJOR,
        "interface_json_format": INTERFACE_JSON_FORMAT,
        "release_format": RELEASE_FORMAT,
        "package_manifest_format": PACKAGE_MANIFEST_FORMAT,
        "build_script_format": BUILD_SCRIPT_FORMAT,
    }


def version_lines() -> tuple[str, ...]:
    return (
        f"Inscription version: {INSCRIPTION_VERSION}",
        f"Language version: {LANGUAGE_VERSION}",
        f"Required LLVM/MLIR: {REQUIRED_LLVM_MAJOR}.x",
        f"Interface JSON format: {INTERFACE_JSON_FORMAT}",
        f"Release format: {RELEASE_FORMAT}",
        f"Package manifest format: {PACKAGE_MANIFEST_FORMAT}",
        f"Build script format: {BUILD_SCRIPT_FORMAT}",
    )
