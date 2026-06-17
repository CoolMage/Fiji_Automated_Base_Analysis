// Quantify 3D co-occurrence of Iba1 with CD206 and CD86.
//
// The primary measurements are thresholded voxel overlap inside an optional
// anatomical ROI. Marker enrichment inside the Iba1 mask relative to a local
// Iba1-negative ring is also reported. The macro does not estimate cell counts.
//
// IMPORTANT: The fixed thresholds below are pilot values for the supplied
// 2025-05-19 image series. Replace them with thresholds established from
// single-stain and negative controls before inferential analysis.

// --- Project paths ---
inputPath = "{img_path_fiji}";
outputDir = "{output_dir_fiji_slash}";
measurementsDir = "{measurements_dir_fiji_slash}";
imageDir = "{img_dir_fiji_slash}";
resultsPath = "{out_csv}";
documentLabel = "{file_stem}";
explicitRoiList = "{roi_paths_joined}";

// --- Channel mapping ---
// The supplied filenames use Iba1_CD206_CD86 order. Verify this mapping against
// acquisition records or single-stain controls before batch processing.
iba1Channel = 1;
cd206Channel = 2;
cd86Channel = 3;

// --- Fixed segmentation parameters ---
// Values are applied after rolling-ball subtraction and median filtering.
iba1ThresholdLow = 1600;
cd206ThresholdLow = 2200;
cd86ThresholdLow = 1800;
thresholdHigh = 65535;
thresholdCalibration = "PILOT_VALUES_NOT_NEGATIVE_CONTROL_CALIBRATED";

rollingBallRadiusPixels = 50;
medianRadiusPixels = 1;
ringDilationsPixels = 5;

// --- Output and execution ---
saveQcMips = true;
saveFullMaskStacks = false;
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

iba1CorrectedTitle = "COLOC_IBA1_CORRECTED";
cd206CorrectedTitle = "COLOC_CD206_CORRECTED";
cd86CorrectedTitle = "COLOC_CD86_CORRECTED";
iba1MaskTitle = "COLOC_IBA1_MASK";
cd206MaskTitle = "COLOC_CD206_MASK";
cd86MaskTitle = "COLOC_CD86_MASK";
analysisRoiMaskTitle = "COLOC_ANALYSIS_ROI";
iba1RingTitle = "COLOC_IBA1_RING";
iba1Cd206Title = "COLOC_IBA1_CD206";
iba1Cd86Title = "COLOC_IBA1_CD86";
tripleTitle = "COLOC_IBA1_CD206_CD86";

function findChannelTitle(titles, channelIndex) {
    prefix = "C" + channelIndex + "-";
    for (i = 0; i < titles.length; i++) {
        if (startsWith(titles[i], prefix)) return titles[i];
    }
    if (channelIndex >= 1 && channelIndex <= titles.length) {
        return titles[channelIndex - 1];
    }
    return "";
}

function failAndQuit(message) {
    print("Macro Error: COLOCALIZATION ERROR: " + message);
    run("Close All");
    run("Quit");
    exit();
}

