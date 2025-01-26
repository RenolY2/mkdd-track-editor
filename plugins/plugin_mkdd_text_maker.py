import os
import subprocess
import sys

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import mkdd_editor


class Plugin(object):

    def __init__(self):
        self.name = "MKDD Text Maker"
        self.actions = [("Open MKDD Text Maker", self.testfunc)]

    def testfunc(self, editor: "mkdd_editor.GenEditor"):
        textmaker_folder = os.path.join(editor.plugins_menu.pluginfolder, "mkdd_text_maker")
        command = [os.path.join(textmaker_folder, "mkdd text maker.exe")]
        if sys.platform != "win32":
            command = ["wine"] + command
        subprocess.Popen(command)

    def unload(self):
        pass
