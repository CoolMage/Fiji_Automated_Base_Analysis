"""Build the Fiji macro used for scientifically conservative 3D deconvolution."""

from __future__ import annotations

import json
import math
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional, Sequence


DEFAULT_DECONVOLUTION_ITERATIONS = 10
DEFAULT_DECONVOLUTION_MEMORY_GB = 8
DEFAULT_DECONVOLUTION_TIMEOUT_SECONDS = 1800
DEFAULT_DECONVOLUTION_FOLDER = "Deconvolved"
PSF_MODE_FILES = "files"
PSF_MODE_THEORETICAL = "theoretical"
DEFAULT_THEORETICAL_PSF_WIDTH = 31
DEFAULT_THEORETICAL_PSF_HEIGHT = 31
DEFAULT_THEORETICAL_PSF_SLICES = 15
DEFAULT_THEORETICAL_PSF_INTENSITY = 255.0


@dataclass(frozen=True)
class ImageGeometry:
    """Image dimensions read from the first Bio-Formats series."""

    width: int
    height: int
    channels: int
    slices: int
    frames: int
    pixel_width_um: Optional[float] = None
    pixel_height_um: Optional[float] = None
    voxel_depth_um: Optional[float] = None


@dataclass(frozen=True)
class TheoreticalPSFChannel:
    """Parameters of one DeconvolutionLab2 AxialDiffractionSimulation PSF."""

    pupil_size: float = 10.0
    defocus_factor: float = 10.0
    wave_number_axial: float = 2.0


@dataclass(frozen=True)
class TheoreticalPSFConfig:
    """Shared geometry and per-channel parameters for synthetic DL2 PSFs."""

    width: int = DEFAULT_THEORETICAL_PSF_WIDTH
    height: int = DEFAULT_THEORETICAL_PSF_HEIGHT
    slices: int = DEFAULT_THEORETICAL_PSF_SLICES
    intensity: float = DEFAULT_THEORETICAL_PSF_INTENSITY
    center_x: float = 0.5
    center_y: float = 0.5
    center_z: float = 0.5
    channels: tuple[TheoreticalPSFChannel, ...] = ()
    reference_geometry: Optional[ImageGeometry] = None
    reference_image_path: Optional[str] = None


def default_theoretical_psf_config(channel_count: int = 1) -> TheoreticalPSFConfig:
    """Return the DeconvolutionLab2 defaults for the requested channel count."""

    return TheoreticalPSFConfig(
        channels=tuple(TheoreticalPSFChannel() for _ in range(channel_count))
    )


def theoretical_psf_config_to_dict(config: TheoreticalPSFConfig) -> dict[str, Any]:
    """Return a JSON-ready representation of a theoretical PSF configuration."""

    return {
        "model": "AxialDiffractionSimulation",
        **asdict(config),
    }


def validate_theoretical_psf_config(
    config: Optional[TheoreticalPSFConfig],
) -> TheoreticalPSFConfig:
    """Validate settings accepted by DL2's AxialDiffractionSimulation factory."""

    if config is None:
        raise ValueError("Configure theoretical PSF parameters before processing.")
    if not 1 <= len(config.channels) <= 7:
        raise ValueError("Theoretical PSF settings require 1 to 7 channels.")
    for name, value in (
        ("width", config.width),
        ("height", config.height),
        ("slices", config.slices),
    ):
        if int(value) < 2:
            raise ValueError(f"Theoretical PSF {name} must be at least 2 pixels.")
    if float(config.intensity) <= 0:
        raise ValueError("Theoretical PSF intensity must be positive.")
    for name, value in (
        ("center_x", config.center_x),
        ("center_y", config.center_y),
        ("center_z", config.center_z),
    ):
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"Theoretical PSF {name} must be between 0 and 1.")
    for index, channel in enumerate(config.channels, start=1):
        for name, value in (
            ("pupil size", channel.pupil_size),
            ("defocus factor", channel.defocus_factor),
            ("axial wave number", channel.wave_number_axial),
        ):
            if float(value) <= 0:
                raise ValueError(
                    f"Theoretical PSF C{index} {name} must be positive."
                )
    reference = config.reference_geometry
    if reference is not None:
        if reference.channels != len(config.channels):
            raise ValueError(
                "Theoretical PSF channel count must match the reference image."
            )
        if reference.frames != 1:
            raise ValueError(
                "The reference image must contain exactly one time frame."
            )
        if reference.slices < 2:
            raise ValueError("The reference image must be a 3D Z-stack.")
        if (
            config.width > reference.width
            or config.height > reference.height
            or config.slices > reference.slices
        ):
            raise ValueError(
                "Theoretical PSF dimensions must not exceed the reference "
                "image dimensions."
            )
    return config


