import os
import shutil
import threading
import queue
import logging
from datetime import datetime
from typing import NamedTuple, Optional, List, Dict, Any
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from tankhub.core.base_module import BaseModule

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
        
        # Processing state
        self.processing: bool = False
        self.total_operations: int = 0
        self.current_thread: Optional[threading.Thread] = None
        
        # Initialize GUI variables as None
        self.operation_var = None
        self.recursive_var = None
        self.preserve_var = None
        
        # Default settings - store actual values here
        self.config = {
            'operation_type': 'copy',
            'recursive': True,
            'preserve_metadata': True
        }

    def get_supported_extensions(self) -> List[str]:
        """Return supported file extensions (all files supported)."""
        return ['*']

    def get_settings_widget(self, parent) -> ttk.Frame:
        """Create and return the settings widget."""
        frame = ttk.Frame(parent)

        # Create variables using config values
        self.operation_var = tk.StringVar(value=self.config['operation_type'])
        self.recursive_var = tk.BooleanVar(value=self.config['recursive'])
        self.preserve_var = tk.BooleanVar(value=self.config['preserve_metadata'])

        # Operation type selection
        op_frame = ttk.LabelFrame(frame, text="Operation Type", padding=5)
        op_frame.pack(fill='x', padx=5, pady=5)
        
        self.operation_var = tk.StringVar(value=self.config['operation_type'])
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

    def save_settings(self) -> Dict[str, Any]:
        """Save current settings to dictionary."""
        # If GUI has been created, get values from widgets
        if hasattr(self, 'operation_var') and self.operation_var is not None:
            return {
                'operation_type': self.operation_var.get(),
                'recursive': self.recursive_var.get(),
                'preserve_metadata': self.preserve_var.get()
            }
        # Otherwise return current config
        return self.config.copy()

    def load_settings(self, settings: Dict[str, Any]) -> None:
        """Load settings from dictionary."""
        self.config.update(settings)
        
        # If GUI exists, update the widgets
        if hasattr(self, 'operation_var') and self.operation_var is not None:
            self.operation_var.set(self.config.get('operation_type', 'copy'))
            self.recursive_var.set(self.config.get('recursive', True))
            self.preserve_var.set(self.config.get('preserve_metadata', True))

    def process_file(self, file_path: Path, dest_path: Path) -> bool:
        """Process a single file."""
        try:
            # Create the operation
            operation = FileOperation(
                str(file_path),
                str(dest_path),
                file_path.is_file(),
                self.config['operation_type']
            )
            
            # Add to queue
            self.operation_queue.put(operation)
            
            # Start processing if not already running
            if not self.processing:
                self.total_operations = self.operation_queue.qsize()
                self.processing = True
                self.cancel_btn.configure(state="normal")
                self.current_thread = threading.Thread(
                    target=self._process_queue,
                    daemon=True
                )
                self.current_thread.start()
            
            return True
            
        except Exception as e:
            self.message_queue.put(f"Error queuing {file_path}: {str(e)}")
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
                    operation_func = shutil.copy2 if operation.operation_type == "copy" else shutil.move
                    operation_func(operation.source, operation.dest)
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
                    else:
                        shutil.move(operation.source, operation.dest)
                    self.message_queue.put(
                        f"Successfully {operation.operation_type}d folder: {os.path.basename(operation.source)}"
                    )

                # Update progress
                remaining = self.operation_queue.qsize()
                total = self.total_operations
                progress = ((total - remaining) / total) * 100
                self.progress_queue.put(
                    (progress, f"{operation.operation_type.capitalize()}ing files... ({total - remaining}/{total})")
                )
                
            except Exception as e:
                self.message_queue.put(
                    f"Error processing {os.path.basename(operation.source)}: {str(e)}"
                )

        # Processing complete
        self.processing = False
        self.progress_queue.put((100, "Ready"))
        self.cancel_btn.configure(state="disabled")

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
