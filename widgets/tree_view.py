from PySide6 import QtCore, QtGui, QtWidgets

from lib.libbol import BOL, get_full_name, AREA_TYPES, KART_START_POINTS_PLAYER_IDS


class BaseTreeWidgetItem(QtWidgets.QTreeWidgetItem):

    dim_color = None

    def get_index_in_parent(self):
        return self.parent().indexOfChild(self)

    def dim_label(self, dim: bool):
        self.setForeground(0, self.dim_color if dim else QtGui.QBrush())


class BolHeader(BaseTreeWidgetItem):
    def __init__(self):
        super().__init__()
        self.setText(0, "Track Settings")


class ObjectGroup(BaseTreeWidgetItem):
    def __init__(self, name, parent=None, bound_to=None):
        if parent is None:
            super().__init__()
        else:
            super().__init__(parent)
        self.setText(0, name)
        self.bound_to = bound_to
        if bound_to is not None:
            bound_to.widget = self

    def remove_children(self):
        self.takeChildren()


class ObjectGroupObjects(ObjectGroup):
    def sort(self):
        """items = []
        for i in range(self.childCount()):
            items.append(self.takeChild(0))

        items.sort(key=lambda x: x.bound_to.objectid)

        for item in items:
            self.addChild(item)"""
        self.sortChildren(0, QtCore.Qt.SortOrder.AscendingOrder)


# Groups
class EnemyPointGroup(ObjectGroup):
    def __init__(self, parent, bound_to):
        super().__init__("Enemy Path", parent=parent, bound_to=bound_to)
        bound_to.widget = self
        self.update_name()

    def update_name(self):
        index = self.parent().indexOfChild(self)
        if self.bound_to.points:
            link_start = self.bound_to.points[0].link
            link_end = self.bound_to.points[-1].link
        else:
            link_start = link_end = '?'
        self.setText(
            0,
            "Enemy Path {0} (ID: {1}, link: {2}->{3})".format(index,
                                                                     self.bound_to.id,
                                                                     link_start,
                                                                     link_end))


class CheckpointGroup(ObjectGroup):
    def __init__(self, parent, bound_to):
        super().__init__("Checkpoint Group", parent=parent, bound_to=bound_to)
        self.update_name()

    def update_name(self):
        index = self.parent().indexOfChild(self)
        self.setText(0, "Checkpoint Group {0}".format(index))


class ObjectPointGroup(ObjectGroup):
    def __init__(self, parent, bound_to):
        super().__init__("Route", parent=parent, bound_to=bound_to)
        self.update_name()

    def update_name(self):
        index = self.parent().indexOfChild(self)
        self.setText(0, "Route {0}".format(index))


# Entries in groups or entries without groups
class NamedItem(BaseTreeWidgetItem):
    def __init__(self, parent, name, bound_to, index=None):
        super().__init__(parent)
        self.setText(0, name)
        self.bound_to = bound_to
        if bound_to is not None:
            bound_to.widget = self
        self.index = index
        self.update_name()

    def update_name(self):
        pass


class EnemyRoutePoint(NamedItem):

    def update_name(self):
        self.dim_label(self.bound_to.hidden)

        group_item = self.parent()
        group = group_item.bound_to
        offset = 0
        groups_item = group_item.parent()

        for i in range(groups_item.childCount()):
            other_group_item = groups_item.child(i)
            if other_group_item == group_item:
                break
            else:
                #print("Hmmm,", other_group_item.text(0), len(other_group_item.bound_to.points), offset)
                group_object = other_group_item.bound_to
                offset += len(group_object.points)


        index = group.points.index(self.bound_to)
        point = group.points[index]

        if point.link == -1:
            self.setText(0, "Enemy Point {0} (pos={1})".format(index + offset, index))
        else:
            self.setText(
                0,
                "Enemy Point {0} (pos={1}, link={2})".format(index + offset,
                                                                   index,
                                                                   point.link))


