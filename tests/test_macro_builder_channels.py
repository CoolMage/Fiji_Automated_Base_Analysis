from utils.general.macro_builder import MacroBuilder, MacroCommand


def test_macro_command_applies_to_specified_channels():
    builder = MacroBuilder()
    commands = [
        MacroCommand("open_standard", {"input_path": "/path/image.tif"}),
        MacroCommand("enhance_contrast", {"saturated": 0.5, "channels": "1, 3"}),
    ]

    macro = builder.build_macro_from_commands(commands)

    assert 'open("/path/image.tif");' in macro
    assert '_channels_1 = newArray(1, 3);' in macro
    assert 'Stack.setChannel(int(_channels_1[_channel_index_1]));' in macro
    assert 'run("Enhance Contrast...", "saturated=0.5 normalize");' in macro


def test_macro_builder_expands_channel_ranges():
    builder = MacroBuilder()
    command = MacroCommand("median_filter", {"radius": 2, "channels": "2-4"})

    macro = builder.build_macro_from_commands([command])

    assert '_channels_1 = newArray(2, 3, 4);' in macro
    assert 'run("Median...", "radius=2");' in macro


def test_duplicate_command_preserves_channel_parameter():
    builder = MacroBuilder()
    command = MacroCommand("duplicate", {"title": "C2", "channels": "2"})

    macro = builder.build_macro_from_commands([command])

    assert 'run("Duplicate...", "title=C2 duplicate channels=2 slices=1-end frames=1-end");' in macro
    assert "newArray" not in macro


def test_target_channels_attribute_is_used():
    builder = MacroBuilder()
    command = MacroCommand(
        "gaussian_blur",
        {"sigma": 1},
        target_channels=[2],
    )

    macro = builder.build_macro_from_commands([command])

    assert '_channels_1 = newArray(2);' in macro
    assert 'run("Gaussian Blur...", "sigma=1");' in macro


def test_apply_channels_alias_is_supported():
    builder = MacroBuilder()
    command = MacroCommand("measure", {"apply_channels": "1 2"})

    macro = builder.build_macro_from_commands([command])

    assert '_channels_1 = newArray(1, 2);' in macro
    assert 'run("Measure");' in macro
