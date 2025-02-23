import logging
from tkinterdnd2 import TkinterDnD
from tankhub.gui.main_window import TaNKsHubGUI
from tankhub.modules.file_mover import FileMoverModule

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tankhub.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    root = TkinterDnD.Tk()
    app = TaNKsHubGUI(root)
    
    # Register the file mover module
    file_mover = FileMoverModule()
    app.module_manager.register_module(file_mover)
    
    logger.info("TaNKsHub started")
    root.mainloop()

if __name__ == "__main__":
    main()