# Iba1/CD206/CD86 3D co-occurrence protocol

## Scope

This macro quantifies spatial co-occurrence of thresholded Iba1 signal with
CD206 and CD86 in a three-channel Z-stack. It reports image-level voxel
fractions and local marker enrichment. It does **not** report the fraction of
individual cells expressing a marker because this dataset has no nuclear
channel and Iba1-positive processes cannot be reliably separated into cells at
20x.

## Channel mapping

The supplied files are named `Iba1_CD206_CD86_...` and contain:

- C1: 488/529 nm, default `Iba1`
- C2: 561/600 nm, default `CD206`
- C3: 638/700 nm, default `CD86`

The `.ims` metadata names channels only by color, not antibody. Confirm this
mapping from the acquisition protocol or single-stain controls before running
the batch. Edit `iba1Channel`, `cd206Channel`, and `cd86Channel` if needed.

## Analysis design

1. Open the complete stack through Bio-Formats.
2. Apply an optional matching anatomical ROI to all Z slices. Multiple ROIs are
   treated as a union. Without an ROI, the full image is analyzed and
   `ROIMode=FullImage` is written to the CSV.
3. For each channel, subtract rolling-ball background (`50 px`, about `30.5 um`
   for these images), clamp negative values to zero, and apply a `1 px` median
   filter.
4. Apply fixed channel-specific thresholds and create 3D binary masks.
5. Compute Iba1/CD206, Iba1/CD86, and triple-positive voxel intersections.
6. Measure corrected CD206 and CD86 intensity inside the Iba1 mask and in a
   five-pixel Iba1-negative ring.
7. Save one CSV row and QC MIPs of all masks and intersections.

Measurements are performed in 3D. MIPs are output only for visual QC and are
not used to calculate overlap.

## Threshold calibration

The bundled values (`1600`, `2200`, and `1800` after preprocessing) are pilot
values selected from the supplied 2025-05-19 series. They are intentionally
tagged in every CSV as
`PILOT_VALUES_NOT_NEGATIVE_CONTROL_CALIBRATED`.

Before inferential analysis:

1. Use unstained, secondary-only, and single-stain controls acquired with the
   same exposure, gain, objective, pixel size, and Z step.
2. Verify channel bleed-through and acquisition order.
3. Apply the same preprocessing used by the macro.
4. Choose thresholds that exclude negative-control signal while retaining
   visually confirmed positive structures.
5. Lock one threshold per channel for the complete staining/acquisition batch.
6. Replace the three threshold constants and change
   `thresholdCalibration` to a traceable calibration identifier.
7. Inspect the saved QC masks blind to animal/group and reject failed
   segmentation using predefined criteria.

Do not optimize thresholds separately for each image or experimental group.

## Primary output metrics

- `Iba1CoveredByCD206_pct`: fraction of Iba1-positive voxels also CD206-positive.
- `Iba1CoveredByCD86_pct`: fraction of Iba1-positive voxels also CD86-positive.
- `CD206InsideIba1_pct` and `CD86InsideIba1_pct`: fractions of marker-positive
  voxels located inside the Iba1 mask.
- `Iba1_CD206_Dice`, `Iba1_CD206_Jaccard`,
  `Iba1_CD86_Dice`, and `Iba1_CD86_Jaccard`: symmetric overlap coefficients.
- `Iba1_DoubleMarker_pctIba1`: Iba1 voxels positive for both CD206 and CD86.
- `CD206_LocalEnrichment_Iba1VsRing` and
  `CD86_LocalEnrichment_Iba1VsRing`: corrected marker intensity inside Iba1
  divided by corrected intensity in the adjacent Iba1-negative ring.

The asymmetric coverage metrics are the most directly interpretable for the
question "what fraction of Iba1 signal co-occurs with CD86/CD206?" Dice and
Jaccard are supporting descriptors, not substitutes for biological controls.

## Anatomical ROI

The supplied overview images include black background, tissue fragments,
meninges, and strong peripheral signal. Define the biological compartment
before analysis, for example spinal cord parenchyma or a prespecified gray/white
matter region. Use the same ROI rule for all sections and draw ROIs blind to
group. Whether meninges and vessels are included must be decided before
quantification because CD206-positive border-associated macrophages can change
the interpretation.

## Statistical unit

Sections are technical/within-animal replicates. Average or model section-level
measurements within each rat and use the rat as the biological replicate.
For the supplied files, the nominal biological sample size is three rats, not
twenty sections. A mixed model may retain section-level rows while including a
random intercept for rat.

## Run

Select the library macro
`measure_iba1_cd206_cd86_3d_colocalization`, enable processed-image and
measurement output, and optionally provide matching ROI files.

CLI example:

```bash
python main.py "/path/to/Deconvol" \
  --keyword Iba1_CD206_CD86 \
  --macro-library measure_iba1_cd206_cd86_3d_colocalization \
  --save-processed \
  --save-measurements
```

## Methodological basis

- Manders et al. introduced asymmetric overlap coefficients for dual-color
  confocal images: <https://pubmed.ncbi.nlm.nih.gov/33930978/>
- Costes et al. described automated thresholding and randomization-based
  assessment, while emphasizing background and resolution:
  <https://pubmed.ncbi.nlm.nih.gov/15189895/>
- Dunn et al. provide a practical discussion of ROI selection, thresholding,
  bleed-through, and interpretation:
  <https://pubmed.ncbi.nlm.nih.gov/21209361/>
- Fiji Coloc 2 documentation details the effects of background, noise, and
  uninformative zero-zero pixels:
  <https://imagej.net/plugins/coloc-2>
