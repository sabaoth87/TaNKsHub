import os
import re
import json
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import requests
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from tankhub.core.base_module import BaseModule
from tankhub.modules.file_mover import FileMoverModule
from tankhub.modules.file_name_editor import FileNameEditorModule, MediaInfo
from tankhub.core.api_tracker import APIUsageTracker

logger = logging.getLogger(__name__)


@dataclass
class MediaDetails:
    title: str
    year: Optional[str] = None
    genres: List[str] = None
    type: str = "unknown"  # "movie" or "tv"
    content_rating: Optional[str] = None  # Store content rating if available (e.g., PG, R, TV-MA)
    
    def __post_init__(self):
        if self.genres is None:
            self.genres = []
    
    def get_audience_category(self) -> str:
        """Determine audience category based on genres and content rating."""
        # First, check content rating if available
        if self.content_rating:
            if self.content_rating in ["F"]:
                return "Kids"
            elif self.content_rating in ["G", "TV-Y", "TV-Y7", "TV-G", "PG", "TV-PG"]:
                return "Family"
            elif self.content_rating in ["PG-13", "R", "NC-17", "TV-MA", "TV-14"]:
                return "Adult"
        
        # If no content rating, use genres to categorize
        kids_genres = ["Animation", "Family", "Children"]
        adult_genres = ["Horror", "Thriller", "Crime", "War"]
        
        # Check if any genre matches kids content
        for genre in self.genres:
            if genre in kids_genres:
                return "Kids"
            elif genre in adult_genres:
                return "Adult"
        
        # Default to family if we can't determine
        return "Adult"

