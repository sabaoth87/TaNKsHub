import os
import shutil
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from pathlib import Path
import json
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from tkinterdnd2 import DND_FILES, TkinterDnD
from ..modules.TaNKsHub_QuickQopy import FileMoverModule

# Enhanced logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tankhub.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BaseModule(ABC):
    """Abstract base class for all modules."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.enabled = True
        self.config: Dict[str, Any] = {}
    
    @abstractmethod
    def get_settings_widget(self, parent) -> ttk.Frame:
        """Return a widget containing module-specific settings."""
        pass

    @abstractmethod
    def save_settings(self) -> Dict[str, Any]:
        """Save current settings to a dictionary."""
        pass

    @abstractmethod
    def load_settings(self, settings: Dict[str, Any]) -> None:
        """Load settings from a dictionary."""
        pass

class FileProcessingModule(BaseModule):
    """Base class for modules that process files."""
    
    @abstractmethod
    def process_file(self, file_path: Path, dest_path: Path) -> bool:
        """Process a single file."""
        pass

    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        pass

class ModuleManager:
    """Manages loading and execution of modules."""
    
    def __init__(self):
        self.modules: Dict[str, BaseModule] = {}
        self.config_path = Path('module_config.json')
        self._load_config()

    def register_module(self, module: BaseModule) -> None:
        """Register a new module."""
        self.modules[module.name] = module
        logger.info(f"Registered module: {module.name}")

    def get_enabled_modules(self) -> List[BaseModule]:
        """Return list of enabled modules."""
        return [mod for mod in self.modules.values() if mod.enabled]

    def _load_config(self) -> None:
        """Load module configuration from file."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                for module_name, settings in config.items():
                    if module_name in self.modules:
                        self.modules[module_name].load_settings(settings)

    def save_config(self) -> None:
        """Save current module configuration to file."""
        config = {
            name: module.save_settings() 
            for name, module in self.modules.items()
        }
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=4)

class TaNKsHubGUI:
    """Main application GUI."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("TaNKsHub")
        self.module_manager = ModuleManager()
        
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
        """Set up the main files processing interface."""
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
        
        # File list
        self.files_frame = ttk.LabelFrame(self.files_tab, text="Selected Files", padding=5)
        self.files_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.file_list = ScrolledText(self.files_frame, height=10)
        self.file_list.pack(fill='both', expand=True)
        
        # Operations frame
        self.operations_frame = ttk.LabelFrame(self.files_tab, text="Operations", padding=5)
        self.operations_frame.pack(fill='x', padx=5, pady=5)
        
        # Add module-specific operation widgets here
        
        # Process button
        self.process_button = ttk.Button(
            self.files_tab, 
            text="Process Files",
            command=self.process_files
        )
        self.process_button.pack(pady=10)

    def setup_modules_tab(self):
        """Set up the modules management interface."""
        # Module list
        self.module_list_frame = ttk.LabelFrame(
            self.modules_tab,
            text="Available Modules",
            padding=5
        )
        self.module_list_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Module settings
        self.module_settings_frame = ttk.LabelFrame(
            self.modules_tab,
            text="Module Settings",
            padding=5
        )
        self.module_settings_frame.pack(fill='both', expand=True, padx=5, pady=5)

    def setup_settings_tab(self):
        """Set up the application settings interface."""
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
        
        # Add log level selector
        ttk.Label(self.logging_frame, text="Log Level:").pack(side='left', padx=5)
        self.log_level = tk.StringVar(value="INFO")
        log_level_combo = ttk.Combobox(
            self.logging_frame,
            textvariable=self.log_level,
            values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        )
        log_level_combo.pack(side='left', padx=5)
        
        # Add log file location
        ttk.Label(self.logging_frame, text="Log File:").pack(side='left', padx=5)
        self.log_file = tk.StringVar(value="tankhub.log")
        ttk.Entry(self.logging_frame, textvariable=self.log_file).pack(
            side='left',
            padx=5,
            expand=True,
            fill='x'
        )

    def handle_drop(self, event):
        """Handle file drop events."""
        files = event.data.split()
        files = [f.strip('{}') for f in files]  # Handle Windows paths
        self.add_files(files)

    def select_files(self, event=None):
        """Open file selection dialog."""
        files = filedialog.askopenfilenames(title="Select Files")
        if files:
            self.add_files(files)

    def add_files(self, files: List[str]):
        """Add files to the processing list."""
        # Implementation here

    def process_files(self):
        """Process selected files using enabled modules."""
        # Implementation here

    def save_settings(self):
        """Save application and module settings."""
        # Implementation here

def main():
    root = TkinterDnD.Tk()
    app = TaNKsHubGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()