// Measure threshold-positive area over the full image field.
//
// Use this macro for signal-positive area or area-fraction measurements when
// no anatomical ROI is used.
// Inputs: one Bio-Formats-readable image and a locked threshold range.
// Outputs: one Results CSV row for the selected channel.
// Limitations: thresholds must be calibrated once per acquisition/staining
// batch and should not be tuned per image or group.
//
// --- Editable parameters ---
inputPath = "{img_path_fiji}";
resultsPath = "{out_csv}";
documentLabel = "{file_stem_raw}";
targetChannelPosition = 2;
projectBeforeMeasure = false;
projectionMethod = "Max Intensity";
thresholdLow = 500;
thresholdHigh = 65535;
measurementsOptions = "area mean standard min max integrated median area_fraction limit redirect=None decimal=3";
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

if (continueProcessing) {
    selectWindow(channelTitles[targetChannelPosition - 1]);
    if (projectBeforeMeasure) {
        run("Z Project...", "projection=[" + projectionMethod + "]");
    }
    channelTitle = getTitle();
    setThreshold(thresholdLow, thresholdHigh);
    run("Set Measurements...", measurementsOptions);
    run("Select None");

    before = nResults;
    run("Measure");
    after = nResults;

    for (r = before; r < after; r++) {
        setResult("Channel", r, channelTitle);
        setResult("Document", r, documentLabel);
        setResult("Scope", r, "ThresholdedFullImage");
        setResult("ThresholdLow", r, thresholdLow);
        setResult("ThresholdHigh", r, thresholdHigh);
    }
    updateResults();

    if (resultsPath == "" || resultsPath == "null") {
        print("WARN: resultsPath is empty; measurements were not written to disk.");
    } else {
        saveAs("Results", resultsPath);
    }
}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
