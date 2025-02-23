import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
from pathlib import Path
import logging
from typing import Dict, List

from tankhub.core.module_manager import ModuleManager
from tankhub.core.base_module import BaseModule

logger = logging.getLogger(__name__)

class TaNKsHubGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TaNKsHub")
        self.module_manager = ModuleManager()
        self.active_modules: Dict[str, ttk.Frame] = {}
        
        self.setup_gui()
        self.process_queues()

    def setup_gui(self):
        # Create main notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both', padx=5, pady=5)
        
        # Create main tabs
        self.files_tab = ttk.Frame(self.notebook)
        self.modules_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.files_tab, text='Files')
        self.notebook.add(self.modules_tab, text='Modules')
        self.notebook.add(self.settings_tab, text='Settings')
        
        self.setup_files_tab()
        self.setup_modules_tab()
        self.setup_settings_tab()

    def setup_files_tab(self):
        # Drop zone frame
        self.drop_frame = ttk.LabelFrame(self.files_tab, text="Drop Files", padding=10)
        self.drop_frame.pack(fill='x', padx=5, pady=5)
        
        self.drop_label = ttk.Label(
            self.drop_frame,
            text="Drag and drop files here or click to select",
            padding=20
        )
        self.drop_label.pack(expand=True)
        
        # Configure drag and drop
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>', self.handle_drop)
        self.drop_frame.bind("<Button-1>", self.select_files)

    def setup_modules_tab(self):
        # Create a frame for each module
        for module in self.module_manager.get_enabled_modules():
            module_frame = ttk.LabelFrame(
                self.modules_tab,
                text=f"{module.name} - {module.description}",
                padding=5
            )
            module_frame.pack(fill='x', padx=5, pady=5)
            
            # Get and pack module's settings widget
            settings_widget = module.get_settings_widget(module_frame)
            settings_widget.pack(fill='x', expand=True)
            
            self.active_modules[module.name] = module_frame

    def setup_settings_tab(self):
        # General settings
        self.general_settings_frame = ttk.LabelFrame(
            self.settings_tab,
            text="General Settings",
            padding=5
        )
        self.general_settings_frame.pack(fill='x', padx=5, pady=5)
        
        # Logging settings
        self.logging_frame = ttk.LabelFrame(
            self.settings_tab,
            text="Logging",
            padding=5
        )
        self.logging_frame.pack(fill='x', padx=5, pady=5)

    def handle_drop(self, event):
        """Handle file drop events."""
        files = self.root.tk.splitlist(event.data)
        files = [f.strip('{}') for f in files]  # Handle Windows paths
        self.process_files(files)

    def select_files(self, event=None):
        """Open file selection dialog."""
        files = filedialog.askopenfilenames(title="Select Files")
        if files:
            self.process_files(files)

    def process_files(self, file_paths: List[str]):
        """Process files using enabled modules."""
        for module in self.module_manager.get_enabled_modules():
            for file_path in file_paths:
                path = Path(file_path)
                if path.suffix.lower() in module.get_supported_extensions():
                    try:
                        success = module.process_file(path, path)
                        if success:
                            logger.info(f"Successfully processed {path} with {module.name}")
                        else:
                            logger.warning(f"Failed to process {path} with {module.name}")
                    except Exception as e:
                        logger.error(f"Error processing {path} with {module.name}: {str(e)}")

    def process_queues(self):
        """Process module queues."""
        for module in self.module_manager.get_enabled_modules():
            if hasattr(module, 'process_queues'):
                module.process_queues()
        
        # Schedule next queue check
        self.root.after(100, self.process_queues)