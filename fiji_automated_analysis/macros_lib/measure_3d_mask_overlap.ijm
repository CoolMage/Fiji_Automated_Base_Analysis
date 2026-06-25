// Measure 3D voxel overlap between thresholded masks from two or three channels.
//
// Use this macro for spatial co-occurrence endpoints when channels are
// registered, bleed-through is controlled, and thresholds are fixed from
// controls or a documented pilot rule.
// Inputs: one Bio-Formats-readable multichannel stack, optional ROI files, and
// locked thresholds for each analyzed channel.
// Outputs: one Results CSV with positive voxel counts, pairwise overlap,
// coverage percentages, Jaccard ratios, and optional triple overlap.
// Limitations: this macro measures voxel co-occurrence, not cell counts or
// object-level colocalization.
//
// --- Editable parameters ---
inputPath = "{img_path_fiji}";
outputDir = "{output_dir_fiji_slash}";
imageDir = "{img_dir_fiji_slash}";
resultsPath = "{out_csv}";
documentLabel = "{file_stem_raw}";
normalizedDocumentLabel = "{file_stem}";
documentFilename = "{document_filename_raw}";
explicitRoiList = "{roi_paths_joined}";
primaryChannel = 1;
secondaryChannel = 2;
tertiaryChannel = 3;
useTertiaryChannel = true;
primaryLabel = "Primary";
secondaryLabel = "Secondary";
tertiaryLabel = "Tertiary";
primaryThresholdLow = 500;
secondaryThresholdLow = 500;
tertiaryThresholdLow = 500;
thresholdHigh = 65535;
thresholdCalibration = "PILOT_VALUES_NOT_CONTROL_CALIBRATED";
rollingBallRadiusPixels = 0;
medianRadiusPixels = 0;
saveQcMips = true;
saveFullMaskStacks = false;
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

primaryCorrectedTitle = "BASE_PRIMARY_CORRECTED";
secondaryCorrectedTitle = "BASE_SECONDARY_CORRECTED";
tertiaryCorrectedTitle = "BASE_TERTIARY_CORRECTED";
primaryMaskTitle = "BASE_PRIMARY_MASK";
secondaryMaskTitle = "BASE_SECONDARY_MASK";
tertiaryMaskTitle = "BASE_TERTIARY_MASK";
analysisRoiMaskTitle = "BASE_ANALYSIS_ROI";

function failAndQuit(message) {
    print("Macro Error: 3D_MASK_OVERLAP ERROR: " + message);
    run("Close All");
    run("Quit");
    exit();
}

function findChannelTitle(titles, channelIndex) {
    prefix = "C" + channelIndex + "-";
    for (i = 0; i < titles.length; i++) {
        if (startsWith(titles[i], prefix)) return titles[i];
    }
    if (channelIndex >= 1 && channelIndex <= titles.length) return titles[channelIndex - 1];
    return "";
}

function makeCorrectedImageAndMask(sourceTitle, correctedTitle, maskTitle, rollingRadius, medianRadius, thresholdLow, thresholdUpper) {
    selectWindow(sourceTitle);
    run("Duplicate...", "title=[" + correctedTitle + "] duplicate");
    selectWindow(sourceTitle);
    run("Close");
    selectWindow(correctedTitle);

    if (rollingRadius > 0) {
        run("Subtract Background...", "rolling=" + rollingRadius + " stack");
    }
    if (medianRadius > 0) {
        run("Median...", "radius=" + medianRadius + " stack");
    }

    run("Duplicate...", "title=[" + maskTitle + "] duplicate");
    selectWindow(maskTitle);
    setThreshold(thresholdLow, thresholdUpper);
    setOption("BlackBackground", true);
    run("Convert to Mask", "method=Default background=Dark black");
    resetThreshold();
}

function positiveVoxels(maskTitle) {
    selectWindow(maskTitle);
    Stack.getStatistics(voxelCount, meanValue, minValue, maxValue, stdDev);
    return voxelCount * meanValue / 255.0;
}

