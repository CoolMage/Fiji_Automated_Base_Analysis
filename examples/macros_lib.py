
MACROS_LIB = {
    "Split_Channels_in_dif_dir" : '''
// --- Open & prepare (Bio-Formats + Z-MIP) ---
setBatchMode(true);
run("Bio-Formats Importer", "open=[{img_path_fiji}] autoscale color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT");

// --- Split and loop channels ---
run("Split Channels");
img_list = getList("image.titles");

for (i = 0; i < img_list.length; i++) {{
    selectWindow(img_list[i]);
    chTitle = getTitle();
    if (!File.exists("{output_dir_fiji_slash}{file_stem}")) File.makeDirectory("{output_dir_fiji_slash}{file_stem}");
    saveAs("Tiff", "{output_dir_fiji_slash}{file_stem}/" + "{file_stem}" + "_ch" + (i+1) + ".tif");
}}

run("Close All");
run("Quit");
''',

    "mip_all_image_measure_for_channel" : '''
// --- Open & prepare (Bio-Formats + Z-MIP) ---
setBatchMode(true);
run("Bio-Formats Importer", "open=[{img_path_fiji}] autoscale color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT");
origTitle = getTitle();
run("Z Project...", "projection=[Max Intensity]");
selectWindow(origTitle); run("Close");
rename("{file_stem}_MIP");
saveAs("Tiff", "{output_dir_fiji_slash}{file_stem}_MIP");

// --- Split and loop channels ---
run("Split Channels");
img_list = getList("image.titles");
run("Set Measurements...", "area mean min max std integrated redirect=None decimal=3");
run("Select None");

for (i = 0; i < img_list.length; i++) {{
    selectWindow(img_list[i]);
    chTitle = getTitle();
    before = nResults;
    run("Measure");
    after = nResults;
    for (r = before; r < after; r++) {{
        setResult("Channel", r, chTitle);
        setResult("Document", r, "{document_name}");
    }}
    updateResults();
}}

saveAs("Results", "{out_csv}");
run("Close All");
run("Quit");
''',

    "all_image_measure_for_channel" : '''
// --- Open & prepare (Bio-Formats + Z-MIP) ---
setBatchMode(true);
run("Bio-Formats Importer", "open=[{img_path_fiji}] autoscale color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT");

// --- Split and loop channels ---
run("Split Channels");
img_list = getList("image.titles");
run("Set Measurements...", "area mean min max std integrated redirect=None decimal=3");
roiManager("Reset");
roiManager("Open", {document_name}.roi);
run("Select None");

for (i = 0; i < img_list.length; i++) {{
    selectWindow(img_list[i]);
    chTitle = getTitle();
    before = nResults;
    run("Measure");
    after = nResults;
    for (r = before; r < after; r++) {{
        setResult("Channel", r, chTitle);
        setResult("Document", r, "{document_name}");
    }}
    updateResults();
}}

saveAs("Results", "{out_csv}");
run("Close All");
run("Quit");
''',


    "mip_roi_measure_AllChannels" : '''
// --- Open & prepare (Bio-Formats + Z-MIP) ---
setBatchMode(true);
run("Bio-Formats Importer", "open=[{img_path_fiji}] autoscale color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT");
origTitle = getTitle();
run("Z Project...", "projection=[Max Intensity]");
selectWindow(origTitle); run("Close");
rename("{file_stem}_MIP");

// --- Load ROIs once ---
roiManager("Reset");
roiZip = "{img_dir_fiji_slash}{document_name}.zip";
roiRoi = "{img_dir_fiji_slash}{document_name}.roi";
if (File.exists(roiZip)) {{
    roiManager("Open", roiZip);
}} else if (File.exists(roiRoi)) {{
    roiManager("Open", roiRoi);
}} else {{
    print("WARN: ROI file not found: " + roiZip + " or " + roiRoi);
    run("Close All");
    run("Quit");
}}
run("Select None");


// --- Split and loop channels ---
run("Split Channels");
img_list = getList("image.titles");

// --- Set Measurements ---
run("Set Measurements...", "area mean standard min integrated median area_fraction redirect=None decimal=3");

for (i = 0; i < img_list.length; i++) {{
    selectWindow(img_list[i]);
    chTitle = getTitle();

    // --- measure each ROI separately, store ROI name ---
    n = roiManager("count");
    for (j = 0; j < n; j++) {{
        roiManager("Select", j);
        roiName = call("ij.plugin.frame.RoiManager.getName", j);
        if (roiName=="" || roiName=="null") roiName = "ROI_" + (j+1);

        before = nResults;
        run("Measure");
        after = nResults;

        for (r = before; r < after; r++) {{
            setResult("Channel", r, chTitle);
            setResult("Document", r, "{document_name}");
            setResult("ROI", r, roiName);
            setResult("Scope", r, "ROI");
        }}
    }}

    updateResults();
}}

saveAs("Results", "{out_csv}");
run("Close All");
run("Quit");
'''
}