class Checkpoint(NamedItem):
    def update_name(self):
        self.dim_label(self.bound_to.hidden)

        offset = 0
        group_item = self.parent()
        groups_item = group_item.parent()
        for i in range(groups_item.childCount()):
            other_group_item = groups_item.child(i)
            if other_group_item == group_item:
                break
            else:
                group_object = other_group_item.bound_to
                offset += len(group_object.points)

        group = group_item.bound_to

        index = group.points.index(self.bound_to)

        self.setText(0, "Checkpoint {0} (pos={1})".format(index+offset, index))


class ObjectRoutePoint(NamedItem):
    def update_name(self):
        self.dim_label(self.bound_to.hidden)

        group_item = self.parent()
        group = group_item.bound_to

        index = group.points.index(self.bound_to)

        self.setText(0, "Route Point {0}".format(index))


class ObjectEntry(NamedItem):

    def update_name(self):
        self.dim_label(self.bound_to.hidden)
        self.setText(0, get_full_name(self.bound_to.objectid))

    def __lt__(self, other):
        return self.bound_to.objectid < other.bound_to.objectid


class KartpointEntry(NamedItem):

    def update_name(self):
        self.dim_label(self.bound_to.hidden)
        playerid = self.bound_to.playerid
        self.setText(0, f'Kart Start Point ({KART_START_POINTS_PLAYER_IDS[playerid]})')


class AreaEntry(NamedItem):

    def update_name(self):
        self.dim_label(self.bound_to.hidden)
        self.setText(0, f'{AREA_TYPES[self.bound_to.area_type]} {self.index}')


class CameraEntry(NamedItem):

    def update_name(self, intro_cameras=None, area_cameras=None):
        self.dim_label(self.bound_to.hidden)

        if intro_cameras is None or area_cameras is None:
            bol = self.treeWidget().editor.level_file
            intro_cameras, _cycle_detected = bol.get_intro_cameras()
            area_cameras = bol.get_cameras_bound_to_areas()

        camera = self.bound_to

        camera_tags = ''
        try:
            intro_camera_index = intro_cameras.index(camera)
            camera_tags += f' - Intro {intro_camera_index + 1}/{len(intro_cameras)}'
        except ValueError:
            pass
        area_indexes = area_cameras.get(camera)
        if area_indexes is not None:
            if len(area_indexes) == 1:
                camera_tags += f' - Replay Area: {area_indexes[0]}'
            else:
                area_indexes = ', '.join(str(i) for i in area_indexes)
                camera_tags += f' - Replay Areas: {area_indexes}'

        self.setText(0, f"Camera {self.index} ({camera.camtype:03X}){camera_tags}")


class RespawnEntry(NamedItem):

    def update_name(self):
        self.dim_label(self.bound_to.hidden)
        for i in range(self.parent().childCount()):
            if self == self.parent().child(i):
                self.setText(0, "Respawn Point {0} (ID: {1} / 0x{1:02X})".format(i, self.bound_to.respawn_id))
                break


class LightParamEntry(NamedItem):
    def update_name(self):
        self.setText(0, "LightParam {0}".format(self.index))


class MGEntry(NamedItem):
    def update_name(self):
        self.setText(0, "MG")


