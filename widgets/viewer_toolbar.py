import enum
import json
import math
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
    ################################################################################################
    'Add Enemy Path':
    """
    If an existing enemy path or enemy path point is selected, the new enemy path will be inserted
    underneath; otherwise the enemy path will be appended.
    """,
    ################################################################################################
    'Add Enemy Path Points':
    """
    Enters insertion mode for enemy path points.

    Each click in the viewer will add a new enemy path point. Press `ESC` to leave insertion mode.

    If an existing enemy path or enemy path point is selected, the new enemy path point will be
    inserted underneath; otherwise the new enemy path point will be appended to the last enemy path.
    """,
    ################################################################################################
    'Add Checkpoint Group':
    """
    If an existing checkpoint group or checkpoint is selected, the new checkpoint group will be
    inserted underneath; otherwise the checkpoint group will be appended.
    """,
    ################################################################################################
    'Add Checkpoints':
    """
    Enters insertion mode for checkpoints.

    Each click in the viewer will add a new checkpoint. Press `ESC` to leave insertion mode.

    If an existing checkpoint group or checkpoint is selected, the new checkpoint will be inserted
    underneath; otherwise the new checkpoint will be appended to the last checkpoint group.
    """,
    ################################################################################################
    'Add Route':
    """
    If an existing route or route point is selected, the new route will be inserted underneath;
    otherwise the route will be appended.
    """,
    ################################################################################################
    'Add Route Points':
    """
    Enters insertion mode for route points.

    Each click in the viewer will add a new route point. Press `ESC` to leave insertion mode.

    If an existing route or route point is selected, the new route point will be inserted
    underneath; otherwise the new route point will be appended to the last route.
    """,
    ################################################################################################
    'Add Objects':
    """
    Enters insertion mode for objects.

    Each click in the viewer will add a new object. Press `ESC` to leave insertion mode.

    If an existing object is selected, the new object will be inserted underneath; otherwise the new
    object will be appended.
    """,
    ################################################################################################
    'Add Kart Start Points':
    """
    Enters insertion mode for kart start points.

    Each click in the viewer will add a new kart start point. Press `ESC` to leave insertion mode.

    If an existing kart start point is selected, the new kart start point will be inserted
    underneath; otherwise the new kart start point will be appended.
    """,
    ################################################################################################
    'Add Areas':
    """
    Enters insertion mode for areas.

    Each click in the viewer will add a new area. Press `ESC` to leave insertion mode.

    If an existing area is selected, the new area will be inserted underneath; otherwise the new
    area will be appended.
    """,
    ################################################################################################
    'Add Cameras':
    """
    Enters insertion mode for cameras.

    Each click in the viewer will add a new camera. Press `ESC` to leave insertion mode.

    If an existing camera is selected, the new camera will be inserted underneath; otherwise the new
    camera will be appended.
    """,
    ################################################################################################
    'Add Respawn Points':
    """
    Enters insertion mode for respawn points.

    Each click in the viewer will add a new respawn point. Press `ESC` to leave insertion mode.

    If an existing respawn point is selected, the new respawn point will be inserted underneath;
    otherwise the new respawn point will be appended.
    """,
    ################################################################################################
    'Add Light Param':
    """
    If an existing light param is selected, the new light param will be inserted underneath;
    otherwise the new light param will be appended.
    """,
    ################################################################################################
    'Add Minigame Param':
    """
    If an existing minigame param is selected, the new minigame param will be inserted underneath;
    otherwise the new minigame param will be appended.
    """,
}


