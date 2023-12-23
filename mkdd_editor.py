#!/usr/bin/env python3
"""
A tool for Mario Kart: Double Dash!! that can edit the BOL files that contain the course data (item
boxes, checkpoints, respawn points, etc.).
"""
import contextlib
import cProfile
import enum
import pickle
import platform
import pstats
import textwrap
import traceback
import weakref
import os
from timeit import default_timer
from copy import deepcopy, copy
from io import TextIOWrapper, BytesIO, StringIO
from math import sin, cos, atan2
import json
from PIL import Image

from PySide6 import QtCore, QtGui, QtWidgets

import py_obj

from lib import bti
from widgets.data_editor import choose_data_editor
from widgets.editor_widgets import catch_exception
from widgets.tree_view import LevelDataTreeView
from widgets.tooltip_list import markdown_to_html
import widgets.tree_view as tree_view
from configuration import (
    make_default_config,
    open_config_directory,
    read_config,
    save_cfg,
)

import mkdd_widgets # as mkddwidgets
from widgets import utils
from widgets.side_widget import PikminSideWidget
from widgets.editor_widgets import open_error_dialog, open_info_dialog, catch_exception_with_dialog
from mkdd_widgets import BolMapViewer, MODE_TOPDOWN, SnappingMode
from lib.libbol import BOL, MGEntry, Route, get_full_name
import lib.libbol as libbol
from lib.rarc import Archive
from lib.BCOllider import RacetrackCollision
from lib.model_rendering import TexturedModel, CollisionModel, Minimap
from widgets.editor_widgets import ErrorAnalyzer, ErrorAnalyzerButton, show_minimap_generator
from lib.dolreader import DolFile, read_float, write_float, read_load_immediate_r0, write_load_immediate_r0, UnmappedAddress
from widgets.file_select import FileSelect
from lib.bmd_render import clear_temp_folder, load_textured_bmd
from lib.game_visualizer import Game
from lib.vectors import Vector3


__version__ = '1.3'

APP_NAME = f'MKDD Track Editor {__version__}'


class SelectionHistorySpecials(enum.IntEnum):
    MINIMAP_CORNER_1 = -1001
    MINIMAP_CORNER_2 = -1002
    CHECKPOINT_START = -1003
    CHECKPOINT_END = -1004


RECENT_FILE_LIST_LENGTH = 20


def detect_dol_region(dol):
    try:
        dol.seek(0x803CDD38)
    except UnmappedAddress:
        pass
    else:
        if dol.read(5) == b"title":
            return "US"

    try:
        dol.seek(0x803D7B78)
    except UnmappedAddress:
        pass
    else:
        if dol.read(5) == b"title":
            return "PAL"

    try:
        dol.seek(0x803E8358)
    except UnmappedAddress:
        pass
    else:
        if dol.read(5) == b"title":
            return "JP"

    try:
        dol.seek(0x80419020)
    except UnmappedAddress:
        pass
    else:
        if dol.read(5) == b"title":
            return "US_DEBUG"


    raise RuntimeError("Unsupported DOL version/region")


def get_treeitem(root: QtWidgets.QTreeWidgetItem, obj):
    for i in range(root.childCount()):
        child = root.child(i)
        if child.bound_to == obj:
            return child
    return None


class UndoEntry:

    _cache = weakref.WeakValueDictionary()

    class _UndoCacheEntry:

        def __init__(self, bol_document, enemy_path_data):
            self.bol_document = bol_document
            self.enemy_path_data = enemy_path_data

    def __init__(self, bol_document: bytes, enemy_path_data: 'tuple[tuple[bool, int]]',
                 minimap_data: tuple, selected_items_data: tuple):
        self.bol_hash = hash((bol_document, enemy_path_data))

        # To avoid keeping track of duplicates of the BOL document (likely the case when the part
        # that changes in the undo entry is the selection data), a cache is used.
        if self.bol_hash not in UndoEntry._cache:
            self._cache_entry = UndoEntry._UndoCacheEntry(bol_document, enemy_path_data)
            UndoEntry._cache[self.bol_hash] = self._cache_entry
        else:
            self._cache_entry = UndoEntry._cache[self.bol_hash]

        self.bol_document = self._cache_entry.bol_document
        self.enemy_path_data = self._cache_entry.enemy_path_data
        self.minimap_data = minimap_data
        self.selected_items_data = selected_items_data

        self.hash = hash((self.bol_hash, self.minimap_data, self.selected_items_data))

    def __eq__(self, other) -> bool:
        return self.hash == other.hash


