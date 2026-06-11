from __future__ import annotations

from collections.abc import Iterable, Iterator, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent


@dataclass(frozen=True)
class MacroGuiProfile:
    """Recommended GUI settings for a bundled macro template."""

    apply_roi_templates: bool | None = None
    save_processed_images: bool | None = None
    save_measurement_csv: bool | None = None
    generate_measurement_summary: bool | None = None
    secondary_filter: str | None = None
    processed_suffix: str | None = None
    measurements_folder: str | None = None
    processed_folder: str | None = None
    measurement_prefix: str | None = None
    note: str = ""


class MacroLibrary(MutableMapping[str, str]):
    """Alias-aware registry for bundled Fiji macro templates.

    Only canonical macro names are exposed through iteration and ``keys()`` so
    the GUI and other selectors stay clean. Legacy names remain available as
    aliases for backward compatibility.
    """

    def __init__(self) -> None:
        self._macros: dict[str, str] = {}
        self._aliases: dict[str, str] = {}
        self._profiles: dict[str, MacroGuiProfile] = {}

    def add(
        self,
        name: str,
        code: str,
        aliases: Iterable[str] = (),
        profile: MacroGuiProfile | None = None,
    ) -> None:
        self._macros[name] = dedent(code).strip() + "\n"
        for alias in aliases:
            if alias != name:
                self._aliases[alias] = name
        if profile is not None:
            self._profiles[name] = profile

    def add_from_file(
        self,
        name: str,
        filename: str,
        aliases: Iterable[str] = (),
        profile: MacroGuiProfile | None = None,
    ) -> None:
        self.add(name, _load_macro_file(filename), aliases=aliases, profile=profile)

    def resolve_name(self, name: str) -> str:
        return self._aliases.get(name, name)

    @property
    def aliases(self) -> dict[str, str]:
        return dict(self._aliases)

    def get_profile(self, key: str) -> MacroGuiProfile | None:
        return self._profiles.get(self.resolve_name(key))

    def __getitem__(self, key: str) -> str:
        return self._macros[self.resolve_name(key)]

    def __setitem__(self, key: str, value: str) -> None:
        self.add(key, value)

    def __delitem__(self, key: str) -> None:
        resolved = self.resolve_name(key)
        if key in self._aliases:
            del self._aliases[key]
            return

        del self._macros[resolved]
        self._aliases = {
            alias: target for alias, target in self._aliases.items() if target != resolved
        }

    def __iter__(self) -> Iterator[str]:
        return iter(self._macros)

    def __len__(self) -> int:
        return len(self._macros)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return self.resolve_name(key) in self._macros

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._macros.get(self.resolve_name(key), default)


def _load_macro_file(name: str) -> str:
    path = Path(__file__).with_name(name)
    return path.read_text(encoding="utf-8")


MACROS_LIB = MacroLibrary()

MACROS_LIB.add(
    "split_channels_to_subfolder",
    '''
    // Split a multichannel image and save each channel as a TIFF inside a dedicated output folder.
    //
    // --- Editable parameters ---
    inputPath = "{img_path_fiji}";
    outputDir = "{output_dir_fiji_slash}{file_stem}";
    outputStem = "{file_stem}";
    batchModeEnabled = true;
    closeAllWhenDone = true;
    quitWhenDone = true;

    // --- Open image ---
    if (batchModeEnabled) setBatchMode(true);
    run("Bio-Formats Macro Extensions");
    Ext.openImagePlus(inputPath);

    // --- Split and save channels ---
    run("Split Channels");
    imgList = getList("image.titles");

    if (!File.exists(outputDir)) File.makeDirectory(outputDir);

    for (i = 0; i < imgList.length; i++) {{
        selectWindow(imgList[i]);
        saveAs("Tiff", outputDir + "/" + outputStem + "_ch" + (i + 1) + ".tif");
    }}

    if (closeAllWhenDone) run("Close All");
    if (quitWhenDone) run("Quit");
    ''',
    aliases=("Split_Channels_in_dif_dir",),
    profile=MacroGuiProfile(
        apply_roi_templates=False,
        save_processed_images=True,
        save_measurement_csv=False,
        generate_measurement_summary=False,
        processed_suffix="processed",
        measurements_folder="Measurements",
        processed_folder="Split_Channels",
        measurement_prefix="measurements_summary",
        note="Splits channels into saved TIFF files and does not export measurements.",
    ),
)

