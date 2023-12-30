import re

import widgets.tooltip_list as ttl

from PySide6 import QtCore, QtGui, QtWidgets

from collections import OrderedDict
from math import inf
from lib.libbol import (EnemyPoint, EnemyPointGroup, CheckpointGroup, Checkpoint, Route, RoutePoint,
                        MapObject, KartStartPoint, Area, Camera, BOL, JugemPoint, MapObject,
                        LightParam, MGEntry, PositionedObject, OBJECTNAMES, REVERSEOBJECTNAMES, MUSIC_IDS, REVERSE_MUSIC_IDS,
                        SWERVE_IDS, REVERSE_SWERVE_IDS, REVERSE_AREA_TYPES,
                        KART_START_POINTS_PLAYER_IDS, REVERSE_KART_START_POINTS_PLAYER_IDS,
                        read_object_parameters, all_same_type, get_average_obj)
from lib.vectors import Vector3
from lib.model_rendering import Minimap


def load_parameter_names(objectname):
    try:
        data = read_object_parameters(objectname)

        parameter_names = data["Object Parameters"]

        if len(parameter_names) != 8:
            raise RuntimeError("Not enough or too many parameters: {0} (should be 8)".format(
                len(parameter_names)))

        assets = data["Assets"]

        tooltips = data.get("Tooltips", [])
        tooltips += [''] * (8 - len(tooltips))

        tooltips = [
            ttl.markdown_to_html(re.sub(r'[^\x00-\x7f]', r'', parameter_name).strip(), tool_tip)
            if tool_tip else '' for parameter_name, tool_tip in zip(parameter_names, tooltips)
        ]

        widget_types = data.get("Widgets", [])
        widget_types += [None] * (8 - len(widget_types))

        return tuple(parameter_names), tuple(assets), tuple(tooltips), tuple(widget_types)

    except Exception:
        return (
            tuple(f'Obj Data {i + 1}' for i in range(8)),
            tuple(),
            tuple([''] * 8),
            tuple([None] * 8),
        )


def clear_layout(layout):
    while layout.count():
        child = layout.itemAt(0)
        if child.widget():
            child.widget().deleteLater()
        if child.layout():
            clear_layout(child.layout())
            child.layout().deleteLater()
        layout.takeAt(0)


def find_parent_layout(widget_or_layout) -> QtWidgets.QLayout:
    """
    Finds the parent layout of the given widget or layout.
    """
    parent_widget = widget_or_layout.parentWidget()
    if parent_widget is None:
        return None

    for layout in parent_widget.findChildren(QtWidgets.QLayout):
        for i in range(layout.count()):
            layout_item = layout.itemAt(i)
            if layout_item.widget() is widget_or_layout or layout_item.layout() is widget_or_layout:
                return layout

    return None


def set_tool_tip(widget: QtWidgets.QWidget, tool_tip: str):
    """
    Sets the tool tip in the given widget, but also in all siblings of the widget.
    """
    parent_layout = find_parent_layout(widget)
    if parent_layout is not None:
        for i in range(parent_layout.count()):
            layout_item = parent_layout.itemAt(i)
            layout_item_widget = layout_item.widget()
            if layout_item_widget is not None:
                layout_item_widget.setToolTip(tool_tip)
    else:
        widget.setToolTip(tool_tip)


class MaskBoxMenu(QtWidgets.QMenu):

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        action = self.activeAction()
        if action is not None and action.isEnabled():
            action.trigger()
            event.accept()
            return

        super().mouseReleaseEvent(event)


class MaskBox(QtWidgets.QPushButton):

    value_changed = QtCore.Signal(int)

    def __init__(self, entries: 'dict[int, (str, str)]'):
        super().__init__()

        policy = self.sizePolicy()
        policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Expanding)
        self.setSizePolicy(policy)

        self.entries = entries
        self.actions = {}

        self.menu = MaskBoxMenu()
        for field, (char, label) in entries.items():
            action = self.menu.addAction(f'{char} {label}')
            action.setCheckable(True)
            action.toggled.connect(self._on_action_toggled)
            self.actions[field] = action

        self.setMenu(self.menu)

    def set_value(self, value: int):
        for field, action in self.actions.items():
            with QtCore.QSignalBlocker(action):
                action.setChecked(bool(field & value))

        button_label = ''
        for field, (char, _label) in self.entries.items():
            if field & value:
                if button_label:
                    button_label += ' '
                button_label += char
        self.setText(button_label)

    def _on_action_toggled(self, checked: bool):
        _ = checked
        value = 0
        for field, action in self.actions.items():
            if action.isChecked():
                value |= field

        self.set_value(value)
        self.value_changed.emit(value)


class SpinBox(QtWidgets.QSpinBox):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        policy = self.sizePolicy()
        policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Expanding)
        self.setSizePolicy(policy)

    def setValueQuiet(self, value: int):
        with QtCore.QSignalBlocker(self):
            self.setValue(value)


class DoubleSpinBox(QtWidgets.QDoubleSpinBox):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        policy = self.sizePolicy()
        policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Expanding)
        self.setSizePolicy(policy)

        self.setDecimals(4)

    def setValueQuiet(self, value: float):
        with QtCore.QSignalBlocker(self):
            self.setValue(value)


class ClickableLabel(QtWidgets.QLabel):

    clicked = QtCore.Signal()

    def mouseReleaseEvent(self, event):

        if self.rect().contains(event.position().toPoint()):
            event.accept()
            self.clicked.emit()


class ColorPicker(ClickableLabel):

    color_changed = QtCore.Signal(QtGui.QColor)
    color_picked = QtCore.Signal(QtGui.QColor)

    def __init__(self, with_alpha=False):
        super().__init__()

        height = int(self.fontMetrics().height() / 1.5)
        pixmap = QtGui.QPixmap(height, height)
        pixmap.fill(QtCore.Qt.black)
        self.setPixmap(pixmap)
        self.setFixedWidth(height)

        self.color = QtGui.QColor(0, 0, 0, 0)
        self.with_alpha = with_alpha
        self.tmp_color = QtGui.QColor(0, 0, 0, 0)

        self.clicked.connect(self.show_color_dialog)

    def show_color_dialog(self):
        dialog = QtWidgets.QColorDialog(self)
        dialog.setOption(QtWidgets.QColorDialog.DontUseNativeDialog, True)
        if self.with_alpha:
            dialog.setOption(QtWidgets.QColorDialog.ShowAlphaChannel, True)
        dialog.setCurrentColor(self.color)
        dialog.currentColorChanged.connect(self.update_color)
        dialog.currentColorChanged.connect(self.color_changed)

        color = self.color

        accepted = dialog.exec()
        if accepted:
            self.color = dialog.currentColor()
            self.color_picked.emit(self.color)
        else:
            self.color = color
            self.update_color(self.color)
            self.color_changed.emit(self.color)

    def update_color(self, color):
        self.tmp_color = color
        color = QtGui.QColor(color)
        color.setAlpha(255)
        pixmap = self.pixmap()
        pixmap.fill(color)
        self.setPixmap(pixmap)


