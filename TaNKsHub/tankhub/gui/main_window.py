import os
import json
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
from pathlib import Path
from typing import Dict, List
from tankhub.core.base_module import BaseModule

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

        # Shared files list?
        self.file_paths = []  # Store current file paths

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
        
        # Configure drag and drop for both frame and label
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_label.drop_target_register(DND_FILES)
        
        # Bind drop events
        self.drop_frame.dnd_bind('<<Drop>>', self.handle_drop)
        self.drop_label.dnd_bind('<<Drop>>', self.handle_drop)
        
        # Bind click events
        self.drop_frame.bind("<Button-1>", self.select_files)
        self.drop_label.bind("<Button-1>", self.select_files)
        
        # Add a file list display
        self.file_list_frame = ttk.LabelFrame(self.files_tab, text="Selected Files", padding=5)
        self.file_list_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.file_list = tk.Text(self.file_list_frame, height=10, wrap=tk.WORD)
        self.file_list.pack(fill='both', expand=True, padx=5, pady=5)

    def setup_modules_tab(self):
        """Set up the modules management interface."""
        logger.debug("Setting up modules tab")
    
        # Clear existing content
        for widget in self.modules_tab.winfo_children():
            widget.destroy()
        self.active_modules.clear()
    
        # Module list frame
        self.module_list_frame = ttk.LabelFrame(
            self.modules_tab,
            text="Available Modules",
            padding=5
        )
        self.module_list_frame.pack(fill='x', padx=5, pady=5)
    
        # Get all enabled modules
        enabled_modules = self.module_manager.get_enabled_modules()
        logger.debug(f"Found {len(enabled_modules)} enabled modules")
    
        # Create a frame for each module
        for module in enabled_modules:
            logger.debug(f"Creating frame for module: {module.name}")
            module_frame = ttk.LabelFrame(
                self.module_list_frame,
                text=f"{module.name} - {module.description}",
                padding=5
            )
            module_frame.pack(fill='x', padx=5, pady=5)
        
            # Add enable/disable checkbox
            enabled_var = tk.BooleanVar(value=module.enabled)
            ttk.Checkbutton(
                module_frame,
                text="Enabled",
                variable=enabled_var,
                command=lambda m=module, v=enabled_var: self.toggle_module(m, v)
            ).pack(anchor='w', padx=5)
        
            # Get and pack module's settings widget
            settings_widget = module.get_settings_widget(module_frame)
            if settings_widget:
                settings_widget.pack(fill='x', expand=True, padx=5, pady=5)
            
            # Store reference to module's frame
            self.active_modules[module.name] = module_frame
            logger.debug(f"Successfully created frame for {module.name}")
    
        # Add a message if no modules are available
        if not self.active_modules:
            logger.debug("No modules found, adding placeholder message")
            ttk.Label(
                self.module_list_frame,
                text="No modules currently available",
                padding=20
            ).pack(expand=True)

    def setup_settings_tab(self):
        """Set up the application settings interface."""
        # General settings
        self.general_settings_frame = ttk.LabelFrame(
            self.settings_tab,
            text="General Settings",
            padding=5
        )
        self.general_settings_frame.pack(fill='x', padx=5, pady=5)
        
        # Theme selection
        ttk.Label(self.general_settings_frame, text="Theme:").pack(anchor='w', padx=5, pady=2)
        self.theme_var = tk.StringVar(value="default")
        theme_combo = ttk.Combobox(
            self.general_settings_frame,
            textvariable=self.theme_var,
            values=["default", "light", "dark"]
        )
        theme_combo.pack(anchor='w', padx=5, pady=2)
        
        # Logging settings
        self.logging_frame = ttk.LabelFrame(
            self.settings_tab,
            text="Logging",
            padding=5
        )
        self.logging_frame.pack(fill='x', padx=5, pady=5)
        
        # Log level
        ttk.Label(self.logging_frame, text="Log Level:").pack(anchor='w', padx=5, pady=2)
        self.log_level_var = tk.StringVar(value="INFO")
        log_level_combo = ttk.Combobox(
            self.logging_frame,
            textvariable=self.log_level_var,
            values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        )
        log_level_combo.pack(anchor='w', padx=5, pady=2)
        
        # Log file location
        ttk.Label(self.logging_frame, text="Log File:").pack(anchor='w', padx=5, pady=2)
        self.log_file_var = tk.StringVar(value="tankhub.log")
        log_file_frame = ttk.Frame(self.logging_frame)
        log_file_frame.pack(fill='x', padx=5, pady=2)
        
        ttk.Entry(log_file_frame, textvariable=self.log_file_var).pack(side='left', fill='x', expand=True)
        ttk.Button(
            log_file_frame,
            text="Browse",
            command=self.select_log_file
        ).pack(side='right', padx=5)
        
        # Save settings button
        ttk.Button(
            self.settings_tab,
            text="Save Settings",
            command=self.save_settings
        ).pack(pady=10)

    def toggle_module(self, module: BaseModule, enabled_var: tk.BooleanVar):
        """Toggle module enabled state."""
        module.enabled = enabled_var.get()
        if hasattr(self.module_manager, '_save_config'):
            self.module_manager._save_config()  # Save the new state
        logger.info(f"Module {module.name} {'enabled' if module.enabled else 'disabled'}")

    def handle_drop(self, event):
        """Handle file drop events."""
        files = event.data.split()
        files = [f.strip('{}') for f in files]  # Handle Windows paths
        
        # Update file list display
        self.file_list.delete('1.0', tk.END)
        for file_path in files:
            self.file_list.insert(tk.END, f"{os.path.basename(file_path)}\n")
        
        # Store file paths
        self.file_paths = files
        
        # Process files with enabled modules
        for file_path in files:
            path = Path(file_path)
            for module in self.module_manager.get_enabled_modules():
                if '*' in module.get_supported_extensions() or path.suffix.lower() in module.get_supported_extensions():
                    try:
                        dest_path = path  # You might want to modify this based on module
                        success = module.process_file(path, dest_path)
                        if success:
                            logger.info(f"Successfully processed {path} with {module.name}")
                        else:
                            logger.warning(f"Failed to process {path} with {module.name}")
                    except Exception as e:
                        logger.error(f"Error processing {path} with {module.name}: {str(e)}")

    def select_files(self, event=None):
        """Open file selection dialog."""
        files = filedialog.askopenfilenames(title="Select Files")
        if files:
            # Create a drop event-like structure
            class DropEvent:
                def __init__(self, files):
                    self.data = ' '.join(files)
            
            self.handle_drop(DropEvent(files))

    def select_log_file(self):
        """Select log file location."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("All files", "*.*")]
        )
        if filename:
            self.log_file_var.set(filename)

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
            # Only process queues for modules that have the method
            if hasattr(module, 'process_queues'):
                try:
                    module.process_queues()
                except Exception as e:
                    logger.error(f"Error processing queues for module {module.name}: {str(e)}")
    
        # Schedule next queue check
        if hasattr(self, 'root'):  # Check if GUI still exists
            self.root.after(100, self.process_queues)

    def save_settings(self):
        """Save application settings."""
        # Update logging configuration
        logging.getLogger().setLevel(self.log_level_var.get())
        
        # Save to config file
        settings = {
            'theme': self.theme_var.get(),
            'logging': {
                'level': self.log_level_var.get(),
                'file': self.log_file_var.get()
            }
        }
        
        try:
            with open('config/app_settings.json', 'w') as f:
                json.dump(settings, f, indent=4)
            messagebox.showinfo("Success", "Settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {str(e)}")

    def toggle_module(self, module: BaseModule, enabled_var: tk.BooleanVar):
        """Toggle module enabled state."""
        module.enabled = enabled_var.get()
        if hasattr(module, 'on_enable_changed'):
            module.on_enable_changed(enabled_var.get())
            if enabled_var.get():
                # If module is being enabled, send current file list
                if hasattr(module, 'sync_with_main_list'):
                    module.sync_with_main_list(self.file_paths)
        self.module_manager._save_config()

    def get_current_files(self) -> List[str]:
        """Return the current list of files."""
        return self.file_paths