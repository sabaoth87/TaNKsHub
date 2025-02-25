import os
import re
import logging
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import List, Dict, Any
from tankhub.core.base_module import BaseModule
from typing import Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class MediaInfo:
    title: str
    year: Optional[str] = None
    season: Optional[str] = None
    episode: Optional[str] = None

class FilenameParser:
    def __init__(self):
        # Patterns for different filename formats
        self.movie_patterns = [
            # Pattern: Movie.Name.2024.1080p...
            r'^((?:[A-Za-z0-9.]+[. ])*?)(?:[\[(]?(\d{4})[\])]?)',
            # Pattern: Movie.Name.(2024)...
            r'^((?:[A-Za-z0-9.]+[. ])*?)\((\d{4})\)',
        ]
        
        self.tv_patterns = [
            # Pattern: Show.Name.S01E02...
            r'^((?:[A-Za-z0-9.]+[. ])*?)S(\d{1,2})E(\d{1,2})',
            # Pattern: Show.Name.1x02...
            r'^((?:[A-Za-z0-9.]+[. ])*?)(\d{1,2})x(\d{1,2})',
        ]

    def clean_title(self, title: str) -> str:
        """Clean up title by replacing dots/underscores with spaces and proper capitalization"""
        # Replace dots and underscores with spaces
        title = re.sub(r'[._]', ' ', title)
        # Remove any remaining unwanted characters
        title = re.sub(r'[^\w\s-]', '', title)
        # Proper title case
        title = ' '.join(word.capitalize() for word in title.split())
        return title.strip()

    def parse_filename(self, filename: str) -> MediaInfo:
        """Parse filename and extract media information"""
        # Try TV show patterns first
        for pattern in self.tv_patterns:
            match = re.match(pattern, filename)
            if match:
                title = self.clean_title(match.group(1))
                return MediaInfo(
                    title=title,
                    season=str(int(match.group(2))),  # Remove leading zeros
                    episode=str(int(match.group(3)))
                )
        
        # Try movie patterns
        for pattern in self.movie_patterns:
            match = re.match(pattern, filename)
            if match:
                title = self.clean_title(match.group(1))
                return MediaInfo(
                    title=title,
                    year=match.group(2)
                )
        
        # If no pattern matches, just clean the filename
        return MediaInfo(title=self.clean_title(filename))

    def generate_filename(self, media_info: MediaInfo) -> str:
        """Generate clean filename from MediaInfo"""
        if media_info.season and media_info.episode:
            # TV Show format: "Show Name - S01E02"
            return f"{media_info.title} - S{media_info.season.zfill(2)}E{media_info.episode.zfill(2)}"
        elif media_info.year:
            # Movie format: "Movie Name (2024)"
            return f"{media_info.title} ({media_info.year})"
        else:
            # Just the clean title
            return media_info.title

