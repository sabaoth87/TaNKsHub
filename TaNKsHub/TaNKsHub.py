import os
import shutil
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from pathlib import Path
import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FileProcessor:
    """Main class for file processing operations."""
    
    def __init__(self):
        self.modules: Dict[str, ProcessingModule] = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration from config file."""
        config_path = Path('config.json')
        if config_path.exists():
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                'default_patterns': [],
                'enabled_modules': []
            }
            self._save_config()
    
    def _save_config(self):
        """Save current configuration to file."""
        with open('config.json', 'w') as f:
            json.dump(self.config, f, indent=4)

    def register_module(self, module: 'ProcessingModule'):
        """Register a new processing module."""
        self.modules[module.name] = module
        logger.info(f"Registered module: {module.name}")

    def process_files(self, 
                     source_paths: List[str], 
                     destination_dir: str,
                     operation: str = 'copy',
                     filename_patterns: Optional[List[Dict]] = None) -> None:
        """
        Process files according to specified operations and patterns.
        
        Args:
            source_paths: List of source file paths
            destination_dir: Destination directory
            operation: 'copy' or 'move'
            filename_patterns: List of pattern dictionaries for filename processing
        """
        dest_path = Path(destination_dir)
        dest_path.mkdir(parents=True, exist_ok=True)

        for source_path in source_paths:
            try:
                source = Path(source_path)
                if not source.exists():
                    logger.error(f"Source path does not exist: {source_path}")
                    continue

                # Process filename
                new_filename = self._process_filename(source.name, filename_patterns)
                destination = dest_path / new_filename

                # Perform file operation
                if operation == 'copy':
                    shutil.copy2(source, destination)
                    logger.info(f"Copied {source} to {destination}")
                elif operation == 'move':
                    shutil.move(source, destination)
                    logger.info(f"Moved {source} to {destination}")
                else:
                    logger.error(f"Unknown operation: {operation}")

            except Exception as e:
                logger.error(f"Error processing file {source_path}: {str(e)}")

    def _process_filename(self, 
                         filename: str, 
                         patterns: Optional[List[Dict]] = None) -> str:
        """
        Process filename according to specified patterns.
        
        Args:
            filename: Original filename
            patterns: List of pattern dictionaries with 'type' and 'params'
        
        Returns:
            Processed filename
        """
        if not patterns:
            return filename

        result = filename
        for pattern in patterns:
            pattern_type = pattern.get('type', '')
            params = pattern.get('params', {})

            if pattern_type == 'truncate':
                max_length = params.get('length', 0)
                if max_length > 0:
                    name, ext = os.path.splitext(result)
                    result = name[:max_length] + ext

            elif pattern_type == 'replace':
                old = params.get('old', '')
                new = params.get('new', '')
                result = result.replace(old, new)

            elif pattern_type == 'regex':
                pattern_str = params.get('pattern', '')
                replacement = params.get('replacement', '')
                try:
                    result = re.sub(pattern_str, replacement, result)
                except re.error as e:
                    logger.error(f"Invalid regex pattern: {str(e)}")

        return result

class ProcessingModule(ABC):
    """Abstract base class for processing modules."""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def process(self, file_path: Path) -> None:
        """Process a file according to module's functionality."""
        pass

    @abstractmethod
    def get_supported_operations(self) -> List[str]:
        """Return list of operations supported by this module."""
        pass

def main():
    # Example usage
    processor = FileProcessor()
    
    # Example patterns for filename processing
    patterns = [
        {
            'type': 'truncate',
            'params': {'length': 10}
        },
        {
            'type': 'replace',
            'params': {'old': ' ', 'new': '_'}
        },
        {
            'type': 'regex',
            'params': {
                'pattern': r'[\(\)]',
                'replacement': ''
            }
        }
    ]
    
    # Process some files
    source_files = ['example1.txt', 'example2.txt']
    processor.process_files(
        source_paths=source_files,
        destination_dir='processed_files',
        operation='copy',
        filename_patterns=patterns
    )

if __name__ == "__main__":
    main()