function makeCorrectedImageAndMask(
    sourceTitle,
    correctedTitle,
    maskTitle,
    rollingRadius,
    medianRadius,
    thresholdLow,
    thresholdUpper
) {
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

function applyAnalysisRoi(maskTitle, roiMaskTitle) {
    imageCalculator("AND create stack", maskTitle, roiMaskTitle);
    resultTitle = getTitle();
    selectWindow(maskTitle);
    run("Close");
    selectWindow(resultTitle);
    rename(maskTitle);
}

function positiveVoxels(maskTitle) {
    selectWindow(maskTitle);
    Stack.getStatistics(voxelCount, meanValue, minValue, maxValue, stdDev);
    return voxelCount * meanValue / 255.0;
}

function meanInsideMask(imageTitle, maskTitle, maskPositiveVoxels) {
    if (maskPositiveVoxels <= 0) return NaN;
    imageCalculator("Multiply create 32-bit stack", imageTitle, maskTitle);
    productTitle = getTitle();
    Stack.getStatistics(voxelCount, meanValue, minValue, maxValue, stdDev);
    integratedSignal = voxelCount * meanValue / 255.0;
    selectWindow(productTitle);
    run("Close");
    return integratedSignal / maskPositiveVoxels;
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

function saveMaskOutputsAndClose(
    maskTitle,
    mipPath,
    stackPath,
    saveMip,
    saveStack
) {
    if (saveMip) saveMaskMip(maskTitle, mipPath);
    if (saveStack && stackPath != "") {
        selectWindow(maskTitle);
        saveAs("Tiff", stackPath);
    }
    selectWindow(maskTitle);
    run("Close");
}

if (batchModeEnabled) setBatchMode(true);

// --- Open and validate the source image ---
run(
    "Bio-Formats Importer",
    "open=[" + inputPath + "] "
    + "autoscale color_mode=Default view=Hyperstack stack_order=XYCZT"
);
getDimensions(imageWidth, imageHeight, channelCount, sliceCount, frameCount);

if (frameCount != 1) {
    failAndQuit("time series are not supported.");
}
if (channelCount < 3) {
    failAndQuit("expected at least three channels.");
}
if (
    iba1Channel < 1 || iba1Channel > channelCount ||
    cd206Channel < 1 || cd206Channel > channelCount ||
    cd86Channel < 1 || cd86Channel > channelCount
) {
    failAndQuit("a configured channel index is out of range.");
}
if (
    iba1Channel == cd206Channel ||
    iba1Channel == cd86Channel ||
    cd206Channel == cd86Channel
) {
    failAndQuit("Iba1, CD206, and CD86 must use different channels.");
}

run("Split Channels");
channelTitles = getList("image.titles");
iba1SourceTitle = findChannelTitle(channelTitles, iba1Channel);
cd206SourceTitle = findChannelTitle(channelTitles, cd206Channel);
cd86SourceTitle = findChannelTitle(channelTitles, cd86Channel);

if (iba1SourceTitle == "" || cd206SourceTitle == "" || cd86SourceTitle == "") {
    failAndQuit("unable to resolve one or more split channels.");
}

// --- Build an analysis ROI mask ---
// Multiple 2D ROI files are treated as a union and applied to every Z slice.
roiManager("Reset");
if (explicitRoiList != "") {
{roi_manager_open_block}
}
roiCount = roiManager("count");

selectWindow(iba1SourceTitle);
getDimensions(imageWidth, imageHeight, ignoredChannels, sliceCount, ignoredFrames);
getVoxelSize(voxelWidth, voxelHeight, voxelDepth, calibrationUnit);

if (roiCount > 0) {
    newImage(
        analysisRoiMaskTitle,
        "8-bit black",
        imageWidth,
        imageHeight,
        sliceCount
    );
    setColor(255);
    for (z = 1; z <= sliceCount; z++) {
        setSlice(z);
        for (roiIndex = 0; roiIndex < roiCount; roiIndex++) {
            roiManager("Select", roiIndex);
            run("Fill");
        }
    }
    run("Select None");
    roiMode = "MatchingROIUnion";
} else {
    newImage(
        analysisRoiMaskTitle,
        "8-bit white",
        imageWidth,
        imageHeight,
        sliceCount
    );
    roiMode = "FullImage";
}

// --- Stream channels to keep peak memory below the default 4 GB Fiji heap ---
roiVoxelCount = positiveVoxels(analysisRoiMaskTitle);

// Iba1 is processed first because its mask defines the biological compartment.
makeCorrectedImageAndMask(
    iba1SourceTitle,
    iba1CorrectedTitle,
    iba1MaskTitle,
    rollingBallRadiusPixels,
    medianRadiusPixels,
    iba1ThresholdLow,
    thresholdHigh
);
applyAnalysisRoi(iba1MaskTitle, analysisRoiMaskTitle);
iba1VoxelCount = positiveVoxels(iba1MaskTitle);
selectWindow(iba1CorrectedTitle);
run("Close");

// Build a local Iba1-negative ring before processing marker channels.
selectWindow(iba1MaskTitle);
run("Duplicate...", "title=[COLOC_IBA1_DILATED] duplicate");
setOption("BlackBackground", true);
for (i = 0; i < ringDilationsPixels; i++) {
    run("Dilate", "stack");
}
imageCalculator("XOR create stack", "COLOC_IBA1_DILATED", iba1MaskTitle);
rename(iba1RingTitle);
selectWindow("COLOC_IBA1_DILATED");
run("Close");
applyAnalysisRoi(iba1RingTitle, analysisRoiMaskTitle);
ringVoxelCount = positiveVoxels(iba1RingTitle);

// Process CD206, extract intensity metrics, then release its corrected image.
makeCorrectedImageAndMask(
    cd206SourceTitle,
    cd206CorrectedTitle,
    cd206MaskTitle,
    rollingBallRadiusPixels,
    medianRadiusPixels,
    cd206ThresholdLow,
    thresholdHigh
);
applyAnalysisRoi(cd206MaskTitle, analysisRoiMaskTitle);
cd206VoxelCount = positiveVoxels(cd206MaskTitle);
cd206MeanInIba1 = meanInsideMask(
    cd206CorrectedTitle,
    iba1MaskTitle,
    iba1VoxelCount
);
cd206MeanInRing = meanInsideMask(
    cd206CorrectedTitle,
    iba1RingTitle,
    ringVoxelCount
);
selectWindow(cd206CorrectedTitle);
run("Close");

// Process CD86 in the same way.
makeCorrectedImageAndMask(
    cd86SourceTitle,
    cd86CorrectedTitle,
    cd86MaskTitle,
    rollingBallRadiusPixels,
    medianRadiusPixels,
    cd86ThresholdLow,
    thresholdHigh
);
applyAnalysisRoi(cd86MaskTitle, analysisRoiMaskTitle);
cd86VoxelCount = positiveVoxels(cd86MaskTitle);
cd86MeanInIba1 = meanInsideMask(
    cd86CorrectedTitle,
    iba1MaskTitle,
    iba1VoxelCount
);
cd86MeanInRing = meanInsideMask(
    cd86CorrectedTitle,
    iba1RingTitle,
    ringVoxelCount
);
selectWindow(cd86CorrectedTitle);
run("Close");

cd206LocalEnrichment = safeRatio(cd206MeanInIba1, cd206MeanInRing);
cd86LocalEnrichment = safeRatio(cd86MeanInIba1, cd86MeanInRing);

selectWindow(iba1RingTitle);
run("Close");

// Close any unused split channels if the source image had more than three.
for (i = 0; i < channelTitles.length; i++) {
    if (isOpen(channelTitles[i])) {
        selectWindow(channelTitles[i]);
        run("Close");
    }
}

// --- Count overlapping voxels ---
imageCalculator("AND create stack", iba1MaskTitle, cd206MaskTitle);
rename(iba1Cd206Title);
iba1Cd206VoxelCount = positiveVoxels(iba1Cd206Title);

imageCalculator("AND create stack", iba1MaskTitle, cd86MaskTitle);
rename(iba1Cd86Title);
iba1Cd86VoxelCount = positiveVoxels(iba1Cd86Title);

imageCalculator("AND create stack", iba1Cd206Title, cd86MaskTitle);
rename(tripleTitle);
tripleVoxelCount = positiveVoxels(tripleTitle);

// Partition the Iba1-positive compartment into mutually exclusive categories.
iba1Cd206OnlyVoxelCount = iba1Cd206VoxelCount - tripleVoxelCount;
iba1Cd86OnlyVoxelCount = iba1Cd86VoxelCount - tripleVoxelCount;
iba1NoMarkerVoxelCount = (
    iba1VoxelCount -
    iba1Cd206OnlyVoxelCount -
    iba1Cd86OnlyVoxelCount -
    tripleVoxelCount
);
if (iba1NoMarkerVoxelCount < 0) iba1NoMarkerVoxelCount = 0;

// --- Derive overlap coefficients ---
iba1CoveredByCd206 = safeRatio(iba1Cd206VoxelCount, iba1VoxelCount);
cd206InsideIba1 = safeRatio(iba1Cd206VoxelCount, cd206VoxelCount);
iba1Cd206Dice = safeRatio(
    2 * iba1Cd206VoxelCount,
    iba1VoxelCount + cd206VoxelCount
);
iba1Cd206Jaccard = safeRatio(
    iba1Cd206VoxelCount,
    iba1VoxelCount + cd206VoxelCount - iba1Cd206VoxelCount
);

iba1CoveredByCd86 = safeRatio(iba1Cd86VoxelCount, iba1VoxelCount);
cd86InsideIba1 = safeRatio(iba1Cd86VoxelCount, cd86VoxelCount);
iba1Cd86Dice = safeRatio(
    2 * iba1Cd86VoxelCount,
    iba1VoxelCount + cd86VoxelCount
);
iba1Cd86Jaccard = safeRatio(
    iba1Cd86VoxelCount,
    iba1VoxelCount + cd86VoxelCount - iba1Cd86VoxelCount
);

voxelVolume = voxelWidth * voxelHeight * voxelDepth;

// --- Save QC masks ---
if (outputDir == "" || outputDir == "null" || outputDir == "/") {
    outputDir = measurementsDir;
}
if (outputDir == "" || outputDir == "null" || outputDir == "/") {
    outputDir = imageDir + "Colocalization_QC/";
}
if (!File.exists(outputDir)) File.makeDirectory(outputDir);
qcDir = outputDir + documentLabel + "_colocalization_QC/";
if (!File.exists(qcDir)) File.makeDirectory(qcDir);

saveMaskOutputsAndClose(
    analysisRoiMaskTitle,
    qcDir + documentLabel + "_analysis_ROI_MIP.tif",
    "",
    saveQcMips,
    false
);
saveMaskOutputsAndClose(
    iba1MaskTitle,
    qcDir + documentLabel + "_Iba1_mask_MIP.tif",
    qcDir + documentLabel + "_Iba1_mask_3D.tif",
    saveQcMips,
    saveFullMaskStacks
);
saveMaskOutputsAndClose(
    cd206MaskTitle,
    qcDir + documentLabel + "_CD206_mask_MIP.tif",
    qcDir + documentLabel + "_CD206_mask_3D.tif",
    saveQcMips,
    saveFullMaskStacks
);
saveMaskOutputsAndClose(
    cd86MaskTitle,
    qcDir + documentLabel + "_CD86_mask_MIP.tif",
    qcDir + documentLabel + "_CD86_mask_3D.tif",
    saveQcMips,
    saveFullMaskStacks
);
saveMaskOutputsAndClose(
    iba1Cd206Title,
    qcDir + documentLabel + "_Iba1_CD206_overlap_MIP.tif",
    "",
    saveQcMips,
    false
);
saveMaskOutputsAndClose(
    iba1Cd86Title,
    qcDir + documentLabel + "_Iba1_CD86_overlap_MIP.tif",
    "",
    saveQcMips,
    false
);
saveMaskOutputsAndClose(
    tripleTitle,
    qcDir + documentLabel + "_Iba1_CD206_CD86_overlap_MIP.tif",
    "",
    saveQcMips,
    false
);

// --- Write one result row per image ---
run("Clear Results");
row = nResults;
setResult("Document", row, documentLabel);
setResult("AnalysisDimension", row, "3D_voxels");
setResult("ROIMode", row, roiMode);
setResult("ROICount", row, roiCount);
setResult("ThresholdCalibration", row, thresholdCalibration);
setResult("Iba1Channel", row, iba1Channel);
setResult("CD206Channel", row, cd206Channel);
setResult("CD86Channel", row, cd86Channel);
setResult("Iba1ThresholdLow", row, iba1ThresholdLow);
setResult("CD206ThresholdLow", row, cd206ThresholdLow);
setResult("CD86ThresholdLow", row, cd86ThresholdLow);
setResult("RollingBallRadius_px", row, rollingBallRadiusPixels);
setResult("MedianRadius_px", row, medianRadiusPixels);
setResult("RingRadius_px", row, ringDilationsPixels);
setResult("VoxelWidth", row, voxelWidth);
setResult("VoxelHeight", row, voxelHeight);
setResult("VoxelDepth", row, voxelDepth);
setResult("CalibrationUnit", row, calibrationUnit);
setResult("VoxelVolume", row, voxelVolume);
setResult("AnalysisROI_Voxels", row, roiVoxelCount);
setResult("Iba1_Voxels", row, iba1VoxelCount);
setResult("CD206_Voxels", row, cd206VoxelCount);
setResult("CD86_Voxels", row, cd86VoxelCount);
setResult("Iba1_CD206_OverlapVoxels", row, iba1Cd206VoxelCount);
setResult("Iba1_CD86_OverlapVoxels", row, iba1Cd86VoxelCount);
setResult("Iba1_CD206_CD86_TripleVoxels", row, tripleVoxelCount);
setResult("Iba1_Volume_Calibrated3", row, iba1VoxelCount * voxelVolume);
setResult("CD206_Volume_Calibrated3", row, cd206VoxelCount * voxelVolume);
setResult("CD86_Volume_Calibrated3", row, cd86VoxelCount * voxelVolume);
setResult(
    "Iba1_CD206_OverlapVolume_Calibrated3",
    row,
    iba1Cd206VoxelCount * voxelVolume
);
setResult(
    "Iba1_CD86_OverlapVolume_Calibrated3",
    row,
    iba1Cd86VoxelCount * voxelVolume
);
setResult("Iba1_PositivePctROI", row, 100 * safeRatio(iba1VoxelCount, roiVoxelCount));
setResult("CD206_PositivePctROI", row, 100 * safeRatio(cd206VoxelCount, roiVoxelCount));
setResult("CD86_PositivePctROI", row, 100 * safeRatio(cd86VoxelCount, roiVoxelCount));
setResult("Iba1CoveredByCD206_pct", row, 100 * iba1CoveredByCd206);
setResult("CD206InsideIba1_pct", row, 100 * cd206InsideIba1);
setResult("Iba1_CD206_Dice", row, iba1Cd206Dice);
setResult("Iba1_CD206_Jaccard", row, iba1Cd206Jaccard);
setResult("Iba1CoveredByCD86_pct", row, 100 * iba1CoveredByCd86);
setResult("CD86InsideIba1_pct", row, 100 * cd86InsideIba1);
setResult("Iba1_CD86_Dice", row, iba1Cd86Dice);
setResult("Iba1_CD86_Jaccard", row, iba1Cd86Jaccard);
setResult(
    "Iba1_CD206Only_pctIba1",
    row,
    100 * safeRatio(iba1Cd206OnlyVoxelCount, iba1VoxelCount)
);
setResult(
    "Iba1_CD86Only_pctIba1",
    row,
    100 * safeRatio(iba1Cd86OnlyVoxelCount, iba1VoxelCount)
);
setResult(
    "Iba1_DoubleMarker_pctIba1",
    row,
    100 * safeRatio(tripleVoxelCount, iba1VoxelCount)
);
setResult(
    "Iba1_NoMarker_pctIba1",
    row,
    100 * safeRatio(iba1NoMarkerVoxelCount, iba1VoxelCount)
);
setResult("CD206_MeanCorrectedInIba1", row, cd206MeanInIba1);
setResult("CD206_MeanCorrectedInLocalRing", row, cd206MeanInRing);
setResult("CD206_LocalEnrichment_Iba1VsRing", row, cd206LocalEnrichment);
setResult("CD86_MeanCorrectedInIba1", row, cd86MeanInIba1);
setResult("CD86_MeanCorrectedInLocalRing", row, cd86MeanInRing);
setResult("CD86_LocalEnrichment_Iba1VsRing", row, cd86LocalEnrichment);
updateResults();

if (resultsPath == "" || resultsPath == "null") {
    if (measurementsDir == "" || measurementsDir == "null") {
        measurementsDir = imageDir;
    }
    resultsPath = measurementsDir + documentLabel + "_Iba1_CD206_CD86_colocalization.csv";
}
saveAs("Results", resultsPath);

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
