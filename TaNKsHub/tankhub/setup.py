import sys
from cx_Freeze import setup, Executable

# Dependencies
build_exe_options = {
    "packages": ["tkinter", "tkinterdnd2", "os", "json", "logging", "pathlib"],
    "include_files": ["config/"],
}

# Base for Windows (console or no console)
base = None
if sys.platform == "win32":
    base = "Win32GUI"  # Use this to hide console

setup(
    name="TaNKsHub",
    version="1.0",
    description="Media File Management Tool",
    options={"build_exe": build_exe_options},
    executables=[Executable("main.py", base=base, target_name="TaNKsHub.exe")]
)