# Fiji Document Processor

A database-driven document processing tool for Fiji/ImageJ that focuses on keyword-based document selection, measurement collection, and optional processing features. Designed for simplicity and flexibility with comprehensive command library support.

## Core Philosophy

**Default Behavior**: Find documents by keyword → Apply macro → Save measurements  
**Everything Else**: Optional and customizable

## Key Features

- **Database-driven processing**: Find and process documents based on keywords
- **Automatic measurements**: Default behavior saves measurements to CSV/JSON
- **Optional features**: ROI processing, file saving, custom suffixes, secondary filtering
- **Command library**: 25+ pre-built commands with detailed documentation
- **Cross-platform**: Works on Windows, macOS, and Linux
- **Flexible filtering**: Primary keyword + optional secondary filter (e.g., "MIP")
- **Bio-Formats support**: Handles .tif, .ims, .czi, .nd2, and other formats

## Installation

### From Source

1. Clone the repository:
```bash
git clone https://github.com/yourusername/fiji-automated-analysis.git
cd fiji-automated-analysis
```

2. Install the package:
```bash
pip install -e .
```

### Requirements

- Python 3.7 or higher
- Fiji/ImageJ installed on your system

## Quick Start

### Basic Usage (Default: Find → Measure → Save)

```bash
# Find documents with keyword "experimental" and measure them
python main.py /path/to/documents --keyword "experimental"

# Find documents with secondary filter (e.g., MIP files)
python main.py /path/to/documents --keyword "experimental" --secondary-filter "MIP"

# Apply custom commands
python main.py /path/to/documents --keyword "control" --commands "open_standard convert_8bit measure"
```

### Optional Features

```bash
# Process with ROI and save processed files
python main.py /path/to/documents --keyword "treatment" --apply-roi --save-processed --suffix "analyzed"

# Custom output folders
python main.py /path/to/documents --keyword "data" --measurements-folder "Results" --processed-folder "Output"

# Show all available commands
python main.py --list-commands

# Validate setup
python main.py --validate
```

## Configuration

### Group Configuration

You can customize group names and subject mappings:

```python
from config import GroupConfig

# Custom group configuration
group_config = GroupConfig(
    groups={
        "Treatment": "Drug_A",
        "Control": "Vehicle",
        "Positive": "Reference"
    }
)
```

### Processing Configuration

Customize image processing parameters:

```python
from config import ProcessingConfig

# Custom processing configuration
processing_config = ProcessingConfig(
    rolling_radius=50,        # Background subtraction radius
    median_radius=3,          # Median filter radius
    saturated_pixels=0.4,     # Contrast enhancement
    convert_to_8bit=True,     # Convert to 8-bit
    duplicate_channels=1,     # Number of channels to duplicate
    duplicate_slices="1-end", # Slices to duplicate
    duplicate_frames="1-end"  # Frames to duplicate
)
```

### File Configuration

Customize supported file types and patterns:

```python
from config import FileConfig

# Custom file configuration
file_config = FileConfig(
    supported_extensions=['.tif', '.ims', '.czi', '.nd2'],
    mip_keywords=['_MIP_', '_MIP.tif', '_MIP.ims'],
    roi_patterns={
        'roiset': 'RoiSet_{cut_number}.zip',
        'single_roi': 'roi_{cut_number}.roi',
        'inverted_roi': 'roi_{cut_number}_inverted.roi'
    }
)
```

## Programming Interface

### Using the FijiProcessor Class

```python
from fiji_processor import FijiProcessor
from config import ProcessingConfig, FileConfig, GroupConfig

# Initialize processor with custom configuration
processor = FijiProcessor(
    fiji_path="/path/to/fiji",  # Optional, auto-detected if None
    processing_config=ProcessingConfig(),
    file_config=FileConfig(),
    group_config=GroupConfig()
)

# Process images
result = processor.process_images(
    base_path="/path/to/images",
    group_keywords=["Experimental", "Control"],
    mip_only=False,
    verbose=True
)

# Process ROIs
roi_result = processor.process_rois(
    base_path="/path/to/images",
    group_keywords=["Experimental", "Control"],
    roi_name_pattern="roi_cut"
)

# Check results
if result["success"]:
    print(f"Processed {len(result['processed_files'])} files")
else:
    print(f"Error: {result['error']}")
```

### Using Custom Macros

```python
# Custom macro code
custom_macro = """
open("{input_path}");
run("8-bit");
run("Gaussian Blur...", "sigma=2");
saveAs("Tiff", "{output_path}");
"""

# Process with custom macro
result = processor.process_images(
    base_path="/path/to/images",
    custom_macro=custom_macro
)
```

### Using Simple Commands

```python
# Simple command sequence
simple_commands = "open_standard convert_8bit subtract_background save_tiff"

result = processor.process_images(
    base_path="/path/to/images",
    simple_commands=simple_commands
)
```

## Command Library

The tool includes a comprehensive library of 25+ pre-built commands. Use `python main.py --list-commands` to see all available commands.

### File Operations

| Command | Description | Parameters | Example |
|---------|-------------|------------|---------|
| `open_standard` | Open image with standard ImageJ method | `input_path` | `open_standard` |
| `open_bioformats` | Open image using Bio-Formats importer | `input_path` | `open_bioformats` |
| `save_tiff` | Save current image as TIFF | `output_path` | `save_tiff` |
| `save_csv` | Save measurements as CSV | `output_path` | `save_csv` |

### Image Processing

