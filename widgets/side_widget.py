from PyQt5 import QtCore, QtWidgets, QtGui

from widgets.data_editor import choose_data_editor
from widgets.more_buttons import MoreButtons


class PikminSideWidget(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Top bottoms.
        self.button_add_object = QtWidgets.QPushButton()
        self.button_remove_object = QtWidgets.QPushButton()
        self.button_ground_object = QtWidgets.QPushButton()

        self.button_add_object.setText("Add Object")
        self.button_remove_object.setText("Remove Object(s)")
        self.button_ground_object.setText("Ground Object(s)")

        self.button_add_object.setToolTip("Hotkey: Ctrl+A")
        self.button_remove_object.setToolTip("Hotkey: Delete")
        self.button_ground_object.setToolTip("Hotkey: G")

        self.button_add_object.setCheckable(True)

        # More buttons.
        self.more_buttons = MoreButtons(None)
        self.more_buttons.add_buttons(None)

        # Scroll area.
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameStyle(QtWidgets.QFrame.NoFrame)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_area_frame = QtWidgets.QFrame()
        scroll_area_frame.setFrameStyle(QtWidgets.QFrame.StyledPanel)
        palette = scroll_area_frame.palette()
        palette.setBrush(scroll_area_frame.backgroundRole(), palette.dark())
        scroll_area_frame.setPalette(palette)
        self.scroll_area_frame_layout = QtWidgets.QVBoxLayout(scroll_area_frame)
        self.scroll_area_frame_layout.addStretch(0)
        self.scroll_area_frame_layout.setSpacing(self.fontMetrics().height())
        scroll_area.setWidget(scroll_area_frame)

        font = QtGui.QFont()
        font.setFamily("Consolas")
        font.setStyleHint(QtGui.QFont.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(round(font.pointSize() * 0.9))

        # Name label.
        self.name_label = QtWidgets.QLabel()
        self.name_label.setFont(font)
        self.name_label.setWordWrap(True)
        self.scroll_area_frame_layout.addWidget(self.name_label)

        # Comment label.
        self.comment_label = QtWidgets.QLabel()
        self.comment_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.comment_label.setWordWrap(True)
        self.comment_label.setFont(font)
        self.scroll_area_frame_layout.addWidget(self.comment_label)
        self.comment_label.hide()

        # Data editor.
        self.object_data_edit = None

        # Main layout.
        verticalLayout = QtWidgets.QVBoxLayout(self)
        verticalLayout.addWidget(self.button_add_object)
        verticalLayout.addWidget(self.button_remove_object)
        verticalLayout.addWidget(self.button_ground_object)
        verticalLayout.addWidget(self.more_buttons)
        verticalLayout.addWidget(scroll_area)

        self.reset_info()

    def reset_info(self, info="None selected"):
        self.name_label.setText(info)
        self.comment_label.setText("")
        self.comment_label.hide()

        if self.object_data_edit is not None:
            self.object_data_edit.deleteLater()
            self.object_data_edit = None

    def update_info(self):
        if self.object_data_edit is not None:
            self.object_data_edit.update_data()

    def set_info(self, obj, update3d, usedby=tuple()):
        if usedby:
            self.name_label.setText("Selected: {}\nUsed by: {}".format(
                type(obj).__name__, ", ".join(usedby)))
        else:
            self.name_label.setText("Selected: {}".format(type(obj).__name__))

        if self.object_data_edit is not None:
            self.object_data_edit.deleteLater()
            self.object_data_edit = None

        editor = choose_data_editor(obj)
        if editor is not None:
            self.object_data_edit = editor(self, obj)
            self.scroll_area_frame_layout.addWidget(self.object_data_edit)
            self.object_data_edit.emit_3d_update.connect(update3d)

        self.comment_label.setText("")
        self.comment_label.hide()

    def set_objectlist(self, objs):
        objectnames = []

        for obj in objs:
            if len(objectnames) < 25:
                if hasattr(obj, "name") and obj.name != 'null':
                    objectnames.append(obj.name)

        text = ''
        if objectnames:
            objectnames.sort()
            text = f"Selected objects: {', '.join(objectnames)}"
            diff = len(objs) - len(objectnames)
            if diff:
                text += f"\n...and {diff} more object{'s' if diff > 1 else ''}"
        elif objs:
            text = f"Selected objects: {len(objs)}"

        self.comment_label.setText(text)
        self.comment_label.setVisible(bool(text))

    def set_buttons(self, obj):
        self.more_buttons.add_buttons(obj)
