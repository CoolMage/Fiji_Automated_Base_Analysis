# LFB Luxol RGB Protocol (Red Channel, Threshold 185)

## Macro file

- `examples/macros_lib/lfb_luxol_red_threshold185_macro.ijm`

## What the macro does

1. Opens an RGB image in Fiji via Bio-Formats.
2. Splits channels and keeps only `C1` (red channel).
3. Converts red channel to 8-bit, inverts it, applies threshold `185..255`.
4. Loads ROI(s) for this image (or creates full-image ROI if none found).
5. Runs `Measure` for each ROI with all enabled Fiji metrics, including `%Area` (`Area Fraction`).
6. Saves Fiji Results table to CSV.

## Fixed analysis settings

- Channel: `C1` (red)
- Threshold: `185..255` on **inverted** red channel

## Output columns (CSV)

- All columns produced by Fiji `Measure` with enabled options.
- Includes `%Area` (Area Fraction), `Mean`, `Area`, and other selected metrics.
- Additional metadata columns added by macro:
  - `Document`
  - `ROI`
  - `ThresholdLow`
  - `ThresholdHigh`

## Run in the current pipeline

Use `main.py` with:

- `--apply-roi`
- `--save-measurements`
- custom macro content from:
  - `examples/macros_lib/lfb_luxol_red_threshold185_macro.ijm`

Recommended ROI template for your dataset:

- `--roi-template "{name}.roi"`

Recommended keywords:

- `--keyword Exp --keyword Control`

Example:

```bash
python main.py "/Volumes/T7_Shield/Luxol" \
  --keyword Exp --keyword Control \
  --apply-roi --roi-template "{name}.roi" \
  --save-measurements \
  --macro-file examples/macros_lib/lfb_luxol_red_threshold185_macro.ijm
```

## Notes

- Keep threshold fixed for all images within one staining/scanning batch.
- If you change preprocessing or channel, recalibrate threshold before batch run.