| Command | Description | Parameters | Example |
|---------|-------------|------------|---------|
| `convert_8bit` | Convert image to 8-bit | None | `convert_8bit` |
| `convert_16bit` | Convert image to 16-bit | None | `convert_16bit` |
| `subtract_background` | Subtract background using rolling ball | `radius` (default: 30) | `subtract_background radius=50` |
| `median_filter` | Apply median filter | `radius` (default: 2) | `median_filter radius=3` |
| `gaussian_blur` | Apply Gaussian blur | `sigma` (default: 2.0) | `gaussian_blur sigma=1.5` |
| `enhance_contrast` | Enhance contrast using histogram equalization | `saturated` (default: 0.35) | `enhance_contrast saturated=0.4` |
| `threshold` | Apply threshold | `method` (default: 'Default') | `threshold method='Otsu'` |

### Measurements

| Command | Description | Parameters | Example |
|---------|-------------|------------|---------|
| `measure` | Measure current selection or entire image | `measurements` (optional) | `measure` |
| `set_measurements` | Set which measurements to record | `measurements` | `set_measurements measurements='area,mean,std'` |
| `clear_measurements` | Clear all measurements | None | `clear_measurements` |

### ROI Operations

| Command | Description | Parameters | Example |
|---------|-------------|------------|---------|
| `roi_manager_reset` | Reset ROI Manager | None | `roi_manager_reset` |
| `roi_manager_open` | Open ROI file | `roi_path` | `roi_manager_open roi_path='/path/to/roi.zip'` |
| `roi_manager_select` | Select ROI by index | `index` | `roi_manager_select index=0` |
| `roi_manager_measure` | Measure all ROIs in manager | None | `roi_manager_measure` |
| `make_inverse` | Create inverse of current selection | None | `make_inverse` |
| `roi_manager_add` | Add current selection to ROI Manager | None | `roi_manager_add` |
| `roi_manager_save` | Save ROIs to file | `roi_path` | `roi_manager_save roi_path='/path/to/save.zip'` |

### Utility Operations

| Command | Description | Parameters | Example |
|---------|-------------|------------|---------|
| `duplicate` | Duplicate current image | `title`, `channels`, `slices`, `frames` | `duplicate title='Copy' channels=1` |
| `close_all` | Close all open windows | None | `close_all` |
| `quit` | Quit ImageJ/Fiji | None | `quit` |

### Display Operations

| Command | Description | Parameters | Example |
|---------|-------------|------------|---------|
| `set_option_show_all` | Set 'Show All' option to false | None | `set_option_show_all` |
| `remove_overlay` | Remove any overlays | None | `remove_overlay` |
| `roi_manager_show_none` | Hide all ROIs | None | `roi_manager_show_none` |
| `roi_manager_deselect` | Deselect all ROIs | None | `roi_manager_deselect` |

### Command Usage Examples

```bash
# Basic measurement workflow
python main.py /path/to/docs --keyword "data" --commands "open_standard measure save_csv"

# Image processing with measurements
python main.py /path/to/docs --keyword "images" --commands "open_standard convert_8bit subtract_background measure"

# ROI-based processing
python main.py /path/to/docs --keyword "roi_data" --commands "open_standard roi_manager_open roi_manager_measure" --apply-roi

# Custom parameters
python main.py /path/to/docs --keyword "processed" --commands "open_standard subtract_background radius=50 enhance_contrast saturated=0.4 measure"
```

## File Structure

```
fiji-automated-analysis/
├── main.py                 # Main entry point
├── fiji_processor.py      # Core processor class
├── config.py              # Configuration classes
├── utils/
│   ├── general/
│   │   ├── fiji_utils.py      # Fiji utilities
│   │   ├── file_utils.py      # File processing utilities
│   │   ├── macro_builder.py   # Macro building system
│   │   └── macros_operation.py # Macro execution
│   └── processing/
│       └── roi_processing.py  # ROI processing (legacy)
├── examples/              # Example scripts
├── tests/                 # Test files
├── setup.py              # Package setup
├── requirements.txt      # Dependencies
└── README.md            # This file
```

## Examples

### Example 1: Basic Image Processing

```python
from fiji_processor import FijiProcessor

# Initialize processor
processor = FijiProcessor()

# Process images with default settings
result = processor.process_images("/path/to/images")

print(f"Success: {result['success']}")
print(f"Processed files: {len(result['processed_files'])}")
```

### Example 2: Custom Processing Pipeline

```python
from fiji_processor import FijiProcessor
from config import ProcessingConfig

# Custom processing configuration
config = ProcessingConfig(
    rolling_radius=50,
    median_radius=3,
    saturated_pixels=0.4
)

# Initialize processor with custom config
processor = FijiProcessor(processing_config=config)

# Process with custom settings
result = processor.process_images(
    base_path="/path/to/images",
    group_keywords=["Treatment", "Control"],
    mip_only=True
)
```

### Example 3: ROI Processing

```python
from fiji_processor import FijiProcessor

# Initialize processor
processor = FijiProcessor()

# Process ROIs
result = processor.process_rois(
    base_path="/path/to/images",
    group_keywords=["Experimental", "Control"]
)

if result["success"]:
    print("ROI processing completed successfully")
else:
    print(f"ROI processing failed: {result['error']}")
```

## Troubleshooting

### Fiji Not Found

If Fiji is not automatically detected:

1. Install Fiji from https://fiji.sc/
2. Provide the path manually:
   ```bash
   python main.py /path/to/images --fiji-path /path/to/fiji
   ```

### Platform-Specific Issues

- **Windows**: Ensure Fiji is in your PATH or provide the full path
- **macOS**: Fiji is typically found in `/Applications/Fiji.app/`
- **Linux**: Install Fiji in `/opt/fiji/` or provide the path

### Validation

Check your setup:

```bash
python main.py /path/to/images --validate
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Create an issue on GitHub
- Check the documentation
- Review the examples

## Changelog

### Version 1.0.0
- Initial release
- Cross-platform support
- Flexible configuration system
- Multiple macro options
- ROI processing capabilities
- Comprehensive documentation
