
"""
Cross-platform macro execution utilities for Fiji.
"""

import os
import subprocess
import tempfile
import platform
from typing import Optional, Dict, Any
from utils.general.fiji_utils import validate_fiji_path


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
        cmd = [fiji_path, "-macro", macro_file_path]
        if additional_args:
            cmd.extend(additional_args)

        # Launch process using Popen to allow cancellation
        system = platform.system().lower()
        use_shell = system == "windows"
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=use_shell
        )

        # Poll loop with cancellation and timeout handling
        stdout_data = ""
        stderr_data = ""
        # We'll use communicate with short timeouts to accumulate output
        remaining = timeout
        step = 0.2
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

        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": stdout_data,
            "stderr": stderr_data
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