
"""
Cross-platform macro execution utilities for Fiji.
"""

import os
import subprocess
import tempfile
import platform
from pathlib import Path
from typing import Optional, Dict, Any
from fiji_automated_analysis.utils.general.fiji_utils import validate_fiji_path, normalize_fiji_path


def _select_macos_bundled_java(fiji_root: Path) -> Optional[Path]:
    """Pick the best bundled Java home from a Fiji macOS installation."""

    java_root = fiji_root / "java"
    if not java_root.exists():
        return None

    java_homes: list[Path] = []
    for java_bin in java_root.glob("**/Contents/Home/bin/java"):
        java_homes.append(java_bin.parent.parent)

    if not java_homes:
        return None

    machine = platform.machine().lower()
    machine_markers = {
        "arm64": ("arm64", "aarch64"),
        "aarch64": ("arm64", "aarch64"),
        "x86_64": ("x64", "x86_64", "amd64"),
        "amd64": ("x64", "x86_64", "amd64"),
    }
    preferred_markers = machine_markers.get(machine, (machine,))

    def _score(path: Path) -> tuple[int, int, str]:
        path_str = str(path).lower()
        arch_score = 1 if any(marker in path_str for marker in preferred_markers) else 0
        version_score = 1 if any(token in path_str for token in ("jdk21", "zulu-21", "temurin-21", "jdk-21")) else 0
        return (arch_score, version_score, path_str)

    return sorted(java_homes, key=_score, reverse=True)[0]


def _prefer_macos_native_launcher(fiji_path: str) -> str:
    """Prefer the native Jaunch binary over the shell wrapper on macOS."""

    normalized = normalize_fiji_path(fiji_path)
    fiji_path_obj = Path(normalized)
    if fiji_path_obj.name != "fiji":
        return normalized

    fiji_root = fiji_path_obj.parent
    machine = platform.machine().lower()
    native_candidates = []
    if machine in {"arm64", "aarch64"}:
        native_candidates.append(
            fiji_root / "Fiji.app" / "Contents" / "MacOS" / "fiji-macos-arm64"
        )
    if machine in {"x86_64", "amd64"}:
        native_candidates.append(
            fiji_root / "Fiji.app" / "Contents" / "MacOS" / "fiji-macos-x64"
        )
    native_candidates.extend(
        [
            fiji_root / "Fiji.app" / "Contents" / "MacOS" / "fiji-macos-arm64",
            fiji_root / "Fiji.app" / "Contents" / "MacOS" / "fiji-macos-x64",
        ]
    )

    for candidate in native_candidates:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)

    return normalized


def _macro_requires_classic_ij1(macro_code: str) -> bool:
    """Detect macro fragments that need classic IJ1 UI classes on macOS."""

    macro_code_lower = macro_code.lower()
    return (
        "bio-formats importer" in macro_code_lower
        or "bio-formats macro extensions" in macro_code_lower
        or "ext.openimageplus" in macro_code_lower
        or "roimanager(" in macro_code_lower
    )


def _has_fiji_runtime_failure(stdout_text: str, stderr_text: str) -> bool:
    """Treat Java stack traces and macro errors as execution failures."""

    combined = "\n".join(part for part in (stdout_text, stderr_text) if part)
    failure_markers = (
        "Macro Error:",
        "DECONVOLUTION ERROR:",
        "Exception Details:",
        "java.lang.",
        "VerifyError",
        "NoClassDefFoundError",
    )
    return any(marker in combined for marker in failure_markers)


def _macro_launch_flag(system: str, use_classic_ij1: bool) -> str:
    """Choose the ImageJ macro mode without duplicating headless batch flags."""

    if system == "darwin" and use_classic_ij1:
        return "-macro"
    return "-batch"


def _utf16_code_units(value: str) -> list[int]:
    """Return Java-compatible UTF-16 code units for an ImageJ string."""

    encoded = value.encode("utf-16-be")
    return [
        int.from_bytes(encoded[index : index + 2], byteorder="big")
        for index in range(0, len(encoded), 2)
    ]


def _macro_char_code_expression(value: str) -> str:
    """Build ImageJ macro expressions for a non-ASCII string fragment."""

    code_units = _utf16_code_units(value)
    calls = []
    for start in range(0, len(code_units), 100):
        arguments = ",".join(str(code) for code in code_units[start : start + 100])
        calls.append(f"fromCharCode({arguments})")
    return " + ".join(calls)


