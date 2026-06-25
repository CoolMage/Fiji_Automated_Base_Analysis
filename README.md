# Fiji Document Processor

Batch automation for Fiji/ImageJ microscopy workflows. The program scans a
folder tree, selects images by filename keywords, optionally loads matching ROI
files, runs a complete Fiji macro or a bundled macro, and can export processed
images plus measurement summaries.

Fiji is preferred over plain ImageJ because the bundled workflows often rely on
Bio-Formats and Fiji plugins.

## Features

- GUI and command-line interfaces.
- Keyword-based batch selection with optional secondary filename filters.
- ROI lookup from common `.roi` and `.zip` naming patterns.
- Custom Fiji macro code, `.ijm` macro files, or bundled library macros.
- Processed image exports and per-image or combined CSV measurements.
- Optional calibrated 3D deconvolution with DeconvolutionLab2.

## Requirements

- Python 3.10 or newer.
- A local Fiji or ImageJ installation. Use Fiji unless you have a specific
  reason to use ImageJ.
- Tkinter for the GUI. It is included with most Windows/macOS Python installs;
  on Linux it may need a separate package such as `python3-tk`.
- Optional: DeconvolutionLab2 installed into Fiji when using 3D deconvolution.

## Installation

Download or copy this repository to the target computer, then open a terminal
inside the project folder. If you use Git:

```bash
git clone https://github.com/CoolMage/Fiji_Automated_Base_Analysis.git
cd Fiji_Automated_Base_Analysis
```

