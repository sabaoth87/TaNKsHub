import os
import shutil
import threading
import queue
import logging
from datetime import datetime
from typing import NamedTuple, Optional, List, Dict, Any
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tankhub.core.base_module import BaseModule

logger = logging.getLogger(__name__)

class FileOperation(NamedTuple):
    source: str
    dest: str
    is_file: bool
    operation_type: str

class FileMoverModule(BaseModule):
    """File movement/copying module based on QuickQopy functionality."""
    
    def __init__(self):
        super().__init__("File Mover", "Copy or move files with progress tracking")
        # Initiate Logging
        self.logger = logging.getLogger(__name__)  # Changed to self.logger

        # Operation queues
        self.operation_queue: queue.Queue = queue.Queue()
        self.message_queue: queue.Queue = queue.Queue()
        self.progress_queue: queue.Queue = queue.Queue()
        
        # Keep track of queued files
        self.queued_files: List[Path] = []

        # Processing state
        self.processing: bool = False
        self.total_operations: int = 0
        self.current_thread: Optional[threading.Thread] = None
        
        # GUI elements stored as instance variables
        self.operation_var = None
        self.recursive_var = None
        self.preserve_var = None
        self.dest_path = None
        self.queued_files_text = None
        self.cancel_btn = None

        # Default settings - store actual values here
        self.config = {
            'operation_type': 'copy',
            'recursive': True,
            'preserve_metadata': True,
            'destination_folder': ''
        }

        # Add filename editor integration
        self.filename_editor = None  # Will be set by the main application
        self.rename_enabled = False
        
        # Update config with rename settings
        self.config.update({
            'rename_enabled': False,
        })

    def get_supported_extensions(self) -> List[str]:
        """Return supported file extensions (all files supported)."""
        return ['*']

    def get_settings_widget(self, parent) -> ttk.Frame:
        """Create and return the settings widget."""
        # frame = ttk.Frame(parent)
        frame = super().get_settings_widget(parent)

        # Queued files display
        queue_frame = ttk.LabelFrame(frame, text="Queued Files", padding=5)
        queue_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.queued_files_text = tk.Text(queue_frame, height=4, wrap=tk.WORD)
        self.queued_files_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        queue_buttons = ttk.Frame(queue_frame)
        queue_buttons.pack(fill='x', padx=5, pady=2)
        
        ttk.Button(
            queue_buttons,
            text="Clear Queue",
            command=self._clear_queue
        ).pack(side='left', padx=5)
        
        ttk.Button(
            queue_buttons,
            text="Process Queue",
            command=self._process_current_queue
        ).pack(side='left', padx=5)

        # Destination folder section
        dest_frame = ttk.LabelFrame(frame, text="Destination Folder", padding=5)
        dest_frame.pack(fill='x', padx=5, pady=5)
        
        self.dest_path = tk.StringVar(value=self.config['destination_folder'])
        self.dest_path.trace_add('write', self._on_destination_change)
        
        dest_entry = ttk.Entry(dest_frame, textvariable=self.dest_path)
        dest_entry.pack(side='left', fill='x', expand=True, padx=5)
        
        browse_btn = ttk.Button(
            dest_frame,
            text="Browse",
            command=self._browse_destination
        )
        browse_btn.pack(side='right', padx=5)

        # Create variables using config values
        self.operation_var = tk.StringVar(value=self.config['operation_type'])
        self.recursive_var = tk.BooleanVar(value=self.config['recursive'])
        self.preserve_var = tk.BooleanVar(value=self.config['preserve_metadata'])

        # Operation type selection
        op_frame = ttk.LabelFrame(frame, text="Operation Type", padding=5)
        op_frame.pack(fill='x', padx=5, pady=5)
        
        self.operation_var = tk.StringVar(value=self.config['operation_type'])
        self.operation_var.trace_add('write', self._on_settings_change)
        
        ttk.Radiobutton(
            op_frame,
            text="Copy",
            variable=self.operation_var,
            value="copy"
        ).pack(side='left', padx=5)
        ttk.Radiobutton(
            op_frame,
            text="Move",
            variable=self.operation_var,
            value="move"
        ).pack(side='left', padx=5)
        
        # Options
        options_frame = ttk.LabelFrame(frame, text="Options", padding=5)
        options_frame.pack(fill='x', padx=5, pady=5)
        
        self.recursive_var = tk.BooleanVar(value=self.config['recursive'])
        self.recursive_var.trace_add('write', self._on_settings_change)
        
        ttk.Checkbutton(
            options_frame,
            text="Process folders recursively",
            variable=self.recursive_var
        ).pack(anchor='w', padx=5)
        
        self.preserve_var = tk.BooleanVar(value=self.config['preserve_metadata'])
        ttk.Checkbutton(
            options_frame,
            text="Preserve file metadata",
            variable=self.preserve_var
        ).pack(anchor='w', padx=5)
        
        # Add rename integration checkbox
        rename_frame = ttk.LabelFrame(frame, text="Filename Processing", padding=5)
        rename_frame.pack(fill='x', padx=5, pady=5)
        
        self.rename_var = tk.BooleanVar(value=self.config['rename_enabled'])
        self.rename_checkbox = ttk.Checkbutton(
            rename_frame,
            text="Enable filename processing",
            variable=self.rename_var,
            command=self._toggle_rename
        )
        self.rename_checkbox.pack(anchor='w', padx=5)

        # Progress section
        progress_frame = ttk.LabelFrame(frame, text="Progress", padding=5)
        progress_frame.pack(fill='x', padx=5, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            mode="determinate",
            variable=self.progress_var
        )
        self.progress_bar.pack(fill='x', padx=5, pady=5)
        
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(
            progress_frame,
            textvariable=self.status_var
        ).pack(fill='x', padx=5)
        
        # Cancel button
        self.cancel_btn = ttk.Button(
            frame,
            text="Cancel Operation",
            command=self.cancel_operation,
            state="disabled"
        )
        self.cancel_btn.pack(pady=5)
        
        return frame

    def _toggle_rename(self):
        """Handle rename checkbox toggle."""
        self.rename_enabled = self.rename_var.get()
        self.config['rename_enabled'] = self.rename_enabled
        if self.queued_files:
            self._update_preview()

    def _update_preview(self):
        """Update the queued files display with preview of operations."""
        if not self.queued_files_text:
            return

        self.queued_files_text.delete('1.0', tk.END)
        if not self.queued_files:
            self.queued_files_text.insert(tk.END, "No files in queue\n")
            return

        # Get destination base path
        dest_base = self.dest_path.get() if self.dest_path else ""
        if not dest_base:
            self.queued_files_text.insert(tk.END, "Please select a destination folder\n")
            return

        # Show operation type in preview header
        operation = self.operation_var.get() if hasattr(self, 'operation_var') else self.config['operation_type']
        self.queued_files_text.insert(tk.END, f"Operation: {operation.upper()}\n")
        if self.rename_enabled and self.filename_editor:
            self.queued_files_text.insert(tk.END, "Filename processing enabled\n")
        self.queued_files_text.insert(tk.END, "-" * 50 + "\n")

        # Process each file
        for file_path in self.queued_files:
            try:
                # Show source path
                self.queued_files_text.insert(tk.END, f"Source: {file_path}\n")
            
                # Generate destination path
                if self.rename_enabled and self.filename_editor:
                    # Get new filename using the filename editor
                    media_info = self.filename_editor.filename_parser.parse_filename(file_path.stem)
                    new_name = self.filename_editor.filename_parser.generate_filename(media_info)
                    if self.filename_editor.preserve_ext_var.get():
                        new_name += file_path.suffix
                else:
                    new_name = file_path.name

                # Construct full destination path
                dest_path = Path(dest_base) / new_name
                self.queued_files_text.insert(tk.END, f"Dest:   {dest_path}\n")

                # Add warning if destination exists
                if dest_path.exists():
                    self.queued_files_text.insert(tk.END, "⚠️ Warning: Destination file already exists\n")

                self.queued_files_text.insert(tk.END, "\n")

            except Exception as e:
                self.logger.error(f"Error generating preview for {file_path}: {str(e)}")
                self.queued_files_text.insert(
                    tk.END, 
                    f"Error processing {file_path.name}: {str(e)}\n\n"
                )

        # Show total count
        self.queued_files_text.insert(
            tk.END,
            f"-" * 50 + f"\nTotal files: {len(self.queued_files)}\n"
        )
    
        # Scroll to the beginning
        self.queued_files_text.see("1.0")

    def _browse_destination(self):
            """Open folder selection dialog."""
            folder = filedialog.askdirectory()
            if folder:
                self.dest_path.set(folder)
                self.config['destination_folder'] = folder

    def _on_destination_change(self, *args):
        """Handle destination folder changes."""
        if self.queued_files and self.dest_path.get() != self.config['destination_folder']:
            if messagebox.askyesno(
                "Update Queue",
                "Do you want to update the destination for all queued files?"
            ):
                self._update_queue_destination()
        self.config['destination_folder'] = self.dest_path.get()

    def _on_settings_change(self, *args):
        """Handle settings changes."""
        if self.queued_files:
            if messagebox.askyesno(
                "Update Queue",
                "Settings have changed. Do you want to reprocess the current queue with new settings?"
            ):
                self._process_current_queue()

    def _clear_queue(self):
        """Clear the current file queue."""
        self.queued_files.clear()
        self.operation_queue = queue.Queue()
        if self.queued_files_text:
            self.queued_files_text.delete('1.0', tk.END)
        self.status_var.set("Queue cleared")

    def _update_queue_destination(self):
        """Update destination for all queued files."""
        new_dest = Path(self.dest_path.get())
        self.operation_queue = queue.Queue()
        for file_path in self.queued_files:
            final_dest = new_dest / file_path.name
            operation = FileOperation(
                str(file_path),
                str(final_dest),
                file_path.is_file(),
                self.config['operation_type']
            )
            self.operation_queue.put(operation)

    def _process_current_queue(self):
        """Process the current queue with current settings."""
        if not self.dest_path.get():
            messagebox.showerror("Error", "Please select a destination folder first!")
            return
            
        if not self.queued_files:
            messagebox.showinfo("Info", "No files in queue to process")
            return
            
        self._update_queue_destination()  # Ensure queue is up to date
        self.total_operations = self.operation_queue.qsize()
        self.processing = True
        self.cancel_btn.configure(state="normal")
        self.current_thread = threading.Thread(
            target=self._process_queue,
            daemon=True
        )
        self.current_thread.start()

    def process_file(self, file_path: Path, dest_path: Path) -> bool:
        """Queue a file for processing with optional renaming."""
        try:
            if file_path not in self.queued_files:
                self.queued_files.append(file_path)
                
                # If renaming is enabled and we have a filename editor
                if self.rename_enabled and self.filename_editor:
                    # Get the new filename
                    media_info = self.filename_editor.filename_parser.parse_filename(file_path.stem)
                    new_name = self.filename_editor.filename_parser.generate_filename(media_info)
                    if self.filename_editor.preserve_ext_var.get():
                        new_name += file_path.suffix
                else:
                    new_name = file_path.name
                
                # Create the operation with the potentially new filename
                final_dest = Path(self.dest_path.get()) / new_name
                operation = FileOperation(
                    str(file_path),
                    str(final_dest),
                    file_path.is_file(),
                    self.operation_var.get()
                )
                self.operation_queue.put(operation)
                
                self._update_preview()
            return True
        except Exception as e:
            self.logger.error(f"Error queueing {file_path}: {str(e)}")
            return False

    def _process_queue(self) -> None:
        """Process the operation queue."""
        while self.processing and not self.operation_queue.empty():
            try:
                operation = self.operation_queue.get_nowait()
                
                if not self.processing:  # Check if cancelled
                    break
                    
                if operation.is_file:
                    # Process single file
                    if operation.operation_type == "copy":
                        shutil.copy2(operation.source, operation.dest)
                    else:  # move operation
                        shutil.move(operation.source, operation.dest)
                    self.message_queue.put(
                        f"Successfully {operation.operation_type}d {os.path.basename(operation.source)}"
                    )
                else:
                    # Process directory
                    if operation.operation_type == "copy":
                        shutil.copytree(
                            operation.source,
                            operation.dest,
                            dirs_exist_ok=True
                        )
                    else:  # move operation
                        shutil.move(operation.source, operation.dest)
                    self.message_queue.put(
                        f"Successfully {operation.operation_type}d folder: {os.path.basename(operation.source)}"
                    )

                # Update progress
                remaining = self.operation_queue.qsize()
                progress = ((self.total_operations - remaining) / self.total_operations) * 100
                self.progress_queue.put(
                    (progress, f"{operation.operation_type.capitalize()}ing files... ({self.total_operations - remaining}/{self.total_operations})")
                )
                
            except Exception as e:
                self.message_queue.put(
                    f"Error processing {os.path.basename(operation.source)}: {str(e)}"
                )

        # Processing complete
        self.processing = False
        self.progress_queue.put((100, "Ready"))
        if self.cancel_btn:
            self.cancel_btn.configure(state="disabled")

    def _update_queued_files_display(self):
        """Update the queued files display."""
        if self.queued_files_text:
            self.queued_files_text.delete('1.0', tk.END)
            for file_path in self.queued_files:
                self.queued_files_text.insert(tk.END, f"{file_path.name}\n")
            self.queued_files_text.see(tk.END)

    def sync_with_main_list(self, file_paths: List[str]):
        """Sync the module's queue with the main file list."""
        self.queued_files = [Path(fp) for fp in file_paths]
        self._update_queued_files_display()
        # If destination is set, update operation queue
        if self.dest_path and self.dest_path.get():
            self._update_queue_destination()

    def on_enable_changed(self, enabled: bool):
        """Handle module enable/disable state changes."""
        self.enabled = enabled
        if enabled:
            # Request main window to send current file list
            if hasattr(self, 'request_file_list'):
                file_paths = self.request_file_list()
                if file_paths:
                    self.sync_with_main_list(file_paths)

    def _update_queue_destination(self):
        """Update destination for all queued files."""
        if not self.dest_path.get():
            return
            
        new_dest = Path(self.dest_path.get())
        self.operation_queue = queue.Queue()
        for file_path in self.queued_files:
            final_dest = new_dest / file_path.name
            operation = FileOperation(
                str(file_path),
                str(final_dest),
                file_path.is_file(),
                self.operation_var.get() if self.operation_var else self.config['operation_type']
            )
            self.operation_queue.put(operation)

    def cancel_operation(self) -> None:
        """Cancel the current operation."""
        self.processing = False
        self.message_queue.put("Operation cancelled by user")
        self.cancel_btn.configure(state="disabled")

    def process_queues(self) -> None:
        """Process message and progress queues."""
        try:
            # Process all pending messages
            while True:
                try:
                    message = self.message_queue.get_nowait()
                    # Log message to main application
                    logger.info(message)
                except queue.Empty:
                    break

            # Process progress updates
            try:
                progress, status = self.progress_queue.get_nowait()
                self.progress_var.set(progress)
                self.status_var.set(status)
            except queue.Empty:
                pass

        finally:
            # Schedule next queue check if module is enabled
            if self.enabled and hasattr(self, 'progress_bar'):
                self.progress_bar.after(100, self.process_queues)

    def save_settings(self) -> Dict[str, Any]:
        """Save current settings including rename settings."""
        settings = super().save_settings()
        settings.update({
            'rename_enabled': self.rename_enabled,
        })
        return settings

    def load_settings(self, settings: Dict[str, Any]) -> None:
        """Load settings including rename settings."""
        super().load_settings(settings)
        self.rename_enabled = settings.get('rename_enabled', False)
        if hasattr(self, 'rename_var'):
            self.rename_var.set(self.rename_enabled)
