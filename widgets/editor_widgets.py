import contextlib
import json
import traceback
from io import StringIO
from itertools import chain
from typing import TYPE_CHECKING

from math import acos, pi
import os
import sys

from PIL import Image

from PyQt5.QtGui import QMouseEvent, QWheelEvent, QPainter, QColor, QFont, QFontMetrics, QPolygon, QImage, QPixmap, QKeySequence
from PyQt5.QtWidgets import (QWidget, QListWidget, QListWidgetItem, QDialog, QMenu, QLineEdit, QFileDialog, QScrollArea,
                            QMdiSubWindow, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QTextEdit, QAction, QShortcut)
import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as QtCore
from PyQt5.QtCore import QSize, pyqtSignal, QPoint, QRect
from PyQt5.QtCore import Qt
import PyQt5.QtGui as QtGui

import configuration
import lib.libbol as libbol
from widgets.data_editor import choose_data_editor, ClickableLabel, ColorPicker
from lib.libbol import get_full_name
from lib import minimap_generator


if TYPE_CHECKING:
    from mkdd_editor import GenEditor


def catch_exception(func):
    def handle(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            QtWidgets.QApplication.quit()
        except:
            traceback.print_exc()
            #raise
    return handle


def catch_exception_with_dialog(func):
    def handle(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), None)
    return handle


def catch_exception_with_dialog_nokw(func):
    def handle(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), None)
    return handle


def open_error_dialog(errormsg, self):
    errorbox = QtWidgets.QMessageBox()
    errorbox.critical(self, "Error", errormsg)
    errorbox.setFixedSize(500, 200)


def open_info_dialog(msg, self):
    box = QtWidgets.QMessageBox()
    box.information(self, "Info", msg)
    box.setFixedSize(500, 200)


