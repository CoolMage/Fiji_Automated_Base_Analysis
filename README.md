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

### Launching the GUI after installation

Installing the project with pip now registers both the command-line interface
(`fiji-document-processor`) and the graphical application (`fiji-gui`). The
latter is defined as a `gui_script`, so Windows users receive a launcher that
does not spawn a console window.

```bash
# Install globally
pip install .

# or inside a virtual environment
python -m venv .venv
. .venv/bin/activate  # On Windows use `.venv\\Scripts\\activate`
pip install .

# Launch the GUI from your shell or operating-system app launcher
fiji-gui
```

The entry point simply forwards to `gui.main()`, so it will pick up new
functionality automatically as you iterate on the codebase.

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

## Example of using your own macro

Option A: inline macro lines

```bash
macro_commands = [
    'open("{input_path}");',
    'run("Gaussian Blur...", "sigma=2");',
    'saveAs("Tiff", "{output_path}");',
    'run("Quit");',  # or omit—it will be appended automatically
]
```

Option B: load an existing .ijm file and split it into lines

```bash
macro_commands = [
    line for line in Path("my_macro.ijm").read_text().splitlines() if line.strip()
]
```

Option C: provide a full macro template string

```python
custom_macro = """
// Open .czi file - this will trigger Bio-Formats dialogs
run("Bio-Formats Importer", "open=[{img_path_fiji}] autoscale color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT series_1");

originalTitle = getTitle();
run("Z Project...", "projection=[Max Intensity]");
selectWindow(originalTitle);
run("Close");
run("Split Channels");

// Insert ROI loading code here. The helper `roi_manager_open_block`
// expands to one `roiManager("Open", path);` line per ROI.
{roi_manager_open_block}
roiManager("Measure");

saveAs("Results", "{out_csv}");
run("Close All");
run("Quit");
"""

processor.process_documents(
    base_path="/data/study",
    keyword="Control",
    macro_commands=custom_macro,
    options=options,
)
```

When you supply a complete macro template, the processor injects useful
variables before execution. The most common placeholders are:

| Placeholder | Description |
| --- | --- |
| `{img_path_fiji}`, `{input_path}` | Fiji-friendly path to the current image. |
| `{img_path_native}` | Original filesystem path to the image. |
| `{out_tiff}`, `{output_path}` | Target path for processed images (created when `--save-processed` is used). |
| `{out_csv}`, `{measurements_path}` | Target path for measurement exports (created when `--save-measurements` is enabled). |
| `{document_name}`, `{file_stem}` | Filename without extension. |
| `{roi_manager_open_block}` | Multi-line helper that opens every matched ROI using Fiji paths. |
| `{roi_paths}` / `{roi_paths_native}` | Lists of ROI paths (Fiji-formatted and native). |

Include any other macro logic you need—the template is executed verbatim, so
remember to add cleanup commands such as `run("Quit");` when necessary.


## Building standalone desktop apps

If your users do not have Python installed, create self-contained bundles with
[PyInstaller](https://pyinstaller.org/). A ready-to-use spec file lives under
`packaging/fiji_gui.spec` and collects all runtime resources required by the GUI.

```bash
pip install pyinstaller
pyinstaller packaging/fiji_gui.spec
```

The resulting artifacts appear in `dist/FijiProcessorGUI/`:

- **Windows** – wrap the folder into an installer (MSI/EXE) and add a shortcut
  that points to `FijiProcessorGUI.exe`. Inno Setup and WiX Toolset both work.
- **macOS** – the spec enables `argv_emulation`, so the `FijiProcessorGUI.app`
  bundle behaves like a native application. Codesign and notarize before
  distribution if required by your organization.
- **Linux** – create an AppImage or copy the folder into `/opt`. Ship the
  template desktop entry located at `packaging/linux/fiji-gui.desktop`; update
  the `Exec` and `Icon` paths to match your installation root and place the file
  under `~/.local/share/applications/`.

Because the spec runs on the current platform, build on each operating system
you plan to support. The Fiji auto-discovery helpers are bundled with the app,
so users can rely on automatic detection or select a custom executable at
runtime.


## Running the built-in smoke tests

Two lightweight scripts ensure the environment is set up correctly:

```bash
python test_setup.py
python test_core_setup.py
```

They focus on import checks, helper utilities, and validating that the processor
handles both single and multiple keywords.

## Don't know what to do?

- Open `run_sample_processing.py`
- Replace `base_path` with the path to the folder where your data is stored.
- Replace `keyword` with keywords in the file names so the script can distinguish them.
- Replace macro_commands with the list of commands you need to execute. You can check the list of commands in the `macro_builder.py` document.
- Run `run_sample_processing.py`


## What's next for updates?

- Integration of built-in complex commands
- Pre-written macro library
- Adding the ability to select the channel to be processed
- Optional automatic data visualization