Install Fiji from the official [Fiji website](https://fiji.sc/) and open it
once so it can finish its first-run setup and plugin updates. If the program
cannot find Fiji automatically, pass the executable path with `--fiji-path`.

### Windows

1. Install Python 3.10+ and enable "Add python.exe to PATH" during setup.
2. Install or unzip Fiji, for example under `C:\Program Files\Fiji` or
   `C:\Fiji.app`.
3. Double-click this file in Explorer:

```text
Start_GUI_Windows.cmd
```

On first launch it creates `.venv`, installs `requirements.txt`, and starts the
GUI. If something fails, the console window stays open so you can read the
error.

Manual setup is also possible:

```powershell
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python gui.py
```

You can also start it from PowerShell or Command Prompt:

```powershell
.\run_gui.bat
```

Do not run `.cmd` or `.bat` launchers with Python. If you see
`SyntaxError: invalid syntax` near `@echo off`, the file was opened by Python
instead of `cmd.exe`; double-click `Start_GUI_Windows.cmd`, use
`.\run_gui.bat` from a terminal, or run `python gui.py` directly.

Validate Fiji manually if auto-detection fails:

```powershell
python main.py --validate --fiji-path "C:\Fiji.app\ImageJ-win64.exe"
```

### macOS

1. Install Python 3.10+.
2. Copy `Fiji.app` to `/Applications`, `~/Applications`, `~/Documents`, or a
   parent/sibling folder near this project.
3. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
chmod +x run_gui.sh run_analysis.sh
```

Start the GUI:

```bash
./run_gui.sh
```

Validate Fiji manually if needed:

```bash
python main.py --validate --fiji-path /Applications/Fiji.app/Contents/MacOS/ImageJ-macosx
```

For newer Fiji builds, the application also detects `fiji-macos-arm64` and
`fiji-macos-x64` launchers.

### Linux

1. Install Python 3.10+, venv, and Tkinter. On Debian/Ubuntu:

```bash
sudo apt install python3 python3-venv python3-tk
```

2. Install Fiji under a location such as `/opt/Fiji.app`, `/opt/fiji`,
   `~/Fiji.app`, `~/Documents/Fiji.app`, `~/Downloads/Fiji.app`, or a
   parent/sibling folder near this project.
3. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
chmod +x run_gui.sh run_analysis.sh
```

Start the GUI:

```bash
./run_gui.sh
```

Validate Fiji manually if needed:

```bash
python main.py --validate --fiji-path ~/Fiji.app/ImageJ-linux64
```

You can also pass the Fiji installation directory itself:

```bash
python main.py --validate --fiji-path ~/Fiji.app
```

Automatic detection also checks parent directories of the project folder, so a
layout such as `~/Documents/Fiji.app` and
`~/Documents/Git_rep/Fiji_Automated_Base_Analysis` is supported.

On Linux, directory selection uses `zenity` or `kdialog` when available and
falls back to Tk's built-in file picker.

## Verify Setup

Run these from the project folder after installation:

```bash
python main.py --validate
python main.py --list-macros
```

`--validate` reports the detected Fiji/ImageJ path, supported file extensions,
and whether DeconvolutionLab2 was found.

## GUI Usage

Launch the interface with `Start_GUI_Windows.cmd` on Windows or `./run_gui.sh`
on macOS and Linux.

The GUI defaults to 150% scaling. Override it when needed:

```bash
FIJI_GUI_SCALE=2.0 ./run_gui.sh
```

Open **Macro configuration** to choose one of the supported macro sources:

- **Full macro code** for pasted Fiji macro code.
- **Library macro** for a bundled template.

Both modes support project placeholders such as `{input_path}`, `{out_csv}`,
and `{roi_manager_open_block}`.

## Command Line Usage

Basic syntax:

```bash
python main.py BASE_PATH --keyword KEYWORD [options]
```

Run a bundled macro on matching files:

```bash
python main.py /data/study --keyword Control \
  --macro-library measure_matching_roi_per_channel_after_mip \
  --apply-roi --save-measurements
```

Load a custom `.ijm` macro file:

```bash
python main.py /data/study --keyword Control --macro-file analysis.ijm
```

Use inline Fiji macro code:

```bash
python main.py /data/study --keyword Control \
  --macro-code 'open("{input_path}"); run("Measure"); run("Quit");'
```

List bundled macros:

```bash
python main.py --list-macros
```

If no macro option is provided, the CLI uses a minimal macro that opens the
image, runs `Measure`, closes images, and quits Fiji.

### Common Options

| Option | Purpose |
| --- | --- |
| `--keyword`, `--keywords` | Filename keyword. Repeat or comma-separate values. |
| `--secondary-filter` | Extra substring required in the filename. |
| `--macro-code` | Complete Fiji macro code. |
| `--macro-file` | Path to a complete `.ijm` macro. |
| `--macro-library` | Bundled macro name. |
| `--apply-roi` | Load matching ROI files before measurement. |
| `--roi-template` | ROI filename template using `{name}` for the image stem. |
| `--save-processed` | Create processed image output paths. |
| `--save-measurements` | Create per-document measurement CSV paths. |
| `--measurement-prefix` | Prefix for combined measurement summaries. |
| `--generate-measurement-summary` | Enable the combined summary table. Disabled by default. |
| `--skip-measurement-summary` | Disable the combined summary table; kept for compatibility. |
| `--fiji-path` | Explicit Fiji/ImageJ executable path. |
| `--validate` | Validate the Fiji/ImageJ setup and exit. |
| `--list-macros` | Print bundled macro names and exit. |

Run `python main.py --help` for the complete option list.

## Project Layout

```text
fiji_automated_analysis/   Main package: CLI, GUI, processor, config, utilities
fiji_automated_analysis/macros_lib/
                           Bundled Fiji macro templates and protocols
scripts/                   Full shell and batch launchers
examples/                  Sample data and example automation scripts
tests/                     Pytest test suite
```

Root files such as `main.py`, `gui.py`, `run_gui.sh`, and `run_analysis.sh`
are compatibility wrappers, so old commands still work while the implementation
lives in the package.

## Input Layout

The program recursively scans the base folder and matches supported image files
by filename. A typical study can look like this:

```text
/data/study
|-- Experiment_A
|   |-- 01_Control_MIP.tif
|   |-- 01_Control_MIP.roi
|   |-- 02_Exp_pre.tif
|   `-- 02_Exp_pre.zip
`-- Experiment_B
    |-- 03_Control_post.tif
    |-- 03_Control_post_RoiSet.zip
    `-- 04_Exp_followup.tif
```

Default ROI templates cover `image.roi`, `image.zip`, and `RoiSet_image.zip`.
Output folders such as `Measurements/`, `Processed_Files/`, and
`Deconvolved/` are ignored during recursive input scanning.

Supported input extensions include `.tif`, `.tiff`, `.ims`, `.czi`, `.nd2`,
`.vsi`, and `.mp4`.

## Macro Placeholders

Custom macro code can use placeholders that are replaced for each image:

| Placeholder | Value |
| --- | --- |
| `{img_path_fiji}`, `{input_path}` | Fiji-formatted input path. |
| `{img_path_native}` | Native OS input path. |
| `{out_tiff}`, `{output_path}` | Processed image output path. |
| `{out_csv}`, `{measurements_path}` | Measurement CSV output path. |
| `{document_name}`, `{file_stem}` | Filename without extension. |
| `{roi_manager_open_block}` | Fiji statements that open matched ROIs. |
| `{roi_paths}`, `{roi_paths_native}` | ROI path lists. |

Enable `--save-processed` or `--save-measurements` when a macro uses the
corresponding output placeholders.

## 3D Deconvolution

Deconvolution is optional preprocessing. It runs before the selected library or
custom analysis macro, so downstream MIP, thresholding, ROI measurements, and
exports use the deconvolved stack.

Install the official
[DeconvolutionLab2](https://bigwww.epfl.ch/deconvolution/deconvolutionlab2/)
plugin into the Fiji installation selected by the application. `--validate`
reports whether the plugin was detected.

Run deconvolution with one PSF TIFF Z-stack per image channel:

```bash
python main.py /data/study --keyword Control \
  --macro-library measure_matching_roi_per_channel_after_mip \
  --deconvolve \
  --psf /data/psf/C1.tif \
  --psf /data/psf/C2.tif
```

The simple preset uses 3D Richardson-Lucy, 10 iterations by default, PSF
normalization to unit sum, and 32-bit float TIFF output. The program validates
that inputs and PSFs are calibrated grayscale 3D stacks with matching voxel
sizes, one PSF per channel, and no time dimension. Outputs are written to
`Deconvolved/` with a JSON manifest.

In the GUI, PSFs can come from TIFF files or from DeconvolutionLab2's
theoretical `AxialDiffractionSimulation` model. The theoretical settings are
stored in the same deconvolution manifest.

Additional CLI options:

| Option | Purpose |
| --- | --- |
| `--psf` | PSF TIFF Z-stack; repeat in `C1`, `C2`, ... order. |
| `--deconvolution-iterations` | Richardson-Lucy iterations; default is `10`. |
| `--deconvolution-folder` | Output folder; default is `Deconvolved`. |
| `--deconvolution-memory-gb` | Fiji heap for deconvolution; default is `8`. |
| `--deconvolution-timeout` | Maximum seconds per deconvolution job. |

## Troubleshooting

- If Fiji is not found, run with `--fiji-path` and quote paths containing
  spaces.
- On Windows, Fiji is often unpacked as `Fiji.app`. The executable is usually
  `Fiji.app\ImageJ-win64.exe`; select that file manually or set `FIJI_PATH` to
  its full path if auto-detection misses it.
- If the GUI does not start on Linux, install `python3-tk`.
- If directory selection is awkward on Linux, install `zenity` or `kdialog`.
- If DeconvolutionLab2 is missing, install the plugin into the same Fiji copy
  reported by `python main.py --validate`.

## Tests

For development, install test dependencies and run pytest:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```
