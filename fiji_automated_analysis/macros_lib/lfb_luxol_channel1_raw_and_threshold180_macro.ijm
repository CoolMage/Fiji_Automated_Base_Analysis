// Measure channel 1 inside the ROI that matches the current image name,
// then repeat the measurement after applying a fixed threshold of 180..255.
//
// --- Editable parameters ---
inputPath = "{input_path}";
imageDir = "{img_dir_fiji_slash}";
outputDir = "{output_dir_fiji_slash}";
fallbackOutputDir = "{img_dir_fiji_slash}";
resultsPath = "{out_csv}";
fallbackResultsPath = "{img_dir_fiji}/" + "{file_stem}" + "_channel1_threshold180_metrics.csv";
documentLabel = "{document_name_raw}";
normalizedDocumentLabel = "{document_name}";
documentFilename = "{document_filename_raw}";
explicitRoiList = "{roi_paths_joined}";
firstChannelPrefix = "C1-";
channelLabelRaw = "C1";
channelLabelThresholded = "C1_threshold180";
measurementTypeRaw = "RawIntensity";
measurementTypeThresholded = "ThresholdedIntensity";
workingTitle = "LFB_C1_WORK";
thresholdMaskTitle = "LFB_C1_THRESHOLD180_MASK";
thresholdLow = 150;
thresholdHigh = 190;
measurementsOptions = "area mean standard modal min centroid center perimeter bounding fit shape feret's integrated median skewness kurtosis area_fraction limit display redirect=None decimal=6";
saveThresholdMask = true;
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

continueProcessing = true;
matchingRoiIndex = 0;
matchingRoiName = documentLabel;

// --- Open image ---
if (batchModeEnabled) setBatchMode(true);
run("Bio-Formats Macro Extensions");
Ext.openImagePlus(inputPath);

// --- Split channels and keep only channel 1 ---
run("Split Channels");
titles = getList("image.titles");
firstChannelTitle = "";
for (i = 0; i < titles.length; i++) {{
    if (startsWith(titles[i], firstChannelPrefix)) {{
        firstChannelTitle = titles[i];
        break;
    }}
}}
if (firstChannelTitle == "" && titles.length > 0) firstChannelTitle = titles[0];

if (firstChannelTitle == "") {{
    print("WARN: Split Channels did not produce any channel images for " + documentLabel);
    continueProcessing = false;
}}

if (continueProcessing) {{
    if (outputDir == "" || outputDir == "null" || outputDir == "/") {{
        outputDir = fallbackOutputDir;
    }}
    if (!File.exists(outputDir)) File.makeDirectory(outputDir);

    for (i = 0; i < titles.length; i++) {{
        if (titles[i] != firstChannelTitle) {{
            selectWindow(titles[i]);
            run("Close");
        }}
    }}

    selectWindow(firstChannelTitle);
    rename(workingTitle);
}}

// --- Load the ROI with the same name as the file ---
if (continueProcessing) {{
    roiManager("Reset");
    if (explicitRoiList != "") {{
    {roi_manager_open_block}
    }} else {{
        roiZipRaw = imageDir + documentLabel + ".zip";
        roiRoiRaw = imageDir + documentLabel + ".roi";
        roiZipRoiSetRaw = imageDir + "RoiSet_" + documentLabel + ".zip";
        roiZipNormalized = imageDir + normalizedDocumentLabel + ".zip";
        roiRoiNormalized = imageDir + normalizedDocumentLabel + ".roi";
        roiZipRoiSetNormalized = imageDir + "RoiSet_" + normalizedDocumentLabel + ".zip";
        roiRoiWithExtension = imageDir + documentFilename + ".roi";

        if (File.exists(roiZipRaw)) {{
            roiManager("Open", roiZipRaw);
        }} else if (File.exists(roiRoiRaw)) {{
            roiManager("Open", roiRoiRaw);
        }} else if (File.exists(roiZipRoiSetRaw)) {{
            roiManager("Open", roiZipRoiSetRaw);
        }} else if (File.exists(roiZipNormalized)) {{
            roiManager("Open", roiZipNormalized);
        }} else if (File.exists(roiRoiNormalized)) {{
            roiManager("Open", roiRoiNormalized);
        }} else if (File.exists(roiZipRoiSetNormalized)) {{
            roiManager("Open", roiZipRoiSetNormalized);
        }} else if (File.exists(roiRoiWithExtension)) {{
            roiManager("Open", roiRoiWithExtension);
        }} else {{
            print("WARN: ROI file not found for image: " + documentLabel);
            continueProcessing = false;
        }}
    }}
}}

