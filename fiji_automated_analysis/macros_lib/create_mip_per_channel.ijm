// Create a max-intensity projection for every channel and save each channel.
//
// Use this macro for 3D stacks when downstream review or analysis should use
// a 2D projection for each channel.
// Inputs: one Bio-Formats-readable image with one or more channels.
// Outputs: one projected channel TIFF per channel.
// Limitations: projection collapses Z information and is not suitable when
// object counts or voxel-level overlap must remain 3D.
//
// --- Editable parameters ---
inputPath = "{img_path_fiji}";
outputDir = "{output_dir_fiji_slash}{file_stem}_mip_channels";
outputStem = "{file_stem}";
projectionMethod = "Max Intensity";
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

// --- Open image and project Z ---
if (batchModeEnabled) setBatchMode(true);
run("Bio-Formats Macro Extensions");
Ext.openImagePlus(inputPath);
originalTitle = getTitle();
run("Z Project...", "projection=[" + projectionMethod + "]");
projectionTitle = getTitle();

selectWindow(originalTitle);
run("Close");
selectWindow(projectionTitle);

// --- Split projected channels and save ---
if (!File.exists(outputDir)) File.makeDirectory(outputDir);
run("Split Channels");
channelTitles = getList("image.titles");

for (i = 0; i < channelTitles.length; i++) {
    selectWindow(channelTitles[i]);
    saveAs("Tiff", outputDir + "/" + outputStem + "_MIP_C" + (i + 1) + ".tif");
}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