MACROS_LIB.add(
    "create_rgb_mip_blue_green_red",
    '''
    // Create a three-channel composite max-intensity projection and save its channels separately.
    //
    // Channel mapping:
    // - 3-channel input: source C1 -> blue, C2 -> green, C3 -> red
    // - 4-channel input: source C2 is removed, then C1 -> blue, C3 -> green, C4 -> red
    //
    // --- Editable parameters ---
    inputPath = "{img_path_fiji}";
    outputDir = "{output_dir_fiji_slash}";
    fallbackOutputDir = "{img_dir_fiji_slash}";
    outputStem = "{file_stem}";
    outputSuffix = "_MIP_RGB";
    blueSuffix = "_MIP_Blue";
    greenSuffix = "_MIP_Green";
    redSuffix = "_MIP_Red";
    projectionMethod = "Max Intensity";
    batchModeEnabled = true;
    closeAllWhenDone = true;
    quitWhenDone = true;

    continueProcessing = true;

    // --- Create a dedicated output folder for this input file ---
    if (outputDir == "" || outputDir == "null" || outputDir == "/") {{
        outputDir = fallbackOutputDir;
    }}
    fileOutputDir = outputDir + outputStem + outputSuffix;
    if (!File.exists(fileOutputDir)) File.makeDirectory(fileOutputDir);

    // --- Open image and validate channel count ---
    if (batchModeEnabled) setBatchMode(true);
    run("Bio-Formats Macro Extensions");
    Ext.openImagePlus(inputPath);
    originalTitle = getTitle();
    getDimensions(imageWidth, imageHeight, channelCount, sliceCount, frameCount);

    if (channelCount != 3 && channelCount != 4) {{
        print(
            "WARN: Expected a 3- or 4-channel image, but found "
            + channelCount + " channel(s): " + inputPath
        );
        continueProcessing = false;
    }}

    // For four-channel images, retain source channels C1, C3, and C4.
    if (continueProcessing && channelCount == 4) {{
        run("Arrange Channels...", "new=134");
    }}

    if (continueProcessing) {{
        // Project along Z while preserving the three selected channels.
        run("Z Project...", "projection=[" + projectionMethod + "]");
        projectionTitle = getTitle();

        selectWindow(originalTitle);
        run("Close");
        selectWindow(projectionTitle);

        // Split projected channels, then map source order to B, G, R.
        run("Split Channels");
        projectedChannels = getList("image.titles");

        if (projectedChannels.length != 3) {{
            print(
                "WARN: Expected three projected channel images, but found "
                + projectedChannels.length + "."
            );
            continueProcessing = false;
        }}
    }}

    if (continueProcessing) {{
        blueSource = projectedChannels[0];
        greenSource = projectedChannels[1];
        redSource = projectedChannels[2];

        // Save each projected source channel as its own TIFF with the assigned LUT.
        selectWindow(blueSource);
        run("Blue");
        saveAs("Tiff", fileOutputDir + "/" + outputStem + blueSuffix + ".tif");
        blueSource = getTitle();

        selectWindow(greenSource);
        run("Green");
        saveAs("Tiff", fileOutputDir + "/" + outputStem + greenSuffix + ".tif");
        greenSource = getTitle();

        selectWindow(redSource);
        run("Red");
        saveAs("Tiff", fileOutputDir + "/" + outputStem + redSuffix + ".tif");
        redSource = getTitle();

        // "create" keeps the result as a three-channel composite instead of flattening it to RGB.
        run(
            "Merge Channels...",
            "c1=[" + blueSource + "] "
            + "c2=[" + greenSource + "] "
            + "c3=[" + redSource + "] create"
        );

        // Preserve source order C1=blue, C2=green, C3=red and display all channels together.
        Stack.setChannel(1);
        run("Blue");
        Stack.setChannel(2);
        run("Green");
        Stack.setChannel(3);
        run("Red");
        Stack.setDisplayMode("composite");
        rename(outputStem + outputSuffix);

        saveAs("Tiff", fileOutputDir + "/" + outputStem + outputSuffix + ".tif");
    }}

    if (closeAllWhenDone) run("Close All");
    if (quitWhenDone) run("Quit");
    ''',
    aliases=("rgb_mip_blue_green_red",),
    profile=MacroGuiProfile(
        apply_roi_templates=False,
        save_processed_images=True,
        save_measurement_csv=False,
        generate_measurement_summary=False,
        processed_suffix="processed",
        measurements_folder="Measurements",
        processed_folder="Processed_Files",
        measurement_prefix="measurements_summary",
        note=(
            "Creates a per-file folder containing a three-channel composite "
            "max-intensity projection and separate blue, green, and red TIFFs. "
            "Source C2 is removed from four-channel inputs."
        ),
    ),
)

MACROS_LIB.add(
    "adjust_channel_2_and_save_as_tiff",
    '''
    // Extract channel 2, create a MIP, apply brightness/contrast settings, and save the adjusted result as a TIFF file.
    //
    // --- Editable parameters ---
    inputPath = "{img_path_fiji}";
    outputDir = "{output_dir_fiji_slash}";
    fallbackOutputDir = "{img_dir_fiji_slash}";
    outputStem = "{file_stem}";
    targetChannelPosition = 2;
    projectionMethod = "Max Intensity";
    displayMin = 0;
    displayMax = 5000;
    resetDisplayRangeFirst = true;
    applyBrightnessContrastToPixels = true;
    convertTo8Bit = false;
    outputSuffix = "_C2_MIP_adjusted";
    batchModeEnabled = true;
    closeAllWhenDone = true;
    quitWhenDone = true;

    continueProcessing = true;

    // --- Open image ---
    if (batchModeEnabled) setBatchMode(true);
    run("Bio-Formats Macro Extensions");
    Ext.openImagePlus(inputPath);

    if (outputDir == "" || outputDir == "null" || outputDir == "/") {{
        outputDir = fallbackOutputDir;
    }}
    if (!File.exists(outputDir)) File.makeDirectory(outputDir);

    // --- Select the requested channel ---
    run("Split Channels");
    imgList = getList("image.titles");
    if (imgList.length < targetChannelPosition) {{
        print("WARN: Requested channel index is out of range.");
        continueProcessing = false;
    }}

    if (continueProcessing) {{
        selectWindow(imgList[targetChannelPosition - 1]);
        run("Z Project...", "projection=[" + projectionMethod + "]");
        rename(outputStem + outputSuffix);

        // --- Apply brightness/contrast to the channel-2 projection ---
        if (resetDisplayRangeFirst) {{
            resetMinAndMax();
        }}
        setMinAndMax(displayMin, displayMax);
        if (applyBrightnessContrastToPixels) {{
            run("Apply LUT");
        }}

        if (convertTo8Bit) {{
            run("8-bit");
        }}

        saveAs("Tiff", outputDir + outputStem + outputSuffix + ".tif");
    }}

    if (closeAllWhenDone) run("Close All");
    if (quitWhenDone) run("Quit");
    ''',
    profile=MacroGuiProfile(
        apply_roi_templates=False,
        save_processed_images=True,
        save_measurement_csv=False,
        generate_measurement_summary=False,
        processed_suffix="processed",
        measurements_folder="Measurements",
        processed_folder="Processed_Files",
        measurement_prefix="measurements_summary",
        note="Extracts channel 2, builds a MIP, applies brightness/contrast settings, and saves a TIFF without measurement output.",
    ),
)

MACROS_LIB.add(
    "measure_full_image_per_channel_after_mip",
    '''
    // Create a max-intensity projection, then measure the full image area in every channel.
    //
    // --- Editable parameters ---
    inputPath = "{img_path_fiji}";
    mipPath = "{output_dir_fiji_slash}{file_stem}_MIP";
    resultsPath = "{out_csv}";
    documentLabel = "{document_name_raw}";
    outputStem = "{file_stem}";
    projectionMethod = "Max Intensity";
    measurementsOptions = "area mean min max std integrated redirect=None decimal=3";
    saveMipImage = true;
    batchModeEnabled = true;
    closeAllWhenDone = true;
    quitWhenDone = true;

    // --- Open image and build MIP ---
    if (batchModeEnabled) setBatchMode(true);
    run("Bio-Formats Macro Extensions");
    Ext.openImagePlus(inputPath);
    originalTitle = getTitle();
    run("Z Project...", "projection=[" + projectionMethod + "]");
    selectWindow(originalTitle);
    run("Close");
    rename(outputStem + "_MIP");

    if (saveMipImage) saveAs("Tiff", mipPath);

    // --- Split and measure each channel ---
    run("Split Channels");
    imgList = getList("image.titles");
    run("Set Measurements...", measurementsOptions);
    run("Select None");

    for (i = 0; i < imgList.length; i++) {{
        selectWindow(imgList[i]);
        channelTitle = getTitle();
        before = nResults;
        run("Measure");
        after = nResults;
        for (r = before; r < after; r++) {{
            setResult("Channel", r, channelTitle);
            setResult("Document", r, documentLabel);
            setResult("Scope", r, "FullImageAfterMIP");
        }}
        updateResults();
    }}

    if (resultsPath == "" || resultsPath == "null") {{
        print("WARN: resultsPath is empty; measurements were not written to disk.");
    }} else {{
        saveAs("Results", resultsPath);
    }}

    if (closeAllWhenDone) run("Close All");
    if (quitWhenDone) run("Quit");
    ''',
    aliases=("mip_all_image_measure_for_channel",),
    profile=MacroGuiProfile(
        apply_roi_templates=False,
        save_processed_images=True,
        save_measurement_csv=True,
        generate_measurement_summary=True,
        processed_suffix="processed",
        measurements_folder="Measurements",
        processed_folder="Processed_Files",
        measurement_prefix="measurements_summary",
        note="Builds and saves a MIP, then exports channel-wise measurements for the full image.",
    ),
)

