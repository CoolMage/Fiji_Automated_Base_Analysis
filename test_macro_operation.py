"""Tests for platform-specific Fiji/ImageJ macro launch arguments."""

from utils.general import macros_operation
from utils.general.macros_operation import _macro_launch_flag, run_fiji_macro


def test_linux_uses_direct_batch_macro_launch() -> None:
    assert _macro_launch_flag("linux", use_classic_ij1=False) == "-batch"
    assert _macro_launch_flag("linux", use_classic_ij1=True) == "-batch"


def test_macos_classic_ij1_keeps_macro_launch() -> None:
    assert _macro_launch_flag("darwin", use_classic_ij1=True) == "-macro"
    assert _macro_launch_flag("darwin", use_classic_ij1=False) == "-batch"


def test_windows_uses_batch_macro_launch() -> None:
    assert _macro_launch_flag("windows", use_classic_ij1=False) == "-batch"


def test_linux_jaunch_command_does_not_prepend_headless_to_macro(
    monkeypatch,
) -> None:
    captured = {}

    class FakeProcess:
        returncode = 0

        def communicate(self, timeout):
            return "", ""

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(macros_operation.platform, "system", lambda: "Linux")
    monkeypatch.setattr(macros_operation, "validate_fiji_path", lambda _path: True)
    monkeypatch.setattr(macros_operation.subprocess, "Popen", fake_popen)

    result = run_fiji_macro(
        "/home/user/Fiji.app/fiji-linux64",
        'print("ok");',
        verbose=False,
    )

    command = captured["command"]
    assert result["success"] is True
    assert "--headless" not in command
    assert "-macro" not in command
    batch_index = command.index("-batch")
    assert command[batch_index + 1].endswith(".ijm")
