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
            # Original patterns
            r'^((?:[A-Za-z0-9.]+[. ])*?)(?:[\[(]?(\d{4})[\])]?)',
            r'^((?:[A-Za-z0-9.]+[. ])*?)\((\d{4})\)',
            r'^(.*?)[\.\s](\d{4})[\.\s]',  # More general pattern: anything followed by 4 digits
            r'^(.*?)[_\-\.\s]\((\d{4})\)',  # Title followed by (year)
            r'^(.*?)[\.\s]\[(\d{4})\]',     # Title followed by [year]
            
            # NEW PATTERNS:
            # Handle YTS and similar tagged releases with year.quality.format
            r'^(.*?)\.(\d{4})\..*?\[?(?:YTS|YIFY|RARBG).*?\]?.*?$',
            
            # Handle releases with year followed by quality/source details
            r'^(.*?)\.(\d{4})\.(?:.*?(?:WEBRip|BluRay|HDRip|DVDRip|BRRip)).*?$',
            
            # Handle releases with distributor/network like "Lifetime" after year
            r'^(.*?)\.(\d{4})\.(?:.*?(?:Lifetime|Netflix|Disney|HBO|Amazon)).*?$',
            
            # General pattern for year followed by resolution that's NOT directly attached
            r'^(.*?)[\.\s](\d{4})[\.\s](?!(?:p|i)).*?$',
            
            # Handle cases with spaces like "Movie Name 2020 (1080p)"
            r'^(.*?)\s+(\d{4})\s+(?:\(.*?\)|\[.*?\]|.*?)$',
        ]
        
        # Define patterns to AVOID matching as years (resolutions, etc.)
        self.non_year_patterns = [
            r'1080p', r'1080i', r'720p', r'720i', r'480p', r'480i', r'2160p', r'4k',
            r'4K', r'UHD', r'x264', r'x265', r'HEVC', r'XVID', r'MP4', r'MKV',
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
        logger.debug(f"Parsing filename: {filename}")
        
        # Try TV show patterns first
        for pattern in self.tv_patterns:
            match = re.match(pattern, filename)
            if match:
                logger.debug(f"Matched TV pattern: {pattern}")
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
                logger.debug(f"Matched movie pattern: {pattern}")
                title = self.clean_title(match.group(1))
                year = match.group(2)
                
                # Skip if the "year" is actually a resolution or codec
                year_text = f"{year}p" if year else ""
                if any(re.search(non_year, year_text, re.IGNORECASE) for non_year in self.non_year_patterns):
                    logger.debug(f"Skipping matched year '{year}' because it appears to be a resolution/codec")
                    continue
                
                # Validate years (typically between 1900 and current year + a few years)
                if year and 1900 <= int(year) <= 2030:
                    return MediaInfo(
                        title=title,
                        year=year
                    )
                else:
                    logger.debug(f"Matched year '{year}' is out of valid range, ignoring")
        
        # If no pattern matches, just clean the filename
        logger.debug("No pattern matched, using clean title only")
        return MediaInfo(title=self.clean_title(filename))

    def generate_filename(self, media_info: MediaInfo) -> str:
        """Generate clean filename from MediaInfo"""
        logger.debug(f"Generating filename from: {media_info}")
        
        if media_info.season and media_info.episode:
            # TV Show format: "Show Name - S01E02"
            result = f"{media_info.title} - S{media_info.season.zfill(2)}E{media_info.episode.zfill(2)}"
        elif media_info.year:
            # Movie format: "Movie Name (2024)"
            result = f"{media_info.title} ({media_info.year})"
        else:
            # Just the clean title
            result = media_info.title
            
        logger.debug(f"Generated filename: {result}")
        return result

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
            # Add other settings here
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
        """Queue a file for processing with improved path handling."""
        try:
            # Ensure we're working with Path objects
            file_path = Path(file_path) if not isinstance(file_path, Path) else file_path
        
            # Check if file exists
            if not file_path.exists():
                self.logger.warning(f"File does not exist: {file_path}")
                return False
            
            # Use resolved path for deduplication
            file_path_resolved = file_path.resolve()
        
            # Check if file is already in queue
            for queued_file in self.queued_files:
                queued_resolved = Path(queued_file).resolve()
                if queued_resolved == file_path_resolved:
                    self.logger.debug(f"File already in queue: {file_path}")
                    return True
                
            # Add to queue
            self.queued_files.append(file_path_resolved)
            self._update_preview()
            return True
        
        except Exception as e:
            self.logger.error(f"Error queueing {file_path}: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
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
        """Apply the rename changes to files with improved error handling."""
        if not self.queued_files:
            return

        success_count = 0
        error_count = 0
        unchanged_count = 0
    
        # Create a results window to show progress
        results_window = tk.Toplevel()
        results_window.title("Rename Results")
        results_window.geometry("600x400")
    
        # Results text widget
        results_text = tk.Text(results_window, wrap=tk.WORD)
        results_text.pack(fill='both', expand=True, padx=10, pady=10)
    
        # Add scrollbar
        scrollbar = ttk.Scrollbar(results_window, command=results_text.yview)
        scrollbar.pack(side='right', fill='y')
        results_text.configure(yscrollcommand=scrollbar.set)
    
        # Updated file paths
        updated_files = []

        for i, file_path in enumerate(self.queued_files):
            try:
                # Check if file still exists
                if not file_path.exists():
                    error_msg = f"File no longer exists: {file_path.name}"
                    self.logger.error(error_msg)
                    results_text.insert(tk.END, f"❌ {error_msg}\n")
                    error_count += 1
                    continue
                
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
            
                # Check if the name would actually change
                if new_path == file_path:
                    results_text.insert(tk.END, f"⚠️ {file_path.name} (unchanged)\n")
                    unchanged_count += 1
                    updated_files.append(file_path)  # Keep original path
                    continue
                
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
                results_text.insert(tk.END, f"✅ {file_path.name} -> {new_path.name}\n")
                success_count += 1
            
                # Add the new path to our updated list
                updated_files.append(new_path)
            
            except Exception as e:
                self.logger.error(f"Error renaming {file_path}: {str(e)}")
                results_text.insert(tk.END, f"❌ Error renaming {file_path.name}: {str(e)}\n")
                updated_files.append(file_path)  # Keep original path on error
                error_count += 1
    
        # Add summary to results
        results_text.insert(tk.END, f"\n=== Summary ===\n")
        results_text.insert(tk.END, f"✅ Successfully renamed: {success_count}\n")
        results_text.insert(tk.END, f"⚠️ Unchanged: {unchanged_count}\n")
        results_text.insert(tk.END, f"❌ Errors: {error_count}\n")
    
        # Add close button
        ttk.Button(
            results_window,
            text="Close",
            command=results_window.destroy
        ).pack(pady=10)
    
        # Update the queue with new paths
        self.queued_files = updated_files
        self._update_preview()
    
        # Scroll to the top
        results_text.see("1.0")

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

# Test function to verify pattern matching
def test_patterns():
    parser = FilenameParser()
    
    test_files = [
        "Richie.Rich.1994.720p.WEBRip.x264-[YTS.AM].mp4",
        "Practical.Magic.1998.720p.BluRay.x264-[YTS.AG].mkv",
        "Once.Upon.A.Main.Street.2020.Lifetime.720P.WEBRip.X264-Solar.mp4",
        "Hotel Transylvania 2012 (1080).mp4",
        "The.Matrix.1999.1080p.BluRay.x264.mp4",
        "Inception.2010.BluRay.1080p.x264.mkv",
        "Movie.1080p.2021.BluRay.mp4",  # Tricky case with resolution before year
        "Movie.2021.1080p.BluRay.mp4",  # Normal case with year before resolution
    ]
    
    for test_file in test_files:
        print(f"\nTesting: {test_file}")
        basename = test_file.rsplit('.', 1)[0]  # Remove extension
        
        media_info = parser.parse_filename(basename)
        print(f"  Parsed as: {media_info}")
        
        new_filename = parser.generate_filename(media_info)
        print(f"  New name: {new_filename}")