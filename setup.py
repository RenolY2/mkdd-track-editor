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

for name in os.listdir("./plugins"):
    print(name)
    if name != "mkdd_text_maker":
        include_files.append(("plugins/"+name, "lib/plugins/"+name))

system = platform.system().lower()

ARCH_USER_FRIENDLY_ALIASES = {'AMD64': 'x64', 'x86_64': 'x64'}
machine = platform.machine()
arch = ARCH_USER_FRIENDLY_ALIASES.get(machine) or machine.lower()

build_dirpath = 'build'
bundle_dirname = f'mkdd-track-editor-{version}{version_suffix}-{system}-{arch}'
bundle_dirpath = os.path.join(build_dirpath, bundle_dirname)

build_exe_options = {
    "packages": ["OpenGL", "numba", "numpy.core", "numpy.lib.format", "PIL"],
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

# Manual copy of the mkdd text maker because cx_freeze printing filenames can 
# cause encoding issues on some systems
shutil.copytree(os.path.join("plugins", "mkdd_text_maker"),
                os.path.join(bundle_dirpath, "lib", "plugins", "mkdd_text_maker")) 

# cx-Freeze bundles many libraries in the Qt framework that are not used by this application, which
# is wasteful; in some cases, there are even duplicates.
#
# Duplicates and unused files will be removed from the build to reduce the size of the bundle.
#
# NOTE: What files can or cannot be removed varies between PySide and cx-Freeze versions, meaning
# that this process must be revisited, in both platforms, when there is a library upgrade.

relative_pyside_dir = os.path.join('lib', 'PySide6')
pyside_dir = os.path.join(bundle_dirpath, relative_pyside_dir)

unwelcome_files = []

# Select unwanted files based on glob patterns.
glob_patterns = (
    '**/*Network*',
    '**/*Qml*',
    '**/*Quick*',
    '**/*Pdf*',
    '**/*VirtualKeyboard*',
    '**/platforminputcontexts',
    '**/networkinformation',
)
for glob_pattern in glob_patterns:
    for relative_filepath in glob.glob(glob_pattern,
                                       root_dir=pyside_dir,
                                       recursive=True):
        unwelcome_files.append(relative_filepath)

# Select duplicates of files that exist in the main `lib/` directory.
if system == 'windows':
    qtlib_dirpath = pyside_dir
else:
    qtlib_dirpath = os.path.join(pyside_dir, 'Qt', 'lib')
potentially_duplicate_filenames = os.listdir(qtlib_dirpath)
for rootdir, dirnames, filenames in os.walk(pyside_dir):
    if rootdir == qtlib_dirpath:
        continue
    relative_rootdir = os.path.relpath(rootdir, pyside_dir)
    dirnames.sort()
    filenames.sort()
    for filename in filenames:
        if filename in potentially_duplicate_filenames:
            relative_filepath = os.path.join(relative_rootdir, filename)
            unwelcome_files.append(relative_filepath)

# Effectively remove unwanted files.
for relative_path in set(unwelcome_files):
    print(f'Remove: "{relative_path}"')
    path = os.path.join(pyside_dir, relative_path)
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)

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
