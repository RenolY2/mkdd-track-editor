import hashlib
import shutil
import subprocess
import sys
import os
import tempfile
from lib.model_rendering import TexturedModel


def md5sum(filepath: str) -> str:
    return hashlib.md5(open(filepath, 'rb').read()).hexdigest()


def superbmd_to_obj(src):
    checksum = md5sum(src)
    cached_dir = os.path.join(tempfile.gettempdir(), f'mkdd_track_editor_tmp_{checksum}')

    if os.path.isdir(cached_dir):
        shutil.rmtree('lib/temp')
        shutil.copytree(cached_dir, 'lib/temp')
        return

    command = ["lib/superbmd/SuperBMD.exe", src, "lib/temp/temp.obj", "--exportobj"]
    if sys.platform != "Windows":
        command = ["wine"] + command
    subprocess.call(command)

    shutil.copytree('lib/temp', cached_dir)


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

