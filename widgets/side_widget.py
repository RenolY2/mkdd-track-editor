import collections

from PySide6 import QtCore, QtWidgets, QtGui

from lib import libbol
from widgets.data_editor import choose_data_editor


class PikminSideWidget(QtWidgets.QWidget):

    def __init__(self, editor, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.boleditor = editor

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
        verticalLayout.addWidget(scroll_area)
        verticalLayout.setContentsMargins(0, 0, 0, 0)

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

    def set_info(self, objs, update3d, usedby=tuple()):
        if self.object_data_edit is not None:
            self.object_data_edit.deleteLater()
            self.object_data_edit = None

        editor = choose_data_editor(objs)
        if editor is not None:
            bol = self.boleditor.level_file
            self.object_data_edit = editor(self, bol, objs)
            self.object_data_edit.layout().addStretch()
            self.scroll_area_frame_layout.addWidget(self.object_data_edit)
            self.object_data_edit.emit_3d_update.connect(update3d)

        self.comment_label.setText("")
        self.comment_label.hide()

    def set_label(self, objs, usedby):
        names = collections.defaultdict(int)
        for obj in objs:
            name = type(obj).__name__
            if isinstance(obj, libbol.Camera):
                if obj.name and obj.name != 'null':
                    name += f' "{obj.name}"'
            elif isinstance(obj, libbol.Area):
                name = f'{libbol.AREA_TYPES[obj.area_type]} Area'
            elif isinstance(obj, libbol.MapObject):
                name = f'{libbol.OBJECTNAMES[obj.objectid]}'
            names[name] += 1

        text = 'Selected: ' if objs else ''
        text += ', '.join(
            [name if count == 1 else f'{name} (x{count})' for name, count in names.items()])

        if usedby:
            text += f'\nUsed by: {", ".join(usedby)}'

        self.name_label.setText(text)
