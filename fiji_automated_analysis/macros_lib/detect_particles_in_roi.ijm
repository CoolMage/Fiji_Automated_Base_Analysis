// Detect thresholded particles inside one matching ROI and measure them.
//
// Use this macro when objects should only be detected inside a tissue,
// anatomical, or manually drawn parent ROI.
// Inputs: one Bio-Formats-readable image, optional matching ROI files, and
// fixed threshold/particle settings.
// Outputs: parent ROI row, threshold mask TIFF, optional particle ROI zip, and
// particle Results CSV.
// Limitations: by default the first ROI is used; change matchingRoiIndex when a
// multi-ROI file contains several compartments.
//
// --- Editable parameters ---
inputPath = "{img_path_fiji}";
imageDir = "{img_dir_fiji_slash}";
outputDir = "{output_dir_fiji_slash}";
fallbackOutputDir = "{img_dir_fiji_slash}";
resultsPath = "{out_csv}";
documentLabel = "{file_stem_raw}";
normalizedDocumentLabel = "{file_stem}";
documentFilename = "{document_filename_raw}";
explicitRoiList = "{roi_paths_joined}";
outputStem = "{file_stem}";
matchingRoiIndex = 0;
targetChannelPosition = 2;
projectBeforeDetection = true;
projectionMethod = "Max Intensity";
rollingBallRadiusPixels = 0;
blurSigma = 2;
thresholdLow = 500;
thresholdHigh = 65535;
particleSize = "25-Infinity";
particleCircularity = "0.00-1.00";
measurementsOptions = "area mean standard min max integrated median perimeter feret shape redirect=None decimal=3";
saveThresholdMask = true;
saveParticleRois = true;
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

continueProcessing = true;
matchingRoiName = documentLabel;

// --- Open image and select the source channel ---
if (batchModeEnabled) setBatchMode(true);
run("Bio-Formats Macro Extensions");
Ext.openImagePlus(inputPath);
run("Split Channels");
channelTitles = getList("image.titles");

if (channelTitles.length < targetChannelPosition) {
    print("WARN: requested channel index is out of range.");
    continueProcessing = false;
}

if (continueProcessing) {
    if (outputDir == "" || outputDir == "null" || outputDir == "/") outputDir = fallbackOutputDir;
    if (!File.exists(outputDir)) File.makeDirectory(outputDir);

    selectWindow(channelTitles[targetChannelPosition - 1]);
    if (projectBeforeDetection) run("Z Project...", "projection=[" + projectionMethod + "]");
    sourceTitle = getTitle();
    sourceImageId = getImageID();

    run("Duplicate...", "title=[" + outputStem + "_roi_particle_mask]");
    maskTitle = getTitle();
    maskImageId = getImageID();
}

// --- Load parent ROI ---
if (continueProcessing) {
    roiManager("Reset");
    if (explicitRoiList != "") {
{roi_manager_open_block}
    } else {
        roiZipRaw = imageDir + documentLabel + ".zip";
        roiRoiRaw = imageDir + documentLabel + ".roi";
        roiZipRoiSetRaw = imageDir + "RoiSet_" + documentLabel + ".zip";
        roiZipNormalized = imageDir + normalizedDocumentLabel + ".zip";
        roiRoiNormalized = imageDir + normalizedDocumentLabel + ".roi";
        roiZipRoiSetNormalized = imageDir + "RoiSet_" + normalizedDocumentLabel + ".zip";
        roiRoiWithExtension = imageDir + documentFilename + ".roi";

        if (File.exists(roiZipRaw)) {
            roiManager("Open", roiZipRaw);
        } else if (File.exists(roiRoiRaw)) {
            roiManager("Open", roiRoiRaw);
        } else if (File.exists(roiZipRoiSetRaw)) {
            roiManager("Open", roiZipRoiSetRaw);
        } else if (File.exists(roiZipNormalized)) {
            roiManager("Open", roiZipNormalized);
        } else if (File.exists(roiRoiNormalized)) {
            roiManager("Open", roiRoiNormalized);
        } else if (File.exists(roiZipRoiSetNormalized)) {
            roiManager("Open", roiZipRoiSetNormalized);
        } else if (File.exists(roiRoiWithExtension)) {
            roiManager("Open", roiRoiWithExtension);
        } else {
            print("WARN: ROI file not found for image: " + documentLabel);
            continueProcessing = false;
        }
    }
}

if (continueProcessing && roiManager("count") == 0) {
    print("WARN: no ROIs loaded; particle analysis was skipped.");
    continueProcessing = false;
}
if (continueProcessing && matchingRoiIndex >= roiManager("count")) {
    print("WARN: matchingRoiIndex is out of range.");
    continueProcessing = false;
}

if (continueProcessing) {
    matchingRoiName = call("ij.plugin.frame.RoiManager.getName", matchingRoiIndex);
    if (matchingRoiName == "" || matchingRoiName == "null") matchingRoiName = documentLabel;
}

// --- Measure parent ROI and restrict mask to the parent ROI ---
if (continueProcessing) {
    run("Clear Results");
    selectImage(sourceImageId);
    roiManager("Select", matchingRoiIndex);
    run("Set Measurements...", measurementsOptions);
    before = nResults;
    run("Measure");
    after = nResults;
    for (r = before; r < after; r++) {
        setResult("Channel", r, sourceTitle);
        setResult("Document", r, documentLabel);
        setResult("ROI", r, matchingRoiName);
        setResult("Scope", r, "ParentROI");
    }

    selectImage(maskImageId);
    roiManager("Select", matchingRoiIndex);
    setBackgroundColor(0, 0, 0);
    run("Clear Outside");
}

// --- Segment particles inside the restricted mask ---
if (continueProcessing) {
    selectImage(maskImageId);
    if (rollingBallRadiusPixels > 0) {
        run("Subtract Background...", "rolling=" + rollingBallRadiusPixels);
    }
    if (blurSigma > 0) {
        run("Gaussian Blur...", "sigma=" + blurSigma);
    }
    setThreshold(thresholdLow, thresholdHigh);
    setOption("BlackBackground", false);
    run("Convert to Mask");
    run("Grays");

    if (saveThresholdMask) {
        saveAs("Tiff", outputDir + outputStem + "_roi_particle_mask.tif");
    }

    roiManager("Reset");
    run("Analyze Particles...", "size=" + particleSize + " circularity=" + particleCircularity + " show=Nothing add");
    particleCount = roiManager("count");

    if (saveParticleRois && particleCount > 0) {
        roiManager("Select All");
        roiManager("Save", outputDir + "RoiSet_" + outputStem + "_particles.zip");
    }
}

// --- Measure detected particles on the source channel ---
if (continueProcessing) {
    selectImage(sourceImageId);
    run("Set Measurements...", measurementsOptions);

    for (j = 0; j < particleCount; j++) {
        roiManager("Select", j);
        before = nResults;
        run("Measure");
        after = nResults;

        for (r = before; r < after; r++) {
            setResult("Channel", r, sourceTitle);
            setResult("Document", r, documentLabel);
            setResult("ParentROI", r, matchingRoiName);
            setResult("ParticleROI", r, "Particle_" + (j + 1));
            setResult("Scope", r, "DetectedParticleInROI");
            setResult("ThresholdLow", r, thresholdLow);
            setResult("ThresholdHigh", r, thresholdHigh);
        }
        updateResults();
    }

    if (resultsPath == "" || resultsPath == "null") {
        print("WARN: resultsPath is empty; particle measurements were not written to disk.");
    } else {
        saveAs("Results", resultsPath);
    }
}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
