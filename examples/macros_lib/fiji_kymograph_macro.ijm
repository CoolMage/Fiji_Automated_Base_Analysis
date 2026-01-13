// Create per-channel kymographs for each ROI
setBatchMode(true);

// 1) Open image (special-case MP4 via FFMPEG)
inputPath = "{input_path}";
if (endsWith(inputPath, ".mp4")) {{
    run("Movie (FFMPEG)...", "choose=" + inputPath + " use_virtual_stack first_frame=0 last_frame=-1");
}} else {{
    run("Bio-Formats Importer", "open=[" + inputPath + "] autoscale color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT");
}}

// 2) Split channels only if there is more than one channel
getDimensions(width, height, channels, slices, frames);
if (channels > 1) {{
    run("Split Channels");
    img_list = getList("image.titles");
}} else {{
    img_list = newArray(getTitle());
}}

// 3) Load ROIs provided by the processor
roiManager("Reset");
{roi_manager_open_block}

// Ensure output directory exists
if (!File.exists("{output_dir_fiji}")) File.makeDirectory("{output_dir_fiji}");

// 4) Reslice per channel and ROI, saving kymographs
for (i = 0; i < img_list.length; i++) {{
    selectWindow(img_list[i]);
    chTitle = getTitle();

    roiCount = roiManager("count");
    for (r = 0; r < roiCount; r++) {{
        roiManager("Select", r);
        roiName = call("ij.plugin.frame.RoiManager.getName", r);
        if (roiName=="" || roiName=="null") roiName = "ROI_" + (r+1);

        // Sanitize ROI name for file paths
        roiSafe = replace(roiName, " ", "_");
        roiSafe = replace(roiSafe, "/", "_");
        roiSafe = replace(roiSafe, "\\", "_");

        // Generate kymograph via reslice
        run("Reslice [/]...", "output=1.000 start=Top avoid");
        resTitle = getTitle();

        savePath = "{output_dir_fiji}/" + "{file_stem}" + "_ch" + (i+1) + "_" + roiSafe + "_kymo.tif";
        saveAs("Tiff", savePath);

        // Close the reslice window before the next ROI
        run("Close");
    }}

    // Close channel slice window after processing its ROIs
    selectWindow(chTitle);
    run("Close");
}}

// 5) Clean up
run("Close All");
run("Quit");