function safeRatio(numerator, denominator) {
    if (denominator <= 0) return NaN;
    return numerator / denominator;
}

function saveMaskMip(maskTitle, outputPath) {
    selectWindow(maskTitle);
    run("Z Project...", "projection=[Max Intensity]");
    projectionTitle = getTitle();
    saveAs("Tiff", outputPath);
    selectWindow(projectionTitle);
    run("Close");
}

function saveMaskOutputs(maskTitle, mipPath, stackPath, saveMip, saveStack) {
    if (saveMip) saveMaskMip(maskTitle, mipPath);
    if (saveStack && stackPath != "") {
        selectWindow(maskTitle);
        saveAs("Tiff", stackPath);
    }
}

function applyAnalysisRoi(maskTitle, roiMaskTitle) {
    imageCalculator("AND create stack", maskTitle, roiMaskTitle);
    resultTitle = getTitle();
    selectWindow(maskTitle);
    run("Close");
    selectWindow(resultTitle);
    rename(maskTitle);
}

function overlapVoxels(maskATitle, maskBTitle, overlapTitle, outputPath, saveMip) {
    imageCalculator("AND create stack", maskATitle, maskBTitle);
    resultTitle = getTitle();
    rename(overlapTitle);
    overlapCount = positiveVoxels(overlapTitle);
    if (saveMip) saveMaskMip(overlapTitle, outputPath);
    selectWindow(overlapTitle);
    run("Close");
    return overlapCount;
}

if (batchModeEnabled) setBatchMode(true);

// --- Open and validate source image ---
run("Bio-Formats Macro Extensions");
Ext.openImagePlus(inputPath);
getDimensions(imageWidth, imageHeight, channelCount, sliceCount, frameCount);

if (frameCount != 1) failAndQuit("time series are not supported.");
if (primaryChannel < 1 || primaryChannel > channelCount) failAndQuit("primaryChannel is out of range.");
if (secondaryChannel < 1 || secondaryChannel > channelCount) failAndQuit("secondaryChannel is out of range.");
if (useTertiaryChannel && (tertiaryChannel < 1 || tertiaryChannel > channelCount)) failAndQuit("tertiaryChannel is out of range.");
if (primaryChannel == secondaryChannel) failAndQuit("primary and secondary channels must differ.");
if (useTertiaryChannel && (primaryChannel == tertiaryChannel || secondaryChannel == tertiaryChannel)) failAndQuit("tertiary channel must differ from primary and secondary.");

run("Split Channels");
channelTitles = getList("image.titles");
primarySourceTitle = findChannelTitle(channelTitles, primaryChannel);
secondarySourceTitle = findChannelTitle(channelTitles, secondaryChannel);
tertiarySourceTitle = "";
if (useTertiaryChannel) tertiarySourceTitle = findChannelTitle(channelTitles, tertiaryChannel);

if (primarySourceTitle == "" || secondarySourceTitle == "") failAndQuit("unable to resolve primary or secondary split channel.");
if (useTertiaryChannel && tertiarySourceTitle == "") failAndQuit("unable to resolve tertiary split channel.");

