# modules/__init__.py
from .file_mover import FileMoverModule

# Now someone can do:
from tankhub.modules import FileMoverModule
# Instead of:
from tankhub.modules.file_mover import FileMoverModule
