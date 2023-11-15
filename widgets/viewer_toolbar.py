import enum
import textwrap

from PySide6 import QtCore, QtGui, QtWidgets

from . import tooltip_list

_TOOL_TIPS = {
    ################################################################################################
    'Transform Gizmo':
    """
    Shows the transform gizmo on the selected object or objects.

    ---
    Shortcut: `T`
    """,
    ################################################################################################
    'Rotate Around Median Point':
    """
    If enabled, selected objects will be rotated around the median point. If disabled, each object
    will be rotated around its individual origin.
    """,
    ################################################################################################
    'Snapping':
    """
    Enables Snapping mode. When objects are translated, their position will be snapped to the
    closest snapping point, based on the chosen snapping strategy.

    This functionality requires visible geometry to work (i.e. a loaded collision file or model
    file).

    ---
    Shortcut: `V` (toggle)

    Shortcut: `Shift+V` (cycle through modes)
    """,
    ################################################################################################
    'Delete':
    """
    Deletes the currently selected objects.

    ---
    Shortcut: `Delete`
    """,
    ################################################################################################
    'Ground':
    """
    Moves the currently selected objects to the ground, which is defined as the closest, visible
    face in the vertical axis.

    This action requires visible geometry to work (i.e. a loaded collision file or model file).

    ---
    Shortcut: `G`
    """,
    ################################################################################################
    'Distribute':
    """
    Evenly distributes the selected objects between the two points defined by the first and last
    objects in the selection.

    At least three objects must be selected.
    """,
    ################################################################################################
    'Top-down View':
    """
    Shows the world from above, with a fixed camera orientation.

    ---
    Shortcut: `Ctrl+1`
    """,
    ################################################################################################
    '3D View':
    """
    Shows the world through a free camera with a transformable orientation.

    ---
    Shortcut: `Ctrl+2`
    """,
}


class ButtonPosition(enum.Enum):
    TOP = 0
    MIDDLE = 1
    BOTTOM = 2
    ISOLATED = 3


class ToolbarButtonMenu(QtWidgets.QMenu):

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent=parent)

    def showEvent(self, event: QtGui.QShowEvent):
        size = self.parent().size()
        local_position = QtCore.QPoint(size.width(), 0)
        position = self.parent().mapToGlobal(local_position)
        self.move(position)


