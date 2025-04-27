# modules/__init__.py
from .file_mover import FileMoverModule
from .file_name_editor import FileNameEditorModule
from .media_sorter import MediaSorterModule
from .video_converter import VideoConverterModule
from .pdf_extractor import PDFExtractorModule

"""
# Now someone can do:
# from tankhub.modules import FileMoverModule
# Instead of:
# from tankhub.modules.file_mover import FileMoverModule
# from tankhub.modules.video_converter import VideoConverterModule
"""