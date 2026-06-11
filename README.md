# Fiji Document Processor

A keyword-driven automation pipeline for Fiji/ImageJ. The processor scans a
directory tree, selects images by filename, applies a complete Fiji macro, and
can export processed images and measurement summaries.

Macros can be supplied in two ways:

1. Paste or load complete Fiji macro code.
2. Select a bundled macro from the project library.

The former simplified command-sequence syntax is not supported.

## Requirements

- Python 3.8 or later
- A local Fiji or ImageJ installation. Fiji is preferred during auto-detection
  because it includes plugins used by the bundled macros.

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

## GUI

Launch the graphical interface with:

```bash
./run_gui.sh
```

On Windows, use `run_gui.bat`.

The GUI uses 150% scaling by default. Override it when launching if needed:

```bash
FIJI_GUI_SCALE=2.0 ./run_gui.sh
```

On Linux, directory selection uses `zenity` or `kdialog` when available and
falls back to Tk's built-in picker. Windows are automatically capped to the
available screen size so action buttons remain visible on smaller displays.

Open **Macro configuration** to choose either:

- **Full macro code** for pasted Fiji code
- **Library macro** for a bundled template

Both modes support project placeholders such as `{input_path}`, `{out_csv}`,
and `{roi_manager_open_block}`.

## Command Line

```bash
python main.py BASE_PATH --keyword KEYWORD [options]
```

### Macro sources

Use complete inline code:

```bash
python main.py /data/study --keyword Control \
  --macro-code 'open("{input_path}"); run("Measure"); run("Quit");'
```

Load complete code from an `.ijm` file:

```bash
python main.py /data/study --keyword Control --macro-file analysis.ijm
```

Select a bundled macro:

```bash
python main.py /data/study --keyword Control \
  --macro-library measure_matching_roi_per_channel_after_mip \
  --apply-roi --save-measurements
```

List bundled macros:

```bash
python main.py --list-macros
```

When no macro option is provided, the CLI uses a small complete Fiji macro that
opens the current image, runs `Measure`, closes images, and quits Fiji.

### Common options

| Option | Description |
| --- | --- |
| `--keyword` / `--keywords` | Filename keyword. Repeat or comma-separate values. |
| `--secondary-filter` | Additional substring required in the filename. |
| `--macro-code` | Complete Fiji macro code. |
| `--macro-file` | Path to a complete `.ijm` macro. |
| `--macro-library` | Bundled macro name. |
| `--list-macros` | List bundled macro names. |
| `--apply-roi` | Load ROI files matching configured templates. |
| `--roi-template` | ROI filename template using `{name}` for the image stem. |
| `--save-processed` | Create the processed image output path. |
| `--save-measurements` | Create per-document measurement CSV paths. |
| `--measurement-prefix` | Prefix for combined measurement summaries. |
| `--skip-measurement-summary` | Disable the combined summary table. |
| `--fiji-path` | Explicit Fiji executable path. |
| `--validate` | Validate the Fiji installation. |

## Directory Layout

```text
/data/study
├── Experiment_A
│   ├── 01_Control_MIP.tif
│   ├── 01_Control_MIP.roi
│   ├── 02_Exp_pre.tif
│   └── 02_Exp_pre.zip
└── Experiment_B
    ├── 03_Control_post.tif
    ├── 03_Control_post_RoiSet.zip
    └── 04_Exp_followup.tif
```

Default ROI templates cover `image.roi`, `image.zip`, and
`RoiSet_image.zip`.

## Programmatic Use

```python
from config import FileConfig
from core_processor import CoreProcessor, ProcessingOptions
from examples.macros_lib import MACROS_LIB

processor = CoreProcessor(
    fiji_path="/Applications/Fiji.app/Contents/MacOS/ImageJ-macosx",
    file_config=FileConfig(
        supported_extensions=(".tif", ".tiff", ".czi"),
        roi_search_templates=("{name}.zip", "{name}_ROI.zip"),
    ),
)

options = ProcessingOptions(
    apply_roi=True,
    save_measurements_csv=True,
    measurements_folder="Measurements",
)

result = processor.process_documents(
    base_path="/data/study",
    keyword=["Exp", "Control"],
    macro_code=MACROS_LIB["measure_matching_roi_per_channel_after_mip"],
    options=options,
)
```

## Custom Macro Templates

Complete macro code can use placeholders that are replaced for every document:

```python
custom_macro = """
run("Bio-Formats Macro Extensions");
Ext.openImagePlus("{img_path_fiji}");
{roi_manager_open_block}
roiManager("Measure");
saveAs("Results", "{out_csv}");
run("Close All");
run("Quit");
"""

processor.process_documents(
    base_path="/data/study",
    keyword="Control",
    macro_code=custom_macro,
    options=options,
)
```

Common placeholders:

| Placeholder | Description |
| --- | --- |
| `{img_path_fiji}`, `{input_path}` | Fiji-formatted input path. |
| `{img_path_native}` | Native input path. |
| `{out_tiff}`, `{output_path}` | Processed image output path. |
| `{out_csv}`, `{measurements_path}` | Measurement CSV output path. |
| `{document_name}`, `{file_stem}` | Current filename without extension. |
| `{roi_manager_open_block}` | Fiji statements that open all matched ROIs. |
| `{roi_paths}`, `{roi_paths_native}` | ROI path lists. |

Enable `--save-processed` or `--save-measurements` when the selected macro uses
the corresponding output placeholders.

## Tests

```bash
python -m pytest -q
```