def build_theoretical_psf_command(
    config: TheoreticalPSFConfig,
    channel: TheoreticalPSFChannel,
) -> str:
    """Build the command consumed by DL2's synthetic PSF loader."""

    return (
        "AxialDiffractionSimulation "
        f"{channel.pupil_size:g} "
        f"{channel.defocus_factor:g} "
        f"{channel.wave_number_axial:g} "
        f"size {int(config.width)} {int(config.height)} {int(config.slices)} "
        f"intensity {float(config.intensity):g} "
        f"center {float(config.center_x):g} "
        f"{float(config.center_y):g} {float(config.center_z):g}"
    )


def _macro_string(value: str) -> str:
    """Return an ImageJ macro string literal."""

    return json.dumps(str(value).replace("\\", "/"), ensure_ascii=False)


def build_image_geometry_probe_macro(
    *,
    input_path: str,
    result_path: str,
) -> str:
    """Build a metadata-only Bio-Formats macro for the first image series."""

    return f"""\
// Read dimensions without loading the image pixels.
setBatchMode(true);
inputPath = {_macro_string(input_path)};
resultPath = {_macro_string(result_path)};

run("Bio-Formats Macro Extensions");
Ext.setId(inputPath);
Ext.setSeries(0);
Ext.getSizeX(imageWidth);
Ext.getSizeY(imageHeight);
Ext.getSizeC(channelCount);
Ext.getSizeZ(sliceCount);
Ext.getSizeT(frameCount);
Ext.getPixelsPhysicalSizeX(pixelWidthUm);
Ext.getPixelsPhysicalSizeY(pixelHeightUm);
Ext.getPixelsPhysicalSizeZ(voxelDepthUm);
Ext.close();

geometry =
    "width=" + imageWidth + "\\n"
    + "height=" + imageHeight + "\\n"
    + "channels=" + channelCount + "\\n"
    + "slices=" + sliceCount + "\\n"
    + "frames=" + frameCount + "\\n"
    + "pixel_width_um=" + pixelWidthUm + "\\n"
    + "pixel_height_um=" + pixelHeightUm + "\\n"
    + "voxel_depth_um=" + voxelDepthUm + "\\n";
File.saveString(geometry, resultPath);
run("Quit");
"""


def parse_image_geometry(text: str) -> ImageGeometry:
    """Parse dimensions written by the Bio-Formats geometry probe."""

    values: dict[str, int] = {}
    calibration: dict[str, Optional[float]] = {
        "pixel_width_um": None,
        "pixel_height_um": None,
        "voxel_depth_um": None,
    }
    for raw_line in text.splitlines():
        if "=" not in raw_line:
            continue
        key, raw_value = raw_line.split("=", 1)
        key = key.strip()
        if key in {"width", "height", "channels", "slices", "frames"}:
            values[key] = int(float(raw_value.strip()))
        elif key in calibration:
            try:
                parsed = float(raw_value.strip())
            except ValueError:
                parsed = math.nan
            calibration[key] = (
                parsed if math.isfinite(parsed) and parsed > 0 else None
            )

    missing = [
        key
        for key in ("width", "height", "channels", "slices", "frames")
        if key not in values
    ]
    if missing:
        raise ValueError(
            "Fiji did not return complete image geometry: "
            + ", ".join(missing)
        )
    if any(value < 1 for value in values.values()):
        raise ValueError("Fiji returned invalid image dimensions.")

    return ImageGeometry(**values, **calibration)


