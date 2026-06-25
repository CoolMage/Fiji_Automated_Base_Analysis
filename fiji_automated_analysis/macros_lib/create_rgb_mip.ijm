// Create a configurable RGB/composite max-intensity projection.
//
// Use this macro for visual QC or figure-preview exports when channels should
// be mapped consistently to blue, green, and red display channels.
// Inputs: one Bio-Formats-readable multichannel image.
// Outputs: a composite MIP TIFF plus separate blue, green, and red source TIFFs.
// Limitations: this is a visualization/QC macro, not a quantitative endpoint.
//
// --- Editable parameters ---
inputPath = "{img_path_fiji}";
outputDir = "{output_dir_fiji_slash}";
fallbackOutputDir = "{img_dir_fiji_slash}";
outputStem = "{file_stem}";
projectionMethod = "Max Intensity";
sourceBlueChannel = 1;
sourceGreenChannel = 2;
sourceRedChannel = 3;
outputSuffix = "_MIP_RGB";
blueSuffix = "_MIP_Blue";
greenSuffix = "_MIP_Green";
redSuffix = "_MIP_Red";
batchModeEnabled = true;
closeAllWhenDone = true;
quitWhenDone = true;

function channelTitleByIndex(titles, channelIndex) {
    prefix = "C" + channelIndex + "-";
    for (i = 0; i < titles.length; i++) {
        if (startsWith(titles[i], prefix)) return titles[i];
    }
    if (channelIndex >= 1 && channelIndex <= titles.length) return titles[channelIndex - 1];
    return "";
}

continueProcessing = true;

// --- Open image and create projection ---
if (batchModeEnabled) setBatchMode(true);
run("Bio-Formats Macro Extensions");
Ext.openImagePlus(inputPath);
originalTitle = getTitle();
getDimensions(imageWidth, imageHeight, channelCount, sliceCount, frameCount);

if (
    sourceBlueChannel < 1 || sourceBlueChannel > channelCount ||
    sourceGreenChannel < 1 || sourceGreenChannel > channelCount ||
    sourceRedChannel < 1 || sourceRedChannel > channelCount
) {
    print("WARN: one or more configured source channels are out of range.");
    continueProcessing = false;
}

if (continueProcessing) {
    run("Z Project...", "projection=[" + projectionMethod + "]");
    projectionTitle = getTitle();
    selectWindow(originalTitle);
    run("Close");
    selectWindow(projectionTitle);
    run("Split Channels");
    channelTitles = getList("image.titles");

    blueSource = channelTitleByIndex(channelTitles, sourceBlueChannel);
    greenSource = channelTitleByIndex(channelTitles, sourceGreenChannel);
    redSource = channelTitleByIndex(channelTitles, sourceRedChannel);

    if (blueSource == "" || greenSource == "" || redSource == "") {
        print("WARN: unable to resolve one or more projected channels.");
        continueProcessing = false;
    }
}

// --- Save channels and merged composite ---
if (continueProcessing) {
    if (outputDir == "" || outputDir == "null" || outputDir == "/") outputDir = fallbackOutputDir;
    fileOutputDir = outputDir + outputStem + outputSuffix;
    if (!File.exists(fileOutputDir)) File.makeDirectory(fileOutputDir);

    selectWindow(blueSource);
    run("Blue");
    saveAs("Tiff", fileOutputDir + "/" + outputStem + blueSuffix + ".tif");
    blueSource = getTitle();

    selectWindow(greenSource);
    run("Green");
    saveAs("Tiff", fileOutputDir + "/" + outputStem + greenSuffix + ".tif");
    greenSource = getTitle();

    selectWindow(redSource);
    run("Red");
    saveAs("Tiff", fileOutputDir + "/" + outputStem + redSuffix + ".tif");
    redSource = getTitle();

    run(
        "Merge Channels...",
        "c1=[" + blueSource + "] "
        + "c2=[" + greenSource + "] "
        + "c3=[" + redSource + "] create"
    );

    Stack.setChannel(1);
    run("Blue");
    Stack.setChannel(2);
    run("Green");
    Stack.setChannel(3);
    run("Red");
    Stack.setDisplayMode("composite");
    rename(outputStem + outputSuffix);
    saveAs("Tiff", fileOutputDir + "/" + outputStem + outputSuffix + ".tif");
}

if (closeAllWhenDone) run("Close All");
if (quitWhenDone) run("Quit");