MACROS_LIB.add(
    "measure_matching_roi_per_channel",
    '''
    // Measure every channel inside ROI files that match the current image name.
    //
    // --- Editable parameters ---
    inputPath = "{img_path_fiji}";
    imageDir = "{img_dir_fiji_slash}";
    resultsPath = "{out_csv}";
    documentLabel = "{document_name_raw}";
    normalizedDocumentLabel = "{document_name}";
    documentFilename = "{document_filename_raw}";
    explicitRoiList = "{roi_paths_joined}";
    measurementsOptions = "area mean standard min integrated median area_fraction redirect=None decimal=3";
    batchModeEnabled = true;
    closeAllWhenDone = true;
    quitWhenDone = true;

    continueProcessing = true;

    // --- Open image ---
    if (batchModeEnabled) setBatchMode(true);
    run("Bio-Formats Macro Extensions");
    Ext.openImagePlus(inputPath);

    // --- Load matching ROI(s) ---
    roiManager("Reset");
    if (explicitRoiList != "") {{
    {roi_manager_open_block}
    }} else {{
        roiZipRaw = imageDir + documentLabel + ".zip";
        roiRoiRaw = imageDir + documentLabel + ".roi";
        roiZipRoiSetRaw = imageDir + "RoiSet_" + documentLabel + ".zip";
        roiZipNormalized = imageDir + normalizedDocumentLabel + ".zip";
        roiRoiNormalized = imageDir + normalizedDocumentLabel + ".roi";
        roiZipRoiSetNormalized = imageDir + "RoiSet_" + normalizedDocumentLabel + ".zip";
        roiRoiWithExtension = imageDir + documentFilename + ".roi";

        if (File.exists(roiZipRaw)) {{
            roiManager("Open", roiZipRaw);
        }} else if (File.exists(roiRoiRaw)) {{
            roiManager("Open", roiRoiRaw);
        }} else if (File.exists(roiZipRoiSetRaw)) {{
            roiManager("Open", roiZipRoiSetRaw);
        }} else if (File.exists(roiZipNormalized)) {{
            roiManager("Open", roiZipNormalized);
        }} else if (File.exists(roiRoiNormalized)) {{
            roiManager("Open", roiRoiNormalized);
        }} else if (File.exists(roiZipRoiSetNormalized)) {{
            roiManager("Open", roiZipRoiSetNormalized);
        }} else if (File.exists(roiRoiWithExtension)) {{
            roiManager("Open", roiRoiWithExtension);
        }} else {{
            print("WARN: ROI file not found for image: " + documentLabel);
            continueProcessing = false;
        }}
    }}

    if (continueProcessing && roiManager("count") == 0) {{
        print("WARN: No ROIs loaded; measurements were not written.");
        continueProcessing = false;
    }}

    if (continueProcessing) {{
        run("Select None");

        // --- Split and measure each ROI in every channel ---
        run("Split Channels");
        imgList = getList("image.titles");
        run("Set Measurements...", measurementsOptions);

        for (i = 0; i < imgList.length; i++) {{
            selectWindow(imgList[i]);
            channelTitle = getTitle();

            roiCount = roiManager("count");
            for (j = 0; j < roiCount; j++) {{
                roiManager("Select", j);
                roiName = call("ij.plugin.frame.RoiManager.getName", j);
                if (roiName == "" || roiName == "null") roiName = "ROI_" + (j + 1);

                before = nResults;
                run("Measure");
                after = nResults;

                for (r = before; r < after; r++) {{
                    setResult("Channel", r, channelTitle);
                    setResult("Document", r, documentLabel);
                    setResult("ROI", r, roiName);
                    setResult("Scope", r, "MatchingROI");
                }}
            }}

            updateResults();
        }}

        if (resultsPath == "" || resultsPath == "null") {{
            print("WARN: resultsPath is empty; measurements were not written to disk.");
        }} else {{
            saveAs("Results", resultsPath);
        }}
    }}

    if (closeAllWhenDone) run("Close All");
    if (quitWhenDone) run("Quit");
    ''',
    aliases=(
        "all_image_measure_for_channel",
        "all_image_and_rois_measure_for_channel",
    ),
    profile=MacroGuiProfile(
        apply_roi_templates=True,
        save_processed_images=False,
        save_measurement_csv=True,
        generate_measurement_summary=True,
        processed_suffix="processed",
        measurements_folder="Measurements",
        processed_folder="Processed_Files",
        measurement_prefix="measurements_summary",
        note="Loads ROI files matched by image name and exports measurements for every channel.",
    ),
)

