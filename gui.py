"""Graphical user interface for the Fiji automated base analysis toolkit."""

# cd /Users/savvaarutsev/Documents/Проекты/Cod_Diplom/Raw_Data_Analysis/Fiji_Automated_Base_Analysis
# /opt/homebrew/bin/python3 gui.py

from __future__ import annotations

import os
import platform
import queue
import shutil
import subprocess
import threading
from typing import Iterable, List, Sequence, Optional, Union

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox
from tkinter import scrolledtext

from config import FileConfig
from core_processor import CoreProcessor, ProcessingOptions
from examples.macros_lib import MACROS_LIB
from utils.general.fiji_utils import find_fiji, detect_ffmpeg_plugin
from utils.general.macro_builder import DEFAULT_MACRO_CODE
from utils.general.measurement_summary_utils import detect_summary_naming_patterns


DEFAULT_UI_SCALE = 1.5
WINDOW_HORIZONTAL_MARGIN = 80
WINDOW_VERTICAL_MARGIN = 100


def _get_ui_scale() -> float:
    """Return a validated GUI scale from the environment."""

    raw_value = os.environ.get("FIJI_GUI_SCALE", str(DEFAULT_UI_SCALE))
    try:
        scale = float(raw_value)
    except ValueError:
        return DEFAULT_UI_SCALE
    return scale if 0.75 <= scale <= 3.0 else DEFAULT_UI_SCALE


def _scale_named_fonts(root: tk.Tk, scale: float) -> None:
    """Scale Tk's shared fonts so every current and future widget is affected."""

    for font_name in tkfont.names(root):
        font = tkfont.nametofont(font_name, root=root)
        size = int(font.cget("size"))
        if size == 0:
            continue
        scaled_size = max(1, round(abs(size) * scale))
        font.configure(size=scaled_size if size > 0 else -scaled_size)


def _selection_indicator_size(scale: float) -> int:
    """Return a readable checkbox/radio size for the current GUI scale."""

    return max(18, min(40, round(16 * scale)))


