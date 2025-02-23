# core/base_module.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from pathlib import Path  # Add this import
import tkinter as tk
from tkinter import ttk

class BaseModule(ABC):
    """Abstract base class for all modules.
    
    This is like a template that defines what every module must be able to do.
    Think of it as a contract - if you want to create a module, you must implement
    all these methods.
    """
    
    def __init__(self, name: str, description: str):
        self.name = name  # e.g., "File Mover"
        self.description = description  # e.g., "Copy or move files with progress tracking"
        self.enabled = True
        self.config: Dict[str, Any] = {}
    
    @abstractmethod
    def get_settings_widget(self, parent) -> ttk.Frame:
        """Return a widget containing module-specific settings.
        
        Example implementation in FileMoverModule:
        - Creates a frame with "Copy/Move" radio buttons
        - Adds checkboxes for recursive copying
        - Adds a progress bar
        """
        pass

    @abstractmethod
    def process_file(self, file_path: Path, dest_path: Path) -> bool:
        """Process a single file.
        
        Example implementation in FileMoverModule:
        - Takes a file like "document.txt" and copies it to new location
        - Returns True if successful, False if failed
        """
        pass

    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions.
        
        Example implementation in FileMoverModule:
        - Returns ['*'] because it can handle any file type
        """
        pass