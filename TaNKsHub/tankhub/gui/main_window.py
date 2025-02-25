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
        
        # Initialize module icons (will be populated in setup_gui)
        self.module_icons = {}
        self.load_module_icons()
        
        # Configure styles for the dashboard
        self.configure_styles()
        
        # Initialize shared file paths list before setting up GUI
        self.file_paths = []  # Store current file paths
        
        self.setup_gui()
        self.process_queues()
        
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
        
        right_column = ttk.Frame(content_frame)
        right_column.pack(side='right', fill='both', expand=True, padx=5)
        
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