def _draw_image_line(
    image: tk.PhotoImage,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str,
    thickness: int,
) -> None:
    """Draw a short antialias-free line into a Tk image."""

    x1, y1 = start
    x2, y2 = end
    steps = max(abs(x2 - x1), abs(y2 - y1), 1)
    radius = max(0, thickness // 2)
    width = image.width()
    height = image.height()

    for step in range(steps + 1):
        x = round(x1 + (x2 - x1) * step / steps)
        y = round(y1 + (y2 - y1) * step / steps)
        for offset_x in range(-radius, radius + 1):
            for offset_y in range(-radius, radius + 1):
                target_x = x + offset_x
                target_y = y + offset_y
                if 0 <= target_x < width and 0 <= target_y < height:
                    image.put(color, (target_x, target_y))


def _build_linux_selection_images(
    root: tk.Tk,
    scale: float,
) -> dict[str, tk.PhotoImage]:
    """Create scalable checkbox and radio images for classic Tk on Linux."""

    size = _selection_indicator_size(scale)
    margin = max(1, size // 12)
    border_width = max(2, size // 10)
    border = "#666666"
    fill = "#ffffff"
    selected = "#1976d2"

    check_off = tk.PhotoImage(master=root, width=size, height=size)
    check_on = tk.PhotoImage(master=root, width=size, height=size)
    for image, inner_color in ((check_off, fill), (check_on, selected)):
        image.put(border, to=(margin, margin, size - margin, size - margin))
        image.put(
            inner_color,
            to=(
                margin + border_width,
                margin + border_width,
                size - margin - border_width,
                size - margin - border_width,
            ),
        )

    tick_thickness = max(2, size // 9)
    _draw_image_line(
        check_on,
        (round(size * 0.25), round(size * 0.52)),
        (round(size * 0.43), round(size * 0.70)),
        "#ffffff",
        tick_thickness,
    )
    _draw_image_line(
        check_on,
        (round(size * 0.43), round(size * 0.70)),
        (round(size * 0.76), round(size * 0.30)),
        "#ffffff",
        tick_thickness,
    )

    radio_off = tk.PhotoImage(master=root, width=size, height=size)
    radio_on = tk.PhotoImage(master=root, width=size, height=size)
    center = (size - 1) / 2
    outer_radius = size * 0.42
    inner_radius = outer_radius - border_width
    dot_radius = size * 0.20

    for y in range(size):
        for x in range(size):
            distance_squared = (x - center) ** 2 + (y - center) ** 2
            if distance_squared <= outer_radius**2:
                radio_off.put(border, (x, y))
                radio_on.put(selected, (x, y))
            if distance_squared <= inner_radius**2:
                radio_off.put(fill, (x, y))
                radio_on.put(fill, (x, y))
            if distance_squared <= dot_radius**2:
                radio_on.put(selected, (x, y))

    return {
        "check_off": check_off,
        "check_on": check_on,
        "radio_off": radio_off,
        "radio_on": radio_on,
    }


def _fit_window_size(
    width: int,
    height: int,
    scale: float,
    screen_width: int,
    screen_height: int,
) -> tuple[int, int]:
    """Scale a window while keeping it inside the usable screen area."""

    available_width = max(320, screen_width - WINDOW_HORIZONTAL_MARGIN)
    available_height = max(320, screen_height - WINDOW_VERTICAL_MARGIN)
    return (
        min(round(width * scale), available_width),
        min(round(height * scale), available_height),
    )


def _linux_directory_dialog(
    initial_directory: str,
    title: str,
) -> tuple[bool, Optional[str]]:
    """Use a desktop-native Linux directory picker when one is available."""

    if platform.system().lower() != "linux":
        return False, None

    initial_directory = os.path.abspath(os.path.expanduser(initial_directory))
    if not os.path.isdir(initial_directory):
        initial_directory = os.path.dirname(initial_directory)
    if not os.path.isdir(initial_directory):
        initial_directory = os.getcwd()

    zenity = shutil.which("zenity")
    if zenity:
        command = [
            zenity,
            "--file-selection",
            "--directory",
            f"--title={title}",
            f"--filename={initial_directory.rstrip(os.sep)}{os.sep}",
        ]
    else:
        kdialog = shutil.which("kdialog")
        if not kdialog:
            return False, None
        command = [
            kdialog,
            "--title",
            title,
            "--getexistingdirectory",
            initial_directory,
        ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False, None

    if result.returncode == 0:
        selected = result.stdout.strip()
        return True, selected or None
    if result.returncode == 1:
        return True, None
    return False, None


class FijiProcessorGUI:
    """Tkinter-based GUI for orchestrating Fiji document processing."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.ui_scale = _get_ui_scale()
        _scale_named_fonts(self.root, self.ui_scale)
        self._selection_images = (
            _build_linux_selection_images(self.root, self.ui_scale)
            if platform.system().lower() == "linux"
            else {}
        )
        self.root.title("Fiji Automated Base Analysis")
        self._set_window_geometry(self.root, 900, 650)

        self._processor: Optional[CoreProcessor] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._cancel_event: Optional[threading.Event] = None
        self._log_queue: "queue.Queue[str]" = queue.Queue()

        self.macro_mode_var = tk.StringVar(value="code")
        self.macro_library_var = tk.StringVar()
        self.macro_code_value = DEFAULT_MACRO_CODE
        self.macro_summary_var = tk.StringVar()
        self._library_code_overrides: dict[str, str] = {}
        self._macro_profile_applied_text_values: dict[str, str] = {}
        self._macro_profile_default_texts = {
            "secondary_filter": "",
            "processed_suffix": "processed",
            "measurements_folder": "Measurements",
            "processed_folder": "Processed_Files",
            "measurement_prefix": "measurements_summary",
        }

        self._build_widgets()
        self.root.after(100, self._process_log_queue)

    def _set_window_geometry(
        self,
        window: Union[tk.Tk, tk.Toplevel],
        width: int,
        height: int,
        *,
        min_width: int = 560,
        min_height: int = 420,
    ) -> None:
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        fitted_width, fitted_height = _fit_window_size(
            width,
            height,
            self.ui_scale,
            screen_width,
            screen_height,
        )
        minimum_width = min(round(min_width * self.ui_scale), fitted_width)
        minimum_height = min(round(min_height * self.ui_scale), fitted_height)
        window.minsize(minimum_width, minimum_height)

        offset_x = max(0, (screen_width - fitted_width) // 2)
        offset_y = max(0, (screen_height - fitted_height) // 3)
        window.geometry(
            f"{fitted_width}x{fitted_height}+{offset_x}+{offset_y}"
        )

    def _checkbutton(self, parent: tk.Widget, **kwargs: object) -> tk.Checkbutton:
        widget = tk.Checkbutton(parent, **kwargs)
        if self._selection_images:
            widget.configure(
                image=self._selection_images["check_off"],
                selectimage=self._selection_images["check_on"],
                compound=tk.LEFT,
                indicatoron=False,
                relief=tk.FLAT,
                offrelief=tk.FLAT,
                overrelief=tk.FLAT,
                borderwidth=0,
                highlightthickness=1,
                anchor=tk.W,
                padx=max(3, round(3 * self.ui_scale)),
                pady=max(1, round(2 * self.ui_scale)),
            )
        return widget

    def _radiobutton(self, parent: tk.Widget, **kwargs: object) -> tk.Radiobutton:
        widget = tk.Radiobutton(parent, **kwargs)
        if self._selection_images:
            widget.configure(
                image=self._selection_images["radio_off"],
                selectimage=self._selection_images["radio_on"],
                compound=tk.LEFT,
                indicatoron=False,
                relief=tk.FLAT,
                offrelief=tk.FLAT,
                overrelief=tk.FLAT,
                borderwidth=0,
                highlightthickness=1,
                anchor=tk.W,
                padx=max(3, round(3 * self.ui_scale)),
                pady=max(1, round(2 * self.ui_scale)),
            )
        return widget

    # ------------------------------------------------------------------
    # Widget construction helpers
    # ------------------------------------------------------------------
    def _build_widgets(self) -> None:
        container = tk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        main_frame = tk.Frame(canvas, padx=10, pady=10)
        frame_window = canvas.create_window((0, 0), window=main_frame, anchor="nw")

        def _configure_scroll_region(event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _resize_frame(event: tk.Event) -> None:
            canvas.itemconfigure(frame_window, width=event.width)

        main_frame.bind("<Configure>", _configure_scroll_region)
        canvas.bind("<Configure>", _resize_frame)
        self._enable_mousewheel(canvas)

        # Path configuration -------------------------------------------------
        path_frame = tk.LabelFrame(main_frame, text="Paths", padx=10, pady=10)
        path_frame.pack(fill=tk.X, expand=False, pady=(0, 10))

        self.base_path_var = tk.StringVar()
        self.fiji_path_var = tk.StringVar()

        self._add_labeled_entry(
            path_frame,
            "Base directory:",
            self.base_path_var,
            0,
            browse_command=self._browse_directory,
        )
        self._add_labeled_entry(
            path_frame,
            "Fiji / ImageJ executable:",
            self.fiji_path_var,
            1,
            browse_command=lambda: self._browse_file(self.fiji_path_var),
        )
        tk.Button(path_frame, text="Auto-detect", command=self._auto_detect_fiji).grid(
            row=1, column=3, padx=(5, 0)
        )

        # Keyword configuration ---------------------------------------------
        keyword_frame = tk.LabelFrame(main_frame, text="Keywords", padx=10, pady=10)
        keyword_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 10))

        self.keyword_var = tk.StringVar()
        keyword_entry = tk.Entry(keyword_frame, textvariable=self.keyword_var)
        keyword_entry.grid(row=0, column=0, sticky="we")

        add_keyword_btn = tk.Button(keyword_frame, text="Add", command=self._add_keyword)
        add_keyword_btn.grid(row=0, column=1, padx=5)

        remove_keyword_btn = tk.Button(
            keyword_frame, text="Remove Selected", command=self._remove_selected_keyword
        )
        remove_keyword_btn.grid(row=0, column=2)

        keyword_frame.grid_columnconfigure(0, weight=1)

        self.keyword_listbox = tk.Listbox(keyword_frame, height=4, selectmode=tk.EXTENDED)
        self.keyword_listbox.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(5, 0))

        keyword_frame.grid_rowconfigure(1, weight=1)

        # ROI templates ------------------------------------------------------
        roi_frame = tk.LabelFrame(main_frame, text="ROI Templates", padx=10, pady=10)
        roi_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 10))

        self.roi_var = tk.StringVar()
        roi_entry = tk.Entry(roi_frame, textvariable=self.roi_var)
        roi_entry.grid(row=0, column=0, sticky="we")

        add_roi_btn = tk.Button(roi_frame, text="Add", command=self._add_roi_template)
        add_roi_btn.grid(row=0, column=1, padx=5)

        remove_roi_btn = tk.Button(
            roi_frame, text="Remove Selected", command=self._remove_selected_roi_template
        )
        remove_roi_btn.grid(row=0, column=2)

        roi_frame.grid_columnconfigure(0, weight=1)

        self.roi_listbox = tk.Listbox(roi_frame, height=3, selectmode=tk.EXTENDED)
        self.roi_listbox.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(5, 0))

        roi_frame.grid_rowconfigure(1, weight=1)

        # Custom filename extractors -----------------------------------------
        extract_frame = tk.LabelFrame(main_frame, text="Custom Filename Placeholders", padx=10, pady=10)
        extract_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 10))

        tk.Label(extract_frame, text="Name (used as {name} in macro)").grid(row=0, column=0, sticky="w")
        tk.Label(extract_frame, text="Mask (X=digits, Y=letters)").grid(row=0, column=1, sticky="w")

        self.extract_name_var = tk.StringVar()
        self.extract_mask_var = tk.StringVar()
        name_entry = tk.Entry(extract_frame, textvariable=self.extract_name_var)
        mask_entry = tk.Entry(extract_frame, textvariable=self.extract_mask_var)
        name_entry.grid(row=1, column=0, sticky="we", padx=(0,5))
        mask_entry.grid(row=1, column=1, sticky="we")

        tk.Button(extract_frame, text="Add", command=self._add_custom_extractor).grid(row=1, column=2, padx=(5,0))
        tk.Button(extract_frame, text="Remove Selected", command=self._remove_selected_extractor).grid(row=1, column=3, padx=(5,0))

        extract_frame.grid_columnconfigure(0, weight=1)
        extract_frame.grid_columnconfigure(1, weight=2)

        self.extract_listbox = tk.Listbox(extract_frame, height=4, selectmode=tk.EXTENDED)
        self.extract_listbox.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=(5, 0))
        extract_frame.grid_rowconfigure(2, weight=1)

        # Processing options -------------------------------------------------
        options_frame = tk.LabelFrame(main_frame, text="Processing Options", padx=10, pady=10)
        options_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 10))

        self.secondary_filter_var = tk.StringVar()
        self.suffix_var = tk.StringVar(value="processed")
        self.measurements_folder_var = tk.StringVar(value="Measurements")
        self.processed_folder_var = tk.StringVar(value="Processed_Files")
        self.measurement_prefix_var = tk.StringVar(value="measurements_summary")

        self.apply_roi_var = tk.BooleanVar(value=False)
        self.save_processed_var = tk.BooleanVar(value=False)
        self.save_measurements_var = tk.BooleanVar(value=False)
        self.verbose_var = tk.BooleanVar(value=False)
        self.generate_summary_var = tk.BooleanVar(value=True)
        self.generate_slice_average_var = tk.BooleanVar(value=False)
        self.generate_animal_average_var = tk.BooleanVar(value=False)
        self.cut_prefix_var = tk.StringVar()
        self.group_animal_prefix_vars: dict[str, tk.StringVar] = {}
        self.group_prefix_rows_frame: Optional[tk.Frame] = None

        row = 0
        row = self._add_option_entry(
            options_frame,
            row,
            "Secondary filter:",
            self.secondary_filter_var,
            tooltip="Optional secondary substring that must also be present.",
        )
        row = self._add_macro_configuration(options_frame, row)
        row = self._add_option_entry(options_frame, row, "Processed suffix:", self.suffix_var)
        row = self._add_option_entry(
            options_frame, row, "Measurements folder:", self.measurements_folder_var
        )
        row = self._add_option_entry(
            options_frame, row, "Processed folder:", self.processed_folder_var
        )
        row = self._add_option_entry(
            options_frame, row, "Measurement prefix:", self.measurement_prefix_var
        )

        checkbox_frame = tk.Frame(options_frame)
        checkbox_frame.grid(row=row, column=0, columnspan=2, sticky="w", pady=(5, 0))

        self._checkbutton(
            checkbox_frame, text="Apply ROI templates", variable=self.apply_roi_var
        ).pack(anchor="w")
        self._checkbutton(
            checkbox_frame, text="Save processed images", variable=self.save_processed_var
        ).pack(anchor="w")
        self._checkbutton(
            checkbox_frame, text="Save measurement CSV", variable=self.save_measurements_var
        ).pack(anchor="w")
        self._checkbutton(
            checkbox_frame, text="Verbose logging", variable=self.verbose_var
        ).pack(anchor="w")
        self._checkbutton(
            checkbox_frame, text="Generate measurement summary", variable=self.generate_summary_var
        ).pack(anchor="w")

        # Summary aggregation ------------------------------------------------
        summary_frame = tk.LabelFrame(main_frame, text="Summary Aggregation", padx=10, pady=10)
        summary_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 10))

        tk.Label(
            summary_frame,
            text=(
                "Auto-detect animal prefixes from filenames inside each keyword group and optionally"
                " build mean tables per slice and per animal."
            ),
            justify=tk.LEFT,
            wraplength=760,
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        self._checkbutton(
            summary_frame,
            text="Generate per-slice mean summary",
            variable=self.generate_slice_average_var,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self._checkbutton(
            summary_frame,
            text="Generate per-animal mean summary",
            variable=self.generate_animal_average_var,
        ).grid(row=2, column=0, columnspan=3, sticky="w")

        tk.Label(summary_frame, text="Section prefix:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        tk.Entry(summary_frame, textvariable=self.cut_prefix_var).grid(
            row=3, column=1, sticky="we", padx=(5, 5), pady=(8, 0)
        )
        tk.Button(
            summary_frame,
            text="Auto-detect from filenames",
            command=lambda: self._auto_detect_summary_patterns(silent=False, overwrite=True),
        ).grid(row=3, column=2, sticky="e", pady=(8, 0))

        tk.Label(
            summary_frame,
            text="Animal prefixes by keyword:",
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self.group_prefix_rows_frame = tk.Frame(summary_frame)
        self.group_prefix_rows_frame.grid(row=5, column=0, columnspan=3, sticky="we", pady=(4, 0))
        summary_frame.grid_columnconfigure(1, weight=1)

        # Action buttons -----------------------------------------------------
        action_frame = tk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(0, 10))

        self.validate_button = tk.Button(action_frame, text="Validate Setup", command=self._validate_setup)
        self.validate_button.pack(side=tk.LEFT)

        self.list_placeholders_button = tk.Button(
            action_frame, text="List Placeholders", command=self._list_placeholders
        )
        self.list_placeholders_button.pack(side=tk.LEFT, padx=5)

        self.run_button = tk.Button(action_frame, text="Run Processing", command=self._run_processing)
        self.run_button.pack(side=tk.RIGHT)
        self.stop_button = tk.Button(action_frame, text="Stop", command=self._stop_processing)
        self.stop_button.pack(side=tk.RIGHT, padx=(5, 5))
        self.stop_button.configure(state=tk.DISABLED)

        # Log output ---------------------------------------------------------
        log_frame = tk.LabelFrame(main_frame, text="Log", padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_widget = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state="disabled")
        self.log_widget.pack(fill=tk.BOTH, expand=True)

        self._update_macro_summary()
        self._refresh_group_animal_prefix_rows()

    def _add_labeled_entry(
        self,
        parent: tk.Widget,
        label: str,
        variable: tk.StringVar,
        row: int,
        *,
        browse_command=None,
    ) -> None:
        tk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
        entry = tk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="we", padx=(5, 5))
        parent.grid_columnconfigure(1, weight=1)
        if browse_command is not None:
            tk.Button(parent, text="Browse", command=browse_command).grid(row=row, column=2)

    def _add_option_entry(
        self,
        parent: tk.Widget,
        row: int,
        label: str,
        variable: tk.StringVar,
        *,
        tooltip: Optional[str] = None,
    ) -> int:
        tk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
        entry = tk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="we", padx=(5, 0), pady=(0, 3))
        parent.grid_columnconfigure(1, weight=1)
        return row + 1

    def _add_macro_configuration(self, parent: tk.Widget, row: int) -> int:
        tk.Label(parent, text="Macro configuration:").grid(row=row, column=0, sticky="w")
        summary = tk.Label(
            parent,
            textvariable=self.macro_summary_var,
            anchor="w",
            relief=tk.SUNKEN,
            padx=5,
            pady=2,
        )
        summary.grid(row=row, column=1, sticky="we", padx=(5, 0), pady=(0, 3))
        tk.Button(parent, text="Configure...", command=self._open_macro_window).grid(
            row=row, column=2, padx=(5, 0)
        )
        tk.Button(parent, text="Apply Defaults", command=self._apply_selected_macro_profile).grid(
            row=row, column=3, padx=(5, 0)
        )
        parent.grid_columnconfigure(1, weight=1)
        return row + 1

    def _enable_mousewheel(self, canvas: tk.Canvas) -> None:
        def _on_mousewheel(event: tk.Event) -> None:
            if event.delta:
                delta = int(-event.delta / 120) if abs(event.delta) >= 120 else -1 if event.delta > 0 else 1
                canvas.yview_scroll(delta, "units")

        def _on_scroll_up(event: tk.Event) -> None:
            canvas.yview_scroll(-1, "units")

        def _on_scroll_down(event: tk.Event) -> None:
            canvas.yview_scroll(1, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_scroll_up)
        canvas.bind_all("<Button-5>", _on_scroll_down)

    def _open_macro_window(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Configure Macro")
        self._set_window_geometry(window, 640, 520)
        window.transient(self.root)
        window.grab_set()

        mode_var = tk.StringVar(value=self.macro_mode_var.get())
        library_names = sorted(MACROS_LIB.keys())
        initial_library = self.macro_library_var.get() or (library_names[0] if library_names else "")
        library_var = tk.StringVar(value=initial_library)

        mode_frame = tk.LabelFrame(window, text="Macro input mode", padx=10, pady=10)
        mode_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        # Pack the action bar before the editor so Save/Cancel always remain visible.
        button_frame = tk.Frame(window, pady=10)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 10))

        def _show_mode() -> None:
            selected = mode_var.get()
            for frame in mode_frames.values():
                frame.pack_forget()
            frame = mode_frames.get(selected, code_frame)
            frame.pack(fill=tk.BOTH, expand=True)
            if frame is code_frame:
                code_text.focus_set()
            else:
                window.focus_set()

        for label, value in (
            ("Full macro code", "code"),
            ("Library macro", "library"),
        ):
            self._radiobutton(
                mode_frame,
                text=label,
                variable=mode_var,
                value=value,
                command=_show_mode,
            ).pack(
                anchor="w"
            )

        content_frame = tk.Frame(window, padx=10, pady=10)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Full macro code input -------------------------------------------------
        code_frame = tk.Frame(content_frame)
        tk.Label(
            code_frame,
            text=(
                "Paste the complete Fiji macro code."
                " Template placeholders such as {input_path} are supported."
            ),
            wraplength=560,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 5))
        code_text = scrolledtext.ScrolledText(code_frame, wrap=tk.WORD, height=15)
        code_text.insert("1.0", self.macro_code_value)
        code_text.pack(fill=tk.BOTH, expand=True)

        # Macro library selection ----------------------------------------------
        library_frame = tk.Frame(content_frame)
        tk.Label(
            library_frame,
            text=(
                "Select a macro template from the bundled library."
                " The template will be formatted with document details at runtime."
            ),
            wraplength=560,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 5))
        library_code_text: Optional[scrolledtext.ScrolledText] = None

        def _get_library_code(name: str) -> str:
            if not name:
                return ""
            override = self._library_code_overrides.get(name)
            if override is not None:
                return override
            return MACROS_LIB.get(name, "")

        def _update_library_text(*_: object) -> None:
            if library_code_text is None:
                return
            code_value = _get_library_code(library_var.get().strip())
            library_code_text.delete("1.0", tk.END)
            library_code_text.insert("1.0", code_value)
            library_code_text.edit_modified(False)

        if library_names:
            option_menu = tk.OptionMenu(
                library_frame,
                library_var,
                *library_names,
                command=lambda *_: _update_library_text(),
            )
            option_menu.configure(anchor="w", width=45)
            option_menu.pack(fill=tk.X, pady=(0, 5))
            library_code_text = scrolledtext.ScrolledText(
                library_frame,
                wrap=tk.WORD,
                height=15,
            )
            library_code_text.pack(fill=tk.BOTH, expand=True)
            _update_library_text()
        else:
            tk.Label(
                library_frame,
                text="No library macros available.",
                fg="red",
            ).pack(anchor="w")

        mode_frames = {
            "code": code_frame,
            "library": library_frame,
        }

        window.focus_set()
        _show_mode()

        def _apply() -> None:
            previous_mode = self.macro_mode_var.get()
            previous_library = self.macro_library_var.get().strip()
            self.macro_mode_var.set(mode_var.get())
            self.macro_code_value = code_text.get("1.0", tk.END).strip()
            selected_library = ""
            if library_names:
                selected_library = library_var.get().strip()
                self.macro_library_var.set(selected_library)
                if library_code_text is not None:
                    library_code_value = library_code_text.get("1.0", tk.END).strip()
                    default_code = MACROS_LIB.get(selected_library, "").strip()
                    if library_code_value == default_code:
                        self._library_code_overrides.pop(selected_library, None)
                    else:
                        self._library_code_overrides[selected_library] = library_code_value
            else:
                self.macro_library_var.set("")
            if self.macro_mode_var.get() == "library" and selected_library:
                self._apply_macro_profile(
                    selected_library,
                    overwrite_text_fields=(
                        previous_mode != "library" or previous_library != selected_library
                    ),
                    source_label="selected macro",
                )
            self._update_macro_summary()
            window.destroy()

        tk.Button(button_frame, text="Cancel", command=window.destroy).pack(side=tk.RIGHT, padx=(5, 0))
        tk.Button(button_frame, text="Save", command=_apply).pack(side=tk.RIGHT)

    def _update_macro_summary(self) -> None:
        mode = self.macro_mode_var.get()
        if mode == "code":
            length = len(self.macro_code_value.strip())
            summary = f"{length} character(s)" if length else "(none)"
            text = f"Macro code: {summary}"
        else:
            name = self.macro_library_var.get().strip()
            summary = name or "(none selected)"
            if name and name in self._library_code_overrides:
                text = f"Library macro: {summary} (customized)"
            else:
                text = f"Library macro: {summary}"
        self.macro_summary_var.set(text)

    def _get_selected_library_macro_name(self) -> str:
        if self.macro_mode_var.get() != "library":
            return ""
        return self.macro_library_var.get().strip()

    def _apply_selected_macro_profile(self) -> None:
        macro_name = self._get_selected_library_macro_name()
        if not macro_name:
            messagebox.showwarning(
                "Library macro required",
                "Select a bundled library macro first to apply its recommended processing settings.",
            )
            return
        self._apply_macro_profile(
            macro_name,
            overwrite_text_fields=True,
            source_label="Apply Defaults",
        )

    def _apply_macro_profile(
        self,
        macro_name: str,
        *,
        overwrite_text_fields: bool,
        source_label: str,
    ) -> bool:
        profile = MACROS_LIB.get_profile(macro_name)
        if profile is None:
            self._log(f"No GUI defaults are defined for macro '{macro_name}'.")
            return False

        changes: list[str] = []

        boolean_fields = (
            ("Apply ROI templates", self.apply_roi_var, profile.apply_roi_templates),
            ("Save processed images", self.save_processed_var, profile.save_processed_images),
            ("Save measurement CSV", self.save_measurements_var, profile.save_measurement_csv),
            (
                "Generate measurement summary",
                self.generate_summary_var,
                profile.generate_measurement_summary,
            ),
        )
        for label, variable, value in boolean_fields:
            if value is None:
                continue
            if variable.get() != value:
                variable.set(value)
                changes.append(f"{label}={'on' if value else 'off'}")

        if profile.save_measurement_csv is False or profile.generate_measurement_summary is False:
            if self.generate_slice_average_var.get():
                self.generate_slice_average_var.set(False)
                changes.append("Generate per-slice mean summary=off")
            if self.generate_animal_average_var.get():
                self.generate_animal_average_var.set(False)
                changes.append("Generate per-animal mean summary=off")

        text_fields = (
            (
                "secondary_filter",
                "Secondary filter",
                self.secondary_filter_var,
                profile.secondary_filter,
            ),
            (
                "processed_suffix",
                "Processed suffix",
                self.suffix_var,
                profile.processed_suffix,
            ),
            (
                "measurements_folder",
                "Measurements folder",
                self.measurements_folder_var,
                profile.measurements_folder,
            ),
            (
                "processed_folder",
                "Processed folder",
                self.processed_folder_var,
                profile.processed_folder,
            ),
            (
                "measurement_prefix",
                "Measurement prefix",
                self.measurement_prefix_var,
                profile.measurement_prefix,
            ),
        )
        for key, label, variable, value in text_fields:
            if value is None:
                continue
            current = variable.get().strip()
            previous_auto = self._macro_profile_applied_text_values.get(key)
            default_value = self._macro_profile_default_texts.get(key, "")
            should_apply = overwrite_text_fields or current in {"", default_value} or (
                previous_auto is not None and current == previous_auto
            )
            if should_apply:
                if current != value:
                    variable.set(value)
                    changes.append(f"{label}='{value}'")
                self._macro_profile_applied_text_values[key] = value

        if changes:
            self._log(
                f"{source_label} updated processing options for '{macro_name}': "
                + ", ".join(changes)
            )
        else:
            self._log(f"{source_label} found no processing-option changes for '{macro_name}'.")
        if profile.note:
            self._log(f"Macro requirements: {profile.note}")
        return True

    # ------------------------------------------------------------------
    # Path utilities
    # ------------------------------------------------------------------
    def _browse_directory(self, variable: tk.StringVar | None = None) -> None:
        target = variable or self.base_path_var
        initial = target.get() or os.getcwd()
        handled, directory = _linux_directory_dialog(
            initial,
            "Select base directory",
        )
        if not handled:
            directory = filedialog.askdirectory(
                parent=self.root,
                initialdir=initial,
                mustexist=True,
                title="Select base directory",
            )
        if directory:
            target.set(directory)
            if target is self.base_path_var:
                self._auto_detect_summary_patterns(silent=True, overwrite=False)

    def _browse_file(self, variable: tk.StringVar) -> None:
        initial = variable.get() or os.getcwd()
        path = filedialog.askopenfilename(initialdir=initial, title="Select file")
        if path:
            variable.set(path)

    def _auto_detect_fiji(self) -> None:
        detected_path = find_fiji()
        if detected_path:
            self.fiji_path_var.set(detected_path)
            self._log(f"Detected Fiji / ImageJ executable: {detected_path}")
            messagebox.showinfo(
                "Fiji / ImageJ detected",
                f"Executable found at:\n{detected_path}",
            )
        else:
            messagebox.showwarning(
                "Fiji / ImageJ not found",
                "Unable to automatically locate a Fiji or ImageJ executable."
                "\nPlease specify the path manually.",
            )

    # ------------------------------------------------------------------
    # Keyword & ROI helpers
    # ------------------------------------------------------------------
    def _add_keyword(self) -> None:
        value = self.keyword_var.get().strip()
        if not value:
            return
        for keyword in self._split_entries(value):
            if keyword:
                self.keyword_listbox.insert(tk.END, keyword)
        self.keyword_var.set("")
        self._refresh_group_animal_prefix_rows()
        self._auto_detect_summary_patterns(silent=True, overwrite=False)

    def _remove_selected_keyword(self) -> None:
        self._remove_selected(self.keyword_listbox)
        self._refresh_group_animal_prefix_rows()
        self._auto_detect_summary_patterns(silent=True, overwrite=False)

    def _add_roi_template(self) -> None:
        value = self.roi_var.get().strip()
        if not value:
            return
        for template in self._split_entries(value):
            if template:
                self.roi_listbox.insert(tk.END, template)
        self.roi_var.set("")

    def _remove_selected_roi_template(self) -> None:
        self._remove_selected(self.roi_listbox)

    def _remove_selected(self, listbox: tk.Listbox) -> None:
        selection = listbox.curselection()
        for index in reversed(selection):
            listbox.delete(index)

    @staticmethod
    def _split_entries(value: str) -> Iterable[str]:
        return [part.strip() for part in value.split(",") if part.strip()]

    @staticmethod
    def _ffmpeg_plugin_available(fiji_path: Optional[str]) -> bool:
        if not fiji_path:
            return False
        return detect_ffmpeg_plugin(fiji_path)

    # ------------------------------------------------------------------
    # Logging utilities
    # ------------------------------------------------------------------
    def _log(self, message: str) -> None:
        self._log_queue.put(message)

    def _process_log_queue(self) -> None:
        while True:
            try:
                message = self._log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_widget.configure(state="normal")
            self.log_widget.insert(tk.END, message + "\n")
            self.log_widget.configure(state="disabled")
            self.log_widget.see(tk.END)
        self.root.after(100, self._process_log_queue)

    # ------------------------------------------------------------------
    # Button actions
    # ------------------------------------------------------------------
    def _validate_setup(self) -> None:
        try:
            processor = self._get_processor()
            self._log("Validating Fiji / ImageJ setup...")
            validation = processor.validate_setup()
            self._log("Fiji / ImageJ validation complete.")

            fiji_path = validation.get("fiji_path")
            if fiji_path:
                ffmpeg_ok = self._ffmpeg_plugin_available(fiji_path)
                self._log(f"FFMPEG plugin available: {ffmpeg_ok}")
                if not ffmpeg_ok:
                    messagebox.showwarning(
                        "FFMPEG plugin missing",
                        "Movie (FFMPEG) plugin was not found.\n"
                        "Install a compatible plugin if MP4 processing is required.",
                    )
            details = [
                f"Fiji / ImageJ path: {validation['fiji_path']}",
                f"Executable valid: {validation['fiji_valid']}",
                f"Supported extensions: {', '.join(validation['supported_extensions'])}",
            ]
            self._log("\n".join(details))
            messagebox.showinfo("Validation", "Setup validation complete. See log for details.")
        except Exception as exc:  # pragma: no cover - GUI fallback
            messagebox.showerror("Validation error", str(exc))

    def _list_placeholders(self) -> None:
        placeholder_groups = [
            (
                "{input_path}, {input_path_fiji}, {img_path_fiji}, {img_path}, {IMG}",
                "Fiji-formatted path to the current image.",
            ),
            (
                "{input_path_native}, {img_path_native}",
                "Native filesystem path to the current image.",
            ),
            (
                "{output_path}, {output_path_fiji}, {out_tiff}, {out_image}, {OUT}",
                "Fiji path for processed image output (created when processed files are saved).",
            ),
            (
                "{output_path_native}",
                "Native filesystem path to the processed image output.",
            ),
            (
                "{measurements_path}, {measurements_path_fiji}, {out_csv}, {CSV}",
                "Fiji path to the measurement export (created when measurements are saved).",
            ),
            (
                "{measurements_path_native}",
                "Native filesystem path to the measurement export.",
            ),
            (
                "{document_name}, {file_stem}",
                "Filename without extension for the current document.",
            ),
            (
                "{roi_paths}, {roi_paths_native}",
                "Lists of ROI paths in Fiji-formatted and native styles.",
            ),
            (
                "{roi_paths_joined}, {roi_paths_native_joined}",
                "Newline-joined versions of the ROI path lists.",
            ),
            (
                "{roi_manager_open_block}, {roi_manager_open_native_block}",
                "Convenience blocks that open every ROI path with roiManager().",
            ),
            (
                "{img_dir_fiji}, {img_dir_fiji_slash}, {img_dir_native}",
                "Directories containing the source image (Fiji formatted and native).",
            ),
            (
                "{output_dir_fiji}, {output_dir_fiji_slash}, {output_dir_native}",
                "Directories for processed outputs (Fiji formatted and native).",
            ),
            (
                "{measurements_dir_fiji}, {measurements_dir_fiji_slash}, {measurements_dir_native}",
                "Directories for measurement exports (Fiji formatted and native).",
            ),
        ]

        window = tk.Toplevel(self.root)
        window.title("Macro Placeholders")
        self._set_window_geometry(window, 520, 480)

        text = scrolledtext.ScrolledText(window, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)

        intro = (
            "Macro templates accept the following placeholders. "
            "Each placeholder is substituted before the macro runs:\n\n"
        )
        text.insert(tk.END, intro)

        for names, description in placeholder_groups:
            text.insert(tk.END, f"{names}\n")
            text.insert(tk.END, f"  {description}\n\n")

        # User-defined placeholders info
        custom_map = {}
        # Safely read current custom extractors if listbox exists
        try:
            for idx in range(self.extract_listbox.size()):
                entry = self.extract_listbox.get(idx)
                if "=" in entry:
                    name, mask = entry.split("=", 1)
                    custom_map[name.strip()] = mask.strip()
        except Exception:
            custom_map = {}

        text.insert(tk.END, "User-defined placeholders (from filename masks):\n")
        if custom_map:
            for name, mask in custom_map.items():
                text.insert(tk.END, f"  {{{name}}}  — mask: {mask}\n")
        else:
            text.insert(tk.END, "  (none configured)\n")

        text.configure(state="disabled")

    def _run_processing(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            messagebox.showinfo("Processing", "Processing is already running.")
            return

        base_path = self.base_path_var.get().strip()
        if not base_path:
            messagebox.showwarning("Missing information", "Please select a base directory.")
            return

        keywords = self._collect_listbox_values(self.keyword_listbox)
        if not keywords:
            messagebox.showwarning("Missing information", "Please add at least one keyword.")
            return

        keyword_input: Union[str, Sequence[str]] = (
            keywords[0] if len(keywords) == 1 else list(keywords)
        )

        base_path = os.path.abspath(os.path.expanduser(base_path))

        if self.generate_slice_average_var.get() or self.generate_animal_average_var.get():
            self._auto_detect_summary_patterns(silent=True, overwrite=False)

        try:
            macro_input = self._get_macro_input()
        except ValueError as exc:
            messagebox.showerror("Macro configuration", str(exc))
            return

        if not macro_input:
            messagebox.showerror(
                "Macro configuration",
                "Paste complete Fiji macro code or select a library macro.",
            )
            return

        options = self._gather_processing_options()
        processor = self._get_processor()
        args = dict(
            base_path=base_path,
            keyword=keyword_input,
            macro_code=macro_input,
            options=options,
            verbose=self.verbose_var.get(),
        )

        self._log("Starting processing...\n")
        self._set_running(True)

        def worker() -> None:
            try:
                result = processor.process_documents(**args, cancel_event=self._cancel_event)
                if result.get("success"):
                    self._log("✅ Processing completed successfully!")
                    processed = result.get("processed_documents", [])
                    self._log(f"Processed documents: {len(processed)}")
                    if processed and self.verbose_var.get():
                        for entry in processed:
                            match_note = (
                                f" (matched keyword: {entry['matched_keyword']})"
                                if entry.get("matched_keyword")
                                else ""
                            )
                            secondary_note = (
                                f" [secondary: {entry['secondary_key']}]"
                                if entry.get("secondary_key")
                                else ""
                            )
                            self._log(f"  - {entry['filename']}{match_note}{secondary_note}")
                    measurements = result.get("measurements")
                    if measurements:
                        self._log(
                            f"Measurements recorded for {len(measurements)} document(s)."
                        )
                    summary_outputs = result.get("summary_outputs") or {}
                    if summary_outputs:
                        label_map = {
                            "summary_csv": "Summary CSV",
                            "slice_summary_csv": "Per-slice mean CSV",
                            "animal_summary_csv": "Per-animal mean CSV",
                        }
                        for label, path in summary_outputs.items():
                            self._log(f"{label_map.get(label, label)}: {path}")
                    failed = result.get("failed_documents") or []
                    if failed:
                        self._log(
                            f"Completed with {len(failed)} warning(s). See details below:"
                        )
                        for entry in failed:
                            match_note = (
                                f" (matched keyword: {entry['matched_keyword']})"
                                if entry.get("matched_keyword")
                                else ""
                            )
                            secondary_note = (
                                f" [secondary: {entry['secondary_key']}]"
                                if entry.get("secondary_key")
                                else ""
                            )
                            self._log(
                                f"  - {entry['filename']}{match_note}{secondary_note}: {entry['error']}"
                            )
                else:
                    failed = result.get("failed_documents") or []
                    processed = result.get("processed_documents") or []
                    error_message = result.get("error")
                    if failed:
                        self._log(
                            f"❌ Processing completed with {len(failed)} failure(s)."
                            f" Processed: {len(processed)}"
                        )
                        for entry in failed:
                            match_note = (
                                f" (matched keyword: {entry['matched_keyword']})"
                                if entry.get("matched_keyword")
                                else ""
                            )
                            secondary_note = (
                                f" [secondary: {entry['secondary_key']}]"
                                if entry.get("secondary_key")
                                else ""
                            )
                            self._log(
                                f"  - {entry['filename']}{match_note}{secondary_note}: {entry['error']}"
                            )
                    else:
                        self._log(f"❌ Processing failed: {error_message}")
            except Exception as exc:  # pragma: no cover - background thread fallback
                self._log(f"Error: {exc}")
            finally:
                self._set_running(False)

        # Prepare/clear cancel event
        self._cancel_event = threading.Event()
        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def _stop_processing(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            if self._cancel_event is not None:
                self._cancel_event.set()
            self._log("Cancellation requested. Attempting to stop...")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _collect_listbox_values(self, listbox: tk.Listbox) -> List[str]:
        return [listbox.get(idx) for idx in range(listbox.size())]

    def _refresh_group_animal_prefix_rows(self) -> None:
        if self.group_prefix_rows_frame is None:
            return

        keywords = self._collect_listbox_values(self.keyword_listbox)
        existing_values = {
            keyword: variable.get().strip()
            for keyword, variable in self.group_animal_prefix_vars.items()
        }
        self.group_animal_prefix_vars = {
            keyword: tk.StringVar(value=existing_values.get(keyword, ""))
            for keyword in keywords
        }

        for child in self.group_prefix_rows_frame.winfo_children():
            child.destroy()

        if not keywords:
            tk.Label(
                self.group_prefix_rows_frame,
                text="Add keyword groups to enable auto-detected animal prefixes.",
                fg="gray40",
                justify=tk.LEFT,
            ).grid(row=0, column=0, sticky="w")
            return

        self.group_prefix_rows_frame.grid_columnconfigure(1, weight=1)
        for row, keyword in enumerate(keywords):
            tk.Label(
                self.group_prefix_rows_frame,
                text=f"{keyword}:",
            ).grid(row=row, column=0, sticky="w", pady=(0, 3))
            tk.Entry(
                self.group_prefix_rows_frame,
                textvariable=self.group_animal_prefix_vars[keyword],
            ).grid(row=row, column=1, sticky="we", padx=(5, 0), pady=(0, 3))

    def _collect_group_animal_prefixes(self) -> dict[str, str]:
        return {
            keyword: variable.get().strip()
            for keyword, variable in self.group_animal_prefix_vars.items()
            if variable.get().strip()
        }

    def _auto_detect_summary_patterns(
        self,
        *,
        silent: bool = True,
        overwrite: bool = False,
    ) -> None:
        base_path = self.base_path_var.get().strip()
        keywords = self._collect_listbox_values(self.keyword_listbox)
        if not base_path or not keywords:
            return

        self._refresh_group_animal_prefix_rows()

        try:
            detected = detect_summary_naming_patterns(
                os.path.abspath(os.path.expanduser(base_path)),
                keywords,
                secondary_filter=self.secondary_filter_var.get().strip() or None,
                supported_extensions=FileConfig().supported_extensions,
            )
        except Exception as exc:
            if not silent:
                messagebox.showerror("Auto-detect summary patterns", str(exc))
            return

        updated_keywords: List[str] = []
        detected_prefixes = detected.get("keyword_animal_prefixes", {}) or {}
        for keyword in keywords:
            variable = self.group_animal_prefix_vars.get(keyword)
            if variable is None:
                continue

            detected_prefix = (detected_prefixes.get(keyword) or "").strip()
            if not detected_prefix:
                continue
            if overwrite or not variable.get().strip():
                variable.set(detected_prefix)
                updated_keywords.append(f"{keyword} -> {detected_prefix}")

        detected_cut_prefix = (detected.get("cut_prefix") or "").strip()
        cut_updated = False
        if detected_cut_prefix and (overwrite or not self.cut_prefix_var.get().strip()):
            self.cut_prefix_var.set(detected_cut_prefix)
            cut_updated = True

        if not silent:
            if updated_keywords or cut_updated:
                message_lines = []
                if cut_updated:
                    message_lines.append(f"Section prefix: {self.cut_prefix_var.get().strip()}")
                if updated_keywords:
                    message_lines.extend(updated_keywords)
                messagebox.showinfo(
                    "Summary patterns detected",
                    "\n".join(message_lines),
                )
            else:
                messagebox.showwarning(
                    "Summary patterns",
                    "No animal or section markers were detected in the matching filenames.",
                )

    def _collect_extractors(self) -> dict:
        """Collect custom extractor entries from listbox into a dict name->mask."""
        mapping = {}
        for idx in range(self.extract_listbox.size()):
            entry = self.extract_listbox.get(idx)
            if "=" in entry:
                name, mask = entry.split("=", 1)
                name = name.strip()
                mask = mask.strip()
                if name and mask:
                    mapping[name] = mask
        return mapping

    def _gather_processing_options(self) -> ProcessingOptions:
        roi_templates = self._collect_listbox_values(self.roi_listbox) or None
        generate_slice_averages = self.generate_slice_average_var.get()
        generate_animal_averages = self.generate_animal_average_var.get()

        if (generate_slice_averages or generate_animal_averages) and not self.save_measurements_var.get():
            self.save_measurements_var.set(True)
            self._log(
                "Enabled 'Save measurement CSV' automatically because aggregated summaries need per-document CSV files."
            )
        if (generate_slice_averages or generate_animal_averages) and not self.generate_summary_var.get():
            self.generate_summary_var.set(True)
            self._log(
                "Enabled 'Generate measurement summary' automatically because aggregated summaries depend on it."
            )

        options = ProcessingOptions(
            apply_roi=self.apply_roi_var.get(),
            save_processed_files=self.save_processed_var.get(),
            save_measurements_csv=self.save_measurements_var.get(),
            custom_suffix=self.suffix_var.get().strip() or "processed",
            measurements_folder=self.measurements_folder_var.get().strip() or "Measurements",
            processed_folder=self.processed_folder_var.get().strip() or "Processed_Files",
            measurement_summary_prefix=self.measurement_prefix_var.get().strip()
            or "measurements_summary",
            generate_measurement_summary=self.generate_summary_var.get(),
            roi_search_templates=roi_templates,
            generate_slice_averages=generate_slice_averages,
            generate_animal_averages=generate_animal_averages,
            keyword_animal_prefixes=self._collect_group_animal_prefixes() or None,
            cut_prefix=self.cut_prefix_var.get().strip() or None,
        )

        secondary = self.secondary_filter_var.get().strip()
        options.secondary_filter = secondary or None

        # Attach custom extractors
        custom_map = self._collect_extractors()
        options.custom_name_patterns = custom_map or None

        return options

    # ------------------------------------------------------------------
    # Custom extractor helpers
    # ------------------------------------------------------------------
    def _add_custom_extractor(self) -> None:
        name = (self.extract_name_var.get() or "").strip()
        mask = (self.extract_mask_var.get() or "").strip()
        if not name or not mask:
            return
        # Ensure no spaces and braces in name to be safe for {name}
        if any(ch in name for ch in " {}\t\n"):
            messagebox.showwarning("Invalid name", "Name must not contain spaces or braces.")
            return
        # Insert or replace existing of same name
        existing_indices = [i for i in range(self.extract_listbox.size()) if self.extract_listbox.get(i).split("=",1)[0].strip() == name]
        for idx in reversed(existing_indices):
            self.extract_listbox.delete(idx)
        self.extract_listbox.insert(tk.END, f"{name}={mask}")
        self.extract_name_var.set("")
        self.extract_mask_var.set("")

    def _remove_selected_extractor(self) -> None:
        self._remove_selected(self.extract_listbox)

    def _get_macro_input(self) -> Optional[str]:
        mode = self.macro_mode_var.get()
        if mode == "code":
            value = self.macro_code_value.strip()
            return value or None
        if mode == "library":
            name = self.macro_library_var.get().strip()
            if not name:
                return None
            if name not in MACROS_LIB:
                raise ValueError(
                    f"Macro '{name}' was not found in the bundled macro library."
                )
            if name in self._library_code_overrides:
                value = self._library_code_overrides[name].strip()
                return value or None
            return MACROS_LIB[name]
        raise ValueError(f"Unsupported macro mode: {mode}")

    def _get_processor(self) -> CoreProcessor:
        if self._processor is None:
            fiji_path = self.fiji_path_var.get().strip() or None
            self._processor = CoreProcessor(fiji_path=fiji_path)
        else:
            fiji_path = self.fiji_path_var.get().strip() or None
            if fiji_path:
                self._processor.fiji_path = fiji_path
        return self._processor

    def _set_running(self, running: bool) -> None:
        state = tk.DISABLED if running else tk.NORMAL
        for widget in (self.run_button, self.validate_button):
            widget.configure(state=state)
        # Stop button enabled only while running
        self.stop_button.configure(state=(tk.NORMAL if running else tk.DISABLED))
        if not running:
            self._log("\n")


def main() -> None:
    root = tk.Tk()
    FijiProcessorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