class FileNameEditorModule(BaseModule):
    """Module for batch editing filenames."""
    
    def __init__(self):
        # Initialize the base module with name and description
        super().__init__(
            "File Name Editor",
            "Batch edit filenames with preview functionality"
        )
        
        # Initialize filename parser
        self.filename_parser = FilenameParser()

        # Preserve the extension?
        self.preserve_ext_var = tk.BooleanVar(value=True)

        # Initialize module-specific variables
        self.logger = logging.getLogger(__name__)
        self.queued_files: List[Path] = []
        
        # Store GUI elements that need to be accessed across methods
        self.preview_text = None
        self.pattern_var = None
        
        # Default settings
        self.config = {
            'pattern': '',  # Default naming pattern
            'preserve_extension': True,
            'case_sensitive': False,
            # Add other settings as needed
        }

    def get_supported_extensions(self) -> List[str]:
        """Define which file types this module can handle."""
        return ['*']  # Handle all file types
        # Or specify extensions: ['.txt', '.pdf', '.doc']

    def get_settings_widget(self, parent) -> ttk.Frame:
        """Create and return the module's settings interface."""
        frame = ttk.Frame(parent)

        # File list display
        preview_frame = ttk.LabelFrame(frame, text="File Preview", padding=5)
        preview_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.preview_text = tk.Text(preview_frame, height=4, wrap=tk.WORD)
        self.preview_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Pattern input section
        pattern_frame = ttk.LabelFrame(frame, text="Rename Pattern", padding=5)
        pattern_frame.pack(fill='x', padx=5, pady=5)
        
        self.pattern_var = tk.StringVar(value=self.config['pattern'])
        pattern_entry = ttk.Entry(pattern_frame, textvariable=self.pattern_var)
        pattern_entry.pack(fill='x', padx=5, pady=5)
        
        # Options section
        options_frame = ttk.LabelFrame(frame, text="Options", padding=5)
        options_frame.pack(fill='x', padx=5, pady=5)
        
        self.preserve_ext_var = tk.BooleanVar(value=self.config['preserve_extension'])
        ttk.Checkbutton(
            options_frame,
            text="Preserve file extensions",
            variable=self.preserve_ext_var
        ).pack(anchor='w', padx=5)

        # Action buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(
            button_frame,
            text="Preview Changes",
            command=self._preview_changes
        ).pack(side='left', padx=5)
        
        ttk.Button(
            button_frame,
            text="Apply Changes",
            command=self._apply_changes
        ).pack(side='left', padx=5)
        
        return frame

    def process_file(self, file_path: Path, dest_path: Path) -> bool:
        """Queue a file for processing."""
        try:
            if file_path not in self.queued_files:
                self.queued_files.append(file_path)
                self._update_preview()
            return True
        except Exception as e:
            self.logger.error(f"Error queueing {file_path}: {str(e)}")
            return False

    def _preview_changes(self):
        """Generate preview of filename changes."""
        if not self.queued_files:
            return
            
        self.preview_text.delete('1.0', tk.END)
        for file_path in self.queued_files:
            input_filename = Path(file_path).stem
            media_info = self.filename_parser.parse_filename(input_filename)
            # new_name = self._generate_new_name(file_path)
            new_name = self.filename_parser.generate_filename(media_info)
            self.preview_text.insert(
                tk.END,
                f"{file_path.name} → {new_name}\n"
            )

    def _apply_changes(self):
        """Apply the rename changes to files."""
        if not self.queued_files:
            return

        for file_path in self.queued_files:
            try:
                # Get the parent directory and current extension
                parent_dir = file_path.parent
                extension = file_path.suffix if self.preserve_ext_var.get() else ""
                
                # Parse and generate new name
                input_filename = file_path.stem
                media_info = self.filename_parser.parse_filename(input_filename)
                new_basename = self.filename_parser.generate_filename(media_info)
                
                # Construct new path with extension
                new_filename = f"{new_basename}{extension}"
                new_path = parent_dir / new_filename
                
                # Check if target file already exists
                if new_path.exists() and new_path != file_path:
                    # Add a number to the filename to make it unique
                    counter = 1
                    while new_path.exists():
                        numbered_name = f"{new_basename} ({counter}){extension}"
                        new_path = parent_dir / numbered_name
                        counter += 1
                
                # Perform the rename
                file_path.rename(new_path)
                self.logger.info(f"Renamed: {file_path.name} -> {new_path.name}")
                
            except Exception as e:
                self.logger.error(f"Error renaming {file_path}: {str(e)}")
                continue
        
        # Clear the queue and update display
        self.queued_files.clear()
        self._update_preview()
        self.preview_text.insert('1.0', "All files processed!\n")

    def _update_preview(self):
        """Update the preview display."""
        if self.preview_text:
            self.preview_text.delete('1.0', tk.END)
            for file_path in self.queued_files:
                self.preview_text.insert(tk.END, f"{file_path.name}\n")

    def save_settings(self) -> Dict[str, Any]:
        """Save current settings to dictionary."""
        return {
            'pattern': self.pattern_var.get() if self.pattern_var else '',
            'preserve_extension': self.preserve_ext_var.get(),
            # Add other settings as needed
        }

    def load_settings(self, settings: Dict[str, Any]) -> None:
        """Load settings from dictionary."""
        self.config.update(settings)
        
        if hasattr(self, 'pattern_var'):
            self.pattern_var.set(self.config.get('pattern', ''))
            self.preserve_ext_var.set(self.config.get('preserve_extension', True))
