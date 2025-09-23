"""
Universal macro builder for Fiji operations.
Supports both custom macros and simplified command prompts.
"""

import os
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from config import ProcessingConfig, FileConfig


@dataclass
class ImageData:
    """Data structure containing information about the image to process."""
    input_path: str
    output_path: str
    file_extension: str
    is_bioformats: bool = False
    roi_paths: Optional[List[str]] = None
    processing_params: Optional[Dict[str, Any]] = None
    measurements_path: str = ""


@dataclass
class MacroCommand:
    """Represents a single macro command with parameters."""
    command: str
    parameters: Optional[Dict[str, Any]] = None
    comment: Optional[str] = None
    target_channels: Optional[List[int]] = None


class MacroBuilder:
    """Universal macro builder for Fiji operations."""
    
    def __init__(self, processing_config: Optional[ProcessingConfig] = None, 
                 file_config: Optional[FileConfig] = None):
        self.processing_config = processing_config or ProcessingConfig()
        self.file_config = file_config or FileConfig()
        
        # Command templates for common operations
        self.command_templates = {
            # File operations
            'open_bioformats': 'run("Bio-Formats Importer", "open=[{input_path}] autoscale color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT series_1");',
            'open_standard': 'open("{input_path}");',
            'save_tiff': 'saveAs("Tiff", "{output_path}");',
            'save_csv': 'saveAs("Measurements", "{measurements_path}");',
            
            # Image processing
            'convert_8bit': 'run("8-bit");',
            'convert_16bit': 'run("16-bit");',
            'subtract_background': 'run("Subtract Background...", "rolling={radius}");',
            'median_filter': 'run("Median...", "radius={radius}");',
            'gaussian_blur': 'run("Gaussian Blur...", "sigma={sigma}");',
            'enhance_contrast': 'run("Enhance Contrast...", "saturated={saturated} normalize");',
            'threshold': 'run("Threshold...", "method={method}");',
            
            # Measurements
            'measure': 'run("Measure");',
            'set_measurements': 'run("Set Measurements...", "area mean std min max center perimeter bounding fit shape feret\'s integrated median skewness kurtosis area_fraction stack display redirect=None decimal=3");',
            'clear_measurements': 'run("Clear Results");',
            
            # ROI operations
            'roi_manager_reset': 'roiManager("Reset");',
            'roi_manager_open': 'roiManager("Open", "{roi_path}");',
            'roi_manager_select': 'roiManager("Select", {index});',
            'roi_manager_measure': 'roiManager("Measure");',
            'make_inverse': 'run("Make Inverse");',
            'roi_manager_add': 'roiManager("Add");',
            'roi_manager_save': 'roiManager("Save", "{roi_path}");',
            'roi_manager_show_none': 'roiManager("Show None");',
            'roi_manager_deselect': 'roiManager("Deselect");',
            
            # Utility operations
            'duplicate': 'run("Duplicate...", "title={title} duplicate channels={channels} slices={slices} frames={frames}");',
            'close_all': 'run("Close All");',
            'quit': 'run("Quit");',
            
            # Display operations
            'set_option_show_all': 'setOption("Show All", false);',
            'remove_overlay': 'run("Remove Overlay");',
        }
    
    def build_macro_from_commands(self, commands: List[MacroCommand]) -> str:
        """
        Build a macro from a list of commands.
        
        Args:
            commands: List of MacroCommand objects
            
        Returns:
            Complete macro code as string
        """
        macro_lines = []
        channel_block_counter = 0

        for cmd in commands:
            if cmd.comment:
                macro_lines.append(f"// {cmd.comment}")

            template = self.command_templates.get(cmd.command, cmd.command)
            params = dict(cmd.parameters) if cmd.parameters else {}
            target_channels = list(cmd.target_channels) if cmd.target_channels else None

            if params:
                # For duplicate command, provide default values for missing parameters
                if cmd.command == 'duplicate':
                    default_params = {
                        'title': 'Copy',
                        'channels': '1',
                        'slices': '1-end',
                        'frames': '1-end'
                    }
                    # Merge provided parameters with defaults
                    params = {**default_params, **params}
                elif cmd.command == 'save_csv':
                    if 'measurements_path' not in params and 'output_path' in params:
                        params['measurements_path'] = params.pop('output_path')
                else:
                    params = dict(params)

            if target_channels is None and params:
                for channel_key in ("apply_channels", "target_channels", "channels", "channel"):
                    if channel_key in params and f"{{{channel_key}}}" not in template:
                        raw_value = params.pop(channel_key)
                        target_channels = self._parse_target_channels(raw_value)
                        break

            if params:
                macro_code = template.format(**params)
            else:
                macro_code = template

            if target_channels:
                channel_block_counter += 1
                array_name = f"_channels_{channel_block_counter}"
                index_name = f"_channel_index_{channel_block_counter}"
                channel_list = ', '.join(str(ch) for ch in target_channels)
                macro_lines.append(f"{array_name} = newArray({channel_list});")
                macro_lines.append(f"for ({index_name} = 0; {index_name} < {array_name}.length; {index_name}++) {{")
                macro_lines.append(f"    Stack.setChannel(int({array_name}[{index_name}]));")
                for line in macro_code.splitlines():
                    macro_lines.append(f"    {line}")
                macro_lines.append("}")
            else:
                macro_lines.append(macro_code)

        return '\n'.join(macro_lines)

    @staticmethod
    def _parse_target_channels(value: Any) -> Optional[List[int]]:
        """Parse channel selection definitions into a list of integers."""

        if value is None:
            return None

        if isinstance(value, list):
            parsed = [int(v) for v in value]
            return parsed if parsed else None

        if isinstance(value, tuple):
            parsed = [int(v) for v in value]
            return parsed if parsed else None

        if isinstance(value, (int, float)):
            return [int(value)]

        value_str = str(value).strip()
        if not value_str:
            return None

        if (value_str.startswith("[") and value_str.endswith("]")) or (
            value_str.startswith("(") and value_str.endswith(")")
        ):
            value_str = value_str[1:-1]

        separators = [',', ';']
        segments = [value_str]
        for sep in separators:
            segments = [
                subsegment for segment in segments for subsegment in segment.split(sep)
            ]

        refined_segments = []
        for segment in segments:
            refined_segments.extend(segment.split())

        if refined_segments:
            segments = refined_segments

        channels: List[int] = []

        for segment in segments:
            part = segment.strip()
            if not part:
                continue

            if '-' in part:
                start_str, end_str = part.split('-', 1)
                try:
                    start = int(start_str)
                    end = int(end_str)
                except ValueError as exc:
                    raise ValueError(f"Invalid channel range '{part}'") from exc
                step = 1 if end >= start else -1
                channels.extend(range(start, end + step, step))
            else:
                try:
                    channels.append(int(part))
                except ValueError as exc:
                    raise ValueError(f"Invalid channel value '{part}'") from exc

        if not channels:
            return None

        return channels
    
    def build_standard_processing_macro(self, image_data: ImageData) -> str:
        """
        Build a standard image processing macro.
        
        Args:
            image_data: ImageData object with processing information
            
        Returns:
            Complete macro code as string
        """
        commands = []
        
        # Open image
        if image_data.is_bioformats:
            commands.append(MacroCommand(
                'open_bioformats',
                {'input_path': image_data.input_path},
                'Open image using Bio-Formats'
            ))
        else:
            commands.append(MacroCommand(
                'open_standard',
                {'input_path': image_data.input_path},
                'Open image'
            ))
        
        # Setup
        commands.extend([
            MacroCommand('set_option_show_all', comment='Hide all overlays'),
            MacroCommand('remove_overlay', comment='Remove any overlays'),
            MacroCommand('roi_manager_show_none', comment='Hide ROI manager'),
            MacroCommand('roi_manager_deselect', comment='Deselect all ROIs'),
        ])
        
        commands.append(MacroCommand('orig = getTitle();', comment='Store original title'))

        # Duplicate image
        commands.append(MacroCommand(
            'duplicate',
            {
                'title': 'C1',
                'channels': self.processing_config.duplicate_channels,
                'slices': self.processing_config.duplicate_slices,
                'frames': self.processing_config.duplicate_frames
            },
            'Duplicate image for processing'
        ))
        
        # Close original and select duplicate
        commands.extend([
            MacroCommand('keep = getTitle();', comment='Store duplicate title'),
            MacroCommand('selectWindow(orig); close();', comment='Close original'),
            MacroCommand('selectWindow(keep);', comment='Select duplicate'),
        ])
        
        # Processing steps
        if self.processing_config.convert_to_8bit:
            commands.append(MacroCommand('convert_8bit', comment='Convert to 8-bit'))
        
        commands.extend([
            MacroCommand(
                'subtract_background',
                {'radius': self.processing_config.rolling_radius},
                'Subtract background'
            ),
            MacroCommand(
                'median_filter',
                {'radius': self.processing_config.median_radius},
                'Apply median filter'
            ),
            MacroCommand(
                'enhance_contrast',
                {'saturated': self.processing_config.saturated_pixels},
                'Enhance contrast'
            ),
        ])
        
        # Save result
        commands.append(MacroCommand(
            'save_tiff',
            {'output_path': image_data.output_path},
            'Save processed image'
        ))
        
        # Cleanup
        commands.extend([
            MacroCommand('close_all', comment='Close all windows'),
            MacroCommand('quit', comment='Quit Fiji'),
        ])
        
        return self.build_macro_from_commands(commands)
    
    def build_roi_processing_macro(self, image_data: ImageData) -> str:
        """
        Build a macro for ROI processing operations.
        
        Args:
            image_data: ImageData object with ROI information
            
        Returns:
            Complete macro code as string
        """
        commands = []
        
        # Open image
        if image_data.is_bioformats:
            commands.append(MacroCommand(
                'open_bioformats',
                {'input_path': image_data.input_path},
                'Open image using Bio-Formats'
            ))
        else:
            commands.append(MacroCommand(
                'open_standard',
                {'input_path': image_data.input_path},
                'Open image'
            ))
        
        # Reset ROI manager
        commands.append(MacroCommand('roi_manager_reset', comment='Reset ROI manager'))
        
        # Process each ROI
        if image_data.roi_paths:
            for roi_path in image_data.roi_paths:
                inverted_path = roi_path.replace('.roi', '_inverted.roi')
                
                commands.extend([
                    MacroCommand(
                        'roi_manager_open',
                        {'roi_path': roi_path},
                        f'Open ROI: {os.path.basename(roi_path)}'
                    ),
                    MacroCommand('roi_manager_select', {'index': 0}, 'Select first ROI'),
                    MacroCommand('make_inverse', comment='Create inverse ROI'),
                    MacroCommand('roi_manager_add', comment='Add inverse to manager'),
                    MacroCommand('roi_manager_select', {'index': 1}, 'Select inverse ROI'),
                    MacroCommand(
                        'roi_manager_save',
                        {'roi_path': inverted_path},
                        f'Save inverted ROI: {os.path.basename(inverted_path)}'
                    ),
                    MacroCommand('roi_manager_reset', comment='Reset for next ROI'),
                ])
        
        # Cleanup
        commands.extend([
            MacroCommand('close_all', comment='Close all windows'),
            MacroCommand('quit', comment='Quit Fiji'),
        ])
        
        return self.build_macro_from_commands(commands)
    
    def build_custom_macro(self, custom_commands: Union[str, List[str]], 
                          image_data: Optional[ImageData] = None) -> str:
        """
        Build a macro from custom commands or template.
        
        Args:
            custom_commands: Custom macro code or list of command strings
            image_data: Optional ImageData for template substitution
            
        Returns:
            Complete macro code as string
        """
        if isinstance(custom_commands, str):
            # If it's a template string, substitute variables
            if image_data:
                return custom_commands.format(
                    input_path=image_data.input_path,
                    output_path=image_data.output_path,
                    measurements_path=image_data.measurements_path,
                    IMG=image_data.input_path,
                    OUT=image_data.output_path,
                    CSV=image_data.measurements_path
                )
            return custom_commands
        
        elif isinstance(custom_commands, list):
            # Convert list of strings to MacroCommand objects
            commands = [MacroCommand(cmd) for cmd in custom_commands]
            return self.build_macro_from_commands(commands)
        
        else:
            raise ValueError("custom_commands must be a string or list of strings")
    
    def parse_simple_commands(self, command_string: str) -> List[MacroCommand]:
        """
        Parse a simplified command string into MacroCommand objects.
        
        Args:
            command_string: Space-separated command names
            
        Returns:
            List of MacroCommand objects
        """
        commands = []
        command_list = command_string.strip().split()
        
        for cmd_name in command_list:
            if cmd_name in self.command_templates:
                commands.append(MacroCommand(cmd_name))
            else:
                # If command not found, treat as raw command
                commands.append(MacroCommand(cmd_name))
        
        return commands
