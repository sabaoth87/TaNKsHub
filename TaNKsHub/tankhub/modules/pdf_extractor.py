
import os
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import List, Dict, Any, Optional
import threading
import queue
import PyPDF2
from io import StringIO
import re
from tankhub.core.base_module import BaseModule

logger = logging.getLogger(__name__)

class PDFExtractorModule(BaseModule):
    """Module for extracting and simplifying text from PDF files."""
    
    def __init__(self):
        super().__init__("PDF Extractor", "Extract text from PDFs with formatting options")
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing PDFExtractorModule")
        
        # Queue for PDF files
        self.queued_files: List[Path] = []
        
        # Output settings
        self.config = {
            'output_directory': '',
            'preserve_paragraphs': True,
            'remove_headers_footers': True,
            'simplify_formatting': True,
            'extract_metadata': True,
            'merge_hyphenated_words': True,
            'page_separators': False,
            # New AI-specific options
            'ai_friendly_format': False,  # New option for AI-friendly formatting
            'ai_chunk_size': 2000,        # Approximate characters per chunk for AI processing
            'ai_add_headings': True,      # Add heading markers for better context
            'ai_enhance_structure': True  # Improve document structure for AI understanding
        }
        
        # Output content
        self.extracted_text = {}  # filename -> text content
        
        # Progress tracking
        self.processing = False
        self.current_thread = None
        self.operation_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        self.message_queue = queue.Queue()
        
        # Keep references to UI elements that need updating
        self.queue_text = None
        self.progress_var = None
        self.status_var = None
        self.output_preview = None
        self.cancel_btn = None
        
    def get_supported_extensions(self) -> List[str]:
        """Define which file types this module can handle."""
        return ['.pdf']

    def process_file(self, file_path: Path, dest_path: Path) -> bool:
        """Queue a PDF file for processing."""
        try:
            # Ensure we're working with Path objects
            file_path = Path(file_path) if not isinstance(file_path, Path) else file_path
            
            # Check if file exists and is supported
            if not file_path.exists():
                self.logger.warning(f"File does not exist: {file_path}")
                return False
                
            if file_path.suffix.lower() not in self.get_supported_extensions():
                self.logger.warning(f"Unsupported file type: {file_path.suffix}")
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
            self._update_queue_display()
            return True
            
        except Exception as e:
            self.logger.error(f"Error queuing {file_path}: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def get_settings_widget(self, parent) -> ttk.Frame:
        """Create and return the settings widget."""
        try:
            self.logger.info("Creating settings widget")
            
            # Create main frame
            frame = ttk.Frame(parent)
            
            # Queue display section
            queue_frame = ttk.LabelFrame(frame, text="PDF Queue", padding=5)
            queue_frame.pack(fill='both', expand=True, padx=5, pady=5)
            
            # Create text widget with scrollbar
            queue_container = ttk.Frame(queue_frame)
            queue_container.pack(fill='both', expand=True, padx=5, pady=5)
            
            self.queue_text = tk.Text(queue_container, height=4, wrap=tk.WORD)
            scrollbar = ttk.Scrollbar(queue_container, command=self.queue_text.yview)
            self.queue_text.configure(yscrollcommand=scrollbar.set)
            
            self.queue_text.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            # Queue buttons
            queue_buttons = ttk.Frame(queue_frame)
            queue_buttons.pack(fill='x', padx=5, pady=5)
            
            ttk.Button(
                queue_buttons,
                text="Add PDFs",
                command=self._add_files
            ).pack(side='left', padx=5)
            
            ttk.Button(
                queue_buttons,
                text="Clear Queue",
                command=self._clear_queue
            ).pack(side='left', padx=5)
            
            # Output directory section
            output_frame = ttk.LabelFrame(frame, text="Output Settings", padding=5)
            output_frame.pack(fill='x', padx=5, pady=5)
            
            # Output directory selection
            dir_frame = ttk.Frame(output_frame)
            dir_frame.pack(fill='x', padx=5, pady=5)
            
            ttk.Label(dir_frame, text="Output Directory:").pack(side='left')
            
            self.output_dir = tk.StringVar(value=self.config.get('output_directory', ''))
            ttk.Entry(dir_frame, textvariable=self.output_dir).pack(side='left', fill='x', expand=True, padx=5)
            
            ttk.Button(
                dir_frame,
                text="Browse",
                command=self._browse_output_dir
            ).pack(side='right')
            
            # Text processing options
            options_frame = ttk.LabelFrame(output_frame, text="Text Processing Options", padding=5)
            options_frame.pack(fill='x', padx=5, pady=5)
            
            # Create checkboxes for options
            self.preserve_paragraphs_var = tk.BooleanVar(value=self.config.get('preserve_paragraphs', True))
            ttk.Checkbutton(
                options_frame,
                text="Preserve paragraphs",
                variable=self.preserve_paragraphs_var
            ).pack(anchor='w', padx=5, pady=2)
            
            self.remove_headers_footers_var = tk.BooleanVar(value=self.config.get('remove_headers_footers', True))
            ttk.Checkbutton(
                options_frame,
                text="Remove headers and footers",
                variable=self.remove_headers_footers_var
            ).pack(anchor='w', padx=5, pady=2)
            
            self.simplify_formatting_var = tk.BooleanVar(value=self.config.get('simplify_formatting', True))
            ttk.Checkbutton(
                options_frame,
                text="Simplify formatting (remove extra spaces, normalize line breaks)",
                variable=self.simplify_formatting_var
            ).pack(anchor='w', padx=5, pady=2)
            
            self.extract_metadata_var = tk.BooleanVar(value=self.config.get('extract_metadata', True))
            ttk.Checkbutton(
                options_frame,
                text="Extract metadata (title, author) if available",
                variable=self.extract_metadata_var
            ).pack(anchor='w', padx=5, pady=2)
            
            self.merge_hyphenated_words_var = tk.BooleanVar(value=self.config.get('merge_hyphenated_words', True))
            ttk.Checkbutton(
                options_frame,
                text="Merge hyphenated words at line breaks",
                variable=self.merge_hyphenated_words_var
            ).pack(anchor='w', padx=5, pady=2)
            
            self.page_separators_var = tk.BooleanVar(value=self.config.get('page_separators', False))
            ttk.Checkbutton(
                options_frame,
                text="Add page separator markers",
                variable=self.page_separators_var
            ).pack(anchor='w', padx=5, pady=2)
            
            # AI-friendly formatting options (new section)
            ai_frame = ttk.LabelFrame(options_frame, text="AI-Friendly Formatting", padding=5)
            ai_frame.pack(fill='x', padx=5, pady=5)

            self.ai_friendly_var = tk.BooleanVar(value=self.config.get('ai_friendly_format', False))
            ai_friendly_check = ttk.Checkbutton(
                ai_frame,
                text="Optimize text for AI interpretation",
                variable=self.ai_friendly_var,
                command=self._toggle_ai_options
            )
            ai_friendly_check.pack(anchor='w', padx=5, pady=2)

            # Sub-options for AI formatting
            self.ai_options_frame = ttk.Frame(ai_frame)
            self.ai_options_frame.pack(fill='x', padx=20, pady=2)

            self.ai_add_headings_var = tk.BooleanVar(value=self.config.get('ai_add_headings', True))
            ttk.Checkbutton(
                self.ai_options_frame,
                text="Add semantic heading markers",
                variable=self.ai_add_headings_var
            ).pack(anchor='w', pady=2)

            self.ai_enhance_structure_var = tk.BooleanVar(value=self.config.get('ai_enhance_structure', True))
            ttk.Checkbutton(
                self.ai_options_frame,
                text="Enhance document structure",
                variable=self.ai_enhance_structure_var
            ).pack(anchor='w', pady=2)

            # Chunk size for AI processing
            chunk_frame = ttk.Frame(self.ai_options_frame)
            chunk_frame.pack(fill='x', pady=2)

            ttk.Label(chunk_frame, text="AI chunk size:").pack(side='left')

            self.ai_chunk_size_var = tk.StringVar(value=str(self.config.get('ai_chunk_size', 2000)))
            chunk_sizes = ["1000", "2000", "4000", "8000", "16000", "No chunking"]
            chunk_combo = ttk.Combobox(
                chunk_frame,
                textvariable=self.ai_chunk_size_var,
                values=chunk_sizes,
                width=15
            )
            chunk_combo.pack(side='left', padx=5)

            # Initially disable AI options if not checked
            if not self.ai_friendly_var.get():
                self.ai_options_frame.pack_forget()

            # Progress section
            progress_frame = ttk.LabelFrame(frame, text="Progress", padding=5)
            progress_frame.pack(fill='x', padx=5, pady=5)
            
            self.progress_var = tk.DoubleVar()
            self.progress_bar = ttk.Progressbar(
                progress_frame,
                orient="horizontal",
                mode="determinate",
                variable=self.progress_var
            )
            self.progress_bar.pack(fill='x', padx=5, pady=5)
            
            self.status_var = tk.StringVar(value="Ready")
            ttk.Label(
                progress_frame,
                textvariable=self.status_var
            ).pack(fill='x', padx=5)
            
            # Create a status indicator for the current operation
            status_frame = ttk.Frame(progress_frame)
            status_frame.pack(fill='x', padx=5, pady=2)

            ttk.Label(status_frame, text="Status:").pack(side='left')
            self.status_var = tk.StringVar(value="Ready")
            ttk.Label(status_frame, textvariable=self.status_var).pack(side='left', padx=5)

            # Add a page counter for current processing
            self.page_counter_var = tk.StringVar(value="")
            ttk.Label(status_frame, textvariable=self.page_counter_var).pack(side='right')

            # Cancel button
            self.cancel_btn = ttk.Button(
                progress_frame,
                text="Cancel Operation",
                command=self.cancel_operation,
                state="disabled"
            )
            self.cancel_btn.pack(pady=5)
            
            # Extract and preview buttons
            button_frame = ttk.Frame(frame)
            button_frame.pack(fill='x', padx=5, pady=10)
            
            ttk.Button(
                button_frame,
                text="Extract Text",
                command=self._extract_text
            ).pack(side='left', padx=5)
            
            ttk.Button(
                button_frame,
                text="Save Extracted Text",
                command=self._save_extracted_text
            ).pack(side='left', padx=5)
            
            ttk.Button(
                button_frame,
                text="Preview Output",
                command=self._preview_output
            ).pack(side='right', padx=5)
            
            self._update_queue_display()
            
            return frame
            
        except Exception as e:
            self.logger.error(f"Error creating settings widget: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            
            # Return a basic frame with error message
            error_frame = ttk.Frame(parent)
            ttk.Label(
                error_frame,
                text=f"Error creating PDF Extractor UI: {str(e)}",
                foreground="red"
            ).pack(padx=20, pady=20)
            
            return error_frame
    
    def _add_files(self):
        """Add PDF files via dialog."""
        try:
            file_paths = filedialog.askopenfilenames(
                title="Select PDF Files",
                filetypes=[("PDF Files", "*.pdf")]
            )
            
            if file_paths:
                for path in file_paths:
                    self.process_file(Path(path), None)
                
        except Exception as e:
            self.logger.error(f"Error adding files: {str(e)}")
            messagebox.showerror("Error", f"Failed to add files: {str(e)}")
    
    def _clear_queue(self):
        """Clear the file queue."""
        self.queued_files.clear()
        self._update_queue_display()
        self.status_var.set("Queue cleared")
    
    def _browse_output_dir(self):
        """Browse for output directory."""
        try:
            directory = filedialog.askdirectory()
            if directory:
                self.output_dir.set(directory)
                self.config['output_directory'] = directory
        except Exception as e:
            self.logger.error(f"Error selecting directory: {str(e)}")
    
    def _update_queue_display(self):
        """Update the queue display with current files."""
        if not hasattr(self, 'queue_text') or not self.queue_text:
            return
            
        self.queue_text.delete('1.0', tk.END)
        
        if not self.queued_files:
            self.queue_text.insert(tk.END, "No PDF files in queue. Click 'Add PDFs' or drag PDFs here.")
            return
            
        for file_path in self.queued_files:
            self.queue_text.insert(tk.END, f"{file_path.name}\n")
            
        self.queue_text.insert(tk.END, f"\nTotal: {len(self.queued_files)} PDF files")
    
    def _extract_text(self):
        """Extract text from queued PDF files."""
        if not self.queued_files:
            messagebox.showinfo("Information", "No PDF files in queue to process.")
            return
        
        # Update configuration from UI
        self.config['preserve_paragraphs'] = self.preserve_paragraphs_var.get()
        self.config['remove_headers_footers'] = self.remove_headers_footers_var.get()
        self.config['simplify_formatting'] = self.simplify_formatting_var.get()
        self.config['extract_metadata'] = self.extract_metadata_var.get()
        self.config['merge_hyphenated_words'] = self.merge_hyphenated_words_var.get()
        self.config['page_separators'] = self.page_separators_var.get()
        
        # Update AI formatting options
        self.config['ai_friendly_format'] = self.ai_friendly_var.get()
        self.config['ai_add_headings'] = self.ai_add_headings_var.get()
        self.config['ai_enhance_structure'] = self.ai_enhance_structure_var.get()

        # Handle chunk size (convert to int or keep "No chunking")
        chunk_size = self.ai_chunk_size_var.get()
        if chunk_size != "No chunking":
            try:
                self.config['ai_chunk_size'] = int(chunk_size)
            except ValueError:
                self.config['ai_chunk_size'] = 2000
        else:
            self.config['ai_chunk_size'] = "No chunking"

        # Prepare operation queue
        self.operation_queue = queue.Queue()
        for file_path in self.queued_files:
            self.operation_queue.put(file_path)
        
        # Start processing
        self.processing = True
        self.total_operations = len(self.queued_files)
        self.cancel_btn.configure(state="normal")
        
        # Update UI to show we're starting
        self.progress_queue.put((0, f"Starting extraction of {self.total_operations} files..."))
    

        # Start processing in a background thread
        self.current_thread = self.run_in_thread(
            self._process_pdfs,
            lambda _: self.logger.debug("PDF extraction complete")
        )

        # Disable controls during processing
        def disable_controls():
            # Disable buttons and settings that shouldn't be changed during processing
            for widget in [self.add_button, self.clear_button, self.extract_button, 
                          self.save_button, self.preview_button]:
                if hasattr(self, widget):
                    widget.configure(state="disabled")

        def enable_controls():
            # Re-enable controls after processing is complete
            for widget in [self.add_button, self.clear_button, self.extract_button, 
                          self.save_button, self.preview_button]:
                if hasattr(self, widget):
                    widget.configure(state="normal")

        # Disable controls at the start
        if hasattr(self, 'app') and hasattr(self.app, 'root'):
            self.app.root.after(0, disable_controls)

        # In the _on_extraction_complete method:
        if hasattr(self, 'app') and hasattr(self.app, 'root'):
            self.app.root.after(0, enable_controls)
    
    def _on_extraction_complete(self):
        """Handle completion of the extraction process."""
        self.logger.debug("PDF extraction complete")
        self.progress_queue.put((100, "Extraction complete"))
        # Re-enable any UI elements that might have been disabled
        self.cancel_btn.configure(state="disabled")
    
        # Show a notification to the user
        if hasattr(self, 'app') and hasattr(self.app, 'root'):
            # Use the application's root window for the messagebox
            self.app.root.after(0, lambda: messagebox.showinfo(
                "Extraction Complete", 
                f"Successfully processed {self.total_operations} files."
            ))

    def _process_pdfs(self):
        """Background thread to process PDF files."""
        self.extracted_text = {}  # Clear previous results
    
        total_files = self.total_operations
        processed_files = 0
    
        while self.processing and not self.operation_queue.empty():
            try:
                file_path = self.operation_queue.get_nowait()
            
                # Update progress info for starting this file
                processed_files += 1
                overall_progress = ((processed_files - 1) / total_files) * 100
                self.progress_queue.put(
                    (overall_progress, f"Processing file {processed_files}/{total_files}: {file_path.name}")
                )
            
                self.logger.info(f"Processing PDF: {file_path}")
                self.message_queue.put(f"Processing: {file_path.name}")
            
                # Extract text from the PDF with progress updates
                extracted_text = self._extract_text_from_pdf_with_progress(file_path, processed_files, total_files)
            
                # Store the result
                self.extracted_text[str(file_path)] = extracted_text
            
                self.message_queue.put(f"Completed: {file_path.name}")
            
            except Exception as e:
                self.logger.error(f"Error processing {file_path.name}: {str(e)}")
                self.message_queue.put(f"Error processing {file_path.name}: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
    
        # Processing complete
        self.processing = False
        self.progress_queue.put((100, "Text extraction complete"))
        if self.cancel_btn:
            self.cancel_btn.configure(state="disabled")

    def _extract_text_from_pdf_with_progress(self, pdf_path: Path, file_num: int, total_files: int) -> str:
        """Extract text from PDF with progress updates for the current file."""
        try:
            # Read PDF
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                total_pages = len(reader.pages)
            
                if total_pages > 100:  # Threshold for large PDFs
                    # Process in batches of pages to reduce memory usage
                    batch_size = 20  # Adjust based on expected page size
                    for batch_start in range(0, total_pages, batch_size):
                        batch_end = min(batch_start + batch_size, total_pages)
                        # Process batch
                        # Save intermediate results
                        # Force garbage collection
                        import gc
                        gc.collect()

                # Calculate base progress percentage for this file within overall progress
                # Each file gets an equal portion of the progress bar
                file_progress_base = ((file_num - 1) / total_files) * 100
                file_progress_range = (1 / total_files) * 100
                
                # Get approximate file size proportion for better progress calculation
                total_size = sum(path.stat().st_size for path in self.queued_files)
                file_weight = pdf_path.stat().st_size / total_size
                file_progress_range = file_weight * 100

                # Get metadata if requested (same as before)
                metadata = {}
                if self.config['extract_metadata']:
                    info = reader.metadata
                    if info:
                        # Extract available metadata fields
                        for key in ['/Title', '/Author', '/Subject', '/Keywords', '/Producer', '/Creator']:
                            if key in info:
                                metadata[key.strip('/')] = info[key]
            
                # Process all pages with progress updates
                text_parts = []
            
                # Add metadata at the top if available (same as before)
                if metadata:
                    meta_text = "--- Document Metadata ---\n"
                    for key, value in metadata.items():
                        if value:
                            meta_text += f"{key}: {value}\n"
                    meta_text += "------------------------\n\n"
                    text_parts.append(meta_text)
            
                # Process each page with progress updates
                for i, page in enumerate(reader.pages):
                    # Update progress for this page
                    page_progress = (i / total_pages) * file_progress_range
                    overall_progress = file_progress_base + page_progress
                
                    # Update UI with current page progress
                    self.progress_queue.put(
                        (overall_progress, f"File {file_num}/{total_files}: {pdf_path.name} - Page {i+1}/{total_pages}")
                    )
                
                    # Process the page (extract and format text)
                    page_text = page.extract_text()
                
                    # Skip empty pages
                    if not page_text or page_text.isspace():
                        continue
                
                    # Apply text processing based on settings
                    processed_text = self._process_text(page_text, i+1)
                
                    # Add page separator if requested
                    if self.config['page_separators']:
                        text_parts.append(f"\n----- Page {i+1} -----\n\n{processed_text}\n")
                    else:
                        text_parts.append(processed_text)
                
                    # Small delay to allow for UI updates
                    # This helps keep the UI responsive during processing
                    if hasattr(self, 'app') and hasattr(self.app, 'root'):
                        self.app.root.update_idletasks()
            
                # Combine and post-process text (same as before)
                full_text = "\n".join(text_parts)
            
                # Final post-processing
                if self.config['simplify_formatting']:
                    # Remove excessive whitespace
                    full_text = re.sub(r'\n{3,}', '\n\n', full_text)
                    full_text = re.sub(r' {2,}', ' ', full_text)  
                    
                if self.config['merge_hyphenated_words']:
                    full_text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', full_text)
            
                # Apply AI-friendly formatting if enabled
                if self.config['ai_friendly_format']:
                    full_text = self._apply_ai_formatting(full_text, pdf_path.name)
            
                return full_text
            
        except Exception as e:
            self.logger.error(f"Error extracting text from {pdf_path}: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return f"Error extracting text: {str(e)}"
    
    def _extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text content from a PDF file with specified processing options."""
        try:
            # Read PDF
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                # Get metadata if requested
                metadata = {}
                if self.config['extract_metadata']:
                    info = reader.metadata
                    if info:
                        # Extract available metadata fields
                        for key in ['/Title', '/Author', '/Subject', '/Keywords', '/Producer', '/Creator']:
                            if key in info:
                                metadata[key.strip('/')] = info[key]
                
                # Process all pages
                text_parts = []
                
                # Add metadata at the top if available
                if metadata:
                    meta_text = "--- Document Metadata ---\n"
                    for key, value in metadata.items():
                        if value:
                            meta_text += f"{key}: {value}\n"
                    meta_text += "------------------------\n\n"
                    text_parts.append(meta_text)
                
                # Process each page
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    
                    # Skip empty pages
                    if not page_text or page_text.isspace():
                        continue
                    
                    # Apply text processing based on settings
                    processed_text = self._process_text(page_text, i+1)
                    
                    # Add page separator if requested
                    if self.config['page_separators']:
                        text_parts.append(f"\n----- Page {i+1} -----\n\n{processed_text}\n")
                    else:
                        text_parts.append(processed_text)
                
                # Combine all text parts
                full_text = "\n".join(text_parts)
                
                # Final post-processing
                if self.config['simplify_formatting']:
                    # Remove excessive whitespace
                    full_text = re.sub(r'\n{3,}', '\n\n', full_text)
                    full_text = re.sub(r' {2,}', ' ', full_text)
                
                # Merge hyphenated words if requested
                if self.config['merge_hyphenated_words']:
                    full_text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', full_text)
                
                # Apply AI-friendly formatting if enabled
                if self.config['ai_friendly_format']:
                    full_text = self._apply_ai_formatting(full_text, pdf_path.name)

                return full_text
                
        except Exception as e:
            self.logger.error(f"Error extracting text from {pdf_path}: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return f"Error extracting text: {str(e)}"
    
    def _process_text(self, text: str, page_num: int) -> str:
        """Process extracted text according to configuration settings."""
        if not text:
            return ""
        
        # Remove headers and footers if requested
        if self.config['remove_headers_footers']:
            # Simple heuristic: remove first and last line if they seem like headers/footers
            lines = text.splitlines()
            if len(lines) > 2:
                # Check if first line is a header (short, contains page number, etc.)
                if len(lines[0]) < 100 and (str(page_num) in lines[0] or re.search(r'^\s*\d+\s*$', lines[0])):
                    lines = lines[1:]
                
                # Check if last line is a footer
                if len(lines[-1]) < 100 and (str(page_num) in lines[-1] or re.search(r'^\s*\d+\s*$', lines[-1])):
                    lines = lines[:-1]
                
                text = '\n'.join(lines)
        
        # Simplify formatting if requested
        if self.config['simplify_formatting']:
            # Replace multiple spaces with single space
            text = re.sub(r' {2,}', ' ', text)
            
            # Normalize line breaks and paragraph marks
            if self.config['preserve_paragraphs']:
                # First, convert single line breaks that aren't paragraph breaks to spaces
                text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
                
                # Then ensure paragraph breaks are just double line breaks
                text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text
    
    def _preview_output(self):
        """Show a preview of the extracted text."""
        if not self.extracted_text:
            messagebox.showinfo("Information", "No text has been extracted yet. Please extract text first.")
            return
        
        # Create a preview window
        preview_window = tk.Toplevel()
        preview_window.title("Extracted Text Preview")
        preview_window.geometry("700x500")
        
        # Add a combobox to select which file to preview
        select_frame = ttk.Frame(preview_window, padding=5)
        select_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(select_frame, text="Select file:").pack(side='left', padx=5)
        
        file_paths = list(self.extracted_text.keys())
        file_names = [Path(path).name for path in file_paths]
        
        selected_file = tk.StringVar()
        if file_names:
            selected_file.set(file_names[0])
        
        file_combo = ttk.Combobox(
            select_frame, 
            textvariable=selected_file,
            values=file_names,
            width=50
        )
        file_combo.pack(side='left', fill='x', expand=True, padx=5)
        
        # Create a text widget with scrollbars
        text_frame = ttk.Frame(preview_window, padding=5)
        text_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.output_preview = tk.Text(text_frame, wrap=tk.WORD)
        
        # Add vertical scrollbar
        v_scrollbar = ttk.Scrollbar(text_frame, command=self.output_preview.yview)
        self.output_preview.configure(yscrollcommand=v_scrollbar.set)
        
        # Add horizontal scrollbar
        h_scrollbar = ttk.Scrollbar(text_frame, orient='horizontal', command=self.output_preview.xview)
        self.output_preview.configure(xscrollcommand=h_scrollbar.set)
        
        # Pack scrollbars and text widget
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')
        self.output_preview.pack(side='left', fill='both', expand=True)
        
        # Button frame for actions
        button_frame = ttk.Frame(preview_window, padding=5)
        button_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(
            button_frame,
            text="Copy to Clipboard",
            command=lambda: self._copy_to_clipboard(preview_window)
        ).pack(side='left', padx=5)
        
        ttk.Button(
            button_frame,
            text="Save Selected File",
            command=lambda: self._save_single_file(selected_file.get())
        ).pack(side='left', padx=5)
        
        ttk.Button(
            button_frame,
            text="Close",
            command=preview_window.destroy
        ).pack(side='right', padx=5)
        
        # Function to update preview when selection changes
        def update_preview(*args):
            self.output_preview.delete('1.0', tk.END)
            selected_name = selected_file.get()
            if selected_name:
                selected_path = None
                for path, name in zip(file_paths, file_names):
                    if name == selected_name:
                        selected_path = path
                        break
                
                if selected_path and selected_path in self.extracted_text:
                    self.output_preview.insert(tk.END, self.extracted_text[selected_path])
        
        # Bind selection change event
        file_combo.bind("<<ComboboxSelected>>", update_preview)
        
        # Initialize with first file
        update_preview()
    
    def _copy_to_clipboard(self, parent_window):
        """Copy the current preview text to clipboard."""
        if hasattr(self, 'output_preview') and self.output_preview:
            text = self.output_preview.get('1.0', tk.END)
            parent_window.clipboard_clear()
            parent_window.clipboard_append(text)
            messagebox.showinfo("Success", "Text copied to clipboard!")
    
    def _save_single_file(self, filename):
        """Save the currently selected file."""
        if not filename:
            return
            
        # Find the full path for this filename
        file_path = None
        for path in self.extracted_text.keys():
            if Path(path).name == filename:
                file_path = path
                break
                
        if not file_path or file_path not in self.extracted_text:
            messagebox.showerror("Error", f"Could not find content for {filename}")
            return
            
        self._save_text_file(file_path, self.extracted_text[file_path])
    
    def _save_extracted_text(self):
        """Save all extracted text to output directory."""
        if not self.extracted_text:
            messagebox.showinfo("Information", "No text has been extracted yet. Please extract text first.")
            return
            
        output_dir = self.output_dir.get()
        if not output_dir:
            # Ask for directory if not set
            output_dir = filedialog.askdirectory(title="Select Output Directory")
            if not output_dir:
                return
            self.output_dir.set(output_dir)
            self.config['output_directory'] = output_dir
            
        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save each file
        saved_count = 0
        failed_count = 0
        
        for file_path, content in self.extracted_text.items():
            try:
                success = self._save_text_file(file_path, content)
                if success:
                    saved_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                self.logger.error(f"Error saving {file_path}: {str(e)}")
                failed_count += 1
        
        # Show summary
        messagebox.showinfo(
            "Save Complete",
            f"Successfully saved {saved_count} files to {output_dir}.\n"
            f"Failed: {failed_count}"
        )
    
    def _save_text_file(self, pdf_path: str, content: str) -> bool:
        """Save extracted text content to a file."""
        try:
            output_dir = Path(self.output_dir.get())
            pdf_filename = Path(pdf_path).name
            
            # Create output filename by replacing .pdf with .txt
            stem = pdf_filename.replace('.pdf', '')

            # Add a suffix for AI-formatted files
            if self.config.get('ai_friendly_format', False):
                output_filename = f"{stem}_ai.txt"
            else:
                output_filename = f"{stem}.txt"
    
            output_path = output_dir / output_filename
            
            # Check if file exists and rename if needed
            counter = 1
            original_stem = output_path.stem
            while output_path.exists():
                output_path = output_dir / f"{original_stem}_{counter}.txt"
                counter += 1
            
            # Write content to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            self.logger.info(f"Saved extracted text to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving text file for {pdf_path}: {str(e)}")
            messagebox.showerror("Error", f"Failed to save {Path(pdf_path).name}: {str(e)}")
            return False
    
    def cancel_operation(self):
        """Cancel the current extraction operation."""
        self.processing = False
        self.message_queue.put("Operation cancelled by user")
        self.cancel_btn.configure(state="disabled")
    
    def process_queues(self):
        """Process message and progress queues."""
        try:
            # Process all pending messages
            while True:
                try:
                    message = self.message_queue.get_nowait()
                    self.status_var.set(message)
                    self.logger.info(message)
                except queue.Empty:
                    break

            # Process progress updates
            try:
                progress, status = self.progress_queue.get_nowait()
                self.progress_var.set(progress)
                self.status_var.set(status)
            except queue.Empty:
                pass
            
        finally:
            # Schedule next queue check if module is enabled
            if self.enabled and hasattr(self, 'progress_bar'):
                self.progress_bar.after(100, self.process_queues)
    
    def save_settings(self) -> Dict[str, Any]:
        """Save current settings to dictionary."""
        # Convert chunk size to integer or keep string for "No chunking"
        chunk_size = self.ai_chunk_size_var.get() if hasattr(self, 'ai_chunk_size_var') else "2000"
        if chunk_size != "No chunking":
            try:
                chunk_size = int(chunk_size)
            except ValueError:
                chunk_size = 2000  # Default if invalid

        if hasattr(self, 'preserve_paragraphs_var'):
            return {
                'output_directory': self.output_dir.get() if hasattr(self, 'output_dir') else '',
                'preserve_paragraphs': self.preserve_paragraphs_var.get(),
                'remove_headers_footers': self.remove_headers_footers_var.get(),
                'simplify_formatting': self.simplify_formatting_var.get(),
                'extract_metadata': self.extract_metadata_var.get(),
                'merge_hyphenated_words': self.merge_hyphenated_words_var.get(),
                'page_separators': self.page_separators_var.get(),
                'ai_friendly_format': self.ai_friendly_var.get(),
                'ai_add_headings': self.ai_add_headings_var.get(),
                'ai_enhance_structure': self.ai_enhance_structure_var.get(),
                'ai_chunk_size': chunk_size
            }
        return self.config.copy()
        
    def load_settings(self, settings: Dict[str, Any]) -> None:
        """Load settings from dictionary."""
        self.config.update(settings)
        # Load AI settings
        if hasattr(self, 'ai_friendly_var'):
            self.ai_friendly_var.set(self.config.get('ai_friendly_format', False))
            self.ai_add_headings_var.set(self.config.get('ai_add_headings', True))
            self.ai_enhance_structure_var.set(self.config.get('ai_enhance_structure', True))
    
            # Set chunk size (handle both string and integer values)
            chunk_size = self.config.get('ai_chunk_size', 2000)
            if isinstance(chunk_size, int):
                self.ai_chunk_size_var.set(str(chunk_size))
            else:
                self.ai_chunk_size_var.set(chunk_size)
    
            # Toggle visibility of AI options
            self._toggle_ai_options()
        
        # Load default settings
        if hasattr(self, 'preserve_paragraphs_var'):
            self.preserve_paragraphs_var.set(self.config.get('preserve_paragraphs', True))
            self.remove_headers_footers_var.set(self.config.get('remove_headers_footers', True))
            self.simplify_formatting_var.set(self.config.get('simplify_formatting', True))
            self.extract_metadata_var.set(self.config.get('extract_metadata', True))
            self.merge_hyphenated_words_var.set(self.config.get('merge_hyphenated_words', True))
            self.page_separators_var.set(self.config.get('page_separators', False))
            
            if hasattr(self, 'output_dir'):
                self.output_dir.set(self.config.get('output_directory', ''))

    def _toggle_ai_options(self):
        """Toggle visibility of AI formatting options."""
        if self.ai_friendly_var.get():
            self.ai_options_frame.pack(fill='x', padx=20, pady=2)
        else:
            self.ai_options_frame.pack_forget()

    def _apply_ai_formatting(self, text: str, filename: str) -> str:
        """
        Apply AI-friendly formatting to the extracted text.
        This optimizes the text for better interpretation by AI models.
        """
        self.logger.info(f"Applying AI-friendly formatting to {filename}")
    
        # First, add document title at the beginning
        ai_text = f"# Document: {filename}\n\n"
    
        # Add table of contents placeholder if it's a long document
        if len(text) > 10000 and self.config['ai_add_headings']:
            ai_text += "## Table of Contents\n"
            ai_text += "The following is a structured extraction of content from the PDF document.\n\n"
        
        # Process document structure if requested
        if self.config['ai_enhance_structure']:
            # Detect potential headings (e.g., lines that appear to be headings)
            lines = text.split('\n')
            inside_list = False
            processed_lines = []
        
            # Try to identify document structure elements
            for i, line in enumerate(lines):
                # Skip empty lines
                if not line.strip():
                    processed_lines.append(line)
                    continue
            
                # Simple heading detection (uppercase lines, numbered sections, etc.)
                if self.config['ai_add_headings']:
                    # Check for section numbers (e.g., "1.2 Section Title")
                    if re.match(r'^\s*\d+(\.\d+)*\s+[A-Z0-9]', line) and len(line) < 100:
                        processed_lines.append(f"\n## {line.strip()}\n")
                        continue
                
                    # Check for all uppercase lines that might be headings
                    if line.isupper() and len(line) < 80:
                        processed_lines.append(f"\n## {line.strip()}\n")
                        continue
                    
                    # Check for title case lines that might be headings
                    words = line.split()
                    if (len(words) >= 2 and len(words) <= 10 and 
                        all(w[0].isupper() for w in words if w and w[0].isalpha()) and
                        len(line) < 80):
                        processed_lines.append(f"\n## {line.strip()}\n")
                        continue
            
                # List item detection
                if line.strip().startswith(('•', '-', '*', '○', '·', '+')) or re.match(r'^\s*\d+[\.\)]\s', line):
                    if not inside_list:
                        processed_lines.append("")  # Add a blank line before lists
                        inside_list = True
                    processed_lines.append(line)
                    continue
            
                # End of list detection
                if inside_list and not line.strip().startswith(('•', '-', '*', '○', '·', '+')) and not re.match(r'^\s*\d+[\.\)]\s', line):
                    inside_list = False
                    processed_lines.append("")  # Add a blank line after lists
            
                # Default - just add the line
                processed_lines.append(line)
        
            # Reassemble text with improved structure
            text = '\n'.join(processed_lines)
        
            # Improve paragraph formatting (add blank lines before headings)
            text = re.sub(r'([^\n])\n## ', r'\1\n\n## ', text)
        
            # Fix any excessive newlines that might have been introduced
            text = re.sub(r'\n{4,}', '\n\n\n', text)
    
        # Add the processed text to our output
        ai_text += text
    
        # Apply chunking if requested (for large documents)
        chunk_size = self.config['ai_chunk_size']
        if chunk_size != "No chunking" and len(ai_text) > chunk_size:
            # Split into approximate chunks
            chunks = self._chunk_text(ai_text, chunk_size)
        
            # Add chunk markers
            chunked_text = ""
            for i, chunk in enumerate(chunks):
                chunked_text += f"\n\n<!-- CHUNK {i+1} OF {len(chunks)} -->\n\n"
                chunked_text += chunk
            
            ai_text = chunked_text
    
        # Add a final note for AI processing
        ai_text += "\n\n<!-- END OF DOCUMENT -->"
    
        return ai_text

    def _chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """
        Split text into chunks of approximately chunk_size characters,
        trying to break at paragraph boundaries where possible.
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        current_pos = 0
        text_length = len(text)
    
        while current_pos < text_length:
            # Find the end position for this chunk
            end_pos = min(current_pos + chunk_size, text_length)
        
            # Try to find a paragraph break near the target end position
            if end_pos < text_length:
                # Look for paragraph breaks (double newlines)
                paragraph_break = text.rfind('\n\n', current_pos, end_pos + 200)
            
                # If found within a reasonable distance, use it
                if paragraph_break != -1 and paragraph_break <= end_pos + 200:
                    end_pos = paragraph_break + 2  # Include the double newline
                else:
                    # Otherwise, look for single newlines
                    newline = text.rfind('\n', current_pos, end_pos + 100)
                    if newline != -1 and newline <= end_pos + 100:
                        end_pos = newline + 1  # Include the newline
                    else:
                        # Last resort: break at a sentence if possible
                        sentence_break = text.rfind('. ', current_pos, end_pos + 50)
                        if sentence_break != -1 and sentence_break <= end_pos + 50:
                            end_pos = sentence_break + 2  # Include the period and space
        
            # Add this chunk to our list
            chunks.append(text[current_pos:end_pos])
            current_pos = end_pos
        
        return chunks