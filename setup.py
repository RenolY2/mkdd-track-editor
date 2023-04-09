import sys
import os 
from cx_Freeze import setup, Executable
version = "1.2"
# Dependencies are automatically detected, but it might need fine tuning.

def files_from_folder(folder):
    return [(folder, x) for x in os.listdir(folder)]

#include_files = files_from_folder("resources/")
#include_files.extend(files_from_folder("object_templates"))
include_files = ["object_parameters",
                "resources/", 
                ("lib/mkddobjects.json", "lib/mkddobjects.json"), 
                ("lib/music_ids.json", "lib/music_ids.json"),
                ("lib/color_coding.json", "lib/color_coding.json"),
                ("lib/minimap_locations.json", "lib/minimap_locations.json"),
                ("lib/superbmd/", "lib/superbmd/")]

build_exe_options = {
"packages": ["OpenGL", "numpy.core._methods", "numpy.lib.format", "PIL"],
"includes": ["widgets"], 
"excludes": ["tkinter", "scipy", "PyQt5.QtWebEngine", "PyQt5.QtWebEngineCore", "PySide2"],
"optimize": 0,
"build_exe": "build/mkdd-track-editor-{}".format(version),
"include_files": include_files}

# GUI applications require a different base on Windows (the default is for a
# console application).
consoleBase = None
guiBase = None#"Win32GUI"
#if sys.platform == "win32":
#    base = "Win32GUI"

setup(  name = "MKDD Track Editor",
        version = version,
        description = "Track Editor for MKDD",
        options={"build_exe": build_exe_options},
        executables = [Executable("mkdd_editor.py", base=guiBase, icon="resources/icon.ico")])
        
os.mkdir("build/mkdd-track-editor-{}/lib/temp".format(version))