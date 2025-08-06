
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import List, Dict, Any
from tankhub.core.base_module import BaseModule

class DocumentJoinerModule(BaseModule):
    def __init__(self):
        super().__init__("Document Joiner", "Combine text or markdown documents into a single output")
        self.queued_files: List[Path] = []
        self.config = {
            'output_directory': '',
            'output_format_md': True,
            'output_format_txt': True
        }

    def get_supported_extensions(self) -> List[str]:
        return ['.txt', '.md']

    def process_file(self, file_path: Path, dest_path: Path) -> bool:
        if file_path.exists() and file_path.suffix.lower() in self.get_supported_extensions():
            self.queued_files.append(file_path.resolve())
            self._update_preview()
            return True
        return False

    def get_settings_widget(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent)

        self.preview = tk.Text(frame, height=5, wrap=tk.WORD)
        self.preview.pack(fill='both', expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=5)

        ttk.Button(btn_frame, text="Add Files", command=self._add_files).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Clear Queue", command=self._clear_queue).pack(side='left', padx=5)

        output_frame = ttk.LabelFrame(frame, text="Output Options", padding=5)
        output_frame.pack(fill='x', pady=5)

        self.output_dir_var = tk.StringVar(value=self.config['output_directory'])
        ttk.Entry(output_frame, textvariable=self.output_dir_var).pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(output_frame, text="Browse", command=self._browse_output_dir).pack(side='right', padx=5)

        self.output_md_var = tk.BooleanVar(value=self.config['output_format_md'])
        self.output_txt_var = tk.BooleanVar(value=self.config['output_format_txt'])
        ttk.Checkbutton(output_frame, text="Export .md", variable=self.output_md_var).pack(anchor='w')
        ttk.Checkbutton(output_frame, text="Export .txt", variable=self.output_txt_var).pack(anchor='w')

        ttk.Button(frame, text="Join and Export", command=self._join_and_export).pack(pady=10)

        self._update_preview()
        return frame

    def _add_files(self):
        paths = filedialog.askopenfilenames(title="Select Documents", filetypes=[("Text and Markdown", "*.txt *.md")])
        for p in paths:
            self.process_file(Path(p), None)

    def _clear_queue(self):
        self.queued_files.clear()
        self._update_preview()

    def _browse_output_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir_var.set(directory)

    def _join_and_export(self):
        if not self.queued_files:
            messagebox.showinfo("Info", "No documents in queue.")
            return

        joined_text = ""
        for path in self.queued_files:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    joined_text += f"# {path.name}\n\n{f.read().strip()}\n\n"
            except Exception as e:
                messagebox.showerror("Error", f"Error reading {path.name}: {e}")
                return

        output_dir = Path(self.output_dir_var.get())
        output_dir.mkdir(parents=True, exist_ok=True)

        if self.output_md_var.get():
            (output_dir / "joined_output.md").write_text(joined_text, encoding='utf-8')
        if self.output_txt_var.get():
            (output_dir / "joined_output.txt").write_text(joined_text, encoding='utf-8')

        messagebox.showinfo("Success", f"Export complete to: {output_dir}")

    def _update_preview(self):
        if hasattr(self, 'preview'):
            self.preview.delete('1.0', tk.END)
            for file in self.queued_files:
                self.preview.insert(tk.END, f"{file.name}\n")
            self.preview.insert(tk.END, f"\nTotal: {len(self.queued_files)} file(s) queued.")

    def save_settings(self) -> Dict[str, Any]:
        return {
            'output_directory': self.output_dir_var.get(),
            'output_format_md': self.output_md_var.get(),
            'output_format_txt': self.output_txt_var.get()
        }

    def load_settings(self, settings: Dict[str, Any]) -> None:
        self.config.update(settings)
        self.output_dir_var.set(self.config.get('output_directory', ''))
        self.output_md_var.set(self.config.get('output_format_md', True))
        self.output_txt_var.set(self.config.get('output_format_txt', True))
