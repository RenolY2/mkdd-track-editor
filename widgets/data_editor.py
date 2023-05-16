import os
import json
import widgets.tooltip_list as ttl

from PySide6 import QtCore, QtGui, QtWidgets

from collections import OrderedDict
from math import inf
from lib.libbol import (EnemyPoint, EnemyPointGroup, CheckpointGroup, Checkpoint, Route, RoutePoint,
                        MapObject, KartStartPoint, Area, Camera, BOL, JugemPoint, MapObject,
                        LightParam, MGEntry, OBJECTNAMES, REVERSEOBJECTNAMES, MUSIC_IDS, REVERSE_MUSIC_IDS,
                        SWERVE_IDS, REVERSE_SWERVE_IDS, REVERSE_AREA_TYPES,
                        KART_START_POINTS_PLAYER_IDS, REVERSE_KART_START_POINTS_PLAYER_IDS)
from lib.vectors import Vector3
from lib.model_rendering import Minimap


def load_parameter_names(objectname):
    try:
        with open(os.path.join("object_parameters", objectname+".json"), "r") as f:
            data = json.load(f)
            parameter_names = data["Object Parameters"]
            assets = data["Assets"]
            if "Tooltips" in data:
                tooltips = data["Tooltips"]
            else:
                tooltips = ""
            if len(parameter_names) != 8:
                raise RuntimeError("Not enough or too many parameters: {0} (should be 8)".format(len(parameter_names)))
            if tooltips != "":
                return parameter_names, assets, tooltips
            else:
                return parameter_names, assets
    except Exception as err:
        print(err)
        return None, None


class PythonIntValidator(QtGui.QValidator):
    def __init__(self, min, max, parent):
        super().__init__(parent)
        self.min = min
        self.max = max

    def validate(self, p_str, p_int):
        if p_str == "" or p_str == "-":
            return QtGui.QValidator.Intermediate, p_str, p_int

        try:
            result = int(p_str)
        except:
            return QtGui.QValidator.Invalid, p_str, p_int

        if self.min <= result <= self.max:
            return QtGui.QValidator.Acceptable, p_str, p_int
        else:
            return QtGui.QValidator.Invalid, p_str, p_int

    def fixup(self, s):
        pass


