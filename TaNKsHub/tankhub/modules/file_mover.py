from dataclasses import dataclass
from typing import Optional, List, Dict, Any, NamedTuple
from pathlib import Path
import os
import shutil
import threading
import queue
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tankhub.core.base_module import BaseModule

logger = logging.getLogger(__name__)

class FileOperation(NamedTuple):
    source: str
    dest: str
    is_file: bool
    operation_type: str
    rename: bool = False

class FileMoverModule(BaseModule):
    """File movement/copying module with integrated filename editing."""
    
    def __init__(self):
        super().__init__("File Mover", "Copy or move files with optional renaming")
        # Initiate Logging
        self.logger = logging.getLogger(__name__)

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
        self.rename_var = None

        # Filename editor integration
        self.filename_editor = None
        self._rename_enabled = False

        # Default settings
        self.config = {
            'operation_type': 'move',
            'recursive': False,
            'preserve_metadata': False,
            'destination_folder': '',
            'rename_enabled': False
        }

    @property
    def rename_enabled(self):
        """Get the current rename enabled state."""
        # If we have a rename_var, use its value, otherwise use stored value
        if hasattr(self, 'rename_var') and self.rename_var is not None:
            return self.rename_var.get()
        return self._rename_enabled

    @rename_enabled.setter
    def rename_enabled(self, value):
        """Set the rename enabled state."""
        self._rename_enabled = value
        # Update the checkbox if it exists
        if hasattr(self, 'rename_var') and self.rename_var is not None:
            self.rename_var.set(value)
        # Update config
        self.config['rename_enabled'] = value

    def get_supported_extensions(self) -> List[str]:
        """Define which file types this module can handle."""
        return ['*']  # Handle all file types
        # Or specify extensions: ['.txt', '.pdf', '.doc']

    def get_settings_widget(self, parent) -> ttk.Frame:
        """Create and return the settings widget."""
        frame = ttk.Frame(parent)

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
        
        # Rename integration
        rename_frame = ttk.LabelFrame(frame, text="Filename Processing", padding=5)
        rename_frame.pack(fill='x', padx=5, pady=5)
        
        # Initialize the BooleanVar with the current config setting
        self.rename_var = tk.BooleanVar(value=self.config.get('rename_enabled', False))
        ttk.Checkbutton(
            rename_frame,
            text="Clean up filenames during transfer",
            variable=self.rename_var,
            command=self._on_rename_toggle
        ).pack(anchor='w', padx=5)
        
        # Testing Section
        ttk.Button(
            rename_frame,
            text="Test Filename Processor",
            command=self.debug_filename_parsing
        ).pack(side='left', padx=5, pady=5)
        
        ttk.Button(
            rename_frame,
            text="Test Integration",
            command=self.test_integration
        ).pack(side='left', padx=5, pady=5)
        
        ttk.Button(
            rename_frame,
            text="Debug Settings",
            command=self.debug_rename_setting
        ).pack(side='left', padx=5, pady=5)
        
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

    def _on_rename_toggle(self):
        """Handle rename checkbox toggle."""
        self._rename_enabled = self.rename_var.get()
        self.config['rename_enabled'] = self._rename_enabled
        self.logger.debug(f"Rename setting changed to: {self.rename_enabled}")
        
        # If there are queued files, update the queue with the new rename setting
        if self.queued_files and self.dest_path and self.dest_path.get():
            self._update_queue_destination()
        
        # Always update the preview to reflect current settings
        self._update_preview()

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
                self._update_queue_destination()
                self._update_preview()

    def _clear_queue(self):
        """Clear the current file queue."""
        self.queued_files.clear()
        self.operation_queue = queue.Queue()
        if self.queued_files_text:
            self.queued_files_text.delete('1.0', tk.END)
        self.status_var.set("Queue cleared")

    def _update_queue_destination(self):
        """Update destination for all queued files with improved path handling."""
        if not self.dest_path.get():
            self.logger.debug("No destination path set")
            return
    
        new_dest = Path(self.dest_path.get())
        self.operation_queue = queue.Queue()  # Clear existing queue

        # Log current settings
        self.logger.debug(f"Updating queue destination to {new_dest}")
        self.logger.debug(f"Rename enabled: {self.rename_enabled}")
        self.logger.debug(f"Filename editor available: {self.filename_editor is not None}")

        for file_path in self.queued_files:
            try:
                # Make sure file_path is a Path object
                file_path = Path(file_path) if not isinstance(file_path, Path) else file_path
            
                # Skip if file doesn't exist
                if not file_path.exists():
                    self.logger.warning(f"File no longer exists: {file_path}")
                    continue
                
                # Determine the filename based on rename setting
                orig_name = file_path.name
                dest_name = orig_name  # Default to original name
        
                # Check if rename is enabled and we have a filename editor
                if self.rename_enabled and self.filename_editor:
                    # Get new filename using the filename editor
                    self.logger.debug(f"Processing {file_path.stem} for renaming")
                    media_info = self.filename_editor.filename_parser.parse_filename(file_path.stem)
                    new_base = self.filename_editor.filename_parser.generate_filename(media_info)
                    # Always preserve extension for now
                    dest_name = new_base + file_path.suffix
                    self.logger.debug(f"Generated new name: {orig_name} -> {dest_name}")
                else:
                    self.logger.debug(f"No renaming applied for {orig_name}")
            
                # Create the final destination path
                final_dest = new_dest / dest_name
            
                # Check if destination already exists, add a number if needed
                counter = 1
                while final_dest.exists() and final_dest != file_path:
                    base_name = final_dest.stem
                    # Check if base_name already ends with a number in parentheses
                    match = re.search(r'^(.*)\s\((\d+)\)$', base_name)
                    if match:
                        # Increment the existing number
                        base_name = match.group(1)
                        counter = int(match.group(2)) + 1
                
                    new_name = f"{base_name} ({counter}){file_path.suffix}"
                    final_dest = new_dest / new_name
                    counter += 1
                    self.logger.debug(f"Destination exists, using {new_name} instead")
        
                # IMPORTANT: Create the operation with the right rename flag
                operation = FileOperation(
                    str(file_path.resolve()),  # Use absolute path
                    str(final_dest),
                    file_path.is_file(),
                    self.operation_var.get(),
                    rename=self.rename_enabled
                )
        
                # Debug check the operation to ensure rename flag is set correctly
                self.logger.debug(f"Created operation with source={file_path.name}, dest={dest_name}, rename={operation.rename}")
        
                self.operation_queue.put(operation)
        
            except Exception as e:
                self.logger.error(f"Error in _update_queue_destination for {file_path}: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
        
        self.logger.debug(f"Queue updated with {self.operation_queue.qsize()} operations")

    def _process_current_queue(self):
        """Process the current queue with current settings using a background thread."""
        if not self.dest_path.get():
            messagebox.showerror("Error", "Please select a destination folder first!")
            return
    
        if not self.queued_files:
            messagebox.showinfo("Info", "No files in queue to process")
            return

        # Important - re-create the queue with the current settings BEFORE processing
        self.logger.debug(f"Processing queue with rename_enabled={self.rename_enabled}")
        self._update_queue_destination()  # Ensure queue is up to date with latest settings

        self.total_operations = self.operation_queue.qsize()

        # Debug check an operation from the queue to verify settings
        if not self.operation_queue.empty():
            temp_queue = queue.Queue()
            op = self.operation_queue.get()
            self.logger.debug(f"Sample operation before processing: {os.path.basename(op.source)} -> {os.path.basename(op.dest)}, rename={op.rename}")
            temp_queue.put(op)
    
            # Restore the queue
            while not self.operation_queue.empty():
                temp_queue.put(self.operation_queue.get())
            self.operation_queue = temp_queue

        self.processing = True
        self.cancel_btn.configure(state="normal")
    
        # Find the main application instance (to use run_in_background)
        # This requires a reference to the main TaNKsHubGUI instance from each module
        main_app = None
        if hasattr(self, 'app') and hasattr(self.app, 'run_in_background'):
            main_app = self.app
    
        # Start processing in a background thread
        if main_app:
            # Use the main app's background thread method if available
            self.current_thread = main_app.run_in_background(
                self._process_queue,
                lambda _: self.logger.debug("Queue processing complete")
            )
        else:
            # Fall back to the old method
            self.current_thread = threading.Thread(
                target=self._process_queue,
                daemon=True
            )
            self.current_thread.start()

    def process_file(self, file_path: Path, dest_path: Path) -> bool:
        """Queue a file for processing with improved path handling."""
        try:
            # Ensure we're working with Path objects
            file_path = Path(file_path) if not isinstance(file_path, Path) else file_path
        
            # Log the file being processed
            self.logger.debug(f"Processing file: {file_path} (exists: {file_path.exists()})")
        
            # Check if file exists before adding to queue
            if not file_path.exists():
                self.logger.warning(f"File does not exist: {file_path}")
                self.message_queue.put(f"File does not exist: {file_path}")
                return False
            
            # Check if file is already in queue (compare resolved paths)
            file_path_resolved = file_path.resolve()
            for queued_file in self.queued_files:
                if Path(queued_file).resolve() == file_path_resolved:
                    self.logger.debug(f"File already in queue: {file_path}")
                    return True
        
            # Add to queue using the resolved path
            self.queued_files.append(file_path_resolved)
            self.logger.debug(f"Added file to queue: {file_path_resolved}")
            self._update_preview()
        
            # Update queue with current settings if destination is set
            if self.dest_path and self.dest_path.get():
                self._update_queue_destination()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error queuing {file_path}: {str(e)}")
            self.message_queue.put(f"Error queuing {file_path}: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _process_queue(self) -> None:
        """Process the operation queue with improved error handling."""
        self.logger.debug("Starting to process queue")
        self.logger.debug(f"Queue size: {self.operation_queue.qsize()}")

        while self.processing and not self.operation_queue.empty():
            try:
                operation = self.operation_queue.get_nowait()
        
                self.logger.debug(f"Processing operation: {operation.source} -> {operation.dest}")
                self.logger.debug(f"Operation type: {operation.operation_type}, Rename: {operation.rename}")
        
                if not self.processing:  # Check if cancelled
                    break
                
                # Verify source file still exists
                if not Path(operation.source).exists():
                    error_msg = f"Source file not found: {operation.source}"
                    self.logger.error(error_msg)
                    self.message_queue.put(error_msg)
                    continue
        
                # Check if the destination directory exists, create if needed
                dest_dir = os.path.dirname(operation.dest)
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir, exist_ok=True)
                    self.logger.debug(f"Created destination directory: {dest_dir}")
            
                # Get source and destination filenames for display
                source_filename = os.path.basename(operation.source)
                dest_filename = os.path.basename(operation.dest)
            
                if operation.is_file:
                    # Process single file
                    if operation.operation_type == "copy":
                        shutil.copy2(operation.source, operation.dest)
                        operation_past_tense = "copied"
                    else:  # move operation
                        shutil.move(operation.source, operation.dest)
                        operation_past_tense = "moved"
                
                    # Determine the message based on whether renaming was done
                    if operation.rename and dest_filename != source_filename:
                        self.message_queue.put(
                            f"Successfully {operation_past_tense} and renamed {source_filename} to {dest_filename}"
                        )
                    else:
                        self.message_queue.put(
                            f"Successfully {operation_past_tense} {source_filename}"
                        )
                else:
                    # Process directory
                    if operation.operation_type == "copy":
                        shutil.copytree(
                            operation.source,
                            operation.dest,
                            dirs_exist_ok=True
                        )
                        operation_past_tense = "copied"
                    else:  # move operation
                        shutil.move(operation.source, operation.dest)
                        operation_past_tense = "moved"
                
                    self.message_queue.put(
                        f"Successfully {operation_past_tense} folder: {os.path.basename(operation.source)}"
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
                self.logger.error(f"Error processing {os.path.basename(operation.source)}: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())

        # Processing complete
        self.processing = False
        self.progress_queue.put((100, "Ready"))
        if self.cancel_btn:
            self.cancel_btn.configure(state="disabled")

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
                    # Always preserve extension for now
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

    def sync_with_main_list(self, file_paths: List[str]):
        """Sync the module's queue with the main file list using resolved paths."""
        # Convert all paths to Path objects with resolved paths
        self.queued_files = []
        for fp in file_paths:
            path = Path(fp)
            if path.exists():
                self.queued_files.append(path.resolve())
            else:
                self.logger.warning(f"Skipping non-existent file during sync: {fp}")
    
        self._update_preview()
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
                    self.logger.info(message)
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

    def debug_filename_parsing(self, test_files=None):
        """Test the filename parsing to identify any issues."""
        if test_files is None:
            # Use queued files or some defaults
            test_files = [str(p) for p in self.queued_files] if self.queued_files else [
                "Movie.Name.2021.1080p.mkv",
                "Godzilla.vs.Kong.2021.1080p.WEBRip.x264-RARBG.mp4"
            ]
    
        if not self.filename_editor:
            self.logger.error("No filename editor connected!")
            return
    
        self.logger.debug("Testing filename parsing:")
    
        for test_file in test_files:
            try:
                path = Path(test_file)
                stem = path.stem
                ext = path.suffix
            
                self.logger.debug(f"File: {test_file}")
            
                # Parse using the filename editor
                media_info = self.filename_editor.filename_parser.parse_filename(stem)
                self.logger.debug(f"  Parsed as: {media_info}")
            
                # Generate new filename
                new_base = self.filename_editor.filename_parser.generate_filename(media_info)
                new_name = f"{new_base}{ext}"
            
                self.logger.debug(f"  New name: {new_name}")
            
                if path.name == new_name:
                    self.logger.warning(f"  ⚠️ Name unchanged: {path.name}")
                
            except Exception as e:
                self.logger.error(f"Error parsing {test_file}: {str(e)}")

    def test_integration(self):
        """Function to validate the integration between FileMover and FileNameEditor modules."""
        # Create instances
        file_mover = self
        filename_editor = self.filename_editor
        
        if not filename_editor:
            self.logger.error("No filename editor connected! Integration test failed.")
            return
        
        # Test filename parsing and generation
        test_filename = "Movie.Name.2021.1080p.mp4"
        path = Path(test_filename)
        
        self.logger.debug("Testing integration:")
        self.logger.debug(f"Original filename: {test_filename}")
        
        # Manual test of filename editor
        media_info = filename_editor.filename_parser.parse_filename(path.stem)
        new_name = filename_editor.filename_parser.generate_filename(media_info)
        self.logger.debug(f"FileNameEditor direct result: {new_name}{path.suffix}")
        
        # Test via FileMover
        self.rename_enabled = True
        self.queued_files = [path]
        
        # Set a destination path
        test_dest = Path("./test_destination")
        orig_dest_path = self.dest_path
        self.dest_path = type('obj', (object,), {
            'get': lambda: str(test_dest)
        })
        
        # Mock the operation queue
        orig_queue = self.operation_queue
        self.operation_queue = queue.Queue()
        
        # Test the update queue function
        self._update_queue_destination()
        
        # Get the result
        if not self.operation_queue.empty():
            operation = self.operation_queue.get()
            self.logger.debug(f"FileMover integration result: {Path(operation.dest).name}")
            if Path(operation.dest).name == path.name:
                self.logger.debug("ERROR: Filename was not changed!")
            else:
                self.logger.debug("SUCCESS: Filename was properly changed!")
        else:
            self.logger.debug("ERROR: No operation was queued!")
        
        # Restore original state
        self.dest_path = orig_dest_path
        self.operation_queue = orig_queue
        self.queued_files = []

    def debug_rename_setting(self):
        """Print the current rename settings for debugging."""
        self.logger.debug(f"Current rename settings:")
        self.logger.debug(f"  rename_enabled attribute: {self.rename_enabled}")
        self.logger.debug(f"  rename_var.get(): {self.rename_var.get() if hasattr(self, 'rename_var') else 'N/A'}")
        self.logger.debug(f"  config setting: {self.config.get('rename_enabled', 'Not set')}")
    
        # Check if we have queued operations and their rename flags
        if hasattr(self, 'operation_queue') and not self.operation_queue.empty():
            # Create a copy of the queue for inspection
            temp_queue = queue.Queue()
            count = 0
        
            self.logger.debug("Current operations in queue:")
            while not self.operation_queue.empty():
                op = self.operation_queue.get()
                count += 1
                self.logger.debug(f"  Operation {count}: {os.path.basename(op.source)} -> {os.path.basename(op.dest)}, rename={op.rename}")
                temp_queue.put(op)
            
            # Restore the queue
            self.operation_queue = temp_queue
        else:
            self.logger.debug("No operations in queue")

    def save_settings(self) -> Dict[str, Any]:
        """Save current settings to dictionary."""
        if hasattr(self, 'operation_var') and self.operation_var is not None:
            return {
                'operation_type': self.operation_var.get(),
                'recursive': self.recursive_var.get(),
                'preserve_metadata': self.preserve_var.get(),
                'destination_folder': self.dest_path.get() if self.dest_path else '',
                'rename_enabled': self.rename_var.get() if hasattr(self, 'rename_var') else False
            }
        return self.config.copy()

    def load_settings(self, settings: Dict[str, Any]) -> None:
        """Load settings from dictionary."""
        self.config.update(settings)
        
        if hasattr(self, 'operation_var') and self.operation_var is not None:
            self.operation_var.set(self.config.get('operation_type', 'copy'))
            self.recursive_var.set(self.config.get('recursive', True))
            self.preserve_var.set(self.config.get('preserve_metadata', True))
            if hasattr(self, 'rename_var'):
                self.rename_var.set(self.config.get('rename_enabled', False))
                self.rename_enabled = self.config.get('rename_enabled', False)
            if self.dest_path:
                self.dest_path.set(self.config.get('destination_folder', ''))