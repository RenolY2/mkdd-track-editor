import glob
import os
import platform
import re
import shutil
import subprocess
import time

from cx_Freeze import setup, Executable


def get_git_revision_hash() -> str:
    return subprocess.check_output(('git', 'rev-parse', 'HEAD')).decode('ascii').strip()


# To avoid importing the module, simply parse the file to find the version variable in it.
with open('mkdd_editor.py', 'r', encoding='utf-8') as f:
    main_file_data = f.read()
for line in main_file_data.splitlines():
    if '__version__' in line:
        version = re.search(r"'(.+)'", line).group(1)
        break
else:
    raise RuntimeError('Unable to parse product version.')

is_ci = bool(os.getenv('CI'))
triggered_by_tag = os.getenv('GITHUB_REF_TYPE') == 'tag'
commit_sha = os.getenv('GITHUB_SHA') or get_git_revision_hash()
build_time = time.strftime("%Y-%m-%d %H-%M-%S")

version_suffix = f'-{commit_sha[:8]}' if commit_sha and not triggered_by_tag else ''

# Replace constants in source file.
main_file_data = main_file_data.replace('OFFICIAL = False', f"OFFICIAL = {triggered_by_tag}")
main_file_data = main_file_data.replace("COMMIT_SHA = ''", f"COMMIT_SHA = '{commit_sha}'")
main_file_data = main_file_data.replace("BUILD_TIME = None", f"BUILD_TIME = '{build_time}'")
with open('mkdd_editor.py', 'w', encoding='utf-8') as f:
    f.write(main_file_data)

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

system = platform.system().lower()

ARCH_USER_FRIENDLY_ALIASES = {'AMD64': 'x64', 'x86_64': 'x64'}
machine = platform.machine()
arch = ARCH_USER_FRIENDLY_ALIASES.get(machine) or machine.lower()

build_dirpath = 'build'
bundle_dirname = f'mkdd-track-editor-{version}{version_suffix}-{system}-{arch}'
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
unwelcome_files = []
if os.name == 'nt':
    for plugin in os.listdir(os.path.join(pyside_dir, 'plugins')):
        if plugin not in ('platforms', 'imageformats'):
            unwelcome_files.append(os.path.join('plugins', plugin))
else:
    for plugin in os.listdir(os.path.join(pyside_dir, 'Qt', 'plugins')):
        if not (plugin in ('iconengines', 'imageformats') or plugin.startswith('platform')
                or plugin.startswith('wayland') or plugin.startswith('xcb')):
            unwelcome_files.append(os.path.join('Qt', 'plugins', plugin))

glob_patterns = [
    '*.exe',
    '*3D*',
    '*Bluetooth*',
    '*Body*',
    '*Charts*',
    '*Compat*',
    '*compiler*',
    '*Concurrent*',
    '*Container*',
    '*Designer*',
    '*Help*',
    '*HttpServer*',
    '*JsonRpc*',
    '*Keyboard*',
    '*Labs*',
    '*Language*',
    '*Location*',
    '*Multimedia*',
    '*Network*',
    '*Nfc*',
    '*Pdf*',
    '*Positioning*',
    '*Print*',
    '*Qml*',
    '*Quick*',
    '*Remote*',
    '*Scxml*',
    '*Sensors*',
    '*Serial*',
    '*Shader*',
    '*SpatialAudio*',
    '*Sql*',
    '*StateMachine*',
    '*SvgWidgets*',
    '*Test*',
    '*TextToSpeech*',
    '*Tools*',
    '*Visualization*',
    '*Web*',
    '*Xml*',
    'assistant*',
    'designer*',
    'examples',
    'glue',
    'include',
    'libexec',
    'linguist*',
    'lrelease*',
    'lupdate*',
    'metatypes',
    'plugins/imageformats/*Pdf*',
    'qml',
    'qmlformat*',
    'qmllint*',
    'qmlls*',
    'resources',
    'scripts',
    'support',
    'translations',
    'typesystems',
]
if os.name == 'nt':
    glob_patterns.append('*Bus*')
for glob_pattern in glob_patterns:
    for filename in glob.glob(glob_pattern, root_dir=pyside_dir):
        unwelcome_files.append(filename)
    if os.name != 'nt':
        for filename in glob.glob(glob_pattern, root_dir=os.path.join(pyside_dir, 'Qt')):
            unwelcome_files.append(os.path.join('Qt', filename))
        for filename in glob.glob(glob_pattern, root_dir=os.path.join(pyside_dir, 'Qt', 'lib')):
            unwelcome_files.append(os.path.join('Qt', 'lib', filename))

for relative_path in sorted(tuple(set(unwelcome_files))):
    path = os.path.join(pyside_dir, relative_path)

    if not os.path.exists(path):
        continue

    print(f'Remove: "{path}"')
    if os.path.isfile(path):
        os.remove(path)
    else:
        shutil.rmtree(path)

if not is_ci:
    # Create the ZIP archive.
    current_dirpath = os.getcwd()
    os.chdir(build_dirpath)
    try:
        print('Creating archive...')
        archive_format = 'zip' if os.name == 'nt' else 'xztar'
        shutil.make_archive(bundle_dirname, archive_format, '.', bundle_dirname)
    finally:
        os.chdir(current_dirpath)