// --- Build optional 3D ROI mask from loaded 2D ROIs ---
roiManager("Reset");
if (explicitRoiList != "") {
{roi_manager_open_block}
} else {
    roiZipRaw = imageDir + documentLabel + ".zip";
    roiRoiRaw = imageDir + documentLabel + ".roi";
    roiZipRoiSetRaw = imageDir + "RoiSet_" + documentLabel + ".zip";
    roiZipNormalized = imageDir + normalizedDocumentLabel + ".zip";
    roiRoiNormalized = imageDir + normalizedDocumentLabel + ".roi";
    roiZipRoiSetNormalized = imageDir + "RoiSet_" + normalizedDocumentLabel + ".zip";
    roiRoiWithExtension = imageDir + documentFilename + ".roi";

    if (File.exists(roiZipRaw)) {
        roiManager("Open", roiZipRaw);
    } else if (File.exists(roiRoiRaw)) {
        roiManager("Open", roiRoiRaw);
    } else if (File.exists(roiZipRoiSetRaw)) {
        roiManager("Open", roiZipRoiSetRaw);
    } else if (File.exists(roiZipNormalized)) {
        roiManager("Open", roiZipNormalized);
    } else if (File.exists(roiRoiNormalized)) {
        roiManager("Open", roiRoiNormalized);
    } else if (File.exists(roiZipRoiSetNormalized)) {
        roiManager("Open", roiZipRoiSetNormalized);
    } else if (File.exists(roiRoiWithExtension)) {
        roiManager("Open", roiRoiWithExtension);
    }
}
roiCount = roiManager("count");

if (roiCount > 0) {
    selectWindow(primarySourceTitle);
    getDimensions(imageWidth, imageHeight, ignoredChannels, sliceCount, ignoredFrames);
    newImage(analysisRoiMaskTitle, "8-bit black", imageWidth, imageHeight, sliceCount);
    setForegroundColor(255, 255, 255);
    for (z = 1; z <= sliceCount; z++) {
        setSlice(z);
        for (r = 0; r < roiCount; r++) {
            roiManager("Select", r);
            run("Fill", "slice");
        }
    }
    run("Select None");
}

// --- Create threshold masks ---
makeCorrectedImageAndMask(primarySourceTitle, primaryCorrectedTitle, primaryMaskTitle, rollingBallRadiusPixels, medianRadiusPixels, primaryThresholdLow, thresholdHigh);
makeCorrectedImageAndMask(secondarySourceTitle, secondaryCorrectedTitle, secondaryMaskTitle, rollingBallRadiusPixels, medianRadiusPixels, secondaryThresholdLow, thresholdHigh);
if (useTertiaryChannel) {
    makeCorrectedImageAndMask(tertiarySourceTitle, tertiaryCorrectedTitle, tertiaryMaskTitle, rollingBallRadiusPixels, medianRadiusPixels, tertiaryThresholdLow, thresholdHigh);
}

if (roiCount > 0) {
    applyAnalysisRoi(primaryMaskTitle, analysisRoiMaskTitle);
    applyAnalysisRoi(secondaryMaskTitle, analysisRoiMaskTitle);
    if (useTertiaryChannel) applyAnalysisRoi(tertiaryMaskTitle, analysisRoiMaskTitle);
}

// --- Count positive and overlapping voxels ---
primaryPositive = positiveVoxels(primaryMaskTitle);
secondaryPositive = positiveVoxels(secondaryMaskTitle);
tertiaryPositive = NaN;
if (useTertiaryChannel) tertiaryPositive = positiveVoxels(tertiaryMaskTitle);

primarySecondaryOverlap = overlapVoxels(
    primaryMaskTitle,
    secondaryMaskTitle,
    "BASE_PRIMARY_SECONDARY_OVERLAP",
    outputDir + documentLabel + "_primary_secondary_overlap_mip.tif",
    saveQcMips
);

primaryTertiaryOverlap = NaN;
secondaryTertiaryOverlap = NaN;
tripleOverlap = NaN;
if (useTertiaryChannel) {
    primaryTertiaryOverlap = overlapVoxels(
        primaryMaskTitle,
        tertiaryMaskTitle,
        "BASE_PRIMARY_TERTIARY_OVERLAP",
        outputDir + documentLabel + "_primary_tertiary_overlap_mip.tif",
        saveQcMips
    );
    secondaryTertiaryOverlap = overlapVoxels(
        secondaryMaskTitle,
        tertiaryMaskTitle,
        "BASE_SECONDARY_TERTIARY_OVERLAP",
        outputDir + documentLabel + "_secondary_tertiary_overlap_mip.tif",
        saveQcMips
    );

    imageCalculator("AND create stack", primaryMaskTitle, secondaryMaskTitle);
    primarySecondaryTitle = getTitle();
    imageCalculator("AND create stack", primarySecondaryTitle, tertiaryMaskTitle);
    tripleTitle = getTitle();
    rename("BASE_TRIPLE_OVERLAP");
    tripleOverlap = positiveVoxels("BASE_TRIPLE_OVERLAP");
    if (saveQcMips) saveMaskMip("BASE_TRIPLE_OVERLAP", outputDir + documentLabel + "_triple_overlap_mip.tif");
    selectWindow(primarySecondaryTitle);
    run("Close");
    selectWindow("BASE_TRIPLE_OVERLAP");
    run("Close");
}