MACROS_LIB.add(
    "measure_matching_roi_per_channel_after_mip",
    '''
    // Create a max-intensity projection, load matching ROI files, and measure each ROI in every channel.
    //
    // --- Editable parameters ---
    inputPath = "{img_path_fiji}";
    imageDir = "{img_dir_fiji_slash}";
    resultsPath = "{out_csv}";
    documentLabel = "{document_name_raw}";
    normalizedDocumentLabel = "{document_name}";
    documentFilename = "{document_filename_raw}";
    explicitRoiList = "{roi_paths_joined}";
    projectionMethod = "Max Intensity";
    measurementsOptions = "area mean standard min integrated median area_fraction redirect=None decimal=3";
    saveMipImage = false;
    mipPath = "{output_dir_fiji_slash}{file_stem}_MIP";
    batchModeEnabled = true;
    closeAllWhenDone = true;
    quitWhenDone = true;

    continueProcessing = true;

    // --- Open image and build MIP ---
    if (batchModeEnabled) setBatchMode(true);
    run("Bio-Formats Macro Extensions");
    Ext.openImagePlus(inputPath);
    originalTitle = getTitle();
    run("Z Project...", "projection=[" + projectionMethod + "]");
    selectWindow(originalTitle);
    run("Close");
    rename("{file_stem}_MIP");

    if (saveMipImage) saveAs("Tiff", mipPath);

    // --- Load matching ROI(s) ---
    roiManager("Reset");
    if (explicitRoiList != "") {{
    {roi_manager_open_block}
    }} else {{
        roiZipRaw = imageDir + documentLabel + ".zip";
        roiRoiRaw = imageDir + documentLabel + ".roi";
        roiZipRoiSetRaw = imageDir + "RoiSet_" + documentLabel + ".zip";
        roiZipNormalized = imageDir + normalizedDocumentLabel + ".zip";
        roiRoiNormalized = imageDir + normalizedDocumentLabel + ".roi";
        roiZipRoiSetNormalized = imageDir + "RoiSet_" + normalizedDocumentLabel + ".zip";
        roiRoiWithExtension = imageDir + documentFilename + ".roi";

        if (File.exists(roiZipRaw)) {{
            roiManager("Open", roiZipRaw);
        }} else if (File.exists(roiRoiRaw)) {{
            roiManager("Open", roiRoiRaw);
        }} else if (File.exists(roiZipRoiSetRaw)) {{
            roiManager("Open", roiZipRoiSetRaw);
        }} else if (File.exists(roiZipNormalized)) {{
            roiManager("Open", roiZipNormalized);
        }} else if (File.exists(roiRoiNormalized)) {{
            roiManager("Open", roiRoiNormalized);
        }} else if (File.exists(roiZipRoiSetNormalized)) {{
            roiManager("Open", roiZipRoiSetNormalized);
        }} else if (File.exists(roiRoiWithExtension)) {{
            roiManager("Open", roiRoiWithExtension);
        }} else {{
            print("WARN: ROI file not found for image: " + documentLabel);
            continueProcessing = false;
        }}
    }}

    if (continueProcessing && roiManager("count") == 0) {{
        print("WARN: No ROIs loaded; measurements were not written.");
        continueProcessing = false;
    }}

    if (continueProcessing) {{
        run("Select None");

        // --- Split and measure each ROI in every channel ---
        run("Split Channels");
        imgList = getList("image.titles");
        run("Set Measurements...", measurementsOptions);

        for (i = 0; i < imgList.length; i++) {{
            selectWindow(imgList[i]);
            channelTitle = getTitle();

            roiCount = roiManager("count");
            for (j = 0; j < roiCount; j++) {{
                roiManager("Select", j);
                roiName = call("ij.plugin.frame.RoiManager.getName", j);
                if (roiName == "" || roiName == "null") roiName = "ROI_" + (j + 1);

                before = nResults;
                run("Measure");
                after = nResults;

                for (r = before; r < after; r++) {{
                    setResult("Channel", r, channelTitle);
                    setResult("Document", r, documentLabel);
                    setResult("ROI", r, roiName);
                    setResult("Scope", r, "MatchingROIAfterMIP");
                }}
            }}

            updateResults();
        }}

        if (resultsPath == "" || resultsPath == "null") {{
            print("WARN: resultsPath is empty; measurements were not written to disk.");
        }} else {{
            saveAs("Results", resultsPath);
        }}
    }}

    if (closeAllWhenDone) run("Close All");
    if (quitWhenDone) run("Quit");
    ''',
    aliases=("mip_roi_measure_AllChannels",),
    profile=MacroGuiProfile(
        apply_roi_templates=True,
        save_processed_images=False,
        save_measurement_csv=True,
        generate_measurement_summary=True,
        processed_suffix="processed",
        measurements_folder="Measurements",
        processed_folder="Processed_Files",
        measurement_prefix="measurements_summary",
        note="Builds a MIP, applies same-name ROI files, and exports per-channel ROI measurements.",
    ),
)

MACROS_LIB.add(
    "measure_channel_2_area_fraction_full_image",
    '''
    // Measure the second channel over the full image and record area-fraction metrics.
    //
    // --- Editable parameters ---
    inputPath = "{img_path_fiji}";
    resultsPath = "{out_csv}";
    documentLabel = "{document_name_raw}";
    targetChannelPosition = 2;
    measurementsOptions = "area mean standard min integrated median area_fraction redirect=None decimal=3";
    batchModeEnabled = true;
    closeAllWhenDone = true;
    quitWhenDone = true;

    continueProcessing = true;

    // --- Open image ---
    if (batchModeEnabled) setBatchMode(true);
    run("Bio-Formats Macro Extensions");
    Ext.openImagePlus(inputPath);

    // --- Select the requested channel ---
    run("Split Channels");
    imgList = getList("image.titles");
    if (imgList.length < targetChannelPosition) {{
        print("WARN: Requested channel index is out of range.");
        continueProcessing = false;
    }}

    if (continueProcessing) {{
        selectWindow(imgList[targetChannelPosition - 1]);
        channelTitle = getTitle();

        run("Set Measurements...", measurementsOptions);
        before = nResults;
        run("Measure");
        after = nResults;

        for (r = before; r < after; r++) {{
            setResult("Channel", r, channelTitle);
            setResult("Document", r, documentLabel);
            setResult("Scope", r, "FullImageChannel" + targetChannelPosition);
        }}
        updateResults();

        if (resultsPath == "" || resultsPath == "null") {{
            print("WARN: resultsPath is empty; measurements were not written to disk.");
        }} else {{
            saveAs("Results", resultsPath);
        }}
    }}

    if (closeAllWhenDone) run("Close All");
    if (quitWhenDone) run("Quit");
    ''',
    aliases=("measure_area_fraction_channel2",),
    profile=MacroGuiProfile(
        apply_roi_templates=False,
        save_processed_images=False,
        save_measurement_csv=True,
        generate_measurement_summary=True,
        processed_suffix="processed",
        measurements_folder="Measurements",
        processed_folder="Processed_Files",
        measurement_prefix="measurements_summary",
        note="Measures channel 2 over the full image and exports the result table only.",
    ),
)

