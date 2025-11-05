
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
    if (!File.exists("{output_dir_native}/{custom_name}")) File.makeDirectory("{output_dir_native}/{custom_name}");
    saveAs("Tiff", "{output_dir_native}/{custom_name}/" + "{file_stem}" + "_ch" + (i+1) + ".tif");
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
saveAs("Tiff", "{output_dir_native}/{file_stem}_MIP");

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
''',

    "all_image_analise_particule_one_channle" : '''
// --- Open & keep only Ch1 + Z1 via duplication ---
run("Bio-Formats Importer", "open=[{img_path_fiji}] autoscale color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT");
origTitle = getTitle();

// дублируем строго 1-й канал, 1-й Z-срез, 1-й кадр
dupTitle = "{document_name}_ch1z1";
run("Duplicate...", "title=["+dupTitle+"] duplicate channels=1 slices=1-1 frames=1-1");
selectWindow(dupTitle);

// (опционально) закрыть исходник, чтобы не мешал
selectWindow(origTitle);
close();
selectWindow(dupTitle);

// --- Threshold: min = 1000, max = максимум изображения ---
getRawStatistics(nPixels, mean, minVal, maxVal);
minThr = 1000;
if (maxVal < minThr) minThr = maxVal; // на случай 8-bit/аномалий
setThreshold(minThr, maxVal);
setOption("BlackBackground", false);
run("Convert to Mask");  // делаем бинарную маску из порога

// --- Analyze Particles (size 50–500 px²) + сохранить ROIs ---
run("Set Measurements...", "area mean min max std integrated centroid feret's redirect=None decimal=3");
roiManager("Reset");
run("Analyze Particles...", "size=50-500 clear add");

// --- Save results table to CSV ---
saveAs("Results", "{out_csv}");

// --- Save ROIs as ZIP (имя документа + пометка) ---
roiZip = "{img_dir_fiji_slash}{document_name}_ch1z1_thr1000_part50-500_ROIs.zip";
roiManager("Save", roiZip);

// --- Cleanup ---
run("Close All");
run("Quit");

''',

    "all_image_analise_particule_one_channle" : '''
// --- Open & keep only Ch1 + Z1 via duplication ---
run("Bio-Formats Importer", "open=[{img_path_fiji}] autoscale color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT");
origTitle = getTitle();

// дублируем строго 2-й канал, 2-й Z-срез, 2-й кадр
dupTitle = "{document_name}_ch2z2";
run("Duplicate...", "title=["+dupTitle+"] duplicate channels=2 slices=2");
selectWindow(dupTitle);

// (опционально) закрыть исходник, чтобы не мешал
selectWindow(origTitle);
close();
selectWindow(dupTitle);

// --- Threshold ---
getRawStatistics(nPixels, mean, minVal, maxVal);
minThr = 1350;
if (maxVal < minThr) minThr = maxVal; // на случай 8-bit/аномалий
setThreshold(minThr, maxVal);
setOption("BlackBackground", false);
run("Convert to Mask");  // делаем бинарную маску из порога

saveAs("Tiff", "{output_dir_native}/{document_name}_ch2z2_thr1350");

// --- Analyze Particles + сохранить ROIs ---
run("Set Measurements...", "area mean min max std integrated centroid feret's redirect=None decimal=3");
roiManager("Reset");
run("Analyze Particles...", "size=25-1200 circularity=0.30-1.00 clear include add");

// --- Save results table to CSV ---
saveAs("Results", "{out_csv}");

// --- Save ROIs as ZIP (имя документа + пометка) ---
roiZip = "{output_dir_native}/{document_name}_ch2z2_thr400_part15-750_ROIs.zip";
roiManager("Save", roiZip);

// --- Cleanup ---
run("Close All");
run("Quit");

''',

    "AllImgae_AP_OneChannle2_CLAHE_WithRoi" : '''
// --- Open & keep only Ch1 + Z1 via duplication ---
run("Bio-Formats Importer", "open=[{img_path_fiji}] autoscale color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT");
origTitle = getTitle();

// дублируем строго 2-й канал, 2-й Z-срез, 2-й кадр
dupTitle = "{document_name}_ch2z2";
run("Duplicate...", "title=["+dupTitle+"] duplicate channels=2 slices=2");
selectWindow(dupTitle);

// (опционально) закрыть исходник, чтобы не мешал
selectWindow(origTitle);
close();
selectWindow(dupTitle);

// --- Make a MIP ---
origTitle = getTitle();
run("Z Project...", "projection=[Max Intensity]");
selectWindow(origTitle); run("Close");
rename("{file_stem}_MIP");

// --- Enhance Local Contrast (CLAHE) ---

run("Enhance Local Contrast (CLAHE)", "blocksize=127 histogram=256 maximum=3 mask=*None* fast_(less_accurate)");

// --- Threshold ---
getRawStatistics(nPixels, mean, minVal, maxVal);
minThr = 1350;
if (maxVal < minThr) minThr = maxVal; // на случай 8-bit/аномалий
setThreshold(minThr, maxVal);
setOption("BlackBackground", false);
run("Convert to Mask");  // делаем бинарную маску из порога

saveAs("Tiff", "{output_dir_native}/{document_name}_ch2z2_thr1350_CLAHE");

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


// --- Analyze Particles + сохранить ROIs ---
run("Set Measurements...", "area mean min max std integrated centroid feret's redirect=None decimal=3");
roiManager("Reset");
run("Analyze Particles...", "size=25-1200 circularity=0.30-1.00 clear include add");

// --- Save results table to CSV ---
saveAs("Results", "{out_csv}");

// --- Save ROIs as ZIP (имя документа + пометка) ---
roiZip = "{output_dir_native}/{document_name}_ch2z2_thr1350_part25-1200_CLAHE_ROIs.zip";
roiManager("Save", roiZip);

// --- Cleanup ---
run("Close All");
run("Quit");

''',
}
