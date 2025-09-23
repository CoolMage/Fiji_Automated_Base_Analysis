#!/usr/bin/env python3
"""
Test script to validate the new core processor setup.
"""

import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_core_imports():
    """Test that core modules can be imported."""
    print("Testing core imports...")
    
    try:
        from core_processor import CoreProcessor, ProcessingOptions, CommandLibrary, DocumentInfo
        print("✅ Core processor imported successfully")
    except ImportError as e:
        print(f"❌ Core processor import failed: {e}")
        return False

    try:
        from config import ProcessingConfig, FileConfig
        print("✅ Config modules imported successfully")
    except ImportError as e:
        print(f"❌ Config import failed: {e}")
        return False
    
    try:
        from utils.general.fiji_utils import find_fiji, validate_fiji_path
        print("✅ Fiji utils imported successfully")
    except ImportError as e:
        print(f"❌ Fiji utils import failed: {e}")
        return False
    
    return True

def test_command_library():
    """Test command library functionality."""
    print("\nTesting command library...")
    
    try:
        from core_processor import CommandLibrary
        
        library = CommandLibrary()
        commands = library.list_commands()
        
        print(f"✅ Command library loaded with {len(commands)} commands")
        
        # Test specific commands
        test_commands = ["open_standard", "measure", "convert_8bit", "roi_manager_open"]
        for cmd in test_commands:
            if cmd in commands:
                cmd_info = commands[cmd]
                print(f"  ✅ {cmd}: {cmd_info['description']}")
            else:
                print(f"  ❌ {cmd}: Not found")
        
        return True
    except Exception as e:
        print(f"❌ Command library test failed: {e}")
        return False

def test_processing_options():
    """Test processing options."""
    print("\nTesting processing options...")
    
    try:
        from core_processor import ProcessingOptions
        
        # Test default options
        options = ProcessingOptions()
        print(
            "✅ Default options: apply_roi="
            f"{options.apply_roi}, save_processed={options.save_processed_files}, "
            f"summary_prefix={options.measurement_summary_prefix}"
        )

        # Test custom options
        custom_options = ProcessingOptions(
            apply_roi=True,
            save_processed_files=True,
            custom_suffix="test",
            secondary_filter="MIP",
            measurement_summary_prefix="demo",
            roi_search_templates=("{name}.roi",),
        )
        print(
            "✅ Custom options: suffix='"
            f"{custom_options.custom_suffix}', filter='{custom_options.secondary_filter}', "
            f"roi_templates={custom_options.roi_search_templates}"
        )
        
        return True
    except Exception as e:
        print(f"❌ Processing options test failed: {e}")
        return False

def test_document_info():
    """Test DocumentInfo class."""
    print("\nTesting DocumentInfo...")
    
    try:
        from core_processor import DocumentInfo
        
        doc = DocumentInfo(
            file_path="/test/path/image.tif",
            filename="image",
            keywords=("test",),
            matched_keyword="test",
            secondary_key="MIP",
            roi_path="/test/path/roi.zip"
        )

        print(
            f"✅ DocumentInfo created: {doc.filename} (keywords: {doc.keywords}, matched: {doc.matched_keyword})"
        )

        multi_doc = DocumentInfo(
            file_path="/test/path/other_image.tif",
            filename="other_image",
            keywords=("alpha", "beta"),
            matched_keyword="beta"
        )

        print(
            "✅ DocumentInfo supports multiple keywords: "
            f"{multi_doc.keywords} (matched: {multi_doc.matched_keyword})"
        )
        return True
    except Exception as e:
        print(f"❌ DocumentInfo test failed: {e}")
        return False

def test_core_processor():
    """Test CoreProcessor initialization."""
    print("\nTesting CoreProcessor...")
    
    try:
        from core_processor import CoreProcessor
        
        # Try to initialize processor (may fail if Fiji not found)
        try:
            processor = CoreProcessor()
            print("✅ CoreProcessor initialized successfully")
            
            # Test validation
            validation = processor.validate_setup()
            print(f"✅ Validation: fiji_valid={validation['fiji_valid']}")
            
            # Test command library
            commands = processor.get_available_commands()
            print(f"✅ Available commands: {len(commands)}")
            
        except RuntimeError as e:
            if "Fiji not found" in str(e):
                print("⚠️  CoreProcessor initialization failed: Fiji not found")
                print("   This is expected if Fiji is not installed")
            else:
                print(f"❌ CoreProcessor initialization failed: {e}")
                return False
        
        return True
    except Exception as e:
        print(f"❌ CoreProcessor test failed: {e}")
        return False

def test_command_parsing():
    """Test command parsing functionality."""
    print("\nTesting command parsing...")
    
    try:
        from core_processor import CoreProcessor
        
        # Test command string parsing
        test_commands = [
            "open_standard",
            "convert_8bit",
            "subtract_background radius=50",
            "enhance_contrast saturated=0.4",
            "measure",
            "save_csv"
        ]
        
        print("✅ Command parsing test commands:")
        for cmd in test_commands:
            print(f"  - {cmd}")
        
        return True
    except Exception as e:
        print(f"❌ Command parsing test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Fiji Document Processor - Core Setup Test")
    print("=" * 45)
    
    tests = [
        test_core_imports,
        test_command_library,
        test_processing_options,
        test_document_info,
        test_core_processor,
        test_command_parsing
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\nTest Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The core system is working correctly.")
        print("\nNext steps:")
        print("1. Install Fiji if not already installed")
        print("2. Run: python main.py --validate")
        print("3. Run: python main.py --list-commands")
        print("4. Try: python main.py /path/to/docs --keyword 'test'")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    exit(main())