class GenEditor(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.level_file = BOL()
        self.dolphin = Game()

        self.undo_history: list[UndoEntry] = []
        self.redo_history: list[UndoEntry] = []
        self.undo_history_disabled_count: int  = 0

        try:
            self.configuration = read_config()
        except FileNotFoundError as e:
            print("No config file found, creating default config...")
            self.configuration = make_default_config()

        self.pathsconfig = self.configuration["default paths"]
        self.editorconfig = self.configuration["editor"]
        self.current_gen_path = None

        self.dolphin.show_target_enemy_path_points = self.editorconfig.get(
            'show_target_enemy_path_points', 'true') == 'true'
        self.dolphin.show_target_item_points = self.editorconfig.get('show_target_item_points',
                                                                     'true') == 'true'

        self._template_enemy_path = libbol.EnemyPointGroup.new()
        self._template_enemy_path_point = libbol.EnemyPoint.new()
        self._template_enemy_path_point.scale = 2000.0
        self._template_checkpoint_group = libbol.CheckpointGroup.new()
        self._template_checkpoint = libbol.Checkpoint.new()
        self._template_route = libbol.Route.new()
        self._template_route_point = libbol.RoutePoint.new()
        self._template_object = libbol.MapObject.new()
        self._template_kart_start_point = libbol.KartStartPoint.new()
        self._template_area = libbol.Area.new()
        self._template_area.scale *= 100.0
        self._template_camera = libbol.Camera.new()
        self._template_respawn_point = libbol.JugemPoint.new()
        self._template_light_param = libbol.LightParam.new()
        self._template_minigame_param = libbol.MGEntry.new()
        self._insertion_mode_type_name = None

        self.setup_ui()

        self.level_view.level_file = self.level_file
        self.level_view.set_editorconfig(self.configuration["editor"])
        self.level_view.visibility_menu = self.visibility_menu

        self.collision_area_dialog = None

        self.current_coordinates = None

        self._window_title = ""
        self._user_made_change = False
        self._justupdatingselectedobject = False

        self.bco_coll = None
        self.loaded_archive = None
        self.loaded_archive_file = None
        self.next_checkpoint_start_position = None

        self._dontselectfromtree = False

        self.level_view.dolphin = self.dolphin

        self.restore_geometry()

        self.fullscreen.setChecked(
            bool(QtCore.Qt.WindowFullScreen & self.windowState()))

        self.undo_history.append(self.generate_undo_entry())

        self.leveldatatreeview.set_objects(self.level_file)
        self.leveldatatreeview.bound_to_group(self.level_file)

        self.setAcceptDrops(True)

    def save_geometry(self):
        if "geometry" not in self.configuration:
            self.configuration["geometry"] = {}
        geo_config = self.configuration["geometry"]

        def to_base64(byte_array: QtCore.QByteArray) -> str:
            return bytes(byte_array.toBase64()).decode(encoding='ascii')

        geo_config["window_geometry"] = to_base64(self.saveGeometry())
        geo_config["window_state"] = to_base64(self.saveState())
        geo_config["window_splitter"] = to_base64(self.horizontalLayout.saveState())

        if self.collision_area_dialog is not None:
            geo_config["collision_window_geometry"] = to_base64(
                self.collision_area_dialog.saveGeometry())

        save_cfg(self.configuration)

    def restore_geometry(self):
        if "geometry" not in self.configuration:
            return
        geo_config = self.configuration["geometry"]

        def to_byte_array(byte_array: str) -> QtCore.QByteArray:
            return QtCore.QByteArray.fromBase64(byte_array.encode(encoding='ascii'))

        if "window_geometry" in geo_config:
            self.restoreGeometry(to_byte_array(geo_config["window_geometry"]))
        if "window_state" in geo_config:
            self.restoreState(to_byte_array(geo_config["window_state"]))
        if "window_splitter" in geo_config:
            self.horizontalLayout.restoreState(to_byte_array(geo_config["window_splitter"]))

    def closeEvent(self, event: QtGui.QCloseEvent):
        self.save_geometry()

        if self._user_made_change:
            msgbox = QtWidgets.QMessageBox(self)
            size = self.fontMetrics().height() * 3
            msgbox.setIconPixmap(QtGui.QIcon('resources/warning.svg').pixmap(size, size))
            msgbox.setWindowTitle("Unsaved Changes")
            msgbox.setText('Are you sure you want to exit the application?')
            msgbox.addButton('Cancel', QtWidgets.QMessageBox.RejectRole)
            exit_button = msgbox.addButton('Exit', QtWidgets.QMessageBox.DestructiveRole)
            msgbox.exec()
            if msgbox.clickedButton() != exit_button:
                event.ignore()
                return

        super().closeEvent(event)

    @catch_exception
    def reset(self):
        self.next_checkpoint_start_position = None
        self.loaded_archive = None
        self.loaded_archive_file = None
        self.level_view.reset()

        self.current_coordinates = None

        self.current_gen_path = None
        self.pik_control.reset_info()

        self._window_title = ""
        self._user_made_change = False

    def set_base_window_title(self, name):
        self._window_title = name
        if name != "":
            self.setWindowTitle(f"{APP_NAME} - {name}")
        else:
            self.setWindowTitle(f"{APP_NAME}")

    def set_has_unsaved_changes(self, hasunsavedchanges):
        if hasunsavedchanges and not self._user_made_change:
            self._user_made_change = True

            if self._window_title != "":
                self.setWindowTitle(f"{APP_NAME} [Unsaved Changes] - {self._window_title}")
            else:
                self.setWindowTitle(f"{APP_NAME} [Unsaved Changes]")
        elif not hasunsavedchanges and self._user_made_change:
            self._user_made_change = False
            if self._window_title != "":
                self.setWindowTitle(f"{APP_NAME} - {self._window_title}")
            else:
                self.setWindowTitle(f"{APP_NAME}")

    def generate_undo_entry(self) -> UndoEntry:
        bol_document = self.level_file.to_bytes()

        # List containing a tuple with the emptiness and ID of each of the enemy paths.
        enemy_paths = self.level_file.enemypointgroups.groups
        enemy_path_data = tuple((not path.points, path.id) for path in enemy_paths)

        minimap = self.level_view.minimap
        minimap_data = (
            minimap.corner1.x, minimap.corner1.y, minimap.corner1.z,
            minimap.corner2.x, minimap.corner2.y, minimap.corner2.z,
            minimap.orientation
        )

        # Model indexes would be quickly invalidated, so they are not used. Instead, row indexes
        # (of the item, and all its ancestors) are tracked.
        selected_items_data = []
        for model_index in self.leveldatatreeview.selectionModel().selectedIndexes():
            selected_item_data = [model_index.row()]
            model_index_parent = model_index.parent()
            while model_index_parent.isValid():
                selected_item_data.append(model_index_parent.row())
                model_index_parent = model_index_parent.parent()
            selected_items_data.append(tuple(selected_item_data))
        if minimap.corner1 in self.level_view.selected_positions:
            selected_items_data.append((SelectionHistorySpecials.MINIMAP_CORNER_1, ))
        if minimap.corner2 in self.level_view.selected_positions:
            selected_items_data.append((SelectionHistorySpecials.MINIMAP_CORNER_2, ))
        for i, checkpoint_groups in enumerate(self.level_file.checkpoints.groups):
            for j, checkpoint in enumerate(checkpoint_groups.points):
                if checkpoint.start in self.level_view.selected_positions:
                    selected_items_data.append((SelectionHistorySpecials.CHECKPOINT_START, i, j))
                if checkpoint.end in self.level_view.selected_positions:
                    selected_items_data.append((SelectionHistorySpecials.CHECKPOINT_END, i, j))
        selected_items_data = tuple(selected_items_data)

        return UndoEntry(bol_document, enemy_path_data, minimap_data, selected_items_data)

    def load_top_undo_entry(self):
        if not self.undo_history:
            return

        current_undo_entry = self.generate_undo_entry()
        undo_entry = self.undo_history[-1]

        bol_changed = current_undo_entry.bol_hash != undo_entry.bol_hash

        self.level_file = BOL.from_bytes(undo_entry.bol_document)

        # The BOL document cannot store information on empty enemy paths; this information is
        # sourced from a separate list.
        bol_enemy_paths = list(self.level_file.enemypointgroups.groups)
        self.level_file.enemypointgroups.groups.clear()
        enemy_path_data = undo_entry.enemy_path_data
        for empty, enemy_path_id in enemy_path_data:
            if empty:
                empty_enemy_path = libbol.EnemyPointGroup()
                empty_enemy_path.id = enemy_path_id
                self.level_file.enemypointgroups.groups.append(empty_enemy_path)
            else:
                enemy_path = bol_enemy_paths.pop(0)
                assert enemy_path.id == enemy_path_id
                self.level_file.enemypointgroups.groups.append(enemy_path)

        # Clear existing selection.
        with QtCore.QSignalBlocker(self.leveldatatreeview):
            for item in self.leveldatatreeview.selectedItems():
                item.setSelected(False)

        self.level_view.level_file = self.level_file
        self.leveldatatreeview.set_objects(self.level_file)

        minimap = self.level_view.minimap
        minimap.corner1.x = undo_entry.minimap_data[0]
        minimap.corner1.y = undo_entry.minimap_data[1]
        minimap.corner1.z = undo_entry.minimap_data[2]
        minimap.corner2.x = undo_entry.minimap_data[3]
        minimap.corner2.y = undo_entry.minimap_data[4]
        minimap.corner2.z = undo_entry.minimap_data[5]
        minimap.orientation = undo_entry.minimap_data[6]

        self.level_view.selected = []
        self.level_view.selected_positions = []
        self.level_view.selected_rotations = []

        # Restore the selection that was current when the undo entry was produced.
        items_to_select = []
        with QtCore.QSignalBlocker(self.leveldatatreeview):
            for selected_item_data in undo_entry.selected_items_data:
                # Deal with special cases that are not linked to the tree view first.
                if selected_item_data[0] in (SelectionHistorySpecials.MINIMAP_CORNER_1,
                                             SelectionHistorySpecials.MINIMAP_CORNER_2):
                    if minimap not in self.level_view.selected:
                        self.level_view.selected.append(minimap)
                    if selected_item_data[0] == SelectionHistorySpecials.MINIMAP_CORNER_1:
                        self.level_view.selected_positions.append(minimap.corner1)
                    else:
                        self.level_view.selected_positions.append(minimap.corner2)
                    continue
                if selected_item_data[0] in (SelectionHistorySpecials.CHECKPOINT_START,
                                             SelectionHistorySpecials.CHECKPOINT_END):
                    i, j = selected_item_data[1:]
                    checkpoint_group = self.level_file.checkpoints.groups[i]
                    checkpoint = checkpoint_group.points[j]
                    if checkpoint not in self.level_view.selected:
                        self.level_view.selected.append(checkpoint)
                    if selected_item_data[0] == SelectionHistorySpecials.CHECKPOINT_START:
                        self.level_view.selected_positions.append(checkpoint.start)
                    else:
                        self.level_view.selected_positions.append(checkpoint.end)
                    continue

                item = self.leveldatatreeview.invisibleRootItem()
                for row in reversed(selected_item_data):
                    item = item.child(row)
                item.setSelected(True)
                if hasattr(item, 'bound_to') and isinstance(item.bound_to, libbol.Checkpoint):
                    # Handled as a special case.
                    continue
                items_to_select.append(item)
        self.tree_select_object(items_to_select, clear_existing_selection=False)

        self.update_3d()
        self.pik_control.update_info()

        if bol_changed:
            self.set_has_unsaved_changes(True)
            self.error_analyzer_button.analyze_bol(self.level_file)

    def on_undo_action_triggered(self):
        if len(self.undo_history) > 1:
            self.redo_history.insert(0, self.undo_history.pop())
            self.update_undo_redo_actions()
            self.load_top_undo_entry()

    def on_redo_action_triggered(self):
        if self.redo_history:
            self.undo_history.append(self.redo_history.pop(0))
            self.update_undo_redo_actions()
            self.load_top_undo_entry()

    def on_document_potentially_changed(self, update_unsaved_changes=True):
        # Early out if undo history is temporarily disabled.
        if self.undo_history_disabled_count:
            return

        undo_entry = self.generate_undo_entry()

        if self.undo_history[-1] != undo_entry:
            bol_changed = self.undo_history[-1].bol_hash != undo_entry.bol_hash

            self.undo_history.append(undo_entry)
            self.redo_history.clear()
            self.update_undo_redo_actions()

            if bol_changed:
                if update_unsaved_changes:
                    self.set_has_unsaved_changes(True)

                self.error_analyzer_button.analyze_bol(self.level_file)

    def update_undo_redo_actions(self):
        self.undo_action.setEnabled(len(self.undo_history) > 1)
        self.redo_action.setEnabled(bool(self.redo_history))

    @contextlib.contextmanager
    def undo_history_disabled(self):
        self.undo_history_disabled_count += 1
        try:
            yield
        finally:
            self.undo_history_disabled_count -= 1

        self.on_document_potentially_changed()

    @catch_exception_with_dialog
    def do_goto_action(self, item, index):
        _ = index
        self.tree_select_object([item])
        self.frame_selection(adjust_zoom=False)

    def frame_selection(self, adjust_zoom):
        selected_only = bool(self.level_view.selected_positions)
        minx, miny, minz, maxx, maxy, maxz = self.compute_objects_extent(selected_only)

        # Center of the extent.
        x = (maxx + minx) / 2
        y = (maxy + miny) / 2
        z = (maxz + minz) / 2

        if self.level_view.mode == MODE_TOPDOWN:
            self.level_view.offset_z = -z
            self.level_view.offset_x = -x

            if adjust_zoom:
                if self.level_view.canvas_width > 0 and self.level_view.canvas_height > 0:
                    MARGIN = 2000
                    deltax = maxx - minx + MARGIN
                    deltay = maxz - minz + MARGIN
                    hzoom = deltax / self.level_view.canvas_width * 10
                    vzoom = deltay / self.level_view.canvas_height * 10
                    DEFAULT_ZOOM = 80
                    self.level_view._zoom_factor = max(hzoom, vzoom, DEFAULT_ZOOM)
        else:
            look = self.level_view.camera_direction

            if adjust_zoom:
                MARGIN = 3000
                deltax = maxx - minx + MARGIN
                fac = deltax
            else:
                fac = 5000

            self.level_view.camera_z = -(z + look.y * fac)
            self.level_view.camera_x = x - look.x * fac
            self.level_view.camera_height = y - look.z * fac

        self.level_view.do_redraw()

    def compute_objects_extent(self, selected_only):
        extent = []

        def extend(position):
            if not extent:
                extent.extend([position.x, position.y, position.z,
                               position.x, position.y, position.z])
                return

            extent[0] = min(extent[0], position.x)
            extent[1] = min(extent[1], position.y)
            extent[2] = min(extent[2], position.z)
            extent[3] = max(extent[3], position.x)
            extent[4] = max(extent[4], position.y)
            extent[5] = max(extent[5], position.z)

        if selected_only:
            for selected_position in self.level_view.selected_positions:
                extend(selected_position)
            return tuple(extent) or (0, 0, 0, 0, 0, 0)

        if self.visibility_menu.enemyroute.is_visible():
            for enemy_path in self.level_file.enemypointgroups.groups:
                for enemy_path_point in enemy_path.points:
                    extend(enemy_path_point.position)

        visible_objectroutes = self.visibility_menu.objectroutes.is_visible()
        visible_cameraroutes = self.visibility_menu.cameraroutes.is_visible()
        visible_unassignedroutes = self.visibility_menu.unassignedroutes.is_visible()

        if visible_objectroutes or visible_cameraroutes or visible_unassignedroutes:
            camera_routes = set(camera.route for camera in self.level_file.cameras)
            object_routes = set(obj.route for obj in self.level_file.objects.objects)
            assigned_routes = camera_routes.union(object_routes)

            for object_route in self.level_file.routes:
                if (not ((object_route in object_routes and visible_objectroutes) or
                         (object_route in camera_routes and visible_cameraroutes) or
                         (object_route not in assigned_routes and visible_unassignedroutes))):
                    continue
                for object_route_point in object_route.points:
                    extend(object_route_point.position)

        if self.visibility_menu.checkpoints.is_visible():
            for checkpoint_group in self.level_file.checkpoints.groups:
                for checkpoint in checkpoint_group.points:
                    extend(checkpoint.start)
                    extend(checkpoint.end)
        if self.visibility_menu.objects.is_visible():
            for object_ in self.level_file.objects.objects:
                extend(object_.position)
        if self.visibility_menu.areas.is_visible():
            for area in self.level_file.areas.areas:
                extend(area.position)
        if self.visibility_menu.cameras.is_visible():
            for camera in self.level_file.cameras:
                extend(camera.position)
        if self.visibility_menu.respawnpoints.is_visible():
            for respawn_point in self.level_file.respawnpoints:
                extend(respawn_point.position)
        if self.visibility_menu.kartstartpoints.is_visible():
            for karts_point in self.level_file.kartpoints.positions:
                extend(karts_point.position)
        if (self.level_view.minimap is not None and self.level_view.minimap.is_available()
                and self.visibility_menu.minimap.is_visible()):
            extend(self.level_view.minimap.corner1)
            extend(self.level_view.minimap.corner2)

        if self.level_view.collision is not None and self.level_view.collision.extent is not None:
            min_x, min_y, min_z, max_x, max_y, max_z = self.level_view.collision.extent
            min_y, min_z, max_y, max_z = min_z, -max_y, max_z, -min_y

            if extent:
                extent[0] = min(extent[0], min_x)
                extent[1] = min(extent[1], min_y)
                extent[2] = min(extent[2], min_z)
                extent[3] = max(extent[3], max_x)
                extent[4] = max(extent[4], max_y)
                extent[5] = max(extent[5], max_z)
            else:
                extent.extend([min_x, min_y, min_z, max_x, max_y, max_z])

        return tuple(extent) or (0, 0, 0, 0, 0, 0)

    def tree_select_arrowkey(self):
        self.tree_select_object(self.leveldatatreeview.selectedItems())

    def tree_select_object(self, items, clear_existing_selection=True):
        if clear_existing_selection:
            self.level_view.selected = []
            self.level_view.selected_positions = []
            self.level_view.selected_rotations = []

        for item in items:
            if isinstance(item, (tree_view.CameraEntry, tree_view.RespawnEntry, tree_view.AreaEntry,
                                 tree_view.ObjectEntry, tree_view.KartpointEntry,
                                 tree_view.EnemyRoutePoint, tree_view.ObjectRoutePoint)):
                bound_to = item.bound_to
                self.level_view.selected.append(bound_to)
                self.level_view.selected_positions.append(bound_to.position)

                if hasattr(bound_to, "rotation"):
                    self.level_view.selected_rotations.append(bound_to.rotation)

            elif isinstance(item, tree_view.Checkpoint):
                bound_to = item.bound_to
                self.level_view.selected.append(bound_to)
                self.level_view.selected_positions.extend((bound_to.start, bound_to.end))
            elif isinstance(item, (
                    tree_view.EnemyPointGroup,
                    tree_view.CheckpointGroup,
                    tree_view.ObjectPointGroup,
            )):
                self.level_view.selected.append(item.bound_to)
            elif isinstance(item, tree_view.BolHeader) and self.level_file is not None:
                self.level_view.selected.append(self.level_file)
            elif isinstance(item, (tree_view.LightParamEntry, tree_view.MGEntry)):
                self.level_view.selected.append(item.bound_to)

        self.level_view.gizmo.move_to_average(self.level_view.selected_positions,
                                              self.level_view.selected_rotations)
        self.level_view.do_redraw()
        self.action_update_info()

    def setup_ui(self):
        self.resize(1000, 800)
        self.set_base_window_title("")

        self.setup_ui_menubar()
        self.setup_ui_toolbar()

        #self.centralwidget = QWidget(self)
        #self.centralwidget.setObjectName("centralwidget")

        self.horizontalLayout = QtWidgets.QSplitter()
        self.centralwidget = self.horizontalLayout
        self.setCentralWidget(self.horizontalLayout)
        self.leveldatatreeview = LevelDataTreeView(self, self.centralwidget)
        #self.leveldatatreeview.itemClicked.connect(self.tree_select_object)
        self.leveldatatreeview.itemDoubleClicked.connect(self.do_goto_action)
        self.leveldatatreeview.itemSelectionChanged.connect(self.tree_select_arrowkey)

        self.level_view = BolMapViewer(int(self.editorconfig.get("multisampling", 8)),
                                       self.centralwidget)
        self.level_view.editor = self

        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalLayout.addWidget(self.leveldatatreeview)
        self.horizontalLayout.addWidget(self.level_view)
        self.leveldatatreeview.resize(200, self.leveldatatreeview.height())

        self.pik_control = PikminSideWidget(self)
        self.horizontalLayout.addWidget(self.pik_control)

        self.snapping_toggle_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_V), self)
        self.snapping_toggle_shortcut.activated.connect(self.level_view.toggle_snapping)
        self.snapping_cycle_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.QKeyCombination(QtCore.Qt.ShiftModifier, QtCore.Qt.Key_V)),
            self)
        self.snapping_cycle_shortcut.activated.connect(self.level_view.cycle_snapping_mode)

        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_G), self).activated.connect(self.action_ground_objects)
        self.statusbar = QtWidgets.QStatusBar(self)
        self.statusbar.setObjectName("statusbar")
        self.setStatusBar(self.statusbar)

        self.error_analyzer_button = ErrorAnalyzerButton()
        self.error_analyzer_button.clicked.connect(lambda _checked: self.analyze_for_mistakes())
        self.statusbar.addPermanentWidget(self.error_analyzer_button)

        self.connect_actions()

    @catch_exception_with_dialog
    def setup_ui_menubar(self):
        self.menubar = QtWidgets.QMenuBar(self)
        self.file_menu = QtWidgets.QMenu(self)
        self.file_menu.setTitle("File")

        save_file_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.QKeyCombination(QtCore.Qt.ControlModifier, QtCore.Qt.Key_V)),
            self.file_menu)
        save_file_shortcut.activated.connect(self.button_save_level)

        self.file_load_action = QtGui.QAction("Load", self)
        self.file_load_recent_menu = QtWidgets.QMenu("Load Recent", self)
        self.save_file_action = QtGui.QAction("Save", self)
        self.save_file_as_action = QtGui.QAction("Save As", self)
        self.save_file_action.setShortcut("Ctrl+S")
        self.file_load_action.setShortcut("Ctrl+O")
        self.save_file_as_action.setShortcut("Ctrl+Alt+S")

        self.save_file_copy_as_action = QtGui.QAction("Save Copy As", self)
        open_config_dir_action = QtGui.QAction('Open Configuration Directory...', self)
        quit_action = QtGui.QAction('Quit', self)

        self.file_load_action.triggered.connect(self.button_load_level)
        self.save_file_action.triggered.connect(self.button_save_level)
        self.save_file_as_action.triggered.connect(self.button_save_level_as)
        self.save_file_copy_as_action.triggered.connect(self.button_save_level_copy_as)
        open_config_dir_action.triggered.connect(open_config_directory)
        quit_action.triggered.connect(self.close)

        self.file_menu.addAction(self.file_load_action)
        self.file_menu.addMenu(self.file_load_recent_menu)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.save_file_action)
        self.file_menu.addAction(self.save_file_as_action)
        self.file_menu.addAction(self.save_file_copy_as_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(open_config_dir_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(quit_action)

        self.file_menu.aboutToShow.connect(self.on_file_menu_aboutToShow)

        self.edit_menu = QtWidgets.QMenu(self)
        self.edit_menu.setTitle("Edit")
        self.undo_action = self.edit_menu.addAction('Undo')
        self.undo_action.setShortcut(QtGui.QKeySequence('Ctrl+Z'))
        self.undo_action.triggered.connect(self.on_undo_action_triggered)
        self.redo_action = self.edit_menu.addAction('Redo')
        self.redo_action.setShortcuts([
            QtGui.QKeySequence('Ctrl+Shift+Z'),
            QtGui.QKeySequence('Ctrl+Y'),
        ])
        self.redo_action.triggered.connect(self.on_redo_action_triggered)
        self.update_undo_redo_actions()

        self.edit_menu.addSeparator()
        self.cut_action = self.edit_menu.addAction("Cut")
        self.cut_action.setShortcut(QtGui.QKeySequence('Ctrl+X'))
        self.cut_action.triggered.connect(self.on_cut_action_triggered)
        self.copy_action = self.edit_menu.addAction("Copy")
        self.copy_action.setShortcut(QtGui.QKeySequence('Ctrl+C'))
        self.copy_action.triggered.connect(self.on_copy_action_triggered)
        self.paste_action = self.edit_menu.addAction("Paste")
        self.paste_action.setShortcut(QtGui.QKeySequence('Ctrl+V'))
        self.paste_action.triggered.connect(self.on_paste_action_triggered)

        # ---- Visibility
        self.visibility_menu = mkdd_widgets.FilterViewMenu(self)
        self.visibility_menu.filter_update.connect(self.on_filter_update)
        filters = self.editorconfig["filter_view"].split(",")
        for object_toggle in self.visibility_menu.get_entries():
            if object_toggle.action_view_toggle.text() in filters:
                object_toggle.action_view_toggle.blockSignals(True)
                object_toggle.action_view_toggle.setChecked(False)
                object_toggle.action_view_toggle.blockSignals(False)
            if object_toggle.action_select_toggle.text() in filters:
                object_toggle.action_select_toggle.blockSignals(True)
                object_toggle.action_select_toggle.setChecked(False)
                object_toggle.action_select_toggle.blockSignals(False)

        # ------ Collision Menu
        self.collision_menu = QtWidgets.QMenu(self.menubar)
        self.collision_menu.setTitle("Geometry")

        self.choose_default_collision = QtWidgets.QMenu("Choose Autoloaded Geometry", self)
        self.collision_menu.addMenu(self.choose_default_collision)
        self.auto_load_choose = self.choose_default_collision.addAction("Always Ask")
        self.auto_load_choose.setCheckable(True)
        self.auto_load_choose.setChecked(self.editorconfig.get("addi_file_on_load") == "Choose")
        self.auto_load_choose.triggered.connect(lambda: self.on_default_geometry_changed("Choose"))
        self.auto_load_bco = self.choose_default_collision.addAction("BCO")
        self.auto_load_bco.setCheckable(True)
        self.auto_load_bco.setChecked(self.editorconfig.get("addi_file_on_load") == "BCO")
        self.auto_load_bco.triggered.connect(lambda: self.on_default_geometry_changed("BCO"))
        self.auto_load_bmd = self.choose_default_collision.addAction("BMD")
        self.auto_load_bmd.setCheckable(True)
        self.auto_load_bmd.setChecked(self.editorconfig.get("addi_file_on_load") == "BMD")
        self.auto_load_bmd.triggered.connect(lambda: self.on_default_geometry_changed("BMD"))
        self.auto_load_none = self.choose_default_collision.addAction("Nothing")
        self.auto_load_none.setCheckable(True)
        self.auto_load_none.setChecked(self.editorconfig.get("addi_file_on_load") == "None")
        self.auto_load_none.triggered.connect(lambda: self.on_default_geometry_changed("None"))
        if self.editorconfig.get("addi_file_on_load") not in ("BCO", "BMD", "None", "Choose"):
            self.on_default_geometry_changed("Choose")

        self.collision_menu.addSeparator()
        self.collision_load_bco_action = QtGui.QAction("Load BCO", self)
        self.collision_load_bco_action.triggered.connect(self.button_load_collision_bco)
        self.collision_menu.addAction(self.collision_load_bco_action)
        self.collision_load_bmd_action = QtGui.QAction("Load BMD", self)
        self.collision_load_bmd_action.triggered.connect(self.button_load_collision_bmd)
        self.collision_menu.addAction(self.collision_load_bmd_action)
        self.collision_load_obj_action = QtGui.QAction("Load OBJ", self)
        self.collision_load_obj_action.triggered.connect(self.button_load_collision_obj)
        self.collision_menu.addAction(self.collision_load_obj_action)
        self.clear_current_collision = QtGui.QAction("Clear Current Model", self)
        self.clear_current_collision.triggered.connect(self.clear_collision)
        self.collision_menu.addAction(self.clear_current_collision)

        self.collision_menu.addSeparator()
        cull_faces_action = self.collision_menu.addAction("Cull Faces")
        cull_faces_action.setCheckable(True)
        cull_faces_action.setChecked(self.editorconfig.get("cull_faces") == "True")
        cull_faces_action.triggered.connect(self.on_cull_faces_triggered)
        self.choose_bco_area = QtGui.QAction("Collision Areas (BCO)")
        self.choose_bco_area.triggered.connect(self.action_choose_bco_area)
        self.collision_menu.addAction(self.choose_bco_area)
        self.choose_bco_area.setShortcut("Ctrl+K")

        # ------- Tools Menu
        self.tools_menu = QtWidgets.QMenu(self.menubar)
        self.tools_menu.setTitle("Tools")

        snapping_menu_tool_tip = markdown_to_html(
            'Snapping',
            'Press **V** to toggle snapping on and off. '
            'Press **Shift+V** to cycle through snapping modes.',
        )
        self.snapping_menu = self.tools_menu.addMenu('Snapping\tV')
        self.snapping_menu.setToolTipsVisible(True)
        self.snapping_menu.aboutToShow.connect(self.on_snapping_menu_aboutToShow)
        self.snapping_menu.addAction('Disabled')
        for snapping_mode in SnappingMode:
            self.snapping_menu.addAction(f'Snap to {snapping_mode.value}').setObjectName(
                snapping_mode.name)
        self.snapping_menu_action_group = QtGui.QActionGroup(self)
        for action in self.snapping_menu.actions():
            action.triggered.connect(self.on_snapping_menu_action_triggered)
            action.setCheckable(True)
            action.setToolTip(snapping_menu_tool_tip)
            self.snapping_menu_action_group.addAction(action)

        self.analyze_action = QtGui.QAction("Analyze for common mistakes", self)
        self.analyze_action.triggered.connect(self.analyze_for_mistakes)
        self.tools_menu.addAction(self.analyze_action)

        self.show_code_patch_fields_action = QtGui.QAction("Show Code Patch-Dependent Fields (🧩)")
        self.show_code_patch_fields_action.setCheckable(True)
        self.show_code_patch_fields_action.setChecked(
            bool(self.editorconfig.get('show_code_patch_fields') == 'true'))

        def on_show_code_patch_fields_triggered(checked):
            self.editorconfig['show_code_patch_fields'] = 'true' if checked else 'false'
            self.action_update_info()

        self.show_code_patch_fields_action.triggered[bool].connect(
            on_show_code_patch_fields_triggered)

        self.tools_menu.addAction(self.show_code_patch_fields_action)

        self.tools_menu.addSeparator()
        self.rotation_mode = QtGui.QAction("Rotate Around Median Point", self)
        self.rotation_mode.setCheckable(True)
        self.rotation_mode.setChecked(True)
        self.tools_menu.addAction(self.rotation_mode)


        # -------- Minimap Menu
        self.minimap_menu = QtWidgets.QMenu(self.menubar)
        self.minimap_menu.setTitle("Minimap")
        load_minimap = QtGui.QAction("Load Minimap Image", self)
        save_minimap_png = QtGui.QAction("Save Minimap Image as PNG", self)
        save_minimap_bti = QtGui.QAction("Save Minimap Image as BTI", self)
        load_coordinates_dol = QtGui.QAction("Load Data from DOL", self)
        save_coordinates_dol = QtGui.QAction("Save Data to DOL", self)
        load_coordinates_json = QtGui.QAction("Load Data from JSON", self)
        save_coordinates_json = QtGui.QAction("Save Data to JSON", self)
        minimap_generator_action = QtGui.QAction("Minimap Generator", self)
        minimap_generator_action.setShortcut("Ctrl+M")


        load_minimap.triggered.connect(self.action_load_minimap_image)
        save_minimap_png.triggered.connect(
            lambda checked: self.action_save_minimap_image(checked, 'png'))
        save_minimap_bti.triggered.connect(
            lambda checked: self.action_save_minimap_image(checked, 'bti'))
        load_coordinates_dol.triggered.connect(self.action_load_dol)
        save_coordinates_dol.triggered.connect(self.action_save_to_dol)
        load_coordinates_json.triggered.connect(self.action_load_coordinates_json)
        save_coordinates_json.triggered.connect(self.action_save_coordinates_json)
        minimap_generator_action.triggered.connect(self.minimap_generator_action)
        self.minimap_menu.addAction(load_minimap)
        self.minimap_menu.addAction(save_minimap_png)
        self.minimap_menu.addAction(save_minimap_bti)
        self.minimap_menu.addSeparator()
        self.minimap_menu.addAction(load_coordinates_dol)
        self.minimap_menu.addAction(save_coordinates_dol)
        self.minimap_menu.addAction(load_coordinates_json)
        self.minimap_menu.addAction(save_coordinates_json)
        self.minimap_menu.addSeparator()
        self.minimap_menu.addAction(minimap_generator_action)

        #View
        self.view_menu = QtWidgets.QMenu(self.menubar)
        self.view_menu.setTitle("View")
        self.frame_action = QtGui.QAction("Frame Selection/All", self)
        self.frame_action.triggered.connect(
            lambda _checked: self.frame_selection(adjust_zoom=True))
        self.frame_action.setShortcut("F")
        self.view_menu.addAction(self.frame_action)


        self.view_menu.aboutToShow.connect(
            lambda: self.frame_action.setText(
                "Frame Selection" if self.level_view.selected_positions else "Frame All"))

        self.view_menu.addSeparator()

        self.view_action_group = QtGui.QActionGroup(self)

        self.change_to_topdownview_action = QtGui.QAction("Topdown View", self)
        self.view_action_group.addAction(self.change_to_topdownview_action)
        self.change_to_topdownview_action.triggered.connect(self.change_to_topdownview)
        self.view_menu.addAction(self.change_to_topdownview_action)
        self.change_to_topdownview_action.setCheckable(True)
        self.change_to_topdownview_action.setChecked(True)
        self.change_to_topdownview_action.setShortcut("Ctrl+1")

        self.change_to_3dview_action = QtGui.QAction("3D View", self)
        self.view_action_group.addAction(self.change_to_3dview_action)
        self.change_to_3dview_action.triggered.connect(self.change_to_3dview)
        self.view_menu.addAction(self.change_to_3dview_action)
        self.change_to_3dview_action.setCheckable(True)
        self.change_to_3dview_action.setShortcut("Ctrl+2")

        self.view_menu.addSeparator()

        self.viewer_toolbar_action = self.view_menu.addAction('Viewer Toolbar')
        self.viewer_toolbar_action.setShortcut('Ctrl+T')
        self.viewer_toolbar_action.setCheckable(True)
        self.viewer_toolbar_action.setChecked(True)

        self.transform_gizmo = self.view_menu.addAction('&Transform Gizmo')
        self.transform_gizmo.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_T))
        self.transform_gizmo.setCheckable(True)
        self.transform_gizmo.setChecked(True)
        self.transform_gizmo.triggered.connect(self.visibility_menu.filter_update)

        self.grid = self.view_menu.addAction('Grid')
        self.grid.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_NumberSign))
        self.grid.setCheckable(True)
        self.grid.setChecked(True)
        self.grid.triggered.connect(self.visibility_menu.filter_update)

        self.view_menu.addSeparator()

        self.fullscreen = self.view_menu.addAction('Fullscreen')
        self.fullscreen.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_F11))
        self.fullscreen.setCheckable(True)
        self.fullscreen.triggered[bool].connect(lambda checked: self.setWindowState(
            (self.windowState() | QtCore.Qt.WindowFullScreen)
            if checked else (self.windowState() & ~QtCore.Qt.WindowFullScreen)))

        self.dolphin_menu = utils.NonAutodismissibleMenu(self.menubar)
        self.dolphin_menu.setTitle("Dolphin")

        self.menubar.addAction(self.file_menu.menuAction())
        self.menubar.addAction(self.edit_menu.menuAction())
        self.menubar.addAction(self.visibility_menu.menuAction())
        self.menubar.addAction(self.collision_menu.menuAction())
        self.menubar.addAction(self.tools_menu.menuAction())
        self.menubar.addAction(self.minimap_menu.menuAction())
        self.menubar.addAction(self.view_menu.menuAction())
        self.menubar.addAction(self.dolphin_menu.menuAction())
        self.setMenuBar(self.menubar)

        self.last_obj_select_pos = 0

        self.dolphin_menu.addSeparator()

        self.dolphin_action = QtGui.QAction("Hook into Dolphin", self)
        self.dolphin_action.setCheckable(True)
        self.dolphin_action.triggered[bool].connect(self.action_hook_into_dolphion)
        self.dolphin_menu.addAction(self.dolphin_action)

        self.dolphin_menu.addSeparator()
        self.freeze_player_action = QtGui.QAction("Freeze Player 1")
        self.freeze_player_action.setCheckable(True)
        self.dolphin_menu.addAction(self.freeze_player_action)
        self.camera_actions = [QtGui.QAction("Unfollow", self)]

        for i in range(8):
            self.camera_actions.append(QtGui.QAction("Follow Player {0}".format(i+1)))

        def make_func(i):
            def action_follow_player():
                self.dolphin.stay_focused_on_player = i
            return action_follow_player

        self.camera_actions_group = QtGui.QActionGroup(self)

        for i in range(-1, 8):
            action = self.camera_actions[i+1]
            self.camera_actions_group.addAction(action)
            action.setCheckable(True)
            action.setChecked(i == self.dolphin.stay_focused_on_player)
            action.triggered.connect(make_func(i))

            self.dolphin_menu.addAction(action)

        self.dolphin_menu.addSeparator()

        def show_target_enemy_path_points(checked: bool):
            self.dolphin.show_target_enemy_path_points = checked
            self.update_3d()
            self.editorconfig['show_target_enemy_path_points'] = 'true' if checked else 'false'
            save_cfg(self.configuration)

        show_target_enemy_path_points_action = self.dolphin_menu.addAction(
            'Show Target Enemy Path Points')
        show_target_enemy_path_points_action.setCheckable(True)
        show_target_enemy_path_points_action.setChecked(self.dolphin.show_target_enemy_path_points)
        show_target_enemy_path_points_action.triggered[bool].connect(show_target_enemy_path_points)

        def show_target_item_points(checked):
            self.dolphin.show_target_item_points = checked
            self.update_3d()
            self.editorconfig['show_target_item_points'] = 'true' if checked else 'false'
            save_cfg(self.configuration)

        show_target_item_points_action = self.dolphin_menu.addAction('Show Target Item Points')
        show_target_item_points_action.setCheckable(True)
        show_target_item_points_action.setChecked(self.dolphin.show_target_item_points)
        show_target_item_points_action.triggered[bool].connect(show_target_item_points)

        if self.editorconfig.get('debug_ui'):
            self.debug_menu = self.menubar.addMenu('Debug')

            self.profile_action = self.debug_menu.addAction('Start Profiling')
            self.profile_action.setShortcut('Ctrl+Alt+P')
            self.profile_action.triggered.connect(self.action_profile_start_stop)
            self.profile = None

        help_menu = self.menubar.addMenu('Help')
        about_action = help_menu.addAction('About')
        about_action.triggered.connect(self._open_about_dialog)

    def action_hook_into_dolphion(self, checked: bool):
        self.dolphin.autoconnect = False

        if not checked:
            self.dolphin.reset()
            return

        error = self.dolphin.initialize()
        if error != "":
            open_error_dialog(error, self)
            self.dolphin_action.setChecked(False)
        else:
            # If successful, let it reconnect quietly from now on.
            self.dolphin.autoconnect = True

    def action_profile_start_stop(self):
        if self.profile is None:
            # Start profiling.
            self.profile_action.setText('Stop Profiling')
            self.profile = cProfile.Profile()
            self.profile.enable()
            return

        # Stop profiling.
        self.profile.disable()

        # Print results sorted by total time.
        s = StringIO()
        ps = pstats.Stats(self.profile, stream=s).sort_stats('tottime')
        ps.print_stats()
        print(s.getvalue())

        print('')

        # Print results sorted by cummulative time.
        s = StringIO()
        ps = pstats.Stats(self.profile, stream=s).sort_stats('cumtime')
        ps.print_stats()
        print(s.getvalue())

        self.profile = None
        self.profile_action.setText('Start Profiling')

    def _open_about_dialog(self):
        license_url = 'https://github.com/RenolY2/mkdd-track-editor/blob/master/LICENSE'
        updates_url = 'https://github.com/RenolY2/mkdd-track-editor/releases'

        title = 'About MKDD Track Editor'
        text = textwrap.dedent(f"""\
            <h1 style="white-space: nowrap">MKDD Track Editor {__version__}</h1>
            <br/>
            <small><a href="https://github.com/RenolY2/mkdd-track-editor">
                github.com/RenolY2/mkdd-track-editor
            </a></small>
            <p>{__doc__}</p>
            <br/>
            <br/>
            <small>
            Python {platform.python_version()}
            <br/>
            Qt {QtCore.__version__}
            </small>
            <br/>
            <br/>
            <small>
            <a href="{license_url}">License</a> | <a href="{updates_url}">Updates</a>
            </small>
        """)
        message_box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.NoIcon, title, text,
                                            QtWidgets.QMessageBox.NoButton, self)

        icon = self.windowIcon()
        icon_size = message_box.fontMetrics().averageCharWidth() * 8
        message_box.setIconPixmap(icon.pixmap(icon.actualSize(QtCore.QSize(icon_size, icon_size))))

        message_box.addButton(QtWidgets.QPushButton('Close', message_box),
                              QtWidgets.QMessageBox.AcceptRole)

        message_box.exec()

    def action_load_minimap_image(self):
        supported_extensions = [f'*{ext}' for ext in Image.registered_extensions()]
        supported_extensions.insert(0, '*.bti')
        supported_extensions = ' '.join(supported_extensions)

        if "minimap_image" not in self.pathsconfig:
            self.pathsconfig["minimap_image"] = ""

        filepath, choosentype = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Image", self.pathsconfig["minimap_image"],
            f"Images ({supported_extensions});;All files (*)")

        if filepath:
            if filepath.endswith('.bti'):
                with open(filepath, 'rb') as f:
                    bti_image = bti.BTI(f)
                    self.level_view.minimap.set_texture(bti_image.render())
            else:
                self.level_view.minimap.set_texture(filepath)
            self.level_view.do_redraw()

            self.pathsconfig["minimap_image"] = filepath
            save_cfg(self.configuration)

    def action_save_minimap_image(self, checked: bool = False, extension: str = 'png'):
        if not self.level_view.minimap.has_texture():
            open_info_dialog('No minimap image has been loaded yet.', self)
            return

        if "minimap_image" not in self.pathsconfig:
            self.pathsconfig["minimap_image"] = ""

        initial_filepath = self.pathsconfig["minimap_image"]
        stem, _ext = os.path.splitext(initial_filepath)
        initial_filepath = f'{stem}.{extension}'

        filepath, _choosentype = QtWidgets.QFileDialog.getSaveFileName(
            self, f"Save {extension.upper()} Image", initial_filepath,
            f"{extension.upper()} (*.{extension})")

        if filepath:
            image = self.level_view.minimap.get_texture().convert('RGBA')
            if extension == 'bti':
                for pixel in image.getdata():
                    if pixel[0] != pixel[1] or pixel[0] != pixel[2]:
                        colorful = True
                        break
                else:
                    colorful = False
                image_format = bti.ImageFormat.RGB5A3 if colorful else bti.ImageFormat.IA4
                bti_image = bti.BTI.create_from_image(image, image_format)
                bti_image.save(filepath)
            else:
                image.save(filepath)

            self.pathsconfig["minimap_image"] = filepath
            save_cfg(self.configuration)

    @catch_exception_with_dialog
    def action_load_dol(self):
        filepath, choosentype = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open File",
            self.pathsconfig["dol"],
            "Game Executable (*.dol);;All files (*)")

        if filepath:
            with open("lib/minimap_locations.json", "r") as f:
                addresses_json = json.load(f)

            with open(filepath, "rb") as f:
                dol = DolFile(f)
                region = detect_dol_region(dol)

            addresses = addresses_json[region]

            item_list = ["None"]
            item_list.extend(addresses.keys())
            result, pos = FileSelect.open_file_list(self, item_list, "Select Track Slot")

            if result == "None" or result is None:
                return

            corner1x, corner1z, corner2x, corner2z, orientation = addresses[result]
            with open(filepath, "rb") as f:
                dol = DolFile(f)

                dol.seek(int(orientation, 16))
                orientation = read_load_immediate_r0(dol)
                if orientation not in (0, 1, 2, 3):
                    raise RuntimeError("Wrong Address, orientation value in DOL isn't in 0-3 range: {0}. Maybe you are using"
                                       " a dol from a different version?".format(orientation))
                self.level_view.minimap.orientation = orientation
                dol.seek(int(corner1x, 16))
                self.level_view.minimap.corner1.x = read_float(dol)
                dol.seek(int(corner1z, 16))
                self.level_view.minimap.corner1.z = read_float(dol)
                dol.seek(int(corner2x, 16))
                self.level_view.minimap.corner2.x = read_float(dol)
                dol.seek(int(corner2z, 16))
                self.level_view.minimap.corner2.z = read_float(dol)
                self.level_view.do_redraw()

            self.pathsconfig["dol"] = filepath
            save_cfg(self.configuration)

    @catch_exception_with_dialog
    def action_save_to_dol(self, val):
        filepath, choosentype = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save to File",
            self.pathsconfig["dol"],
            "Game Executable (*.dol);;All files (*)")

        if filepath:
            with open("lib/minimap_locations.json", "r") as f:
                addresses_json = json.load(f)

            with open(filepath, "rb") as f:
                dol = DolFile(f)
                region = detect_dol_region(dol)

            addresses = addresses_json[region]

            item_list = ["None"]
            item_list.extend(addresses.keys())
            result, pos = FileSelect.open_file_list(self, item_list, "Select Track Slot")

            if result == "None" or result is None:
                return

            corner1x, corner1z, corner2x, corner2z, orientation = addresses[result]
            with open(filepath, "rb") as f:
                dol = DolFile(f)

            orientation_val = self.level_view.minimap.orientation
            if orientation_val not in (0, 1, 2, 3):
                raise RuntimeError(
                    "Invalid Orientation value: Must be in the range 0-3 but is {0}".format(orientation_val))

            dol.seek(int(orientation, 16))
            orientation_val = read_load_immediate_r0(dol)
            if orientation_val not in (0, 1, 2, 3):
                raise RuntimeError(
                    "Wrong Address, orientation value in DOL isn't in 0-3 range: {0}. Maybe you are using"
                    " a dol from a different game version?".format(orientation_val))

            dol.seek(int(orientation, 16))
            write_load_immediate_r0(dol, self.level_view.minimap.orientation)
            dol.seek(int(corner1x, 16))
            write_float(dol, self.level_view.minimap.corner1.x)
            dol.seek(int(corner1z, 16))
            write_float(dol, self.level_view.minimap.corner1.z)
            dol.seek(int(corner2x, 16))
            write_float(dol, self.level_view.minimap.corner2.x)
            dol.seek(int(corner2z, 16))
            write_float(dol, self.level_view.minimap.corner2.z)
            self.level_view.do_redraw()

            with open(filepath, "wb") as f:
                dol.save(f)

            self.pathsconfig["dol"] = filepath
            save_cfg(self.configuration)

    @catch_exception_with_dialog
    def action_load_coordinates_json(self):
        filepath, choosentype = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open File",
            self.pathsconfig["minimap_json"],
            "Json File (*.json);;All files (*)")

        if filepath:
            with open(filepath, "r") as f:
                data = json.load(f)
                self.level_view.minimap.corner1.x = data["Top Left Corner X"]
                self.level_view.minimap.corner1.z = data["Top Left Corner Z"]
                self.level_view.minimap.corner2.x = data["Bottom Right Corner X"]
                self.level_view.minimap.corner2.z = data["Bottom Right Corner Z"]
                self.level_view.minimap.orientation = data["Orientation"]

            self.pathsconfig["minimap_json"] = filepath
            save_cfg(self.configuration)

    @catch_exception_with_dialog
    def action_save_coordinates_json(self):
        filepath, choosentype = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save File",
            self.pathsconfig["minimap_json"],
            "Json File (*.json);;All files (*)")

        if filepath:
            data = {"Top Left Corner X": self.level_view.minimap.corner1.x,
                    "Top Left Corner Z": self.level_view.minimap.corner1.z,
                    "Bottom Right Corner X": self.level_view.minimap.corner2.x,
                    "Bottom Right Corner Z": self.level_view.minimap.corner2.z,
                    "Orientation": self.level_view.minimap.orientation}

            with open(filepath, "w") as f:
                json.dump(data, f, indent=4)

            self.pathsconfig["minimap_json"] = filepath
            save_cfg(self.configuration)

    @catch_exception_with_dialog
    def minimap_generator_action(self):
        if self.bco_coll is None:
            open_info_dialog('No BCO file has been loaded yet.', self)
            return

        with self.undo_history_disabled():
            show_minimap_generator(self)

    def action_choose_bco_area(self):
        if not isinstance(self.level_view.alternative_mesh, CollisionModel):
            QtWidgets.QMessageBox.information(self, "Collision Areas (BCO)",
                                              "No collision file is loaded.")
            return

        if self.collision_area_dialog is not None:
            self.collision_area_dialog.close()
            self.collision_area_dialog = None

        collision_model = self.level_view.alternative_mesh
        colltypes = tuple(sorted(collision_model.meshes))

        colltypegroups = {}
        for colltype in colltypes:
            colltypegroup = colltype & 0xFF00
            if colltypegroup not in colltypegroups:
                colltypegroups[colltypegroup] = []
            colltypegroups[colltypegroup].append(colltype)

        class DeselectableTableWidget(QtWidgets.QTreeWidget):
            def mousePressEvent(self, event):
                super().mousePressEvent(event)

                modelIndex = self.indexAt(event.position().toPoint())
                if not modelIndex.isValid():
                    self.clearSelection()

        tree_widget = DeselectableTableWidget()
        tree_widget.setColumnCount(2)
        tree_widget.setHeaderLabels(("Type", "Description"))

        def get_collision_type_desc(label):
            # http://wiki.tockdom.com/wiki/BCO_(File_Format)
            # https://mkdd.miraheze.org/wiki/BCO_(File_Format)#Collision_Flags

            group_descs = {
                "0x00__": "Medium Off-road",
                "0x01__": "Road",
                "0x02__": "Wall",
                "0x03__": "Medium Off-road",
                "0x04__": "Slippery Ice",
                "0x05__": "Dead zone",
                "0x06__": "Grassy Wall",
                "0x07__": "Boost",
                "0x08__": "Boost",
                "0x09__": "Cannon Boost",
                "0x0A__": "Dead zone",
                "0x0C__": "Weak Off-road",
                "0x0D__": "Teleport",
                "0x0E__": "Sand Dead zone",
                "0x0F__": "Wavy Dead zone",
                "0x10__": "Quicksand Dead zone",
                "0x11__": "Dead zone",
                "0x12__": "Kart-Only Wall",
                "0x13__": "Heavy Off-road",
                "0x37__": "Boost",
                "0x47__": "Boost",
            }

            return group_descs.get(label[:-2] + "__", "")

        for colltypegroup in sorted(colltypegroups):
            colltypes = colltypegroups[colltypegroup]

            if len(colltypes) == 1 and colltypegroup not in collision_model.hidden_collision_type_groups:
                colltype = colltypes[0]
                label = "0x{0:0{1}X}".format(colltype, 4)
                tree_widget_item = QtWidgets.QTreeWidgetItem(None, (label, ))
                tree_widget_item.setData(0, QtCore.Qt.UserRole + 1, colltype)
                tree_widget_item.setData(1, QtCore.Qt.DisplayRole, get_collision_type_desc(label))
                tree_widget_item.setCheckState(
                    0, QtCore.Qt.Checked
                    if colltype not in collision_model.hidden_collision_types
                    else QtCore.Qt.Unchecked)
                tree_widget.addTopLevelItem(tree_widget_item)
                continue

            label = "0x{0:0{1}X}".format(colltypegroup, 4)[:-2] + "__"
            tree_widget_item = QtWidgets.QTreeWidgetItem(None, (label, ))
            tree_widget_item.setData(0, QtCore.Qt.UserRole + 1, colltypegroup)
            tree_widget_item.setData(1, QtCore.Qt.DisplayRole, get_collision_type_desc(label))
            tree_widget_item.setCheckState(
                0, QtCore.Qt.Checked
                if colltypegroup not in collision_model.hidden_collision_type_groups
                else QtCore.Qt.Unchecked)
            tree_widget.addTopLevelItem(tree_widget_item)
            for colltype in colltypes:
                label = "0x{0:0{1}X}".format(colltype, 4)
                child_tree_widget_item = QtWidgets.QTreeWidgetItem(tree_widget_item, (label, ))
                child_tree_widget_item.setData(0, QtCore.Qt.UserRole + 1, colltype)
                child_tree_widget_item.setCheckState(
                    0, QtCore.Qt.Checked
                    if colltype not in collision_model.hidden_collision_types
                    else QtCore.Qt.Unchecked)

        def on_tree_widget_itemSelectionChanged(tree_widget=tree_widget):
            self.level_view.highlight_colltype = None

            for item in tree_widget.selectedItems():
                if item.childCount():
                    continue
                self.level_view.highlight_colltype = item.data(0, QtCore.Qt.UserRole + 1)
                break

            self.update_3d()

        all_items = tree_widget.findItems(
            "*",
            QtCore.Qt.MatchWrap | QtCore.Qt.MatchWildcard
            | QtCore.Qt.MatchRecursive)

        show_all_button = QtWidgets.QPushButton('Show All')
        hide_all_button = QtWidgets.QPushButton('Hide All')

        def update_both_all_buttons():
            checked_count = 0
            for item in all_items:
                checked = item.checkState(0) == QtCore.Qt.Checked
                if checked:
                    checked_count += 1

            show_all_button.setEnabled(checked_count < len(all_items))
            hide_all_button.setEnabled(checked_count)

        pending_operations = [False]

        def update_widgets_and_config():
            if not pending_operations[0]:
                return
            pending_operations[0] = False

            update_both_all_buttons()

            self.configuration["editor"]["hidden_collision_types"] = \
                ",".join(str(t) for t in collision_model.hidden_collision_types)
            self.configuration["editor"]["hidden_collision_type_groups"] = \
                ",".join(str(t) for t in collision_model.hidden_collision_type_groups)
            save_cfg(self.configuration)

            self.level_view.set_collision([], [], collision_model)
            self.update_3d()

        def on_tree_widget_itemChanged(_item, _column):
            for item in all_items:
                checked = item.checkState(0) == QtCore.Qt.Checked
                if item.childCount():
                    target_set = collision_model.hidden_collision_type_groups
                else:
                    target_set = collision_model.hidden_collision_types
                colltype = item.data(0, QtCore.Qt.UserRole + 1)
                if checked:
                    target_set.discard(colltype)
                else:
                    target_set.add(colltype)

            # To avoid updating widgets several times when multiple items change at once, the
            # update operation is scheduled to the next tick in the event loop.
            pending_operations[0] |= True
            QtCore.QTimer.singleShot(0, update_widgets_and_config)

        tree_widget.itemSelectionChanged.connect(on_tree_widget_itemSelectionChanged)
        tree_widget.itemChanged.connect(on_tree_widget_itemChanged)

        tree_widget.expandAll()
        tree_widget.resizeColumnToContents(0)

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.setContentsMargins(5, 5, 5, 5)
        buttons_layout.setSpacing(5)
        def on_show_all_button_clicked(checked):
            for item in all_items:
                item.setCheckState(0, QtCore.Qt.Checked)
        show_all_button.clicked.connect(on_show_all_button_clicked)
        def on_hide_all_button_clicked(checked):
            for item in all_items:
                item.setCheckState(0, QtCore.Qt.Unchecked)
        hide_all_button.clicked.connect(on_hide_all_button_clicked)
        buttons_layout.addWidget(show_all_button)
        buttons_layout.addWidget(hide_all_button)
        update_both_all_buttons()

        self.collision_area_dialog = QtWidgets.QDialog(self)
        self.collision_area_dialog.setWindowTitle("Collision Areas (BCO)")
        self.collision_area_dialog.setContentsMargins(0, 0, 0, 0)
        layout = QtWidgets.QVBoxLayout(self.collision_area_dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(tree_widget)
        layout.addLayout(buttons_layout)

        if "geometry" in self.configuration:
            geo_config = self.configuration["geometry"]

            def to_byte_array(byte_array: str) -> QtCore.QByteArray:
                return QtCore.QByteArray.fromBase64(byte_array.encode(encoding='ascii'))

            if "collision_window_geometry" in geo_config:
                self.collision_area_dialog.restoreGeometry(
                    to_byte_array(geo_config["collision_window_geometry"]))

        self.collision_area_dialog.show()

        def on_dialog_finished(result):
            _ = result
            if self.isVisible():
                self.save_geometry()

        self.collision_area_dialog.finished.connect(on_dialog_finished)

    def analyze_for_mistakes(self):
        analyzer_window = ErrorAnalyzer(self.level_file, parent=self)
        analyzer_window.exec()
        analyzer_window.deleteLater()

    def on_file_menu_aboutToShow(self):
        recent_files = self.get_recent_files_list()

        self.file_load_recent_menu.setEnabled(bool(recent_files))
        self.file_load_recent_menu.clear()

        for filepath in recent_files:
            recent_file_action = self.file_load_recent_menu.addAction(filepath)
            recent_file_action.triggered[bool].connect(
                lambda _checked, filepath=filepath: self.button_load_level(filepath))

        self.file_load_recent_menu.addSeparator()

        self.file_load_recent_menu.addAction('Clear Invalid').triggered[bool].connect(
            lambda _checked: self.clear_invalid_recent_files())
        self.file_load_recent_menu.addAction('Clear').triggered[bool].connect(
            lambda _checked: self.clear_recent_files())

    def on_filter_update(self):
        filters = []
        for object_toggle in self.visibility_menu.get_entries():
            if not object_toggle.action_view_toggle.isChecked():
                filters.append(object_toggle.action_view_toggle.text())
            if not object_toggle.action_select_toggle.isChecked():
                filters.append(object_toggle.action_select_toggle.text())

        self.editorconfig["filter_view"] = ','.join(filters)
        save_cfg(self.configuration)

        self.level_view.do_redraw()

    def on_cull_faces_triggered(self, checked):
        self.editorconfig["cull_faces"] = "True" if checked else "False"
        save_cfg(self.configuration)

        self.level_view.cull_faces = bool(checked)
        self.level_view.do_redraw()

    def on_default_geometry_changed(self, default_filetype):
        self.editorconfig["addi_file_on_load"] = default_filetype
        save_cfg(self.configuration)

        collision_actions = [self.auto_load_bco, self.auto_load_bmd, self.auto_load_none, self.auto_load_choose]
        collision_options = ("BCO", "BMD", "None", "Choose")

        for i, option in enumerate(collision_options):
            collision_actions[i].setChecked(option == default_filetype)

    def on_snapping_menu_aboutToShow(self):
        if self.level_view.snapping_enabled:
            for action in self.snapping_menu.actions():
                if action.objectName() == self.level_view.snapping_mode.name:
                    action.setChecked(True)
                    return

        self.snapping_menu.actions()[0].setChecked(True)

    def on_snapping_menu_action_triggered(self):
        self.level_view.set_snapping_mode(self.sender().objectName())

    def change_to_topdownview(self, checked):
        if checked:
            self.level_view.change_from_3d_to_topdown()

    def change_to_3dview(self, checked):
        if checked:
            self.level_view.change_from_topdown_to_3d()
            self.statusbar.clearMessage()

    def setup_ui_toolbar(self):
        # self.toolbar = QtWidgets.QToolBar("Test", self)
        # self.toolbar.addAction(QtGui.QAction("TestToolbar", self))
        # self.toolbar.addAction(QtGui.QAction("TestToolbar2", self))
        # self.toolbar.addAction(QtGui.QAction("TestToolbar3", self))

        # self.toolbar2 = QtWidgets.QToolBar("Second Toolbar", self)
        # self.toolbar2.addAction(QtGui.QAction("I like cake", self))

        # self.addToolBar(self.toolbar)
        # self.addToolBarBreak()
        # self.addToolBar(self.toolbar2)
        pass

    def connect_actions(self):
        #self.pik_control.lineedit_coordinatex.textChanged.connect(self.create_field_edit_action("coordinatex"))
        #self.pik_control.lineedit_coordinatey.textChanged.connect(self.create_field_edit_action("coordinatey"))
        #self.pik_control.lineedit_coordinatez.textChanged.connect(self.create_field_edit_action("coordinatez"))

        #self.pik_control.lineedit_rotationx.textChanged.connect(self.create_field_edit_action("rotationx"))
        #self.pik_control.lineedit_rotationy.textChanged.connect(self.create_field_edit_action("rotationy"))
        #self.pik_control.lineedit_rotationz.textChanged.connect(self.create_field_edit_action("rotationz"))

        self.level_view.position_update.connect(self.action_update_position)

        self.level_view.customContextMenuRequested.connect(self.mapview_showcontextmenu)

        self.level_view.move_points.connect(self.action_move_objects)
        self.level_view.move_points_to.connect(self.action_move_objects_to)
        self.level_view.create_waypoint.connect(self.action_add_object)
        self.level_view.create_waypoint_3d.connect(self.action_add_object_3d)

        delete_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete), self)
        delete_shortcut.activated.connect(self.action_delete_objects)

        self.level_view.rotate_current.connect(self.action_rotate_object)
        self.leveldatatreeview.select_all.connect(self.select_all_of_group)
        self.leveldatatreeview.reverse.connect(self.reverse_all_of_group)
        self.leveldatatreeview.duplicate.connect(self.duplicate_group)
        self.leveldatatreeview.split.connect(self.split_group)
        self.leveldatatreeview.split_checkpoint.connect(self.split_group_checkpoint)
        self.leveldatatreeview.select_object_type.connect(self.select_object_type)
        self.leveldatatreeview.select_area_type.connect(self.select_area_type)
        self.leveldatatreeview.select_area_assoc.connect(self.select_area_assoc)
        self.leveldatatreeview.select_route_assoc.connect(self.select_route_assoc)
        self.leveldatatreeview.select_route_points.connect(self.select_route_points)

        viewer_toolbar = self.level_view.viewer_toolbar

        self.viewer_toolbar_action.triggered[bool].connect(viewer_toolbar.setVisible)

        viewer_toolbar.transform_gizmo_button.clicked.connect(self.transform_gizmo.trigger)
        self.transform_gizmo.triggered[bool].connect(
            viewer_toolbar.transform_gizmo_button.setChecked)
        viewer_toolbar.rotate_around_median_point_button.clicked.connect(self.rotation_mode.trigger)
        self.rotation_mode.triggered[bool].connect(
            viewer_toolbar.rotate_around_median_point_button.setChecked)
        snapping_button_menu = viewer_toolbar.snapping_button.get_or_create_menu()
        snapping_button_menu.aboutToShow.connect(self.on_snapping_menu_aboutToShow)
        snapping_button_menu.addActions(self.snapping_menu.actions())
        for action in snapping_button_menu.actions():
            action.triggered[bool].connect(
                lambda checked: checked and viewer_toolbar.snapping_button.setChecked(
                    self.level_view.snapping_enabled))
        self.snapping_toggle_shortcut.activated.connect(
            lambda: viewer_toolbar.snapping_button.setChecked(self.level_view.snapping_enabled))
        self.snapping_cycle_shortcut.activated.connect(
            lambda: viewer_toolbar.snapping_button.setChecked(self.level_view.snapping_enabled))

        viewer_toolbar.delete_button.clicked.connect(self.action_delete_objects)
        viewer_toolbar.ground_button.clicked.connect(self.action_ground_objects)
        viewer_toolbar.distribute_button.clicked.connect(self.action_distribute_objects)

        viewer_toolbar.view_topdown_button.clicked.connect(
            self.change_to_topdownview_action.trigger)
        self.change_to_topdownview_action.toggled[bool].connect(
            viewer_toolbar.view_topdown_button.setChecked)
        viewer_toolbar.view_3d_button.clicked.connect(self.change_to_3dview_action.trigger)
        self.change_to_3dview_action.toggled[bool].connect(viewer_toolbar.view_3d_button.setChecked)

        viewer_toolbar.add_enemy_path_button.clicked.connect(self._add_enemy_path)
        viewer_toolbar.add_enemy_path_points_button.clicked.connect(
            lambda checked: self._enter_insertion_mode(checked, 'enemy_path_point'))
        viewer_toolbar.add_checkpoint_group_button.clicked.connect(self._add_checkpoint_group)
        viewer_toolbar.add_checkpoints_button.clicked.connect(
            lambda checked: self._enter_insertion_mode(checked, 'checkpoint'))
        viewer_toolbar.add_route_button.clicked.connect(self._add_route)
        viewer_toolbar.add_route_points_button.clicked.connect(
            lambda checked: self._enter_insertion_mode(checked, 'route_point'))
        viewer_toolbar.add_objects_button.clicked.connect(
            lambda checked: self._enter_insertion_mode(checked, 'object'))
        viewer_toolbar.add_kart_start_points_button.clicked.connect(
            lambda checked: self._enter_insertion_mode(checked, 'kart_start_point'))
        viewer_toolbar.add_areas_button.clicked.connect(
            lambda checked: self._enter_insertion_mode(checked, 'area'))
        viewer_toolbar.add_cameras_button.clicked.connect(
            lambda checked: self._enter_insertion_mode(checked, 'camera'))
        viewer_toolbar.add_respawn_points_button.clicked.connect(
            lambda checked: self._enter_insertion_mode(checked, 'respawn_point'))
        viewer_toolbar.add_light_param_button.clicked.connect(self._add_light_param)
        viewer_toolbar.add_minigame_param_button.clicked.connect(self._add_minigame_param)

        for label, button in (
            ('Enemy Path', viewer_toolbar.add_enemy_path_button),
            ('Enemy Path Point', viewer_toolbar.add_enemy_path_points_button),
            ('Checkpoint Group', viewer_toolbar.add_checkpoint_group_button),
            ('Checkpoint', viewer_toolbar.add_checkpoints_button),
            ('Route', viewer_toolbar.add_route_button),
            ('Route Point', viewer_toolbar.add_route_points_button),
            ('Object', viewer_toolbar.add_objects_button),
            ('Kart Start Point', viewer_toolbar.add_kart_start_points_button),
            ('Area', viewer_toolbar.add_areas_button),
            ('Camera', viewer_toolbar.add_cameras_button),
            ('Respawn Point', viewer_toolbar.add_respawn_points_button),
            ('Light Param', viewer_toolbar.add_light_param_button),
            ('Minigame Param', viewer_toolbar.add_minigame_param_button),
        ):
            name = label.replace(' ', '_').lower()
            template = getattr(self, f'_template_{name}')

            alternative_menu = button.get_or_create_alternative_menu()

            configure_action = alternative_menu.addAction(f'Configure {label} Template')
            configure_action.triggered[bool].connect(
                lambda _checked, label=label: self._configure_template(label))

            reset_action = alternative_menu.addAction(f'Reset {label} Template')
            reset_action.triggered[bool].connect(lambda _checked, name=name, template_copy=deepcopy(
                template): setattr(self, f'_template_{name}', deepcopy(template_copy)))

    def split_group_checkpoint(self, group_item, item):
        group = group_item.bound_to
        point = item.bound_to

        if point == group.points[-1]:
            return

        """# Get an unused link to connect the groups with
        new_link = self.level_file.enemypointgroups.new_link_id()
        if new_link >= 2**14:
            raise RuntimeError("Too many links, cannot create more")
        """

        # Get new hopefully unused group id
        new_id = self.level_file.checkpoints.new_group_id()
        new_group = group.copy_group_after(new_id, point)
        self.level_file.checkpoints.groups.append(new_group)
        group.remove_after(point)
        new_group.prevlinks = [group.grouplink, -1, -1, -1]
        new_group.nextlinks = deepcopy(group.nextgroup)
        group.nextgroup = [new_group.grouplink, -1, -1, -1]

        self.leveldatatreeview.set_objects(self.level_file)
        self.update_3d()
        self.set_has_unsaved_changes(True)

    def split_group(self, group_item, item):
        group = group_item.bound_to
        point = item.bound_to

        if point == group.points[-1]:
            return

        # Get an unused link to connect the groups with
        new_link = self.level_file.enemypointgroups.new_link_id()
        if new_link >= 2**14:
            raise RuntimeError("Too many links, cannot create more")

        # Get new hopefully unused group id
        new_id = self.level_file.enemypointgroups.new_group_id()
        new_group = group.copy_group_after(new_id, point)
        self.level_file.enemypointgroups.groups.append(new_group)
        group.remove_after(point)

        group.points[-1].link = new_group.points[0].link = new_link

        self.leveldatatreeview.set_objects(self.level_file)
        self.update_3d()
        self.set_has_unsaved_changes(True)

    def duplicate_group(self, item):
        group = item.bound_to
        if isinstance(group, libbol.EnemyPointGroup):
            new_id = len(self.level_file.enemypointgroups.groups)
            new_group = group.copy_group(new_id)
            self.level_file.enemypointgroups.groups.append(new_group)

            self.leveldatatreeview.set_objects(self.level_file)
            self.update_3d()
            self.set_has_unsaved_changes(True)

    def reverse_all_of_group(self, item):
        group = item.bound_to
        if isinstance(group, libbol.CheckpointGroup):
            group.points.reverse()
            for point in group.points:
                start = point.start
                point.start = point.end
                point.end = start
        elif isinstance(group, libbol.EnemyPointGroup):
            group.points.reverse()
        elif isinstance(group, libbol.Route):
            group.points.reverse()

        self.leveldatatreeview.set_objects(self.level_file)
        self.update_3d()

    def select_all_of_group(self, item):
        group = item.bound_to
        self.level_view.selected = []
        self.level_view.selected_positions = []
        self.level_view.selected_rotations = []
        for point in group.points:
            self.level_view.selected.append(point)

            if isinstance(group, libbol.CheckpointGroup):
                self.level_view.selected_positions.append(point.start)
                self.level_view.selected_positions.append(point.end)
            else:
                self.level_view.selected_positions.append(point.position)
        self.update_3d()

    def update_recent_files_list(self, filepath):
        filepath = os.path.abspath(os.path.normpath(filepath))

        recent_files = self.get_recent_files_list()
        if filepath in recent_files:
            recent_files.remove(filepath)

        recent_files.insert(0, filepath)
        recent_files = recent_files[:RECENT_FILE_LIST_LENGTH]

        self.configuration["recent files"] = {}
        recent_files_config = self.configuration["recent files"]

        for i, filepath in enumerate(recent_files):
            config_entry = f"file{i}"
            recent_files_config[config_entry] = filepath

    def get_recent_files_list(self):
        if "recent files" not in self.configuration:
            self.configuration["recent files"] = {}
        recent_files_config = self.configuration["recent files"]

        recent_files = []
        for i in range(RECENT_FILE_LIST_LENGTH):
            config_entry = f"file{i}"
            if config_entry in recent_files_config:
                recent_files.append(recent_files_config[config_entry])

        return recent_files

    def clear_invalid_recent_files(self):
        recent_files = [f for f in self.get_recent_files_list() if os.path.isfile(f)]

        self.configuration['recent files'] = {}
        recent_files_config = self.configuration['recent files']

        for i, filepath in enumerate(recent_files):
            config_entry = f'file{i}'
            recent_files_config[config_entry] = filepath

    def clear_recent_files(self):
        if 'recent files' not in self.configuration:
            return

        msgbox = QtWidgets.QMessageBox(self)
        size = self.fontMetrics().height() * 3
        msgbox.setIconPixmap(QtGui.QIcon('resources/warning.svg').pixmap(size, size))
        msgbox.setWindowTitle(f'{len(self.configuration["recent files"])} Recently Loaded Files')
        msgbox.setText('Are you sure you want to clear the recently loaded file list?')
        msgbox.addButton('No', QtWidgets.QMessageBox.RejectRole)
        clear_button = msgbox.addButton('Clear', QtWidgets.QMessageBox.DestructiveRole)
        msgbox.exec()
        if msgbox.clickedButton() != clear_button:
            return

        self.configuration['recent files'].clear()

    def select_object_type(self, item):
        mapobject = item.bound_to
        all_objects = self.level_file.objects.objects
        map_objects = [obj for obj in all_objects if obj.objectid == mapobject.objectid]

        self.level_view.selected = map_objects
        self.level_view.selected_positions = [obj.position for obj in map_objects]
        self.level_view.selected_rotations = [obj.rotation for obj in map_objects]

        self.level_view.gizmo.move_to_average(self.level_view.selected_positions,
                                              self.level_view.selected_rotations)
        self.level_view.do_redraw()
        self.action_update_info()

    def select_area_type(self, item):
        if isinstance(item, libbol.Area):
            ref_area = item
        else:
            ref_area = item.bound_to
        all_areas = self.level_file.areas.areas
        areas = [area for area in all_areas if ref_area.area_type == area.area_type]

        self.level_view.selected = areas
        self.level_view.selected_positions = [obj.position for obj in areas]
        self.level_view.selected_rotations = [obj.rotation for obj in areas]

        self.level_view.gizmo.move_to_average(self.level_view.selected_positions,
                                              self.level_view.selected_rotations)
        self.level_view.do_redraw()
        self.action_update_info()

    def select_area_assoc(self, item):
        if isinstance(item, libbol.Area):
            ref_area = item
        else:
            ref_area = item.bound_to

        self.level_view.selected = [ref_area]
        self.level_view.selected_positions = [ref_area.position]
        self.level_view.selected_rotations = [ref_area.rotation]

        camera = ref_area.camera
        if camera is not None:
            self.level_view.selected.append(camera)
            self.level_view.selected_positions.append(camera.position)
            self.level_view.selected_rotations.append(camera.rotation)

            route = camera.route
            if route is not None:

                self.level_view.selected.extend(route.points)
                route_point_positions = [point.position for point in route.points]
                self.level_view.selected_positions.extend(route_point_positions)

        self.level_view.gizmo.move_to_average(self.level_view.selected_positions,
                                              self.level_view.selected_rotations)
        self.level_view.do_redraw()
        self.action_update_info()

    def select_route_assoc(self, item):
        if isinstance(item, (libbol.MapObject, libbol.Camera)):
            ref_obj = item
        else:
            ref_obj = item.bound_to

        self.level_view.selected = [ref_obj]
        self.level_view.selected_positions = [ref_obj.position]
        self.level_view.selected_rotations = [ref_obj.rotation]

        route = ref_obj.route
        self.level_view.selected.extend(route.points)
        route_point_positions = [point.position for point in route.points]
        self.level_view.selected_positions.extend(route_point_positions)

        self.level_view.gizmo.move_to_average(self.level_view.selected_positions,
                                              self.level_view.selected_rotations)
        self.level_view.do_redraw()
        self.action_update_info()

    def select_route_points(self, item):
        if isinstance(item, libbol.RoutePoint):
            ref_point = item
        else:
            ref_point = item.bound_to

        self.level_view.selected = []
        self.level_view.selected_positions = []
        self.level_view.selected_rotations = []


        route, _point_index = self.level_file.get_route_of_points(ref_point)
        if route is not None:
            self.level_view.selected.extend(route.points)
            self.level_view.selected_positions = [point.position for point in route.points]

            self.level_view.gizmo.move_to_average(self.level_view.selected_positions,
                                                self.level_view.selected_rotations)
            self.level_view.do_redraw()
            self.action_update_info()

    #@catch_exception
    def button_load_level(self, filepath=None, update_config=True):
        if filepath is None:
            filepath, _chosentype = QtWidgets.QFileDialog.getOpenFileName(
                self, "Open File",
                self.pathsconfig["bol"],
                'BOL or RARC (*.bol *.arc);;All files (*)')

        if filepath:
            _stem, ext = os.path.splitext(filepath)
            if ext not in ('.bol', '.arc'):
                open_error_dialog(f'Unrecognized file extension: "{ext}"', self)
                return

            self.reset()
            if ext == '.arc':
                try:
                    with open(filepath, "rb") as f:
                        self.loaded_archive = Archive.from_file(f)
                        root_name = self.loaded_archive.root.name
                        coursename = find_file(self.loaded_archive.root, "_course.bol")
                        bol_file = self.loaded_archive[root_name + "/" + coursename]
                        bol_data = BOL.from_file(bol_file)
                        self.setup_bol_file(bol_data, filepath, update_config)
                        self.leveldatatreeview.set_objects(bol_data)
                        self.current_gen_path = filepath
                        self.loaded_archive_file = coursename
                except Exception as error:
                    print("Error appeared while loading:", error)
                    traceback.print_exc()
                    open_error_dialog(str(error), self)
                    self.loaded_archive = None
                    self.loaded_archive_file = None
                    return

                bmdfile = get_file_safe(self.loaded_archive.root, "_course.bmd")
                collisionfile = get_file_safe(self.loaded_archive.root, "_course.bco")

                if self.editorconfig["addi_file_on_load"] == "Choose":
                    try:
                        additional_files = []

                        if bmdfile is not None:
                            additional_files.append(os.path.basename(bmdfile.name) + " (3D Model)")
                        if collisionfile is not None:
                            additional_files.append(os.path.basename(collisionfile.name) + " (3D Collision)")

                        if len(additional_files) > 0:
                            additional_files.append("None")
                            self.load_optional_3d_file_arc(additional_files, bmdfile, collisionfile, filepath)
                        else:
                            self.clear_collision()
                    except Exception as error:
                        print("Error appeared while loading:", error)
                        traceback.print_exc()
                        open_error_dialog(str(error), self)
                elif bmdfile is not None and self.editorconfig["addi_file_on_load"] == "BMD":
                    self.load_bmd_from_arc(bmdfile, filepath)
                elif collisionfile is not None and self.editorconfig["addi_file_on_load"] == "BCO":
                    self.load_bco_from_arc(collisionfile, filepath)
                elif self.editorconfig["addi_file_on_load"] == "None":
                    self.clear_collision()

            else:
                try:
                    with open(filepath, "rb") as f:
                        bol_file = BOL.from_file(f)
                        self.setup_bol_file(bol_file, filepath, update_config)
                        self.leveldatatreeview.set_objects(bol_file)
                        self.current_gen_path = filepath
                except Exception as error:
                    print("Error appeared while loading:", error)
                    traceback.print_exc()
                    open_error_dialog(str(error), self)
                    return

                if filepath.endswith("_course.bol"):
                    filepath_base = filepath[:-11]
                    bmdfile = filepath_base + "_course.bmd"
                    collisionfile = filepath_base + "_course.bco"

                    if self.editorconfig["addi_file_on_load"] == "Choose":

                        additional_files = []

                        if os.path.exists(bmdfile):
                            additional_files.append(os.path.basename(bmdfile) + " (3D Model)")
                        if os.path.exists(collisionfile):
                            additional_files.append(
                                os.path.basename(collisionfile) + " (3D Collision)")

                        if len(additional_files) > 0:
                            additional_files.append("None")
                            self.load_optional_3d_file(additional_files, bmdfile, collisionfile)
                        else:
                            self.clear_collision()
                    elif bmdfile is not None and self.editorconfig["addi_file_on_load"] == "BMD":
                        if os.path.isfile(bmdfile):
                            self.load_optional_bmd(bmdfile)
                    elif collisionfile is not None and self.editorconfig[
                            "addi_file_on_load"] == "BCO":
                        if os.path.isfile(collisionfile):
                            self.load_optional_bco(collisionfile)
                    elif self.editorconfig["addi_file_on_load"] == "None":
                        self.clear_collision()

            self.update_3d()

    def load_optional_3d_file(self, additional_files, bmdfile, collisionfile):
        choice, pos = FileSelect.open_file_list(self, additional_files,
                                                "Select additional file to load", startat=0)

        self.clear_collision()

        if not choice:
            return

        if choice.endswith("(3D Model)"):
            self.load_optional_bmd(bmdfile)

        elif choice.endswith("(3D Collision)"):
            self.load_optional_bco(collisionfile)

    def load_optional_bmd(self, bmdfile):
        alternative_mesh = load_textured_bmd(bmdfile)
        with open("lib/temp/temp.obj", "r") as f:
            verts, faces, normals = py_obj.read_obj(f)

        self.setup_collision(verts, faces, bmdfile, alternative_mesh)

    def load_optional_bco(self, collisionfile):
        bco_coll = RacetrackCollision()
        verts = []
        faces = []

        with open(collisionfile, "rb") as f:
            bco_coll.load_file(f)
        self.bco_coll = bco_coll

        for vert in bco_coll.vertices:
            verts.append(vert)

        for v1, v2, v3, collision_type, rest in bco_coll.triangles:
            faces.append(((v1 + 1, None), (v2 + 1, None), (v3 + 1, None)))
        model = CollisionModel(bco_coll)
        self.setup_collision(verts, faces, collisionfile, alternative_mesh=model)

    def load_optional_3d_file_arc(self, additional_files, bmdfile, collisionfile, arcfilepath):
        choice, pos = FileSelect.open_file_list(self, additional_files,
                                                "Select additional file to load", startat=0)

        self.clear_collision()

        if not choice:
            return

        if choice.endswith("(3D Model)"):
            self.load_bmd_from_arc(bmdfile, arcfilepath)

        elif choice.endswith("(3D Collision)"):
            self.load_bco_from_arc(collisionfile, arcfilepath)

    def load_bmd_from_arc(self, bmdfile, arcfilepath):
        with open("lib/temp/temp.bmd", "wb") as f:
            f.write(bmdfile.getvalue())

        bmdpath = "lib/temp/temp.bmd"
        alternative_mesh = load_textured_bmd(bmdpath)
        with open("lib/temp/temp.obj", "r") as f:
            verts, faces, normals = py_obj.read_obj(f)

        self.setup_collision(verts, faces, arcfilepath, alternative_mesh)

    def load_bco_from_arc(self, collisionfile, arcfilepath):
        bco_coll = RacetrackCollision()
        verts = []
        faces = []

        bco_coll.load_file(collisionfile)
        self.bco_coll = bco_coll

        for vert in bco_coll.vertices:
            verts.append(vert)

        for v1, v2, v3, collision_type, rest in bco_coll.triangles:
            faces.append(((v1 + 1, None), (v2 + 1, None), (v3 + 1, None)))
        model = CollisionModel(bco_coll)
        self.setup_collision(verts, faces, arcfilepath, alternative_mesh=model)

    def load_file(self, filepath, additional=None):
        if filepath.endswith('.bol'):
            return self.load_bol_file(filepath, additional=additional)

        if filepath.endswith('.arc'):
            return self.load_arc_file(filepath, additional=additional)

    def load_bol_file(self, filepath, additional=None):
        with open(filepath, "rb") as f:
            bol_file = BOL.from_file(f)
            self.setup_bol_file(bol_file, filepath)
            self.leveldatatreeview.set_objects(bol_file)
            self.current_gen_path = filepath

        if not filepath.endswith('_course.bol'):
            return

        self.clear_collision()

        if additional == 'model':
            bmdfile = filepath[:-len('.bol')] + ".bmd"
            if not os.path.isfile(bmdfile):
                return

            alternative_mesh = load_textured_bmd(bmdfile)
            with open("lib/temp/temp.obj", "r") as f:
                verts, faces, normals = py_obj.read_obj(f)

            self.setup_collision(verts, faces, bmdfile, alternative_mesh)

        elif additional == 'collision':
            collisionfile = filepath[:-len('.bol')] + ".bco"
            if not os.path.isfile(collisionfile):
                return

            bco_coll = RacetrackCollision()
            with open(collisionfile, "rb") as f:
                bco_coll.load_file(f)
            self.bco_coll = bco_coll

            verts = []
            for vert in bco_coll.vertices:
                verts.append(vert)

            faces = []
            for v1, v2, v3, collision_type, rest in bco_coll.triangles:
                faces.append(((v1 + 1, None), (v2 + 1, None), (v3 + 1, None)))

            model = CollisionModel(bco_coll)
            self.setup_collision(verts, faces, collisionfile, alternative_mesh=model)

        QtCore.QTimer.singleShot(0, self.update_3d)

    def load_arc_file(self, filepath, additional=None):
        with open(filepath, "rb") as f:
            try:
                self.loaded_archive = Archive.from_file(f)
                root_name = self.loaded_archive.root.name
                coursename = find_file(self.loaded_archive.root, "_course.bol")
                bol_file = self.loaded_archive[root_name + "/" + coursename]
                bol_data = BOL.from_file(bol_file)
                self.setup_bol_file(bol_data, filepath)
                self.leveldatatreeview.set_objects(bol_data)
                self.current_gen_path = filepath
                self.loaded_archive_file = coursename
            except:
                self.loaded_archive = None
                self.loaded_archive_file = None
                raise

        self.clear_collision()

        if additional == 'model':
            bmdfile = get_file_safe(self.loaded_archive.root, "_course.bmd")
            if bmdfile is None:
                return

            bmdpath = "lib/temp/temp.bmd"
            with open(bmdpath, "wb") as f:
                f.write(bmdfile.getvalue())

            alternative_mesh = load_textured_bmd(bmdpath)
            with open("lib/temp/temp.obj", "r") as f:
                verts, faces, normals = py_obj.read_obj(f)

            self.setup_collision(verts, faces, filepath, alternative_mesh)

        elif additional == 'collision':
            collisionfile = get_file_safe(self.loaded_archive.root, "_course.bco")
            if collisionfile is None:
                return

            bco_coll = RacetrackCollision()
            bco_coll.load_file(collisionfile)
            self.bco_coll = bco_coll

            verts = []
            for vert in bco_coll.vertices:
                verts.append(vert)

            faces = []
            for v1, v2, v3, collision_type, rest in bco_coll.triangles:
                faces.append(((v1 + 1, None), (v2 + 1, None), (v3 + 1, None)))

            model = CollisionModel(bco_coll)
            self.setup_collision(verts, faces, filepath, alternative_mesh=model)

        QtCore.QTimer.singleShot(0, self.update_3d)

    def setup_bol_file(self, bol_file, filepath, update_config=True):
        self.level_file = bol_file
        self.level_view.level_file = self.level_file
        self.level_view.do_redraw()

        self.on_document_potentially_changed(update_unsaved_changes=False)

        # self.bw_map_screen.update()
        # path_parts = path.split(filepath)
        self.set_base_window_title(filepath)
        if update_config:
            self.pathsconfig["bol"] = filepath
            self.update_recent_files_list(filepath)
            save_cfg(self.configuration)
        self.current_gen_path = filepath

    @catch_exception_with_dialog
    def button_save_level(self, *args, **kwargs):
        if self.current_gen_path is not None:
            if not self._check_errors_on_saving():
                return

            if self.loaded_archive is not None:
                assert self.loaded_archive_file is not None
                root_name = self.loaded_archive.root.name
                file = self.loaded_archive[root_name + "/" + self.loaded_archive_file]
                file.seek(0)

                self.level_file.write(file)

                with open(self.current_gen_path, "wb") as f:
                    self.loaded_archive.write_arc(f)

                self.set_has_unsaved_changes(False)
                self.statusbar.showMessage("Saved to {0}".format(self.current_gen_path))

            else:
                with open(self.current_gen_path, "wb") as f:
                    self.level_file.write(f)
                    self.set_has_unsaved_changes(False)

                    self.statusbar.showMessage("Saved to {0}".format(self.current_gen_path))
        else:
            self.button_save_level_as()

    def button_save_level_as(self, *args, **kwargs):
        self._button_save_level_as(True, *args, **kwargs)

    def button_save_level_copy_as(self, *args, **kwargs):
        self._button_save_level_as(False, *args, **kwargs)

    @catch_exception_with_dialog
    def _button_save_level_as(self, modify_current_path, *args, **kwargs):
        if not self._check_errors_on_saving():
            return

        filepath, _chosentype = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save File",
            self.pathsconfig["bol"],
            'BOL or RARC (*.bol *.arc);;All files (*)')

        if filepath:
            _stem, ext = os.path.splitext(filepath)
            if ext not in ('.bol', '.arc'):
                open_error_dialog(f'Unrecognized file extension: "{ext}"', self)
                return

            if ext == '.arc':
                if self.loaded_archive is None or self.loaded_archive_file is None:
                    with open(filepath, "rb") as f:
                        self.loaded_archive = Archive.from_file(f)

                self.loaded_archive_file = find_file(self.loaded_archive.root, "_course.bol")
                root_name = self.loaded_archive.root.name
                file = self.loaded_archive[root_name + "/" + self.loaded_archive_file]
                file.seek(0)

                self.level_file.write(file)

                with open(filepath, "wb") as f:
                    self.loaded_archive.write_arc(f)

                self.set_has_unsaved_changes(False)
                self.statusbar.showMessage("Saved to {0}".format(filepath))
            else:
                with open(filepath, "wb") as f:
                    self.level_file.write(f)

                    self.set_has_unsaved_changes(False)

            self.pathsconfig["bol"] = filepath
            save_cfg(self.configuration)

            if modify_current_path:
                self.current_gen_path = filepath
                self.set_base_window_title(filepath)

            self.statusbar.showMessage("Saved to {0}".format(filepath))

    def _check_errors_on_saving(self) -> bool:
        error_count = self.error_analyzer_button.get_error_count()
        if error_count > 0:
            msgbox = QtWidgets.QMessageBox(self)
            size = self.fontMetrics().height() * 3
            msgbox.setIconPixmap(QtGui.QIcon('resources/warning.svg').pixmap(size, size))
            msgbox.setWindowTitle("Course Errors")
            if error_count == 1:
                text = f'There os {error_count} error in the course.'
            else:
                text = f'There are {error_count} errors in the course.'
            text += '\n\nWould you like to save the document anyway?'
            msgbox.setText(text)
            msgbox.addButton('Cancel', QtWidgets.QMessageBox.RejectRole)
            save_button = msgbox.addButton('Save Anyway', QtWidgets.QMessageBox.DestructiveRole)
            msgbox.exec()
            if msgbox.clickedButton() != save_button:
                return False

        return True

    def button_load_collision_obj(self):
        try:
            last_path = self.pathsconfig["collision"]
            if not last_path.endswith('.obj'):
                last_path = os.path.dirname(last_path)

            filepath, _chosentype = QtWidgets.QFileDialog.getOpenFileName(
                self, "Open File",
                last_path,
                "OBJ (*.obj);;All files (*)")

            if not filepath:
                return

            _stem, ext = os.path.splitext(filepath)
            if ext not in ('.obj', ):
                open_error_dialog(f'Unrecognized file extension: "{ext}"', self)
                return

            # TODO(CA): At the moment, only proper OBJ textured models are supported; if the user
            # attempts to load a OBJ converted from a BCO file, the action fails. It'd be good to
            # transparently support both formats, by scanning through the content of the OBJ file in
            # advance and verifying whether it is a collision file.

            with open(filepath, "r") as f:
                verts, faces, normals = py_obj.read_obj(f)
            alternative_mesh = TexturedModel.from_obj_path(filepath, rotate=True)

            self.setup_collision(verts, faces, filepath, alternative_mesh)

        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), self)

        finally:
            self.update_3d()

    def button_load_collision_bmd(self):
        try:
            last_path = self.pathsconfig["collision"]
            if not last_path.endswith('.bmd') and not last_path.endswith('.arc'):
                last_path = os.path.dirname(last_path)

            filepath, _chosentype = QtWidgets.QFileDialog.getOpenFileName(
                self, "Open File",
                last_path,
                "BMD or RARC (*.bmd *.arc);;All files (*)")

            if not filepath:
                return

            _stem, ext = os.path.splitext(filepath)
            if ext not in ('.bmd', '.arc'):
                open_error_dialog(f'Unrecognized file extension: "{ext}"', self)
                return

            bmdpath = filepath
            clear_temp_folder()
            if ext == '.arc':
                with open(filepath, "rb") as f:
                    rarc = Archive.from_file(f)

                root_name = rarc.root.name
                bmd_filename = find_file(rarc.root, "_course.bmd")
                bmd = rarc[root_name][bmd_filename]
                with open("lib/temp/temp.bmd", "wb") as f:
                    f.write(bmd.getvalue())

                bmdpath = "lib/temp/temp.bmd"

            self.clear_collision()

            alternative_mesh = load_textured_bmd(bmdpath)
            with open("lib/temp/temp.obj", "r") as f:
                verts, faces, normals = py_obj.read_obj(f)

            self.setup_collision(verts, faces, filepath, alternative_mesh)

        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), self)

        finally:
            self.update_3d()

    def button_load_collision_bco(self):
        try:
            last_path = self.pathsconfig["collision"]
            if not last_path.endswith('.bco') and not last_path.endswith('.arc'):
                last_path = os.path.dirname(last_path)

            filepath, _chosentype = QtWidgets.QFileDialog.getOpenFileName(
                self, "Open File",
                last_path,
                "BCO or RARC (*.bco *.arc);;All files (*)")

            if filepath:
                _stem, ext = os.path.splitext(filepath)
                if ext not in ('.bco', '.arc'):
                    open_error_dialog(f'Unrecognized file extension: "{ext}"', self)
                    return

                bco_coll = RacetrackCollision()
                verts = []
                faces = []

                if ext == '.arc':
                    with open(filepath, "rb") as f:
                        rarc = Archive.from_file(f)


                    root_name = rarc.root.name
                    collision_file = find_file(rarc.root, "_course.bco")
                    bco = rarc[root_name][collision_file]
                    bco_coll.load_file(bco)
                    self.bco_coll = bco_coll
                else:
                    with open(filepath, "rb") as f:
                        bco_coll.load_file(f)
                    self.bco_coll = bco_coll

                for vert in bco_coll.vertices:
                    verts.append(vert)

                for v1, v2, v3, collision_type, rest in bco_coll.triangles:
                    faces.append(((v1+1, None), (v2+1, None), (v3+1, None)))
                model = CollisionModel(bco_coll)
                self.setup_collision(verts, faces, filepath, alternative_mesh=model)

        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), self)

        finally:
            self.update_3d()

    def clear_collision(self):
        self.bco_coll = None
        self.level_view.clear_collision()

        # Synchronously force a draw operation to provide immediate feedback.
        self.level_view.update()
        QtWidgets.QApplication.instance().processEvents()

    def setup_collision(self, verts, faces, filepath, alternative_mesh=None):
        editor_config = self.configuration["editor"]
        alternative_mesh.hidden_collision_types = \
            set(int(t) for t in editor_config.get("hidden_collision_types", "").split(",") if t)
        alternative_mesh.hidden_collision_type_groups = \
            set(int(t) for t in editor_config.get("hidden_collision_type_groups", "").split(",") if t)
        self.level_view.set_collision(verts, faces, alternative_mesh)

        self.pathsconfig["collision"] = filepath
        save_cfg(self.configuration)

    def select_tree_item_bound_to(self, objects):
        # Iteratively traverse all the tree widget items to retrieve all the bound objects.
        bound_objects_and_items = []
        pending_items = [self.leveldatatreeview.invisibleRootItem()]
        while pending_items:
            item = pending_items.pop(0)
            for child_index in range(item.childCount()):
                child_item = item.child(child_index)
                if hasattr(child_item, 'bound_to') and child_item.bound_to is not None:
                    bound_objects_and_items.append((child_item.bound_to, child_item))
                pending_items.append(child_item)

        new_item_selection = []
        for obj in objects:
            for bound_object, item in bound_objects_and_items:
                if obj is bound_object:
                    new_item_selection.append(item)

        if new_item_selection:
            # If found, deselect current selection.
            for selected_item in self.leveldatatreeview.selectedItems():
                selected_item.setSelected(False)

            # Make last item in the new selection current (focus effect), and select new items.
            self.leveldatatreeview.setCurrentItem(new_item_selection[-1])
            for bound_item in new_item_selection:
                bound_item.setSelected(True)

                # Ensure that the new item is visible.
                parent_item = bound_item.parent()
                while parent_item is not None:
                    parent_item.setExpanded(True)
                    parent_item = parent_item.parent()
                self.leveldatatreeview.scrollToItem(bound_item)

    @catch_exception
    def action_add_object(self, x, z):
        y = 0
        if self.level_view.collision is not None:
            y_limit = self.editorconfig.getint("topdown_cull_height")
            y_collided = self.level_view.collision.collide_ray_downwards(x, z, y=y_limit)
            if y_collided is not None:
                y = y_collided

        self.action_add_object_3d(x, y, z)

    @catch_exception
    def action_add_object_3d(self, x, y, z):
        placeobject = deepcopy(getattr(self, f'_template_{self._insertion_mode_type_name}'))

        if hasattr(placeobject, 'position'):
            placeobject.position.x = x
            placeobject.position.y = y
            placeobject.position.z = z

        if isinstance(placeobject, libbol.Checkpoint):
            if self.next_checkpoint_start_position is None:
                self.next_checkpoint_start_position = (x, y, z)
                self.update_3d()
                return

            x1, _y1, z1 = self.next_checkpoint_start_position
            self.next_checkpoint_start_position = None

            placeobject.start.x = x1
            placeobject.start.z = z1
            placeobject.end.x = x
            placeobject.end.z = z

            # For convenience, create a group if none exists yet.
            if not self.level_file.checkpoints.groups:
                self.level_file.checkpoints.groups.append(libbol.CheckpointGroup.new())

            group_index = len(self.level_file.checkpoints.groups) - 1
            index = sys.maxsize
            for selected_item in reversed(self.leveldatatreeview.selectedItems()):
                if selected_item is self.leveldatatreeview.checkpointgroups:
                    group_index = 0
                    index = 0
                    break
                if not hasattr(selected_item, 'bound_to'):
                    continue
                if isinstance(selected_item.bound_to, libbol.Checkpoint):
                    group_index = selected_item.parent().get_index_in_parent()
                    index = selected_item.get_index_in_parent() + 1
                    break
                if isinstance(selected_item.bound_to, libbol.CheckpointGroup):
                    group_index = selected_item.get_index_in_parent()
                    index = 0
                    break

            self.level_file.checkpoints.groups[group_index].points.insert(index, placeobject)

        elif isinstance(placeobject, libbol.EnemyPoint):
            # For convenience, create a group if none exists yet.
            if not self.level_file.enemypointgroups.groups:
                self.level_file.enemypointgroups.groups.append(libbol.EnemyPointGroup.new())

            group_index = len(self.level_file.enemypointgroups.groups) - 1
            index = sys.maxsize
            for selected_item in reversed(self.leveldatatreeview.selectedItems()):
                if selected_item is self.leveldatatreeview.enemyroutes:
                    group_index = 0
                    index = 0
                    break
                if not hasattr(selected_item, 'bound_to'):
                    continue
                if isinstance(selected_item.bound_to, libbol.EnemyPoint):
                    group_index = selected_item.parent().get_index_in_parent()
                    index = selected_item.get_index_in_parent() + 1
                    break
                if isinstance(selected_item.bound_to, libbol.EnemyPointGroup):
                    group_index = selected_item.get_index_in_parent()
                    index = 0
                    break

            placeobject.group = group_index
            self.level_file.enemypointgroups.groups[group_index].points.insert(index, placeobject)

        elif isinstance(placeobject, libbol.RoutePoint):
            # For convenience, create a group if none exists yet.
            if not self.level_file.routes:
                self.level_file.routes.append(libbol.Route.new())

            group_index = len(self.level_file.routes) - 1
            index = sys.maxsize
            for selected_item in reversed(self.leveldatatreeview.selectedItems()):
                if selected_item is self.leveldatatreeview.routes:
                    group_index = 0
                    index = 0
                    break
                if not hasattr(selected_item, 'bound_to'):
                    continue
                if isinstance(selected_item.bound_to, libbol.RoutePoint):
                    group_index = selected_item.parent().get_index_in_parent()
                    index = selected_item.get_index_in_parent() + 1
                    break
                if isinstance(selected_item.bound_to, libbol.Route):
                    group_index = selected_item.get_index_in_parent()
                    index = 0
                    break

            self.level_file.routes[group_index].points.insert(index, placeobject)

        elif isinstance(placeobject, libbol.MapObject):
            index = sys.maxsize
            for selected_item in reversed(self.leveldatatreeview.selectedItems()):
                if selected_item is self.leveldatatreeview.objects:
                    index = 0
                    break
                if not hasattr(selected_item, 'bound_to'):
                    continue
                if isinstance(selected_item.bound_to, libbol.MapObject):
                    index = selected_item.get_index_in_parent() + 1
                    break

            self.level_file.objects.objects.insert(index, placeobject)

        elif isinstance(placeobject, libbol.KartStartPoint):
            index = sys.maxsize
            for selected_item in reversed(self.leveldatatreeview.selectedItems()):
                if selected_item is self.leveldatatreeview.kartpoints:
                    index = 0
                    break
                if not hasattr(selected_item, 'bound_to'):
                    continue
                if isinstance(selected_item.bound_to, libbol.KartStartPoint):
                    index = selected_item.get_index_in_parent() + 1
                    break

            self.level_file.kartpoints.positions.insert(index, placeobject)

        elif isinstance(placeobject, libbol.JugemPoint):
            index = sys.maxsize
            for selected_item in reversed(self.leveldatatreeview.selectedItems()):
                if selected_item is self.leveldatatreeview.respawnpoints:
                    index = 0
                    break
                if not hasattr(selected_item, 'bound_to'):
                    continue
                if isinstance(selected_item.bound_to, libbol.JugemPoint):
                    index = selected_item.get_index_in_parent() + 1
                    break

            self.level_file.adjust_respawn_point(placeobject)
            self.level_file.respawnpoints.insert(index, placeobject)

        elif isinstance(placeobject, libbol.Area):
            index = sys.maxsize
            for selected_item in reversed(self.leveldatatreeview.selectedItems()):
                if selected_item is self.leveldatatreeview.areas:
                    index = 0
                    break
                if not hasattr(selected_item, 'bound_to'):
                    continue
                if isinstance(selected_item.bound_to, libbol.Area):
                    index = selected_item.get_index_in_parent() + 1
                    break

            self.level_file.areas.areas.insert(index, placeobject)

        elif isinstance(placeobject, libbol.Camera):
            index = sys.maxsize
            for selected_item in reversed(self.leveldatatreeview.selectedItems()):
                if selected_item is self.leveldatatreeview.cameras:
                    index = 0
                    break
                if not hasattr(selected_item, 'bound_to'):
                    continue
                if isinstance(selected_item.bound_to, libbol.Camera):
                    index = selected_item.get_index_in_parent() + 1
                    break

            self.level_file.cameras.insert(index, placeobject)

        self.level_view.do_redraw()
        self.leveldatatreeview.set_objects(self.level_file)
        self.set_has_unsaved_changes(True)
        self.select_tree_item_bound_to([placeobject])

    @catch_exception
    def _insert_object(self, obj, target_list, root_item):
        index = sys.maxsize
        for selected_item in reversed(self.leveldatatreeview.selectedItems()):
            if not hasattr(selected_item, 'bound_to'):
                continue
            selected_obj = selected_item.bound_to
            if selected_item is root_item:
                index = 0
                break
            if isinstance(selected_obj, type(obj)):
                index = 1 + target_list.index(selected_obj)
                break

        target_list.insert(index, obj)

        self.leveldatatreeview.set_objects(self.level_file)
        self.select_tree_item_bound_to([obj])

    def _add_enemy_path(self):
        obj = deepcopy(self._template_enemy_path)
        obj.id = self.level_file.enemypointgroups.new_group_id()
        self._insert_object(
            obj,
            self.level_file.enemypointgroups.groups,
            self.leveldatatreeview.enemyroutes,
        )

    def _add_checkpoint_group(self):
        obj = deepcopy(self._template_checkpoint_group)
        obj.id = self.level_file.checkpoints.new_group_id()
        self._insert_object(
            obj,
            self.level_file.checkpoints.groups,
            self.leveldatatreeview.checkpointgroups,
        )

    def _add_route(self):
        self._insert_object(
            deepcopy(self._template_route),
            self.level_file.routes,
            self.leveldatatreeview.routes,
        )

    def _add_light_param(self):
        self._insert_object(
            deepcopy(self._template_light_param),
            self.level_file.lightparams,
            self.leveldatatreeview.lightparams,
        )

    def _add_minigame_param(self):
        self._insert_object(
            deepcopy(self._template_minigame_param),
            self.level_file.mgentries,
            self.leveldatatreeview.mgentries,
        )

    def _enter_insertion_mode(self, checked: bool, type_name: str):
        self._insertion_mode_type_name = type_name
        move = mkdd_widgets.MOUSE_MODE_INSERTION if checked else mkdd_widgets.MOUSE_MODE_NONE
        self.level_view.set_mouse_mode(move)
        self.next_checkpoint_start_position = None

        self.update_3d()

    def _configure_template(self, label):
        name = label.replace(' ', '_').lower()
        template = getattr(self, f'_template_{name}')
        editor_class = choose_data_editor([template])
        assert editor_class is not None

        editor = editor_class(self, self.level_file, [template])
        editor.update_data()

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f'{label} Template')
        dialog.setMinimumWidth(dialog.fontMetrics().averageCharWidth() * 60)
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.addWidget(editor)
        layout.addStretch()
        dialog.exec()
        dialog.deleteLater()

    @catch_exception
    def action_move_objects(self, deltax, deltay, deltaz):
        for pos in self.level_view.selected_positions:
            """obj.x += deltax
            obj.z += deltaz
            obj.x = round(obj.x, 6)
            obj.z = round(obj.z, 6)
            obj.position_x = obj.x
            obj.position_z = obj.z
            obj.offset_x = 0
            obj.offset_z = 0

            if self.editorconfig.getboolean("GroundObjectsWhenMoving") is True:
                if self.pikmin_gen_view.collision is not None:
                    y = self.pikmin_gen_view.collision.collide_ray_downwards(obj.x, obj.z)
                    obj.y = obj.position_y = round(y, 6)
                    obj.offset_y = 0"""
            pos.x += deltax
            pos.y += deltay
            pos.z += deltaz

        self.level_view.gizmo.move_to_average(self.level_view.selected_positions,
                                              self.level_view.selected_rotations)

        self.level_view.do_redraw()
        self.pik_control.update_info()
        self.set_has_unsaved_changes(True)

    @catch_exception
    def action_move_objects_to(self, posx, posy, posz):
        self.level_view.gizmo.move_to_average(self.level_view.selected_positions,
                                              self.level_view.selected_rotations)
        orig_avg = self.level_view.gizmo.position.copy()
        new_avg = Vector3(posx, posz, -posy)
        diff = new_avg - orig_avg
        for pos in self.level_view.selected_positions:
            pos.x = pos.x + diff.x
            pos.y = pos.y + diff.y
            pos.z = pos.z + diff.z

            self.level_view.gizmo.move_to_average(self.level_view.selected_positions,
                                                  self.level_view.selected_rotations)
        self.level_view.do_redraw()
        self.pik_control.update_info()
        self.set_has_unsaved_changes(True)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if self.level_view.focused:
            if event.key() == QtCore.Qt.Key_Plus:
                self.level_view.zoom_in()
            elif event.key() == QtCore.Qt.Key_Minus:
                self.level_view.zoom_out()

        if event.isAutoRepeat():
            return

        if event.key() == QtCore.Qt.Key_Escape:
            if button := self.level_view.viewer_toolbar.add_button_group.checkedButton():
                button.setChecked(False)
            self.level_view.set_mouse_mode(mkdd_widgets.MOUSE_MODE_NONE)
            self.next_checkpoint_start_position = None

            self.update_3d()

        if self.level_view.focused:
            if event.key() == QtCore.Qt.Key_Shift:
                self.level_view.shift_is_pressed = True

            if event.key() == QtCore.Qt.Key_W:
                self.level_view.MOVE_FORWARD = 1
            elif event.key() == QtCore.Qt.Key_S:
                self.level_view.MOVE_BACKWARD = 1
            elif event.key() == QtCore.Qt.Key_A:
                self.level_view.MOVE_LEFT = 1
            elif event.key() == QtCore.Qt.Key_D:
                self.level_view.MOVE_RIGHT = 1
            elif event.key() == QtCore.Qt.Key_Q:
                self.level_view.MOVE_UP = 1
            elif event.key() == QtCore.Qt.Key_E:
                self.level_view.MOVE_DOWN = 1

    def keyReleaseEvent(self, event: QtGui.QKeyEvent):
        if event.isAutoRepeat():
            return

        if event.key() == QtCore.Qt.Key_Shift:
            self.level_view.shift_is_pressed = False

        if event.key() == QtCore.Qt.Key_W:
            self.level_view.MOVE_FORWARD = 0
        elif event.key() == QtCore.Qt.Key_S:
            self.level_view.MOVE_BACKWARD = 0
        elif event.key() == QtCore.Qt.Key_A:
            self.level_view.MOVE_LEFT = 0
        elif event.key() == QtCore.Qt.Key_D:
            self.level_view.MOVE_RIGHT = 0
        elif event.key() == QtCore.Qt.Key_Q:
            self.level_view.MOVE_UP = 0
        elif event.key() == QtCore.Qt.Key_E:
            self.level_view.MOVE_DOWN = 0

    def reset_move_flags(self):
        self.level_view.MOVE_FORWARD = 0
        self.level_view.MOVE_BACKWARD = 0
        self.level_view.MOVE_LEFT = 0
        self.level_view.MOVE_RIGHT = 0
        self.level_view.MOVE_UP = 0
        self.level_view.MOVE_DOWN = 0
        self.level_view.shift_is_pressed = False

    def action_rotate_object(self, deltarotation):
        #obj.set_rotation((None, round(angle, 6), None))
        for rot in self.level_view.selected_rotations:
            if deltarotation.x != 0:
                rot.rotate_around_y(deltarotation.x)
            elif deltarotation.y != 0:
                rot.rotate_around_z(deltarotation.y)
            elif deltarotation.z != 0:
                rot.rotate_around_x(deltarotation.z)

        if self.rotation_mode.isChecked():
            middle = self.level_view.gizmo.position

            for position in self.level_view.selected_positions:
                diff = position - middle
                diff.y = 0.0

                length = diff.norm()
                if length > 0:
                    diff.normalize()
                    angle = atan2(diff.x, diff.z)
                    angle += deltarotation.y
                    position.x = middle.x + length * sin(angle)
                    position.z = middle.z + length * cos(angle)

        self.level_view.do_redraw()
        self.set_has_unsaved_changes(True)
        self.pik_control.update_info()

    def can_ground_objects(self):
        return bool(self.level_view.selected_positions)

    def action_ground_objects(self, objects=None):
        if not self.can_ground_objects():
            return

        for pos in objects or self.level_view.selected_positions:
            if self.level_view.collision is None:
                return None
            height = self.level_view.collision.collide_ray_closest(pos.x, pos.z, pos.y)

            if height is not None:
                pos.y = height

        self.pik_control.update_info()
        self.level_view.gizmo.move_to_average(self.level_view.selected_positions,
                                              self.level_view.selected_rotations)
        self.set_has_unsaved_changes(True)
        self.level_view.do_redraw()

    def can_delete_objects(self):
        DELETABLE_TYPES = (
            libbol.EnemyPoint,
            libbol.RoutePoint,
            libbol.Checkpoint,
            libbol.MapObject,
            libbol.KartStartPoint,
            libbol.JugemPoint,
            libbol.Area,
            libbol.Camera,
            libbol.CheckpointGroup,
            libbol.EnemyPointGroup,
            libbol.Route,
            libbol.LightParam,
            libbol.MGEntry,
        )

        for obj in self.level_view.selected:
            if isinstance(obj, DELETABLE_TYPES):
                return True
        return False

    def action_delete_objects(self):
        if not self.can_delete_objects():
            return

        for obj in self.level_view.selected:
            if isinstance(obj, libbol.EnemyPoint):
                for group in self.level_file.enemypointgroups.groups:
                    if obj in group.points:
                        group.points.remove(obj)
                        break

            elif isinstance(obj, libbol.RoutePoint):
                for route in self.level_file.routes:
                    if obj in route.points:
                        route.points.remove(obj)
                        break

            elif isinstance(obj, libbol.Checkpoint):
                for group in self.level_file.checkpoints.groups:
                    if obj in group.points:
                        group.points.remove(obj)
                        break

            elif isinstance(obj, libbol.MapObject):
                self.level_file.objects.objects.remove(obj)
            elif isinstance(obj, libbol.KartStartPoint):
                self.level_file.kartpoints.positions.remove(obj)
            elif isinstance(obj, libbol.JugemPoint):
                self.level_file.respawnpoints.remove(obj)
            elif isinstance(obj, libbol.Area):
                self.level_file.areas.areas.remove(obj)
            elif isinstance(obj, libbol.Camera):
                self.level_file.cameras.remove(obj)
            elif isinstance(obj, libbol.CheckpointGroup):
                self.level_file.checkpoints.groups.remove(obj)
            elif isinstance(obj, libbol.EnemyPointGroup):
                self.level_file.enemypointgroups.groups.remove(obj)
            elif isinstance(obj, libbol.Route):
                self.level_file.routes.remove(obj)
            elif isinstance(obj, libbol.LightParam):
                self.level_file.lightparams.remove(obj)
            elif isinstance(obj, libbol.MGEntry):
                self.level_file.mgentries.remove(obj)
        self.level_view.selected = []
        self.level_view.selected_positions = []
        self.level_view.selected_rotations = []

        self.pik_control.reset_info()
        self.leveldatatreeview.set_objects(self.level_file)
        self.level_view.gizmo.hidden = True
        self.level_view.do_redraw()
        self.set_has_unsaved_changes(True)

    def can_distribute_objects(self):
        return len(self.level_view.selected_positions) >= 3

    def action_distribute_objects(self):
        if not self.can_distribute_objects():
            return

        positions = self.level_view.selected_positions
        start_position = positions[0]
        last_position = positions[-1]
        delta = (last_position - start_position) / (len(positions) - 1)

        for i, position in enumerate(positions[1:-1]):
            position.x = start_position.x + delta.x * (i + 1)
            position.y = start_position.y + delta.y * (i + 1)
            position.z = start_position.z + delta.z * (i + 1)

        self.pik_control.update_info()
        self.level_view.gizmo.move_to_average(self.level_view.selected_positions,
                                              self.level_view.selected_rotations)
        self.set_has_unsaved_changes(True)
        self.level_view.do_redraw()

    def on_cut_action_triggered(self):
        self.on_copy_action_triggered()
        self.action_delete_objects()

    def on_copy_action_triggered(self):
        selected = list(self.level_view.selected)

        # If a point (enemy path point, route point, or checkpoint) is selected, but also its parent
        # container is selected, discard the point, to give preference to the entire group.
        for obj in tuple(selected):
            if isinstance(obj, (libbol.EnemyPointGroup, libbol.CheckpointGroup, libbol.Route)):
                for point in obj.points:
                    try:
                        selected.remove(point)
                    except ValueError:
                        pass

        # Copy selection in a logical order that matches the order of the objects in their
        # respective groups. This is relevant to ensure that route-like objects, where order
        # matters, are later pasted in the same order as seen in the current BOL document.
        selected_set = set(selected)
        selected = [obj for obj in self.level_file.get_all_objects() if obj in selected_set]

        # Widgets are unpickleable, so they need to be temporarily stashed. This needs to be done
        # recursively, as top-level groups main contain points associated with widgets too.
        object_to_widget = {}
        pending = list(selected)
        while pending:
            obj = pending.pop(0)
            if hasattr(obj, 'widget'):
                object_to_widget[obj] = obj.widget
                obj.widget = None
            if hasattr(obj, '__dict__'):
                pending.extend(list(obj.__dict__.values()))
            if isinstance(obj, list):
                pending.extend(obj)

        # Equally, route instances assigned to cameras and objects, although pickleable, won't work
        # well when pasted, as the newly constructed Python object wouldn't be a reference to any
        # route instance; they will be temporarily converted to route indexes instead.
        object_camera_routes = []
        for obj in selected:
            if isinstance(obj, (libbol.MapObject, libbol.Camera)):
                object_camera_routes.append((obj, obj.route))
                if obj.route is not None:
                    obj.route = self.level_file.routes.index(obj.route)
                else:
                    obj.route = -1
        # And the same applies to cameras assigned to areas.
        areas_cameras = []
        for obj in selected:
            if isinstance(obj, libbol.Area):
                areas_cameras.append((obj, obj.camera))
                if obj.camera is not None:
                    obj.camera = self.level_file.cameras.index(obj.camera)
                else:
                    obj.camera = -1

        try:
            # Effectively serialize the data.
            data = pickle.dumps(selected)
        finally:
            # Restore the widgets.
            for obj, widget in object_to_widget.items():
                obj.widget = widget
            # Restore the routes instances.
            for obj, route in object_camera_routes:
                obj.route = route
            # Restore the cameras instances.
            for obj, camera in areas_cameras:
                obj.camera = camera

        mimedata = QtCore.QMimeData()
        mimedata.setData("application/mkdd-track-editor", QtCore.QByteArray(data))
        QtWidgets.QApplication.instance().clipboard().setMimeData(mimedata)

    def on_paste_action_triggered(self):
        mimedata = QtWidgets.QApplication.instance().clipboard().mimeData()
        data = bytes(mimedata.data("application/mkdd-track-editor"))
        if not data:
            return

        copied_objects = pickle.loads(data)
        if not copied_objects:
            return

        # The currently selected items are used as reference for the insertion points. For each
        # element kind, we need to figure out the target group, and the index in the target group.
        target_enemy_path = None
        target_enemy_path_index = -1
        target_enemy_point_index = -1
        target_checkpoint_group = None
        target_checkpoint_group_index = -1
        target_checkpoint_index = -1
        target_route = None
        target_route_index = -1
        target_route_point_index = -1
        target_object_index = -1
        target_kart_start_point_index = -1
        target_area_index = -1
        target_camera_index = -1
        target_respawn_point_index = -1
        target_light_param_index = -1
        target_minigame_param_index = -1

        for selected_item in reversed(self.leveldatatreeview.selectedItems()):
            if not hasattr(selected_item, 'bound_to'):
                continue

            selected_obj = selected_item.bound_to

            if selected_item is self.leveldatatreeview.enemyroutes:
                if target_enemy_path_index >= 0:
                    continue
                target_enemy_path_index = 0
            elif isinstance(selected_obj, libbol.EnemyPointGroup):
                if target_enemy_path is not None:
                    continue
                target_enemy_path = selected_obj
                target_enemy_path_index = 1 + self.level_file.enemypointgroups.groups.index(
                    selected_obj)
                target_enemy_point_index = 0
            elif isinstance(selected_obj, libbol.EnemyPoint):
                if target_enemy_point_index >= 0:
                    continue
                for enemy_path in self.level_file.enemypointgroups.groups:
                    if enemy_path.id == selected_obj.group:
                        target_enemy_path = enemy_path
                        target_enemy_point_index = 1 + enemy_path.points.index(selected_obj)
                        break

            elif selected_item is self.leveldatatreeview.checkpointgroups:
                if target_checkpoint_group_index >= 0:
                    continue
                target_checkpoint_group_index = 0
            elif isinstance(selected_obj, libbol.CheckpointGroup):
                if target_checkpoint_group is not None:
                    continue
                target_checkpoint_group = selected_obj
                target_checkpoint_group_index = 1 + self.level_file.checkpoints.groups.index(
                    selected_obj)
                target_checkpoint_index = 0
            elif isinstance(selected_obj, libbol.Checkpoint):
                if target_checkpoint_index >= 0:
                    continue
                for checkpoint_group in self.level_file.checkpoints.groups:
                    if selected_obj in checkpoint_group.points:
                        target_checkpoint_group = checkpoint_group
                        target_checkpoint_index = 1 + checkpoint_group.points.index(selected_obj)
                        break

            elif selected_item is self.leveldatatreeview.routes:
                if target_route_index >= 0:
                    continue
                target_route_index = 0
            elif isinstance(selected_obj, libbol.Route):
                if target_route is not None:
                    continue
                target_route = selected_obj
                target_route_index = 1 + self.level_file.routes.index(selected_obj)
                target_route_point_index = 0
            elif isinstance(selected_obj, libbol.RoutePoint):
                if target_route_point_index >= 0:
                    continue
                for route in self.level_file.routes:
                    if selected_obj in route.points:
                        target_route = route
                        target_route_point_index = 1 + route.points.index(selected_obj)
                        break

            elif selected_item is self.leveldatatreeview.objects:
                if target_object_index >= 0:
                    continue
                target_object_index = 0
            elif isinstance(selected_obj, libbol.MapObject):
                if target_object_index >= 0:
                    continue
                target_object_index = 1 + self.level_file.objects.objects.index(selected_obj)

            elif selected_item is self.leveldatatreeview.kartpoints:
                if target_kart_start_point_index >= 0:
                    continue
                target_kart_start_point_index = 0
            elif isinstance(selected_obj, libbol.KartStartPoint):
                if target_kart_start_point_index >= 0:
                    continue
                target_kart_start_point_index = 1 + self.level_file.kartpoints.positions.index(
                    selected_obj)

            elif selected_item is self.leveldatatreeview.areas:
                if target_area_index >= 0:
                    continue
                target_area_index = 0
            elif isinstance(selected_obj, libbol.Area):
                if target_area_index >= 0:
                    continue
                target_area_index = 1 + self.level_file.areas.areas.index(selected_obj)

            elif selected_item is self.leveldatatreeview.cameras:
                if target_camera_index >= 0:
                    continue
                target_camera_index = 0
            elif isinstance(selected_obj, libbol.Camera):
                if target_camera_index >= 0:
                    continue
                target_camera_index = 1 + self.level_file.cameras.index(selected_obj)

            elif selected_item is self.leveldatatreeview.respawnpoints:
                if target_respawn_point_index >= 0:
                    continue
                target_respawn_point_index = 0
            elif isinstance(selected_obj, libbol.JugemPoint):
                if target_respawn_point_index >= 0:
                    continue
                target_respawn_point_index = 1 + self.level_file.respawnpoints.index(selected_obj)

            elif selected_item is self.leveldatatreeview.lightparams:
                if target_light_param_index >= 0:
                    continue
                target_light_param_index = 0
            elif isinstance(selected_obj, libbol.LightParam):
                if target_light_param_index >= 0:
                    continue
                target_light_param_index = 1 + self.level_file.lightparams.index(selected_obj)

            elif selected_item is self.leveldatatreeview.mgentries:
                if target_minigame_param_index >= 0:
                    continue
                target_minigame_param_index = 0
            elif isinstance(selected_obj, libbol.MGEntry):
                if target_minigame_param_index >= 0:
                    continue
                target_minigame_param_index = 1 + self.level_file.mgentries.index(selected_obj)

        added = []

        for obj in copied_objects:
            # Routes. They may be referenced by other objects; they need to be pasted first.
            if isinstance(obj, libbol.RoutePoint):
                if target_route is None:
                    if not self.level_file.routes:
                        self.level_file.routes.append(libbol.Route.new())
                    target_route = self.level_file.routes[-1]

                if target_route_point_index == -1:
                    target_route.points.append(obj)
                else:
                    target_route.points.insert(target_route_point_index, obj)
                    target_route_point_index += 1

                added.append(obj)

        for obj in copied_objects:
            # Cameras. They may be referenced by other objects; they need to be pasted first.
            if isinstance(obj, libbol.Camera):
                if 0 <= obj.route < len(self.level_file.routes):
                    obj.route = self.level_file.routes[obj.route]
                else:
                    obj.route = None

                if target_camera_index == -1:
                    self.level_file.cameras.append(obj)
                else:
                    self.level_file.cameras.insert(target_camera_index, obj)
                    target_camera_index += 1

                added.append(obj)

        for obj in copied_objects:
            # Group objects.
            if isinstance(obj, libbol.EnemyPointGroup):
                obj.id = self.level_file.enemypointgroups.new_group_id()
                for point in obj.points:
                    point.link = -1
                    point.group_id = obj.id
                if target_enemy_path_index == -1:
                    self.level_file.enemypointgroups.groups.append(obj)
                else:
                    self.level_file.enemypointgroups.groups.insert(target_enemy_path_index, obj)
                    target_enemy_path_index += 1
            elif isinstance(obj, libbol.CheckpointGroup):
                if target_checkpoint_group_index == -1:
                    self.level_file.checkpoints.groups.append(obj)
                else:
                    self.level_file.checkpoints.groups.insert(target_checkpoint_group_index, obj)
                    target_checkpoint_group_index += 1
            elif isinstance(obj, libbol.Route):
                if target_route_index == -1:
                    self.level_file.routes.append(obj)
                else:
                    self.level_file.routes.insert(target_route_index, obj)
                    target_route_index += 1

            # Objects in group objects.
            elif isinstance(obj, libbol.EnemyPoint):
                if target_enemy_path is None:
                    if not self.level_file.enemypointgroups.groups:
                        self.level_file.enemypointgroups.groups.append(libbol.EnemyPointGroup.new())
                    target_enemy_path = self.level_file.enemypointgroups.groups[-1]

                obj.group = target_enemy_path.id
                obj.link = -1
                if target_enemy_point_index == -1:
                    target_enemy_path.points.append(obj)
                else:
                    target_enemy_path.points.insert(target_enemy_point_index, obj)
                    target_enemy_point_index += 1

                # If the enemy point has been prepended or appended, link values need to be updated
                # accordingly.
                if len(target_enemy_path.points) >= 2:
                    if target_enemy_path.points[0] is obj:
                        obj.link = target_enemy_path.points[1].link
                        target_enemy_path.points[1].link = -1
                    elif target_enemy_path.points[-1] is obj:
                        obj.link = target_enemy_path.points[-2].link
                        if len(target_enemy_path.points) >= 3:
                            target_enemy_path.points[-2].link = -1

            elif isinstance(obj, libbol.Checkpoint):
                if target_checkpoint_group is None:
                    if not self.level_file.checkpoints.groups:
                        self.level_file.checkpoints.groups.append(libbol.CheckpointGroup.new())
                    target_checkpoint_group = self.level_file.checkpoints.groups[-1]

                if target_checkpoint_index == -1:
                    target_checkpoint_group.points.append(obj)
                else:
                    target_checkpoint_group.points.append(target_checkpoint_index, obj)
                    target_checkpoint_index += 1

            # Autonomous objects.
            elif isinstance(obj, libbol.MapObject):
                if 0 <= obj.route < len(self.level_file.routes):
                    obj.route = self.level_file.routes[obj.route]
                else:
                    obj.route = None
                if target_object_index == -1:
                    self.level_file.objects.objects.append(obj)
                else:
                    self.level_file.objects.objects.insert(target_object_index, obj)
                    target_object_index += 1
            elif isinstance(obj, libbol.KartStartPoint):
                if target_kart_start_point_index == -1:
                    self.level_file.kartpoints.positions.append(obj)
                else:
                    self.level_file.kartpoints.positions.insert(target_kart_start_point_index, obj)
                    target_kart_start_point_index += 1
            elif isinstance(obj, libbol.JugemPoint):
                max_respawn_id = -1
                for point in self.level_file.respawnpoints:
                    max_respawn_id = max(point.respawn_id, max_respawn_id)
                obj.respawn_id = max_respawn_id + 1
                if target_respawn_point_index == -1:
                    self.level_file.respawnpoints.append(obj)
                else:
                    self.level_file.respawnpoints.insert(target_respawn_point_index, obj)
                    target_respawn_point_index += 1
            elif isinstance(obj, libbol.Area):
                if 0 <= obj.camera < len(self.level_file.cameras):
                    obj.camera = self.level_file.cameras[obj.camera]
                else:
                    obj.camera = None
                if target_area_index == -1:
                    self.level_file.areas.areas.append(obj)
                else:
                    self.level_file.areas.areas.insert(target_area_index, obj)
                    target_area_index += 1
            elif isinstance(obj, libbol.LightParam):
                if target_light_param_index == -1:
                    self.level_file.lightparams.append(obj)
                else:
                    self.level_file.lightparams.insert(target_light_param_index, obj)
                    target_light_param_index += 1
            elif isinstance(obj, libbol.MGEntry):
                if target_minigame_param_index == -1:
                    self.level_file.mgentries.append(obj)
                else:
                    self.level_file.mgentries.insert(target_minigame_param_index, obj)
                    target_minigame_param_index += 1
            else:
                continue

            added.append(obj)

        if not added:
            return

        self.set_has_unsaved_changes(True)
        self.leveldatatreeview.set_objects(self.level_file)

        self.select_tree_item_bound_to(added)
        self.level_view.selected = added
        self.level_view.selected_positions = []
        self.level_view.selected_rotations = []
        for obj in added:
            if hasattr(obj, 'position'):
                self.level_view.selected_positions.append(obj.position)
            if hasattr(obj, 'start') and hasattr(obj, 'end'):
                self.level_view.selected_positions.append(obj.start)
                self.level_view.selected_positions.append(obj.end)
            if hasattr(obj, 'rotation'):
                self.level_view.selected_rotations.append(obj.rotation)

        self.update_3d()

    def update_3d(self):
        self.level_view.gizmo.move_to_average(self.level_view.selected_positions,
                                              self.level_view.selected_rotations)
        self.level_view.do_redraw()

    def select_from_3d_to_treeview(self):
        if self.level_file is not None:
            item = None
            selected = self.level_view.selected
            selected_positions = copy(self.level_view.selected_positions)

            if len(selected) == 1:
                currentobj = selected[0]
                if isinstance(currentobj, libbol.EnemyPoint):
                    for i in range(self.leveldatatreeview.enemyroutes.childCount()):
                        child = self.leveldatatreeview.enemyroutes.child(i)
                        item = get_treeitem(child, currentobj)
                        if item is not None:
                            break

                elif isinstance(currentobj, libbol.Checkpoint):
                    for i in range(self.leveldatatreeview.checkpointgroups.childCount()):
                        child = self.leveldatatreeview.checkpointgroups.child(i)
                        item = get_treeitem(child, currentobj)

                        if item is not None:
                            break

                elif isinstance(currentobj, libbol.RoutePoint):
                    for i in range(self.leveldatatreeview.routes.childCount()):
                        child = self.leveldatatreeview.routes.child(i)
                        item = get_treeitem(child, currentobj)
                        if item is not None:
                            break

                elif isinstance(currentobj, libbol.MapObject):
                    item = get_treeitem(self.leveldatatreeview.objects, currentobj)
                elif isinstance(currentobj, libbol.Camera):
                    item = get_treeitem(self.leveldatatreeview.cameras, currentobj)
                elif isinstance(currentobj, libbol.Area):
                    item = get_treeitem(self.leveldatatreeview.areas, currentobj)
                elif isinstance(currentobj, libbol.JugemPoint):
                    item = get_treeitem(self.leveldatatreeview.respawnpoints, currentobj)
                elif isinstance(currentobj, libbol.KartStartPoint):
                    item = get_treeitem(self.leveldatatreeview.kartpoints, currentobj)

                # Temporarily suppress signals to prevent both checkpoints from
                # being selected when just one checkpoint is selected in 3D view.
                suppress_signal = False
                if (isinstance(currentobj, libbol.Checkpoint)
                    and (currentobj.start in self.level_view.selected_positions
                         or currentobj.end in self.level_view.selected_positions)):
                    suppress_signal = True

                if suppress_signal:
                    self.leveldatatreeview.blockSignals(True)

                if item is not None:
                    self.leveldatatreeview.setCurrentItem(item)
                    self.level_view.selected_positions = selected_positions

                if suppress_signal:
                    self.leveldatatreeview.blockSignals(False)

            if item is None or suppress_signal:
                # If no item was selected, or the signal was suppressed, no tree item will be
                # selected, and the data editor needs to be updated manually.
                self.action_update_info()

                # Without emitting any signal, programmatically update the currently selected item
                # in the tree view.
                with QtCore.QSignalBlocker(self.leveldatatreeview):
                    if selected:
                        self.select_tree_item_bound_to(selected)
                    else:
                        # If no selection occurred, ensure that no tree item remains selected. This
                        # is relevant to ensure that non-pickable objects (such as the top-level
                        # items) do not remain selected when the user clicks on an empty space in
                        # the viewport.
                        for selected_item in self.leveldatatreeview.selectedItems():
                            selected_item.setSelected(False)

    @catch_exception
    def action_update_info(self):
        if self.level_file is not None:
            selected = self.level_view.selected
            objects = []
            if len(selected) == 1:
                currentobj = selected[0]
                if isinstance(currentobj, Route):
                    index = self.level_file.routes.index(currentobj)
                    for object in self.level_file.objects.objects:
                        if object.route == currentobj:
                            objects.append(get_full_name(object.objectid))
                    for i, camera in enumerate(self.level_file.cameras):
                        if camera.route == currentobj:
                            objects.append("Camera {0}".format(i))
            else:
                self.pik_control.reset_info("{0} objects selected".format(len(self.level_view.selected)))
                self.pik_control.set_objectlist(selected)

            viewer_toolbar = self.level_view.viewer_toolbar
            viewer_toolbar.delete_button.setEnabled(self.can_delete_objects())
            viewer_toolbar.ground_button.setEnabled(self.can_ground_objects())
            viewer_toolbar.distribute_button.setEnabled(self.can_distribute_objects())

            self.pik_control.set_info(selected, self.update_3d, objects)
            self.pik_control.update_info()

    @catch_exception
    def mapview_showcontextmenu(self, position):
        self.reset_move_flags()

        context_menu = QtWidgets.QMenu(self)
        action = QtGui.QAction("Copy Coordinates", self)
        action.triggered.connect(self.action_copy_coords_to_clipboard)
        context_menu.addAction(action)

        selected = self.level_view.selected
        if len(selected) == 1:
            item = selected[0]
            if isinstance(item, libbol.Area):
                select_all_action = QtGui.QAction("Select All with Same Type", self)
                select_all_action.triggered.connect(lambda:
                                                    self.select_area_type(item))
                context_menu.addAction(select_all_action)

                if item.area_type == 1:
                    select_assoc_action = QtGui.QAction("Select Associated Camera + Route", self)
                    select_assoc_action.triggered.connect(lambda:
                                                          self.select_area_assoc(item))
                    context_menu.addAction(select_assoc_action)
            elif isinstance(item, (libbol.MapObject, libbol.Camera)) and item.route is not None:
                if isinstance(item, libbol.MapObject):
                    select_object_id = QtGui.QAction("Select All with Same ID", self)
                    select_object_id.triggered.connect(lambda:
                                                        self.select_object_type(item))
                    context_menu.addAction(select_object_id)
                select_assoc_action = QtGui.QAction("Select Associated Route", self)
                select_assoc_action.triggered.connect(lambda:
                                                        self.select_route_assoc(item))
                context_menu.addAction(select_assoc_action)
            elif isinstance(item, libbol.RoutePoint):
                select_all_group = QtGui.QAction("Select All Points in Route", self)
                select_all_group.triggered.connect(lambda:
                                                        self.select_route_points(item))
                context_menu.addAction(select_all_group)

        context_menu.exec(self.level_view.mapToGlobal(position))
        context_menu.destroy()

    def action_copy_coords_to_clipboard(self):
        if self.current_coordinates is not None:
            QtWidgets.QApplication.clipboard().setText(", ".join(
                str(x) for x in self.current_coordinates))

    def action_update_position(self, pos):
        self.current_coordinates = pos

        y_coord = f"{pos[1]:.2f}" if pos[1] is not None else "-"

        display_string = f"🖱️ ({pos[0]:.2f}, {y_coord}, {pos[2]:.2f})"

        selected = self.level_view.selected
        if len(selected) == 1 and hasattr(selected[0], "position"):

            obj_pos = selected[0].position
            display_string += f"   📦 ({obj_pos.x:.2f}, {obj_pos.y:.2f}, {obj_pos.z:.2f})"

            if self.level_view.collision is not None:
                height = self.level_view.collision.collide_ray_closest(obj_pos.x, obj_pos.z, obj_pos.y)
                if height is not None:
                    display_string += f"   📏 {obj_pos.y - height:.2f}"

        self.statusbar.showMessage(display_string)

    def dragEnterEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            url = mime_data.urls()[0]
            filepath = url.toLocalFile()
            ext = os.path.splitext(filepath)[1].lower()
            if ext in (".bol", ".arc", ".bmd", ".bco"):
                event.acceptProposedAction()

    def dropEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            url = mime_data.urls()[0]
            filepath = url.toLocalFile()
            ext = os.path.splitext(filepath)[1].lower()
            if ext in (".bol", ".arc"):
                self.button_load_level(filepath, update_config=False)
            elif ext == ".bco":
                self.load_optional_bco(filepath)
            elif ext == ".bmd":
                self.load_optional_bmd(filepath)