class ErrorAnalyzer(QDialog):

    @catch_exception
    def __init__(self, bol, *args, **kwargs):
        super().__init__(*args, **kwargs)
        font = QFont()
        font.setFamily("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(10)

        self.setWindowTitle("Analysis Results")
        self.text_widget = QTextEdit(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text_widget)

        self.setMinimumSize(QSize(300, 300))
        self.text_widget.setFont(font)
        self.text_widget.setReadOnly(True)

        width = self.text_widget.fontMetrics().averageCharWidth() * 80
        height = self.text_widget.fontMetrics().height() * 20
        self.resize(width, height)

        lines = ErrorAnalyzer.analyze_bol(bol)
        if not lines:
            text = "No known common errors detected!"
        else:
            text ='\n\n'.join(lines)
        self.text_widget.setText(text)

    @classmethod
    @catch_exception
    def analyze_bol(cls, bol: libbol.BOL) -> 'list[str]':
        lines: list[str] = []

        def write_line(line):
            lines.append(line)

        # Check enemy point linkage errors
        links = {}
        for group_index, group in enumerate(bol.enemypointgroups.groups):
            for i, point in enumerate(group.points):
                if point.link == -1:
                    continue

                if point.link not in links:
                    links[point.link] = [(group_index, i, point)]
                else:
                    links[point.link].append(((group_index, i, point)))

        for link_id, points in links.items():
            if len(points) == 1:
                group_index, i, point = points[0]
                write_line("Point {0} in enemy point group {1} has link {2}; No other point has link {2}".format(
                    i, group_index, point.link
                ))
        for group_index, group in enumerate(bol.enemypointgroups.groups):
            if not group.points:
                write_line("Empty enemy path {0}.".format(group_index))
                continue

            if group.points[0].link == -1:
                write_line("Start point of enemy point group {0} has no valid link to form a loop".format(group_index))
            if group.points[-1].link == -1:
                write_line("End point of enemy point group {0} has no valid link to form a loop".format(group_index))

        # Check enemy paths unique ID.
        enemy_paths_ids = {}
        for enemy_path_index, enemy_path in enumerate(bol.enemypointgroups.groups):
            if enemy_path.id in enemy_paths_ids:
                write_line(f"Enemy path {group_index} using ID {enemy_path.id} that is already "
                           f"used by enemy path {enemy_paths_ids[enemy_path.id]}.")
            else:
                enemy_paths_ids[enemy_path.id] = enemy_path_index

        # Check prev/next groups of checkpoints
        for i, group in enumerate(bol.checkpoints.groups):
            for index in chain(group.prevgroup, group.nextgroup):
                if index != -1:
                    if index < -1 or index+1 > len(bol.checkpoints.groups):
                        write_line("Checkpoint group {0} has invalid Prev or Nextgroup index {1}".format(
                            i, index
                        ))

        # Validate path id in objects
        for object in bol.objects.objects:
            if object.pathid < -1 or object.pathid + 1 > len(bol.routes):
                write_line("Map object {0} uses path id {1} that does not exist".format(
                    get_full_name(object.objectid), object.pathid
                ))

        # Validate Kart start positions
        if len(bol.kartpoints.positions) == 0:
            write_line("Map contains no kart start points")
        else:
            exist = [False for x in range(8)]

            for i, kartstartpos in enumerate(bol.kartpoints.positions):
                if kartstartpos.playerid == 0xFF:
                    if all(exist):
                        write_line("Duplicate kart start point for all karts")
                    exist = [True for x in range(8)]
                elif kartstartpos.playerid > 8:
                    write_line("A kart start point with an invalid player id exists: {0}".format(
                        kartstartpos.playerid
                    ))
                elif exist[kartstartpos.playerid]:
                    write_line("Duplicate kart start point for player id {0}".format(
                        kartstartpos.playerid))
                else:
                    exist[kartstartpos.playerid] = True

        # Check camera indices in areas
        for i, area in enumerate(bol.areas.areas):
            if area.camera_index < -1 or area.camera_index + 1 > len(bol.cameras):
                write_line("Area {0} uses invalid camera index {1}".format(i, area.camera_index))

        # Check cameras
        for i, camera in enumerate(bol.cameras):
            if camera.nextcam < -1 or camera.nextcam + 1 > len(bol.cameras):
                write_line("Camera {0} uses invalid nextcam (next camera) index {1}".format(
                    i, camera.nextcam
                ))
            if camera.route < -1 or camera.route + 1 > len(bol.routes):
                write_line("Camera {0} uses invalid path id {1}".format(i,
                                                                        camera.route))

        if len(bol.checkpoints.groups) == 0:
            write_line("You need at least one checkpoint group!")

        if len(bol.enemypointgroups.groups) == 0:
            write_line("You need at least one enemy point group!")

        cls.check_checkpoints_convex(bol, write_line)

        return lines

    @classmethod
    def check_checkpoints_convex(cls, bol, write_line):
        for gindex, group in enumerate(bol.checkpoints.groups):
            if len(group.points) > 1:
                for i in range(1, len(group.points)):
                    c1 = group.points[i-1]
                    c2 = group.points[i]

                    lastsign = None

                    for p1, mid, p3 in ((c1.start, c2.start, c2.end),
                                        (c2.start, c2.end, c1.end),
                                        (c2.end, c1.end, c1.start),
                                        (c1.end, c1.start, c2.start)):
                        side1 = p1 - mid
                        side2 = p3 - mid
                        prod = side1.x * side2.z - side2.x * side1.z
                        if lastsign is None:
                            lastsign = prod > 0
                        else:
                            if not (lastsign == (prod > 0)):
                                write_line("Quad formed by checkpoints {0} and {1} in checkpoint group {2} isn't convex.".format(
                                    i-1, i, gindex
                                ))
                                break


class ErrorAnalyzerButton(QtWidgets.QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.success_icon = QtGui.QIcon('resources/success.svg')
        self.warning_icon = QtGui.QIcon('resources/warning.svg')

        self.setEnabled(False)

        background_color = self.palette().dark().color().name()
        self.setStyleSheet("QPushButton { border: 0px; padding: 2px; } "
                           f"QPushButton:hover {{ background: {background_color}; }}")

    def analyze_bol(self, bol: libbol.BOL):
        lines = ErrorAnalyzer.analyze_bol(bol)
        if lines:
            self.setIcon(self.warning_icon)
            self.setText(str(len(lines)))
        else:
            self.setIcon(self.success_icon)
            self.setText(str())
        self.setEnabled(True)


class AddPikObjectWindow(QDialog):

    @catch_exception
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "windowtype" in kwargs:
            self.window_name = kwargs["windowtype"]
        else:
            self.window_name = "Add Object"

        width = self.fontMetrics().averageCharWidth() * 80
        height = self.fontMetrics().height() * 42
        self.resize(width, height)
        self.setMinimumSize(QSize(300, 300))

        self.entity = None

        font = QFont()
        font.setFamily("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(10)


        self.verticalLayout = QVBoxLayout(self)
        self.verticalLayout.setAlignment(Qt.AlignTop)



        self.setup_dropdown_menu()



        self.hbox1 = QHBoxLayout()
        self.hbox2 = QHBoxLayout()

        self.label1 = QLabel(self)
        self.label2 = QLabel(self)
        self.label3 = QLabel(self)
        self.label1.setText("Group")
        self.label2.setText("Position in Group")
        self.label3.setText("(-1 means end of Group)")
        self.group_edit = QLineEdit(self)
        self.position_edit = QLineEdit(self)

        self.group_edit.setValidator(QtGui.QIntValidator(0, 2**31-1))
        self.position_edit.setValidator(QtGui.QIntValidator(-1, 2**31-1))

        self.hbox1.setAlignment(Qt.AlignRight)
        self.hbox2.setAlignment(Qt.AlignRight)

        self.verticalLayout.addLayout(self.hbox1)
        self.verticalLayout.addLayout(self.hbox2)
        self.hbox1.addWidget(self.label1)
        self.hbox1.addWidget(self.group_edit)
        self.hbox2.addWidget(self.label2)
        self.hbox2.addWidget(self.position_edit)
        self.hbox2.addWidget(self.label3)

        self.label1.setVisible(False)
        self.label2.setVisible(False)
        self.label3.setVisible(False)
        self.group_edit.setVisible(False)
        self.position_edit.setVisible(False)


        self.editor_widget = None
        self.editor_layout = QScrollArea()#QVBoxLayout(self.centralwidget)
        palette = self.editor_layout.palette()
        palette.setBrush(self.editor_layout.backgroundRole(), palette.dark())
        self.editor_layout.setPalette(palette)
        self.editor_layout.setWidgetResizable(True)
        self.verticalLayout.addWidget(self.editor_layout)
        #self.textbox_xml = QTextEdit(self.centralwidget)
        button_area_layout = QHBoxLayout()
        self.button_savetext = QPushButton(self)
        self.button_savetext.setText("Add Object")
        self.button_savetext.setToolTip("Hotkey: Ctrl+S")
        self.button_savetext.setDisabled(True)
        self.button_savetext.clicked.connect(self.accept)
        button_area_layout.addStretch()
        button_area_layout.addWidget(self.button_savetext)

        self.verticalLayout.addLayout(button_area_layout)
        self.setWindowTitle(self.window_name)
        self.created_object = None
        #QtWidgets.QShortcut(Qt.CTRL + Qt.Key_S, self).activated.connect(self.emit_add_object)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == Qt.CTRL + Qt.Key_S:
            self.emit_add_object()
        else:
            super().keyPressEvent(event)

    def emit_add_object(self):
        self.button_savetext.pressed.emit()

    def get_content(self):
        try:
            if not self.group_edit.text():
                group = None
            else:
                group = int(self.group_edit.text())
            if not self.position_edit.text():
                position = None
            else:
                position = int(self.position_edit.text())
            return self.created_object, group, position

        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), self)
            return None

    def setup_dropdown_menu(self):
        self.category_menu = QtWidgets.QComboBox(self)
        self.category_menu.addItem("-- select type --")

        self.verticalLayout.addWidget(self.category_menu)

        self.objecttypes = {
            "Enemy Point": libbol.EnemyPoint,
            "Checkpoint": libbol.Checkpoint,
            "Route Point": libbol.RoutePoint,
            "Object": libbol.MapObject,
            "Area": libbol.Area,
            "Camera": libbol.Camera,
            "Respawn Point": libbol.JugemPoint,
            "Kart Start Point": libbol.KartStartPoint,
            "Enemy Path": libbol.EnemyPointGroup,
            "Checkpoint Group": libbol.CheckpointGroup,
            "Route": libbol.Route,
            "Light Param": libbol.LightParam,
            "Minigame Param": libbol.MGEntry
        }

        self.category_menu.addItem("Enemy Path")
        self.category_menu.addItem("Enemy Point")
        self.category_menu.insertSeparator(self.category_menu.count())
        self.category_menu.addItem("Checkpoint Group")
        self.category_menu.addItem("Checkpoint")
        self.category_menu.insertSeparator(self.category_menu.count())
        self.category_menu.addItem("Route")
        self.category_menu.addItem("Route Point")
        self.category_menu.insertSeparator(self.category_menu.count())
        self.category_menu.addItem("Object")
        self.category_menu.addItem("Kart Start Point")
        self.category_menu.addItem("Area")
        self.category_menu.addItem("Camera")
        self.category_menu.addItem("Respawn Point")
        self.category_menu.insertSeparator(self.category_menu.count())
        self.category_menu.addItem("Light Param")
        self.category_menu.addItem("Minigame Param")

        for i in range(1, self.category_menu.count()):
            text = self.category_menu.itemText(i)
            assert not text or text in self.objecttypes

        self.category_menu.currentIndexChanged.connect(self.change_category)

    def update_label(self):
        editor = self.parent()
        selected_items = editor.leveldatatreeview.selectedItems()
        group = insertion_index = None

        if selected_items:
            selected_item = selected_items[-1]
            if isinstance(selected_item.bound_to, libbol.EnemyPoint):
                group = selected_item.parent().get_index_in_parent()
                insertion_index = selected_item.get_index_in_parent() + 1
            elif isinstance(selected_item.bound_to, libbol.EnemyPointGroup):
                group = selected_item.get_index_in_parent()
                insertion_index = 0

        if group is not None:
            self.group_edit.setText(str(group))
            self.position_edit.setText(str(insertion_index))
            self.group_edit.setDisabled(True)
            self.position_edit.setDisabled(True)
        else:
            self.group_edit.setDisabled(False)
            self.position_edit.setDisabled(False)

    def change_category(self, index):
        if index > 0:
            item = self.category_menu.currentText()
            self.button_savetext.setDisabled(False)
            objecttype = self.objecttypes[item]

            if self.editor_widget is not None:
                self.editor_widget.deleteLater()
                self.editor_widget = None
            if self.created_object is not None:
                del self.created_object

            self.created_object = objecttype.new()


            if isinstance(self.created_object, (libbol.Checkpoint, libbol.EnemyPoint, libbol.RoutePoint)):
                self.group_edit.setVisible(True)
                self.position_edit.setVisible(True)
                self.group_edit.setText("0")
                self.position_edit.setText("-1")
            else:
                self.group_edit.setVisible(False)
                self.position_edit.setVisible(False)
                self.group_edit.clear()
                self.position_edit.clear()

            if isinstance(self.created_object, (libbol.EnemyPoint, )):
                self.update_label()
                
            data_editor = choose_data_editor(self.created_object)
            if data_editor is not None:
                self.editor_widget = data_editor(self, self.created_object)
                self.editor_widget.layout().addStretch()
                margin = self.fontMetrics().averageCharWidth()
                self.editor_widget.setContentsMargins(margin, margin, margin, margin)
                self.editor_layout.setWidget(self.editor_widget)
                self.editor_widget.update_data()

        else:
            self.editor_widget.deleteLater()
            self.editor_widget = None
            del self.created_object
            self.created_object = None
            self.button_savetext.setDisabled(True)
            self.position_edit.setVisible(False)
            self.group_edit.setVisible(False)

        self.label1.setVisible(self.position_edit.isVisible())
        self.label2.setVisible(self.position_edit.isVisible())
        self.label3.setVisible(self.position_edit.isVisible())

class SpawnpointEditor(QMdiSubWindow):
    triggered = pyqtSignal(object)
    closing = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.centralwidget = QWidget(self)
        self.setWidget(self.centralwidget)
        self.entity = None
        self.resize(400, 200)

        font = QFont()
        font.setFamily("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(10)
        self.verticalLayout = QVBoxLayout(self.centralwidget)

        self.position = QLineEdit(self.centralwidget)
        self.rotation = QLineEdit(self.centralwidget)

        self.button_savetext = QPushButton(self.centralwidget)
        self.button_savetext.setText("Set Data")
        self.button_savetext.setMaximumWidth(400)

        self.verticalLayout.addWidget(QLabel("startPos"))
        self.verticalLayout.addWidget(self.position)
        self.verticalLayout.addWidget(QLabel("startDir"))
        self.verticalLayout.addWidget(self.rotation)
        self.verticalLayout.addWidget(self.button_savetext)
        self.setWindowTitle("Edit startPos/Dir")

    def closeEvent(self, event):
        self.closing.emit()

    def get_pos_dir(self):
        pos = self.position.text().strip()
        direction = float(self.rotation.text().strip())

        if "," in pos:
            pos = [float(x.strip()) for x in pos.split(",")]
        else:
            pos = [float(x.strip()) for x in pos.split(" ")]

        assert len(pos) == 3

        return pos, direction


@contextlib.contextmanager
def blocked_signals(obj: QtCore.QObject):
    # QSignalBlocker may or may not be available in some versions of the different Qt bindings.
    signals_were_blocked = obj.blockSignals(True)
    try:
        yield
    finally:
        if not signals_were_blocked:
            obj.blockSignals(False)


class SpinnableSlider(QtWidgets.QWidget):

    value_changed = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.setContentsMargins(0, 0, 0, 0)

        self.__slider = QtWidgets.QSlider()
        self.__slider.setOrientation(QtCore.Qt.Horizontal)
        self.__slider.valueChanged.connect(self._on_value_changed)
        self.__spinbox = QtWidgets.QSpinBox()
        self.__spinbox.valueChanged.connect(self._on_value_changed)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.__slider)
        layout.addWidget(self.__spinbox)

    def set_range(self, min_value: int, max_value: int, value: int):
        self.__slider.setMinimum(min_value)
        self.__slider.setMaximum(max_value)
        self.__spinbox.setMinimum(min_value)
        self.__spinbox.setMaximum(max_value)
        self.__slider.setValue(value)
        self.__spinbox.setValue(value)

    def set_value(self, value: int):
        self.__slider.setValue(value)

    def get_value(self) -> int:
        return self.__slider.value()

    def set_step(self, single_step: int, page_step: int):
        self.__slider.setSingleStep(single_step)
        self.__slider.setPageStep(page_step)
        self.__spinbox.setSingleStep(single_step)

    def _on_value_changed(self, value: int):
        with blocked_signals(self.__slider):
            self.__slider.setValue(value)
        with blocked_signals(self.__spinbox):
            self.__spinbox.setValue(value)
        self.value_changed.emit(value)


def show_minimap_generator(editor: 'GenEditor'):
    dialog = QtWidgets.QDialog(editor)
    dialog.setMinimumWidth(dialog.fontMetrics().averageCharWidth() * 80)
    dialog.setWindowTitle('Minimap Generator')

    description = (
        'Adjust orientation and margin so that the minimap fits the canvas optimally without any '
        'clipping at the edges.'
        '<br/><br/>'
        'Generated minimaps will often require manual editing in an image editor to achieve '
        'professional results. When in doubt, study how minimaps in stock courses look like.')
    description_label = QtWidgets.QLabel()
    description_label.setWordWrap(True)
    description_label.setSizePolicy(description_label.sizePolicy().horizontalPolicy(),
                                    QtWidgets.QSizePolicy.Fixed)
    description_label.setText(description)

    form_layout = QtWidgets.QFormLayout()
    form_layout.setLabelAlignment(QtCore.Qt.AlignRight)
    orientation_combobox = QtWidgets.QComboBox()
    orientation_combobox.addItem('Upwards')
    orientation_combobox.addItem('Leftwards')
    orientation_combobox.addItem('Downwards')
    orientation_combobox.addItem('Rightwards')
    orientation_combobox.setCurrentIndex(minimap_generator.DEFAULT_ORIENTATION)
    form_layout.addRow('Orientation', orientation_combobox)
    margin_slider = SpinnableSlider()
    margin_slider.set_step(1, 1)
    margin_slider.set_range(
        0,
        min(minimap_generator.MINIMAP_WIDTH, minimap_generator.MINIMAP_HEIGHT) * 3 // 8,
        minimap_generator.DEFAULT_MARGIN)
    form_layout.addRow('Margin', margin_slider)
    outline_slider = SpinnableSlider()
    outline_slider.set_step(1, 1)
    outline_slider.set_range(0, 50, minimap_generator.DEFAULT_OUTLINE)
    form_layout.addRow('Outline', outline_slider)
    outline_rasterization_mode_tool_tip = (
        'Choose <b>Combined Pass</b> for courses with overlapped areas; choose '
        '<b>Separate Passes</b> for better results in courses with no overlapped areas.')
    outline_rasterization_mode_widget = QtWidgets.QWidget()
    outline_rasterization_mode_widget.setToolTip(outline_rasterization_mode_tool_tip)
    outline_rasterization_mode_layout = QtWidgets.QHBoxLayout(outline_rasterization_mode_widget)
    outline_rasterization_mode_layout.setContentsMargins(0, 0, 0, 0)
    outline_rasterization_mode_separate_passes_radiobutton = QtWidgets.QRadioButton(
        'Separate Passes')
    outline_rasterization_mode_combined_pass_radiobutton = QtWidgets.QRadioButton('Combined Pass')
    outline_rasterization_mode_combined_pass_radiobutton.setChecked(True)
    outline_rasterization_mode_layout.addWidget(
        outline_rasterization_mode_separate_passes_radiobutton)
    outline_rasterization_mode_layout.addWidget(
        outline_rasterization_mode_combined_pass_radiobutton)
    outline_rasterization_mode_layout.addStretch()
    form_layout.addRow('Outline Rasterization Mode', outline_rasterization_mode_widget)
    form_layout.labelForField(outline_rasterization_mode_widget).setToolTip(
        outline_rasterization_mode_tool_tip)
    outline_vertical_offset_tool_tip = (
        'Vertical offset of the outline associated with the triangle being rasterized. Greater '
        '[absolute] values guarantee that a triangle does not overlap with its outline, at the '
        'expense of potentially overlapping with nearby triangles.'
        '<br/><br/>'
        'This value needs to be adjusted in a per-case basis.')
    outline_vertical_offset_slider = SpinnableSlider()
    outline_vertical_offset_slider.setToolTip(outline_vertical_offset_tool_tip)
    outline_vertical_offset_slider.set_step(10, 100)
    outline_vertical_offset_slider.set_range(-10000, 0,
                                             minimap_generator.DEFAULT_OUTLINE_VERTICAL_OFFSET)
    form_layout.addRow('Outline Vertical Offset', outline_vertical_offset_slider)
    form_layout.labelForField(outline_vertical_offset_slider).setToolTip(
        outline_vertical_offset_tool_tip)
    multisampling_tool_tip = (
        'For faster previsualization, temporarily reduce the number of samples to <b>1x</b>. Set '
        'to at least <b>3x</b> before exporting the image.')
    multisampling_combobox = QtWidgets.QComboBox()
    multisampling_combobox.setToolTip(multisampling_tool_tip)
    for i in range(5):
        multisampling_combobox.addItem(f'{i + 1}x')
    multisampling_combobox.setCurrentIndex(minimap_generator.DEFAULT_MULTISAMPLING - 1)
    form_layout.addRow('Multisampling', multisampling_combobox)
    form_layout.labelForField(multisampling_combobox).setToolTip(multisampling_tool_tip)
    color_mode_tool_tip = (
        'Choose <b>Custom Colors</b> only in Battle Courses, or in courses that need colors in '
        '<em>very</em> specific areas such as off-road types, boost pads, or dead zones.'
        '<br/><br/>'
        'Colored minimaps are often difficult to see, defeating their purpose. Avoid custom colors '
        'whenever possible.')
    color_mode_widget = QtWidgets.QWidget()
    color_mode_widget.setToolTip(color_mode_tool_tip)
    color_mode_layout = QtWidgets.QHBoxLayout(color_mode_widget)
    color_mode_layout.setContentsMargins(0, 0, 0, 0)
    color_mode_blackwhite_radiobutton = QtWidgets.QRadioButton('Black And White')
    color_mode_customcolors_radiobutton = QtWidgets.QRadioButton('Custom Colors')
    color_mode_blackwhite_radiobutton.setChecked(True)
    color_mode_layout.addWidget(color_mode_blackwhite_radiobutton)
    color_mode_layout.addWidget(color_mode_customcolors_radiobutton)
    color_mode_layout.addStretch()
    form_layout.addRow('Color Mode', color_mode_widget)
    form_layout.labelForField(color_mode_widget).setToolTip(color_mode_tool_tip)

    COLUMN_LABELS = ('Type', 'Description', 'Visible', 'Color')
    TERRAIN_DESCRIPTIONS = {
        0x0000: 'Medium Off-road',
        0x0100: 'Road',
        0x0200: 'Wall',
        0x0300: 'Medium Off-road',
        0x0400: 'Slippery Ice',
        0x0500: 'Dead zone',
        0x0600: 'Grassy Wall',
        0x0700: 'Boost',
        0x0800: 'Boost',
        0x0900: 'Cannon Boost',
        0x0A00: 'Deadzone',
        0x0C00: 'Weak Off-road',
        0x0D00: 'Teleport',
        0x0E00: 'Sand Dead zone',
        0x0F00: 'Wavy Dead zone',
        0x1000: 'Quicksand Dead zone',
        0x1100: 'Dead zone',
        0x1200: 'Kart-Only Wall',
        0x1300: 'Heavy Off-road',
        0x3700: 'Boost',
        0x4700: 'Boost',
    }

    terrain_colors_table_font = dialog.font()
    terrain_colors_table_font.setPointSize(round(terrain_colors_table_font.pointSize() * 0.8))
    terrain_colors_table_fontmetrics = QtGui.QFontMetrics(terrain_colors_table_font)

    terrain_colors_table = QtWidgets.QTableWidget(len(minimap_generator.DEFAULT_TERRAIN_COLORS),
                                                  len(COLUMN_LABELS))
    terrain_colors_table.setFont(terrain_colors_table_font)
    terrain_colors_table.setHorizontalHeaderLabels(COLUMN_LABELS)
    terrain_colors_table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
    terrain_colors_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    terrain_colors_table.horizontalHeader().setFont(terrain_colors_table_font)
    terrain_colors_table.horizontalHeader().setSectionResizeMode(
        0, QtWidgets.QHeaderView.ResizeToContents)
    terrain_colors_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
    terrain_colors_table.horizontalHeader().setSectionResizeMode(
        2, QtWidgets.QHeaderView.ResizeToContents)
    terrain_colors_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
    terrain_colors_table.horizontalHeader().setSectionsClickable(False)
    terrain_colors_table.horizontalHeader().setSectionsMovable(False)
    terrain_colors_table.verticalHeader().hide()
    terrain_colors_table.verticalHeader().setDefaultSectionSize(
        round(terrain_colors_table_fontmetrics.height() * 1.5))
    terrain_colors_widgets_map = dict()
    for i, (terrain_type, visible, color) in enumerate(minimap_generator.DEFAULT_TERRAIN_COLORS):
        type_label = f'0x{terrain_type >> 8:02X}__'
        type_label_item = QtWidgets.QTableWidgetItem(type_label)
        type_label_item.setTextAlignment(QtCore.Qt.AlignCenter)
        desc_label_item = QtWidgets.QTableWidgetItem(TERRAIN_DESCRIPTIONS[terrain_type])
        desc_label_item.setTextAlignment(QtCore.Qt.AlignCenter)
        visible_checkbox = QtWidgets.QCheckBox()
        visible_checkbox.setChecked(visible)
        visible_checkbox_widget = QtWidgets.QWidget()
        visible_checkbox_widget_layout = QtWidgets.QHBoxLayout(visible_checkbox_widget)
        visible_checkbox_widget_layout.setContentsMargins(0, 0, 0, 0)
        visible_checkbox_widget_layout.setAlignment(QtCore.Qt.AlignCenter)
        visible_checkbox_widget_layout.addWidget(visible_checkbox)
        color_picker = ColorPicker()
        color_picker.color = QtGui.QColor(*color)
        color_picker.update_color(QtGui.QColor(*color))
        color_picker_label = ClickableLabel('({}, {}, {})'.format(*color))
        color_picker_label.clicked.connect(color_picker.clicked)
        color_picker_widget = QtWidgets.QWidget()
        color_picker_widget_layout = QtWidgets.QHBoxLayout(color_picker_widget)
        color_picker_widget_layout.setContentsMargins(0, 0, 0, 0)
        color_picker_widget_layout.setAlignment(QtCore.Qt.AlignHCenter)
        color_picker_widget_layout.addWidget(color_picker)
        color_picker_widget_layout.addWidget(color_picker_label)
        terrain_colors_table.setItem(i, 0, type_label_item)
        terrain_colors_table.setItem(i, 1, desc_label_item)
        terrain_colors_table.setCellWidget(i, 2, visible_checkbox_widget)
        terrain_colors_table.setCellWidget(i, 3, color_picker_widget)
        terrain_colors_widgets_map[terrain_type] = (visible_checkbox, color_picker,
                                                    color_picker_label)
        # TODO(CA): Fit first and third column; expand the others.
        # TODO(CA): Reduce font size.
    form_layout.addRow(terrain_colors_table)

    menu = QtWidgets.QMenu()
    save_image_png_action = menu.addAction('Save Image as PNG')
    save_image_bti_action = menu.addAction('Save Image as BTI')
    menu.addSeparator()
    save_data_action = menu.addAction('Save Data to JSON')
    menu.addSeparator()
    copy_action = menu.addAction('Copy to Clipboard')

    image_placeholder = []

    def on_copy_action_triggered():
        if not image_placeholder:
            return

        image = image_placeholder[0]
        data = image.tobytes("raw", "RGBA")
        QtWidgets.QApplication.instance().clipboard().setPixmap(
            QtGui.QPixmap.fromImage(
                QtGui.QImage(data, image.width, image.height, QtGui.QImage.Format_RGBA8888)))

    save_image_png_action.triggered.connect(
        lambda checked: editor.action_save_minimap_image(checked, 'png'))
    save_image_bti_action.triggered.connect(
        lambda checked: editor.action_save_minimap_image(checked, 'bti'))
    save_data_action.triggered.connect(editor.action_save_coordinates_json)
    copy_action.triggered.connect(on_copy_action_triggered)

    image_widget = QtWidgets.QLabel()
    image_widget.setAlignment(QtCore.Qt.AlignCenter)
    image_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    image_widget.customContextMenuRequested.connect(
        lambda pos: menu.exec_(image_widget.mapToGlobal(pos)))
    palette = image_widget.palette()
    palette.setColor(image_widget.foregroundRole(), QtGui.QColor(170, 20, 20))
    image_widget.setPalette(palette)

    image_frame = QtWidgets.QFrame()
    image_frame.setAutoFillBackground(True)
    image_frame.setFrameStyle(QtWidgets.QFrame.StyledPanel)
    image_frame_margin = dialog.fontMetrics().height()
    image_frame.setMinimumSize(minimap_generator.MINIMAP_WIDTH + image_frame_margin * 2,
                               minimap_generator.MINIMAP_HEIGHT + image_frame_margin * 2)
    palette = image_frame.palette()
    palette.setBrush(image_frame.backgroundRole(), palette.dark())
    image_frame.setPalette(palette)
    image_frame_layout = QtWidgets.QVBoxLayout(image_frame)
    image_frame_layout.setAlignment(QtCore.Qt.AlignCenter)
    image_frame_layout.addWidget(image_widget)

    main_layout = QtWidgets.QHBoxLayout()
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.addLayout(form_layout, 2)
    main_layout.addWidget(image_frame, 1)

    reset_button = QtWidgets.QPushButton('Reset')
    reset_button.setAutoDefault(False)
    save_button = QtWidgets.QPushButton('Save')
    save_button.setAutoDefault(False)
    save_button.setMenu(menu)
    bottom_layout = QtWidgets.QHBoxLayout()
    bottom_layout.addWidget(reset_button)
    bottom_layout.addStretch()
    bottom_layout.addWidget(save_button)

    layout = QtWidgets.QVBoxLayout(dialog)
    layout.addWidget(description_label)
    layout.addSpacing(dialog.fontMetrics().height())
    layout.addLayout(main_layout, 1)
    layout.addSpacing(dialog.fontMetrics().height() // 2)
    layout.addLayout(bottom_layout)

    def update():
        # Retrieve arguments.
        orientation = orientation_combobox.currentIndex()
        margin = margin_slider.get_value()
        outline = outline_slider.get_value()
        if outline_rasterization_mode_combined_pass_radiobutton.isChecked():
            outline_vertical_offset = outline_vertical_offset_slider.get_value()
        else:
            outline_vertical_offset = None
        multisampling = multisampling_combobox.currentIndex() + 1
        if color_mode_blackwhite_radiobutton.isChecked():
            terrain_colors = minimap_generator.DEFAULT_TERRAIN_COLORS
        else:
            terrain_colors = tuple(
                (terrain_type, visible_checkbox.isChecked(), (color_picker.tmp_color.red(),
                                                              color_picker.tmp_color.green(),
                                                              color_picker.tmp_color.blue()))
                for terrain_type, (visible_checkbox, color_picker,
                                   _color_picker_label) in terrain_colors_widgets_map.items())

        # Generate the minimap image.
        image_placeholder.clear()
        image, coordinates = minimap_generator.collision_to_minimap(editor.bco_coll, orientation,
                                                                    margin, outline,
                                                                    outline_vertical_offset,
                                                                    multisampling, terrain_colors)
        image_placeholder.append(image)

        # Update image widget with the final image.
        background = (128, 128, 128)
        image_with_background = Image.new('RGBA', (image.width, image.height), background)
        image_with_background.alpha_composite(image)
        data = image_with_background.tobytes("raw", "RGBA")
        pixmap = QtGui.QPixmap.fromImage(
            QtGui.QImage(data, image.width, image.height, QtGui.QImage.Format_RGBA8888))
        image_widget.setPixmap(pixmap)
        image_widget.setMinimumSize(image.width, image.height)

        # Update minimap in viewport.
        editor.level_view.minimap.set_texture(image)
        editor.level_view.minimap.corner1.x = coordinates[0]
        editor.level_view.minimap.corner1.z = coordinates[1]
        editor.level_view.minimap.corner2.x = coordinates[2]
        editor.level_view.minimap.corner2.z = coordinates[3]
        editor.level_view.minimap.orientation = orientation
        editor.level_view.do_redraw()

        # Sync widget states.
        outline_rasterization_mode_combined_pass_radiobutton.setEnabled(bool(outline))
        outline_rasterization_mode_separate_passes_radiobutton.setEnabled(bool(outline))
        outline_vertical_offset_slider.setEnabled(
            bool(outline) and outline_rasterization_mode_combined_pass_radiobutton.isChecked())
        terrain_colors_table.setVisible(color_mode_customcolors_radiobutton.isChecked())

    def reset():
        with blocked_signals(orientation_combobox):
            orientation_combobox.setCurrentIndex(minimap_generator.DEFAULT_ORIENTATION)
        with blocked_signals(margin_slider):
            margin_slider.set_value(minimap_generator.DEFAULT_MARGIN)
        with blocked_signals(outline_slider):
            outline_slider.set_value(minimap_generator.DEFAULT_OUTLINE)
        with blocked_signals(outline_rasterization_mode_separate_passes_radiobutton):
            with blocked_signals(outline_rasterization_mode_combined_pass_radiobutton):
                outline_rasterization_mode_separate_passes_radiobutton.setChecked(False)
                outline_rasterization_mode_combined_pass_radiobutton.setChecked(True)
        with blocked_signals(outline_vertical_offset_slider):
            outline_vertical_offset_slider.set_value(
                minimap_generator.DEFAULT_OUTLINE_VERTICAL_OFFSET)
        with blocked_signals(multisampling_combobox):
            multisampling_combobox.setCurrentIndex(minimap_generator.DEFAULT_MULTISAMPLING - 1)
        with blocked_signals(color_mode_blackwhite_radiobutton):
            with blocked_signals(color_mode_customcolors_radiobutton):
                color_mode_blackwhite_radiobutton.setChecked(True)
                color_mode_customcolors_radiobutton.setChecked(False)
        for terrain_type, visible, color in minimap_generator.DEFAULT_TERRAIN_COLORS:
            visible_checkbox, color_picker, color_picker_label = terrain_colors_widgets_map[
                terrain_type]
            with blocked_signals(visible_checkbox):
                visible_checkbox.setChecked(visible)
            with blocked_signals(color_picker):
                color_picker.color = QtGui.QColor(*color)
                color_picker.update_color(QtGui.QColor(*color))
                color_picker_label.setText('({}, {}, {})'.format(*color))

        update()

    # Restore state from settings.
    if "minimap_generator" not in editor.configuration:
        editor.configuration["minimap_generator"] = {}
    config = editor.configuration["minimap_generator"]
    if 'orientation' in config:
        orientation_combobox.setCurrentIndex(int(config['orientation']))
    if 'margin' in config:
        margin_slider.set_value(int(config['margin']))
    if 'outline' in config:
        outline_slider.set_value(int(config['outline']))
    if 'outline_rasterization_mode' in config:
        outline_rasterization_mode_separate_passes_radiobutton.setChecked(
            config['outline_rasterization_mode'] != 'combined_pass')
        outline_rasterization_mode_combined_pass_radiobutton.setChecked(
            config['outline_rasterization_mode'] == 'combined_pass')
    if 'outline_vertical_offset' in config:
        outline_vertical_offset_slider.set_value(int(config['outline_vertical_offset']))
    if 'multisampling' in config:
        multisampling_combobox.setCurrentIndex(int(config['multisampling']) - 1)
    if 'color_mode' in config:
        color_mode_blackwhite_radiobutton.setChecked(config['color_mode'] == 'black_and_white')
        color_mode_customcolors_radiobutton.setChecked(config['color_mode'] == 'custom_colors')
    if 'terrain_colors' in config:
        terrain_colors = json.loads(config['terrain_colors'])
        for terrain_type, (visible, color) in terrain_colors.items():
            terrain_type = int(terrain_type)
            if terrain_type in terrain_colors_widgets_map:
                visible_checkbox, color_picker, color_picker_label = terrain_colors_widgets_map[
                    terrain_type]
                visible_checkbox.setChecked(visible)
                color_picker.color = QtGui.QColor(*color)
                color_picker.update_color(QtGui.QColor(*color))
                color_picker_label.setText('({}, {}, {})'.format(*color))
    if "dialog_geometry" in config:
        dialog.restoreGeometry(
            QtCore.QByteArray.fromBase64(config["dialog_geometry"].encode(encoding='ascii')))

    # Connect slots.
    orientation_combobox.currentIndexChanged.connect(lambda _index: update())
    margin_slider.value_changed.connect(lambda _value: update())
    outline_slider.value_changed.connect(lambda _value: update())
    outline_rasterization_mode_combined_pass_radiobutton.toggled.connect(lambda checked: update()
                                                                         if checked else None)
    outline_rasterization_mode_separate_passes_radiobutton.toggled.connect(lambda checked: update()
                                                                           if checked else None)
    outline_vertical_offset_slider.value_changed.connect(lambda _value: update())
    multisampling_combobox.currentIndexChanged.connect(lambda _value: update())
    color_mode_blackwhite_radiobutton.toggled.connect(lambda checked: update() if checked else None)
    color_mode_customcolors_radiobutton.toggled.connect(lambda checked: update()
                                                        if checked else None)
    for visible_checkbox, color_picker, _color_picker_label in terrain_colors_widgets_map.values():
        visible_checkbox.stateChanged.connect(lambda _state: update())
        color_picker.color_changed.connect(update)
        color_picker.color_picked.connect(update)
    reset_button.clicked.connect(reset)

    update()

    dialog.exec_()

    # Save values in settings before returning.
    config['orientation'] = str(orientation_combobox.currentIndex())
    config['margin'] = str(margin_slider.get_value())
    config['outline'] = str(outline_slider.get_value())
    config['outline_rasterization_mode'] = (
        'combined_pass'
        if outline_rasterization_mode_combined_pass_radiobutton.isChecked() else 'separate_passes')
    config['outline_vertical_offset'] = str(outline_vertical_offset_slider.get_value())
    config['multisampling'] = str(multisampling_combobox.currentIndex() + 1)
    config['color_mode'] = ('black_and_white'
                            if color_mode_blackwhite_radiobutton.isChecked() else 'custom_colors')
    terrain_colors = {
        terrain_type:
        (visible_checkbox.isChecked(), (color_picker.color.red(), color_picker.color.green(),
                                        color_picker.color.blue()))
        for terrain_type, (visible_checkbox, color_picker,
                           _color_picker_label) in terrain_colors_widgets_map.items()
    }
    config['terrain_colors'] = json.dumps(terrain_colors)
    config["dialog_geometry"] = bytes(dialog.saveGeometry().toBase64()).decode(encoding='ascii')
    configuration.save_cfg(editor.configuration)

    dialog.deleteLater()