class DataEditor(QtWidgets.QWidget):
    emit_3d_update = QtCore.Signal()

    def __init__(self, parent, bol, bound_to):
        super().__init__(parent)

        self.bol = bol
        self.bound_to = bound_to
        self.vbox = QtWidgets.QVBoxLayout(self)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(3)

        self.setup_widgets()

    def catch_text_update(self):
        self.emit_3d_update.emit()

    def setup_widgets(self):
        pass

    def update_data(self):
        pass

    def get_bol_editor(self):
        for window in QtWidgets.QApplication.topLevelWidgets():
            if 'GenEditor' in str(type(window)):
                return window
        return None

    def create_label(self, text):
        label = QtWidgets.QLabel(self)
        label.setText(text)
        return label

    def add_label(self, text):
        label = self.create_label(text)
        self.vbox.addWidget(label)
        return label

    def create_labeled_widget(self, parent, text, widget):
        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(5)
        label = self.create_label(text)
        label.setText(text)
        layout.addWidget(label)
        layout.addWidget(widget)
        return layout

    def create_labeled_widgets(self, parent, text, widgetlist):
        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(5)
        label = self.create_label(text)
        label.setText(text)
        layout.addWidget(label)
        if len(widgetlist) > 1:
            child_layout = QtWidgets.QHBoxLayout()
            child_layout.setSpacing(1)
            child_layout.setContentsMargins(0, 0, 0, 0)
            for widget in widgetlist:
                child_layout.addWidget(widget)
            layout.addLayout(child_layout)
        elif widgetlist:
            layout.addWidget(widgetlist[0])
        return layout

    def add_checkbox(self, text, attribute, off_value, on_value):
        checkbox = QtWidgets.QCheckBox(self)
        layout = self.create_labeled_widget(self, text, checkbox)

        def checked(state):
            for obj in self.bound_to:
                setattr(obj, attribute, off_value if state == 0 else on_value)

        checkbox.stateChanged.connect(checked)
        self.vbox.addLayout(layout)

        return checkbox

    def add_maskbox(self, text, attribute, entries):
        maskbox = MaskBox(entries)
        layout = self.create_labeled_widget(self, text, maskbox)

        def on_value_changed(value: int):
            for obj in self.bound_to:
                setattr(obj, attribute, value)

        maskbox.value_changed.connect(on_value_changed)
        self.vbox.addLayout(layout)

        return maskbox

    def add_integer_input(self, text, attribute, min_val, max_val):
        spinbox = SpinBox(self)
        spinbox.setRange(min_val, max_val)

        def on_spinbox_valueChanged(value):
            for obj in self.bound_to:
                setattr(obj, attribute, value)

        spinbox.valueChanged.connect(on_spinbox_valueChanged)

        layout = self.create_labeled_widget(self, text, spinbox)
        self.vbox.addLayout(layout)

        spinbox.setProperty('parent_layout', layout)

        return spinbox

    def add_decimal_input(self, text, attribute, min_val, max_val):
        spinbox = DoubleSpinBox(self)
        spinbox.setRange(min_val, max_val)

        def on_spinbox_valueChanged(value):
            self.catch_text_update()
            for obj in self.bound_to:
                setattr(obj, attribute, value)

        spinbox.valueChanged.connect(on_spinbox_valueChanged)

        layout = self.create_labeled_widget(self, text, spinbox)
        self.vbox.addLayout(layout)

        return spinbox

    def add_text_input(self, text, attribute, maxlength):
        line_edit = QtWidgets.QLineEdit(self)
        layout = self.create_labeled_widget(self, text, line_edit)

        line_edit.setMaxLength(maxlength)

        def input_edited():
            text = line_edit.text()
            text = text.rjust(maxlength)
            for obj in self.bound_to:
                setattr(obj, attribute, text)

        line_edit.editingFinished.connect(input_edited)
        self.vbox.addLayout(layout)

        return line_edit

    def add_dropdown_input(self, text, attribute, keyval_dict):
        combobox = QtWidgets.QComboBox(self)
        for val in keyval_dict:
            combobox.addItem(val)

        policy = combobox.sizePolicy()
        policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Expanding)
        combobox.setSizePolicy(policy)
        combobox.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)

        layout = self.create_labeled_widget(self, text, combobox)

        def item_selected(item):
            val = keyval_dict[item]
            for obj in self.bound_to:
                setattr(obj, attribute, val)

            tt_dict = getattr(ttl, attribute, {})
            if tt_dict:
                combobox.setToolTip(tt_dict.get(item, ''))

        combobox.currentTextChanged.connect(item_selected)
        self.vbox.addLayout(layout)

        return combobox

    def add_button_input(self, labeltext, text, function):
        button = QtWidgets.QPushButton(self)
        button.setText(text)
        button.clicked.connect(function)

        policy = button.sizePolicy()
        policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Expanding)
        button.setSizePolicy(policy)

        layout = self.create_labeled_widget(self, labeltext, button)
        self.vbox.addLayout(layout)
        return layout

    def add_color_input(self, text, attribute, with_alpha=False):
        spinboxes = []
        input_edited_callbacks = []

        for subattr in ["r", "g", "b", "a"] if with_alpha else ["r", "g", "b"]:
            spinbox = SpinBox(self)
            spinbox.setMaximumWidth(self.fontMetrics().averageCharWidth() * 4)
            spinbox.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
            spinbox.setRange(0, 255)
            input_edited = create_setter(self.bound_to,
                                         attribute,
                                         subattr,
                                         self.catch_text_update)
            input_edited_callbacks.append(input_edited)
            spinbox.valueChanged.connect(input_edited)
            spinboxes.append(spinbox)

        color_picker = ColorPicker(with_alpha=with_alpha)

        def on_spinbox_valueChanged(value: int):
            _ = value
            r = spinboxes[0].value()
            g = spinboxes[1].value()
            b = spinboxes[2].value()
            a = spinboxes[3].value() if len(spinboxes) == 4 else 255
            color_picker.color = QtGui.QColor(r, g, b, a)
            color_picker.update_color(color_picker.color)

        for spinbox in spinboxes:
            spinbox.valueChanged.connect(on_spinbox_valueChanged)

        def on_color_changed(color):
            spinboxes[0].setValue(color.red())
            spinboxes[1].setValue(color.green())
            spinboxes[2].setValue(color.blue())
            if len(spinboxes) == 4:
                spinboxes[3].setValue(color.alpha())

        def on_color_picked(color):
            values = [color.red(), color.green(), color.blue()]
            if len(spinboxes) == 4:
                values.append(color.alpha())
            for callback, value in zip(input_edited_callbacks, values):
                callback(value)

        color_picker.color_changed.connect(on_color_changed)
        color_picker.color_picked.connect(on_color_picked)

        layout = self.create_labeled_widgets(self, text, spinboxes + [color_picker])
        self.vbox.addLayout(layout)

        return spinboxes

    def add_multiple_integer_input(self, text, attribute, subattributes, min_val, max_val):
        spinboxes = []
        for subattr in subattributes:
            spinbox = SpinBox(self)
            if max_val <= MAX_UNSIGNED_BYTE:
                spinbox.setMaximumWidth(self.fontMetrics().averageCharWidth() * 4)
            spinbox.setRange(min_val, max_val)
            input_edited = create_setter(self.bound_to,
                                         attribute,
                                         subattr,
                                         self.catch_text_update)
            spinbox.valueChanged.connect(input_edited)
            spinboxes.append(spinbox)

        layout = self.create_labeled_widgets(self, text, spinboxes)
        self.vbox.addLayout(layout)

        return spinboxes

    def add_multiple_decimal_input(self, text, attribute, subattributes, min_val, max_val):
        spinboxes = []
        for subattr in subattributes:
            spinbox = DoubleSpinBox(self)
            if text in ('Position', 'Start', 'Light Position', 'Start Point', 'End Point'):
                # Some fields can naturally get a greater step; no point in increasing position
                # components by one unit in MKDD.
                spinbox.setSingleStep(10)
            spinbox.setRange(min_val, max_val)
            input_edited = create_setter(self.bound_to,
                                         attribute,
                                         subattr,
                                         self.catch_text_update)
            spinbox.valueChanged.connect(input_edited)
            spinboxes.append(spinbox)

        layout = self.create_labeled_widgets(self, text, spinboxes)
        self.vbox.addLayout(layout)

        return spinboxes

    def add_multiple_integer_input_list(self, text, attribute, min_val, max_val):
        spinboxes = []
        obj = get_average_obj(self.bound_to)
        fieldlist = getattr(obj, attribute)
        for i in range(len(fieldlist)):
            spinbox = SpinBox(self)
            spinbox.setMaximumWidth(self.fontMetrics().averageCharWidth() * 4)
            spinbox.setRange(min_val, max_val)
            input_edited = create_setter_list(self.bound_to, attribute, i)
            spinbox.valueChanged.connect(input_edited)
            spinboxes.append(spinbox)

        layout = self.create_labeled_widgets(self, text, spinboxes)
        self.vbox.addLayout(layout)

        return spinboxes

    def add_types_widget_index(self, layout, text, attribute, index, widget_type):
        # Certain widget types will be accompanied with arguments.
        if isinstance(widget_type, (list, tuple)):
            widget_type, *widget_type_args = widget_type

        def set_value(value, index=index):
            for obj in self.bound_to:
                getattr(obj, attribute)[index] = value

        if widget_type == "checkbox":
            widget = QtWidgets.QCheckBox()
            widget.stateChanged.connect(lambda state: set_value(int(bool(state))))
        elif widget_type == "combobox":
            widget = QtWidgets.QComboBox()
            policy = widget.sizePolicy()
            policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Expanding)
            widget.setSizePolicy(policy)
            widget.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
            for key, value in widget_type_args[0].items():
                widget.addItem(key, value)
            widget.currentIndexChanged.connect(
                lambda index: set_value(widget.itemData(index)))
        else:
            widget = QtWidgets.QSpinBox()
            policy = widget.sizePolicy()
            policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Expanding)
            widget.setSizePolicy(policy)
            widget.setRange(MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
            widget.valueChanged.connect(set_value)

        layout.addLayout(self.create_labeled_widget(None, text, widget))

        return widget

    def update_rotation(self, forwardedits, upedits, leftedits):
        rotation = get_average_obj(self.bound_to).rotation
        forward, up, left = rotation.get_vectors()

        for attr in ("x", "y", "z"):
            if getattr(forward, attr) == 0.0:
                setattr(forward, attr, 0.0)

        for attr in ("x", "y", "z"):
            if getattr(up, attr) == 0.0:
                setattr(up, attr, 0.0)

        for attr in ("x", "y", "z"):
            if getattr(left, attr) == 0.0:
                setattr(left, attr, 0.0)

        forwardedits[0].setValueQuiet(forward.x)
        forwardedits[1].setValueQuiet(forward.y)
        forwardedits[2].setValueQuiet(forward.z)

        upedits[0].setValueQuiet(up.x)
        upedits[1].setValueQuiet(up.y)
        upedits[2].setValueQuiet(up.z)

        leftedits[0].setValueQuiet(left.x)
        leftedits[1].setValueQuiet(left.y)
        leftedits[2].setValueQuiet(left.z)

        self.catch_text_update()

    def add_rotation_input(self):
        rotation = get_average_obj(self.bound_to).rotation
        forward_spinboxes = []
        up_spinboxes = []
        left_spinboxes = []

        for spinboxes in (forward_spinboxes, up_spinboxes, left_spinboxes):
            for attr in ("x", "y", "z"):
                spinbox = DoubleSpinBox(self)
                spinbox.setDecimals(4)
                spinbox.setRange(-1.0, 1.0)
                spinboxes.append(spinbox)

        def change_forward():
            forward, up, left = rotation.get_vectors()

            newforward = Vector3(*[v.value() for v in forward_spinboxes])
            if newforward.norm() == 0.0:
                newforward = left.cross(up)
            newforward.normalize()
            up = newforward.cross(left)
            up.normalize()
            left = up.cross(newforward)
            left.normalize()

            rotation.set_vectors(newforward, up, left)
            self.update_rotation(forward_spinboxes, up_spinboxes, left_spinboxes)

        def change_up():
            forward, up, left = rotation.get_vectors()
            newup = Vector3(*[v.value() for v in up_spinboxes])
            if newup.norm() == 0.0:
                newup = forward.cross(left)
            newup.normalize()
            forward = left.cross(newup)
            forward.normalize()
            left = newup.cross(forward)
            left.normalize()

            rotation.set_vectors(forward, newup, left)
            self.update_rotation(forward_spinboxes, up_spinboxes, left_spinboxes)

        def change_left():
            forward, up, left = rotation.get_vectors()

            newleft = Vector3(*[v.value() for v in left_spinboxes])
            if newleft.norm() == 0.0:
                newleft = up.cross(forward)
            newleft.normalize()
            forward = newleft.cross(up)
            forward.normalize()
            up = forward.cross(newleft)
            up.normalize()

            rotation.set_vectors(forward, up, newleft)
            self.update_rotation(forward_spinboxes, up_spinboxes, left_spinboxes)

        for edit in forward_spinboxes:
            edit.valueChanged.connect(lambda _value: change_forward())
        for edit in up_spinboxes:
            edit.valueChanged.connect(lambda _value: change_up())
        for edit in left_spinboxes:
            edit.valueChanged.connect(lambda _value: change_left())

        layout = self.create_labeled_widgets(self, "Forward dir", forward_spinboxes)
        self.vbox.addLayout(layout)
        layout = self.create_labeled_widgets(self, "Up dir", up_spinboxes)
        self.vbox.addLayout(layout)
        layout = self.create_labeled_widgets(self, "Left dir", left_spinboxes)
        self.vbox.addLayout(layout)
        return forward_spinboxes, up_spinboxes, left_spinboxes


def create_setter_list(bound_to, attribute, index):

    def on_spinbox_valueChanged(value):
        for bound_to_object in bound_to:
            mainattr = getattr(bound_to_object, attribute)
            mainattr[index] = value

    return on_spinbox_valueChanged


def create_setter(bound_to, attribute, subattr, update3dview):

    def on_spinbox_valueChanged(value):
        for bound_to_object in bound_to:
            mainattr = getattr(bound_to_object, attribute)
            setattr(mainattr, subattr, value)
        update3dview()

    return on_spinbox_valueChanged


MIN_SIGNED_BYTE = -128
MAX_SIGNED_BYTE = 127
MIN_SIGNED_SHORT = -2**15
MAX_SIGNED_SHORT = 2**15 - 1
MIN_SIGNED_INT = -2**31
MAX_SIGNED_INT = 2**31 - 1

MIN_UNSIGNED_BYTE = MIN_UNSIGNED_SHORT = MIN_UNSIGNED_INT = 0
MAX_UNSIGNED_BYTE = 255
MAX_UNSIGNED_SHORT = 2**16 - 1
MAX_UNSIGNED_INT = 2**32 - 1


def choose_data_editor(objs):
    if not objs:
        return None
    if not all_same_type(objs):
        if all(isinstance(obj, PositionedObject) for obj in objs):
            return PositionedEdit
        return None

    obj = objs[0]
    if isinstance(obj, EnemyPoint):
        return EnemyPointEdit
    elif isinstance(obj, EnemyPointGroup):
        return EnemyPointGroupEdit
    elif isinstance(obj, CheckpointGroup):
        return CheckpointGroupEdit
    elif isinstance(obj, MapObject):
        return ObjectEdit
    elif isinstance(obj, Checkpoint):
        return CheckpointEdit
    elif isinstance(obj, Route):
        return ObjectRouteEdit
    elif isinstance(obj, RoutePoint):
        return ObjectRoutePointEdit
    elif isinstance(obj, BOL):
        return BOLEdit
    elif isinstance(obj, KartStartPoint):
        return KartStartPointEdit
    elif isinstance(obj, Area):
        return AreaEdit
    elif isinstance(obj, Camera):
        return CameraEdit
    elif isinstance(obj, JugemPoint):
        return RespawnPointEdit
    elif isinstance(obj, LightParam):
        return LightParamEdit
    elif isinstance(obj, MGEntry):
        return MGEntryEdit
    elif isinstance(obj, Minimap):
        return MinimapEdit
    else:
        return None


class EnemyPointGroupEdit(DataEditor):
    def setup_widgets(self):
        if len(self.bound_to) == 1:
            self.groupid = self.add_integer_input("Group ID", "id", MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)

    def update_data(self):
        if len(self.bound_to) == 1:
            self.groupid.setValueQuiet(self.bound_to[0].id)


DRIFT_DIRECTION_OPTIONS = OrderedDict()
DRIFT_DIRECTION_OPTIONS[""] = 0
DRIFT_DIRECTION_OPTIONS["To the left"] = 1
DRIFT_DIRECTION_OPTIONS["To the right"] = 2


class EnemyPointEdit(DataEditor):
    def setup_widgets(self, group_editable=False):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.link = self.add_integer_input("Link", "link",
                                           MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        set_tool_tip(self.link, ttl.enemypoints['Link'])
        self.scale = self.add_decimal_input("Scale", "scale", -inf, inf)
        set_tool_tip(self.scale, ttl.enemypoints['Scale'])
        self.itemsonly = self.add_checkbox("Items Only", "itemsonly", off_value=0, on_value=1)
        set_tool_tip(self.itemsonly, ttl.enemypoints['Items Only'])
        self.swerve = self.add_dropdown_input("Swerve", "swerve", REVERSE_SWERVE_IDS)
        self.group = self.add_integer_input("Group", "group",
                                            MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        if not group_editable:
            self.group.setDisabled(True)

        self.driftdirection = self.add_dropdown_input("Drift Direction", "driftdirection",
                                                      DRIFT_DIRECTION_OPTIONS)
        self.driftacuteness = self.add_integer_input("Drift Acuteness", "driftacuteness",
                                                     MIN_UNSIGNED_BYTE, 250)
        set_tool_tip(self.driftacuteness, ttl.enemypoints['Drift Acuteness'])
        self.driftduration = self.add_integer_input("Drift Duration", "driftduration",
                                                    MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        set_tool_tip(self.driftduration, ttl.enemypoints['Drift Duration'])
        self.driftsupplement = self.add_integer_input("Drift Supplement", "driftsupplement",
                                                      MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        set_tool_tip(self.driftsupplement, ttl.enemypoints['Drift Supplement'])
        self.nomushroomzone = self.add_checkbox("No Mushroom Zone", "nomushroomzone",
                                                off_value=0, on_value=1)
        set_tool_tip(self.nomushroomzone, ttl.enemypoints['No Mushroom Zone'])

        for widget in self.position:
            widget.valueChanged.connect(lambda _value: self.catch_text_update())
        for widget in (self.itemsonly, self.nomushroomzone):
            widget.stateChanged.connect(lambda _state: self.catch_text_update())
        for widget in (self.swerve, self.driftdirection):
            widget.currentIndexChanged.connect(lambda _index: self.catch_text_update())
        for widget in (self.link, self.driftacuteness, self.driftduration, self.driftsupplement):
            widget.valueChanged.connect(lambda _value: self.catch_text_update())

        self.link.valueChanged.connect(lambda _value: self.update_name())

    def update_data(self):
        obj: EnemyPoint = get_average_obj(self.bound_to)
        self.position[0].setValueQuiet(obj.position.x)
        self.position[1].setValueQuiet(obj.position.y)
        self.position[2].setValueQuiet(obj.position.z)
        self.driftdirection.setCurrentIndex(obj.driftdirection)
        set_tool_tip(self.driftdirection, ttl.enemypoints['Drift Direction'])
        self.link.setValueQuiet(obj.link)
        self.scale.setValueQuiet(obj.scale)
        self.itemsonly.setChecked(bool(obj.itemsonly))
        self.group.setValueQuiet(obj.group)
        self.driftacuteness.setValueQuiet(obj.driftacuteness)
        self.driftduration.setValueQuiet(obj.driftduration)
        self.driftsupplement.setValueQuiet(obj.driftsupplement)
        self.nomushroomzone.setChecked(bool(obj.nomushroomzone))

        if obj.swerve in SWERVE_IDS:
            name = SWERVE_IDS[obj.swerve]
        else:
            name = SWERVE_IDS[0]
        index = self.swerve.findText(name)
        self.swerve.setCurrentIndex(index)
        set_tool_tip(self.swerve, ttl.enemypoints['Swerve'])

    def update_name(self):
        for obj in self.bound_to:
            if obj.widget is None:
                continue
            obj.widget.update_name()


class CheckpointGroupEdit(DataEditor):
    def setup_widgets(self):
        if len(self.bound_to) != 1:
            return
        self.grouplink = self.add_integer_input("Group Setting", "grouplink",
                                                MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        self.prevgroup = self.add_multiple_integer_input_list("Previous Groups", "prevgroup",
                                                              MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.nextgroup = self.add_multiple_integer_input_list("Next Groups", "nextgroup",
                                                              MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)

    def update_data(self):
        if len(self.bound_to) != 1:
            return
        obj = self.bound_to[0]
        self.grouplink.setValueQuiet(obj.grouplink)
        for i, widget in enumerate(self.prevgroup):
            widget.setValueQuiet(obj.prevgroup[i])
        for i, widget in enumerate(self.nextgroup):
            widget.setValueQuiet(obj.nextgroup[i])


class CheckpointEdit(DataEditor):
    def setup_widgets(self):
        self.start = self.add_multiple_decimal_input("Start", "start", ["x", "y", "z"],
                                                        -inf, +inf)
        self.end = self.add_multiple_decimal_input("End", "end", ["x", "y", "z"],
                                                     -inf, +inf)

        self.unk1 = self.add_integer_input("Shortcut Point ID", "unk1",
                                           MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        set_tool_tip(self.unk1, ttl.checkpoints["Shortcut Point ID"])
        self.unk3 = self.add_checkbox("Double-sided", "unk3", 0, 1)
        set_tool_tip(self.unk3, ttl.checkpoints["Double-sided"])

        if self.get_bol_editor().show_code_patch_fields_action.isChecked():
            self.unk4 = self.add_checkbox("Lap Checkpoint 🧩", "unk4", 0, 1)
            self.unk4.toggled.connect(self.catch_text_update)
            set_tool_tip(self.unk4, ttl.checkpoints["Lap Checkpoint"])

    def update_data(self):
        obj: Checkpoint = get_average_obj(self.bound_to)
        self.start[0].setValueQuiet(obj.start.x)
        self.start[1].setValueQuiet(obj.start.y)
        self.start[2].setValueQuiet(obj.start.z)

        self.end[0].setValueQuiet(obj.end.x)
        self.end[1].setValueQuiet(obj.end.y)
        self.end[2].setValueQuiet(obj.end.z)

        self.unk1.setValueQuiet(obj.unk1)
        self.unk3.setChecked(obj.unk3 != 0)

        if self.get_bol_editor().show_code_patch_fields_action.isChecked():
            self.unk4.setChecked(obj.unk4 != 0)


class ObjectRouteEdit(DataEditor):
    def setup_widgets(self):
        self.unk1 = self.add_checkbox("Unknown 1", "unk1", 0, 1)

    def update_data(self):
        obj: Route = get_average_obj(self.bound_to)
        self.unk1.setChecked(bool(obj.unk1))


class ObjectRoutePointEdit(DataEditor):
    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.unknown = self.add_integer_input("Object Action", "unk",
                                              MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)

    def update_data(self):
        obj: RoutePoint = get_average_obj(self.bound_to)
        self.position[0].setValueQuiet(obj.position.x)
        self.position[1].setValueQuiet(obj.position.y)
        self.position[2].setValueQuiet(obj.position.z)
        self.unknown.setValueQuiet(obj.unk)


ROLL_OPTIONS = OrderedDict()
ROLL_OPTIONS["Disabled"] = 0
ROLL_OPTIONS["Only Sky+Items"] = 1
ROLL_OPTIONS["Entire Track"] = 2


class BOLEdit(DataEditor):
    def setup_widgets(self):
        self.roll = self.add_dropdown_input("Tilt", "roll", ROLL_OPTIONS)
        self.rgb_ambient = self.add_color_input("RGB Ambient", "rgb_ambient")
        self.rgba_light = self.add_color_input("RGBA Light", "rgba_light", with_alpha=True)
        self.lightsource = self.add_multiple_decimal_input("Light Position", "lightsource", ["x", "y", "z"],
                                                           -inf, +inf)
        self.lap_count = self.add_integer_input("Lap Count", "lap_count",
                                                MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)

        self.music_id = self.add_dropdown_input("Music ID", "music_id",
                                                REVERSE_MUSIC_IDS)
        self.fog_type = self.add_integer_input("Fog Type", "fog_type",
                                               MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        self.fog_color = self.add_color_input("Fog Color", "fog_color")
        self.fog_startz = self.add_decimal_input("Fog Near Z", "fog_startz",
                                                 -inf, +inf)
        self.fog_endz = self.add_decimal_input("Fog Far Z", "fog_endz",
                                               -inf, +inf)
        self.lod_bias = self.add_checkbox("LOD Bias", "lod_bias", off_value=0, on_value=1)
        self.dummy_start_line = self.add_checkbox("Dummy Start Line", "dummy_start_line",
                                                  off_value=0, on_value=1)
        self.snow_effects = self.add_checkbox("Sherbet Land Env. Effects", "snow_effects",
                                              off_value=0, on_value=1)
        self.shadow_opacity = self.add_integer_input("Shadow Opacity", "shadow_opacity",
                                                     MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        self.shadow_color = self.add_color_input("Shadow Color", "shadow_color")
        self.sky_follow = self.add_checkbox("Sky Follow", "sky_follow", off_value=0, on_value=1)

    def update_data(self):
        obj: BOL = get_average_obj(self.bound_to)
        self.roll.setCurrentIndex(obj.roll)
        self.rgb_ambient[0].setValue(obj.rgb_ambient.r)
        self.rgb_ambient[1].setValue(obj.rgb_ambient.g)
        self.rgb_ambient[2].setValue(obj.rgb_ambient.b)
        self.rgba_light[0].setValue(obj.rgba_light.r)
        self.rgba_light[1].setValue(obj.rgba_light.g)
        self.rgba_light[2].setValue(obj.rgba_light.b)
        self.rgba_light[3].setValue(obj.rgba_light.a)
        self.lightsource[0].setValueQuiet(obj.lightsource.x)
        self.lightsource[1].setValueQuiet(obj.lightsource.y)
        self.lightsource[2].setValueQuiet(obj.lightsource.z)
        self.lap_count.setValueQuiet(obj.lap_count)
        self.fog_type.setValueQuiet(obj.fog_type)
        self.fog_color[0].setValue(obj.fog_color.r)
        self.fog_color[1].setValue(obj.fog_color.g)
        self.fog_color[2].setValue(obj.fog_color.b)
        self.fog_startz.setValueQuiet(obj.fog_startz)
        self.fog_endz.setValueQuiet(obj.fog_endz)
        self.lod_bias.setChecked(obj.lod_bias != 0)
        self.dummy_start_line.setChecked(obj.dummy_start_line != 0)
        self.snow_effects.setChecked(obj.snow_effects != 0)
        self.shadow_opacity.setValueQuiet(obj.shadow_opacity)
        self.sky_follow.setChecked(obj.sky_follow != 0)
        self.shadow_color[0].setValue(obj.shadow_color.r)
        self.shadow_color[1].setValue(obj.shadow_color.g)
        self.shadow_color[2].setValue(obj.shadow_color.b)

        if obj.music_id not in MUSIC_IDS:
            name = "INVALID"
        else:
            name = MUSIC_IDS[obj.music_id]
        index = self.music_id.findText(name)
        self.music_id.setCurrentIndex(index)


class ObjectEdit(DataEditor):
    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.scale = self.add_multiple_decimal_input("Scale", "scale", ["x", "y", "z"],
                                                    -inf, +inf)
        for spinbox in self.scale:
            spinbox.setSingleStep(0.1)
        self.rotation = self.add_rotation_input()
        self.objectid = self.add_dropdown_input("Object Type", "objectid", REVERSEOBJECTNAMES)
        self.prev_objectname = None

        #self.pathid = self.add_integer_input("Route ID", "pathid",
        #                                     MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        #set_tool_tip(self.pathid, ttl.objectdata['Route ID'])
        #self.pathid.valueChanged.connect(lambda _value: self.catch_text_update())

        routes = OrderedDict()
        routes["None"] = None
        for i, route in enumerate(self.bol.routes):
            routes["Route {0}".format(i)] = route

        self.route = self.add_dropdown_input("Route", "route", routes)
        self.route.currentIndexChanged.connect(self.catch_text_update)
        set_tool_tip(self.route, ttl.objectdata['Route ID'])

        self.unk_2a = self.add_integer_input("Route Point ID", "unk_2a",
                                             MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        set_tool_tip(self.unk_2a, ttl.objectdata['Route Point ID'])

        self.presence_filter = self.add_maskbox(
            "Game Mode Presence", "presence_filter", {
                0b00000001: ('🎈', 'Balloon Battle'),
                0b00000010: ('💰', 'Robbery (Yanked)'),
                0b00000100: ('💣', 'Bob-omb Blast'),
                0b00001000: ('🌟', 'Shine Thief'),
                0b10000000: ('⏱️', 'Time Trials'),
            })
        set_tool_tip(self.presence_filter, ttl.objectdata['Game Mode Presence'])

        self.presence = self.add_maskbox("Player Mode Presence", "presence", {
            0b01: ('👤', 'Single Player'),
            0b10: ('👥', 'Multi Player'),
        })
        set_tool_tip(self.presence, ttl.objectdata['Player Mode Presence'])

        self.flag = self.add_checkbox("Collision", "unk_flag",
                                      off_value=0, on_value=1)
        set_tool_tip(self.flag, ttl.objectdata['Collision'])

        self.objdata_reset_button_layout = self.add_button_input(
            "Object-Specific Settings", "Reset to Default", self.fill_default_values)

        self.userdata = [None] * 8
        self.userdata_layout = QtWidgets.QVBoxLayout()
        self.vbox.addLayout(self.userdata_layout)

        self.objectid.currentTextChanged.connect(self.update_name)

        for widget in self.position:
            widget.valueChanged.connect(lambda _value: self.catch_text_update())

        self.objectid.currentTextChanged.connect(self.rebuild_object_parameters_widgets)

        self.assets = QtWidgets.QLineEdit()
        self.assets.setReadOnly(True)
        self.vbox.addLayout(self.create_labeled_widget(self, 'Assets', self.assets))

    def rebuild_object_parameters_widgets(self, objectname):
        if self.prev_objectname == objectname:
            return
        self.prev_objectname = objectname

        for i in range(8):
            self.userdata[i] = None
        clear_layout(self.userdata_layout)

        show_code_patch_fields = self.get_bol_editor().show_code_patch_fields_action.isChecked()

        parameter_names, assets, tooltips, widget_types = load_parameter_names(objectname)
        tuples = zip(parameter_names, tooltips, widget_types)
        cmn_obj = get_average_obj(self.bound_to)

        for i, (parameter_name, tooltip, widget_type) in enumerate(tuples):
            if '🧩' in parameter_name and not show_code_patch_fields:
                continue
            if parameter_name == "Unused":
                if cmn_obj.userdata[i] != 0:
                    print(f"Warning: Parameter with index {i} in object {objectname} is marked as "
                          f"unused but has value {cmn_obj.userdata[i]}.")
                continue

            widget = self.add_types_widget_index(self.userdata_layout, parameter_name, 'userdata',
                                                 i, widget_type)

            set_tool_tip(widget, tooltip)

            self.userdata[i] = widget

        # Only show reset button if there is any object-specific field that can be reset.
        has_fields = any(widget is not None for widget in self.userdata)
        for i in range(self.objdata_reset_button_layout.count()):
            item = self.objdata_reset_button_layout.itemAt(i)
            if item_widget := item.widget():
                item_widget.setVisible(has_fields)

        self.update_userdata_widgets(cmn_obj)

        self.assets.setText(', '.join(assets) if assets else 'None')
        self.assets.setToolTip(
            ttl.markdown_to_html('Required Assets',
                                 '\n'.join(f'- {asset}' for asset in assets) if assets else 'None'))
        self.assets.setCursorPosition(0)

    def update_name(self):
        for obj in self.bound_to:
            if obj.widget is None:
                continue
            obj.widget.update_name()
            obj.widget.parent().sort()
            obj.widget.setSelected(True)

    def update_data(self):
        obj: MapObject = get_average_obj(self.bound_to)
        self.position[0].setValueQuiet(obj.position.x)
        self.position[1].setValueQuiet(obj.position.y)
        self.position[2].setValueQuiet(obj.position.z)

        self.scale[0].setValueQuiet(obj.scale.x)
        self.scale[1].setValueQuiet(obj.scale.y)
        self.scale[2].setValueQuiet(obj.scale.z)

        self.update_rotation(*self.rotation)

        if obj.objectid not in OBJECTNAMES:
            name = "INVALID"
        else:
            name = OBJECTNAMES[obj.objectid]
        index = self.objectid.findText(name)
        with QtCore.QSignalBlocker(self.objectid):
            self.objectid.setCurrentIndex(index)

        #self.pathid.setValueQuiet(obj.pathid)

        try:
            routeindex = self.bol.routes.index(obj.route)
        except ValueError:
            routeindex = -1
        if routeindex == -1:
            self.route.setCurrentIndex(0)
        else:
            self.route.setCurrentText("Route {0}".format(routeindex))


        self.unk_2a.setValueQuiet(obj.unk_2a)
        self.presence_filter.set_value(obj.presence_filter)
        self.presence.set_value(obj.presence)
        self.flag.setChecked(obj.unk_flag != 0)

        self.rebuild_object_parameters_widgets(name)

    def fill_default_values(self):
        obj = get_average_obj(self.bound_to)
        defaults = obj.default_values()
        if defaults is None:
            return
        for mapobject in self.bound_to:
            mapobject.userdata = defaults.copy()
        self.update_userdata_widgets(get_average_obj(self.bound_to))

    def update_userdata_widgets(self, obj):
        for i, widget in enumerate(self.userdata):
            if widget is None:
                continue

            with QtCore.QSignalBlocker(widget):
                if isinstance(widget, QtWidgets.QCheckBox):
                    widget.setChecked(bool(obj.userdata[i]))
                elif isinstance(widget, QtWidgets.QComboBox):
                    index = widget.findData(obj.userdata[i])
                    widget.setCurrentIndex(index if index != -1 else 0)
                elif isinstance(widget, QtWidgets.QSpinBox):
                    widget.setValue(obj.userdata[i])


class KartStartPointEdit(DataEditor):
    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.rotation = self.add_rotation_input()
        self.scale = self.add_multiple_decimal_input("Scale", "scale", ["x", "y", "z"],
                                                     -inf, +inf)

        options = OrderedDict()
        options["Left"] = 0
        options["Right"] = 1
        self.poleposition = self.add_dropdown_input("Pole Position", "poleposition",
                                                    options)
        self.playerid = self.add_dropdown_input("Players", "playerid",
                                                REVERSE_KART_START_POINTS_PLAYER_IDS)
        self.unknown = self.add_integer_input("Unknown", "unknown",
                                              MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)

        self.playerid.currentTextChanged.connect(lambda _index: self.update_name())

    def update_data(self):
        obj: KartStartPoint = get_average_obj(self.bound_to)
        self.position[0].setValueQuiet(obj.position.x)
        self.position[1].setValueQuiet(obj.position.y)
        self.position[2].setValueQuiet(obj.position.z)

        self.update_rotation(*self.rotation)

        self.scale[0].setValueQuiet(obj.scale.x)
        self.scale[1].setValueQuiet(obj.scale.y)
        self.scale[2].setValueQuiet(obj.scale.z)

        self.poleposition.setCurrentIndex(obj.poleposition)

        if obj.playerid in KART_START_POINTS_PLAYER_IDS:
            name = KART_START_POINTS_PLAYER_IDS[obj.playerid]
        else:
            name = KART_START_POINTS_PLAYER_IDS[0]
        index = self.playerid.findText(name)
        self.playerid.setCurrentIndex(index)
        set_tool_tip(self.playerid, ttl.kartstartpoints['Players'])

        self.unknown.setValueQuiet(obj.unknown)

    def update_name(self):
        for obj in self.bound_to:
            if obj.widget is None:
                continue
            obj.widget.update_name()

AREA_SHAPE = {
    "Box": 0,
    "Cylinder": 1,
}


class AreaEdit(DataEditor):
    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.scale = self.add_multiple_decimal_input("Scale", "scale", ["x", "y", "z"],
                                                     -inf, +inf)
        self.rotation = self.add_rotation_input()
        self.shape = self.add_dropdown_input("Shape", "shape", AREA_SHAPE)
        self.area_type = self.add_dropdown_input("Area Type", "area_type", REVERSE_AREA_TYPES)

        cameras = OrderedDict()
        cameras["None"] = None
        for i, camera in enumerate(self.bol.cameras):
            cameras["Camera {0}".format(i)] = camera
        self.camera = self.add_dropdown_input("Camera", "camera", cameras)

        set_tool_tip(self.camera, ttl.areadata["Camera Index"])
        self.feather = self.add_multiple_integer_input("Feather", "feather", ["i0", "i1"],
                                                       MIN_UNSIGNED_INT, MAX_SIGNED_INT)
        for i in self.feather:
            set_tool_tip(i, ttl.areadata['Feather'])
        self.unkfixedpoint = self.add_integer_input("Unknown 3 Fixed Point", "unkfixedpoint",
                                                    MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.unkshort = self.add_integer_input("Unknown 4", "unkshort",
                                               MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.shadow_id = self.add_integer_input("Shadow ID", "shadow_id",
                                                MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.lightparam_index = self.add_integer_input("LightParam Index", "lightparam_index",
                                                       MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        set_tool_tip(self.lightparam_index, ttl.areadata['LightParam Index'])

        self.shape.currentIndexChanged.connect(lambda _index: self.catch_text_update())
        self.area_type.currentTextChanged.connect(self.update_name)

    def update_data(self):
        obj: Area = get_average_obj(self.bound_to)
        self.position[0].setValueQuiet(obj.position.x)
        self.position[1].setValueQuiet(obj.position.y)
        self.position[2].setValueQuiet(obj.position.z)

        self.scale[0].setValueQuiet(obj.scale.x)
        self.scale[1].setValueQuiet(obj.scale.y)
        self.scale[2].setValueQuiet(obj.scale.z)

        self.update_rotation(*self.rotation)

        with QtCore.QSignalBlocker(self.shape):
            self.shape.setCurrentIndex(obj.shape)
        with QtCore.QSignalBlocker(self.area_type):
            self.area_type.setCurrentIndex(obj.area_type)

        try:
            camindex = self.bol.cameras.index(obj.camera)
        except ValueError:
            camindex = -1

        with QtCore.QSignalBlocker(self.camera):
            if camindex == -1:
                self.camera.setCurrentIndex(0)
            else:
                self.camera.setCurrentText("Camera {0}".format(camindex))

        self.feather[0].setValueQuiet(obj.feather.i0)
        self.feather[1].setValueQuiet(obj.feather.i1)
        self.unkfixedpoint.setValueQuiet(obj.unkfixedpoint)
        self.unkshort.setValueQuiet(obj.unkshort)
        self.shadow_id.setValueQuiet(obj.shadow_id)
        self.lightparam_index.setValueQuiet(obj.lightparam_index)

    def update_name(self):
        for obj in self.bound_to:
            if obj.widget is None:
                continue
            obj.widget.update_name()


CAMERA_TYPES = OrderedDict()
CAMERA_TYPES["000 - Fix | StartFix"] = 0x0000
CAMERA_TYPES["001 - FixPath | StartOnlyPath"] = 0x0001
CAMERA_TYPES["002 - FixChase"] = 0x0002
CAMERA_TYPES["003 - FixSpl"] = 0x0003
CAMERA_TYPES["004 - StartFixPath"] = 0x0004
CAMERA_TYPES["005 - DemoPath | StartPath"] = 0x0005
CAMERA_TYPES["006 - StartLookPath"] = 0x0006
CAMERA_TYPES["007 - FixPala"] = 0x0007
CAMERA_TYPES["008 - ?"] = 0x0008
CAMERA_TYPES["100 - FixSearch"] = 0x0100
CAMERA_TYPES["101 - ChasePath | StartChasePath"] = 0x0101
CAMERA_TYPES["102 - Chase"] = 0x0102
CAMERA_TYPES["103 - ChaseSpl"] = 0x0103


class CameraEdit(DataEditor):
    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.position3 = self.add_multiple_decimal_input("Start Point", "position3", ["x", "y", "z"],
                                                        -inf, +inf)
        self.position2 = self.add_multiple_decimal_input("End Point", "position2", ["x", "y", "z"],
                                                        -inf, +inf)
        self.rotation = self.add_rotation_input()
        self.camtype = self.add_dropdown_input("Type", "camtype", CAMERA_TYPES)
        self.fov = self.add_multiple_integer_input("Start/End FOV", "fov", ["start", "end"],
                                                   MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        self.camduration = self.add_integer_input("Camera Duration", "camduration",
                                                  MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        set_tool_tip(self.camduration, ttl.camdata['Camera Duration'])
        self.startcamera = self.add_checkbox("Start Camera", "startcamera", off_value=0, on_value=1)
        set_tool_tip(self.startcamera, ttl.camdata['Start Camera'])

        cameras = OrderedDict()
        cameras["None"] = None
        for i, camera in enumerate(self.bol.cameras):
            cameras["Camera {0}".format(i)] = camera

        self.nextcam = self.add_dropdown_input("Next Cam", "nextcam", cameras)

        set_tool_tip(self.nextcam, ttl.camdata['Next Cam'])
        self.shimmer = self.add_multiple_integer_input("Shimmer", "shimmer", ["z0", "z1"], 0, 4095)

        routes = OrderedDict()
        routes["None"] = None
        for i, route in enumerate(self.bol.routes):
            routes["Route {0}".format(i)] = route

        self.route = self.add_dropdown_input("Route", "route", routes)
        set_tool_tip(self.route, ttl.camdata['Route ID'])

        self.route.currentIndexChanged.connect(self.catch_text_update)
        self.routespeed = self.add_integer_input("Route Speed", "routespeed",
                                                 MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        set_tool_tip(self.routespeed, ttl.camdata['Route Speed'])
        self.name = self.add_text_input("Camera Name", "name", 4)

        self.camtype.currentIndexChanged.connect(lambda _index: self.catch_text_update())
        self.camtype.currentTextChanged.connect(self.update_name)

    def update_data(self):
        obj: Camera = get_average_obj(self.bound_to)
        self.position[0].setValueQuiet(obj.position.x)
        self.position[1].setValueQuiet(obj.position.y)
        self.position[2].setValueQuiet(obj.position.z)

        self.position2[0].setValueQuiet(obj.position2.x)
        self.position2[1].setValueQuiet(obj.position2.y)
        self.position2[2].setValueQuiet(obj.position2.z)

        self.position3[0].setValueQuiet(obj.position3.x)
        self.position3[1].setValueQuiet(obj.position3.y)
        self.position3[2].setValueQuiet(obj.position3.z)

        self.update_rotation(*self.rotation)

        self.camtype.setCurrentIndex(list(CAMERA_TYPES.values()).index(obj.camtype))
        self.fov[0].setValueQuiet(obj.fov.start)
        self.fov[1].setValueQuiet(obj.fov.end)
        self.camduration.setValueQuiet(obj.camduration)
        self.startcamera.setChecked(obj.startcamera != 0)
        self.shimmer[0].setValueQuiet(obj.shimmer.z0)
        self.shimmer[1].setValueQuiet(obj.shimmer.z1)

        try:
            routeindex = self.bol.routes.index(obj.route)
        except ValueError:
            routeindex = -1
        if routeindex == -1:
            self.route.setCurrentIndex(0)
        else:
            self.route.setCurrentText("Route {0}".format(routeindex))

        self.routespeed.setValueQuiet(obj.routespeed)

        try:
            camindex = self.bol.cameras.index(obj.nextcam)
        except ValueError:
            camindex = -1
        if camindex == -1:
            self.nextcam.setCurrentIndex(0)
        else:
            self.nextcam.setCurrentText("Camera {0}".format(camindex))

        self.name.setText(obj.name)

    def update_name(self):
        for camera in self.bound_to:
            if camera.widget is None:
                continue
            camera.widget.update_name()


class RespawnPointEdit(DataEditor):
    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.rotation = self.add_rotation_input()
        self.respawn_id = self.add_integer_input("Respawn ID", "respawn_id",
                                                 MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        set_tool_tip(self.respawn_id, ttl.respawn['Respawn ID'])
        self.unk1 = self.add_integer_input("Next Enemy Point", "unk1",
                                           MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)

        def on_partial_clicked():
            for obj in self.bound_to:
                self.bol.adjust_respawn_point(obj, also_id=False, also_rotation=False)
            self.update_data()

        def on_full_clicked():
            for obj in self.bound_to:
                self.bol.adjust_respawn_point(obj, also_id=False, also_rotation=True)
            self.update_data()

        adjust_menu = QtWidgets.QMenu(self)
        adjust_partial = adjust_menu.addAction('Adjust next enemy point')
        adjust_full = adjust_menu.addAction('Adjust next enemy point and rotation')
        adjust_partial.triggered.connect(on_partial_clicked)
        adjust_full.triggered.connect(on_full_clicked)
        adjust_button = QtWidgets.QPushButton('Adjust')
        adjust_button.setMenu(adjust_menu)
        self.unk1.property('parent_layout').addWidget(adjust_button)
        set_tool_tip(self.unk1, ttl.respawn['Next Enemy Point'])
        self.unk1.valueChanged.connect(lambda _value: self.catch_text_update())

        self.unk2 = self.add_integer_input("Camera Index", "unk2",
                                           MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        set_tool_tip(self.unk2, ttl.respawn['Camera Index'])
        self.unk3 = self.add_integer_input("Previous Checkpoint", "unk3",
                                           MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        set_tool_tip(self.unk3, ttl.respawn['Previous Checkpoint'])
        self.unk3.valueChanged.connect(lambda _value: self.catch_text_update())


        self.respawn_id.valueChanged.connect(lambda _value: self.update_name())

    def update_data(self):
        obj: JugemPoint = get_average_obj(self.bound_to)
        self.position[0].setValueQuiet(obj.position.x)
        self.position[1].setValueQuiet(obj.position.y)
        self.position[2].setValueQuiet(obj.position.z)
        self.update_rotation(*self.rotation)
        self.respawn_id.setValueQuiet(obj.respawn_id)
        self.unk1.setValueQuiet(obj.unk1)
        self.unk2.setValueQuiet(obj.unk2)
        self.unk3.setValueQuiet(obj.unk3)

    def update_name(self):
        for obj in self.bound_to:
            if obj.widget is None:
                continue
            obj.widget.update_name()


class LightParamEdit(DataEditor):
    def setup_widgets(self):
        self.color1 = self.add_color_input("RGBA 1", "color1", with_alpha=True)
        for i in self.color1:
            set_tool_tip(i, ttl.lightparam["Light"])
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        for i in self.position:
            set_tool_tip(i, ttl.lightparam["Position"])
        self.color2 = self.add_color_input("RGBA 2", "color2", with_alpha=True)
        for i in self.color2:
            set_tool_tip(i, ttl.lightparam["Ambient"])

    def update_data(self):
        obj: LightParam = get_average_obj(self.bound_to)
        self.color1[0].setValue(obj.color1.r)
        self.color1[1].setValue(obj.color1.g)
        self.color1[2].setValue(obj.color1.b)
        self.color1[3].setValue(obj.color1.a)

        self.color2[0].setValue(obj.color2.r)
        self.color2[1].setValue(obj.color2.g)
        self.color2[2].setValue(obj.color2.b)
        self.color2[3].setValue(obj.color2.a)

        self.position[0].setValueQuiet(obj.position.x)
        self.position[1].setValueQuiet(obj.position.y)
        self.position[2].setValueQuiet(obj.position.z)


class MGEntryEdit(DataEditor):
    def setup_widgets(self):
        self.unk1 = self.add_integer_input("Unknown 1", "unk1",
                                           MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.unk2 = self.add_integer_input("Unknown 2", "unk2",
                                           MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.unk3 = self.add_integer_input("Unknown 3", "unk3",
                                           MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.unk4 = self.add_integer_input("Unknown 4", "unk4",
                                           MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)

    def update_data(self):
        obj: MGEntry = get_average_obj(self.bound_to)
        self.unk1.setValueQuiet(obj.unk1)
        self.unk2.setValueQuiet(obj.unk2)
        self.unk3.setValueQuiet(obj.unk3)
        self.unk4.setValueQuiet(obj.unk4)


ORIENTATION_OPTIONS = OrderedDict()
ORIENTATION_OPTIONS["Upwards"] = 0
ORIENTATION_OPTIONS["Leftwards"] = 1
ORIENTATION_OPTIONS["Downwards"] = 2
ORIENTATION_OPTIONS["Rightwards"] = 3


class MinimapEdit(DataEditor):
    def setup_widgets(self):
        self.topleft = self.add_multiple_decimal_input("TopLeft", "corner1", ["x", "y", "z"],
                                                       -inf, +inf)
        self.bottomright = self.add_multiple_decimal_input("BottomRight", "corner2", ["x", "y", "z"],
                                                           -inf, +inf)
        self.orientation = self.add_dropdown_input("Orientation", "orientation", ORIENTATION_OPTIONS)
        self.orientation.currentIndexChanged.connect(lambda _index: self.catch_text_update())

    def update_data(self):
        obj: Minimap = get_average_obj(self.bound_to)
        self.topleft[0].setValueQuiet(obj.corner1.x)
        self.topleft[1].setValueQuiet(obj.corner1.y)
        self.topleft[2].setValueQuiet(obj.corner1.z)
        self.bottomright[0].setValueQuiet(obj.corner2.x)
        self.bottomright[1].setValueQuiet(obj.corner2.y)
        self.bottomright[2].setValueQuiet(obj.corner2.z)

        self.orientation.setCurrentIndex(obj.orientation)


class PositionedEdit(DataEditor):
    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)

    def update_data(self):
        obj: PositionedObject = get_average_obj(self.bound_to)
        self.position[0].setValueQuiet(obj.position.x)
        self.position[1].setValueQuiet(obj.position.y)
        self.position[2].setValueQuiet(obj.position.z)
