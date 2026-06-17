// Measure the red LFB channel inside the loaded ROIs using a configurable threshold range.
//
// --- Editable parameters ---
inputPath = "{input_path}";
resultsPath = "{out_csv}";
fallbackResultsPath = "{img_dir_fiji}/" + "{file_stem}" + "_lfb_metrics.csv";
documentLabel = "{file_stem_raw}";
redChannelPrefix = "C1-";
workingTitle = "LFB_RED";
thresholdLow = 185;
thresholdHigh = 255;
createFullImageRoiWhenMissing = true;
measurementsOptions = "area mean standard modal min centroid center perimeter bounding fit shape feret's integrated median skewness kurtosis area_fraction limit display redirect=None decimal=6";
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

// --- Open image ---
if (batchModeEnabled) setBatchMode(true);
run("Bio-Formats Macro Extensions");
Ext.openImagePlus(inputPath);

// --- Split channels and keep the red channel ---
run("Split Channels");
titles = getList("image.titles");
redTitle = "";
for (i = 0; i < titles.length; i++) {{
    if (startsWith(titles[i], redChannelPrefix)) {{
        redTitle = titles[i];
        break;
    }}
}}
if (redTitle == "") redTitle = titles[0];

for (i = 0; i < titles.length; i++) {{
    if (titles[i] != redTitle) {{
        selectWindow(titles[i]);
        run("Close");
    }}
}}

selectWindow(redTitle);
rename(workingTitle);
run("8-bit");
run("Invert");
setThreshold(thresholdLow, thresholdHigh);

// --- Load ROIs, or fall back to the full image ---
roiManager("Reset");
{roi_manager_open_block}
roiCount = roiManager("count");
if (roiCount == 0 && createFullImageRoiWhenMissing) {{
    getDimensions(w, h, c, s, f);
    makeRectangle(0, 0, w, h);
    roiManager("Add");
    roiCount = 1;
}}

// --- Measure every ROI ---
run("Set Measurements...", measurementsOptions);
for (r = 0; r < roiCount; r++) {{
    roiManager("Select", r);
    roiName = call("ij.plugin.frame.RoiManager.getName", r);
    if (roiName == "" || roiName == "null") roiName = "ROI_" + (r + 1);

    before = nResults;
    run("Measure");
    after = nResults;
    for (k = before; k < after; k++) {{
        setResult("Document", k, documentLabel);
        setResult("ROI", k, roiName);
        setResult("ThresholdLow", k, thresholdLow);
        setResult("ThresholdHigh", k, thresholdHigh);
    }}
    updateResults();
}}

// --- Save results ---
if (resultsPath == "" || resultsPath == "null") resultsPath = fallbackResultsPath;
saveAs("Results", resultsPath);

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
