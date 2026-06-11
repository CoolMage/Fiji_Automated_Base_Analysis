
"""
Cross-platform macro execution utilities for Fiji.
"""

import os
import subprocess
import tempfile
import platform
from pathlib import Path
from typing import Optional, Dict, Any
from utils.general.fiji_utils import validate_fiji_path, normalize_fiji_path


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
        "Exception Details:",
        "java.lang.",
        "VerifyError",
        "NoClassDefFoundError",
    )
    return any(marker in combined for marker in failure_markers)


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
            "error": f"Invalid Fiji path: {fiji_path}",
            "stdout": "",
            "stderr": ""
        }
    
    # Create temporary macro file
    with tempfile.NamedTemporaryFile(suffix='.ijm', delete=False, mode='w', encoding='utf-8') as macro_file:
        macro_file.write(macro_code)
        macro_file_path = macro_file.name
    try:
        # Build command with platform-specific arguments
        cmd = [fiji_path]
        runtime_args: list[str] = []
        launcher_name = Path(fiji_path).name.lower()
        supports_jaunch_args = launcher_name == "fiji" or launcher_name.startswith("fiji-") or launcher_name.startswith("jaunch-")
        if additional_args is None and system == "darwin":
            additional_args = ["--default-gc"]
        if supports_jaunch_args and not additional_args:
            additional_args = []
        use_classic_ij1 = system == "darwin" and _macro_requires_classic_ij1(macro_code)
        if supports_jaunch_args and additional_args is not None:
            arg_text = " ".join(additional_args).lower()
            if "--memory" not in arg_text and "--mem" not in arg_text and "--heap" not in arg_text:
                runtime_args.extend(["--memory", "4G"])
            if use_classic_ij1 and "--main-class" not in arg_text:
                runtime_args.extend(["--main-class", "ij.ImageJ"])
            if not use_classic_ij1 and "--headless" not in arg_text:
                runtime_args.append("--headless")

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
        cmd.extend(["-macro", macro_file_path])
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
