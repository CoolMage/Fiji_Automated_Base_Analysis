// Create one channel MIP and measure threshold-positive area inside ROIs.
//
// Use this macro for marker-positive area fraction within anatomical or
// manually drawn ROIs.
// Inputs: one Bio-Formats-readable multichannel stack, optional ROI files, and
// a locked threshold range.
// Outputs: one Results CSV with one thresholded-area row per ROI.
// Limitations: thresholds and ROI rules must be fixed before batch processing.
//
// --- Editable parameters ---
inputPath = "{img_path_fiji}";
imageDir = "{img_dir_fiji_slash}";
resultsPath = "{out_csv}";
documentLabel = "{file_stem_raw}";
normalizedDocumentLabel = "{file_stem}";
documentFilename = "{document_filename_raw}";
explicitRoiList = "{roi_paths_joined}";
targetChannelPosition = 2;
projectionMethod = "Max Intensity";
thresholdLow = 500;
thresholdHigh = 65535;
measurementsOptions = "area mean standard min max integrated median area_fraction limit redirect=None decimal=3";
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

continueProcessing = true;

// --- Open image and select projected channel ---
if (batchModeEnabled) setBatchMode(true);
run("Bio-Formats Macro Extensions");
Ext.openImagePlus(inputPath);
run("Split Channels");
channelTitles = getList("image.titles");

if (channelTitles.length < targetChannelPosition) {
    print("WARN: requested channel index is out of range.");
    continueProcessing = false;
}

if (continueProcessing) {
    selectWindow(channelTitles[targetChannelPosition - 1]);
    run("Z Project...", "projection=[" + projectionMethod + "]");
    projectedChannelTitle = getTitle();
}

// --- Load matching ROI files ---
if (continueProcessing) {
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
        } else {
            print("WARN: ROI file not found for image: " + documentLabel);
            continueProcessing = false;
        }
    }
}

if (continueProcessing && roiManager("count") == 0) {
    print("WARN: no ROIs loaded; measurements were not written.");
    continueProcessing = false;
}

// --- Measure thresholded area in every ROI ---
if (continueProcessing) {
    selectWindow(projectedChannelTitle);
    setThreshold(thresholdLow, thresholdHigh);
    run("Set Measurements...", measurementsOptions);
    roiCount = roiManager("count");

    for (j = 0; j < roiCount; j++) {
        roiManager("Select", j);
        roiName = call("ij.plugin.frame.RoiManager.getName", j);
        if (roiName == "" || roiName == "null") roiName = "ROI_" + (j + 1);

        before = nResults;
        run("Measure");
        after = nResults;

        for (r = before; r < after; r++) {
            setResult("Channel", r, projectedChannelTitle);
            setResult("Document", r, documentLabel);
            setResult("ROI", r, roiName);
            setResult("Scope", r, "ThresholdedROIAfterMIP");
            setResult("ThresholdLow", r, thresholdLow);
            setResult("ThresholdHigh", r, thresholdHigh);
        }
        updateResults();
    }

    if (resultsPath == "" || resultsPath == "null") {
        print("WARN: resultsPath is empty; measurements were not written to disk.");
    } else {
        saveAs("Results", resultsPath);
    }
}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