class MediaSorterModule(BaseModule):
    """Module for sorting media files by genre using external API information."""
    
    def __init__(self):
        super().__init__("Media Sorter", "Sort media files by audience category, genre, and type")
        
        # API keys
        # FREE KEYS - GET YOUR OWN!!
        self.TMDB_API_KEY = 'e78d4b98a932657d06d26feb3308adb4'  # https://www.themoviedb.org/
        self.OMDB_API_KEY = '68b552d0'                          # https://www.omdbapi.com/
        #                      DON'T BE LAME. GET YOUR OWN              ^   ^   ^

        # Initialize module-specific variables
        self.logger = logging.getLogger(__name__)
        self.queued_files: List[Path] = []

        # API Usage Tracker
        self.api_tracker = APIUsageTracker()

        # Module references
        self.file_mover = None  # Will be set in main.py
        self.filename_editor = None  # Will be set in main.py - IMPROVED INTEGRATION
        
        # API settings
        self.api_key_var = None
        self.api_type_var = None
        self.api_cache = {}  # Cache API results
        self.cache_file = Path("config/media_cache.json")
        
        # Folder structure settings
        self.base_folder_var = None
        self.sort_by_var = None
        self.tv_folder_var = None
        self.movie_folder_var = None
        
        # Default settings
        self.config = {
            'api_key': self.OMDB_API_KEY,
            'api_type': 'omdb',  # tmdb, omdb
            'base_folder': 'F:\Media',
            'sort_by': 'genre',  # genre, type, year
            'tv_folder': 'TV Shows',
            'movie_folder': 'Movies',
            'unknown_folder': 'Unknown',
            'create_genre_folders': True,
            'create_type_folders': True,
            'create_audience_folders': True,  # New option for audience categorization
            'simulate': True,  # Don't actually move files, just log what would happen
            'pre_process_filenames': True  # New setting to enable filename preprocessing
        }
        
        # Load cached media info
        self._load_cache()
    
    def _save_cache(self):
        """Save media info cache to file."""
        try:
            # Create directory if it doesn't exist
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        
            # Convert MediaDetails objects to dict for JSON serialization
            cache_data = {}
            for key, value in self.api_cache.items():
                cache_data[key] = {
                    'title': value.title,
                    'year': value.year,
                    'genres': value.genres,
                    'type': value.type,
                    'content_rating': value.content_rating
                }
        
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=4)
        
            self.logger.info(f"Saved {len(self.api_cache)} media items to cache")
        except Exception as e:
            self.logger.error(f"Error saving media cache: {str(e)}")
        
    def _load_cache(self):
        """Load media info cache from file."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
            
                # Convert JSON to MediaDetails objects
                for key, value in cache_data.items():
                    self.api_cache[key] = MediaDetails(
                        title=value.get('title', ''),
                        year=value.get('year'),
                        genres=value.get('genres', []),
                        type=value.get('type', 'unknown'),
                        content_rating=value.get('content_rating')
                    )
            
                self.logger.info(f"Loaded {len(self.api_cache)} media items from cache")
            else:
                self.logger.info("No media cache file found")
        except Exception as e:
            self.logger.error(f"Error loading media cache: {str(e)}")

    def clear_cache(self):
        """Clear the API cache to free memory."""
        self.api_cache = {}
        self.logger.info("API cache cleared")

    def get_supported_extensions(self) -> List[str]:
        """Define which file types this module can handle."""
        return ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v']
    
    def get_settings_widget(self, parent) -> ttk.Frame:
        """Create and return the settings widget."""
        frame = ttk.Frame(parent)
        
        # API Settings
        api_frame = ttk.LabelFrame(frame, text="API Settings", padding=5)
        api_frame.pack(fill='x', padx=5, pady=5)
        
        # API Type selection
        ttk.Label(api_frame, text="API:").pack(anchor='w', padx=5, pady=2)
        self.api_type_var = tk.StringVar(value=self.config['api_type'])
        api_combo = ttk.Combobox(
            api_frame, 
            textvariable=self.api_type_var,
            values=["tmdb", "omdb"]
        )
        api_combo.bind("<<ComboboxSelected>>", self._on_api_type_change)
        api_combo.pack(fill='x', padx=5, pady=2)
        
        # API Key entry
        ttk.Label(api_frame, text="API Key:").pack(anchor='w', padx=5, pady=2)
        self.api_key_var = tk.StringVar(value=self._get_default_api_key())
        api_key_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, show="*")
        api_key_entry.pack(fill='x', padx=5, pady=2)
        
        # Show/Hide API key button
        self.show_key_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            api_frame,
            text="Show API Key",
            variable=self.show_key_var,
            command=lambda: api_key_entry.configure(show="" if self.show_key_var.get() else "*")
        ).pack(anchor='w', padx=5, pady=2)
        
        # Test API connection button
        ttk.Button(
            api_frame,
            text="Test API Connection",
            command=self._test_api_connection
        ).pack(padx=5, pady=5)
        
        # Folder Structure Settings
        folder_frame = ttk.LabelFrame(frame, text="Folder Structure", padding=5)
        folder_frame.pack(fill='x', padx=5, pady=5)
        
        # Base folder selection
        ttk.Label(folder_frame, text="Base Folder:").pack(anchor='w', padx=5, pady=2)
        base_folder_frame = ttk.Frame(folder_frame)
        base_folder_frame.pack(fill='x', padx=5, pady=2)
        
        self.base_folder_var = tk.StringVar(value=self.config['base_folder'])
        ttk.Entry(base_folder_frame, textvariable=self.base_folder_var).pack(side='left', fill='x', expand=True)
        ttk.Button(
            base_folder_frame,
            text="Browse",
            command=self._browse_base_folder
        ).pack(side='right', padx=5)
        
        # Sort By selection
        ttk.Label(folder_frame, text="Primary Sort (after audience category):").pack(anchor='w', padx=5, pady=2)
        self.sort_by_var = tk.StringVar(value=self.config['sort_by'])
        ttk.Combobox(
            folder_frame,
            textvariable=self.sort_by_var,
            values=["genre", "type", "year"]
        ).pack(fill='x', padx=5, pady=2)
        
        # TV and Movie folder names
        tv_movie_frame = ttk.Frame(folder_frame)
        tv_movie_frame.pack(fill='x', padx=5, pady=2)
        
        ttk.Label(tv_movie_frame, text="TV Folder:").pack(side='left', padx=5)
        self.tv_folder_var = tk.StringVar(value=self.config['tv_folder'])
        ttk.Entry(tv_movie_frame, textvariable=self.tv_folder_var, width=15).pack(side='left', padx=5)
        
        ttk.Label(tv_movie_frame, text="Movie Folder:").pack(side='left', padx=5)
        self.movie_folder_var = tk.StringVar(value=self.config['movie_folder'])
        ttk.Entry(tv_movie_frame, textvariable=self.movie_folder_var, width=15).pack(side='left', padx=5)
        
        # Folder creation options
        options_frame = ttk.LabelFrame(folder_frame, text="Organization Options", padding=5)
        options_frame.pack(fill='x', padx=5, pady=5)
        
        # NEW: Audience folder option
        self.create_audience_var = tk.BooleanVar(value=self.config['create_audience_folders'])
        ttk.Checkbutton(
            options_frame,
            text="Create Audience Folders (Adult, Family, Kids)",
            variable=self.create_audience_var
        ).pack(anchor='w', padx=5)
        
        self.create_type_var = tk.BooleanVar(value=self.config['create_type_folders'])
        ttk.Checkbutton(
            options_frame,
            text="Create Type Folders (TV/Movies)",
            variable=self.create_type_var
        ).pack(anchor='w', padx=5)
        
        self.create_genre_var = tk.BooleanVar(value=self.config['create_genre_folders'])
        ttk.Checkbutton(
            options_frame,
            text="Create Genre Folders",
            variable=self.create_genre_var
        ).pack(anchor='w', padx=5)
        
        # Simulation mode option
        simulation_frame = ttk.Frame(options_frame)
        simulation_frame.pack(fill='x', padx=5, pady=5)
        
        self.simulate_var = tk.BooleanVar(value=self.config['simulate'])
        ttk.Checkbutton(
            simulation_frame,
            text="Simulation Mode (don't actually move files)",
            variable=self.simulate_var
        ).pack(anchor='w')
        
        # NEW: Pre-process filenames option
        self.preprocess_var = tk.BooleanVar(value=self.config['pre_process_filenames'])
        ttk.Checkbutton(
            options_frame,
            text="Pre-process filenames before analysis",
            variable=self.preprocess_var,
            command=self._on_preprocess_toggle
        ).pack(anchor='w', padx=5)
        
        # File Queue and Controls
        queue_frame = ttk.LabelFrame(frame, text="Queued Files", padding=5)
        queue_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.queue_text = tk.Text(queue_frame, height=6, wrap=tk.WORD)
        self.queue_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        button_frame = ttk.Frame(queue_frame)
        button_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(
            button_frame,
            text="Analyze Files",
            command=self._analyze_files
        ).pack(side='left', padx=5)
        
        ttk.Button(
            button_frame,
            text="Sort Files",
            command=self._sort_files
        ).pack(side='left', padx=5)
        
        ttk.Button(
            button_frame,
            text="Clear Queue",
            command=self._clear_queue
        ).pack(side='left', padx=5)
        
        # Add a button to preprocess filenames
        ttk.Button(
            button_frame,
            text="Preprocess Filenames",
            command=self._preprocess_queued_filenames
        ).pack(side='left', padx=5)
        
        return frame
  
    def _show_analysis_results(self, results, failed, skipped):
        """Show results of media analysis in a results window."""
        if results:
            # Create results window
            results_window = tk.Toplevel()
            results_window.title("Media Analysis Results")
            results_window.geometry("600x400")
            results_window.transient(self.queue_text.master.master)
        
            # Results text area
            results_text = tk.Text(results_window, wrap=tk.WORD)
            results_text.pack(fill='both', expand=True, padx=10, pady=10)
        
            # Add scrollbar
            scrollbar = ttk.Scrollbar(results_text, command=results_text.yview)
            scrollbar.pack(side='right', fill='y')
            results_text.configure(yscrollcommand=scrollbar.set)
        
            # Display results
            results_text.insert(tk.END, f"== Analysis Results ==\n\n")
        
            for file_path, media_details in results:
                results_text.insert(tk.END, f"File: {file_path.name}\n")
                results_text.insert(tk.END, f"Title: {media_details.title}\n")
                results_text.insert(tk.END, f"Year: {media_details.year or 'Unknown'}\n")
                results_text.insert(tk.END, f"Type: {media_details.type}\n")
                results_text.insert(tk.END, f"Genres: {', '.join(media_details.genres)}\n\n")
        
            if failed:
                results_text.insert(tk.END, f"== Failed to analyze ({len(failed)}) ==\n")
                for file_path in failed:
                    results_text.insert(tk.END, f"- {file_path.name}\n")
                results_text.insert(tk.END, "\n")
        
            if skipped:
                results_text.insert(tk.END, f"== Skipped files ({len(skipped)}) ==\n")
                for file_path in skipped:
                    results_text.insert(tk.END, f"- {file_path.name}\n")
        
            # Add buttons for actions
            button_frame = ttk.Frame(results_window)
            button_frame.pack(pady=10)
        
            # Add button to preprocess skipped files
            if skipped:
                ttk.Button(
                    button_frame,
                    text="Preprocess Skipped Files",
                    command=lambda: self._preprocess_specific_files(skipped, results_window)
                ).pack(side='left', padx=5)
        
            # Add button to retry failed files
            if failed:
                ttk.Button(
                    button_frame,
                    text="Retry Failed Files",
                    command=lambda: self._retry_failed_files(failed, results_window)
                ).pack(side='left', padx=5)
        
            # Close button
            ttk.Button(
                button_frame,
                text="Close",
                command=results_window.destroy
            ).pack(side='left', padx=5)
    
        else:
            if failed:
                messagebox.showerror("Error", f"Failed to analyze any files. {len(failed)} files could not be processed.")
            else:
                messagebox.showinfo("Information", "No files were analyzed.")

    def _on_preprocess_toggle(self, *args):
        """Handle changes to the preprocess checkbox."""
        self.config['pre_process_filenames'] = self.preprocess_var.get()
        if self.preprocess_var.get():
            # Check if we have access to the filename editor
            if not self.filename_editor:
                messagebox.showwarning(
                    "Warning",
                    "Filename Editor module is not available. Please enable it for preprocessing."
                )
                self.preprocess_var.set(False)
                self.config['pre_process_filenames'] = False
    
    def _preprocess_queued_filenames(self):
        """Preprocess filenames for better media detection."""
        if not self.queued_files:
            messagebox.showinfo("Information", "No files in queue to process.")
            return
        
        if not self.filename_editor:
            messagebox.showerror("Error", "Filename Editor module is not available.")
            return
        
        # Create a progress dialog
        progress_window = tk.Toplevel()
        progress_window.title("Preprocessing Filenames")
        progress_window.geometry("400x150")
        progress_window.transient(self.queue_text.master.master)
        progress_window.grab_set()
        
        # Add progress bar and status label
        ttk.Label(progress_window, text="Processing filenames...").pack(pady=10)
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(
            progress_window, 
            variable=progress_var,
            maximum=len(self.queued_files),
            length=300
        )
        progress_bar.pack(pady=10)
        
        status_var = tk.StringVar(value="Preparing...")
        status_label = ttk.Label(progress_window, textvariable=status_var)
        status_label.pack(pady=5)
        
        progress_window.update()
        
        # Process files
        results = {}
        processed_count = 0
        unchanged_count = 0
        failed_count = 0
        
        for i, file_path in enumerate(self.queued_files.copy()):
            try:
                # Update progress
                progress_var.set(i)
                status_var.set(f"Processing: {file_path.name}")
                progress_window.update()
                
                # Parse filename using the filename editor
                media_info = self.filename_editor.filename_parser.parse_filename(file_path.stem)
                new_name = self.filename_editor.filename_parser.generate_filename(media_info)
                
                # Check if filename changed
                if new_name != file_path.stem:
                    # Generate new path
                    new_path = file_path.with_name(new_name + file_path.suffix)
                    
                    results[str(file_path)] = {
                        'old_name': file_path.name,
                        'new_name': new_path.name,
                        'new_path': str(new_path)
                    }
                    processed_count += 1
                else:
                    results[str(file_path)] = {
                        'old_name': file_path.name,
                        'unchanged': True
                    }
                    unchanged_count += 1
                
            except Exception as e:
                self.logger.error(f"Error preprocessing {file_path.name}: {str(e)}")
                results[str(file_path)] = {
                    'old_name': file_path.name,
                    'error': str(e)
                }
                failed_count += 1
        
        # Close progress window
        progress_window.destroy()
        
        # Show results and ask for confirmation
        if processed_count > 0:
            confirm_window = tk.Toplevel()
            confirm_window.title("Rename Confirmation")
            confirm_window.geometry("600x400")
            confirm_window.transient(self.queue_text.master.master)
            
            # Display results
            results_frame = ttk.Frame(confirm_window, padding=10)
            results_frame.pack(fill='both', expand=True)
            
            ttk.Label(
                results_frame,
                text=f"Preprocessing Results ({processed_count} changes, {unchanged_count} unchanged, {failed_count} failed)",
                font=("", 11, "bold")
            ).pack(anchor='w', pady=5)
            
            # Create a scrollable text widget to show changes
            results_text = tk.Text(results_frame, height=10, wrap=tk.WORD)
            scrollbar = ttk.Scrollbar(results_frame, command=results_text.yview)
            results_text.configure(yscrollcommand=scrollbar.set)
            
            results_text.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            # Add results to text widget
            for file_path, info in results.items():
                if info.get('unchanged', False):
                    results_text.insert(tk.END, f"- {info['old_name']} (unchanged)\n")
                elif 'error' in info:
                    results_text.insert(tk.END, f"⚠️ {info['old_name']} (error: {info['error']})\n")
                else:
                    results_text.insert(tk.END, f"✓ {info['old_name']} -> {info['new_name']}\n")
            
            # Add confirmation buttons
            button_frame = ttk.Frame(confirm_window, padding=10)
            button_frame.pack(fill='x')
            
            ttk.Button(
                button_frame,
                text="Apply Changes",
                command=lambda: self._apply_filename_changes(results, confirm_window)
            ).pack(side='left', padx=5)
            
            ttk.Button(
                button_frame,
                text="Cancel",
                command=confirm_window.destroy
            ).pack(side='right', padx=5)
            
        else:
            messagebox.showinfo(
                "Results",
                f"No files need preprocessing.\n{unchanged_count} files already have proper names."
            )
    
    def _apply_filename_changes(self, results, window):
        """Apply the filename changes from preprocessing."""
        try:
            rename_count = 0
            failed_count = 0
            
            # Create a new list for updated file paths
            updated_files = []
            
            for i, file_path in enumerate(self.queued_files):
                file_path_str = str(file_path)
                if file_path_str in results and 'new_path' in results[file_path_str]:
                    try:
                        new_path = Path(results[file_path_str]['new_path'])
                        
                        # Check if target file already exists
                        if new_path.exists() and new_path != file_path:
                            # Add a number to make it unique
                            counter = 1
                            while new_path.exists():
                                stem = new_path.stem
                                new_path = new_path.with_name(f"{stem} ({counter}){new_path.suffix}")
                                counter += 1
                        
                        # Rename the file
                        file_path.rename(new_path)
                        self.logger.info(f"Renamed: {file_path.name} -> {new_path.name}")
                        rename_count += 1
                        
                        # Update our queued_files list with the new path
                        updated_files.append(new_path)
                        
                    except Exception as e:
                        self.logger.error(f"Failed to rename {file_path}: {str(e)}")
                        failed_count += 1
                        updated_files.append(file_path)  # Keep the original path
                else:
                    # Keep unchanged files
                    updated_files.append(file_path)
            
            # Update the queue with new file paths
            self.queued_files = updated_files
            self._update_queue_display()
            
            # Close the confirmation window
            window.destroy()
            
            # Show summary
            messagebox.showinfo(
                "Rename Complete",
                f"Successfully renamed {rename_count} files.\n{failed_count} files could not be renamed."
            )
            
        except Exception as e:
            messagebox.showerror("Error", f"Error applying changes: {str(e)}")
    
    def _browse_base_folder(self):
        """Browse for base destination folder."""
        folder = filedialog.askdirectory()
        if folder:
            self.base_folder_var.set(folder)
    
    def _get_default_api_key(self):
        """Get the default API key based on selected API type."""
        api_type = self.api_type_var.get() if hasattr(self, 'api_type_var') else self.config['api_type']
        if api_type == 'tmdb':
            return self.TMDB_API_KEY
        else:  # omdb
            return self.OMDB_API_KEY

    def _test_api_connection(self):
        """Test connection to the selected API."""
        api_type = self.api_type_var.get()
        api_key = self.api_key_var.get()

        if not api_key:
            messagebox.showerror("Error", f"Please enter an API key for {api_type.upper()}")
            return
        
        try:
            # Test with a simple query
            test_title = "Inception"
            if api_type == "tmdb":
                # Test TMDb API
                response = requests.get(
                    f"https://api.themoviedb.org/3/search/movie",
                    params={
                        "api_key": api_key,
                        "query": test_title
                    }
                )
                data = response.json()
                if response.status_code == 200 and data.get("results"):
                    messagebox.showinfo("Success", f"Successfully connected to TMDb API.\n\nFound {len(data['results'])} results for '{test_title}'.")
                else:
                    messagebox.showerror("Error", f"API returned an error: {data.get('status_message', 'Unknown error')}")
            
            elif api_type == "omdb":
                # Test OMDb API
                response = requests.get(
                    f"http://www.omdbapi.com/?t={test_title}&apikey={api_key}"
                )
                data = response.json()
                if response.status_code == 200 and data.get("Response") == "True":
                    messagebox.showinfo("Success", f"Successfully connected to OMDb API.\n\nFound result for '{test_title}':\nTitle: {data.get('Title')}\nYear: {data.get('Year')}\nGenre: {data.get('Genre')}")
                else:
                    messagebox.showerror("Error", f"API returned an error: {data.get('Error', 'Unknown error')}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to API: {str(e)}")
    
    def _on_api_type_change(self, event=None):
        """Update API key when API type changes."""
        self.api_key_var.set(self._get_default_api_key())

    def _clear_queue(self):
        """Clear the file queue."""
        self.queued_files.clear()
        self._update_queue_display()
    
    def _update_queue_display(self):
        """Update the queue display with current files."""
        if not hasattr(self, 'queue_text'):
            return
            
        self.queue_text.delete('1.0', tk.END)
        
        if not self.queued_files:
            self.queue_text.insert(tk.END, "No files in queue.")
            return
            
        for file_path in self.queued_files:
            self.queue_text.insert(tk.END, f"{file_path.name}\n")
            
        self.queue_text.insert(tk.END, f"\nTotal: {len(self.queued_files)} files")
    
    def _get_filename_parser(self) -> Optional[object]:
        """Get the filename parser from either connected module."""
        # First try direct connection to filename editor
        if self.filename_editor:
            return self.filename_editor.filename_parser
        # Fall back to file_mover's connection
        elif self.file_mover and hasattr(self.file_mover, 'filename_editor') and self.file_mover.filename_editor:
            return self.file_mover.filename_editor.filename_parser
        return None
    
    def _analyze_files(self):
        """Analyze queued files and fetch media information using background threads."""
        if not self.queued_files:
            messagebox.showinfo("Information", "No files in queue to analyze.")
            return
        
        if not self.api_key_var.get():
            messagebox.showerror("Error", "Please enter an API key first.")
            return
        
        # Get the parser - improved to check both direct and indirect connections
        filename_parser = self._get_filename_parser()
        if not filename_parser:
            messagebox.showerror("Error", "No filename parser available. Make sure the File Name Editor module is loaded.")
            return
    
        # Create a progress dialog
        progress_window = tk.Toplevel()
        progress_window.title("Analyzing Media Files")
        progress_window.geometry("400x150")
        progress_window.transient(self.queue_text.master.master)
        progress_window.grab_set()
    
        # Add progress bar and status label
        ttk.Label(progress_window, text="Fetching media information...").pack(pady=10)
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(
            progress_window, 
            variable=progress_var,
            maximum=len(self.queued_files),
            length=300
        )
        progress_bar.pack(pady=10)
    
        status_var = tk.StringVar(value="Preparing...")
        status_label = ttk.Label(progress_window, textvariable=status_var)
        status_label.pack(pady=5)
    
        # Update GUI to show initial progress
        progress_window.update()
    
        # Check if we should preprocess filenames first
        if self.config['pre_process_filenames'] and self.preprocess_var.get():
            status_var.set("Pre-processing filenames...")
            progress_window.update()
            self._preprocess_queued_filenames()
    
        # Create shared data containers
        results = []
        failed = []
        skipped = []
        
        def analyze_file(index, file_path):
            try:
                # Check if we already have this info cached
                cache_key = file_path.stem
                if cache_key in self.api_cache:
                    self.logger.info(f"Using cached data for {file_path.name}")
                    return {"status": "success", "file_path": file_path, "media_details": self.api_cache[cache_key]}
            
                # Parse filename
                media_info = filename_parser.parse_filename(file_path.stem)
            
                # Fetch media info from API
                title = media_info.title
                year = media_info.year
            
                # Skip if we don't have enough info
                if not title:
                    self.logger.warning(f"Could not parse title from {file_path.name}")
                    return {"status": "skipped", "file_path": file_path}
            
                # Fetch API data
                media_details = self._fetch_media_info(title, year, media_info.season is not None)
            
                if media_details:
                    # Cache the result
                    self.api_cache[cache_key] = media_details
                    return {"status": "success", "file_path": file_path, "media_details": media_details}
                else:
                    self.logger.warning(f"No API data found for {title} ({year if year else 'unknown year'})")
                    return {"status": "failed", "file_path": file_path}
        
            except Exception as e:
                self.logger.error(f"Error analyzing {file_path.name}: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
                return {"status": "failed", "file_path": file_path, "error": str(e)}

        # Define a callback for when file analysis is done
        def update_progress(index, result):
            nonlocal results, failed, skipped
        
            if result["status"] == "success":
                results.append((result["file_path"], result["media_details"]))
            elif result["status"] == "failed":
                failed.append(result["file_path"])
            elif result["status"] == "skipped":
                skipped.append(result["file_path"])
        
            # Update progress UI
            progress_var.set(index + 1)
            status_var.set(f"Processing: {index + 1}/{len(self.queued_files)}")
            progress_window.update()
        
            # Check if we're done
            if index + 1 >= len(self.queued_files):
                # All files processed, save cache and show results
                self._save_cache()
                progress_window.destroy()
                self._show_analysis_results(results, failed, skipped)
    
        # Start a separate thread for each file (with limit on concurrent tasks)
        import threading
        max_concurrent = 5  # Limit concurrent API requests
        active_threads = []
    
        for i, file_path in enumerate(self.queued_files):
            # Define a callback for this specific file
            callback = lambda idx=i, res=None: update_progress(idx, res)
        
            # Create a new thread for this file
            thread = threading.Thread(
                target=lambda idx=i, fp=file_path: callback(idx, analyze_file(idx, fp)),
                daemon=True
            )
        
            # Control concurrency
            if len(active_threads) >= max_concurrent:
                # Wait for at least one thread to finish
                active_threads[0].join()
                active_threads.pop(0)
        
            # Start the thread and add to active list
            thread.start()
            active_threads.append(thread)
        
            # Let the UI update before starting the next thread
            progress_window.update()
    
        # Create a monitoring thread to ensure completion
        def monitor_threads():
            # Wait for all threads to complete
            for thread in active_threads:
                thread.join()
        
            # If we haven't processed all files yet, make sure we finish
            if progress_var.get() < len(self.queued_files):
                progress_var.set(len(self.queued_files))
                self._save_cache()
                progress_window.destroy()
                self._show_analysis_results(results, failed, skipped)
    
        monitor_thread = threading.Thread(target=monitor_threads, daemon=True)
        monitor_thread.start()
    
    def _preprocess_specific_files(self, files, parent_window=None):
        """Preprocess only specific files for better parsing."""
        if not files:
            return
        
        if not self.filename_editor:
            messagebox.showerror("Error", "Filename Editor module is not available.")
            return
        
        # Filter the queued files to only include the specified files
        old_queue = self.queued_files.copy()
        self.queued_files = [f for f in self.queued_files if f in files]
        
        # Run the preprocessing
        self._preprocess_queued_filenames()
        
        # If we have a parent window, close it after preprocessing
        if parent_window:
            parent_window.destroy()
            
        # Re-analyze the files
        self._analyze_files()
        
    def _retry_failed_files(self, files, parent_window=None):
        """Retry analyzing failed files, possibly with manual input."""
        if not files:
            return
        
        # Close parent window if provided
        if parent_window:
            parent_window.destroy()
        
        # Create a dialog to let user correct titles
        correction_window = tk.Toplevel()
        correction_window.title("Manual Title Correction")
        correction_window.geometry("600x400")
        
        ttk.Label(
            correction_window,
            text="Correct titles for failed files:", 
            font=("", 11, "bold")
        ).pack(anchor='w', padx=10, pady=5)
        
        # Create a frame for the entries
        entries_frame = ttk.Frame(correction_window)
        entries_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create a canvas with scrollbar for many entries
        canvas = tk.Canvas(entries_frame)
        scrollbar = ttk.Scrollbar(entries_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Create input fields for each file
        title_vars = {}
        year_vars = {}
        type_vars = {}
        
        for file_path in files:
            # Get current title and year if available
            filename_parser = self._get_filename_parser()
            media_info = filename_parser.parse_filename(file_path.stem) if filename_parser else None
            
            file_frame = ttk.Frame(scrollable_frame)
            file_frame.pack(fill='x', pady=5)
            
            ttk.Label(file_frame, text=file_path.name, width=30).pack(side='left', padx=5)
            
            title_frame = ttk.Frame(file_frame)
            title_frame.pack(side='left', fill='x', expand=True)
            
            title_var = tk.StringVar(value=media_info.title if media_info else "")
            title_vars[str(file_path)] = title_var
            
            ttk.Label(title_frame, text="Title:").pack(side='left', padx=2)
            ttk.Entry(title_frame, textvariable=title_var, width=20).pack(side='left', padx=2, fill='x', expand=True)
            
            year_var = tk.StringVar(value=media_info.year if media_info and media_info.year else "")
            year_vars[str(file_path)] = year_var
            
            ttk.Label(title_frame, text="Year:").pack(side='left', padx=2)
            ttk.Entry(title_frame, textvariable=year_var, width=6).pack(side='left', padx=2)
            
            # Media type dropdown
            type_var = tk.StringVar(value="movie" if not media_info or not media_info.season else "tv")
            type_vars[str(file_path)] = type_var
            
            ttk.Label(title_frame, text="Type:").pack(side='left', padx=2)
            ttk.Combobox(
                title_frame, 
                textvariable=type_var,
                values=["movie", "tv"],
                width=6
            ).pack(side='left', padx=2)
        
        # Buttons for actions
        button_frame = ttk.Frame(correction_window)
        button_frame.pack(pady=10)
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=correction_window.destroy
        ).pack(side='right', padx=5)
        
        ttk.Button(
            button_frame,
            text="Analyze with Corrections",
            command=lambda: self._analyze_with_manual_corrections(
                files, title_vars, year_vars, type_vars, correction_window
            )
        ).pack(side='right', padx=5)
    
    def _analyze_with_manual_corrections(self, files, title_vars, year_vars, type_vars, window):
        """Analyze files using manually provided title, year, and type info."""
        window.destroy()
        
        # Create a progress dialog
        progress_window = tk.Toplevel()
        progress_window.title("Analyzing with Corrections")
        progress_window.geometry("400x150")
        
        ttk.Label(progress_window, text="Fetching media information...").pack(pady=10)
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(
            progress_window, 
            variable=progress_var,
            maximum=len(files),
            length=300
        )
        progress_bar.pack(pady=10)
        
        status_var = tk.StringVar(value="Preparing...")
        status_label = ttk.Label(progress_window, textvariable=status_var)
        status_label.pack(pady=5)
        
        progress_window.update()
        
        results = []
        failed = []
        
        for i, file_path in enumerate(files):
            # Update progress
            progress_var.set(i)
            status_var.set(f"Processing: {file_path.name}")
            progress_window.update()
            
            try:
                file_path_str = str(file_path)
                title = title_vars[file_path_str].get().strip()
                year = year_vars[file_path_str].get().strip()
                media_type = type_vars[file_path_str].get()
                
                if not title:
                    self.logger.warning(f"No title provided for {file_path.name}")
                    failed.append(file_path)
                    continue
                
                # Fetch API data with manual info
                media_details = self._fetch_media_info(
                    title, 
                    year if year else None,
                    media_type == "tv"
                )
                
                if media_details:
                    # Cache the result
                    self.api_cache[file_path.stem] = media_details
                    results.append((file_path, media_details))
                else:
                    self.logger.warning(f"No API data found for {title} ({year})")
                    failed.append(file_path)
            
            except Exception as e:
                self.logger.error(f"Error analyzing {file_path.name}: {str(e)}")
                failed.append(file_path)
        
        # Save updated cache
        self._save_cache()
        
        # Close progress window
        progress_window.destroy()
        
        # Re-run file analysis to show complete results
        self._analyze_files()
    
    def process_file(self, file_path: Path, dest_path: Path) -> bool:
        """Queue a file for processing with improved path handling."""
        try:
            # Ensure we're working with Path objects
            file_path = Path(file_path) if not isinstance(file_path, Path) else file_path
        
            # Check if file exists
            if not file_path.exists():
                self.logger.warning(f"File does not exist: {file_path}")
                return False
            
            # Check if this is a supported file type
            if file_path.suffix.lower() in self.get_supported_extensions():
                # Use resolved path for deduplication
                file_path_resolved = file_path.resolve()
            
                # Check if file is already in queue
                is_duplicate = False
                for queued_file in self.queued_files:
                    queued_resolved = Path(queued_file).resolve()
                    if queued_resolved == file_path_resolved:
                        is_duplicate = True
                        break
                    
                if not is_duplicate:
                    self.queued_files.append(file_path_resolved)
                    self._update_queue_display()
                
                return True
            return False
        
        except Exception as e:
            self.logger.error(f"Error queuing {file_path}: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _sort_files(self):
        """Sort files based on audience category, genre, and media type."""
        if not self.queued_files:
            messagebox.showinfo("Information", "No files in queue to sort.")
            return
    
        base_folder = self.base_folder_var.get()
        if not base_folder:
            messagebox.showerror("Error", "Please select a base folder for sorting.")
            return
    
        # Make sure the FileMover module is available
        if not self.file_mover:
            messagebox.showerror("Error", "FileMover module is not available.")
            return
    
        # Get sort options
        sort_by = self.sort_by_var.get()
        create_type_folders = self.create_type_var.get()
        create_genre_folders = self.create_genre_var.get()
        create_audience_folders = self.create_audience_var.get()
        tv_folder = self.tv_folder_var.get()
        movie_folder = self.movie_folder_var.get()
        simulation = self.simulate_var.get()
    
        # Create results window to show sorting plan
        results_window = tk.Toplevel(self.queue_text.master.master)
        results_window.title("Media Sorting Plan")
        results_window.geometry("700x500")
        results_window.transient(self.queue_text.master.master)
    
        # Results text area
        results_text = tk.Text(results_window, wrap=tk.WORD)
        results_text.pack(fill='both', expand=True, padx=10, pady=10)
    
        # Add scrollbar
        scrollbar = ttk.Scrollbar(results_text, command=results_text.yview)
        scrollbar.pack(side='right', fill='y')
        results_text.configure(yscrollcommand=scrollbar.set)
    
        # Display sort plan header
        results_text.insert(tk.END, "== Media Sorting Plan ==\n\n")
    
        if simulation:
            results_text.insert(tk.END, "⚠️ SIMULATION MODE - Files will not be moved ⚠️\n\n")
    
        results_text.insert(tk.END, f"Base folder: {base_folder}\n")
        results_text.insert(tk.END, f"Using audience categorization: {create_audience_folders}\n")
        results_text.insert(tk.END, f"Secondary sort by: {sort_by}\n")
        results_text.insert(tk.END, f"Create type folders: {create_type_folders}\n")
        results_text.insert(tk.END, f"Create genre folders: {create_genre_folders}\n\n")
    
        # Process each file
        sort_ops = []
        unknown_files = []
    
        for file_path in self.queued_files:
            # Check if we have cached info for this file
            cache_key = file_path.stem
            if cache_key in self.api_cache:
                media_details = self.api_cache[cache_key]
            
                # Determine audience category
                audience_category = media_details.get_audience_category()
                
                # Determine destination path based on sort options
                dest_path = Path(base_folder)
                
                # UPDATED SORTING LOGIC: Start with audience folders if enabled
                if create_audience_folders:
                    dest_path = dest_path / audience_category
                
                # Then arrange by type if enabled
                if create_type_folders:
                    if media_details.type == "tv":
                        dest_path = dest_path / tv_folder
                    elif media_details.type == "movie":
                        dest_path = dest_path / movie_folder
                    else:
                        dest_path = dest_path / self.config['unknown_folder']
                
                # Then sort by other criteria if enabled
                if sort_by == "genre" and create_genre_folders and media_details.genres:
                    # Add genre subfolder
                    primary_genre = media_details.genres[0]
                    dest_path = dest_path / primary_genre
                elif sort_by == "year" and media_details.year:
                    # Add year subfolder
                    dest_path = dest_path / media_details.year
                
                # Create the final path including the filename
                # Get the final filename based on whether renaming is enabled
                if self.file_mover.rename_enabled and self.file_mover.filename_editor:
                    parser = self.file_mover.filename_editor.filename_parser
                    media_info = parser.parse_filename(file_path.stem)
                    new_name = parser.generate_filename(media_info)
                    final_name = f"{new_name}{file_path.suffix}"
                else:
                    final_name = file_path.name
            
                final_dest = dest_path / final_name
            
                # Add to sort operations
                sort_ops.append((file_path, final_dest))
            
                # Show in results
                results_text.insert(tk.END, f"File: {file_path.name}\n")
                results_text.insert(tk.END, f"  Title: {media_details.title}\n")
                results_text.insert(tk.END, f"  Type: {media_details.type}\n")
                results_text.insert(tk.END, f"  Audience: {audience_category}\n")
                results_text.insert(tk.END, f"  Genres: {', '.join(media_details.genres)}\n")
                if media_details.content_rating:
                    results_text.insert(tk.END, f"  Rating: {media_details.content_rating}\n")
                results_text.insert(tk.END, f"  → {final_dest}\n\n")
        
            else:
                # No info for this file
                unknown_files.append(file_path)
                results_text.insert(tk.END, f"⚠️ No media info for: {file_path.name}\n")
    
        # Report summary
        results_text.insert(tk.END, f"\n== Summary ==\n")
        results_text.insert(tk.END, f"Files to sort: {len(sort_ops)}\n")
        results_text.insert(tk.END, f"Unknown files: {len(unknown_files)}\n")
    
        # Add buttons to execute or cancel
        button_frame = ttk.Frame(results_window)
        button_frame.pack(fill='x', padx=10, pady=10)
    
        # Add a button to execute the sorting operations
        ttk.Button(
            button_frame,
            text="Execute Sorting Plan" if not simulation else "Run Simulation",
            command=lambda: self._execute_sort_plan(sort_ops, simulation, results_window, results_text)
        ).pack(side='left', padx=5)
    
        ttk.Button(
            button_frame,
            text="Cancel",
            command=results_window.destroy
        ).pack(side='right', padx=5)
    
        # Add analyze unknown files button if needed
        if unknown_files:
            ttk.Button(
                button_frame,
                text="Analyze Unknown Files",
                command=lambda: self._retry_failed_files(unknown_files, results_window)
            ).pack(side='left', padx=5)

    def _execute_sort_plan(self, sort_ops, simulation, results_window, results_text):
        """Execute the sorting plan by copying/moving files to their destinations."""
        if not self.file_mover:
            messagebox.showerror("Error", "FileMover module is not available.")
            return
    
        # Create a progress dialog
        progress_window = tk.Toplevel()
        progress_window.title("Executing Sort Plan")
        progress_window.geometry("400x200")
        progress_window.transient(results_window)
        progress_window.grab_set()
    
        # Add progress indicators
        ttk.Label(progress_window, text="Processing files...").pack(pady=10)
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(
            progress_window, 
            variable=progress_var,
            maximum=len(sort_ops),
            length=300
        )
        progress_bar.pack(pady=10)
    
        current_file_var = tk.StringVar(value="Preparing...")
        ttk.Label(progress_window, textvariable=current_file_var).pack(pady=5)
    
        status_var = tk.StringVar(value="")
        status_label = ttk.Label(progress_window, textvariable=status_var)
        status_label.pack(pady=5)
    
        # Add a log text area
        log_frame = ttk.Frame(progress_window)
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)
    
        log_text = tk.Text(log_frame, height=5, wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(log_frame, command=log_text.yview)
        log_text.configure(yscrollcommand=log_scrollbar.set)
    
        log_text.pack(side='left', fill='both', expand=True)
        log_scrollbar.pack(side='right', fill='y')
    
        # Update the UI before starting
        progress_window.update()
    
        # Get file mover operation type (copy or move)
        operation_type = self.file_mover.operation_var.get() if hasattr(self.file_mover, 'operation_var') else "copy"
    
        # Function to add log message
        def add_log(message):
            log_text.insert(tk.END, f"{message}\n")
            log_text.see(tk.END)
            self.logger.info(message)
    
        # Process files
        success_count = 0
        failed_count = 0
    
        try:
            # Process each operation
            for i, (source_path, dest_path) in enumerate(sort_ops):
                try:
                    # Update progress
                    progress_var.set(i)
                    current_file_var.set(f"Processing: {source_path.name}")
                    status_var.set(f"File {i+1} of {len(sort_ops)}")
                    progress_window.update()
                
                    if simulation:
                        # In simulation mode, just log what would happen
                        log_msg = f"SIMULATION: Would {operation_type} '{source_path.name}' to '{dest_path}'"
                        add_log(log_msg)
                        success_count += 1
                        # Small delay to see progress in simulation
                        progress_window.after(100)
                    else:
                        # Ensure destination directory exists
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                    
                        # Execute the operation
                        if operation_type == "copy":
                            import shutil
                            # Check if destination exists
                            if dest_path.exists():
                                add_log(f"Warning: Destination file already exists: {dest_path}")
                                # Modify filename to avoid overwriting
                                stem = dest_path.stem
                                suffix = dest_path.suffix
                                counter = 1
                                while dest_path.exists():
                                    dest_path = dest_path.with_name(f"{stem} ({counter}){suffix}")
                                    counter += 1
                                add_log(f"Using alternative name: {dest_path.name}")
                        
                            # Copy the file
                            shutil.copy2(source_path, dest_path)
                            add_log(f"Copied: {source_path.name} -> {dest_path}")
                        else:  # move
                            # Check if destination exists
                            if dest_path.exists():
                                add_log(f"Warning: Destination file already exists: {dest_path}")
                                # Modify filename to avoid overwriting
                                stem = dest_path.stem
                                suffix = dest_path.suffix
                                counter = 1
                                while dest_path.exists():
                                    dest_path = dest_path.with_name(f"{stem} ({counter}){suffix}")
                                    counter += 1
                                add_log(f"Using alternative name: {dest_path.name}")
                        
                            # Move the file
                            import shutil
                            shutil.move(source_path, dest_path)
                            add_log(f"Moved: {source_path.name} -> {dest_path}")
                    
                        success_count += 1
            
                except Exception as e:
                    add_log(f"Error processing {source_path.name}: {str(e)}")
                    failed_count += 1
                    import traceback
                    self.logger.error(traceback.format_exc())
    
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during sorting: {str(e)}")
    
        finally:
            # Update progress to show completion
            progress_var.set(len(sort_ops))
            current_file_var.set("Completed")
            status_var.set(f"Success: {success_count}, Failed: {failed_count}")
        
            # Update the results window with completion message
            results_text.insert(tk.END, "\n== Execution Complete ==\n")
            results_text.insert(tk.END, f"Files processed: {success_count}\n")
            results_text.insert(tk.END, f"Failed: {failed_count}\n")
            if simulation:
                results_text.insert(tk.END, "NOTE: This was a simulation. No files were actually moved.\n")
        
            # Add a close button to the progress window
            ttk.Button(
                progress_window,
                text="Close",
                command=progress_window.destroy
            ).pack(pady=10)
        
            # If this was a real operation (not simulation) and it moved files, clear the queue
            if not simulation and operation_type == "move" and success_count > 0:
                # Only remove successfully processed files
                processed_files = set(op[0] for op in sort_ops[:success_count])
                self.queued_files = [f for f in self.queued_files if f not in processed_files]
                self._update_queue_display()

    def _fetch_media_info(self, title: str, year: Optional[str], is_tv: bool) -> Optional[MediaDetails]:
        """Fetch media information from the selected API."""
        api_type = self.api_type_var.get()
        api_key = self.api_key_var.get()

        # Check if we've reached the daily limit for the chosen API
        if self.api_tracker.is_limit_reached(api_type):
            # Switch to alternate API if primary is at limit
            alternate_api = "tmdb" if api_type == "omdb" else "omdb"
            if not self.api_tracker.is_limit_reached(alternate_api):
                self.logger.warning(f"{api_type.upper()} daily limit reached, switching to {alternate_api.upper()}")
                api_type = alternate_api
                api_key = self.TMDB_API_KEY if api_type == "tmdb" else self.OMDB_API_KEY
            else:
                self.logger.error("Daily limits reached for both APIs")
                return None

        if api_type == "tmdb":
            # The Movie Database API
            search_type = "tv" if is_tv else "movie"
            
            try:
                # Record API call attempt
                self.api_tracker.record_api_call("tmdb", success=False)  # Will update to success if it works
            
                # Search for the media
                search_params = {
                    "api_key": api_key,
                    "query": title
                }
                if year:
                    if is_tv:
                        search_params["first_air_date_year"] = year
                    else:
                        search_params["year"] = year
                
                response = requests.get(
                    f"https://api.themoviedb.org/3/search/{search_type}",
                    params=search_params
                )
                search_data = response.json()
                
                if not response.ok or not search_data.get("results"):
                    # If TV search fails, try movie search and vice versa
                    if is_tv:
                        search_type = "movie"
                    else:
                        search_type = "tv"
                    
                    response = requests.get(
                        f"https://api.themoviedb.org/3/search/{search_type}",
                        params=search_params
                    )
                    search_data = response.json()
                
                if response.ok and search_data.get("results"):
                    # Get the first result
                    result = search_data["results"][0]
                    
                    # Get detailed info including genres
                    details_response = requests.get(
                        f"https://api.themoviedb.org/3/{search_type}/{result['id']}",
                        params={"api_key": api_key, "append_to_response": "release_dates,content_ratings"}
                    )
                    
                    if details_response.ok:
                        self.api_tracker.record_api_call("tmdb", success=True)
                        details = details_response.json()
                        
                        # Extract information
                        title = details.get("title") or details.get("name", "Unknown")
                        year_str = None
                        if search_type == "movie" and details.get("release_date"):
                            year_str = details["release_date"].split("-")[0]
                        elif search_type == "tv" and details.get("first_air_date"):
                            year_str = details["first_air_date"].split("-")[0]
                        
                        # Get genres
                        genres = [genre["name"] for genre in details.get("genres", [])]
                        
                        # Try to get content rating
                        content_rating = None
                        
                        # For movies, check release_dates
                        if search_type == "movie" and "release_dates" in details:
                            # Look for US rating first
                            for country in details["release_dates"].get("results", []):
                                if country.get("iso_3166_1") == "US":
                                    for release in country.get("release_dates", []):
                                        if release.get("certification"):
                                            content_rating = release["certification"]
                                            break
                                    if content_rating:
                                        break
                        
                        # For TV shows, check content_ratings
                        elif search_type == "tv" and "content_ratings" in details:
                            # Look for US rating first
                            for rating in details["content_ratings"].get("results", []):
                                if rating.get("iso_3166_1") == "US":
                                    content_rating = rating.get("rating")
                                    break
                        
                        return MediaDetails(
                            title=title,
                            year=year_str,
                            genres=genres,
                            type="tv" if search_type == "tv" else "movie",
                            content_rating=content_rating
                        )
            
            except Exception as e:
                self.logger.error(f"Error fetching TMDb info for {title}: {str(e)}")
                return None
        
        elif api_type == "omdb":
            # OMDb API (Open Movie Database)
            try:
                # Record API call attempt
                self.api_tracker.record_api_call("omdb", success=False)  # Will update to success if it works
            
                # Prepare search parameters
                search_params = {
                    "t": title,
                    "apikey": api_key                    
                }
                
                if year:
                    search_params["y"] = year
                
                if is_tv:
                    search_params["type"] = "series"
                else:
                    search_params["type"] = "movie"
                
                # Make API request with formatted URL
                url = f"http://www.omdbapi.com/?t={title}&apikey={api_key}"
                if year:
                    url += f"&y={year}"
                if is_tv:
                    url += "&type=series"
                else:
                    url += "&type=movie"
    
                response = requests.get(url)
                
                if response.ok:
                    data = response.json()
                    
                    if data.get("Response") == "True":
                        # If successful, update API call status
                        self.api_tracker.record_api_call("omdb", success=True)

                        # If we find a result, extract the info
                        title = data.get("Title", "Unknown")
                        year_str = data.get("Year", "").split("–")[0]  # Handle TV show ranges like "2005–2013"
                        
                        # Parse genres
                        genres = [genre.strip() for genre in data.get("Genre", "").split(",")]
                        
                        # Get content rating
                        content_rating = data.get("Rated", None)
                        
                        # Determine type
                        media_type = "tv" if data.get("Type") == "series" else "movie"
                        
                        return MediaDetails(
                            title=title,
                            year=year_str,
                            genres=genres,
                            type=media_type,
                            content_rating=content_rating
                        )
                    
                    # If search with specified type fails, try without type
                    elif "type" in search_params:
                        # Remove type and try again
                        search_params.pop("type")
                        response = requests.get(
                            "http://www.omdbapi.com/",
                            params=search_params
                        )
                        
                        if response.ok:
                            data = response.json()
                            
                            if data.get("Response") == "True":

                                # Extract info
                                title = data.get("Title", "Unknown")
                                year_str = data.get("Year", "").split("–")[0]
                                genres = [genre.strip() for genre in data.get("Genre", "").split(",")]
                                media_type = "tv" if data.get("Type") == "series" else "movie"
                                content_rating = data.get("Rated", None)
                                
                                return MediaDetails(
                                    title=title,
                                    year=year_str,
                                    genres=genres,
                                    type=media_type,
                                    content_rating=content_rating
                                )
            
            except Exception as e:
                self.logger.error(f"Error fetching OMDb info for {title}: {str(e)}")
                return None
        
        return None

    def save_settings(self) -> Dict[str, Any]:
        """Save current settings to dictionary."""
        if hasattr(self, 'api_key_var') and self.api_key_var is not None:
            return {
                'api_key': self.api_key_var.get(),
                'api_type': self.api_type_var.get(),
                'base_folder': self.base_folder_var.get(),
                'sort_by': self.sort_by_var.get(),
                'tv_folder': self.tv_folder_var.get(),
                'movie_folder': self.movie_folder_var.get(),
                'unknown_folder': self.config['unknown_folder'],
                'create_genre_folders': self.create_genre_var.get(),
                'create_type_folders': self.create_type_var.get(),
                'simulate': self.simulate_var.get()
            }
        return self.config.copy()

    def load_settings(self, settings: Dict[str, Any]) -> None:
        """Load settings from dictionary."""
        self.config.update(settings)
    
        if hasattr(self, 'api_key_var') and self.api_key_var is not None:
            self.api_key_var.set(self.config.get('api_key', self._get_default_api_key()))
            self.api_type_var.set(self.config.get('api_type', 'tmdb'))
            self.base_folder_var.set(self.config.get('base_folder', ''))
            self.sort_by_var.set(self.config.get('sort_by', 'genre'))
            self.tv_folder_var.set(self.config.get('tv_folder', 'TV Shows'))
            self.movie_folder_var.set(self.config.get('movie_folder', 'Movies'))
            self.create_genre_var.set(self.config.get('create_genre_folders', True))
            self.create_type_var.set(self.config.get('create_type_folders', True))
            self.simulate_var.set(self.config.get('simulate', True))