if (continueProcessing && roiManager("count") == 0) {{
    print("WARN: No ROIs loaded; measurements were not written.");
    continueProcessing = false;
}}

if (continueProcessing) {{
    if (roiManager("count") > 1) {{
        for (i = 0; i < roiManager("count"); i++) {{
            roiName = call("ij.plugin.frame.RoiManager.getName", i);
            if (roiName == documentLabel || roiName == normalizedDocumentLabel) {{
                matchingRoiIndex = i;
                break;
            }}
        }}
    }}

    roiManager("Select", matchingRoiIndex);
    matchingRoiName = call("ij.plugin.frame.RoiManager.getName", matchingRoiIndex);
    if (matchingRoiName == "" || matchingRoiName == "null") matchingRoiName = documentLabel;
}}

// --- Measure the raw channel-1 intensity inside the ROI ---
if (continueProcessing) {{
    selectWindow(workingTitle);
    roiManager("Select", matchingRoiIndex);
    run("Clear Results");
    run("Set Measurements...", measurementsOptions);

    before = nResults;
    run("Measure");
    after = nResults;

    for (r = before; r < after; r++) {{
        setResult("Channel", r, channelLabelRaw);
        setResult("Document", r, documentLabel);
        setResult("ROI", r, matchingRoiName);
        setResult("Scope", r, "RawROI");
        setResult("MeasurementType", r, measurementTypeRaw);
    }}
    updateResults();
}}

// --- Apply threshold 180..255, convert to mask, and measure the same ROI again ---
if (continueProcessing) {{
    selectWindow(workingTitle);
    roiManager("Select", matchingRoiIndex);
    setThreshold(thresholdLow, thresholdHigh);

    // Clear the active selection before duplicating. Otherwise Fiji duplicates
    // only the ROI bounding box and the saved mask becomes cropped.
    run("Select None");

    // Build and save the threshold mask from the full-size image so the ROI
    // still applies in the original coordinate system.
    run("Duplicate...", "title=[" + thresholdMaskTitle + "]");
    selectWindow(thresholdMaskTitle);
    setThreshold(thresholdLow, thresholdHigh);
    setOption("BlackBackground", true);
    run("Convert to Mask");
    run("Convert to Mask");
    run("Grays");

    roiManager("Select", matchingRoiIndex);
    run("Set Measurements...", measurementsOptions);

    before = nResults;
    run("Measure");
    after = nResults;

    for (r = before; r < after; r++) {{
        setResult("Channel", r, channelLabelThresholded);
        setResult("Document", r, documentLabel);
        setResult("ROI", r, matchingRoiName);
        setResult("Scope", r, "ThresholdedROI");
        setResult("MeasurementType", r, measurementTypeThresholded);
        setResult("ThresholdLow", r, thresholdLow);
        setResult("ThresholdHigh", r, thresholdHigh);
    }}
    updateResults();

    if (saveThresholdMask) {{
        saveAs("Tiff", outputDir + documentLabel + "_C1_threshold180_mask.tif");
    }}
    run("Close");
    selectWindow(workingTitle);
    resetThreshold();
}}

// --- Save results ---
if (continueProcessing) {{
    if (resultsPath == "" || resultsPath == "null") resultsPath = fallbackResultsPath;
    saveAs("Results", resultsPath);
}}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
