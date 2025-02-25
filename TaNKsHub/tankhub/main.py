import logging
from tkinterdnd2 import TkinterDnD
from tankhub.gui.main_window import TaNKsHubGUI
from tankhub.modules.file_mover import FileMoverModule
from tankhub.modules.file_name_editor import FileNameEditorModule
from tankhub.modules.media_sorter import MediaSorterModule  # Import the new module

"""
tankhub/
├── __init__.py
├── main.py
├── core/
│   ├── __init__.py
│   ├── base_module.py
│   └── module_manager.py
├── gui/
│   ├── __init__.py
│   └── main_window.py
└── modules/
    ├── __init__.py
    ├── file_mover.py
    ├── file_name_editor.py
    └── media_sorter.py    # New module for media organization
"""

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
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
    
    # Create the modules
    logger.debug("Creating FileMoverModule instance")
    file_mover = FileMoverModule()
    
    # Create the filename editor module
    logger.debug("Creating FileNameEditorModule instance")
    filename_editor = FileNameEditorModule()
    
    # Create the media sorter module
    logger.debug("Creating MediaSorterModule instance")
    media_sorter = MediaSorterModule()
    
    # Connect the modules - IMPROVED CONNECTIONS
    file_mover.filename_editor = filename_editor
    media_sorter.file_mover = file_mover
    # Direct connection between MediaSorter and FileNameEditor for better integration
    media_sorter.filename_editor = filename_editor
    
    logger.debug(f"Connected FileNameEditor to FileMover: {file_mover.filename_editor is not None}")
    logger.debug(f"Connected FileMover to MediaSorter: {media_sorter.file_mover is not None}")
    logger.debug(f"Connected FileNameEditor to MediaSorter: {media_sorter.filename_editor is not None}")

    # Verify the filename parser works
    test_filename = "Test.Movie.2021.mp4"
    try:
        media_info = filename_editor.filename_parser.parse_filename("Test.Movie.2021")
        new_name = filename_editor.filename_parser.generate_filename(media_info)
        logger.debug(f"Test parse: {test_filename} -> {new_name}.mp4")
    except Exception as e:
        logger.error(f"Error testing filename parser: {str(e)}")

    # Create GUI
    logger.debug("Creating GUI")
    app = TaNKsHubGUI(root)
    
    # Register modules with the application
    logger.debug("Registering modules")
    app.module_manager.register_module(file_mover)
    app.module_manager.register_module(filename_editor)  # Register filename editor
    app.module_manager.register_module(media_sorter)
    
    # Check registered modules
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