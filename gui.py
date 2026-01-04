"""Graphical user interface for the Fiji automated base analysis toolkit."""

# cd /Users/savvaarutsev/Documents/Проекты/Cod_Diplom/Raw_Data_Analysis/Fiji_Automated_Base_Analysis
# /opt/homebrew/bin/python3 gui.py

from __future__ import annotations

import os
import threading
import queue
from typing import Iterable, List, Optional, Sequence, Union

import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import scrolledtext

from core_processor import CommandLibrary, CoreProcessor, ProcessingOptions
from examples.macros_lib import MACROS_LIB
from utils.general.fiji_utils import find_fiji
from utils.general.kymo_utils import find_kymograph_direct, validate_kymograph_direct_path


class FijiProcessorGUI:
    """Tkinter-based GUI for orchestrating Fiji document processing."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Fiji Automated Base Analysis")
        self.root.geometry("900x650")

        self._processor: Optional[CoreProcessor] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._cancel_event: Optional[threading.Event] = None
        self._log_queue: "queue.Queue[str]" = queue.Queue()

        self.kymograph_method_var = tk.StringVar(value="KymographDirect")

        self.macro_mode_var = tk.StringVar(value="commands")
        self.macro_commands_var = tk.StringVar()
        self.macro_library_var = tk.StringVar()
        self.macro_code_value = ""
        self.macro_summary_var = tk.StringVar()
        self._library_code_overrides: dict[str, str] = {}

        self._build_widgets()
        self.root.after(100, self._process_log_queue)

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
        self.kymo_direct_path_var = tk.StringVar()

        self._add_labeled_entry(
            path_frame,
            "Base directory:",
            self.base_path_var,
            0,
            browse_command=self._browse_directory,
        )
        self._add_labeled_entry(
            path_frame,
            "Fiji executable:",
            self.fiji_path_var,
            1,
            browse_command=lambda: self._browse_file(self.fiji_path_var),
        )
        tk.Button(path_frame, text="Auto-detect", command=self._auto_detect_fiji).grid(
            row=1, column=3, padx=(5, 0)
        )

        tk.Label(path_frame, text="Kymograph method:").grid(row=2, column=0, sticky="w")
        method_menu = tk.OptionMenu(
            path_frame,
            self.kymograph_method_var,
            "KymographDirect",
            "Lumicks",
            command=lambda *_: self._update_kymograph_method_state(),
        )
        method_menu.grid(row=2, column=1, sticky="w")

        tk.Label(path_frame, text="KymographDirect executable:").grid(row=3, column=0, sticky="w")
        self.kymo_direct_entry = tk.Entry(path_frame, textvariable=self.kymo_direct_path_var)
        self.kymo_direct_entry.grid(row=3, column=1, sticky="we", padx=(5, 5))
        path_frame.grid_columnconfigure(1, weight=1)
        self.kymo_direct_browse_button = tk.Button(
            path_frame, text="Browse", command=lambda: self._browse_file(self.kymo_direct_path_var)
        )
        self.kymo_direct_browse_button.grid(row=3, column=2)
        self.kymo_direct_auto_button = tk.Button(
            path_frame, text="Auto-detect KymographDirect", command=self._auto_detect_kymograph_direct
        )
        self.kymo_direct_auto_button.grid(row=3, column=3, padx=(5, 0))

        self._update_kymograph_method_state()

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

        tk.Checkbutton(
            checkbox_frame, text="Apply ROI templates", variable=self.apply_roi_var
        ).pack(anchor="w")
        tk.Checkbutton(
            checkbox_frame, text="Save processed images", variable=self.save_processed_var
        ).pack(anchor="w")
        tk.Checkbutton(
            checkbox_frame, text="Save measurement CSV", variable=self.save_measurements_var
        ).pack(anchor="w")
        tk.Checkbutton(
            checkbox_frame, text="Verbose logging", variable=self.verbose_var
        ).pack(anchor="w")
        tk.Checkbutton(
            checkbox_frame, text="Generate measurement summary", variable=self.generate_summary_var
        ).pack(anchor="w")

        # Action buttons -----------------------------------------------------
        action_frame = tk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(0, 10))

        self.validate_button = tk.Button(action_frame, text="Validate Setup", command=self._validate_setup)
        self.validate_button.pack(side=tk.LEFT)

        self.list_commands_button = tk.Button(
            action_frame, text="List Commands", command=self._list_commands
        )
        self.list_commands_button.pack(side=tk.LEFT, padx=5)

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
        window.geometry("640x520")
        window.transient(self.root)
        window.grab_set()

        mode_var = tk.StringVar(value=self.macro_mode_var.get())
        commands_var = tk.StringVar(value=self.macro_commands_var.get())
        library_names = sorted(MACROS_LIB.keys())
        initial_library = self.macro_library_var.get() or (library_names[0] if library_names else "")
        library_var = tk.StringVar(value=initial_library)

        mode_frame = tk.LabelFrame(window, text="Macro input mode", padx=10, pady=10)
        mode_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        def _show_mode() -> None:
            selected = mode_var.get()
            for frame in mode_frames.values():
                frame.pack_forget()
            frame = mode_frames.get(selected, command_frame)
            frame.pack(fill=tk.BOTH, expand=True)
            if frame is command_frame:
                command_entry.focus_set()
            elif frame is code_frame:
                code_text.focus_set()
            else:
                window.focus_set()

        for label, value in (
            ("Command sequence", "commands"),
            ("Full macro code", "code"),
            ("Library macro", "library"),
        ):
            tk.Radiobutton(mode_frame, text=label, variable=mode_var, value=value, command=_show_mode).pack(
                anchor="w"
            )

        content_frame = tk.Frame(window, padx=10, pady=10)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Command sequence input ------------------------------------------------
        command_frame = tk.Frame(content_frame)
        tk.Label(
            command_frame,
            text=(
                "Enter space-separated commands."
                " Use parameters like 'subtract_background radius=50'."
            ),
            wraplength=560,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 5))
        command_entry = tk.Entry(command_frame, textvariable=commands_var)
        command_entry.pack(fill=tk.X, expand=True)

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
            option_menu.pack(anchor="w", pady=(0, 5))
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
            "commands": command_frame,
            "code": code_frame,
            "library": library_frame,
        }

        window.focus_set()
        _show_mode()

        button_frame = tk.Frame(window, pady=10)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        def _apply() -> None:
            self.macro_mode_var.set(mode_var.get())
            self.macro_commands_var.set(commands_var.get().strip())
            self.macro_code_value = code_text.get("1.0", tk.END).strip()
            if library_names:
                selected = library_var.get().strip()
                self.macro_library_var.set(selected)
                if library_code_text is not None:
                    library_code_value = library_code_text.get("1.0", tk.END).strip()
                    default_code = MACROS_LIB.get(selected, "").strip()
                    if library_code_value == default_code:
                        self._library_code_overrides.pop(selected, None)
                    else:
                        self._library_code_overrides[selected] = library_code_value
            else:
                self.macro_library_var.set("")
            self._update_macro_summary()
            window.destroy()

        tk.Button(button_frame, text="Cancel", command=window.destroy).pack(side=tk.RIGHT, padx=(5, 0))
        tk.Button(button_frame, text="Save", command=_apply).pack(side=tk.RIGHT)

    def _update_macro_summary(self) -> None:
        mode = self.macro_mode_var.get()
        if mode == "commands":
            value = self.macro_commands_var.get().strip()
            summary = value or "(none)"
            text = f"Commands: {summary}"
        elif mode == "code":
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

    # ------------------------------------------------------------------
    # Path utilities
    # ------------------------------------------------------------------
    def _browse_directory(self) -> None:
        initial = self.base_path_var.get() or os.getcwd()
        directory = filedialog.askdirectory(initialdir=initial, title="Select base directory")
        if directory:
            self.base_path_var.set(directory)

    def _browse_file(self, variable: tk.StringVar) -> None:
        initial = variable.get() or os.getcwd()
        path = filedialog.askopenfilename(initialdir=initial, title="Select file")
        if path:
            variable.set(path)

    def _auto_detect_fiji(self) -> None:
        detected_path = find_fiji()
        if detected_path:
            self.fiji_path_var.set(detected_path)
            self._log(f"Detected Fiji executable: {detected_path}")
            messagebox.showinfo("Fiji detected", f"Fiji executable found at:\n{detected_path}")
        else:
            messagebox.showwarning(
                "Fiji not found",
                "Unable to automatically locate the Fiji executable."
                "\nPlease specify the path manually.",
            )

    def _auto_detect_kymograph_direct(self) -> None:
        detected_path = find_kymograph_direct()
        if detected_path:
            self.kymo_direct_path_var.set(detected_path)
            self._log(f"Detected KymographDirect executable: {detected_path}")
            messagebox.showinfo(
                "KymographDirect detected",
                f"KymographDirect executable found at:\n{detected_path}",
            )
        else:
            messagebox.showwarning(
                "KymographDirect not found",
                "Unable to automatically locate the KymographDirect executable."
                "\nPlease specify the path manually.",
            )

    def _update_kymograph_method_state(self) -> None:
        is_kymo_direct = self.kymograph_method_var.get() == "KymographDirect"
        state = tk.NORMAL if is_kymo_direct else tk.DISABLED
        for widget in (
            self.kymo_direct_entry,
            self.kymo_direct_browse_button,
            self.kymo_direct_auto_button,
        ):
            widget.configure(state=state)

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

    def _remove_selected_keyword(self) -> None:
        self._remove_selected(self.keyword_listbox)

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
            self._log("Validating Fiji setup...")
            validation = processor.validate_setup()
            self._log("Fiji validation complete.")
            if self.kymograph_method_var.get() == "KymographDirect":
                kymo_path = self.kymo_direct_path_var.get().strip()
                is_valid = validate_kymograph_direct_path(kymo_path)
                if is_valid:
                    self._log(f"KymographDirect path valid: {kymo_path}")
                else:
                    self._log(
                        "KymographDirect validation failed: specify a valid executable path."
                    )
            details = [
                f"Fiji path: {validation['fiji_path']}",
                f"Fiji valid: {validation['fiji_valid']}",
                f"Available commands: {len(validation['available_commands'])}",
                f"Supported extensions: {', '.join(validation['supported_extensions'])}",
            ]
            self._log("\n".join(details))
            messagebox.showinfo("Validation", "Setup validation complete. See log for details.")
        except Exception as exc:  # pragma: no cover - GUI fallback
            messagebox.showerror("Validation error", str(exc))

    def _list_commands(self) -> None:
        try:
            library = CommandLibrary()
            commands = library.list_commands()
        except Exception as exc:  # pragma: no cover - GUI fallback
            messagebox.showerror("Command error", str(exc))
            return

        window = tk.Toplevel(self.root)
        window.title("Available Commands")
        window.geometry("500x500")

        text = scrolledtext.ScrolledText(window, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)

        for name, info in sorted(commands.items()):
            text.insert(tk.END, f"{name}\n")
            text.insert(tk.END, f"  Description: {info['description']}\n")
            if info.get("parameters"):
                text.insert(tk.END, f"  Parameters: {info['parameters']}\n")
            text.insert(tk.END, f"  Example: {info['example']}\n\n")

        text.configure(state="disabled")

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
        window.geometry("520x480")

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

        options = self._gather_processing_options()
        keyword_input: Union[str, Sequence[str]] = (
            keywords[0] if len(keywords) == 1 else list(keywords)
        )

        try:
            macro_input = self._get_macro_input()
        except ValueError as exc:
            messagebox.showerror("Macro configuration", str(exc))
            return

        processor = self._get_processor()

        args = dict(
            base_path=os.path.abspath(os.path.expanduser(base_path)),
            keyword=keyword_input,
            macro_commands=macro_input,
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
                    self._log(f"❌ Processing failed: {result.get('error')}")
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
        if mode == "commands":
            value = self.macro_commands_var.get().strip()
            return value or None
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
        for widget in (self.run_button, self.validate_button, self.list_commands_button):
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
