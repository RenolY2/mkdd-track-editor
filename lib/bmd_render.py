import hashlib
import shutil
import subprocess
import sys
import os
import tempfile
from lib.model_rendering import TexturedModel


mkdd_editor_cache_dir = os.path.join(tempfile.gettempdir(), 'mkdd_track_editor_cache')


def md5sum(filepath: str) -> str:
    return hashlib.md5(open(filepath, 'rb').read()).hexdigest()


def superbmd_to_obj(src):
    checksum = md5sum(src)
    cached_dir = os.path.join(mkdd_editor_cache_dir, checksum)

    if os.path.isdir(cached_dir) and os.path.exists(os.path.join(cached_dir, "temp.obj")):
        shutil.rmtree('lib/temp')
        shutil.copytree(cached_dir, 'lib/temp')
        return

    try:
        os.remove('lib/temp/temp.obj')
    except Exception:
        pass

    command = ["lib/superbmd/SuperBMD.exe", src, "lib/temp/temp.obj", "--exportobj"]
    if sys.platform != "win32":
        command = ["wine"] + command

    with subprocess.Popen(command, stderr=subprocess.PIPE, text=True) as process:
        _output, error_output = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(
                f'BMD conversion failed (code: {process.returncode}):\n{error_output}')

    shutil.rmtree(cached_dir, ignore_errors=True)
    shutil.rmtree(f'{cached_dir}_tmp', ignore_errors=True)
    shutil.copytree('lib/temp', f'{cached_dir}_tmp')
    os.rename(f'{cached_dir}_tmp', cached_dir)


def clear_temp_folder():
    for file in os.listdir("lib/temp/"):
        try:
            os.remove(os.path.join("lib/temp/", file))
        except Exception as err:
            print("Failed to remove", os.path.join("lib/temp/", file), str(err))
            pass


def load_textured_bmd(inputbmd):
    superbmd_to_obj(inputbmd)
    return TexturedModel.from_obj_path("lib/temp/temp.obj", rotate=True)