class ClickableLabel(QtWidgets.QLabel):

    clicked = QtCore.Signal()

    def mouseReleaseEvent(self, event):

        if self.rect().contains(event.pos()):
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

    def __init__(self, parent, bound_to):
        super().__init__(parent)

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
            if state == 0:
                setattr(self.bound_to, attribute, off_value)
            else:
                setattr(self.bound_to, attribute, on_value)

        checkbox.stateChanged.connect(checked)
        self.vbox.addLayout(layout)

        return checkbox

    def add_integer_input(self, text, attribute, min_val, max_val):
        line_edit = QtWidgets.QLineEdit(self)
        layout = self.create_labeled_widget(self, text, line_edit)

        line_edit.setValidator(PythonIntValidator(min_val, max_val, line_edit))

        def input_edited():
            print("Hmmmm")
            text = line_edit.text()
            print("input:", text)

            setattr(self.bound_to, attribute, int(text))

        line_edit.editingFinished.connect(input_edited)

        self.vbox.addLayout(layout)
        print("created for", text, attribute)
        return line_edit

    def add_integer_input_index(self, text, attribute, index, min_val, max_val):
        line_edit = QtWidgets.QLineEdit(self)
        layout = self.create_labeled_widget(self, text, line_edit)

        line_edit.setValidator(QtGui.QIntValidator(min_val, max_val, self))

        def input_edited():
            text = line_edit.text()
            print("input:", text)
            mainattr = getattr(self.bound_to, attribute)
            mainattr[index] = int(text)

        line_edit.editingFinished.connect(input_edited)
        label = layout.itemAt(0).widget()
        self.vbox.addLayout(layout)

        return label, line_edit

    def add_decimal_input(self, text, attribute, min_val, max_val):
        line_edit = QtWidgets.QLineEdit(self)
        layout = self.create_labeled_widget(self, text, line_edit)

        line_edit.setValidator(QtGui.QDoubleValidator(min_val, max_val, 6, self))

        def input_edited():
            text = line_edit.text()
            print("input:", text)
            self.catch_text_update()
            setattr(self.bound_to, attribute, float(text))

        line_edit.editingFinished.connect(input_edited)

        self.vbox.addLayout(layout)

        return line_edit

    def add_text_input(self, text, attribute, maxlength):
        line_edit = QtWidgets.QLineEdit(self)
        layout = self.create_labeled_widget(self, text, line_edit)

        line_edit.setMaxLength(maxlength)

        def input_edited():
            text = line_edit.text()
            text = text.rjust(maxlength)
            setattr(self.bound_to, attribute, text)

        line_edit.editingFinished.connect(input_edited)
        self.vbox.addLayout(layout)

        return line_edit

    def add_dropdown_input(self, text, attribute, keyval_dict):
        combobox = QtWidgets.QComboBox(self)
        for val in keyval_dict:
            combobox.addItem(val)

        tt_dict = getattr(ttl, attribute, None)
        try:
            defaultitem = list(tt_dict)[0]
        except TypeError:
            pass
        else:
            if tt_dict is not None and combobox.currentText() == defaultitem:
                combobox.setToolTip(tt_dict[defaultitem])

        policy = combobox.sizePolicy()
        policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Expanding)
        combobox.setSizePolicy(policy)
        combobox.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)

        layout = self.create_labeled_widget(self, text, combobox)

        def item_selected(item):
            val = keyval_dict[item]
            print("selected", item)
            setattr(self.bound_to, attribute, val)

            if tt_dict is not None and item in tt_dict:
                combobox.setToolTip(tt_dict[item])
            else:
                combobox.setToolTip('')

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
        return button

    def add_color_input(self, text, attribute, with_alpha=False):
        line_edits = []
        input_edited_callbacks = []

        for subattr in ["r", "g", "b", "a"] if with_alpha else ["r", "g", "b"]:
            line_edit = QtWidgets.QLineEdit(self)
            line_edit.setMaximumWidth(30)
            line_edit.setValidator(QtGui.QIntValidator(0, 255, self))
            input_edited = create_setter(line_edit, self.bound_to, attribute, subattr, self.catch_text_update, isFloat=False)
            input_edited_callbacks.append(input_edited)
            line_edit.editingFinished.connect(input_edited)
            line_edits.append(line_edit)

        color_picker = ColorPicker(with_alpha=with_alpha)

        def on_text_changed(text: str):
            _ = text
            r = int(line_edits[0].text() or '0')
            g = int(line_edits[1].text() or '0')
            b = int(line_edits[2].text() or '0')
            a = int(line_edits[3].text() or '0') if len(line_edits) == 4 else 255
            color_picker.color = QtGui.QColor(r, g, b, a)
            color_picker.update_color(color_picker.color)

        for line_edit in line_edits:
            line_edit.textChanged.connect(on_text_changed)

        def on_color_changed(color):
            line_edits[0].setText(str(color.red()))
            line_edits[1].setText(str(color.green()))
            line_edits[2].setText(str(color.blue()))
            if len(line_edits) == 4:
                line_edits[3].setText(str(color.alpha()))

        def on_color_picked(color):
            for callback in input_edited_callbacks:
                callback()

        color_picker.color_changed.connect(on_color_changed)
        color_picker.color_picked.connect(on_color_picked)

        layout = self.create_labeled_widgets(self, text, line_edits + [color_picker])
        self.vbox.addLayout(layout)

        return line_edits

    def add_multiple_integer_input(self, text, attribute, subattributes, min_val, max_val):
        line_edits = []
        for subattr in subattributes:
            line_edit = QtWidgets.QLineEdit(self)

            if max_val <= MAX_UNSIGNED_BYTE:
                line_edit.setMaximumWidth(30)

            line_edit.setValidator(QtGui.QIntValidator(min_val, max_val, self))

            input_edited = create_setter(line_edit, self.bound_to, attribute, subattr, self.catch_text_update, isFloat=False)

            line_edit.editingFinished.connect(input_edited)
            line_edits.append(line_edit)

        layout = self.create_labeled_widgets(self, text, line_edits)
        self.vbox.addLayout(layout)


        return line_edits

    def add_multiple_decimal_input(self, text, attribute, subattributes, min_val, max_val):
        line_edits = []
        for subattr in subattributes:
            line_edit = QtWidgets.QLineEdit(self)

            line_edit.setValidator(QtGui.QDoubleValidator(min_val, max_val, 6, self))

            input_edited = create_setter(line_edit, self.bound_to, attribute, subattr, self.catch_text_update, isFloat=True)
            line_edit.editingFinished.connect(input_edited)
            line_edits.append(line_edit)

        layout = self.create_labeled_widgets(self, text, line_edits)
        self.vbox.addLayout(layout)

        return line_edits

    def add_multiple_integer_input_list(self, text, attribute, min_val, max_val):
        line_edits = []
        fieldlist = getattr(self.bound_to, attribute)
        for i in range(len(fieldlist)):
            line_edit = QtWidgets.QLineEdit(self)
            line_edit.setMaximumWidth(30)

            line_edit.setValidator(QtGui.QIntValidator(min_val, max_val, self))

            input_edited = create_setter_list(line_edit, self.bound_to, attribute, i)
            line_edit.editingFinished.connect(input_edited)
            line_edits.append(line_edit)

        layout = self.create_labeled_widgets(self, text, line_edits)
        self.vbox.addLayout(layout)

        return line_edits

    def update_rotation(self, forwardedits, upedits, leftedits):
        rotation = self.bound_to.rotation
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

        forwardedits[0].setText(str(round(forward.x, 4)))
        forwardedits[1].setText(str(round(forward.y, 4)))
        forwardedits[2].setText(str(round(forward.z, 4)))

        upedits[0].setText(str(round(up.x, 4)))
        upedits[1].setText(str(round(up.y, 4)))
        upedits[2].setText(str(round(up.z, 4)))

        leftedits[0].setText(str(round(left.x, 4)))
        leftedits[1].setText(str(round(left.y, 4)))
        leftedits[2].setText(str(round(left.z, 4)))

        self.catch_text_update()

    def add_rotation_input(self):
        rotation = self.bound_to.rotation
        forward_edits = []
        up_edits = []
        left_edits = []

        for attr in ("x", "y", "z"):
            line_edit = QtWidgets.QLineEdit(self)
            validator = QtGui.QDoubleValidator(-1.0, 1.0, 9999, self)
            validator.setNotation(QtGui.QDoubleValidator.StandardNotation)
            line_edit.setValidator(validator)

            forward_edits.append(line_edit)

        for attr in ("x", "y", "z"):
            line_edit = QtWidgets.QLineEdit(self)
            validator = QtGui.QDoubleValidator(-1.0, 1.0, 9999, self)
            validator.setNotation(QtGui.QDoubleValidator.StandardNotation)
            line_edit.setValidator(validator)

            up_edits.append(line_edit)

        for attr in ("x", "y", "z"):
            line_edit = QtWidgets.QLineEdit(self)
            validator = QtGui.QDoubleValidator(-1.0, 1.0, 9999, self)
            validator.setNotation(QtGui.QDoubleValidator.StandardNotation)
            line_edit.setValidator(validator)

            left_edits.append(line_edit)

        def change_forward():
            forward, up, left = rotation.get_vectors()

            newforward = Vector3(*[float(v.text()) for v in forward_edits])
            if newforward.norm() == 0.0:
                newforward = left.cross(up)
            newforward.normalize()
            up = newforward.cross(left)
            up.normalize()
            left = up.cross(newforward)
            left.normalize()

            rotation.set_vectors(newforward, up, left)
            self.update_rotation(forward_edits, up_edits, left_edits)

        def change_up():
            print("finally changing up")
            forward, up, left = rotation.get_vectors()
            newup = Vector3(*[float(v.text()) for v in up_edits])
            if newup.norm() == 0.0:
                newup = forward.cross(left)
            newup.normalize()
            forward = left.cross(newup)
            forward.normalize()
            left = newup.cross(forward)
            left.normalize()

            rotation.set_vectors(forward, newup, left)
            self.update_rotation(forward_edits, up_edits, left_edits)

        def change_left():
            forward, up, left = rotation.get_vectors()

            newleft = Vector3(*[float(v.text()) for v in left_edits])
            if newleft.norm() == 0.0:
                newleft = up.cross(forward)
            newleft.normalize()
            forward = newleft.cross(up)
            forward.normalize()
            up = forward.cross(newleft)
            up.normalize()

            rotation.set_vectors(forward, up, newleft)
            self.update_rotation(forward_edits, up_edits, left_edits)

        for edit in forward_edits:
            edit.editingFinished.connect(change_forward)
        for edit in up_edits:
            edit.editingFinished.connect(change_up)
        for edit in left_edits:
            edit.editingFinished.connect(change_left)

        layout = self.create_labeled_widgets(self, "Forward dir", forward_edits)
        self.vbox.addLayout(layout)
        layout = self.create_labeled_widgets(self, "Up dir", up_edits)
        self.vbox.addLayout(layout)
        layout = self.create_labeled_widgets(self, "Left dir", left_edits)
        self.vbox.addLayout(layout)
        return forward_edits, up_edits, left_edits

    def set_value(self, field, val):
        field.setText(str(val))


