// Detect thresholded particles over the full image field and measure them.
//
// Use this macro for object or puncta analysis when no anatomical ROI is used
// and segmentation settings have been locked for the acquisition batch.
// Inputs: one Bio-Formats-readable image and fixed threshold/particle settings.
// Outputs: threshold mask TIFF, optional particle ROI zip, and particle Results CSV.
// Limitations: particle rows are object-level QC/traceability rows unless the
// biological design justifies particles as the statistical unit.
//
// --- Editable parameters ---
inputPath = "{img_path_fiji}";
outputDir = "{output_dir_fiji_slash}";
fallbackOutputDir = "{img_dir_fiji_slash}";
resultsPath = "{out_csv}";
documentLabel = "{file_stem_raw}";
outputStem = "{file_stem}";
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

    run("Duplicate...", "title=[" + outputStem + "_particle_mask]");
    maskTitle = getTitle();
    maskImageId = getImageID();
}

// --- Segment particles from the mask image ---
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
        saveAs("Tiff", outputDir + outputStem + "_particle_mask.tif");
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
    run("Clear Results");
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
            setResult("ParticleROI", r, "Particle_" + (j + 1));
            setResult("Scope", r, "DetectedParticleFullImage");
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
