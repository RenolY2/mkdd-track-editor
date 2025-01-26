import traceback

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import mkdd_editor

from PySide6 import QtCore
from PySide6 import QtGui
from PySide6 import QtWidgets

from widgets.editor_widgets import open_error_dialog, open_info_dialog

import plugins.mkddcollision.mkdd_collision_creator as mkdd_collision_creator
import plugins.mkddcollision.mkdd_collision_reader as mkdd_collision_reader


class LabeledWidget(QtWidgets.QWidget):
    def __init__(self, parent, text, widget):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        self.setLayout(layout)
        text = QtWidgets.QLabel(self, text)
        layout.addWidget(text)
        layout.addWidget(widget)


class FilepathEntry(QtWidgets.QWidget):
    path_chosen = QtCore.Signal(str)

    def __init__(self, parent, descriptor, buttontext, supported, default_path=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        self.textinput = QtWidgets.QLineEdit(self)
        self.button = QtWidgets.QPushButton(self, text=buttontext)
        self.textinput.setPlaceholderText(descriptor)
        layout.addWidget(self.textinput)
        layout.addWidget(self.button)
        self.setLayout(layout)
        self.supported = supported
        self.default_path = default_path

        if buttontext == "Open":
            self.save_file = False
        else:
            self.save_file = True

        self.button.pressed.connect(self.set_filepath)
        self.textinput.editingFinished.connect(self.change_default)

    def change_default(self):
        self.default_path = self.get_path()

    def get_path(self):
        path = self.textinput.text()
        if path:
            return path
        else:
            return None

    def set_path(self, path):
        self.default_path = path
        self.textinput.setText(path)

    def set_filepath(self):
        if self.save_file:
            filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save File", self.default_path,
                f"{self.supported};;All files (*)")
        else:
            filepath, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Open File", self.default_path,
                f"{self.supported};;All files (*)")

        if filepath:
            self.textinput.setText(filepath)
            self.default_path = filepath
            self.path_chosen.emit(filepath)


class ClosingMdiSubWindow(QtWidgets.QMdiSubWindow):
    closing = QtCore.Signal()

    def closeEvent(self, closeEvent: QtGui.QCloseEvent) -> None:
        super().closeEvent(closeEvent)
        self.closing.emit()


class FromCollisionConverter(ClosingMdiSubWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MKDD Collision to OBJ")
        self.input_path = FilepathEntry(self, "Path to input collision (.bco)",
                                        "Open",
                                        "MKDD Collision (*.bco)")
        self.output_path = FilepathEntry(self, "Path to output file (.obj)",
                                         "Save",
                                         "3D Model (*.obj)")

        self.convert_button = QtWidgets.QPushButton("Convert")
        self.convert_button.pressed.connect(self.convert)

        self.autogen_path = QtWidgets.QCheckBox("Set output path based on input path", self)
        self.autogen_path.setChecked(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.input_path)
        layout.addWidget(self.output_path)
        layout.addWidget(self.autogen_path)
        layout.addWidget(self.convert_button)
        contentwidget = QtWidgets.QWidget(self)

        contentwidget.setLayout(layout)
        self.setWidget(contentwidget)
        self.resize(600, self.minimumSize().height())
        self.input_path.path_chosen.connect(self.update_output_path)

    def update_output_path(self, path):
        if self.autogen_path.isChecked():
            self.output_path.set_path(path+".obj")

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
            mkdd_collision_reader.convert(input_path, output_path, remap_format=True)
            open_info_dialog("Conversion finished!", None)
        except Exception as err:
            open_error_dialog(f"An exception appeared:\n{str(err)}", None)
            traceback.print_exc()

    def get_paths(self):
        return self.input_path.get_path(), self.output_path.get_path()

    def set_paths(self, *paths):
        self.input_path.default_path = paths[0]
        self.output_path.default_path = paths[1]


class ToCollisionConverter(ClosingMdiSubWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("OBJ to MKDD Collision")
        self.input_path = FilepathEntry(self, "Path to input collision (.obj)",
                                        "Open",
                                        "3D Model (*.obj)")
        self.remap_path = FilepathEntry(self, "Path to remap file (Optional)",
                                        "Open",
                                        "Remap file (*.txt)")
        self.output_path = FilepathEntry(self, "Path to output file (.bco)",
                                         "Save",
                                         "MKDD Collision (*.bco)")
        #self.sound_path = FilepathEntry(self, "Path to sound file (Optional)", "Open")

        self.convert_button = QtWidgets.QPushButton("Convert")
        self.convert_button.pressed.connect(self.convert)

        self.autogen_path = QtWidgets.QCheckBox("Set output path based on input path", self)
        self.autogen_path.setChecked(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.input_path)
        layout.addWidget(self.remap_path)
        layout.addWidget(self.output_path)
        layout.addWidget(self.autogen_path)
        layout.addWidget(self.convert_button)
        contentwidget = QtWidgets.QWidget(self)

        contentwidget.setLayout(layout)
        self.setWidget(contentwidget)
        self.resize(600, self.minimumSize().height())
        self.input_path.path_chosen.connect(self.update_output_path)

    def update_output_path(self, path):
        if self.autogen_path.isChecked():
            self.output_path.set_path(path + ".bco")

    def convert(self):
        input_path = self.input_path.get_path()
        if not input_path:
            open_info_dialog("Please choose an input path.", None)
            return

        remap_path = self.remap_path.get_path()

        output_path = self.output_path.get_path()
        if not output_path:
            open_info_dialog("Please choose an output path.", None)
            return

        try:
            mkdd_collision_creator.convert(input_path, output_path, remap_file=remap_path)
            open_info_dialog("Conversion finished!", None)
        except Exception as err:
            open_error_dialog(f"An exception appeared:\n{str(err)}", None)
            traceback.print_exc()

    def get_paths(self):
        return self.input_path.get_path(), self.remap_path.get_path(), self.output_path.get_path()

    def set_paths(self, *paths):
        self.input_path.default_path = paths[0]
        self.remap_path.default_path = paths[1]
        self.output_path.default_path = paths[2]


class Plugin(object):
    def __init__(self):
        self.name = "Collision Tool"
        self.actions = [("MKDD Collision To .OBJ", self.open_from_converter),
                        (".OBJ to MKDD Collision", self.open_to_converter)]
        print("I have been initialized")
        self.from_converter = None
        self.to_converter = None

        self.from_converter_paths = [None, None]
        self.to_converter_paths = [None, None, None]

    def open_from_converter(self, editor: "mkdd_editor.GenEditor"):
        _ = editor
        self.from_converter = FromCollisionConverter()
        self.from_converter.closing.connect(self.save_from_converter_paths)
        self.from_converter.show()

    def open_to_converter(self, editor: "mkdd_editor.GenEditor"):
        _ = editor
        self.to_converter = ToCollisionConverter()
        self.to_converter.closing.connect(self.save_to_converter_paths)
        self.to_converter.show()

    def save_from_converter_paths(self):
        self.from_converter_paths = self.from_converter.get_paths()

    def save_to_converter_paths(self):
        self.to_converter_paths = self.to_converter.get_paths()

    def unload(self):
        print("I have been unloaded")