if (saveQcMips || saveFullMaskStacks) {
    saveMaskOutputs(primaryMaskTitle, outputDir + documentLabel + "_primary_mask_mip.tif", outputDir + documentLabel + "_primary_mask_stack.tif", saveQcMips, saveFullMaskStacks);
    saveMaskOutputs(secondaryMaskTitle, outputDir + documentLabel + "_secondary_mask_mip.tif", outputDir + documentLabel + "_secondary_mask_stack.tif", saveQcMips, saveFullMaskStacks);
    if (useTertiaryChannel) {
        saveMaskOutputs(tertiaryMaskTitle, outputDir + documentLabel + "_tertiary_mask_mip.tif", outputDir + documentLabel + "_tertiary_mask_stack.tif", saveQcMips, saveFullMaskStacks);
    }
}

// --- Write overlap summary ---
run("Clear Results");
row = 0;
setResult("Document", row, documentLabel);
setResult("Scope", row, "ThreeDMaskOverlap");
setResult("PrimaryLabel", row, primaryLabel);
setResult("SecondaryLabel", row, secondaryLabel);
setResult("TertiaryLabel", row, tertiaryLabel);
setResult("PrimaryChannel", row, primaryChannel);
setResult("SecondaryChannel", row, secondaryChannel);
setResult("TertiaryChannel", row, tertiaryChannel);
setResult("UseTertiaryChannel", row, useTertiaryChannel);
setResult("PrimaryThresholdLow", row, primaryThresholdLow);
setResult("SecondaryThresholdLow", row, secondaryThresholdLow);
setResult("TertiaryThresholdLow", row, tertiaryThresholdLow);
setResult("ThresholdHigh", row, thresholdHigh);
setResult("ThresholdCalibration", row, thresholdCalibration);
setResult("ROI_Count", row, roiCount);
setResult("PrimaryPositiveVoxels", row, primaryPositive);
setResult("SecondaryPositiveVoxels", row, secondaryPositive);
setResult("TertiaryPositiveVoxels", row, tertiaryPositive);
setResult("PrimarySecondaryOverlapVoxels", row, primarySecondaryOverlap);
setResult("PrimaryCoveredBySecondary_pct", row, 100.0 * safeRatio(primarySecondaryOverlap, primaryPositive));
setResult("SecondaryCoveredByPrimary_pct", row, 100.0 * safeRatio(primarySecondaryOverlap, secondaryPositive));
setResult("PrimarySecondaryJaccard", row, safeRatio(primarySecondaryOverlap, primaryPositive + secondaryPositive - primarySecondaryOverlap));
setResult("PrimaryTertiaryOverlapVoxels", row, primaryTertiaryOverlap);
setResult("SecondaryTertiaryOverlapVoxels", row, secondaryTertiaryOverlap);
setResult("TripleOverlapVoxels", row, tripleOverlap);
setResult("PrimaryCoveredByTriple_pct", row, 100.0 * safeRatio(tripleOverlap, primaryPositive));
updateResults();

if (resultsPath == "" || resultsPath == "null") {
    print("WARN: resultsPath is empty; overlap summary was not written to disk.");
} else {
    saveAs("Results", resultsPath);
}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