def _encode_macro_string_literal(content: str) -> str:
    """Return an ASCII-only expression equivalent to one macro string literal."""

    if content.isascii():
        return f'"{content}"'

    parts: list[str] = []
    start = 0
    index = 0
    while index < len(content):
        is_ascii = ord(content[index]) < 128
        index += 1
        while index < len(content) and (ord(content[index]) < 128) == is_ascii:
            index += 1

        fragment = content[start:index]
        if is_ascii:
            if fragment:
                parts.append(f'"{fragment}"')
        else:
            parts.append(_macro_char_code_expression(fragment))
        start = index

    return " + ".join(parts) if parts else '""'


def _prepare_macro_source_for_ij1(macro_code: str) -> str:
    """Make macro source safe for ImageJ 1's ISO-8859-1 file reader.

    ImageJ 1's ``Macro_Runner`` decodes macro files as ISO-8859-1 even when
    the host filesystem and Python use UTF-8. Rebuild non-ASCII characters
    inside string literals with ``fromCharCode`` and replace non-ASCII comment
    text so paths retain their real Unicode value when the macro executes.
    """

    if macro_code.isascii():
        return macro_code

    output: list[str] = []
    index = 0
    length = len(macro_code)
    while index < length:
        if macro_code.startswith("//", index):
            line_end = macro_code.find("\n", index)
            if line_end < 0:
                line_end = length
            output.append(
                "".join(
                    char if ord(char) < 128 else "?"
                    for char in macro_code[index:line_end]
                )
            )
            index = line_end
            continue

        if macro_code.startswith("/*", index):
            comment_end = macro_code.find("*/", index + 2)
            if comment_end < 0:
                comment_end = length - 2
            comment_end += 2
            output.append(
                "".join(
                    char if ord(char) < 128 else "?"
                    for char in macro_code[index:comment_end]
                )
            )
            index = comment_end
            continue

        if macro_code[index] != '"':
            char = macro_code[index]
            output.append(char if ord(char) < 128 else "?")
            index += 1
            continue

        literal_end = index + 1
        while literal_end < length:
            if macro_code[literal_end] == '"':
                backslash_count = 0
                cursor = literal_end - 1
                while cursor > index and macro_code[cursor] == "\\":
                    backslash_count += 1
                    cursor -= 1
                if backslash_count % 2 == 0:
                    break
            literal_end += 1

        if literal_end >= length:
            output.append(
                "".join(
                    char if ord(char) < 128 else "?"
                    for char in macro_code[index:]
                )
            )
            break

        output.append(
            _encode_macro_string_literal(macro_code[index + 1 : literal_end])
        )
        index = literal_end + 1

    return "".join(output)


