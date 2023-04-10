import os
import shutil

from cx_Freeze import setup, Executable

version = "1.2"
# Dependencies are automatically detected, but it might need fine tuning.

include_files = [
    "object_parameters",
    "resources/",
    ("lib/mkddobjects.json", "lib/mkddobjects.json"),
    ("lib/music_ids.json", "lib/music_ids.json"),
    ("lib/color_coding.json", "lib/color_coding.json"),
    ("lib/minimap_locations.json", "lib/minimap_locations.json"),
    ("lib/superbmd/", "lib/superbmd/"),
]

build_dirpath = 'build'
bundle_dirname = f'mkdd-track-editor-{version}'
bundle_dirpath = os.path.join(build_dirpath, bundle_dirname)

build_exe_options = {
    "packages": ["OpenGL", "numpy.core._methods", "numpy.lib.format", "PIL"],
    "includes": ["widgets"],
    "excludes": ["PyQt5.QtWebEngine", "PyQt5.QtWebEngineCore"],
    "optimize": 0,
    "build_exe": bundle_dirpath,
    "include_files": include_files
}

# GUI applications require a different base on Windows (the default is for a
# console application).
consoleBase = None
guiBase = None  #"Win32GUI"
#if sys.platform == "win32":
#    base = "Win32GUI"

setup(name="MKDD Track Editor",
      version=version,
      description="Track Editor for MKDD",
      options={"build_exe": build_exe_options},
      executables=[Executable("mkdd_editor.py", base=guiBase, icon="resources/icon.ico")])

os.mkdir(os.path.join(bundle_dirpath, 'lib', 'temp'))
os.remove(os.path.join(bundle_dirpath, 'frozen_application_license.txt'))

# Create the ZIP archive.
current_dirpath = os.getcwd()
os.chdir(build_dirpath)
try:
    print('Creating ZIP archive...')
    shutil.make_archive(bundle_dirname, 'zip', '.', bundle_dirname)
finally:
    os.chdir(current_dirpath)
