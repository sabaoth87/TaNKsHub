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

"""
Additional improvements for drag and drop functionality with detailed logging
and better handling of edge cases.
"""

class DragDropHandler:
    """Helper class to manage drag and drop operations with better debugging."""
    
    def __init__(self, logger):
        self.logger = logger
    
    def parse_dropped_files(self, data):
        """
        Parse file paths from drag and drop data with detailed logging.
        
        Args:
            data: The data string from the drag and drop event.
            
        Returns:
            list: A list of parsed file paths.
        """
        self.logger.debug(f"Raw drop data: {repr(data)}")
        
        # Different operating systems format drag-drop data differently
        # Windows: Paths with spaces are enclosed in curly braces
        # macOS: Paths are separated by newlines
        # Linux: Various formats depending on desktop environment
        
        files = []
        
        # Check if this is a macOS-style drop (paths separated by newlines)
        if '\n' in data and not (data.startswith('{') or '{' in data):
            self.logger.debug("Detected macOS-style drop (newline separated)")
            files = [path.strip() for path in data.split('\n') if path.strip()]
            
        # Check if this is a simple list of space-separated paths (no braces)
        elif ' ' in data and not ('{' in data or '}' in data):
            self.logger.debug("Detected simple space-separated paths")
            files = [path.strip() for path in data.split() if path.strip()]
            
        # Handle Windows-style drop (paths with spaces in curly braces)
        else:
            self.logger.debug("Detected Windows-style drop (curly braces)")
            
            # If it's a single path in braces
            if data.startswith('{') and data.endswith('}') and data.count('{') == 1:
                self.logger.debug("Single path in braces")
                files = [data.strip('{}')]
                
            # Multiple paths potentially with braces
            else:
                self.logger.debug("Multiple paths with potential braces")
                current_file = ""
                in_braces = False
                
                for char in data:
                    if char == '{':
                        in_braces = True
                        # Don't include the brace in the path
                    elif char == '}':
                        in_braces = False
                        if current_file:
                            files.append(current_file)
                            current_file = ""
                    elif char.isspace() and not in_braces:
                        if current_file:
                            files.append(current_file)
                            current_file = ""
                    else:
                        current_file += char
                
                # Add the last file if there is one
                if current_file:
                    files.append(current_file)
        
        # Log the parsed file list
        self.logger.debug(f"Parsed {len(files)} files from drop data:")
        for i, file_path in enumerate(files):
            self.logger.debug(f"  {i+1}: {file_path}")
        
        # Clean the paths (remove quotes, normalize slashes)
        cleaned_files = []
        for path in files:
            # Remove potential quotes
            path = path.strip('"\'')
            # Normalize path separators
            path = path.replace('\\', '/')
            # Skip empty paths
            if path:
                cleaned_files.append(path)
        
        self.logger.debug(f"Final cleaned file list: {len(cleaned_files)} files")
        return cleaned_files

class ThreadMonitor:
    """Monitors thread execution and can recover from hung threads."""
    
    def __init__(self, app):
        self.app = app
        self.monitored_threads = {}
        self.logger = logging.getLogger(__name__)
    
    def register_thread(self, thread, name, timeout_seconds=60):
        """Register a thread to be monitored."""
        thread_id = id(thread)
        self.monitored_threads[thread_id] = {
            'thread': thread,
            'name': name,
            'start_time': time.time(),
            'timeout': timeout_seconds,
            'completed': False
        }
        self.logger.debug(f"Registered thread: {name} with ID {thread_id}")
        return thread_id
    
    def mark_completed(self, thread_id):
        """Mark a thread as completed."""
        if thread_id in self.monitored_threads:
            self.monitored_threads[thread_id]['completed'] = True
            self.logger.debug(f"Thread {self.monitored_threads[thread_id]['name']} marked as completed")
    
    def check_threads(self):
        """Check monitored threads for timeouts."""
        import time
        current_time = time.time()
        
        for thread_id, info in list(self.monitored_threads.items()):
            # Skip completed threads
            if info['completed']:
                # Clean up old completed threads
                if current_time - info['start_time'] > 300:  # 5 minutes
                    del self.monitored_threads[thread_id]
                continue
            
            # Check if thread is still alive
            if not info['thread'].is_alive():
                self.logger.debug(f"Thread {info['name']} completed normally")
                self.monitored_threads[thread_id]['completed'] = True
                continue
            
            # Check for timeout
            elapsed = current_time - info['start_time']
            if elapsed > info['timeout']:
                self.logger.warning(f"Thread {info['name']} appears to be hung (running for {elapsed:.1f}s)")
                # We can't force-terminate threads in Python, but we can notify the user
                if hasattr(self.app, 'root'):
                    self.app.root.after(0, lambda n=info['name']: messagebox.showwarning(
                        "Warning",
                        f"A background task ({n}) is taking longer than expected.\n"
                        "You may want to restart the application if this persists."
                    ))
                # Mark as completed to prevent repeated warnings
                self.monitored_threads[thread_id]['completed'] = True
        
        # Schedule next check
        if hasattr(self.app, 'root'):
            self.app.root.after(10000, self.check_threads)  # Check every 10 seconds

class TaNKsHubGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TaNKsHub")
        self.module_manager = ModuleManager()
        self.active_modules: Dict[str, ttk.Frame] = {}
        
        self.initialize_thread_monitor()
        self.logger = logging.getLogger(__name__)
        
        # Initialize module icons (will be populated in setup_gui)
        self.module_icons = {}
        self.load_module_icons()
        
        # Configure styles for the dashboard
        self.configure_styles()
        
        # Initialize shared file paths list before setting up GUI
        self.file_paths = []  # Store current file paths
        
        self.setup_gui()
        self.process_queues()
        
    def initialize_thread_monitor(self):
        """Initialize the thread monitor."""
        import time
        self.thread_monitor = ThreadMonitor(self)
        self.root.after(10000, self.thread_monitor.check_threads)  # Start checking after 10 seconds

    def configure_styles(self):
        """Configure ttk styles for the application."""
        style = ttk.Style()
        
        # Create a style for module cards with a border
        style.configure('Card.TFrame', borderwidth=1, relief='solid')
        
    def load_module_icons(self):
        """Load icon images for modules."""
        try:
            # Define default icons for each module type
            # You can replace these with actual file paths to your icons
            icon_size = (16, 16)
            
            # Create a simple colored square as a placeholder icon
            # In a real app, you'd load actual image files
            self.module_icons = {
                "File Mover": self.create_colored_icon("blue", icon_size),
                "File Name Editor": self.create_colored_icon("green", icon_size),
                "Media Sorter": self.create_colored_icon("orange", icon_size),
                # Add more module icons as needed
            }
            
            # Default icon for modules without a specific icon
            self.module_icons["default"] = self.create_colored_icon("gray", icon_size)
            
            logger.debug(f"Loaded {len(self.module_icons)} module icons")
        except Exception as e:
            logger.error(f"Error loading module icons: {str(e)}")
            # Create an empty default icon
            self.module_icons["default"] = self.create_colored_icon("gray", (16, 16))
            
    def create_colored_icon(self, color, size):
        """Create a simple colored square icon as a placeholder.
        In a real application, you'd load actual image files."""
        icon = tk.PhotoImage(width=size[0], height=size[1])
        for x in range(size[0]):
            for y in range(size[1]):
                icon.put(color, (x, y))
        return icon

    def run_in_background(self, task_func, callback=None, *args, **kwargs):
        """
        Run a function in a background thread to prevent UI lockup.
    
        Args:
            task_func: The function to run in the background
            callback: Optional function to call when task completes
            *args, **kwargs: Arguments to pass to task_func
        """
        import threading
    
        def _thread_task():
            result = None
            try:
                result = task_func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in background task: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
        
            # Call the callback in the main thread if provided
            if callback:
                self.root.after(0, lambda: callback(result))
    
        thread = threading.Thread(target=_thread_task, daemon=True)
        thread.start()
        return thread

    def setup_gui(self):
        # Create main notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both', padx=5, pady=5)
        
        # Create main tabs
        self.dashboard_tab = ttk.Frame(self.notebook)
        self.files_tab = ttk.Frame(self.notebook)
        
        # Create a frame to hold the modules section
        self.modules_frame = ttk.Frame(self.notebook)
        
        # Create the modules notebook inside the modules frame
        self.modules_notebook = ttk.Notebook(self.modules_frame)
        
        # Create module search/filter area
        self.create_module_filter(self.modules_frame)
        
        # Pack the modules notebook below the search area
        self.modules_notebook.pack(expand=True, fill='both', padx=5, pady=5)
        
        self.settings_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.dashboard_tab, text='Dashboard')
        self.notebook.add(self.files_tab, text='Files')
        self.notebook.add(self.modules_frame, text='Modules')
        self.notebook.add(self.settings_tab, text='Settings')
        
        self.setup_dashboard_tab()
        self.setup_files_tab()
        self.setup_modules_tab()
        self.setup_settings_tab()
        
    def setup_dashboard_tab(self):
        """Set up the dashboard tab with module summaries and status."""
        # Clear existing content
        for widget in self.dashboard_tab.winfo_children():
            widget.destroy()
            
        # Create a welcome header
        header_frame = ttk.Frame(self.dashboard_tab)
        header_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(
            header_frame,
            text="TaNKsHub Dashboard",
            font=("", 16, "bold")
        ).pack(side='left')
        
        # Add refresh button
        ttk.Button(
            header_frame,
            text="Refresh",
            command=self.setup_dashboard_tab
        ).pack(side='right')
        
        # Display system info
        info_frame = ttk.LabelFrame(self.dashboard_tab, text="System Info", padding=10)
        info_frame.pack(fill='x', padx=10, pady=5)
        
        import platform
        system_info = f"Python {platform.python_version()} on {platform.system()} {platform.release()}"
        
        ttk.Label(
            info_frame,
            text=system_info
        ).pack(anchor='w')
        # Files section
        files_frame = ttk.LabelFrame(self.dashboard_tab, text="Files", padding=10)
        files_frame.pack(fill='x', padx=10, pady=5)
        
        file_count = len(self.file_paths)
        ttk.Label(
            files_frame,
            text=f"Currently loaded: {file_count} files"
        ).pack(anchor='w')
        
        if file_count > 0:
            # Display first few files
            max_display = min(5, file_count)
            for i in range(max_display):
                ttk.Label(
                    files_frame,
                    text=f"• {os.path.basename(self.file_paths[i])}"
                ).pack(anchor='w', padx=10)
                
            if file_count > max_display:
                ttk.Label(
                    files_frame,
                    text=f"... and {file_count - max_display} more"
                ).pack(anchor='w', padx=10)
        else:
            ttk.Label(
                files_frame,
                text="No files loaded. Drag and drop files or click the Files tab to add some."
            ).pack(anchor='w', padx=10)

        # Module summary section
        modules_frame = ttk.LabelFrame(self.dashboard_tab, text="Modules", padding=10)
        modules_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create a canvas with scrollbar for module cards
        canvas_frame = ttk.Frame(modules_frame)
        canvas_frame.pack(fill='both', expand=True)
        
        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        
        # Configure canvas
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Frame inside canvas for module cards
        module_cards_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=module_cards_frame, anchor='nw')
        
        # Add module cards
        self.create_module_summary_cards(module_cards_frame)
        
        # Update canvas scroll region when module_cards_frame changes size
        module_cards_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        
    def create_module_summary_cards(self, parent):
        """Create summary cards for each module."""
        # Get all modules
        all_modules = list(self.module_manager.modules.values())
        enabled_count = len([m for m in all_modules if m.enabled])
        
        # Show enabled count
        ttk.Label(
            parent,
            text=f"Enabled: {enabled_count}/{len(all_modules)} modules",
            font=("", 10, "bold")
        ).pack(anchor='w', padx=5, pady=5)
        
        # Create a card for each module
        for module in all_modules:
            card_frame = ttk.Frame(parent, relief="solid", borderwidth=1)
            card_frame.pack(fill='x', padx=5, pady=5, ipadx=5, ipady=5)
            
            # Add module name and status
            header_frame = ttk.Frame(card_frame)
            header_frame.pack(fill='x', padx=5, pady=5)
            
            # Get the appropriate icon
            icon = self.module_icons.get(module.name, self.module_icons.get("default"))
            icon_label = ttk.Label(header_frame, image=icon)
            icon_label.pack(side='left', padx=5)
            
            title_frame = ttk.Frame(header_frame)
            title_frame.pack(side='left', fill='x', expand=True)
            
            ttk.Label(
                title_frame,
                text=module.name,
                font=("", 11, "bold")
            ).pack(anchor='w')
            
            ttk.Label(
                title_frame,
                text=module.description,
                font=("", 9, "italic")
            ).pack(anchor='w')
            
            # Status indicator - green for enabled, red for disabled
            status_color = "green" if module.enabled else "red"
            status_text = "Enabled" if module.enabled else "Disabled"
            
            status_frame = ttk.Frame(header_frame)
            status_frame.pack(side='right', padx=5)          
        
    def create_module_filter(self, parent):
        """Create a search/filter area for modules."""
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill='x', padx=5, pady=5)
        
        # Search entry
        ttk.Label(filter_frame, text="Search Modules:").pack(side='left', padx=5)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side='left', padx=5)
        
        # Bind search entry to filter function
        self.search_var.trace_add('write', self.filter_modules)
        
        # Category filter
        ttk.Label(filter_frame, text="Category:").pack(side='left', padx=5)
        self.category_var = tk.StringVar(value="All")
        category_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.category_var,
            values=["All", "Files", "Media", "Utilities"],
            width=15
        )
        category_combo.pack(side='left', padx=5)
        
        # Bind category combobox to filter function
        category_combo.bind("<<ComboboxSelected>>", lambda e: self.filter_modules())
        
        # Reset button
        ttk.Button(
            filter_frame,
            text="Reset Filters",
            command=self.reset_filters
        ).pack(side='right', padx=5)
        
    def filter_modules(self, *args):
        """Filter modules based on search text and category."""
        search_text = self.search_var.get().lower()
        category = self.category_var.get()
        
        # Get all modules (enabled or not)
        all_modules = list(self.module_manager.modules.values())
        
        # Store current tab selection
        current_tab = self.modules_notebook.select()
        
        # Clear existing tabs
        for tab in self.modules_notebook.tabs():
            self.modules_notebook.forget(tab)
        
        # Track if we found any matches
        found_modules = False
        
        # Rebuild tabs with filter applied
        for module in all_modules:
            # Check if module matches search text
            name_match = search_text in module.name.lower()
            desc_match = search_text in module.description.lower()
            
            # Check if module matches category
            # In a real app, you would have a category attribute on each module
            category_match = (category == "All" or 
                             (category == "Files" and "File" in module.name) or
                             (category == "Media" and "Media" in module.name) or
                             (category == "Utilities" and not ("File" in module.name or "Media" in module.name)))
            
            if (name_match or desc_match) and category_match:
                found_modules = True
                
                # Create a tab for this module
                module_tab = ttk.Frame(self.modules_notebook, padding=5)
                
                # Get the appropriate icon
                icon = self.module_icons.get(module.name, self.module_icons.get("default"))
                
                # Add the tab
                self.modules_notebook.add(
                    module_tab, 
                    text=module.name,
                    image=icon,
                    compound=tk.LEFT
                )
                
                # Set up the tab content
                self.setup_module_tab_content(module_tab, module)
                
                # Store reference to module's frame
                self.active_modules[module.name] = module_tab
        
        # If no modules match, show a message
        if not found_modules:
            no_match_tab = ttk.Frame(self.modules_notebook)
            self.modules_notebook.add(no_match_tab, text="No Matches")
            
            ttk.Label(
                no_match_tab,
                text="No modules match your search criteria",
                padding=20
            ).pack(expand=True)
        
        # Try to restore the previous tab selection or select the first tab
        if current_tab and current_tab in self.modules_notebook.tabs():
            self.modules_notebook.select(current_tab)
        elif self.modules_notebook.tabs():
            self.modules_notebook.select(0)
    
    def reset_filters(self):
        """Reset search filters and show all modules."""
        self.search_var.set("")
        self.category_var.set("All")
        self.setup_modules_tab()  # Rebuild all tabs
        
    def setup_module_tab_content(self, tab_frame, module):
        """Set up the content for a module tab."""
        # Module info and enable/disable control
        header_frame = ttk.Frame(tab_frame)
        header_frame.pack(fill='x', padx=5, pady=5)
        
        # Module description
        ttk.Label(
            header_frame,
            text=module.description,
            font=("", 10, "italic")
        ).pack(side='left', padx=5)
        
        # Enable/disable checkbox
        enabled_var = tk.BooleanVar(value=module.enabled)
        ttk.Checkbutton(
            header_frame,
            text="Enabled",
            variable=enabled_var,
            command=lambda m=module, v=enabled_var: self.toggle_module(m, v)
        ).pack(side='right', padx=5)
        
        # Get and pack module's settings widget
        settings_widget = module.get_settings_widget(tab_frame)
        if settings_widget:
            settings_widget.pack(fill='both', expand=True, padx=5, pady=5)

    def setup_files_tab(self):
        """Set up the files management interface with improved controls."""
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
    
        # Add a file list display with improved UI
        self.file_list_frame = ttk.LabelFrame(self.files_tab, text="Selected Files", padding=5)
        self.file_list_frame.pack(fill='both', expand=True, padx=5, pady=5)
    
        # Add buttons for file list actions
        self.file_list_actions_frame = ttk.Frame(self.file_list_frame)
        self.file_list_actions_frame.pack(fill='x', padx=5, pady=5)
    
        # File count label
        self.file_count_label = ttk.Label(self.file_list_actions_frame, text="Total: 0 files")
        self.file_count_label.pack(side='left', padx=5)
    
        # Clear all button
        ttk.Button(
            self.file_list_actions_frame,
            text="Clear All",
            command=self.clear_file_list
        ).pack(side='right', padx=5)
    
        # Add files button
        ttk.Button(
            self.file_list_actions_frame,
            text="Add Files",
            command=self.select_files
        ).pack(side='right', padx=5)
    
        # Initialize with empty list
        self.update_file_list_display([])

    def setup_modules_tab(self):
        """Set up the modules management interface with each module in its own tab."""
        logger.debug("Setting up modules tab")
    
        # Reset filters to ensure all modules are shown
        if hasattr(self, 'search_var'):
            self.search_var.set("")
        if hasattr(self, 'category_var'):
            self.category_var.set("All")
    
        # Clear existing tabs in the modules notebook
        for tab in self.modules_notebook.tabs():
            self.modules_notebook.forget(tab)
        self.active_modules.clear()
    
        # Get all modules - we'll show all but highlight enabled ones
        all_modules = list(self.module_manager.modules.values())
        logger.debug(f"Found {len(all_modules)} total modules")
    
        # Create a tab for each module
        for module in all_modules:
            logger.debug(f"Creating tab for module: {module.name}")
            
            # Create a frame for this module's tab
            module_tab = ttk.Frame(self.modules_notebook, padding=5)
            
            # Get the appropriate icon for this module
            icon = self.module_icons.get(module.name, self.module_icons.get("default"))
            
            # Add the tab with icon and text
            self.modules_notebook.add(module_tab, text=module.name, image=icon, compound=tk.LEFT)
            
            # Set up the content for this module's tab
            self.setup_module_tab_content(module_tab, module)
            
            # Store reference to module's frame
            self.active_modules[module.name] = module_tab
            logger.debug(f"Successfully created tab for {module.name}")
    
        # Add a message if no modules are available
        if not self.active_modules:
            logger.debug("No modules found, adding placeholder tab")
            no_modules_tab = ttk.Frame(self.modules_notebook)
            
            # Use a default icon
            self.modules_notebook.add(
                no_modules_tab, 
                text="No Modules",
                image=self.module_icons.get("default"),
                compound=tk.LEFT
            )
            
            ttk.Label(
                no_modules_tab,
                text="No modules currently available",
                padding=20
            ).pack(expand=True)

    def add_memory_management_to_settings(self):
        """Add memory management to settings tab."""
        memory_frame = ttk.LabelFrame(
            self.settings_tab,
            text="Memory Management",
            padding=5
        )
        memory_frame.pack(fill='x', padx=5, pady=5)
    
        ttk.Button(
            memory_frame,
            text="Free Memory",
            command=self.free_memory
        ).pack(padx=5, pady=5)

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

        # Save settings button
        self.add_memory_management_to_settings()

    def setup_dashboard_tab(self):
        """Set up the dashboard tab with module summaries and status."""
        # Clear existing content
        for widget in self.dashboard_tab.winfo_children():
            widget.destroy()
            
        # Create a welcome header
        header_frame = ttk.Frame(self.dashboard_tab)
        header_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(
            header_frame,
            text="TaNKsHub Dashboard",
            font=("", 16, "bold")
        ).pack(side='left')
        
        # Add refresh button
        ttk.Button(
            header_frame,
            text="Refresh",
            command=self.setup_dashboard_tab
        ).pack(side='right')
        
        # Create a frame that will contain all dashboard content
        content_frame = ttk.Frame(self.dashboard_tab)
        content_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create left and right columns
        left_column = ttk.Frame(content_frame)
        left_column.pack(side='left', fill='both', expand=True, padx=5)
        
        # Right column
        right_column = ttk.Frame(content_frame)
        right_column.pack(side='right', fill='both', expand=True, padx=5)
    
        # Add API Usage Panel to right column, before or after the modules summary
        self.create_api_usage_panel(right_column)
    
        # Modules summary panel
        self.create_modules_summary_panel(right_column)

        # System info panel (left column, top)
        self.create_system_info_panel(left_column)
        
        # Files panel (left column, bottom)
        self.create_files_panel(left_column)
        
        # Modules summary panel (right column)
        self.create_modules_summary_panel(right_column)
    
    def create_system_info_panel(self, parent):
        """Create the system info panel for the dashboard."""
        info_frame = ttk.LabelFrame(parent, text="System Info", padding=10)
        info_frame.pack(fill='x', padx=5, pady=5)
        
        import platform
        system_info = f"Python {platform.python_version()} on {platform.system()} {platform.release()}"
        
        ttk.Label(
            info_frame,
            text=system_info
        ).pack(anchor='w')
        
        # Add current time 
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ttk.Label(
            info_frame,
            text=f"Current time: {now}"
        ).pack(anchor='w', pady=5)
        
        # Application info
        ttk.Label(
            info_frame,
            text="TaNKsHub - Media File Management Tool",
            font=("", 9, "bold")
        ).pack(anchor='w', pady=5)
        
        ttk.Label(
            info_frame,
            text="Version: 1.0.0",
            font=("", 9)
        ).pack(anchor='w')
    
    def create_files_panel(self, parent):
        """Create the files info panel for the dashboard."""
        files_frame = ttk.LabelFrame(parent, text="Current Files", padding=10)
        files_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        file_count = len(self.file_paths)
        ttk.Label(
            files_frame,
            text=f"Currently loaded: {file_count} files",
            font=("", 10, "bold")
        ).pack(anchor='w', pady=5)
        
        # Create scrollable frame for file list
        file_list_frame = ttk.Frame(files_frame)
        file_list_frame.pack(fill='both', expand=True)
        
        # Add scrollbar and canvas for scrolling
        canvas = tk.Canvas(file_list_frame)
        scrollbar = ttk.Scrollbar(file_list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        if file_count > 0:
            # Display files in the scrollable frame
            for i, file_path in enumerate(self.file_paths):
                file_frame = ttk.Frame(scrollable_frame)
                file_frame.pack(fill='x', pady=2)
                
                # Get file extension and determine icon color
                ext = Path(file_path).suffix.lower()
                icon_color = "blue"  # Default
                
                if ext in ['.mp4', '.mkv', '.avi', '.mov']:
                    icon_color = "red"  # Video files
                elif ext in ['.jpg', '.png', '.gif']:
                    icon_color = "green"  # Image files
                elif ext in ['.mp3', '.wav', '.flac']:
                    icon_color = "purple"  # Audio files
                    
                # Create colored icon indicator
                icon = self.create_colored_icon(icon_color, (12, 12))
                icon_label = ttk.Label(file_frame, image=icon)
                icon_label.image = icon  # Keep a reference to prevent garbage collection
                icon_label.pack(side='left', padx=5)
                
                # Display filename
                ttk.Label(
                    file_frame,
                    text=os.path.basename(file_path)
                ).pack(side='left')
        else:
            ttk.Label(
                scrollable_frame,
                text="No files loaded. Drag and drop files or click the Files tab to add some.",
                wraplength=250
            ).pack(anchor='w', padx=10, pady=20)
        
        # Add a button to go to the files tab
        ttk.Button(
            files_frame,
            text="Manage Files",
            command=lambda: self.notebook.select(self.files_tab)
        ).pack(pady=10)
    
    def create_modules_summary_panel(self, parent):
        """Create the modules summary panel for the dashboard."""
        modules_frame = ttk.LabelFrame(parent, text="Modules", padding=10)
        modules_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Get all modules
        all_modules = list(self.module_manager.modules.values())
        enabled_modules = [m for m in all_modules if m.enabled]
        
        # Show enabled count
        ttk.Label(
            modules_frame,
            text=f"Enabled: {len(enabled_modules)}/{len(all_modules)} modules",
            font=("", 10, "bold")
        ).pack(anchor='w', pady=5)
        
        # Create scrollable frame for module cards
        cards_frame = ttk.Frame(modules_frame)
        cards_frame.pack(fill='both', expand=True)
        
        # Add scrollbar and canvas for scrolling
        canvas = tk.Canvas(cards_frame)
        scrollbar = ttk.Scrollbar(cards_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Keep references to card widgets to prevent garbage collection
        self.module_cards = []
        
        # Create a card for each module
        for module in all_modules:
            card = self.create_module_card(scrollable_frame, module)
            self.module_cards.append(card)
        
        # Add a button to go to the modules tab
        ttk.Button(
            modules_frame,
            text="Manage Modules",
            command=lambda: self.notebook.select(self.modules_frame)
        ).pack(pady=10)
    
    def create_module_card(self, parent, module):
        """Create a summary card for a module."""
        # Create a bordered frame for the card
        card_frame = ttk.Frame(parent)
        card_frame.pack(fill='x', pady=5, padx=5)
        
        # Create an inner frame with padding and border
        inner_frame = ttk.Frame(card_frame, padding=8)
        inner_frame.pack(fill='x', expand=True)
        
        # Add a thin border around the card
        card_border = ttk.Frame(card_frame, style='Card.TFrame')
        card_border.place(x=0, y=0, relwidth=1, relheight=1)
        
        # Get the appropriate icon
        icon = self.module_icons.get(module.name, self.module_icons.get("default"))
        
        # Header with icon and title
        header_frame = ttk.Frame(inner_frame)
        header_frame.pack(fill='x', pady=(0, 5))
        
        icon_label = ttk.Label(header_frame, image=icon)
        icon_label.image = icon  # Keep a reference to prevent garbage collection
        icon_label.pack(side='left', padx=(0, 5))
        
        ttk.Label(
            header_frame,
            text=module.name,
            font=("", 11, "bold")
        ).pack(side='left')
        
        # Status indicator
        status_text = "Enabled" if module.enabled else "Disabled"
        status_color = "green" if module.enabled else "red"
        
        status_frame = ttk.Frame(header_frame)
        status_frame.pack(side='right')
        
        status_icon = self.create_colored_icon(status_color, (10, 10))
        status_icon_label = ttk.Label(status_frame, image=status_icon)
        status_icon_label.image = status_icon  # Keep a reference
        status_icon_label.pack(side='left', padx=2)
        
        ttk.Label(
            status_frame,
            text=status_text,
            font=("", 9)
        ).pack(side='right')
        
        # Module description
        ttk.Label(
            inner_frame,
            text=module.description,
            font=("", 9, "italic"),
            wraplength=300
        ).pack(anchor='w', pady=2)
        
        # Module-specific info (example)
        # In a real application, you would show module-specific stats here
        if module.name == "File Mover":
            ttk.Label(
                inner_frame,
                text="Files processed: 0",
                font=("", 9)
            ).pack(anchor='w')
        elif module.name == "File Name Editor":
            ttk.Label(
                inner_frame,
                text="Files renamed: 0",
                font=("", 9)
            ).pack(anchor='w')
        elif module.name == "Media Sorter":
            ttk.Label(
                inner_frame,
                text="Files analyzed: 0",
                font=("", 9)
            ).pack(anchor='w')
            
        # Quick action button
        action_frame = ttk.Frame(inner_frame)
        action_frame.pack(fill='x', pady=(5, 0))
        
        # Different actions based on current state
        if module.enabled:
            ttk.Button(
                action_frame,
                text="Configure",
                command=lambda m=module: self.goto_module_tab(m)
            ).pack(side='right', padx=2)
        else:
            ttk.Button(
                action_frame,
                text="Enable",
                command=lambda m=module: self.enable_module_and_goto(m)
            ).pack(side='right', padx=2)
        
        # Store icon references in the card frame
        card_frame.icon = icon
        card_frame.status_icon = status_icon
        
        return card_frame
    
    def goto_module_tab(self, module):
        """Navigate to a specific module's tab."""
        # Select the modules tab first
        self.notebook.select(self.modules_frame)
        
        # Find the module's tab index
        for i, tab_id in enumerate(self.modules_notebook.tabs()):
            tab_text = self.modules_notebook.tab(tab_id, "text")
            if tab_text == module.name:
                self.modules_notebook.select(i)
                break
    
    def enable_module_and_goto(self, module):
        """Enable a module and navigate to its tab."""
        module.enabled = True
        if hasattr(module, 'on_enable_changed'):
            module.on_enable_changed(True)
        
        # Save the new state
        if hasattr(self.module_manager, '_save_config'):
            self.module_manager._save_config()
        
        # Update the dashboard
        self.setup_dashboard_tab()
        
        # Navigate to the module's tab
        self.goto_module_tab(module)
    
    def toggle_module(self, module: BaseModule, enabled_var: tk.BooleanVar):
        """Toggle module enabled state."""
        module.enabled = enabled_var.get()
        if hasattr(module, 'on_enable_changed'):
            module.on_enable_changed(enabled_var.get())
            if enabled_var.get():
                # If module is being enabled, send current file list
                if hasattr(module, 'sync_with_main_list'):
                    module.sync_with_main_list(self.file_paths)
        if hasattr(self.module_manager, '_save_config'):
            self.module_manager._save_config()  # Save the new state
        
        # Refresh the dashboard if it exists
        if hasattr(self, 'dashboard_tab'):
            self.setup_dashboard_tab()
            
        logger.info(f"Module {module.name} {'enabled' if module.enabled else 'disabled'}")

    def handle_drop(self, event):
        """Handle file drop events with robust parsing for all operating systems."""
        # Create a handler if it doesn't exist
        if not hasattr(self, 'drop_handler'):
            self.drop_handler = DragDropHandler(self.logger)
    
        # Use the handler to parse the drop data
        files = self.drop_handler.parse_dropped_files(event.data)
    
        # Update file list display
        self.update_file_list_display(files)
    
        # Store file paths
        self.file_paths = files
    
        # Process files with enabled modules
        self.process_files(files)

    def update_file_list_display(self, files):
        """Update the file list display with improved UI elements."""
        # Clear the existing list
        for widget in self.file_list_frame.winfo_children():
            if widget != self.file_list_actions_frame:
                widget.destroy()
    
        # Create a frame for the file list with scrollbar
        list_container = ttk.Frame(self.file_list_frame)
        list_container.pack(fill='both', expand=True, padx=5, pady=5)
    
        # Add a scrollbar
        scrollbar = ttk.Scrollbar(list_container)
        scrollbar.pack(side='right', fill='y')
    
        # Create a canvas for scrolling
        canvas = tk.Canvas(list_container, yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=canvas.yview)
    
        # Create a frame inside the canvas for the file items
        file_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=file_frame, anchor='nw', tags="file_frame")
    
        # Add each file as a row with controls
        for i, file_path in enumerate(files):
            row_frame = ttk.Frame(file_frame)
            row_frame.pack(fill='x', padx=5, pady=2)
        
            # File path display (truncated if too long)
            path = Path(file_path)
            display_text = f"{i+1}. {path.name}"
        
            # Add an icon based on file type
            ext = path.suffix.lower()
            icon_color = "blue"  # Default
        
            if ext in ['.mp4', '.mkv', '.avi', '.mov']:
                icon_color = "red"  # Video files
            elif ext in ['.jpg', '.png', '.gif']:
                icon_color = "green"  # Image files
            elif ext in ['.mp3', '.wav', '.flac']:
                icon_color = "purple"  # Audio files
            
            icon = self.create_colored_icon(icon_color, (12, 12))
            icon_label = ttk.Label(row_frame, image=icon)
            icon_label.image = icon  # Keep a reference
            icon_label.pack(side='left', padx=2)
        
            ttk.Label(row_frame, text=display_text).pack(side='left', padx=5, fill='x', expand=True)
        
            # Remove button
            remove_btn = ttk.Button(
                row_frame,
                text="✕", 
                width=3,
                command=lambda idx=i: self.remove_file(idx)
            )
            remove_btn.pack(side='right', padx=2)
        
            # Store the full path as an attribute for tooltip
            row_frame.file_path = file_path
        
            # Add tooltip for the full path on hover
            self.add_tooltip(row_frame, file_path)
    
        # Update the canvas scroll region
        file_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    
        # Update file count label
        if hasattr(self, 'file_count_label'):
            self.file_count_label.config(text=f"Total: {len(files)} files")

    def add_tooltip(self, widget, text):
        """Add a tooltip to a widget."""
        def enter(event):
            x, y, _, _ = widget.bbox("insert")
            x += widget.winfo_rootx() + 25
            y += widget.winfo_rooty() + 25
        
            # Create a toplevel window
            self.tooltip = tk.Toplevel(widget)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{x}+{y}")
        
            label = ttk.Label(self.tooltip, text=text, wraplength=500,
                             background="#ffffe0", relief="solid", borderwidth=1)
            label.pack(ipadx=5, ipady=5)
    
        def leave(event):
            if hasattr(self, 'tooltip'):
                self.tooltip.destroy()
            
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def remove_file(self, index):
        """Remove a file from the list."""
        if 0 <= index < len(self.file_paths):
            del self.file_paths[index]
            self.update_file_list_display(self.file_paths)

    def clear_file_list(self):
        """Clear the entire file list."""
        self.file_paths = []
        self.update_file_list_display([])

    def select_files(self, event=None):
        """Open file selection dialog with improved handling for multiple files."""
        new_files = filedialog.askopenfilenames(title="Select Files")
        if new_files:
            # Combine with existing files
            combined_files = self.file_paths + list(new_files)
            # Update UI and internal list
            self.update_file_list_display(combined_files)
            self.file_paths = combined_files
            # Process the new files
            self.process_files(new_files)

    def select_log_file(self):
        """Select log file location."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("All files", "*.*")]
        )
        if filename:
            self.log_file_var.set(filename)

    def free_memory(self):
        """Free memory by clearing caches and unnecessary data."""
        # Clear module caches
        for module in self.module_manager.get_enabled_modules():
            if hasattr(module, 'clear_cache'):
                module.clear_cache()
    
        # Force garbage collection
        import gc
        gc.collect()
    
        self.logger.info("Memory freed successfully")

    def process_files(self, file_paths):
        """Process files using enabled modules with background threading."""
        # Get enabled modules
        enabled_modules = self.module_manager.get_enabled_modules()
    
        if not enabled_modules:
            return  # No enabled modules
    
        # Show a progress dialog for large file sets
        if len(file_paths) > 10:
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Processing Files")
            progress_window.geometry("400x150")
            progress_window.transient(self.root)
        
            ttk.Label(progress_window, text="Processing files with enabled modules...").pack(pady=10)
        
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(
                progress_window, 
                variable=progress_var,
                maximum=len(file_paths) * len(enabled_modules),
                length=300
            )
            progress_bar.pack(pady=10)
        
            status_var = tk.StringVar(value="Starting...")
            status_label = ttk.Label(progress_window, textvariable=status_var)
            status_label.pack(pady=5)
        
            progress_window.update()
        else:
            progress_window = None
            progress_var = None
            status_var = None
    
        # Define the background processing task
        def process_task():
            processed = 0
            for module in enabled_modules:
                # Skip if module doesn't support file processing
                if not hasattr(module, 'process_file'):
                    continue
                
                for file_path in file_paths:
                    path = Path(file_path)
                    extensions = module.get_supported_extensions()
                
                    # Update progress if we have a UI
                    if progress_window:
                        processed += 1
                        progress_var.set(processed)
                        status_var.set(f"Processing with {module.name}: {path.name}")
                        self.root.after(0, progress_window.update)
            
                    # Check if module supports this file type
                    if '*' in extensions or path.suffix.lower() in extensions:
                        try:
                            # Process using the same source and destination initially
                            success = module.process_file(path, path)
                            #success = True
                            if success:
                                self.logger.info(f"Successfully processed {path} with {module.name}")
                            else:
                                self.logger.warning(f"Failed to process {path} with {module.name}")
                        except Exception as e:
                            self.logger.error(f"Error processing {path} with {module.name}: {str(e)}")
                            import traceback
                            self.logger.error(traceback.format_exc())
        
            # Close progress window if we have one
            if progress_window:
                self.root.after(0, progress_window.destroy)
    
        # Run the processing in a background thread
        self.run_in_background(process_task)

    def process_queues(self):
        """Process module queues with improved efficiency."""
        try:
            # Only process active modules that are currently visible
            current_tab = self.notebook.select()
            process_modules = self.module_manager.get_enabled_modules()
        
            # If we're in the modules tab, only process the visible module
            if current_tab == str(self.modules_frame) and hasattr(self, 'modules_notebook'):
                current_module_tab = self.modules_notebook.select()
                if current_module_tab:
                    # Get the module name from the tab text
                    for module_name, frame in self.active_modules.items():
                        if str(frame) == current_module_tab:
                            # Only process this module's queues
                            module = next((m for m in process_modules if m.name == module_name), None)
                            if module and hasattr(module, 'process_queues'):
                                try:
                                    module.process_queues()
                                except Exception as e:
                                    logger.error(f"Error processing queues for module {module_name}: {str(e)}")
                            process_modules = []  # Skip the rest
                            break
        
            # Process the remaining modules' queues
            for module in process_modules:
                if hasattr(module, 'process_queues'):
                    try:
                        module.process_queues()
                    except Exception as e:
                        logger.error(f"Error processing queues for module {module.name}: {str(e)}")
    
        except Exception as e:
            logger.error(f"Error in process_queues: {str(e)}")
    
        # Schedule next queue check with a longer interval if not in focus
        if hasattr(self, 'root'):  # Check if GUI still exists
            # Check if window has focus
            has_focus = self.root.focus_displayof() is not None
            # Use shorter interval when in focus, longer when not
            interval = 100 if has_focus else 500
            self.root.after(interval, self.process_queues)

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
            # Ensure config directory exists
            os.makedirs('config', exist_ok=True)
            
            with open('config/app_settings.json', 'w') as f:
                json.dump(settings, f, indent=4)
            messagebox.showinfo("Success", "Settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {str(e)}")

    def get_current_files(self) -> List[str]:
        """Return the current list of files."""
        return self.file_paths

    def create_api_usage_panel(self, parent):
        """Create the API usage statistics panel for the dashboard."""
        # Get API usage tracker from MediaSorter module if available
        api_tracker = None
        media_sorter = None
    
        for module in self.module_manager.modules.values():
            if module.name == "Media Sorter" and hasattr(module, 'api_tracker'):
                api_tracker = module.api_tracker
                media_sorter = module
                break
    
        if not api_tracker:
            # Create a new tracker if we couldn't find one
            from tankhub.core.api_tracker import APIUsageTracker
            api_tracker = APIUsageTracker()
    
        # Create the frame
        api_frame = ttk.LabelFrame(parent, text="API Usage", padding=10)
        api_frame.pack(fill='x', padx=5, pady=5)
    
        # Get current API stats
        api_stats = api_tracker.get_usage_stats()
    
        if not api_stats:
            ttk.Label(
                api_frame,
                text="No API usage data available"
            ).pack(anchor='w')
            return api_frame
    
        # Create tabs for each API
        api_notebook = ttk.Notebook(api_frame)
        api_notebook.pack(fill='both', expand=True, padx=5, pady=5)
    
        for api_name, stats in api_stats.items():
            api_tab = ttk.Frame(api_notebook)
            api_notebook.add(api_tab, text=api_name.upper())
        
            # Daily usage
            usage_frame = ttk.Frame(api_tab)
            usage_frame.pack(fill='x', pady=5)
        
            # Get daily limit and usage
            daily_limit = stats["daily_limit"]
            calls_today = stats["calls_today"]
            usage_pct = api_tracker.get_usage_percentage(api_name)
        
            ttk.Label(
                usage_frame,
                text=f"Daily Usage: {calls_today}/{daily_limit} calls ({usage_pct:.1f}%)",
                font=("", 10, "bold")
            ).pack(side='left')
        
            # Status indicator
            status_color = "green"
            if usage_pct > 90:
                status_color = "red"
            elif usage_pct > 70:
                status_color = "orange"
            
            status_icon = self.create_colored_icon(status_color, (12, 12))
            status_label = ttk.Label(usage_frame, image=status_icon)
            status_label.image = status_icon  # Keep a reference
            status_label.pack(side='left', padx=5)
        
            # Progress bar
            ttk.Progressbar(
                api_tab,
                value=min(usage_pct, 100),
                maximum=100,
                length=200
            ).pack(anchor='w', padx=5, pady=2)
        
            # API stats
            ttk.Label(
                api_tab,
                text=f"Total Calls: {stats['total_calls']}"
            ).pack(anchor='w', padx=5, pady=2)
        
            ttk.Label(
                api_tab,
                text=f"Successful: {stats['successful_calls']}"
            ).pack(anchor='w', padx=5, pady=2)
        
            ttk.Label(
                api_tab,
                text=f"Failed: {stats['failed_calls']}"
            ).pack(anchor='w', padx=5, pady=2)
        
            ttk.Label(
                api_tab,
                text=f"Last Reset: {stats['last_reset']}"
            ).pack(anchor='w', padx=5, pady=2)
        
            # Add a button to open API settings if the module is available
            if media_sorter:
                ttk.Button(
                    api_tab,
                    text="Configure API Settings",
                    command=lambda: self.goto_module_tab(media_sorter)
                ).pack(anchor='w', padx=5, pady=10)
    
        return api_frame