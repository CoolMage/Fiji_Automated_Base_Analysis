// Create a projection and measure the full image field in every channel.
//
// Use this macro for stack-level intensity summaries when ROIs are not used and
// the biological endpoint is based on a 2D projection.
// Inputs: one Bio-Formats-readable image stack.
// Outputs: one Results CSV with one projected full-image row per channel.
// Limitations: projection collapses Z structure and should not be used for
// voxel-level overlap or 3D object counting.
//
// --- Editable parameters ---
inputPath = "{img_path_fiji}";
outputDir = "{output_dir_fiji_slash}";
resultsPath = "{out_csv}";
documentLabel = "{file_stem_raw}";
outputStem = "{file_stem}";
projectionMethod = "Max Intensity";
measurementsOptions = "area mean min max std integrated median area_fraction redirect=None decimal=3";
saveMipImage = true;
mipPath = outputDir + outputStem + "_MIP.tif";
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

// --- Open image and build MIP ---
if (batchModeEnabled) setBatchMode(true);
run("Bio-Formats Macro Extensions");
Ext.openImagePlus(inputPath);
originalTitle = getTitle();
run("Z Project...", "projection=[" + projectionMethod + "]");
projectionTitle = getTitle();
selectWindow(originalTitle);
run("Close");
selectWindow(projectionTitle);
rename(outputStem + "_MIP");

if (saveMipImage) saveAs("Tiff", mipPath);

// --- Split projected channels and measure ---
run("Split Channels");
channelTitles = getList("image.titles");
run("Set Measurements...", measurementsOptions);
run("Select None");

for (i = 0; i < channelTitles.length; i++) {
    selectWindow(channelTitles[i]);
    channelTitle = getTitle();
    before = nResults;
    run("Measure");
    after = nResults;

    for (r = before; r < after; r++) {
        setResult("Channel", r, channelTitle);
        setResult("Document", r, documentLabel);
        setResult("Scope", r, "FullImageAfterMIP");
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