MACROS_LIB.add(
    "measure_channel_2_thresholded_area_in_matching_roi_after_mip",
    '''
    // Create a projection of channel 2, apply a threshold, and measure the thresholded area inside matching ROI files.
    //
    // --- Editable parameters ---
    inputPath = "{img_path_fiji}";
    imageDir = "{img_dir_fiji_slash}";
    resultsPath = "{out_csv}";
    documentLabel = "{document_name_raw}";
    normalizedDocumentLabel = "{document_name}";
    documentFilename = "{document_filename_raw}";
    explicitRoiList = "{roi_paths_joined}";
    targetChannelPosition = 2;
    projectionMethod = "Max Intensity";
    thresholdLow = 500;
    thresholdHigh = 65535;
    measurementsOptions = "area mean standard min integrated median area_fraction redirect=None decimal=3";
    batchModeEnabled = true;
    closeAllWhenDone = true;
    quitWhenDone = true;

    continueProcessing = true;

    // --- Open image ---
    if (batchModeEnabled) setBatchMode(true);
    run("Bio-Formats Macro Extensions");
    Ext.openImagePlus(inputPath);

    // --- Load matching ROI(s) ---
    roiManager("Reset");
    if (explicitRoiList != "") {{
    {roi_manager_open_block}
    }} else {{
        roiZipRaw = imageDir + documentLabel + ".zip";
        roiRoiRaw = imageDir + documentLabel + ".roi";
        roiZipRoiSetRaw = imageDir + "RoiSet_" + documentLabel + ".zip";
        roiZipNormalized = imageDir + normalizedDocumentLabel + ".zip";
        roiRoiNormalized = imageDir + normalizedDocumentLabel + ".roi";
        roiZipRoiSetNormalized = imageDir + "RoiSet_" + normalizedDocumentLabel + ".zip";
        roiRoiWithExtension = imageDir + documentFilename + ".roi";

        if (File.exists(roiZipRaw)) {{
            roiManager("Open", roiZipRaw);
        }} else if (File.exists(roiRoiRaw)) {{
            roiManager("Open", roiRoiRaw);
        }} else if (File.exists(roiZipRoiSetRaw)) {{
            roiManager("Open", roiZipRoiSetRaw);
        }} else if (File.exists(roiZipNormalized)) {{
            roiManager("Open", roiZipNormalized);
        }} else if (File.exists(roiRoiNormalized)) {{
            roiManager("Open", roiRoiNormalized);
        }} else if (File.exists(roiZipRoiSetNormalized)) {{
            roiManager("Open", roiZipRoiSetNormalized);
        }} else if (File.exists(roiRoiWithExtension)) {{
            roiManager("Open", roiRoiWithExtension);
        }} else {{
            print("WARN: ROI file not found for image: " + documentLabel);
            continueProcessing = false;
        }}
    }}

    if (continueProcessing && roiManager("count") == 0) {{
        print("WARN: No ROIs loaded; measurements were not written.");
        continueProcessing = false;
    }}

    if (continueProcessing) {{
        run("Select None");
        run("Split Channels");
        imgList = getList("image.titles");

        if (imgList.length < targetChannelPosition) {{
            print("WARN: Requested channel index is out of range.");
            continueProcessing = false;
        }}
    }}

    if (continueProcessing) {{
        selectWindow(imgList[targetChannelPosition - 1]);
        channelTitle = getTitle();
        run("Z Project...", "projection=[" + projectionMethod + "]");
        setThreshold(thresholdLow, thresholdHigh);
        run("Set Measurements...", measurementsOptions);

        roiCount = roiManager("count");
        for (j = 0; j < roiCount; j++) {{
            roiManager("Select", j);
            roiName = call("ij.plugin.frame.RoiManager.getName", j);
            if (roiName == "" || roiName == "null") roiName = "ROI_" + (j + 1);

            before = nResults;
            run("Measure");
            after = nResults;

            for (r = before; r < after; r++) {{
                setResult("Channel", r, channelTitle);
                setResult("Document", r, documentLabel);
                setResult("ROI", r, roiName);
                setResult("Scope", r, "ThresholdedMatchingROIAfterMIP");
            }}
        }}
        updateResults();

        if (resultsPath == "" || resultsPath == "null") {{
            print("WARN: resultsPath is empty; measurements were not written to disk.");
        }} else {{
            saveAs("Results", resultsPath);
        }}
    }}

    if (closeAllWhenDone) run("Close All");
    if (quitWhenDone) run("Quit");
    ''',
    aliases=("measure_area_fraction_channel2_mip_threshold_roi",),
    profile=MacroGuiProfile(
        apply_roi_templates=True,
        save_processed_images=False,
        save_measurement_csv=True,
        generate_measurement_summary=True,
        processed_suffix="processed",
        measurements_folder="Measurements",
        processed_folder="Processed_Files",
        measurement_prefix="measurements_summary",
        note="Builds a channel-2 projection, thresholds it inside matching ROI files, and exports measurements.",
    ),
)

