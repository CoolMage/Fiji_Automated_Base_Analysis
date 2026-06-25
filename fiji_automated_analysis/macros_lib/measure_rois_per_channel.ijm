// Measure every loaded or matching ROI in every channel.
//
// Use this macro as the basic ROI intensity/area workflow for 2D images or
// already-projected inputs.
// Inputs: one Bio-Formats-readable image and optional ROI files matched by the
// runner or by same-name ROI lookup.
// Outputs: one Results CSV with one row per channel and ROI.
// Limitations: no Z projection is applied; use measure_mip_rois_per_channel for
// 3D stacks that should be collapsed before measurement.
//
// --- Editable parameters ---
inputPath = "{img_path_fiji}";
imageDir = "{img_dir_fiji_slash}";
resultsPath = "{out_csv}";
documentLabel = "{file_stem_raw}";
normalizedDocumentLabel = "{file_stem}";
documentFilename = "{document_filename_raw}";
explicitRoiList = "{roi_paths_joined}";
measurementsOptions = "area mean standard min max integrated median area_fraction perimeter feret shape redirect=None decimal=3";
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

continueProcessing = true;

// --- Open image ---
if (batchModeEnabled) setBatchMode(true);
run("Bio-Formats Macro Extensions");
Ext.openImagePlus(inputPath);

// --- Load matching ROI files ---
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

if (continueProcessing && roiManager("count") == 0) {
    print("WARN: no ROIs loaded; measurements were not written.");
    continueProcessing = false;
}

// --- Split channels and measure every ROI in every channel ---
if (continueProcessing) {
    run("Select None");
    run("Split Channels");
    channelTitles = getList("image.titles");
    run("Set Measurements...", measurementsOptions);

    for (i = 0; i < channelTitles.length; i++) {
        selectWindow(channelTitles[i]);
        channelTitle = getTitle();
        roiCount = roiManager("count");

        for (j = 0; j < roiCount; j++) {
            roiManager("Select", j);
            roiName = call("ij.plugin.frame.RoiManager.getName", j);
            if (roiName == "" || roiName == "null") roiName = "ROI_" + (j + 1);

            before = nResults;
            run("Measure");
            after = nResults;

            for (r = before; r < after; r++) {
                setResult("Channel", r, channelTitle);
                setResult("Document", r, documentLabel);
                setResult("ROI", r, roiName);
                setResult("Scope", r, "MatchingROI");
            }
            updateResults();
        }
    }

    if (resultsPath == "" || resultsPath == "null") {
        print("WARN: resultsPath is empty; measurements were not written to disk.");
    } else {
        saveAs("Results", resultsPath);
    }
}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
