# Fiji Document Processor

A single, keyword-driven automation pipeline for Fiji/ImageJ. Provide one or more
keywords, optionally constrain matches with a secondary filter, and the processor
will walk your directory tree, open each matching file in Fiji, run your macro
commands, record measurements, and (optionally) export processed images.

The focus is on making every name and key configurable from the command line so
it stays approachable for quick runs while remaining flexible for custom
workflows.

## Requirements

- Python 3.8 or later
- A local Fiji/ImageJ installation (the tool attempts auto-discovery, but you
  can always pass `--fiji-path`)

Install the Python dependencies with:

```bash
pip install -r requirements.txt
```

For editable installs (optional):

```bash
pip install -e .
```

## Expected directory layout

Point the processor at the root directory that contains your study folders.
The tool will recurse through every subdirectory when searching for filenames
that contain the configured keywords.

```
/data/study
├── Experiment_A
│   ├── 01_Control_MIP.tif
│   ├── 01_Control_MIP.roi
│   ├── 02_4MU_pre.tif
│   └── 02_4MU_pre.zip
└── Experiment_B
    ├── 03_Control_post.tif
    ├── 03_Control_post_RoiSet.zip
    └── 04_4MU_followup.tif
```

- **Keywords** are matched against the filename (e.g., `4MU`, `Control`).
- A **secondary filter** further constrains matches (e.g., only files containing
  `MIP`).
- **ROI templates** determine how ROI filenames are derived from the image stem.
  Defaults cover `image.roi`, `image.zip`, and `RoiSet_image.zip`, but you can
  supply your own patterns with `{name}` acting as the filename placeholder.

## Command-line usage

```bash
python main.py BASE_PATH --keyword KEYWORD [options]
```

### Common examples

```bash
# Process every file whose name contains "4MU"
python main.py /data/study --keyword 4MU

# Process files that contain either "4MU" or "Control"
python main.py /data/study --keyword 4MU --keyword Control

# Same as above using a single comma-separated entry
python main.py /data/study --keyword "4MU,Control"

# Require both a primary keyword and a secondary filter (e.g. only MIP files)
python main.py /data/study --keyword 4MU --secondary-filter MIP

# Apply ROIs and use a custom ROI template
python main.py /data/study --keyword Control --apply-roi \
    --roi-template "{name}_ROI.zip"

# Save processed images with a custom suffix and measurement summary prefix
python main.py /data/study --keyword 4MU --save-processed --suffix analyzed \
    --measurement-prefix studyA

# Disable the combined summary table while still exporting per-file measurements
python main.py /data/study --keyword 4MU --save-measurements --skip-measurement-summary

# Show every built-in macro command
python main.py --list-commands

# Verify that Fiji is reachable and inspect supported extensions
python main.py --validate
```

### Option reference

| Option | Description |
| --- | --- |
| `--keyword` / `--keywords` | Primary keyword(s). Repeat the flag or provide a comma-separated list. |
| `--secondary-filter` | Additional substring that must appear in the filename. |
| `--commands` | Space-separated macro commands (defaults to `open_standard measure save_csv quit`). |
| `--apply-roi` | Load ROI files that match the configured templates. |
| `--roi-template` | Override ROI templates. Use `{name}` where the base filename should appear. |
| `--save-processed` | Export processed images to `<base_path>/<processed_folder>`. |
| `--suffix` | Suffix for processed filenames (default: `processed`). |
| `--measurements-folder` | Directory (under the base path) for measurement exports. |
| `--processed-folder` | Directory (under the base path) for processed images. |
| `--measurement-prefix` | Prefix used when saving CSV/JSON measurement summaries. |
| `--skip-measurement-summary` | Skip creation of the combined summary table generated from saved CSV files. |
| `--fiji-path` | Explicit path to the Fiji executable. |
| `--verbose` | Print detailed progress, including the matched keyword for each file. |

## Programmatic use

You can embed the processor in your own scripts to run highly customized
pipelines.

```python
from core_processor import CoreProcessor, ProcessingOptions
from config import FileConfig

file_config = FileConfig(
    supported_extensions=(".tif", ".tiff", ".czi"),
    roi_search_templates=("{name}.zip", "{name}_ROI.zip"),
)

processor = CoreProcessor(
    fiji_path="/Applications/Fiji.app/Contents/MacOS/ImageJ-macosx",
    file_config=file_config,
)

options = ProcessingOptions(
    apply_roi=True,
    save_processed_files=True,
    save_measurements_csv=True,
    custom_suffix="analyzed",
    measurements_folder="Measurements",
    processed_folder="Processed",
    measurement_summary_prefix="studyA",
    generate_measurement_summary=True,
    roi_search_templates=("{name}.zip", "RoiSet_{name}.zip"),
)

result = processor.process_documents(
    base_path="/data/study",
    keyword=["4MU", "Control"],
    macro_commands="open_standard measure save_csv quit",
    options=options,
    verbose=True,
)
```

Results include the list of processed documents, failed documents (with error
messages), measurement data grouped by file, and the keywords that were used for
the search.

## Examples directory

The `examples` folder contains a miniature dataset that mirrors the directory
structure shown above:

```
examples/sample_documents/
├── Experiment_A
│   ├── 01_Control_MIP.tif
│   ├── 01_Control_MIP.roi
│   ├── 02_4MU_pre.tif
│   └── 02_4MU_pre.zip
├── Experiment_B
│   ├── 03_Control_post.tif
│   ├── 03_Control_post_RoiSet.zip
│   └── 04_4MU_followup.tif
└── README.md
```

Use it as a reference for how filenames map to keywords, secondary filters, and
ROI templates. The accompanying `README.md` inside the directory includes
suggested command invocations you can adapt for your own studies.

## Running the built-in smoke tests

Two lightweight scripts ensure the environment is set up correctly:

```bash
python test_setup.py
python test_core_setup.py
```

They focus on import checks, helper utilities, and validating that the processor
handles both single and multiple keywords.
