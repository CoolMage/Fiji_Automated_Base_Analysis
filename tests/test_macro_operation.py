"""Tests for platform-specific Fiji/ImageJ macro launch arguments."""

from fiji_automated_analysis.utils.general import macros_operation
from fiji_automated_analysis.utils.general.macros_operation import (
    _has_fiji_runtime_failure,
    _macro_launch_flag,
    _prepare_macro_source_for_ij1,
    run_fiji_macro,
)


def test_linux_uses_direct_batch_macro_launch() -> None:
    assert _macro_launch_flag("linux", use_classic_ij1=False) == "-batch"
    assert _macro_launch_flag("linux", use_classic_ij1=True) == "-batch"


def test_macos_classic_ij1_keeps_macro_launch() -> None:
    assert _macro_launch_flag("darwin", use_classic_ij1=True) == "-macro"
    assert _macro_launch_flag("darwin", use_classic_ij1=False) == "-batch"


def test_windows_uses_batch_macro_launch() -> None:
    assert _macro_launch_flag("windows", use_classic_ij1=False) == "-batch"


def test_deconvolution_validation_marker_is_runtime_failure() -> None:
    assert _has_fiji_runtime_failure(
        "DECONVOLUTION ERROR: PSF calibration is missing",
        "",
    )


def test_unicode_macro_strings_are_encoded_for_imagej1() -> None:
    macro_code = (
        'inputPath = "/Users/test/Проекты/µm/😀.tif";\n'
        "// Комментарий\n"
    )

    prepared = _prepare_macro_source_for_ij1(macro_code)

    assert prepared.isascii()
    assert "fromCharCode(1055,1088,1086,1077,1082,1090,1099)" in prepared
    assert "fromCharCode(181)" in prepared
    assert "fromCharCode(55357,56832)" in prepared
    assert "Проекты" not in prepared
    assert "// ???????????" in prepared


def test_unicode_macro_strings_split_imagej_char_code_limit() -> None:
    macro_code = 'label = "' + ("Я" * 101) + '";'

    prepared = _prepare_macro_source_for_ij1(macro_code)

    assert prepared.isascii()
    assert prepared.count("fromCharCode(") == 2


def test_ascii_macro_source_is_unchanged() -> None:
    macro_code = 'print("plain ASCII");\nrun("Quit");'

    assert _prepare_macro_source_for_ij1(macro_code) == macro_code


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
