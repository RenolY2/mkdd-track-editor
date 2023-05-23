import glob
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
    "excludes": ["PySide6.QtWebEngine", "PySide6.QtWebEngineCore"],
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

# A copy of SuperBMD that can be removed. The real one is in `lib/superbmd`.
shutil.rmtree(os.path.join(bundle_dirpath, 'lib', 'lib', 'superbmd'))

# Qt will be trimmed to reduce the size of the bundle.
relative_pyside_dir = os.path.join('lib', 'PySide6')
pyside_dir = os.path.join(bundle_dirpath, relative_pyside_dir)
unwelcome_files = [
    'examples',
    'glue',
    'include',
    'qml',
    'resources',
    'scripts',
    'support',
    'translations',
    'typesystems',
]
for plugin in os.listdir(os.path.join(pyside_dir, 'plugins')):
    if plugin not in ('platforms', 'imageformats'):
        unwelcome_files.append(os.path.join('plugins', plugin))
for glob_pattern in (
        '*.exe',
        '*3D*',
        '*Bluetooth*',
        '*Body*',
        '*Bus*',
        '*Charts*',
        '*Compat*',
        '*compiler*',
        '*Concurrent*',
        '*Container*',
        '*Designer*',
        '*Help*',
        '*Keyboard*',
        '*Labs*',
        '*Multimedia*',
        '*Nfc*',
        '*Positioning*',
        '*Print*',
        '*Quick*',
        '*Remote*',
        '*Scxml*',
        '*Sensors*',
        '*Serial*',
        '*Shader*',
        '*Sql*',
        '*StateMachine*',
        '*SvgWidgets*',
        '*Test*',
        '*Tools*',
        '*Visualization*',
        '*Web*',
        '*Xml*',
):
    for filename in glob.glob(glob_pattern, root_dir=pyside_dir):
        unwelcome_files.append(filename)

for relative_path in sorted(tuple(set(unwelcome_files))):
    path = os.path.join(pyside_dir, relative_path)

    print(f'Remove: "{path}"')

    assert os.path.exists(path)
    if os.path.isfile(path):
        os.remove(path)
    else:
        shutil.rmtree(path)

# Create the ZIP archive.
current_dirpath = os.getcwd()
os.chdir(build_dirpath)
try:
    print('Creating ZIP archive...')
    shutil.make_archive(bundle_dirname, 'zip', '.', bundle_dirname)
finally:
    os.chdir(current_dirpath)