MACROS_LIB.add(
    "measure_channel_2_in_matching_roi_after_mip",
    '''
    // Create a projection of channel 2, load matching ROI files, and measure all standard ROI metrics inside each ROI.
    //
    // --- Editable parameters ---
    inputPath = "{img_path_fiji}";
    imageDir = "{img_dir_fiji_slash}";
    resultsPath = "{out_csv}";
    documentLabel = "{document_name_raw}";
    normalizedDocumentLabel = "{document_name}";
    documentFilename = "{document_filename_raw}";
    explicitRoiList = "{roi_paths_joined}";
    targetChannelPosition = 2;
    projectionMethod = "Max Intensity";
    measurementsOptions = "area mean standard min max integrated median area_fraction perimeter feret shape redirect=None decimal=3";
    saveMipImage = false;
    mipPath = "{output_dir_fiji_slash}{file_stem}_C2_MIP";
    batchModeEnabled = true;
    closeAllWhenDone = true;
    quitWhenDone = true;

    continueProcessing = true;

    // --- Open image ---
    if (batchModeEnabled) setBatchMode(true);
    run("Bio-Formats Macro Extensions");
    Ext.openImagePlus(inputPath);

    // --- Load matching ROI(s) ---
    roiManager("Reset");
    if (explicitRoiList != "") {{
    {roi_manager_open_block}
    }} else {{
        roiZipRaw = imageDir + documentLabel + ".zip";
        roiRoiRaw = imageDir + documentLabel + ".roi";
        roiZipRoiSetRaw = imageDir + "RoiSet_" + documentLabel + ".zip";
        roiZipNormalized = imageDir + normalizedDocumentLabel + ".zip";
        roiRoiNormalized = imageDir + normalizedDocumentLabel + ".roi";
        roiZipRoiSetNormalized = imageDir + "RoiSet_" + normalizedDocumentLabel + ".zip";
        roiRoiWithExtension = imageDir + documentFilename + ".roi";

        if (File.exists(roiZipRaw)) {{
            roiManager("Open", roiZipRaw);
        }} else if (File.exists(roiRoiRaw)) {{
            roiManager("Open", roiRoiRaw);
        }} else if (File.exists(roiZipRoiSetRaw)) {{
            roiManager("Open", roiZipRoiSetRaw);
        }} else if (File.exists(roiZipNormalized)) {{
            roiManager("Open", roiZipNormalized);
        }} else if (File.exists(roiRoiNormalized)) {{
            roiManager("Open", roiRoiNormalized);
        }} else if (File.exists(roiZipRoiSetNormalized)) {{
            roiManager("Open", roiZipRoiSetNormalized);
        }} else if (File.exists(roiRoiWithExtension)) {{
            roiManager("Open", roiRoiWithExtension);
        }} else {{
            print("WARN: ROI file not found for image: " + documentLabel);
            continueProcessing = false;
        }}
    }}

    if (continueProcessing && roiManager("count") == 0) {{
        print("WARN: No ROIs loaded; measurements were not written.");
        continueProcessing = false;
    }}

    if (continueProcessing) {{
        run("Select None");
        run("Split Channels");
        imgList = getList("image.titles");

        if (imgList.length < targetChannelPosition) {{
            print("WARN: Requested channel index is out of range.");
            continueProcessing = false;
        }}
    }}

    if (continueProcessing) {{
        selectWindow(imgList[targetChannelPosition - 1]);
        channelTitle = getTitle();
        run("Z Project...", "projection=[" + projectionMethod + "]");
        projectedChannelTitle = getTitle();
        run("Set Measurements...", measurementsOptions);

        if (saveMipImage) {{
            saveAs("Tiff", mipPath);
        }}

        roiCount = roiManager("count");
        for (j = 0; j < roiCount; j++) {{
            roiManager("Select", j);
            roiName = call("ij.plugin.frame.RoiManager.getName", j);
            if (roiName == "" || roiName == "null") roiName = "ROI_" + (j + 1);

            before = nResults;
            run("Measure");
            after = nResults;

            for (r = before; r < after; r++) {{
                setResult("Channel", r, projectedChannelTitle);
                setResult("Document", r, documentLabel);
                setResult("ROI", r, roiName);
                setResult("Scope", r, "Channel2MatchingROIAfterMIP");
            }}
        }}
        updateResults();

        if (resultsPath == "" || resultsPath == "null") {{
            print("WARN: resultsPath is empty; measurements were not written to disk.");
        }} else {{
            saveAs("Results", resultsPath);
        }}
    }}

    if (closeAllWhenDone) run("Close All");
    if (quitWhenDone) run("Quit");
    ''',
    profile=MacroGuiProfile(
        apply_roi_templates=True,
        save_processed_images=False,
        save_measurement_csv=True,
        generate_measurement_summary=True,
        processed_suffix="processed",
        measurements_folder="Measurements",
        processed_folder="Processed_Files",
        measurement_prefix="measurements_summary",
        note="Builds a channel-2 MIP, applies same-name ROI files, and exports full ROI measurements.",
    ),
)

MACROS_LIB.add(
    "detect_channel_2_particles_in_matching_roi",
    '''
    // Restrict channel 2 to a matching ROI, detect thresholded particles, and measure both the parent ROI and particle ROIs.
    //
    // --- Editable parameters ---
    inputPath = "{img_path_fiji}";
    imageDir = "{img_dir_fiji_slash}";
    outputDir = "{output_dir_fiji_slash}";
    resultsPath = "{out_csv}";
    documentLabel = "{document_name_raw}";
    normalizedDocumentLabel = "{document_name}";
    documentFilename = "{document_filename_raw}";
    targetChannelPosition = 2;
    projectionMethod = "Max Intensity";
    blurSigma = 2;
    thresholdLow = 500;
    thresholdHigh = 65535;
    particleSize = "25-Infinity";
    particleCircularity = "0.00-1.00";
    roiMeasurementsOptions = "area mean min max std perimeter feret shape redirect=None decimal=3";
    saveThresholdMask = true;
    saveParticleRois = true;
    batchModeEnabled = true;
    closeAllWhenDone = true;
    quitWhenDone = true;

    continueProcessing = true;

    // --- Open image and build MIP ---
    if (batchModeEnabled) setBatchMode(true);
    run("Bio-Formats Macro Extensions");
    Ext.openImagePlus(inputPath);
    originalTitle = getTitle();
    run("Z Project...", "projection=[" + projectionMethod + "]");
    maxTitle = getTitle();

    selectWindow(originalTitle);
    run("Close");

    selectWindow(maxTitle);
    run("Split Channels");
    imgList = getList("image.titles");
    if (imgList.length < targetChannelPosition) {{
        print("WARN: Requested channel index is out of range.");
        continueProcessing = false;
    }}

    if (continueProcessing) {{
        selectWindow(imgList[targetChannelPosition - 1]);
        channelTitle = getTitle();
        run("Duplicate...", "title=[C2_mask.tif]");
        maskTitle = getTitle();
    }}

    // --- Load matching ROI(s) ---
    if (continueProcessing) {{
        roiManager("Reset");
        roiZipRaw = imageDir + documentLabel + ".zip";
        roiRoiRaw = imageDir + documentLabel + ".roi";
        roiZipRoiSetRaw = imageDir + "RoiSet_" + documentLabel + ".zip";
        roiZipNormalized = imageDir + normalizedDocumentLabel + ".zip";
        roiRoiNormalized = imageDir + normalizedDocumentLabel + ".roi";
        roiZipRoiSetNormalized = imageDir + "RoiSet_" + normalizedDocumentLabel + ".zip";
        roiRoiWithExtension = imageDir + documentFilename + ".roi";

        if (File.exists(roiZipRaw)) {{
            roiManager("Open", roiZipRaw);
        }} else if (File.exists(roiRoiRaw)) {{
            roiManager("Open", roiRoiRaw);
        }} else if (File.exists(roiZipRoiSetRaw)) {{
            roiManager("Open", roiZipRoiSetRaw);
        }} else if (File.exists(roiZipNormalized)) {{
            roiManager("Open", roiZipNormalized);
        }} else if (File.exists(roiRoiNormalized)) {{
            roiManager("Open", roiRoiNormalized);
        }} else if (File.exists(roiZipRoiSetNormalized)) {{
            roiManager("Open", roiZipRoiSetNormalized);
        }} else if (File.exists(roiRoiWithExtension)) {{
            roiManager("Open", roiRoiWithExtension);
        }} else {{
            print("WARN: ROI file not found for image: " + documentLabel);
            continueProcessing = false;
        }}
    }}

    if (continueProcessing && roiManager("count") == 0) {{
        print("WARN: No ROIs loaded; particle analysis was skipped.");
        continueProcessing = false;
    }}

    if (continueProcessing) {{
        // --- Restrict mask to the first ROI ---
        selectWindow(maskTitle);
        roiManager("Select", 0);
        run("Clear Outside");

        // --- Measure the parent ROI on the original channel ---
        selectWindow(channelTitle);
        run("Set Measurements...", roiMeasurementsOptions);
        roiManager("Select", 0);
        before = nResults;
        run("Measure");
        after = nResults;
        for (r = before; r < after; r++) {{
            setResult("Channel", r, channelTitle);
            setResult("Document", r, documentLabel);
            setResult("ROI", r, "ROI_Mask");
            setResult("Scope", r, "ParentROI");
        }}

        // --- Detect particles inside the restricted mask ---
        roiManager("Reset");
        selectWindow(maskTitle);
        run("Gaussian Blur...", "sigma=" + blurSigma);
        setThreshold(thresholdLow, thresholdHigh);
        setOption("BlackBackground", false);
        run("Convert to Mask");

        if (saveThresholdMask) {{
            saveAs("Tiff", outputDir + documentLabel + "_C2_threshold_mask.tif");
        }}

        run("Analyze Particles...", "size=" + particleSize + " circularity=" + particleCircularity + " show=Nothing add");

        if (saveParticleRois && roiManager("count") > 0) {{
            roiManager("Select All");
            roiManager("Save", outputDir + "RoiSet_" + documentLabel + "_particles.zip");
        }}

        // --- Measure every detected particle on the source channel ---
        selectWindow(channelTitle);
        run("Set Measurements...", roiMeasurementsOptions);
        roiTotal = roiManager("count");
        for (j = 0; j < roiTotal; j++) {{
            roiManager("Select", j);
            before = nResults;
            run("Measure");
            after = nResults;
            for (r = before; r < after; r++) {{
                setResult("Channel", r, channelTitle);
                setResult("Document", r, documentLabel);
                setResult("ROI", r, "ROI_" + (j + 1));
                setResult("Scope", r, "DetectedParticle");
            }}
        }}

        if (resultsPath == "" || resultsPath == "null") {{
            print("WARN: resultsPath is empty; measurements were not written to disk.");
        }} else {{
            saveAs("Results", resultsPath);
        }}
    }}

    if (closeAllWhenDone) run("Close All");
    if (quitWhenDone) run("Quit");
    ''',
    aliases=("Analyse_particles_and_measureAll",),
    profile=MacroGuiProfile(
        apply_roi_templates=True,
        save_processed_images=True,
        save_measurement_csv=True,
        generate_measurement_summary=True,
        processed_suffix="processed",
        measurements_folder="Measurements",
        processed_folder="Processed_Files",
        measurement_prefix="measurements_summary",
        note="Needs ROI input and processed output folders because it saves masks and detected particle ROI sets.",
    ),
)

