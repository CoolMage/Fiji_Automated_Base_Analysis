// Create and save a threshold mask for one selected channel.
//
// Use this macro as a segmentation QC artifact before running quantitative
// thresholded-area or particle workflows.
// Inputs: one Bio-Formats-readable image and a locked threshold range.
// Outputs: one binary mask TIFF; optionally one Results CSV with mask occupancy.
// Limitations: the mask is only as valid as the fixed threshold and optional
// preprocessing parameters.
//
// --- Editable parameters ---
inputPath = "{img_path_fiji}";
outputDir = "{output_dir_fiji_slash}";
fallbackOutputDir = "{img_dir_fiji_slash}";
resultsPath = "{out_csv}";
documentLabel = "{file_stem_raw}";
outputStem = "{file_stem}";
targetChannelPosition = 2;
projectBeforeMask = true;
projectionMethod = "Max Intensity";
rollingBallRadiusPixels = 0;
blurSigma = 0;
thresholdLow = 500;
thresholdHigh = 65535;
maskBlackBackground = false;
maskSuffix = "_threshold_mask";
saveMaskSummary = false;
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

// --- Build binary mask ---
if (continueProcessing) {
    if (outputDir == "" || outputDir == "null" || outputDir == "/") outputDir = fallbackOutputDir;
    if (!File.exists(outputDir)) File.makeDirectory(outputDir);

    selectWindow(channelTitles[targetChannelPosition - 1]);
    if (projectBeforeMask) run("Z Project...", "projection=[" + projectionMethod + "]");
    channelTitle = getTitle();

    if (rollingBallRadiusPixels > 0) {
        run("Subtract Background...", "rolling=" + rollingBallRadiusPixels);
    }
    if (blurSigma > 0) {
        run("Gaussian Blur...", "sigma=" + blurSigma);
    }

    setThreshold(thresholdLow, thresholdHigh);
    setOption("BlackBackground", maskBlackBackground);
    run("Convert to Mask");
    run("Grays");
    rename(outputStem + maskSuffix);
    saveAs("Tiff", outputDir + outputStem + maskSuffix + ".tif");

    if (saveMaskSummary && resultsPath != "" && resultsPath != "null") {
        Stack.getStatistics(voxelCount, maskMean, maskMin, maskMax, maskStdDev);
        positiveVoxels = voxelCount * maskMean / 255.0;
        run("Clear Results");
        row = 0;
        setResult("Document", row, documentLabel);
        setResult("Channel", row, channelTitle);
        setResult("Scope", row, "ThresholdMask");
        setResult("ThresholdLow", row, thresholdLow);
        setResult("ThresholdHigh", row, thresholdHigh);
        setResult("VoxelCount", row, voxelCount);
        setResult("PositiveVoxels", row, positiveVoxels);
        setResult("PositiveFraction", row, positiveVoxels / voxelCount);
        updateResults();
        saveAs("Results", resultsPath);
    }
}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
