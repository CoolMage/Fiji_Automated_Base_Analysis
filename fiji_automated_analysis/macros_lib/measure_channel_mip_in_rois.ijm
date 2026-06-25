// Create one channel MIP and measure every loaded or matching ROI.
//
// Use this macro when the quantitative signal is in one channel and should be
// measured in anatomical ROIs after Z projection.
// Inputs: one Bio-Formats-readable multichannel stack and optional ROI files.
// Outputs: one Results CSV with ROI rows for the selected projected channel.
// Limitations: channel identity and the selected projection method must be
// fixed before batch processing.
//
// --- Editable parameters ---
inputPath = "{img_path_fiji}";
imageDir = "{img_dir_fiji_slash}";
outputDir = "{output_dir_fiji_slash}";
resultsPath = "{out_csv}";
documentLabel = "{file_stem_raw}";
normalizedDocumentLabel = "{file_stem}";
documentFilename = "{document_filename_raw}";
explicitRoiList = "{roi_paths_joined}";
targetChannelPosition = 2;
projectionMethod = "Max Intensity";
measurementsOptions = "area mean standard min max integrated median area_fraction perimeter feret shape redirect=None decimal=3";
saveMipImage = false;
mipPath = outputDir + "{file_stem}" + "_selected_channel_MIP.tif";
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

continueProcessing = true;

// --- Open image and select one channel ---
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
    channelTitle = getTitle();
    run("Z Project...", "projection=[" + projectionMethod + "]");
    projectedChannelTitle = getTitle();
    if (saveMipImage) saveAs("Tiff", mipPath);
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

// --- Measure selected channel MIP inside each ROI ---
if (continueProcessing) {
    selectWindow(projectedChannelTitle);
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
            setResult("Scope", r, "SelectedChannelROIAfterMIP");
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