MACROS_LIB.add(
    "measure_channel_2_thresholded_area_and_particles_in_matching_roi_after_mip",
    '''
    // Build a channel-2 MIP, crop it to a matching ROI, measure thresholded %Area, and export full particle measurements.
    //
    // --- Editable parameters ---
    inputPath = "{img_path_fiji}";
    imageDir = "{img_dir_fiji_slash}";
    outputDir = "{output_dir_fiji_slash}";
    measurementsDir = "{measurements_dir_fiji_slash}";
    resultsPath = "{out_csv}";
    documentLabel = "{document_name_raw}";
    normalizedDocumentLabel = "{document_name}";
    documentFilename = "{document_filename_raw}";
    areaFractionResultsPath = measurementsDir + documentLabel + "_area_fraction.csv";
    particleResultsPath = resultsPath;
    particleRoiZipPath = outputDir + "RoiSet_" + documentLabel + "_particles.zip";
    explicitRoiList = "{roi_paths_joined}";
    matchingRoiIndex = 0;
    targetChannelPosition = 2;
    projectionMethod = "Max Intensity";
    blurSigma = 2;
    thresholdLow = 300;
    thresholdHigh = 65535;
    particleSize = "25-Infinity";
    particleCircularity = "0.00-1.00";
    areaMeasurementsOptions = "area area_fraction redirect=None decimal=3";
    particleMeasurementsOptions = "area mean standard min max integrated median perimeter feret shape redirect=None decimal=3";
    saveCroppedMip = true;
    saveThresholdMask = true;
    saveParticleRois = true;
    batchModeEnabled = true;
    closeAllWhenDone = true;
    quitWhenDone = true;

    continueProcessing = true;
    matchingRoiName = documentLabel;

    // --- Open image and build channel-2 MIP ---
    if (batchModeEnabled) setBatchMode(true);
    run("Bio-Formats Macro Extensions");
    Ext.openImagePlus(inputPath);
    run("Split Channels");
    imgList = getList("image.titles");

    if (imgList.length < targetChannelPosition) {{
        print("WARN: Requested channel index is out of range.");
        continueProcessing = false;
    }}

    if (continueProcessing) {{
        selectWindow(imgList[targetChannelPosition - 1]);
        channelTitle = getTitle();
        run("Z Project...", "projection=[" + projectionMethod + "]");
        projectedChannelTitle = getTitle();
        projectedImageId = getImageID();
    }}

    // --- Load matching ROI(s) ---
    if (continueProcessing) {{
        roiManager("Reset");
        if (explicitRoiList != "") {{
        {roi_manager_open_block}
        }} else {{
            roiZipRaw = imageDir + documentLabel + ".zip";
            roiRoiRaw = imageDir + documentLabel + ".roi";
            roiZipRoiSetRaw = imageDir + "RoiSet_" + documentLabel + ".zip";
            roiZipNormalized = imageDir + normalizedDocumentLabel + ".zip";
            roiRoiNormalized = imageDir + normalizedDocumentLabel + ".roi";
            roiZipRoiSetNormalized = imageDir + "RoiSet_" + normalizedDocumentLabel + ".zip";
            roiRoiWithExtension = imageDir + documentFilename + ".roi";

            if (File.exists(roiZipRaw)) {{
                roiManager("Open", roiZipRaw);
            }} else if (File.exists(roiRoiRaw)) {{
                roiManager("Open", roiRoiRaw);
            }} else if (File.exists(roiZipRoiSetRaw)) {{
                roiManager("Open", roiZipRoiSetRaw);
            }} else if (File.exists(roiZipNormalized)) {{
                roiManager("Open", roiZipNormalized);
            }} else if (File.exists(roiRoiNormalized)) {{
                roiManager("Open", roiRoiNormalized);
            }} else if (File.exists(roiZipRoiSetNormalized)) {{
                roiManager("Open", roiZipRoiSetNormalized);
            }} else if (File.exists(roiRoiWithExtension)) {{
                roiManager("Open", roiRoiWithExtension);
            }} else {{
                print("WARN: ROI file not found for image: " + documentLabel);
                continueProcessing = false;
            }}
        }}
    }}

    if (continueProcessing && roiManager("count") == 0) {{
        print("WARN: No ROIs loaded; measurements were not written.");
        continueProcessing = false;
    }}

    if (continueProcessing && matchingRoiIndex >= roiManager("count")) {{
        print("WARN: matchingRoiIndex is out of range.");
        continueProcessing = false;
    }}

    if (continueProcessing) {{
        roiManager("Select", matchingRoiIndex);
        matchingRoiName = call("ij.plugin.frame.RoiManager.getName", matchingRoiIndex);
        if (matchingRoiName == "" || matchingRoiName == "null") matchingRoiName = documentLabel;
    }}

    // --- Measure thresholded %Area on the projected image inside the parent ROI ---
    if (continueProcessing) {{
        selectImage(projectedImageId);
        roiManager("Select", matchingRoiIndex);
        setThreshold(thresholdLow, thresholdHigh);
        run("Set Measurements...", areaMeasurementsOptions);
        run("Clear Results");

        before = nResults;
        run("Measure");
        after = nResults;

        for (r = before; r < after; r++) {{
            setResult("Channel", r, projectedChannelTitle);
            setResult("Document", r, documentLabel);
            setResult("ROI", r, matchingRoiName);
            setResult("Scope", r, "ThresholdedAreaFraction");
            setResult("ThresholdLow", r, thresholdLow);
            setResult("ThresholdHigh", r, thresholdHigh);
        }}
        updateResults();
        saveAs("Results", areaFractionResultsPath);
        resetThreshold();
        run("Clear Results");
    }}

    // --- Create and save the cropped working image ---
    if (continueProcessing) {{
        selectImage(projectedImageId);
        roiManager("Select", matchingRoiIndex);
        croppedTitle = documentLabel + "_C2_MIP_cropped";
        run("Duplicate...", "title=[" + croppedTitle + "]");
        croppedImageId = getImageID();
        croppedTitle = getTitle();
        if (croppedTitle != documentLabel + "_C2_MIP_cropped") {{
            rename(documentLabel + "_C2_MIP_cropped");
            croppedTitle = getTitle();
        }}

        if (selectionType() == -1) {{
            run("Restore Selection");
        }}
        if (selectionType() != -1) {{
            setBackgroundColor(0, 0, 0);
            run("Clear Outside");
        }} else {{
            print("WARN: ROI selection was not preserved on the cropped image.");
            continueProcessing = false;
        }}

        if (continueProcessing && saveCroppedMip) {{
            saveAs("Tiff", outputDir + documentLabel + "_C2_MIP_cropped.tif");
        }}
    }}

    // --- Threshold the cropped image and detect particles ---
    if (continueProcessing) {{
        selectImage(croppedImageId);
        run("Duplicate...", "title=[" + documentLabel + "_C2_threshold_mask]");
        maskTitle = getTitle();
        maskImageId = getImageID();
        run("Gaussian Blur...", "sigma=" + blurSigma);
        setThreshold(thresholdLow, thresholdHigh);
        setOption("BlackBackground", false);
        run("Convert to Mask");

        if (saveThresholdMask) {{
            saveAs("Tiff", outputDir + documentLabel + "_C2_threshold_mask.tif");
        }}

        roiManager("Reset");
        run("Analyze Particles...", "size=" + particleSize + " circularity=" + particleCircularity + " show=Nothing add");

        if (saveParticleRois && roiManager("count") > 0) {{
            roiManager("Select All");
            roiManager("Save", particleRoiZipPath);
        }}
    }}

    // --- Measure every detected particle on the cropped grayscale source image ---
    if (continueProcessing) {{
        if (particleResultsPath == "" || particleResultsPath == "null") {{
            particleResultsPath = measurementsDir + documentLabel + "_particle_measurements.csv";
        }}

        run("Clear Results");
        selectImage(croppedImageId);
        run("Set Measurements...", particleMeasurementsOptions);
        roiTotal = roiManager("count");

        for (j = 0; j < roiTotal; j++) {{
            roiManager("Select", j);
            before = nResults;
            run("Measure");
            after = nResults;

            for (r = before; r < after; r++) {{
                setResult("Channel", r, croppedTitle);
                setResult("Document", r, documentLabel);
                setResult("ParentROI", r, matchingRoiName);
                setResult("ParticleROI", r, "Particle_" + (j + 1));
                setResult("Scope", r, "DetectedParticle");
                setResult("ThresholdLow", r, thresholdLow);
                setResult("ThresholdHigh", r, thresholdHigh);
            }}
        }}
        updateResults();
        saveAs("Results", particleResultsPath);
    }}

    if (closeAllWhenDone) run("Close All");
    if (quitWhenDone) run("Quit");
    ''',
    profile=MacroGuiProfile(
        apply_roi_templates=True,
        save_processed_images=True,
        save_measurement_csv=True,
        generate_measurement_summary=True,
        processed_suffix="processed",
        measurements_folder="Measurements",
        processed_folder="Processed_Files",
        measurement_prefix="measurements_summary",
        note="Saves cropped channel-2 MIPs, threshold masks, particle ROI zips, a separate %Area CSV, and particle measurements.",
    ),
)

