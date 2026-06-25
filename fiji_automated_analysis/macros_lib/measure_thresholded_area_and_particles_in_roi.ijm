// Measure thresholded ROI area and detected particles in one workflow.
//
// Use this macro for a complete segmentation workflow: selected-channel MIP,
// parent ROI area fraction, cropped/cleared QC image, threshold mask, particle
// ROI export, and particle measurements.
// Inputs: one Bio-Formats-readable multichannel stack, optional matching ROI
// files, and fixed threshold/particle settings.
// Outputs: an area-fraction CSV, particle measurement CSV, cropped MIP TIFF,
// threshold mask TIFF, and optional particle ROI zip.
// Limitations: by default the first ROI is used; thresholds and ROI selection
// must be locked before batch processing.
//
// --- Editable parameters ---
inputPath = "{img_path_fiji}";
imageDir = "{img_dir_fiji_slash}";
outputDir = "{output_dir_fiji_slash}";
measurementsDir = "{measurements_dir_fiji_slash}";
resultsPath = "{out_csv}";
documentLabel = "{file_stem_raw}";
normalizedDocumentLabel = "{file_stem}";
documentFilename = "{document_filename_raw}";
explicitRoiList = "{roi_paths_joined}";
outputStem = "{file_stem}";
areaFractionResultsPath = measurementsDir + outputStem + "_area_fraction.csv";
particleResultsPath = resultsPath;
particleRoiZipPath = outputDir + "RoiSet_" + outputStem + "_particles.zip";
matchingRoiIndex = 0;
targetChannelPosition = 2;
projectionMethod = "Max Intensity";
rollingBallRadiusPixels = 0;
blurSigma = 2;
thresholdLow = 500;
thresholdHigh = 65535;
particleSize = "25-Infinity";
particleCircularity = "0.00-1.00";
areaMeasurementsOptions = "area area_fraction limit redirect=None decimal=3";
particleMeasurementsOptions = "area mean standard min max integrated median perimeter feret shape redirect=None decimal=3";
saveCroppedMip = true;
saveThresholdMask = true;
saveParticleRois = true;
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

continueProcessing = true;
matchingRoiName = documentLabel;

// --- Open image and build selected-channel MIP ---
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
    selectWindow(channelTitles[targetChannelPosition - 1]);
    sourceChannelTitle = getTitle();
    run("Z Project...", "projection=[" + projectionMethod + "]");
    projectedTitle = getTitle();
    projectedImageId = getImageID();
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
    print("WARN: no ROIs loaded; measurements were not written.");
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

// --- Measure threshold-positive area in the parent ROI ---
if (continueProcessing) {
    selectImage(projectedImageId);
    roiManager("Select", matchingRoiIndex);
    setThreshold(thresholdLow, thresholdHigh);
    run("Set Measurements...", areaMeasurementsOptions);
    run("Clear Results");

    before = nResults;
    run("Measure");
    after = nResults;

    for (r = before; r < after; r++) {
        setResult("Channel", r, projectedTitle);
        setResult("Document", r, documentLabel);
        setResult("ROI", r, matchingRoiName);
        setResult("Scope", r, "ThresholdedAreaFraction");
        setResult("ThresholdLow", r, thresholdLow);
        setResult("ThresholdHigh", r, thresholdHigh);
    }
    updateResults();
    saveAs("Results", areaFractionResultsPath);
    resetThreshold();
}

// --- Create cropped/cleared working image and threshold mask ---
if (continueProcessing) {
    selectImage(projectedImageId);
    roiManager("Select", matchingRoiIndex);
    run("Duplicate...", "title=[" + outputStem + "_selected_channel_MIP_cropped]");
    croppedTitle = getTitle();
    croppedImageId = getImageID();

    if (selectionType() == -1) run("Restore Selection");
    if (selectionType() != -1) {
        setBackgroundColor(0, 0, 0);
        run("Clear Outside");
    } else {
        print("WARN: ROI selection was not preserved on the cropped image.");
        continueProcessing = false;
    }

    if (continueProcessing && saveCroppedMip) {
        saveAs("Tiff", outputDir + outputStem + "_selected_channel_MIP_cropped.tif");
    }
}

if (continueProcessing) {
    selectImage(croppedImageId);
    run("Duplicate...", "title=[" + outputStem + "_threshold_mask]");
    maskTitle = getTitle();
    maskImageId = getImageID();

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
        saveAs("Tiff", outputDir + outputStem + "_threshold_mask.tif");
    }

    roiManager("Reset");
    run("Analyze Particles...", "size=" + particleSize + " circularity=" + particleCircularity + " show=Nothing add");
    particleCount = roiManager("count");

    if (saveParticleRois && particleCount > 0) {
        roiManager("Select All");
        roiManager("Save", particleRoiZipPath);
    }
}

// --- Measure every detected particle on the cropped source image ---
if (continueProcessing) {
    if (particleResultsPath == "" || particleResultsPath == "null") {
        particleResultsPath = measurementsDir + outputStem + "_particle_measurements.csv";
    }

    run("Clear Results");
    selectImage(croppedImageId);
    run("Set Measurements...", particleMeasurementsOptions);

    for (j = 0; j < particleCount; j++) {
        roiManager("Select", j);
        before = nResults;
        run("Measure");
        after = nResults;

        for (r = before; r < after; r++) {
            setResult("Channel", r, croppedTitle);
            setResult("Document", r, documentLabel);
            setResult("ParentROI", r, matchingRoiName);
            setResult("ParticleROI", r, "Particle_" + (j + 1));
            setResult("Scope", r, "DetectedParticle");
            setResult("ThresholdLow", r, thresholdLow);
            setResult("ThresholdHigh", r, thresholdHigh);
        }
        updateResults();
    }
    saveAs("Results", particleResultsPath);
}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
