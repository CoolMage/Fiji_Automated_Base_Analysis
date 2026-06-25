// Measure the full image field in every channel without projection or ROIs.
//
// Use this macro for 2D whole-field intensity QC or simple full-image
// measurements when anatomical ROIs are not available.
// Inputs: one Bio-Formats-readable image.
// Outputs: one Results CSV with one row per channel.
// Limitations: for Z stacks this measures the active plane behavior of Fiji's
// Measure command; use measure_mip_full_image_per_channel for projection.
//
// --- Editable parameters ---
inputPath = "{img_path_fiji}";
resultsPath = "{out_csv}";
documentLabel = "{file_stem_raw}";
measurementsOptions = "area mean min max std integrated median area_fraction redirect=None decimal=3";
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

// --- Open image and split channels ---
if (batchModeEnabled) setBatchMode(true);
run("Bio-Formats Macro Extensions");
Ext.openImagePlus(inputPath);
run("Split Channels");
channelTitles = getList("image.titles");
run("Set Measurements...", measurementsOptions);
run("Select None");

// --- Measure each channel over the full image ---
for (i = 0; i < channelTitles.length; i++) {
    selectWindow(channelTitles[i]);
    channelTitle = getTitle();
    before = nResults;
    run("Measure");
    after = nResults;

    for (r = before; r < after; r++) {
        setResult("Channel", r, channelTitle);
        setResult("Document", r, documentLabel);
        setResult("Scope", r, "FullImage");
    }
    updateResults();
}

if (resultsPath == "" || resultsPath == "null") {
    print("WARN: resultsPath is empty; measurements were not written to disk.");
} else {
    saveAs("Results", resultsPath);
}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
