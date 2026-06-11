// Create a per-channel kymograph TIFF for every ROI loaded for the current image.
//
// --- Editable parameters ---
inputPath = "{input_path}";
outputDir = "{output_dir_fiji}";
outputStem = "{file_stem}";
resliceOptions = "output=1.000 start=Top avoid";
loadMovieWithFfmpeg = true;
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

// --- Open image ---
if (batchModeEnabled) setBatchMode(true);
if (loadMovieWithFfmpeg && endsWith(inputPath, ".mp4")) {{
    run("Movie (FFMPEG)...", "choose=" + inputPath + " use_virtual_stack first_frame=0 last_frame=-1");
}} else {{
    run("Bio-Formats Macro Extensions");
    Ext.openImagePlus(inputPath);
}}

// --- Split channels only when needed ---
getDimensions(width, height, channels, slices, frames);
if (channels > 1) {{
    run("Split Channels");
    imgList = getList("image.titles");
}} else {{
    imgList = newArray(getTitle());
}}

// --- Load ROIs provided by the processor ---
roiManager("Reset");
{roi_manager_open_block}
roiCount = roiManager("count");
if (roiCount == 0) {{
    print("WARN: No ROIs loaded; no kymographs will be created.");
}}

// --- Ensure output directory exists ---
if (!File.exists(outputDir)) File.makeDirectory(outputDir);

// --- Reslice every ROI for every channel ---
for (i = 0; i < imgList.length; i++) {{
    selectWindow(imgList[i]);
    channelTitle = getTitle();

    for (r = 0; r < roiCount; r++) {{
        roiManager("Select", r);
        roiName = call("ij.plugin.frame.RoiManager.getName", r);
        if (roiName == "" || roiName == "null") roiName = "ROI_" + (r + 1);

        roiSafe = replace(roiName, " ", "_");
        roiSafe = replace(roiSafe, "/", "_");
        roiSafe = replace(roiSafe, "\\", "_");

        run("Reslice [/]...", resliceOptions);
        saveAs("Tiff", outputDir + "/" + outputStem + "_ch" + (i + 1) + "_" + roiSafe + "_kymo.tif");
        run("Close");
    }}

    selectWindow(channelTitle);
    run("Close");
}}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