def create_object_type_pixmap(canvas_size: int, directed: bool,
                              colors: 'tuple[tuple[int]]') -> QtGui.QPixmap:
    border = int(canvas_size * 0.12)
    size = canvas_size // 2 - border
    margin = (canvas_size - size) // 2

    pixmap = QtGui.QPixmap(canvas_size, canvas_size)
    pixmap.fill(QtCore.Qt.transparent)

    painter = QtGui.QPainter(pixmap)
    painter.setRenderHints(QtGui.QPainter.Antialiasing)

    pen = QtGui.QPen()
    pen.setJoinStyle(QtCore.Qt.RoundJoin)
    pen.setWidth(border)
    painter.setPen(pen)

    main_color = QtGui.QColor(colors[0][0], colors[0][1], colors[0][2])

    if directed:
        polygon = QtGui.QPolygonF((
            QtCore.QPointF(margin - size // 2, margin),
            QtCore.QPointF(margin - size // 2, margin + size),
            QtCore.QPointF(margin + size - size // 2, margin + size),
            QtCore.QPointF(margin + size + size - size // 2, margin + size - size // 2),
            QtCore.QPointF(margin + size - size // 2, margin),
        ))
        head = QtGui.QPolygonF((
            QtCore.QPointF(margin + size - size // 2 + size // 4, margin + size - size // 4),
            QtCore.QPointF(margin + size + size - size // 2, margin + size - size // 2),
            QtCore.QPointF(margin + size - size // 2 + size // 4, margin + size // 4),
        ))

        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(main_color)
        painter.drawPolygon(polygon)
        head_color = QtGui.QColor(9, 147, 0)
        painter.setBrush(head_color)
        painter.drawPolygon(head)

        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.transparent)
        painter.drawPolygon(polygon)
    else:
        POINT_COUNT = 30
        radius = size / 2.0 * 1.2
        points = [(math.cos(2.0 * math.pi / POINT_COUNT * x) * radius + radius,
                   math.sin(2.0 * math.pi / POINT_COUNT * x) * radius + radius)
                  for x in range(0, POINT_COUNT + 1)]
        points = [QtCore.QPointF(margin + x, margin + y) for x, y in points]
        polygon = QtGui.QPolygonF(points)

        if len(colors) > 1:
            secondary_color = QtGui.QColor(colors[1][0], colors[1][1], colors[1][2])
            painter.setBrush(secondary_color)
            painter.drawPolygon(polygon.translated(size // 3, size // 3))
            painter.setBrush(main_color)
            painter.drawPolygon(polygon.translated(-size // 3, -size // 3))
        else:
            painter.setBrush(main_color)
            painter.drawPolygon(polygon)

    del painter

    return pixmap


def create_object_type_icon(canvas_size: int,
                            directed: bool,
                            colors: 'tuple[tuple[int]]',
                            container=False) -> QtGui.QIcon:

    object_type_pixmap = create_object_type_pixmap(canvas_size, directed, colors)

    if container:
        painter = QtGui.QPainter(object_type_pixmap)

        container_pixmap = QtGui.QIcon('resources/icons/container.svg').pixmap(
            QtCore.QSize(canvas_size, canvas_size))
        painter.drawPixmap(0, 0, container_pixmap)

        del painter

    icon = QtGui.QIcon()
    icon.addPixmap(object_type_pixmap)
    return icon


class ButtonPosition(enum.Enum):
    TOP = 0
    MIDDLE = 1
    BOTTOM = 2
    ISOLATED = 3


class ButtonColor(enum.Enum):
    BLUE = 0
    GREEN = 1


class ToolbarButtonMenu(QtWidgets.QMenu):

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent=parent)

    def showEvent(self, event: QtGui.QShowEvent):
        _ = event
        size = self.parent().size()
        local_position = QtCore.QPoint(size.width(), 0)
        position = self.parent().mapToGlobal(local_position)
        self.move(position)


class ToolbarButton(QtWidgets.QPushButton):

    def __init__(self,
                 name,
                 button_position=ButtonPosition.ISOLATED,
                 button_color=ButtonColor.BLUE):
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

        style_sheet = f"""
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
        """
        if button_color == ButtonColor.BLUE:
            style_sheet += """
                QPushButton:checked {
                    background: #0F4673;
                }
                QPushButton:checked:hover {
                    background: #1D517B;
                    border: 1px solid #164C77;
                }
                QPushButton:checked:pressed {
                    background: #173E5E;
                    border: none;
                }
            """
        elif button_color == ButtonColor.GREEN:
            style_sheet += """
                QPushButton:checked {
                    background: #119A06;
                }
                QPushButton:checked:hover {
                    background: #28AD1E;
                    border: 1px solid #1EA713;
                }
                QPushButton:checked:pressed {
                    background: #0A8400;
                    border: none;
                }
            """
        self.setStyleSheet(style_sheet)

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

        self.setCursor(QtCore.Qt.ArrowCursor)

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

        layout.addSpacing(group_spacing)

        self.add_enemy_path_button = ToolbarButton('Add Enemy Path', ButtonPosition.TOP)
        self.add_enemy_path_points_button = ToolbarButton('Add Enemy Path Points',
                                                          ButtonPosition.MIDDLE, ButtonColor.GREEN)
        self.add_enemy_path_points_button.setCheckable(True)
        self.add_checkpoint_group_button = ToolbarButton('Add Checkpoint Group',
                                                         ButtonPosition.MIDDLE)
        self.add_checkpoints_button = ToolbarButton('Add Checkpoints', ButtonPosition.MIDDLE,
                                                    ButtonColor.GREEN)
        self.add_checkpoints_button.setCheckable(True)
        self.add_route_button = ToolbarButton('Add Route', ButtonPosition.MIDDLE)
        self.add_route_points_button = ToolbarButton('Add Route Points', ButtonPosition.MIDDLE,
                                                     ButtonColor.GREEN)
        self.add_route_points_button.setCheckable(True)
        self.add_objects_button = ToolbarButton('Add Objects', ButtonPosition.MIDDLE,
                                                ButtonColor.GREEN)
        self.add_objects_button.setCheckable(True)
        self.add_kart_start_points_button = ToolbarButton('Add Kart Start Points',
                                                          ButtonPosition.MIDDLE, ButtonColor.GREEN)
        self.add_kart_start_points_button.setCheckable(True)
        self.add_areas_button = ToolbarButton('Add Areas', ButtonPosition.MIDDLE, ButtonColor.GREEN)
        self.add_areas_button.setCheckable(True)
        self.add_cameras_button = ToolbarButton('Add Cameras', ButtonPosition.MIDDLE,
                                                ButtonColor.GREEN)
        self.add_cameras_button.setCheckable(True)
        self.add_respawn_points_button = ToolbarButton('Add Respawn Points', ButtonPosition.MIDDLE,
                                                       ButtonColor.GREEN)
        self.add_respawn_points_button.setCheckable(True)
        self.add_light_param_button = ToolbarButton('Add Light Param', ButtonPosition.MIDDLE)
        self.add_minigame_param_button = ToolbarButton('Add Minigame Param', ButtonPosition.BOTTOM)

        icon_size = self.add_minigame_param_button.iconSize().width()

        with open('lib/color_coding.json', 'r', encoding='utf-8') as f:
            colors = json.load(f)
            colors = {
                k: (round(r * 255), round(g * 255), round(b * 255))
                for k, (r, g, b, _a) in colors.items()
            }

        self.add_enemy_path_button.setIcon(
            create_object_type_icon(icon_size,
                                    directed=False,
                                    colors=[colors['EnemyPaths']],
                                    container=True))
        self.add_enemy_path_points_button.setIcon(
            create_object_type_icon(icon_size, directed=False, colors=[colors['EnemyPaths']]))
        self.add_checkpoint_group_button.setIcon(
            create_object_type_icon(icon_size,
                                    directed=False,
                                    colors=[colors['CheckpointLeft'], colors['CheckpointRight']],
                                    container=True))
        self.add_checkpoints_button.setIcon(
            create_object_type_icon(icon_size,
                                    directed=False,
                                    colors=[colors['CheckpointLeft'], colors['CheckpointRight']]))
        self.add_route_button.setIcon(
            create_object_type_icon(icon_size,
                                    directed=False,
                                    colors=[colors['UnassignedRoutes']],
                                    container=True))
        self.add_route_points_button.setIcon(
            create_object_type_icon(icon_size, directed=False, colors=[colors['UnassignedRoutes']]))
        self.add_objects_button.setIcon(
            create_object_type_icon(icon_size, directed=True, colors=[colors['Objects']]))
        self.add_kart_start_points_button.setIcon(
            create_object_type_icon(icon_size, directed=True, colors=[colors['StartPoints']]))
        self.add_areas_button.setIcon(
            create_object_type_icon(icon_size, directed=True, colors=[colors['Areas']]))
        self.add_cameras_button.setIcon(
            create_object_type_icon(icon_size, directed=True, colors=[colors['Camera']]))
        self.add_respawn_points_button.setIcon(
            create_object_type_icon(icon_size, directed=True, colors=[colors['Respawn']]))
        self.add_light_param_button.setIcon(
            create_object_type_icon(icon_size, directed=False, colors=[colors['LightParam']]))
        self.add_minigame_param_button.setIcon(
            create_object_type_icon(icon_size, directed=False, colors=[colors['MGParam']]))

        layout.addWidget(self.add_enemy_path_button)
        layout.addWidget(self.add_enemy_path_points_button)
        layout.addWidget(self.add_checkpoint_group_button)
        layout.addWidget(self.add_checkpoints_button)
        layout.addWidget(self.add_route_button)
        layout.addWidget(self.add_route_points_button)
        layout.addWidget(self.add_objects_button)
        layout.addWidget(self.add_kart_start_points_button)
        layout.addWidget(self.add_areas_button)
        layout.addWidget(self.add_cameras_button)
        layout.addWidget(self.add_respawn_points_button)
        layout.addWidget(self.add_light_param_button)
        layout.addWidget(self.add_minigame_param_button)

        self.add_button_group = QtWidgets.QButtonGroup(self)
        self.add_button_group.setExclusive(False)
        self.add_button_group.addButton(self.add_enemy_path_button)
        self.add_button_group.addButton(self.add_enemy_path_points_button)
        self.add_button_group.addButton(self.add_checkpoint_group_button)
        self.add_button_group.addButton(self.add_checkpoints_button)
        self.add_button_group.addButton(self.add_route_button)
        self.add_button_group.addButton(self.add_route_points_button)
        self.add_button_group.addButton(self.add_objects_button)
        self.add_button_group.addButton(self.add_kart_start_points_button)
        self.add_button_group.addButton(self.add_areas_button)
        self.add_button_group.addButton(self.add_cameras_button)
        self.add_button_group.addButton(self.add_respawn_points_button)
        self.add_button_group.addButton(self.add_light_param_button)
        self.add_button_group.addButton(self.add_minigame_param_button)
        self.add_button_group.buttonToggled.connect(self._on_add_button_group_buttonToggled)

    def _on_add_button_group_buttonToggled(self, button: QtWidgets.QAbstractButton, checked: bool):
        if checked:
            for b in self.add_button_group.buttons():
                if b is not button:
                    b.setChecked(False)