def read_image_geometry_with_fiji(
    fiji_path: str,
    input_path: str,
    *,
    timeout: int = 300,
) -> ImageGeometry:
    """Read first-series dimensions through installed Fiji/Bio-Formats."""

    from fiji_automated_analysis.utils.general.macros_operation import run_fiji_macro

    input_file = Path(input_path).expanduser().resolve()
    if not input_file.is_file():
        raise ValueError(f"Image file does not exist: {input_file}")

    with tempfile.TemporaryDirectory(prefix="fiji_geometry_") as temp_dir:
        result_path = Path(temp_dir) / "geometry.txt"
        macro = build_image_geometry_probe_macro(
            input_path=str(input_file),
            result_path=str(result_path),
        )
        result = run_fiji_macro(
            fiji_path,
            macro,
            timeout=timeout,
            verbose=False,
        )
        if not result.get("success"):
            details = (
                result.get("stderr")
                or result.get("stdout")
                or result.get("error")
                or "unknown Fiji error"
            )
            raise RuntimeError(f"Could not read image geometry: {details}")
        if not result_path.is_file():
            raise RuntimeError(
                "Fiji completed without writing image geometry metadata."
            )
        return parse_image_geometry(result_path.read_text(encoding="utf-8"))


def build_deconvolution_macro(
    *,
    input_path: str,
    output_path: str,
    working_directory: str,
    iterations: int,
    psf_paths: Sequence[str] = (),
    theoretical_psf: Optional[TheoreticalPSFConfig] = None,
) -> str:
    """Create a headless Fiji macro for channel-wise 3D Richardson-Lucy.

    The macro deliberately refuses data that would make the result ambiguous:
    2D images, time series, RGB pixels, missing spatial calibration, mismatched
    channel/PSF counts, and PSFs sampled on a different voxel grid.
    """

    psf_literals = ", ".join(_macro_string(path) for path in psf_paths)
    psf_mode = PSF_MODE_THEORETICAL if theoretical_psf is not None else PSF_MODE_FILES
    theoretical_commands: Sequence[str] = ()
    theoretical_width = 0
    theoretical_height = 0
    theoretical_slices = 0
    theoretical_pixel_width_um = 0.0
    theoretical_pixel_height_um = 0.0
    theoretical_voxel_depth_um = 0.0
    if theoretical_psf is not None:
        theoretical_psf = validate_theoretical_psf_config(theoretical_psf)
        theoretical_commands = [
            build_theoretical_psf_command(theoretical_psf, channel)
            for channel in theoretical_psf.channels
        ]
        theoretical_width = theoretical_psf.width
        theoretical_height = theoretical_psf.height
        theoretical_slices = theoretical_psf.slices
        reference = theoretical_psf.reference_geometry
        if reference is not None and all(
            value is not None
            for value in (
                reference.pixel_width_um,
                reference.pixel_height_um,
                reference.voxel_depth_um,
            )
        ):
            theoretical_pixel_width_um = float(reference.pixel_width_um)
            theoretical_pixel_height_um = float(reference.pixel_height_um)
            theoretical_voxel_depth_um = float(reference.voxel_depth_um)
    theoretical_literals = ", ".join(
        _macro_string(command) for command in theoretical_commands
    )
    psf_array = f"newArray({psf_literals})" if psf_literals else "newArray(0)"
    theoretical_array = (
        f"newArray({theoretical_literals})"
        if theoretical_literals
        else "newArray(0)"
    )
    return f"""\
// Internal preprocessing macro: channel-wise 3D Richardson-Lucy deconvolution.
setBatchMode(true);

inputPath = {_macro_string(input_path)};
outputPath = {_macro_string(output_path)};
workDir = {_macro_string(working_directory)};
psfMode = {_macro_string(psf_mode)};
psfPaths = {psf_array};
theoreticalPSFCommands = {theoretical_array};
theoreticalPSFWidth = {int(theoretical_width)};
theoreticalPSFHeight = {int(theoretical_height)};
theoreticalPSFSlices = {int(theoretical_slices)};
theoreticalPixelWidthUm = {float(theoretical_pixel_width_um):g};
theoreticalPixelHeightUm = {float(theoretical_pixel_height_um):g};
theoreticalVoxelDepthUm = {float(theoretical_voxel_depth_um):g};
iterations = {int(iterations)};
calibrationTolerance = 0.02;

if (!File.exists(workDir)) File.makeDirectory(workDir);
run("Bio-Formats Macro Extensions");
Ext.openImagePlus(inputPath);
sourceTitle = getTitle();
getDimensions(imageWidth, imageHeight, channelCount, sliceCount, frameCount);
getVoxelSize(pixelWidth, pixelHeight, voxelDepth, spatialUnit);

if (bitDepth() == 24)
    exit("DECONVOLUTION ERROR: RGB images are not quantitative channel stacks.");
if (sliceCount < 2)
    exit("DECONVOLUTION ERROR: a 3D Z-stack with at least two slices is required.");
if (frameCount != 1)
    exit("DECONVOLUTION ERROR: time series must be exported as one Z-stack per time point.");
if (channelCount < 1 || channelCount > 7)
    exit("DECONVOLUTION ERROR: supported channel count is 1 to 7.");
if (psfMode == "files" && psfPaths.length != channelCount)
    exit("DECONVOLUTION ERROR: provide exactly one PSF Z-stack per image channel.");
if (psfMode == "theoretical" && theoreticalPSFCommands.length != channelCount)
    exit("DECONVOLUTION ERROR: provide theoretical PSF settings for every image channel.");
if (
    psfMode == "theoretical"
    && (
        theoreticalPSFWidth > imageWidth
        || theoreticalPSFHeight > imageHeight
        || theoreticalPSFSlices > sliceCount
    )
)
    exit("DECONVOLUTION ERROR: theoretical PSF dimensions must not exceed image dimensions.");

imageUnitScale = unitToMicrons(spatialUnit);
if (imageUnitScale <= 0 || pixelWidth <= 0 || pixelHeight <= 0 || voxelDepth <= 0)
    exit("DECONVOLUTION ERROR: valid physical XYZ voxel calibration is required.");

imagePixelWidthUm = pixelWidth * imageUnitScale;
imagePixelHeightUm = pixelHeight * imageUnitScale;
imageVoxelDepthUm = voxelDepth * imageUnitScale;
if (
    psfMode == "theoretical"
    && theoreticalPixelWidthUm > 0
    && (
        relativeDifference(imagePixelWidthUm, theoreticalPixelWidthUm) > calibrationTolerance
        || relativeDifference(imagePixelHeightUm, theoreticalPixelHeightUm) > calibrationTolerance
        || relativeDifference(imageVoxelDepthUm, theoreticalVoxelDepthUm) > calibrationTolerance
    )
)
    exit(
        "DECONVOLUTION ERROR: input voxel sampling differs by more than 2% "
        + "from the theoretical PSF reference image."
    );
deconvolvedTitles = newArray(channelCount);

for (channelIndex = 0; channelIndex < channelCount; channelIndex++) {{
    psfArgument = "";
    if (psfMode == "files") {{
        psfPath = psfPaths[channelIndex];
        if (!File.exists(psfPath))
            exit("DECONVOLUTION ERROR: PSF file not found: " + psfPath);

        open(psfPath);
        psfTitle = getTitle();
        getDimensions(psfWidth, psfHeight, psfChannels, psfSlices, psfFrames);
        getVoxelSize(psfPixelWidth, psfPixelHeight, psfVoxelDepth, psfUnit);
        Stack.getStatistics(psfCount, psfMean, psfMin, psfMax, psfStdDev);

        if (bitDepth() == 24)
            exit("DECONVOLUTION ERROR: PSF must be a grayscale Z-stack: " + psfPath);
        if (psfChannels != 1 || psfFrames != 1 || psfSlices < 2)
            exit("DECONVOLUTION ERROR: each PSF must be a single-channel 3D Z-stack: " + psfPath);
        if (psfWidth > imageWidth || psfHeight > imageHeight || psfSlices > sliceCount)
            exit("DECONVOLUTION ERROR: PSF dimensions must not exceed image dimensions: " + psfPath);
        if (psfMax <= 0)
            exit("DECONVOLUTION ERROR: PSF contains no positive signal: " + psfPath);
        if (psfMin < 0)
            exit("DECONVOLUTION ERROR: PSF contains negative values: " + psfPath);

        psfUnitScale = unitToMicrons(psfUnit);
        if (psfUnitScale <= 0)
            exit("DECONVOLUTION ERROR: PSF physical voxel calibration is missing: " + psfPath);

        psfPixelWidthUm = psfPixelWidth * psfUnitScale;
        psfPixelHeightUm = psfPixelHeight * psfUnitScale;
        psfVoxelDepthUm = psfVoxelDepth * psfUnitScale;
        if (
            relativeDifference(imagePixelWidthUm, psfPixelWidthUm) > calibrationTolerance
            || relativeDifference(imagePixelHeightUm, psfPixelHeightUm) > calibrationTolerance
            || relativeDifference(imageVoxelDepthUm, psfVoxelDepthUm) > calibrationTolerance
        )
            exit(
                "DECONVOLUTION ERROR: image and PSF voxel sizes differ by more than 2%. "
                + "Resample the PSF to the image XYZ grid."
            );
        close();
        psfArgument = " -psf file " + psfPath;
    }} else {{
        psfArgument = " -psf synthetic " + theoreticalPSFCommands[channelIndex];
    }}

    selectWindow(sourceTitle);
    inputName = "_dl2_input_c" + (channelIndex + 1);
    run(
        "Duplicate...",
        "title=" + inputName
        + " duplicate channels=" + (channelIndex + 1)
        + " slices=1-" + sliceCount
        + " frames=1"
    );
    run("32-bit");
    inputChannelPath = workDir + "/" + inputName + ".tif";
    saveAs("Tiff", inputChannelPath);
    close();

    outputName = "_dl2_output_c" + (channelIndex + 1);
    command =
        " -image file " + inputChannelPath
        + psfArgument
        + " -algorithm RL " + iterations
        + " -path " + workDir
        + " -out stack intact float noshow " + outputName
        + " -constraint nonnegativity"
        + " -pad X23 X23"
        + " -apo NO NO"
        + " -norm 1"
        + " -multithreading no"
        + " -monitor console"
        + " -verbose log"
        + " -stats false"
        + " -system no";
    run("DeconvolutionLab2 Run", command);

    outputChannelPath = workDir + "/" + outputName + ".tif";
    if (!File.exists(outputChannelPath))
        exit("DECONVOLUTION ERROR: DeconvolutionLab2 did not create " + outputChannelPath);

    open(outputChannelPath);
    setVoxelSize(pixelWidth, pixelHeight, voxelDepth, spatialUnit);
    channelTitle = "Deconvolved_C" + (channelIndex + 1);
    rename(channelTitle);
    deconvolvedTitles[channelIndex] = channelTitle;
}}

selectWindow(sourceTitle);
close();

if (channelCount == 1) {{
    selectWindow(deconvolvedTitles[0]);
}} else {{
    mergeOptions = "";
    for (channelIndex = 0; channelIndex < channelCount; channelIndex++)
        mergeOptions += "c" + (channelIndex + 1) + "=[" + deconvolvedTitles[channelIndex] + "] ";
    run("Merge Channels...", mergeOptions + "create");
    Stack.setDisplayMode("composite");
}}

setVoxelSize(pixelWidth, pixelHeight, voxelDepth, spatialUnit);
rename(File.getNameWithoutExtension(outputPath));
saveAs("Tiff", outputPath);
run("Close All");
run("Quit");

function relativeDifference(a, b) {{
    denominator = maxOf(abs(a), abs(b));
    if (denominator == 0) return 0;
    return abs(a - b) / denominator;
}}

function unitToMicrons(unit) {{
    normalized = toLowerCase(unit);
    if (
        normalized == "µm"
        || normalized == "μm"
        || (lengthOf(normalized) == 2 && endsWith(normalized, "m")
            && normalized != "nm" && normalized != "mm")
    ) return 1;
    normalized = replace(normalized, "µ", "u");
    if (
        normalized == "um"
        || normalized == "micron"
        || normalized == "microns"
        || normalized == "micrometer"
        || normalized == "micrometers"
    ) return 1;
    if (
        normalized == "nm"
        || normalized == "nanometer"
        || normalized == "nanometers"
    ) return 0.001;
    if (
        normalized == "mm"
        || normalized == "millimeter"
        || normalized == "millimeters"
    ) return 1000;
    return -1;
}}
"""


def validate_psf_paths(psf_paths: Sequence[str]) -> list[str]:
    """Normalize and validate user-selected PSF stacks."""

    normalized: list[str] = []
    for raw_path in psf_paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"PSF file does not exist: {path}")
        if path.suffix.lower() not in {".tif", ".tiff"}:
            raise ValueError(f"PSF must be a TIFF Z-stack: {path}")
        normalized.append(str(path))
    if not normalized:
        raise ValueError("Select at least one PSF Z-stack for deconvolution.")
    return normalized