MACROS_LIB.add_from_file(
    "measure_lfb_red_channel_in_rois",
    "lfb_luxol_red_threshold185_macro.ijm",
    aliases=("lfb_luxol_red_threshold185",),
    profile=MacroGuiProfile(
        apply_roi_templates=True,
        save_processed_images=False,
        save_measurement_csv=True,
        generate_measurement_summary=True,
        processed_suffix="processed",
        measurements_folder="Measurements",
        processed_folder="Processed_Files",
        measurement_prefix="measurements_summary",
        note="Measures the red threshold signal inside ROI files and exports measurement tables.",
    ),
)
MACROS_LIB.add_from_file(
    "measure_lfb_channel1_raw_and_threshold180_in_matching_roi",
    "lfb_luxol_channel1_raw_and_threshold180_macro.ijm",
    aliases=("lfb_luxol_channel1_threshold180_dual",),
    profile=MacroGuiProfile(
        apply_roi_templates=True,
        save_processed_images=True,
        save_measurement_csv=True,
        generate_measurement_summary=True,
        processed_suffix="processed",
        measurements_folder="Measurements",
        processed_folder="Processed_Files",
        measurement_prefix="measurements_summary",
        note="Measures channel 1 inside the matching ROI before and after applying a fixed threshold of 180, and saves the threshold mask TIFF.",
    ),
)

MACRO_ALIASES = MACROS_LIB.aliases

__all__ = ["MACROS_LIB", "MACRO_ALIASES", "MacroGuiProfile", "MacroLibrary"]
