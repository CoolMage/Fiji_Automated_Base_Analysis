// Measure secondary-channel enrichment inside a primary mask versus a local ring.
//
// Use this macro when the question is whether a secondary marker is enriched
// inside or around a primary structure compared with its local neighborhood.
// Inputs: one Bio-Formats-readable multichannel stack, optional ROI files, and
// a locked primary-mask threshold.
// Outputs: one Results CSV with primary-mask mean, ring mean, enrichment ratio,
// and optional QC mask MIPs.
// Limitations: this is an intensity-enrichment measurement, not a particle
// count; the primary mask threshold and ring width must be fixed beforehand.
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
primaryLabel = "Primary";
secondaryLabel = "Secondary";
primaryThresholdLow = 500;
thresholdHigh = 65535;
thresholdCalibration = "PILOT_VALUES_NOT_CONTROL_CALIBRATED";
rollingBallRadiusPixels = 0;
medianRadiusPixels = 0;
ringDilationsPixels = 5;
saveQcMips = true;
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

primaryCorrectedTitle = "ENRICH_PRIMARY_CORRECTED";
secondaryCorrectedTitle = "ENRICH_SECONDARY_CORRECTED";
primaryMaskTitle = "ENRICH_PRIMARY_MASK";
analysisRoiMaskTitle = "ENRICH_ANALYSIS_ROI";
ringMaskTitle = "ENRICH_PRIMARY_RING";

function failAndQuit(message) {
    print("Macro Error: LOCAL_ENRICHMENT ERROR: " + message);
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

function makeCorrectedImage(sourceTitle, correctedTitle, rollingRadius, medianRadius) {
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
}

function makeMaskFromCorrected(correctedTitle, maskTitle, thresholdLow, thresholdUpper) {
    selectWindow(correctedTitle);
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

function applyAnalysisRoi(maskTitle, roiMaskTitle) {
    imageCalculator("AND create stack", maskTitle, roiMaskTitle);
    resultTitle = getTitle();
    selectWindow(maskTitle);
    run("Close");
    selectWindow(resultTitle);
    rename(maskTitle);
}

if (batchModeEnabled) setBatchMode(true);

// --- Open and validate source image ---
run("Bio-Formats Macro Extensions");
Ext.openImagePlus(inputPath);
getDimensions(imageWidth, imageHeight, channelCount, sliceCount, frameCount);

if (frameCount != 1) failAndQuit("time series are not supported.");
if (primaryChannel < 1 || primaryChannel > channelCount) failAndQuit("primaryChannel is out of range.");
if (secondaryChannel < 1 || secondaryChannel > channelCount) failAndQuit("secondaryChannel is out of range.");
if (primaryChannel == secondaryChannel) failAndQuit("primary and secondary channels must differ.");

run("Split Channels");
channelTitles = getList("image.titles");
primarySourceTitle = findChannelTitle(channelTitles, primaryChannel);
secondarySourceTitle = findChannelTitle(channelTitles, secondaryChannel);
if (primarySourceTitle == "" || secondarySourceTitle == "") failAndQuit("unable to resolve split channels.");

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

// --- Create primary mask and secondary corrected image ---
makeCorrectedImage(primarySourceTitle, primaryCorrectedTitle, rollingBallRadiusPixels, medianRadiusPixels);
makeCorrectedImage(secondarySourceTitle, secondaryCorrectedTitle, rollingBallRadiusPixels, medianRadiusPixels);
makeMaskFromCorrected(primaryCorrectedTitle, primaryMaskTitle, primaryThresholdLow, thresholdHigh);

if (roiCount > 0) {
    applyAnalysisRoi(primaryMaskTitle, analysisRoiMaskTitle);
}

// --- Create a local ring around the primary mask ---
selectWindow(primaryMaskTitle);
run("Duplicate...", "title=[" + ringMaskTitle + "] duplicate");
selectWindow(ringMaskTitle);
for (d = 0; d < ringDilationsPixels; d++) {
    run("Dilate", "stack");
}
imageCalculator("Subtract create stack", ringMaskTitle, primaryMaskTitle);
ringResultTitle = getTitle();
selectWindow(ringMaskTitle);
run("Close");
selectWindow(ringResultTitle);
rename(ringMaskTitle);
setThreshold(1, 255);
setOption("BlackBackground", true);
run("Convert to Mask", "method=Default background=Dark black");
resetThreshold();

if (roiCount > 0) {
    applyAnalysisRoi(ringMaskTitle, analysisRoiMaskTitle);
}

// --- Measure secondary intensity inside primary mask and ring ---
primaryPositive = positiveVoxels(primaryMaskTitle);
ringPositive = positiveVoxels(ringMaskTitle);
secondaryMeanInPrimary = meanInsideMask(secondaryCorrectedTitle, primaryMaskTitle, primaryPositive);
secondaryMeanInRing = meanInsideMask(secondaryCorrectedTitle, ringMaskTitle, ringPositive);
localEnrichmentRatio = safeRatio(secondaryMeanInPrimary, secondaryMeanInRing);

if (saveQcMips) {
    saveMaskMip(primaryMaskTitle, outputDir + documentLabel + "_primary_mask_mip.tif");
    saveMaskMip(ringMaskTitle, outputDir + documentLabel + "_primary_ring_mip.tif");
}

// --- Write enrichment summary ---
run("Clear Results");
row = 0;
setResult("Document", row, documentLabel);
setResult("Scope", row, "LocalEnrichmentAroundPrimaryMask");
setResult("PrimaryLabel", row, primaryLabel);
setResult("SecondaryLabel", row, secondaryLabel);
setResult("PrimaryChannel", row, primaryChannel);
setResult("SecondaryChannel", row, secondaryChannel);
setResult("PrimaryThresholdLow", row, primaryThresholdLow);
setResult("ThresholdHigh", row, thresholdHigh);
setResult("ThresholdCalibration", row, thresholdCalibration);
setResult("RingDilationsPixels", row, ringDilationsPixels);
setResult("ROI_Count", row, roiCount);
setResult("PrimaryPositiveVoxels", row, primaryPositive);
setResult("RingPositiveVoxels", row, ringPositive);
setResult("SecondaryMeanInPrimary", row, secondaryMeanInPrimary);
setResult("SecondaryMeanInRing", row, secondaryMeanInRing);
setResult("SecondaryLocalEnrichmentRatio", row, localEnrichmentRatio);
updateResults();

if (resultsPath == "" || resultsPath == "null") {
    print("WARN: resultsPath is empty; enrichment summary was not written to disk.");
} else {
    saveAs("Results", resultsPath);
}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