def run_fiji_macro(fiji_path: str, macro_code: str,
                  timeout: int = 300,
                  additional_args: Optional[list] = None,
                  verbose: bool = True,
                  cancel_event: Optional[Any] = None) -> Dict[str, Any]:
    """
    Run a Fiji macro with cross-platform support.

    Args:
        fiji_path: Path to Fiji executable
        macro_code: Macro code to execute
        timeout: Timeout in seconds (default: 300)
        additional_args: Additional command line arguments
        verbose: Whether to print output

    Returns:
        Dictionary with execution results
    """
    system = platform.system().lower()
    if system == "darwin":
        fiji_path = _prefer_macos_native_launcher(fiji_path)

    if not validate_fiji_path(fiji_path):
        return {
            "success": False,
            "error": f"Invalid Fiji / ImageJ path: {fiji_path}",
            "stdout": "",
            "stderr": ""
        }

    # Create temporary macro file
    prepared_macro_code = _prepare_macro_source_for_ij1(macro_code)
    with tempfile.NamedTemporaryFile(
        suffix=".ijm", delete=False, mode="w", encoding="ascii"
    ) as macro_file:
        macro_file.write(prepared_macro_code)
        macro_file_path = macro_file.name
    try:
        # Build command with platform-specific arguments
        cmd = [fiji_path]
        runtime_args: list[str] = []
        launcher_name = Path(fiji_path).name.lower()
        supports_jaunch_args = launcher_name == "fiji" or launcher_name.startswith("fiji-") or launcher_name.startswith("jaunch-")
        if additional_args is None:
            additional_args = (
                ["--default-gc"]
                if system == "darwin" and supports_jaunch_args
                else []
            )
        if supports_jaunch_args and not additional_args:
            additional_args = []
        use_classic_ij1 = system == "darwin" and _macro_requires_classic_ij1(macro_code)
        if supports_jaunch_args and additional_args is not None:
            arg_text = " ".join(additional_args).lower()
            if "--memory" not in arg_text and "--mem" not in arg_text and "--heap" not in arg_text:
                runtime_args.extend(["--memory", "4G"])
            if use_classic_ij1 and "--main-class" not in arg_text:
                runtime_args.extend(["--main-class", "ij.ImageJ"])

        # Launch process using Popen to allow cancellation
        use_shell = system == "windows"
        env = os.environ.copy()
        # Fiji bundles its own Python/Jython environment; inherited project Python
        # variables can crash the launcher on macOS.
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        if system == "darwin":
            fiji_root = None
            try:
                fiji_path_resolved = Path(fiji_path).resolve()
                parts = [part.lower() for part in fiji_path_resolved.parts]
                if "fiji.app" in parts:
                    idx = parts.index("fiji.app")
                    fiji_root = Path(*fiji_path_resolved.parts[: idx + 1])
            except Exception:
                fiji_root = None

            bundled_java = None
            if fiji_root is not None:
                bundled_java = _select_macos_bundled_java(fiji_root)

            if bundled_java and bundled_java.exists():
                env["JAVA_HOME"] = str(bundled_java)
                if supports_jaunch_args:
                    runtime_args.extend(["--java-home", str(bundled_java)])
            elif not env.get("JAVA_HOME"):
                java_home_cmd = ["/usr/libexec/java_home"]
                java_home_result = subprocess.run(
                    java_home_cmd, capture_output=True, text=True, check=False
                )
                if java_home_result.returncode == 0:
                    env["JAVA_HOME"] = java_home_result.stdout.strip()
                    if supports_jaunch_args:
                        runtime_args.extend(["--java-home", env["JAVA_HOME"]])

        if additional_args:
            runtime_args.extend(additional_args)
        if runtime_args:
            cmd.extend(runtime_args)
        launch_flag = _macro_launch_flag(system, use_classic_ij1)
        if "deconvolutionlab2 run" in macro_code.lower():
            launch_flag = "-batch"
        cmd.extend([launch_flag, macro_file_path])
        stdout_data = ""
        stderr_data = ""
        remaining = timeout
        step = 0.2
        if system == "darwin" and use_classic_ij1:
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                return {
                    "success": False,
                    "error": "Cancelled by user",
                    "stdout": stdout_data,
                    "stderr": stderr_data,
                }

            completed = subprocess.run(
                cmd,
                shell=use_shell,
                env=env,
                check=False,
                timeout=timeout,
            )
            proc = completed
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=use_shell,
                env=env
            )

            while True:
                if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    return {
                        "success": False,
                        "error": "Cancelled by user",
                        "stdout": stdout_data,
                        "stderr": stderr_data,
                    }

                try:
                    out, err = proc.communicate(timeout=step)
                    stdout_data += out or ""
                    stderr_data += err or ""
                    break
                except subprocess.TimeoutExpired:
                    remaining -= step
                    if remaining <= 0:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        return {
                            "success": False,
                            "error": f"Error: Fiji process timed out after {timeout} seconds",
                            "stdout": stdout_data,
                            "stderr": stderr_data,
                        }

        if verbose:
            print("Fiji Output:\n", stdout_data)
            if stderr_data:
                print("Fiji Errors:\n", stderr_data)

        runtime_failed = _has_fiji_runtime_failure(stdout_data, stderr_data)

        return {
            "success": proc.returncode == 0 and not runtime_failed,
            "returncode": proc.returncode,
            "stdout": stdout_data,
            "stderr": stderr_data,
            "error": None if proc.returncode == 0 and not runtime_failed else "Fiji reported runtime errors",
        }

    except subprocess.TimeoutExpired:
        error_msg = f"Error: Fiji process timed out after {timeout} seconds"
        if verbose:
            print(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "stdout": "",
            "stderr": ""
        }
    except Exception as e:
        error_msg = f"Error running Fiji macro: {str(e)}"
        if verbose:
            print(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "stdout": "",
            "stderr": ""
        }
    finally:
        # Clean up temporary file
        try:
            os.remove(macro_file_path)
        except OSError:
            pass  # File might already be deleted


def run_fiji_macro_batch(fiji_path: str, macro_codes: list,
                        timeout: int = 300,
                        verbose: bool = True) -> list:
    """
    Run multiple Fiji macros in sequence.

    Args:
        fiji_path: Path to Fiji executable
        macro_codes: List of macro codes to execute
        timeout: Timeout per macro in seconds
        verbose: Whether to print output

    Returns:
        List of execution results
    """
    results = []

    for i, macro_code in enumerate(macro_codes):
        if verbose:
            print(f"Running macro {i+1}/{len(macro_codes)}")

        result = run_fiji_macro(fiji_path, macro_code, timeout, verbose=verbose)
        results.append(result)

        if not result["success"]:
            if verbose:
                print(f"Macro {i+1} failed, stopping batch execution")
            break

    return results


# Backward compatibility
def _run_fiji_macro(fiji_path, macro_code):
    """Backward compatibility wrapper."""
    result = run_fiji_macro(fiji_path, macro_code, verbose=True)
    return result["success"]
