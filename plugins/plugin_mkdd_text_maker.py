import subprocess
import os
from collections import namedtuple
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import mkdd_editor


class Plugin(object):
    def __init__(self):
        self.name = "MKDD Text Maker"
        self.actions = [("Open MKDD Text Maker", self.testfunc)]
        print("I have been initialized")

    def testfunc(self, editor: "mkdd_editor.GenEditor"):
        print(editor.plugins_menu.pluginfolder)
        textmaker_folder = os.path.join(editor.plugins_menu.pluginfolder, "mkdd_text_maker")
        subprocess.Popen([os.path.join(textmaker_folder, "mkdd text maker.exe")])

    def unload(self):
        print("I have been unloaded")