class LevelDataTreeView(QtWidgets.QTreeWidget):
    select_all = QtCore.Signal(ObjectGroup)
    reverse = QtCore.Signal(ObjectGroup)
    duplicate = QtCore.Signal(ObjectGroup)
    split = QtCore.Signal(EnemyPointGroup, EnemyRoutePoint)
    split_checkpoint = QtCore.Signal(CheckpointGroup, Checkpoint)
    select_object_type = QtCore.Signal(ObjectEntry)
    select_area_type = QtCore.Signal(AreaEntry)
    select_area_assoc = QtCore.Signal(AreaEntry)
    select_route_assoc = QtCore.Signal(NamedItem)
    select_route_points = QtCore.Signal(ObjectRoutePoint)

    def __init__(self, editor, *args, **kwargs):
        super().__init__(*args, **kwargs)

        BaseTreeWidgetItem.dim_color = self.palette().light()

        self.editor = editor

        self.resize(200, self.height())
        self.setColumnCount(1)
        self.setHeaderLabel("Track Data Entries")
        self.setHeaderHidden(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.bolheader = BolHeader()
        self.addTopLevelItem(self.bolheader)

        self.enemyroutes = self._add_group("Enemy Paths")
        self.checkpointgroups = self._add_group("Checkpoint Groups")
        self.routes = self._add_group("Routes")
        self.objects = self._add_group("Objects", ObjectGroupObjects)
        self.kartpoints = self._add_group("Kart Start Points")
        self.areas = self._add_group("Areas")
        self.cameras = self._add_group("Cameras")
        self.respawnpoints = self._add_group("Respawn Points")
        self.lightparams = self._add_group("Light Params")
        self.mgentries = self._add_group("Minigame Params")

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.run_context_menu)

    def run_context_menu(self, pos):
        item = self.itemAt(pos)
        context_menu = QtWidgets.QMenu(self)

        if isinstance(item, (EnemyRoutePoint, )):
            split_action = QtGui.QAction("Split Group At", self)

            def emit_current_split():
                item = self.itemAt(pos)
                group_item = item.parent()
                self.split.emit(group_item, item)

            split_action.triggered.connect(emit_current_split)

            context_menu.addAction(split_action)
        elif isinstance(item, (Checkpoint, )):
            split_action = QtGui.QAction("Split Group At", self)

            def emit_current_split():
                item = self.itemAt(pos)
                group_item = item.parent()
                self.split_checkpoint.emit(group_item, item)

            split_action.triggered.connect(emit_current_split)

            context_menu.addAction(split_action)
        elif isinstance(item, (EnemyPointGroup, ObjectPointGroup, CheckpointGroup)):
            select_all_action = QtGui.QAction("Select All", self)
            reverse_action = QtGui.QAction("Reverse", self)

            def emit_current_selectall():
                item = self.itemAt(pos)
                self.select_all.emit(item)

            def emit_current_reverse():
                item = self.itemAt(pos)
                self.reverse.emit(item)



            select_all_action.triggered.connect(emit_current_selectall)
            reverse_action.triggered.connect(emit_current_reverse)

            context_menu.addAction(select_all_action)
            context_menu.addAction(reverse_action)

            if isinstance(item, EnemyPointGroup):
                def emit_current_duplicate():
                    item = self.itemAt(pos)
                    self.duplicate.emit(item)

                duplicate_action = QtGui.QAction("Duplicate", self)
                duplicate_action.triggered.connect(emit_current_duplicate)
                context_menu.addAction(duplicate_action)
        elif isinstance(item, ObjectEntry):

            select_all_action = QtGui.QAction("Select All with Same ID", self)

            def emit_select_areas():
                item = self.itemAt(pos)
                self.select_object_type.emit(item)

            select_all_action.triggered.connect(emit_select_areas)

            context_menu.addAction(select_all_action)
        elif isinstance(item, AreaEntry):
            select_all_action = QtGui.QAction("Select All with Same Type", self)

            def emit_select_areas():
                item = self.itemAt(pos)
                self.select_area_type.emit(item)

            select_all_action.triggered.connect(emit_select_areas)

            context_menu.addAction(select_all_action)

            if item.bound_to.area_type == 1:
                select_assoc_action = QtGui.QAction("Select Associated", self)
                def emit_area_assoc():
                    item = self.itemAt(pos)
                    self.select_area_assoc.emit(item)

                select_assoc_action.triggered.connect(emit_area_assoc)

                context_menu.addAction(select_assoc_action)
        elif isinstance(item, ObjectRoutePoint):
            select_all_group = QtGui.QAction("Select All Points in Route", self)

            def emit_select_route():
                item = self.itemAt(pos)
                self.select_route_points.emit(item)

            select_all_group.triggered.connect(emit_select_route)

            context_menu.addAction(select_all_group)

        if isinstance(item, (ObjectEntry, CameraEntry)):
            if item.bound_to.route is not None:
                select_assoc_action = QtGui.QAction("Select Associated Route", self)

                def emit_route_assoc():
                    item = self.itemAt(pos)
                    self.select_route_assoc.emit(item)

                select_assoc_action.triggered.connect(emit_route_assoc)

                context_menu.addAction(select_assoc_action)

        if context_menu.actions():
            context_menu.exec(self.mapToGlobal(pos))
            context_menu.destroy()
            del context_menu

    def _add_group(self, name, customgroup=None):
        if customgroup is None:
            group = ObjectGroup(name)
        else:
            group = customgroup(name)
        self.addTopLevelItem(group)
        return group

    def _reset(self):
        with QtCore.QSignalBlocker(self):  # Avoid triggering item selection changed events.
            self.bolheader.setSelected(False)
            self.enemyroutes.setSelected(False)
            self.checkpointgroups.setSelected(False)
            self.routes.setSelected(False)
            self.objects.setSelected(False)
            self.kartpoints.setSelected(False)
            self.areas.setSelected(False)
            self.cameras.setSelected(False)
            self.respawnpoints.setSelected(False)
            self.lightparams.setSelected(False)
            self.mgentries.setSelected(False)

            self.enemyroutes.remove_children()
            self.checkpointgroups.remove_children()
            self.routes.remove_children()
            self.objects.remove_children()
            self.kartpoints.remove_children()
            self.areas.remove_children()
            self.cameras.remove_children()
            self.respawnpoints.remove_children()
            self.lightparams.remove_children()
            self.mgentries.remove_children()

    def set_objects(self, boldata: BOL):
        # Compute the location (based on indexes) of the currently selected items, if any.
        selected_item_indexes_list = []
        for item in self.selectedItems():
            selected_item_indexes = []
            while item is not None:
                parent_item = item.parent()
                if parent_item is not None:
                    selected_item_indexes.insert(0, parent_item.indexOfChild(item))
                else:
                    selected_item_indexes.insert(0, self.indexOfTopLevelItem(item))
                item = parent_item
            if selected_item_indexes:
                selected_item_indexes_list.append(selected_item_indexes)

        if selected_item_indexes_list:
            initial_item_count = self.count_items()

        # Preserve the expansion state of the top-level items that can have nested groups.
        enemyroutes_expansion_states = self._get_expansion_states(self.enemyroutes)
        checkpointgroups_expansion_states = self._get_expansion_states(self.checkpointgroups)
        routes_expansion_states = self._get_expansion_states(self.routes)

        self._reset()

        for group in boldata.enemypointgroups.groups:
            group_item = EnemyPointGroup(self.enemyroutes, group)

            for point in group.points:
                point_item = EnemyRoutePoint(group_item, "Enemy Route Point", point)

        for group in boldata.checkpoints.groups:
            group_item = CheckpointGroup(self.checkpointgroups, group)

            for point in group.points:
                point_item = Checkpoint(group_item, "Checkpoint", point)

        for route in boldata.routes:
            route_item = ObjectPointGroup(self.routes, route)

            for point in route.points:
                point_item = ObjectRoutePoint(route_item, "Route Point", point)

        for object in boldata.objects.objects:
            object_item = ObjectEntry(self.objects, "Object", object)

        self.sort_objects()

        for kartpoint in boldata.kartpoints.positions:
            item = KartpointEntry(self.kartpoints, "Kartpoint", kartpoint)

        for i, area in enumerate(boldata.areas.areas):
            item = AreaEntry(self.areas, "Area", area, i)

        for respawn in boldata.respawnpoints:
            item = RespawnEntry(self.respawnpoints, "Respawn", respawn)

        for i, camera in enumerate(boldata.cameras):
            item = CameraEntry(self.cameras, "Camera", camera, i)

        for i, lightparam in enumerate(boldata.lightparams):
            item = LightParamEntry(self.lightparams, "LightParam", lightparam, i)

        for mg in boldata.mgentries:
            item = MGEntry(self.mgentries, "MG", mg)

        # Restore expansion states.
        self._set_expansion_states(self.enemyroutes, enemyroutes_expansion_states)
        self._set_expansion_states(self.checkpointgroups, checkpointgroups_expansion_states)
        self._set_expansion_states(self.routes, routes_expansion_states)

        # And restore previous selection, but only if item counts match, or else indexes could be
        # unreliable. Top-level items always exist, so they can be restored even when the count has
        # changed.
        items_to_select = []
        if selected_item_indexes_list:
            only_top_level_items = initial_item_count != self.count_items()

            for selected_item_indexes in selected_item_indexes_list:
                if only_top_level_items and len(selected_item_indexes) != 1:
                    continue

                item = self.topLevelItem(selected_item_indexes.pop(0))
                while selected_item_indexes:
                    index = selected_item_indexes.pop(0)
                    if index < item.childCount():
                        item = item.child(index)
                    else:
                        break
                items_to_select.append(item)

            # Effectively select items without relying on signals which could trigger a considerate
            # number of events for each item.
            with QtCore.QSignalBlocker(self):
                for item in items_to_select:
                    item.setSelected(True)
        self.editor.tree_select_object(items_to_select)

        self.bound_to_group(boldata)

    def sort_objects(self):
        self.objects.sort()
        """items = []
        for i in range(self.objects.childCount()):
            items.append(self.objects.takeChild(0))

        items.sort(key=lambda x: x.bound_to.objectid)

        for item in items:
            self.objects.addChild(item)"""

    def _get_expansion_states(self, parent_item: QtWidgets.QTreeWidgetItem) -> 'tuple[bool]':
        expansion_states = []
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            expansion_states.append(item.isExpanded())
        return expansion_states

    def _set_expansion_states(self, parent_item: QtWidgets.QTreeWidgetItem,
                              expansion_states: 'tuple[bool]'):
        item_count = parent_item.childCount()
        if item_count != len(expansion_states):
            # If the number of children has changed, it is not possible to reliably restore the
            # state without being very wrong in some cases.
            return

        for i in range(item_count):
            item = parent_item.child(i)
            item.setExpanded(expansion_states[i])

    def count_items(self):
        count = 0

        pending_items = []
        for i in range(self.topLevelItemCount()):
            pending_items.append(self.topLevelItem(i))

        while pending_items:
            item = pending_items.pop()
            count += 1

            for i in range(item.childCount()):
                pending_items.append(item.child(i))

        return count

    def bound_to_group(self, levelfile):
        self.enemyroutes.bound_to = levelfile.enemypointgroups
        self.checkpointgroups.bound_to = levelfile.checkpoints
        self.routes.bound_to = levelfile.routes
        self.objects.bound_to = levelfile.objects
        self.kartpoints.bound_to = levelfile.kartpoints
        self.areas.bound_to = levelfile.areas
        self.cameras.bound_to = levelfile.cameras
        self.respawnpoints.bound_to = levelfile.respawnpoints
        self.lightparams.bound_to = levelfile.lightparams

    def update_camera_names(self):
        bol = self.editor.level_file
        intro_cameras, _cycle_detected = bol.get_intro_cameras()
        area_cameras = bol.get_cameras_bound_to_areas()
        top_level_item = self.cameras
        for i in range(top_level_item.childCount()):
            tree_item = top_level_item.child(i)
            tree_item.update_name(intro_cameras, area_cameras)
