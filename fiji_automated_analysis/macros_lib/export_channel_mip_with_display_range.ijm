// Export one channel MIP with a fixed display range.
//
// Use this macro for standardized QC images where the same channel, projection,
// and brightness/contrast settings must be applied across a batch.
// Inputs: one Bio-Formats-readable multichannel stack.
// Outputs: one TIFF for the selected channel MIP.
// Limitations: applying the LUT to pixels changes the exported pixel values;
// keep it disabled when quantitative pixel values must be preserved.
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
outputSuffix = "_C2_MIP_display_range";
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

continueProcessing = true;

// --- Open image and select channel ---
if (batchModeEnabled) setBatchMode(true);
run("Bio-Formats Macro Extensions");
Ext.openImagePlus(inputPath);
run("Split Channels");
channelTitles = getList("image.titles");

if (channelTitles.length < targetChannelPosition) {
    print("WARN: requested channel index is out of range.");
    continueProcessing = false;
}

// --- Project, apply display range, and save ---
if (continueProcessing) {
    if (outputDir == "" || outputDir == "null" || outputDir == "/") outputDir = fallbackOutputDir;
    if (!File.exists(outputDir)) File.makeDirectory(outputDir);

    selectWindow(channelTitles[targetChannelPosition - 1]);
    run("Z Project...", "projection=[" + projectionMethod + "]");
    rename(outputStem + outputSuffix);

    if (resetDisplayRangeFirst) resetMinAndMax();
    setMinAndMax(displayMin, displayMax);
    if (applyBrightnessContrastToPixels) run("Apply LUT");
    if (convertTo8Bit) run("8-bit");

    saveAs("Tiff", outputDir + outputStem + outputSuffix + ".tif");
}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
