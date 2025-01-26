import traceback

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import mkdd_editor

from PySide6 import QtWidgets

from lib.rarc import convert

from widgets.editor_widgets import open_error_dialog, open_info_dialog
from plugins.plugin_collision_tool import FilepathEntry, ClosingMdiSubWindow


class FolderEntry(FilepathEntry):
    def set_filepath(self):
        filepath = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose Folder", self.default_path)

        if filepath:
            self.textinput.setText(filepath)
            self.default_path = filepath
            self.path_chosen.emit(filepath)


class ArcToFolder(ClosingMdiSubWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RARC Archive to Folder Extractor")
        self.input_path = FilepathEntry(self, "Path to input archive (.arc)",
                                        "Open",
                                        "MKDD Archive (*.arc)")
        self.output_path = FolderEntry(self, "Path to destination folder",
                                         "Extract To",
                                         None)
        self.input_path.textinput.editingFinished.connect(self.choose_destination_from_input)
        self.convert_button = QtWidgets.QPushButton("Extract Archive to Folder")
        self.convert_button.pressed.connect(self.convert)

        self.autogen_path = QtWidgets.QCheckBox("Set output path based on input path", self)
        self.autogen_path.setChecked(True)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.input_path)
        layout.addWidget(self.output_path)
        layout.addWidget(self.autogen_path)
        layout.addWidget(self.convert_button)
        contentwidget = QtWidgets.QWidget()

        contentwidget.setLayout(layout)
        self.setWidget(contentwidget)
        self.resize(600, self.minimumSize().height())
        self.input_path.path_chosen.connect(self.choose_destination_from_input)

    def choose_destination_from_input(self, path):
        #if self.output_path.get_path() is None:
        if self.autogen_path.isChecked():
            self.output_path.set_path(path+"_ext")

    def convert(self):
        input_path = self.input_path.get_path()
        if not input_path:
            open_info_dialog("Please choose an input path.", None)
            return

        output_path = self.output_path.get_path()
        if not output_path:
            open_info_dialog("Please choose an output path.", None)
            return

        try:
            convert(input_path, output_path, dir2arc=False)
            open_info_dialog("Conversion finished!", None)
        except Exception as err:
            open_error_dialog(f"An exception appeared:\n{str(err)}", None)
            traceback.print_exc()

    def get_paths(self):
        return self.input_path.get_path(), self.output_path.get_path()

    def set_paths(self, *paths):
        self.input_path.default_path = paths[0]
        self.output_path.default_path = paths[1]


class FolderToArc(ClosingMdiSubWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Folder to RARC Archive Packer")
        self.input_path = FolderEntry(self,
                                    "Path to input folder",
                                    "Choose Folder",
                                    None)
        self.output_path = FilepathEntry(self,
                                         "Path to output file (.arc)",
                                         "Save",
                                         "MKDD Archive (*.arc)")

        self.convert_button = QtWidgets.QPushButton("Pack Archive")
        self.convert_button.pressed.connect(self.convert)

        self.autogen_path = QtWidgets.QCheckBox("Set output path based on input path (if input ends with '_ext')", self)
        self.autogen_path.setChecked(True)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.input_path)
        layout.addWidget(self.output_path)
        layout.addWidget(self.autogen_path)
        layout.addWidget(self.convert_button)
        contentwidget = QtWidgets.QWidget()

        contentwidget.setLayout(layout)
        self.setWidget(contentwidget)
        self.resize(600, self.minimumSize().height())
        self.input_path.path_chosen.connect(self.choose_destination_from_input)

    def choose_destination_from_input(self, path: str):
        if self.autogen_path.isChecked() and path.endswith("_ext"):
            self.output_path.set_path(path.removesuffix("_ext"))

    def convert(self):
        input_path = self.input_path.get_path()
        if not input_path:
            open_info_dialog("Please choose an input path.", None)
            return

        output_path = self.output_path.get_path()
        if not output_path:
            open_info_dialog("Please choose an output path.", None)
            return

        try:
            convert(input_path, output_path, dir2arc=True)
            open_info_dialog("Packing finished!", None)
        except Exception as err:
            open_error_dialog(f"An exception appeared:\n{str(err)}", None)
            traceback.print_exc()

    def get_paths(self):
        return self.input_path.get_path(), self.output_path.get_path()

    def set_paths(self, *paths):
        self.input_path.default_path = paths[0]
        self.output_path.default_path = paths[1]


class Plugin(object):
    def __init__(self):
        self.name = "RARC Archive Tool"
        self.actions = [("Pack Folder To .ARC", self.arc_packer_tool),
                        ("Extract .ARC to Folder", self.arc_extractor_tool)]
        self.arc_packer = None
        self.arc_extractor = None

        self.arc_packer_paths = [None, None]
        self.arc_extractor_paths = [None, None, None]

    def arc_packer_tool(self, editor: "mkdd_editor.GenEditor"):
        _ = editor
        self.arc_packer = FolderToArc()
        self.arc_packer.closing.connect(self.save_packer_paths)
        self.arc_packer.show()

    def arc_extractor_tool(self, editor: "mkdd_editor.GenEditor"):
        _ = editor
        self.arc_extractor = ArcToFolder()
        self.arc_extractor.closing.connect(self.save_extractor_paths)
        self.arc_extractor.show()

    def save_packer_paths(self):
        self.arc_packer_paths = self.arc_packer.get_paths()

    def save_extractor_paths(self):
        self.arc_extractor_paths = self.arc_extractor.get_paths()

    def unload(self):
        pass