def create_setter_list(lineedit, bound_to, attribute, index):
    def input_edited():
        text = lineedit.text()
        mainattr = getattr(bound_to, attribute)
        mainattr[index] = int(text)

    return input_edited


def create_setter(lineedit, bound_to, attribute, subattr, update3dview, isFloat):
    if isFloat:
        def input_edited():
            text = lineedit.text()
            mainattr = getattr(bound_to, attribute)

            setattr(mainattr, subattr, float(text))
            update3dview()
        return input_edited
    else:
        def input_edited():
            text = lineedit.text()
            mainattr = getattr(bound_to, attribute)

            setattr(mainattr, subattr, int(text))
            update3dview()
        return input_edited

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


def choose_data_editor(obj):
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
        self.groupid = self.add_integer_input("Group ID", "id", MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)

    def update_data(self):
        self.groupid.setText(str(self.bound_to.id))


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
        self.link.setToolTip(ttl.enemypoints['Link'])
        self.scale = self.add_decimal_input("Scale", "scale", -inf, inf)
        self.scale.setToolTip(ttl.enemypoints['Scale'])
        self.itemsonly = self.add_checkbox("Items Only", "itemsonly", off_value=0, on_value=1)
        self.itemsonly.setToolTip(ttl.enemypoints['Items Only'])
        self.swerve = self.add_dropdown_input("Swerve", "swerve", REVERSE_SWERVE_IDS)
        self.group = self.add_integer_input("Group", "group",
                                            MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        if not group_editable:
            self.group.setDisabled(True)

        self.driftdirection = self.add_dropdown_input("Drift Direction", "driftdirection",
                                                      DRIFT_DIRECTION_OPTIONS)
        self.driftacuteness = self.add_integer_input("Drift Acuteness", "driftacuteness",
                                                     MIN_UNSIGNED_BYTE, 250)
        self.driftacuteness.setToolTip(ttl.enemypoints['Drift Acuteness'])
        self.driftduration = self.add_integer_input("Drift Duration", "driftduration",
                                                    MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        self.driftduration.setToolTip(ttl.enemypoints['Drift Duration'])
        self.driftsupplement = self.add_integer_input("Drift Supplement", "driftsupplement",
                                                      MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        self.driftsupplement.setToolTip(ttl.enemypoints['Drift Supplement'])
        self.nomushroomzone = self.add_checkbox("No Mushroom Zone", "nomushroomzone",
                                                off_value=0, on_value=1)
        self.nomushroomzone.setToolTip(ttl.enemypoints['No Mushroom Zone'])

        for widget in self.position:
            widget.editingFinished.connect(self.catch_text_update)
        for widget in (self.itemsonly, self.nomushroomzone):
            widget.stateChanged.connect(lambda _state: self.catch_text_update())
        for widget in (self.swerve, self.driftdirection):
            widget.currentIndexChanged.connect(lambda _index: self.catch_text_update())
        for widget in (self.link, self.driftacuteness, self.driftduration, self.driftsupplement):
            widget.editingFinished.connect(self.catch_text_update)

        self.link.editingFinished.connect(self.update_name)

    def update_data(self):
        obj: EnemyPoint = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))
        self.driftdirection.setCurrentIndex(obj.driftdirection)
        self.driftdirection.setToolTip(ttl.enemypoints['Drift Direction'])
        self.link.setText(str(obj.link))
        self.scale.setText(str(obj.scale))
        self.itemsonly.setChecked(bool(obj.itemsonly))
        self.group.setText(str(obj.group))
        self.driftacuteness.setText(str(obj.driftacuteness))
        self.driftduration.setText(str(obj.driftduration))
        self.driftsupplement.setText(str(obj.driftsupplement))
        self.nomushroomzone.setChecked(bool(obj.nomushroomzone))

        if obj.swerve in SWERVE_IDS:
            name = SWERVE_IDS[obj.swerve]
        else:
            name = SWERVE_IDS[0]
        index = self.swerve.findText(name)
        self.swerve.setCurrentIndex(index)
        self.swerve.setToolTip(ttl.enemypoints['Swerve'])

    def update_name(self):
        if self.bound_to.widget is None:
            return
        self.bound_to.widget.update_name()


class CheckpointGroupEdit(DataEditor):
    def setup_widgets(self):
        self.grouplink = self.add_integer_input("Group Setting", "grouplink",
                                                MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        self.prevgroup = self.add_multiple_integer_input_list("Previous Groups", "prevgroup",
                                                              MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.nextgroup = self.add_multiple_integer_input_list("Next Groups", "nextgroup",
                                                              MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)

    def update_data(self):
        obj = self.bound_to
        self.grouplink.setText(str(obj.grouplink))
        for i, widget in enumerate(self.prevgroup):
            widget.setText(str(obj.prevgroup[i]))
        for i, widget in enumerate(self.nextgroup):
            widget.setText(str(obj.nextgroup[i]))


class CheckpointEdit(DataEditor):
    def setup_widgets(self):
        self.start = self.add_multiple_decimal_input("Start", "start", ["x", "y", "z"],
                                                        -inf, +inf)
        self.end = self.add_multiple_decimal_input("End", "end", ["x", "y", "z"],
                                                     -inf, +inf)

        self.unk1 = self.add_integer_input("Shortcut Point ID", "unk1",
                                           MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        self.unk2 = self.add_checkbox("Unknown Flag", "unk2",
                                      0, 1)
        self.unk3 = self.add_checkbox("Double-sided", "unk3",
                                           0, 1)
        self.unk4 = self.add_checkbox("Lap Checkpoint", "unk4",
                                           0, 1)
        self.unk1.setToolTip(ttl.checkpoints["Shortcut Point ID"])
        self.unk3.setToolTip(ttl.checkpoints["Double-sided"])
        self.unk4.setToolTip(ttl.checkpoints["Lap Checkpoint"])

    def update_data(self):
        obj: Checkpoint = self.bound_to
        self.start[0].setText(str(round(obj.start.x, 3)))
        self.start[1].setText(str(round(obj.start.y, 3)))
        self.start[2].setText(str(round(obj.start.z, 3)))

        self.end[0].setText(str(round(obj.end.x, 3)))
        self.end[1].setText(str(round(obj.end.y, 3)))
        self.end[2].setText(str(round(obj.end.z, 3)))

        self.unk1.setText(str(obj.unk1))
        self.unk2.setChecked(obj.unk2 != 0)
        self.unk3.setChecked(obj.unk3 != 0)
        self.unk4.setChecked(obj.unk4 != 0)


class ObjectRouteEdit(DataEditor):
    def setup_widgets(self):
        self.unk1 = self.add_integer_input("Unknown 1", "unk1",
                                           MIN_UNSIGNED_INT, MAX_UNSIGNED_INT)
        self.unk2 = self.add_integer_input("Unknown 2", "unk2",
                                           MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)

    def update_data(self):
        obj: Route = self.bound_to
        self.unk1.setText(str(obj.unk1))
        self.unk2.setText(str(obj.unk2))


class ObjectRoutePointEdit(DataEditor):
    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.unknown = self.add_integer_input("Object Action", "unk",
                                              MIN_UNSIGNED_INT, MAX_UNSIGNED_INT)

    def update_data(self):
        obj: RoutePoint = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))
        self.unknown.setText(str(obj.unk))


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
        obj: BOL = self.bound_to
        #self.roll.setText(str(obj.roll))
        self.roll.setCurrentIndex(obj.roll)
        self.rgb_ambient[0].setText(str(obj.rgb_ambient.r))
        self.rgb_ambient[1].setText(str(obj.rgb_ambient.g))
        self.rgb_ambient[2].setText(str(obj.rgb_ambient.b))
        self.rgba_light[0].setText(str(obj.rgba_light.r))
        self.rgba_light[1].setText(str(obj.rgba_light.g))
        self.rgba_light[2].setText(str(obj.rgba_light.b))
        self.rgba_light[3].setText(str(obj.rgba_light.a))
        self.lightsource[0].setText(str(round(obj.lightsource.x, 3)))
        self.lightsource[1].setText(str(round(obj.lightsource.y, 3)))
        self.lightsource[2].setText(str(round(obj.lightsource.z, 3)))
        self.lap_count.setText(str(obj.lap_count))
        self.fog_type.setText(str(obj.fog_type))
        self.fog_color[0].setText(str(obj.fog_color.r))
        self.fog_color[1].setText(str(obj.fog_color.g))
        self.fog_color[2].setText(str(obj.fog_color.b))
        self.fog_startz.setText(str(obj.fog_startz))
        self.fog_endz.setText(str(obj.fog_endz))
        self.lod_bias.setChecked(obj.lod_bias != 0)
        self.dummy_start_line.setChecked(obj.dummy_start_line != 0)
        self.snow_effects.setChecked(obj.snow_effects != 0)
        self.shadow_opacity.setText(str(obj.shadow_opacity))
        self.sky_follow.setChecked(obj.sky_follow != 0)
        self.shadow_color[0].setText(str(obj.shadow_color.r))
        self.shadow_color[1].setText(str(obj.shadow_color.g))
        self.shadow_color[2].setText(str(obj.shadow_color.b))

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
        self.rotation = self.add_rotation_input()
        self.objectid = self.add_dropdown_input("Object Type", "objectid", REVERSEOBJECTNAMES)

        self.pathid = self.add_integer_input("Route ID", "pathid",
                                             MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.pathid.setToolTip(ttl.objectdata['Route ID'])
        self.pathid.editingFinished.connect(self.catch_text_update)

        self.unk_28 = self.add_integer_input("Unknown 0x28", "unk_28",
                                             MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)

        self.unk_2a = self.add_integer_input("Route Point ID", "unk_2a",
                                             MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.unk_2a.setToolTip(ttl.objectdata['Route Point ID'])

        self.presence_filter = self.add_integer_input("Presence Mask", "presence_filter",
                                                      MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        self.presence_filter.setToolTip(ttl.objectdata['Presence Mask'])

        self.presence = self.add_integer_input("Presence", "presence",
                                               MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        self.presence.setToolTip(ttl.objectdata['Presence'])

        self.flag = self.add_checkbox("Collision", "unk_flag",
                                      off_value=0, on_value=1)
        self.flag.setToolTip(ttl.objectdata['Collision'])

        self.unk_2f = self.add_integer_input("Unknown 0x2F", "unk_2f",
                                             MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)

        self.objdatalabel = self.add_button_input(
            "Object-Specific Settings", "Reset to Default", self.fill_default_values)
        self.userdata = []
        for i in range(8):
            self.userdata.append(
                self.add_integer_input_index("Obj Data {0}".format(i+1), "userdata", i,
                                             MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
            )

        self.objectid.currentTextChanged.connect(self.update_name)

        for widget in self.position:
            widget.editingFinished.connect(self.catch_text_update)

        self.objectid.currentTextChanged.connect(self.rename_object_parameters)

        self.assets = self.add_label("Required Assets: Unknown")
        self.assets.setWordWrap(True)
        hint = self.assets.sizePolicy()
        hint.setVerticalPolicy(QtWidgets.QSizePolicy.Minimum)
        self.assets.setSizePolicy(hint)

    def rename_object_parameters(self, current):

        if len(load_parameter_names(current)) == 2:
            parameter_names, assets = load_parameter_names(current)
        else:
            parameter_names, assets, tooltips = load_parameter_names(current)
        if parameter_names is None:
            for i in range(8):
                self.userdata[i][0].setText("Obj Data {0}".format(i+1))
                self.userdata[i][0].setVisible(True)
                self.userdata[i][1].setVisible(True)
                self.userdata[i][1].setToolTip('')
            self.assets.setText("Required Assets: Unknown")
        else:
            for i in range(8):
                if parameter_names[i] == "Unused":
                    self.userdata[i][0].setVisible(False)
                    self.userdata[i][1].setVisible(False)
                    if self.bound_to.userdata[i] != 0:
                        Warning("Parameter with index {0} in object {1} is marked as Unused but has value {2}".format(
                            i, current, self.bound_to.userdata[i]
                        ))
                else:
                    self.userdata[i][0].setVisible(True)
                    self.userdata[i][1].setVisible(True)
                    self.userdata[i][0].setText(parameter_names[i])
                    self.userdata[i][1].setToolTip('')
                    if len(load_parameter_names(current)) == 3:
                        self.userdata[i][1].setToolTip(tooltips[i])
            if len(assets) == 0:
                self.assets.setText("Required Assets: None")
            else:
                self.assets.setText("Required Assets: {0}".format(", ".join(assets)))

    def update_name(self):
        if self.bound_to.widget is None:
            return
        self.bound_to.widget.update_name()
        self.bound_to.widget.parent().sort()
        self.bound_to.widget.setSelected(True)

    def update_data(self):
        obj: MapObject = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))

        self.scale[0].setText(str(round(obj.scale.x, 3)))
        self.scale[1].setText(str(round(obj.scale.y, 3)))
        self.scale[2].setText(str(round(obj.scale.z, 3)))

        self.update_rotation(*self.rotation)

        if obj.objectid not in OBJECTNAMES:
            name = "INVALID"
        else:
            name = OBJECTNAMES[obj.objectid]
        index = self.objectid.findText(name)
        self.objectid.setCurrentIndex(index)

        self.pathid.setText(str(obj.pathid))
        self.unk_28.setText(str(obj.unk_28))
        self.unk_2a.setText(str(obj.unk_2a))
        self.unk_2f.setText(str(obj.unk_2f))
        self.presence_filter.setText(str(obj.presence_filter))
        self.presence.setText(str(obj.presence))
        self.flag.setChecked(obj.unk_flag != 0)
        for i in range(8):
            self.userdata[i][1].setText(str(obj.userdata[i]))

    def fill_default_values(self):
        obj = self.bound_to
        defaults = obj.default_values()
        if defaults is None:
            return
        obj.userdata = defaults.copy()

        for i, (_label_widget, value_widget) in enumerate(self.userdata):
            value_widget.setText(str(defaults[i]))


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
        obj: KartStartPoint = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))

        self.update_rotation(*self.rotation)

        self.scale[0].setText(str(obj.scale.x))
        self.scale[1].setText(str(obj.scale.y))
        self.scale[2].setText(str(obj.scale.z))

        self.poleposition.setCurrentIndex(obj.poleposition)

        if obj.playerid in KART_START_POINTS_PLAYER_IDS:
            name = KART_START_POINTS_PLAYER_IDS[obj.playerid]
        else:
            name = KART_START_POINTS_PLAYER_IDS[0]
        index = self.playerid.findText(name)
        self.playerid.setCurrentIndex(index)
        self.playerid.setToolTip(ttl.kartstartpoints['Players'])

        self.unknown.setText(str(obj.unknown))

    def update_name(self):
        if self.bound_to.widget is None:
            return
        self.bound_to.widget.update_name()

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
        self.camera_index = self.add_integer_input("Camera Index", "camera_index",
                                                   MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.camera_index.setToolTip(ttl.areadata["Camera Index"])
        self.feather = self.add_multiple_integer_input("Feather", "feather", ["i0", "i1"],
                                                       MIN_UNSIGNED_INT, MAX_SIGNED_INT)
        for i in self.feather:
            i.setToolTip(ttl.areadata['Feather'])
        self.unkfixedpoint = self.add_integer_input("Unknown 3 Fixed Point", "unkfixedpoint",
                                                    MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.unkshort = self.add_integer_input("Unknown 4", "unkshort",
                                               MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.shadow_id = self.add_integer_input("Shadow ID", "shadow_id",
                                                MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.lightparam_index = self.add_integer_input("LightParam Index", "lightparam_index",
                                                       MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.lightparam_index.setToolTip(ttl.areadata['LightParam Index'])

        self.area_type.currentTextChanged.connect(self.update_name)

    def update_data(self):
        obj: Area = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))

        self.scale[0].setText(str(round(obj.scale.x, 3)))
        self.scale[1].setText(str(round(obj.scale.y, 3)))
        self.scale[2].setText(str(round(obj.scale.z, 3)))

        self.update_rotation(*self.rotation)

        self.shape.setCurrentIndex(obj.shape)
        self.area_type.setCurrentIndex(obj.area_type)
        self.camera_index.setText(str(obj.camera_index))
        self.feather[0].setText(str(obj.feather.i0))
        self.feather[1].setText(str(obj.feather.i1))
        self.unkfixedpoint.setText(str(obj.unkfixedpoint))
        self.unkshort.setText(str(obj.unkshort))
        self.shadow_id.setText(str(obj.shadow_id))
        self.lightparam_index.setText(str(obj.lightparam_index))

    def update_name(self):
        if self.bound_to.widget is None:
            return
        self.bound_to.widget.update_name()


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
        self.camduration.setToolTip(ttl.camdata['Camera Duration'])
        self.startcamera = self.add_checkbox("Start Camera", "startcamera", off_value=0, on_value=1)
        self.startcamera.setToolTip(ttl.camdata['Start Camera'])
        self.nextcam = self.add_integer_input("Next Cam", "nextcam",
                                              MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.nextcam.setToolTip(ttl.camdata['Next Cam'])
        self.shimmer = self.add_multiple_integer_input("Shimmer", "shimmer", ["z0", "z1"], 0, 4095)
        self.route = self.add_integer_input("Route ID", "route",
                                            MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.route.setToolTip(ttl.camdata['Route ID'])
        self.route.editingFinished.connect(self.catch_text_update)
        self.routespeed = self.add_integer_input("Route Speed", "routespeed",
                                                 MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        self.routespeed.setToolTip(ttl.camdata['Route Speed'])
        self.name = self.add_text_input("Camera Name", "name", 4)

        self.camtype.currentIndexChanged.connect(lambda _index: self.catch_text_update())
        self.camtype.currentTextChanged.connect(self.update_name)

    def update_data(self):
        obj: Camera = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))

        self.position2[0].setText(str(round(obj.position2.x, 3)))
        self.position2[1].setText(str(round(obj.position2.y, 3)))
        self.position2[2].setText(str(round(obj.position2.z, 3)))

        self.position3[0].setText(str(round(obj.position3.x, 3)))
        self.position3[1].setText(str(round(obj.position3.y, 3)))
        self.position3[2].setText(str(round(obj.position3.z, 3)))

        self.update_rotation(*self.rotation)

        self.camtype.setCurrentIndex(list(CAMERA_TYPES.values()).index(obj.camtype))
        self.fov[0].setText(str(obj.fov.start))
        self.fov[1].setText(str(obj.fov.end))
        self.camduration.setText(str(obj.camduration))
        self.startcamera.setChecked(obj.startcamera != 0)
        self.shimmer[0].setText(str(obj.shimmer.z0))
        self.shimmer[1].setText(str(obj.shimmer.z1))
        self.route.setText(str(obj.route))
        self.routespeed.setText(str(obj.routespeed))
        self.nextcam.setText(str(obj.nextcam))
        self.name.setText(obj.name)

    def update_name(self):
        if self.bound_to.widget is None:
            return
        self.bound_to.widget.update_name()


class RespawnPointEdit(DataEditor):
    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.rotation = self.add_rotation_input()
        self.respawn_id = self.add_integer_input("Respawn ID", "respawn_id",
                                                 MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        self.respawn_id.setToolTip(ttl.respawn['Respawn ID'])
        self.unk1 = self.add_integer_input("Next Enemy Point", "unk1",
                                           MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        self.unk1.setToolTip(ttl.respawn['Next Enemy Point'])
        self.unk1.editingFinished.connect(self.catch_text_update)

        self.unk2 = self.add_integer_input("Unknown 2", "unk2",
                                           MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.unk3 = self.add_integer_input("Previous Checkpoint", "unk3",
                                           MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.unk3.setToolTip(ttl.respawn['Previous Checkpoint'])
        self.unk3.editingFinished.connect(self.catch_text_update)


        self.respawn_id.editingFinished.connect(self.update_name)

    def update_data(self):
        obj: JugemPoint = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))
        self.update_rotation(*self.rotation)
        self.respawn_id.setText(str(obj.respawn_id))
        self.unk1.setText(str(obj.unk1))
        self.unk2.setText(str(obj.unk2))
        self.unk3.setText(str(obj.unk3))

    def update_name(self):
        if self.bound_to.widget is None:
            return
        self.bound_to.widget.update_name()

class LightParamEdit(DataEditor):
    def setup_widgets(self):
        self.color1 = self.add_color_input("RGBA 1", "color1", with_alpha=True)
        for i in self.color1:
            i.setToolTip(ttl.lightparam["Light"])
        self.unkvec = self.add_multiple_decimal_input("Vector", "unkvec", ["x", "y", "z"],
                                                      -inf, +inf)
        for i in self.unkvec:
            i.setToolTip(ttl.lightparam["Position"])
        self.color2 = self.add_color_input("RGBA 2", "color2", with_alpha=True)
        for i in self.color2:
            i.setToolTip(ttl.lightparam["Ambient"])

    def update_data(self):
        obj: LightParam = self.bound_to
        self.color1[0].setText(str(obj.color1.r))
        self.color1[1].setText(str(obj.color1.g))
        self.color1[2].setText(str(obj.color1.b))
        self.color1[3].setText(str(obj.color1.a))

        self.color2[0].setText(str(obj.color2.r))
        self.color2[1].setText(str(obj.color2.g))
        self.color2[2].setText(str(obj.color2.b))
        self.color2[3].setText(str(obj.color2.a))

        self.unkvec[0].setText(str(obj.unkvec.x))
        self.unkvec[1].setText(str(obj.unkvec.y))
        self.unkvec[2].setText(str(obj.unkvec.z))


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
        obj: MGEntry = self.bound_to
        self.unk1.setText(str(obj.unk1))
        self.unk2.setText(str(obj.unk2))
        self.unk3.setText(str(obj.unk3))
        self.unk4.setText(str(obj.unk4))


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
        obj: Minimap = self.bound_to
        self.topleft[0].setText(str(round(obj.corner1.x, 3)))
        self.topleft[1].setText(str(round(obj.corner1.y, 3)))
        self.topleft[2].setText(str(round(obj.corner1.z, 3)))
        self.bottomright[0].setText(str(round(obj.corner2.x, 3)))
        self.bottomright[1].setText(str(round(obj.corner2.y, 3)))
        self.bottomright[2].setText(str(round(obj.corner2.z, 3)))

        self.orientation.setCurrentIndex(obj.orientation)