def find_file(rarc_folder, ending):
    for filename in rarc_folder.files.keys():
        if filename.endswith(ending):
            return filename
    raise RuntimeError("No Course File found!")


def get_file_safe(rarc_folder, ending):
    for filename in rarc_folder.files.keys():
        if filename.endswith(ending):
            return rarc_folder.files[filename]
    return None


import sys
def except_hook(cls, exception, traceback):
    sys.__excepthook__(cls, exception, traceback)



POTENTIALLY_EDITING_EVENTS = (
    QtCore.QEvent.KeyRelease,
    QtCore.QEvent.MouseButtonRelease,
)


class Application(QtWidgets.QApplication):

    document_potentially_changed = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._pending_focus_change = False

        self.focusChanged.connect(self._on_focus_changed)

    def notify(self, receiver: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() in POTENTIALLY_EDITING_EVENTS:
            if isinstance(receiver, QtGui.QWindow):
                # Certain widget types are known to submit many value changes while they have focus.
                # Potentially-editing events will be disregarded until focus is out (unless there
                # have been a recent focus change)
                disregardable = isinstance(self.focusWidget(), QtWidgets.QAbstractSpinBox)
                if not disregardable or self._pending_focus_change:
                    self._pending_focus_change = False
                    QtCore.QTimer.singleShot(0, self.document_potentially_changed)

        return super().notify(receiver, event)

    def _on_focus_changed(self, old: QtWidgets.QWidget, now: QtWidgets.QWidget):
        _ = old, now
        self._pending_focus_change = True


if __name__ == "__main__":
    #import sys
    import platform
    import signal
    import argparse

    QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.English))

    sys.excepthook = except_hook

    parser = argparse.ArgumentParser()
    parser.add_argument("--load", default=None,
                        help="Path to the ARC or BOL file to be loaded.")
    parser.add_argument("--additional", default=None, choices=['model', 'collision'],
                        help="Whether to also load the additional BMD file (3D model) or BCO file "
                        "(collision file).")

    args = parser.parse_args()

    os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '0'
    app = Application(sys.argv)

    signal.signal(signal.SIGINT, lambda _signal, _frame: app.quit())

    app.setStyle(QtWidgets.QStyleFactory.create("Fusion"))

    role_colors = []
    role_colors.append((QtGui.QPalette.Window, QtGui.QColor(60, 60, 60)))
    role_colors.append((QtGui.QPalette.WindowText, QtGui.QColor(200, 200, 200)))
    role_colors.append((QtGui.QPalette.Base, QtGui.QColor(25, 25, 25)))
    role_colors.append((QtGui.QPalette.AlternateBase, QtGui.QColor(60, 60, 60)))
    role_colors.append((QtGui.QPalette.ToolTipBase, QtGui.QColor(40, 40, 40)))
    role_colors.append((QtGui.QPalette.ToolTipText, QtGui.QColor(200, 200, 200)))
    try:
        role_colors.append((QtGui.QPalette.PlaceholderText, QtGui.QColor(160, 160, 160)))
    except AttributeError:
        pass
    role_colors.append((QtGui.QPalette.Text, QtGui.QColor(200, 200, 200)))
    role_colors.append((QtGui.QPalette.Button, QtGui.QColor(55, 55, 55)))
    role_colors.append((QtGui.QPalette.ButtonText, QtGui.QColor(200, 200, 200)))
    role_colors.append((QtGui.QPalette.BrightText, QtCore.Qt.red))
    role_colors.append((QtGui.QPalette.Light, QtGui.QColor(65, 65, 65)))
    role_colors.append((QtGui.QPalette.Midlight, QtGui.QColor(60, 60, 60)))
    role_colors.append((QtGui.QPalette.Dark, QtGui.QColor(45, 45, 45)))
    role_colors.append((QtGui.QPalette.Mid, QtGui.QColor(50, 50, 50)))
    role_colors.append((QtGui.QPalette.Shadow, QtCore.Qt.black))
    role_colors.append((QtGui.QPalette.Highlight, QtGui.QColor(45, 140, 225)))
    role_colors.append((QtGui.QPalette.HighlightedText, QtCore.Qt.black))
    role_colors.append((QtGui.QPalette.Link, QtGui.QColor(40, 130, 220)))
    role_colors.append((QtGui.QPalette.LinkVisited, QtGui.QColor(110, 70, 150)))
    palette = QtGui.QPalette()
    for role, color in role_colors:
        palette.setColor(QtGui.QPalette.Disabled, role, QtGui.QColor(color).darker())
        palette.setColor(QtGui.QPalette.Active, role, color)
        palette.setColor(QtGui.QPalette.Inactive, role, color)
    app.setPalette(palette)

    QtWidgets.QToolTip.setPalette(palette)
    padding = QtGui.QFontMetrics(QtGui.QFont()).height() // 2
    app.setStyleSheet(f"""
        QToolTip {{
            padding: {padding}px;
            border: 1px solid #202020;
            background: #282828;
        }}
    """)

    if platform.system() == "Windows":
        import ctypes
        myappid = 'P2GeneratorsEditor'  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    os.makedirs("lib/temp", exist_ok=True)

    with open("log.txt", "w") as f:
        #sys.stdout = f
        #sys.stderr = f
        editor_gui = GenEditor()
        editor_gui.setWindowIcon(QtGui.QIcon('resources/icon.ico'))

        app.document_potentially_changed.connect(
            editor_gui.on_document_potentially_changed)

        editor_gui.show()

        app.editor_gui = editor_gui

        if args.load is not None:
            def load():
                editor_gui.load_file(args.load, additional=args.additional)

            QtCore.QTimer.singleShot(0, load)

        err_code = app.exec()

    sys.exit(err_code)
