import logging
from tkinterdnd2 import TkinterDnD
from tankhub.gui.main_window import TaNKsHubGUI
from tankhub.modules.file_mover import FileMoverModule
from tankhub.modules.file_name_editor import FileNameEditorModule

"""
tankhub/
├── __init__.py
├── main.py
├── core/
│   ├── __init__.py         * EMPTY ATM
│   ├── base_module.py
│   └── module_manager.py
├── gui/
│   ├── __init__.py         * EMPTY ATM
│   └── main_window.py
└── modules/
    ├── __init__.py         * EMPTY ATM
    └── file_mover.py
"""

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG level
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tankhub.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    logger.debug("Starting TaNKsHub initialization")
    root = TkinterDnD.Tk()
    
    # Create the module manager and register modules BEFORE creating the GUI
    logger.debug("Creating FileMoverModule instance")
    file_mover = FileMoverModule()
    file_name_editor = FileNameEditorModule()

    # Connect modules
    file_mover.filename_editor = file_name_editor

    # Create GUI with pre-configured module manager
    logger.debug("Creating GUI")
    app = TaNKsHubGUI(root)
    
    logger.debug("Registering FileMoverModule")
    app.module_manager.register_module(file_mover)
    logger.debug("Registering FileNameEditor")
    app.module_manager.register_module(file_name_editor)
    
    logger.debug("Checking registered modules")
    enabled_modules = app.module_manager.get_enabled_modules()
    logger.debug(f"Enabled modules: {[m.name for m in enabled_modules]}")
    
    # Add method to refresh modules tab
    def refresh_modules_tab():
        logger.debug("Refreshing modules tab")
        app.setup_modules_tab()  # Re-run the setup after module registration
    
    # Schedule the refresh after all initialization
    root.after(100, refresh_modules_tab)
    
    logger.info("TaNKsHub started")
    root.mainloop()

if __name__ == "__main__":
    main()