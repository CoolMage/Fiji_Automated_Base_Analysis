// Split a multichannel image into individual channel TIFF files.
//
// Use this macro for channel-mapping QC, manual inspection, or downstream
// workflows that need one file per channel.
// Inputs: one Bio-Formats-readable image supplied by the analysis runner.
// Outputs: one TIFF per split channel in a per-image output folder.
// Limitations: this macro preserves channel pixel data but does not perform
// projection, segmentation, or measurements.
//
// --- Editable parameters ---
inputPath = "{img_path_fiji}";
outputDir = "{output_dir_fiji_slash}{file_stem}_channels";
outputStem = "{file_stem}";
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

// --- Open image ---
if (batchModeEnabled) setBatchMode(true);
run("Bio-Formats Macro Extensions");
Ext.openImagePlus(inputPath);

// --- Split and save channels ---
if (!File.exists(outputDir)) File.makeDirectory(outputDir);
run("Split Channels");
channelTitles = getList("image.titles");

for (i = 0; i < channelTitles.length; i++) {
    selectWindow(channelTitles[i]);
    saveAs("Tiff", outputDir + "/" + outputStem + "_C" + (i + 1) + ".tif");
}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
