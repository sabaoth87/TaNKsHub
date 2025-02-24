from typing import Dict, List
from pathlib import Path
import json
import logging
from tankhub.core.base_module import BaseModule

logger = logging.getLogger(__name__)

class ModuleManager:
    """Manages loading and execution of modules."""
    
    def __init__(self):
        self.modules: Dict[str, BaseModule] = {}
        self.config_path = Path('config/module_config.json')
        self._load_config()

    def _load_config(self) -> None:
        """Load module configuration from file.
        
        Example config.json:
        {
            "File Mover": {
                "enabled": true,
                "settings": {
                    "operation_type": "copy",
                    "recursive": true,
                    "preserve_metadata": true
                }
            }
        }
        """
        try:
            # Create config directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing config or create default
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    
                # Apply config to each module
                for module_name, settings in config.items():
                    if module_name in self.modules:
                        # Set module enabled state
                        self.modules[module_name].enabled = settings.get('enabled', True)
                        # Load module-specific settings
                        if 'settings' in settings:
                            self.modules[module_name].load_settings(settings['settings'])
                            
                logger.info("Loaded module configuration")
            else:
                self._save_config()  # Create default config
                logger.info("Created default module configuration")
                
        except Exception as e:
            logger.error(f"Error loading module configuration: {str(e)}")
            self._save_config()  # Create default config on error

    def _save_config(self) -> None:
        """Save current module configuration to file."""
        try:
            config = {}
            for name, module in self.modules.items():
                config[name] = {
                    'enabled': module.enabled,
                    'settings': module.save_settings()
                }
                
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
                
            logger.info("Saved module configuration")
            
        except Exception as e:
            logger.error(f"Error saving module configuration: {str(e)}")

    def register_module(self, module: BaseModule) -> None:
        """Register a new module."""
        self.modules[module.name] = module
        logger.debug(f"Registered module: {module.name}")
        logger.debug(f"Current modules: {list(self.modules.keys())}")
        self._save_config()  # Update config with new module

    def get_enabled_modules(self) -> List[BaseModule]:
        """Return list of enabled modules."""
        enabled = [mod for mod in self.modules.values() if mod.enabled]
        #logger.debug(f"Getting enabled modules. Total modules: {len(self.modules)}")
        #logger.debug(f"Enabled modules: {[m.name for m in enabled]}")
        return enabled