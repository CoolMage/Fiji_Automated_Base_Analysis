#!/usr/bin/env python3
"""
Test script to validate the Fiji Automated Analysis setup.
"""

import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from config import ProcessingConfig, FileConfig, FijiConfig
        print("✅ Config modules imported successfully")
    except ImportError as e:
        print(f"❌ Config import failed: {e}")
        return False

    try:
        from core_processor import CoreProcessor, ProcessingOptions
        print("✅ Core processor modules imported successfully")
    except ImportError as e:
        print(f"❌ Core processor import failed: {e}")
        return False

    try:
        from utils.general.fiji_utils import find_fiji, validate_fiji_path
        print("✅ Fiji utils imported successfully")
    except ImportError as e:
        print(f"❌ Fiji utils import failed: {e}")
        return False

    try:
        from utils.general.kymo_utils import find_kymograph_direct, validate_kymograph_direct_path
        print("✅ KymographDirect utils imported successfully")
    except ImportError as e:
        print(f"❌ KymographDirect utils import failed: {e}")
        return False

    try:
        from utils.general.file_utils import normalize_path
        print("✅ File utils imported successfully")
    except ImportError as e:
        print(f"❌ File utils import failed: {e}")
        return False

    try:
        from utils.general.macro_builder import MacroBuilder, ImageData, MacroCommand
        print("✅ Macro builder imported successfully")
    except ImportError as e:
        print(f"❌ Macro builder import failed: {e}")
        return False

    try:
        from utils.general.macros_operation import run_fiji_macro
        print("✅ Macros operation imported successfully")
    except ImportError as e:
        print(f"❌ Macros operation import failed: {e}")
        return False
    
    return True

def test_configuration():
    """Test configuration classes."""
    print("\nTesting configuration...")
    
    try:
        from config import ProcessingConfig, FileConfig

        # Test ProcessingConfig
        proc_config = ProcessingConfig()
        print(f"✅ ProcessingConfig: rolling_radius={proc_config.rolling_radius}")

        # Test FileConfig
        file_config = FileConfig()
        print(
            "✅ FileConfig: "
            f"{len(file_config.supported_extensions)} extensions, "
            f"{len(file_config.bioformats_extensions)} bioformats entries"
        )

        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_fiji_detection():
    """Test Fiji detection."""
    print("\nTesting Fiji detection...")
    
    try:
        from utils.general.fiji_utils import find_fiji, validate_fiji_path
        
        fiji_path = find_fiji()
        if fiji_path:
            print(f"✅ Fiji found at: {fiji_path}")
            
            is_valid = validate_fiji_path(fiji_path)
            if is_valid:
                print("✅ Fiji path is valid")
            else:
                print("⚠️  Fiji path is invalid (Fiji may not be properly installed)")
        else:
            print("⚠️  Fiji not found (this is expected if Fiji is not installed)")
        
        return True
    except Exception as e:
        print(f"❌ Fiji detection test failed: {e}")
        return False

def test_kymograph_direct_detection():
    """Test KymographDirect detection."""
    print("\nTesting KymographDirect detection...")

    try:
        from utils.general.kymo_utils import find_kymograph_direct, validate_kymograph_direct_path

        kymo_path = find_kymograph_direct()
        if kymo_path:
            print(f"✅ KymographDirect found at: {kymo_path}")

            is_valid = validate_kymograph_direct_path(kymo_path)
            if is_valid:
                print("✅ KymographDirect path is valid")
            else:
                print("⚠️  KymographDirect path is invalid (application may not be properly installed)")
        else:
            print("⚠️  KymographDirect not found (this is expected if it is not installed)")

        return True
    except Exception as e:
        print(f"❌ KymographDirect detection test failed: {e}")
        return False

def test_macro_builder():
    """Test macro builder functionality."""
    print("\nTesting macro builder...")

    try:
        from utils.general.macro_builder import MacroBuilder, ImageData, MacroCommand
        from config import ProcessingConfig, FileConfig
        
        # Create macro builder
        builder = MacroBuilder()
        print(f"✅ MacroBuilder created with {len(builder.command_templates)} commands")
        
        # Test ImageData
        image_data = ImageData(
            input_path="/test/input.tif",
            output_path="/test/output.tif",
            file_extension=".tif",
            is_bioformats=False,
            measurements_path="/test/output.csv"
        )
        print("✅ ImageData created successfully")
        
        # Test MacroCommand
        cmd = MacroCommand("open_standard", comment="Test command")
        print("✅ MacroCommand created successfully")
        
        # Test simple command parsing
        commands = builder.parse_simple_commands("open_standard convert_8bit save_tiff")
        print(f"✅ Parsed {len(commands)} simple commands")

        return True
    except Exception as e:
        print(f"❌ Macro builder test failed: {e}")
        return False


def test_custom_macro_template():
    """Ensure custom macro templates expand placeholders correctly."""
    print("\nTesting custom macro templates...")

    try:
        from utils.general.macro_builder import MacroBuilder, ImageData

        builder = MacroBuilder()
        image_data = ImageData(
            input_path="/converted/input.tif",
            output_path="/converted/output.tif",
            file_extension=".tif",
            is_bioformats=True,
            roi_paths=[
                "/converted/roi1.zip",
                "/converted/roi2.zip",
            ],
            roi_paths_native=[
                "/native/roi1.zip",
                "/native/roi2.zip",
            ],
            measurements_path="/converted/results.csv",
            source_path="/native/input.tif",
            output_path_native="/native/output.tif",
            measurements_path_native="/native/results.csv",
            document_name="sample_image",
        )

        template = (
            'run("Bio-Formats Macro Extensions");\n'
            'Ext.openImagePlus("{img_path_fiji}");\n'
            "{roi_manager_open_block}\n"
            'saveAs("Results", "{out_csv}");'
        )

        macro_code = builder.build_custom_macro(template, image_data)

        if (
            image_data.input_path not in macro_code
            or 'roiManager("Open", "/converted/roi1.zip");' not in macro_code
            or image_data.measurements_path not in macro_code
        ):
            raise AssertionError("Template placeholders did not expand as expected")

        print("✅ Custom macro template expanded correctly")
        return True
    except Exception as e:
        print(f"❌ Custom macro template test failed: {e}")
        return False

def test_cli_helpers():
    """Test keyword and ROI template collection helpers."""
    print("\nTesting CLI helpers...")

    try:
        from main import _collect_keywords, _collect_roi_templates

        keywords = _collect_keywords(["4MU, Control", "treated"])
        print(f"✅ Keyword helper flattened to: {keywords}")

        templates = _collect_roi_templates(["{name}.roi", "{name}_ROI.zip, RoiSet_{name}.zip"])
        print(f"✅ ROI helper flattened to: {templates}")

        return True
    except Exception as e:
        print(f"❌ CLI helper test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Fiji Automated Analysis - Setup Test")
    print("=" * 40)
    
    tests = [
        test_imports,
        test_configuration,
        test_fiji_detection,
        test_macro_builder,
        test_custom_macro_template,
        test_cli_helpers
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\nTest Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The setup is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    exit(main())