class ToolbarButton(QtWidgets.QPushButton):

    def __init__(self, name, button_position=ButtonPosition.ISOLATED):
        super().__init__()

        self._menu = None

        self.setFlat(True)
        self.setAutoFillBackground(True)

        font_height = self.fontMetrics().height()
        size = int(font_height * 2.2)
        self.setFixedSize(size, size)

        size = int(font_height * 1.5)
        self.setIconSize(QtCore.QSize(size, size))

        tool_tip = tooltip_list.markdown_to_html(name, textwrap.dedent(_TOOL_TIPS.get(name, '')))
        self.setToolTip(tool_tip)

        r = font_height // 4
        border_style = ''
        if button_position == ButtonPosition.TOP:
            border_style = f'border-top-left-radius: {r}px; border-top-right-radius: {r}px;'
        elif button_position == ButtonPosition.BOTTOM:
            border_style = f'border-bottom-left-radius: {r}px; border-bottom-right-radius: {r}px;'
        elif button_position == ButtonPosition.ISOLATED:
            border_style = f'border-radius: {r}px;'
        else:
            border_style = 'border-radius: 0px;'

        self.setStyleSheet(f"""
            QPushButton::menu-indicator {{
                width: 0px;
            }}
            QPushButton {{
                background: #282828;
                {border_style}
            }}
            QPushButton:hover {{
                background: #363636;
                border: 1px solid #313131;
            }}
            QPushButton:pressed {{
                background: #202020;
                border: none;
            }}

            QPushButton:checked {{
                background: #0F4673;
            }}
            QPushButton:checked:hover {{
                background: #1D517B;
                border: 1px solid #164C77;
            }}
            QPushButton:checked:pressed {{
                background: #173E5E;
                border: none;
            }}
        """)

    def event(self, event):
        event_type = event.type()

        if event_type == QtCore.QEvent.Type.ToolTip:
            size = self.size()
            local_position = QtCore.QPoint(size.width() + ViewerToolbar.margin, -size.height() // 2)
            position = self.mapToGlobal(local_position)
            QtWidgets.QToolTip.showText(position, self.toolTip(), self)
            return True

        return super().event(event)

    def get_or_create_menu(self) -> ToolbarButtonMenu:
        if self._menu is None:
            self._menu = ToolbarButtonMenu(self)
            self.setMenu(self._menu)
        return self._menu

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self._set_opacity(1.0 if enabled else 0.6)

    def _set_opacity(self, opacity):
        effect = QtWidgets.QGraphicsOpacityEffect(self)
        effect.setOpacity(opacity)
        self.setGraphicsEffect(effect)


class ViewerToolbar(QtWidgets.QWidget):

    margin = None

    def __init__(self, parent: QtWidgets.QWidget = None):
        super().__init__(parent=parent)

        font_height = self.fontMetrics().height()
        margin = font_height // 3
        if ViewerToolbar.margin is None:
            ViewerToolbar.margin = margin
        self.move(margin, margin)

        layout = QtWidgets.QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        spacing = 1
        group_spacing = font_height // 2 - spacing

        layout.setSpacing(spacing)

        self.transform_gizmo_button = ToolbarButton('Transform Gizmo')
        self.transform_gizmo_button.setIcon(QtGui.QIcon('resources/icons/transform_gizmo.svg'))
        self.transform_gizmo_button.setCheckable(True)
        self.transform_gizmo_button.setChecked(True)
        layout.addWidget(self.transform_gizmo_button)

        self.rotate_around_median_point_button = ToolbarButton('Rotate Around Median Point')
        self.rotate_around_median_point_button.setIcon(
            QtGui.QIcon('resources/icons/rotate_around_median_point.svg'))
        self.rotate_around_median_point_button.setCheckable(True)
        self.rotate_around_median_point_button.setChecked(True)
        layout.addWidget(self.rotate_around_median_point_button)

        self.snapping_button = ToolbarButton('Snapping')
        self.snapping_button.setIcon(QtGui.QIcon('resources/icons/snapping.svg'))
        self.snapping_button.setCheckable(True)
        self.snapping_button.setChecked(False)
        layout.addWidget(self.snapping_button)

        layout.addSpacing(group_spacing)

        self.delete_button = ToolbarButton('Delete')
        self.delete_button.setIcon(QtGui.QIcon('resources/icons/delete.svg'))
        layout.addWidget(self.delete_button)

        self.ground_button = ToolbarButton('Ground')
        self.ground_button.setIcon(QtGui.QIcon('resources/icons/ground.svg'))
        layout.addWidget(self.ground_button)

        self.distribute_button = ToolbarButton('Distribute')
        self.distribute_button.setIcon(QtGui.QIcon('resources/icons/distribute.svg'))
        layout.addWidget(self.distribute_button)

        layout.addSpacing(group_spacing)

        self.view_topdown_button = ToolbarButton('Top-down View',
                                                 button_position=ButtonPosition.TOP)
        self.view_topdown_button.setIcon(QtGui.QIcon('resources/icons/view_topdown.svg'))
        self.view_topdown_button.setCheckable(True)
        self.view_topdown_button.setChecked(True)
        layout.addWidget(self.view_topdown_button)

        self.view_3d_button = ToolbarButton('3D View', button_position=ButtonPosition.BOTTOM)
        self.view_3d_button.setIcon(QtGui.QIcon('resources/icons/view_3d.svg'))
        self.view_3d_button.setCheckable(True)
        self.view_3d_button.setChecked(False)
        layout.addWidget(self.view_3d_button)

        def on_topdown_view_clicked(_checked):
            self.view_topdown_button.setChecked(True)
            self.view_3d_button.setChecked(False)

        self.view_topdown_button.clicked.connect(on_topdown_view_clicked)

        def on_3d_view_clicked(_checked):
            self.view_topdown_button.setChecked(False)
            self.view_3d_button.setChecked(True)

        self.view_3d_button.clicked.connect(on_3d_view_clicked)
