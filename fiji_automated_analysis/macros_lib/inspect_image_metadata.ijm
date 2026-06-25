// Inspect image metadata and write one QC row for the current image.
//
// Use this macro before quantitative analysis to verify that a batch has
// compatible channel counts, Z/T dimensions, calibration, and bit depth.
// Inputs: one Bio-Formats-readable image supplied by the analysis runner.
// Outputs: a Results CSV containing dimensions, voxel calibration, bit depth,
// and whole-stack intensity statistics.
// Limitations: this macro does not validate biological channel identities.
//
// --- Editable parameters ---
inputPath = "{img_path_fiji}";
resultsPath = "{out_csv}";
documentLabel = "{file_stem_raw}";
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

// --- Open image and collect metadata ---
if (batchModeEnabled) setBatchMode(true);
run("Bio-Formats Macro Extensions");
Ext.openImagePlus(inputPath);

imageTitle = getTitle();
getDimensions(imageWidth, imageHeight, channelCount, sliceCount, frameCount);
getVoxelSize(voxelWidth, voxelHeight, voxelDepth, calibrationUnit);
imageBitDepth = bitDepth();
Stack.getStatistics(voxelCount, stackMean, stackMin, stackMax, stackStdDev);

// --- Write a single metadata row ---
run("Clear Results");
row = 0;
setResult("Document", row, documentLabel);
setResult("ImageTitle", row, imageTitle);
setResult("WidthPixels", row, imageWidth);
setResult("HeightPixels", row, imageHeight);
setResult("Channels", row, channelCount);
setResult("ZSlices", row, sliceCount);
setResult("Timepoints", row, frameCount);
setResult("BitDepth", row, imageBitDepth);
setResult("VoxelWidth", row, voxelWidth);
setResult("VoxelHeight", row, voxelHeight);
setResult("VoxelDepth", row, voxelDepth);
setResult("CalibrationUnit", row, calibrationUnit);
setResult("VoxelCount", row, voxelCount);
setResult("StackMean", row, stackMean);
setResult("StackMin", row, stackMin);
setResult("StackMax", row, stackMax);
setResult("StackStdDev", row, stackStdDev);
setResult("Scope", row, "ImageMetadata");
updateResults();

if (resultsPath == "" || resultsPath == "null") {
    print("WARN: resultsPath is empty; metadata was not written to disk.");
} else {
    saveAs("Results", resultsPath);
}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
