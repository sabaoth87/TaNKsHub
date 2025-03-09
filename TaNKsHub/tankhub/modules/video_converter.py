import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import List, Dict, Any
from tankhub.core.base_module import BaseModule

logger = logging.getLogger(__name__)

class VideoConverterModule(BaseModule):
    """Module for converting videos to MP4 format with clean filenames."""
    
    def __init__(self):
        super().__init__("Video Converter", "Convert videos to MP4 format with clean filenames")
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing VideoConverterModule")
        self.queued_files: List[Path] = []
        self.filename_editor = None  # Will be set in main.py
        self.config = {'output_directory': '', 'output_format': 'mp4'}
        
    def get_supported_extensions(self) -> List[str]:
        """Define which file types this module can handle."""
        return ['.mp4', '.avi', '.mkv', '.mov', '.wmv']

    def process_file(self, file_path: Path, dest_path: Path) -> bool:
        """Queue a file for processing."""
        try:
            file_path = Path(file_path) if not isinstance(file_path, Path) else file_path
            if not file_path.exists():
                return False
            
            # Add to queue
            self.queued_files.append(file_path.resolve())
            self._update_ui()
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding file: {str(e)}")
            return False

    def get_settings_widget(self, parent) -> ttk.Frame:
        """Create and return the settings widget."""
        try:
            self.logger.info("Creating settings widget")
            
            # Create a simple frame
            frame = ttk.Frame(parent)
            
            # Add a simple label
            ttk.Label(
                frame,
                text="Video Converter Module",
                font=("", 16)
            ).pack(padx=20, pady=20)
            
            # Add a queue display
            self.queue_text = tk.Text(frame, height=6, width=50)
            self.queue_text.pack(padx=20, pady=10)
            
            # Add some buttons
            button_frame = ttk.Frame(frame)
            button_frame.pack(padx=20, pady=10)
            
            ttk.Button(
                button_frame,
                text="Add Files",
                command=self._add_files
            ).pack(side='left', padx=5)
            
            ttk.Button(
                button_frame,
                text="Clear Queue",
                command=self._clear_queue
            ).pack(side='left', padx=5)
            
            # Add output directory selection
            dir_frame = ttk.Frame(frame)
            dir_frame.pack(padx=20, pady=10, fill='x')
            
            ttk.Label(dir_frame, text="Output Directory:").pack(side='left')
            
            self.output_dir = tk.StringVar(value=self.config.get('output_directory', ''))
            ttk.Entry(dir_frame, textvariable=self.output_dir).pack(side='left', fill='x', expand=True, padx=5)
            
            ttk.Button(
                dir_frame,
                text="Browse",
                command=self._browse_dir
            ).pack(side='right')
            
            # Convert button
            ttk.Button(
                frame,
                text="Convert Files",
                command=self._convert_files
            ).pack(pady=10)
            
            self.logger.info("Settings widget created successfully")
            return frame
            
        except Exception as e:
            self.logger.error(f"Error creating settings widget: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            
            # Return a basic frame with error message
            error_frame = ttk.Frame(parent)
            ttk.Label(
                error_frame,
                text=f"Error creating Video Converter UI: {str(e)}",
                foreground="red"
            ).pack(padx=20, pady=20)
            
            return error_frame
    
    def _add_files(self):
        """Add files via dialog"""
        try:
            file_paths = filedialog.askopenfilenames(
                title="Select Video Files",
                filetypes=[("Video Files", "*.mp4 *.avi *.mkv *.mov *.wmv")]
            )
            
            if file_paths:
                for path in file_paths:
                    self.queued_files.append(Path(path))
                self._update_ui()
                
        except Exception as e:
            self.logger.error(f"Error adding files: {str(e)}")
            messagebox.showerror("Error", f"Failed to add files: {str(e)}")
    
    def _clear_queue(self):
        """Clear the queue"""
        self.queued_files.clear()
        self._update_ui()
    
    def _browse_dir(self):
        """Browse for output directory"""
        try:
            directory = filedialog.askdirectory()
            if directory:
                self.output_dir.set(directory)
                self.config['output_directory'] = directory
        except Exception as e:
            self.logger.error(f"Error selecting directory: {str(e)}")
    
    def _convert_files(self):
        """Mock conversion function"""
        if not self.queued_files:
            messagebox.showinfo("Info", "No files to convert")
            return
            
        if not self.output_dir.get():
            messagebox.showerror("Error", "Please select an output directory")
            return
            
        messagebox.showinfo(
            "Conversion",
            f"Would convert {len(self.queued_files)} files to {self.output_dir.get()}\n\n"
            "This is a simplified version for testing the UI."
        )
        
    def _update_ui(self):
        """Update the UI elements"""
        if hasattr(self, 'queue_text') and self.queue_text:
            self.queue_text.delete('1.0', tk.END)
            if not self.queued_files:
                self.queue_text.insert(tk.END, "No files in queue")
            else:
                for file_path in self.queued_files:
                    self.queue_text.insert(tk.END, f"{file_path.name}\n")
                self.queue_text.insert(tk.END, f"\nTotal: {len(self.queued_files)} files")
                
    def process_queues(self):
        """Required by module interface but not used"""
        pass
        
    def on_enable_changed(self, enabled):
        """Handle enable/disable"""
        self.enabled = enabled
        
    def save_settings(self) -> Dict[str, Any]:
        """Save settings"""
        return self.config.copy()
        
    def load_settings(self, settings: Dict[str, Any]):
        """Load settings"""
        self.config.update(settings)