from math import pi, tan, atan2, degrees, cos, sin

import abc

from PySide6 import QtCore

from lib.vectors import Vector3, Plane
from gizmo import AXIS_X, AXIS_Y, AXIS_Z
import numpy
MOUSE_MODE_NONE = 0
MOUSE_MODE_INSERTION = 1

MODE_TOPDOWN = 0
MODE_3D = 1


key_enums = {
    "Middle": QtCore.Qt.MiddleButton,
    "Left": QtCore.Qt.LeftButton,
    "Right": QtCore.Qt.RightButton
}


class Buttons(object):
    def __init__(self):
        self._buttons = {}
        for key in key_enums:
            self._buttons[key] = False

    def update_status(self, event):
        for key in key_enums:
            self._buttons = event.buttons() & key_enums[key]

    def just_pressed(self, event, key):
        return not self._buttons[key] and self.is_held(event, key)

    def is_held(self, event, key):
        self._buttons[key] = event.buttons() & key_enums[key]
        return self._buttons[key]

    def just_released(self, event, key):
        return self._buttons[key] and not self.is_held(event, key)


class MouseAction(object):
    def __init__(self, name):
        self.name = name

    def condition(self, editor, buttons, event):
        return True


class ClickAction(MouseAction):
    def __init__(self, name, key):
        super().__init__(name)
        self.key = key
        assert key in key_enums

    def condition(self, editor, buttons, event):
        return True

    def just_clicked(self, editor, buttons, event):
        pass

    def move(self, editor, buttons, event):
        pass

    def just_released(self, editor, buttons, event):
        pass


class ClickDragAction(MouseAction):
    def __init__(self, name, key):
        super().__init__(name)
        self.key = key
        assert key in key_enums

        self.first_click = None

    def just_clicked(self, editor, buttons, event):
        self.first_click = event.position().toPoint()

    def move(self, editor, buttons, event):

        pass

    def just_released(self, editor, buttons, event):
        self.first_click = None


class TopdownScroll(ClickDragAction):
    def move(self, editor, buttons, event):
        x, y = event.x(), event.y()
        d_x, d_y = event.x() - self.first_click.x(), event.y() - self.first_click.y()

        if editor.zoom_factor > 1.0:
            adjusted_dx = d_x * editor.zoom_factor  # (1.0 + (self.zoom_factor - 1.0))
            adjusted_dz = d_y * editor.zoom_factor  # (1.0 + (self.zoom_factor - 1.0))
        else:
            adjusted_dx = d_x
            adjusted_dz = d_y

        editor.offset_x += adjusted_dx
        editor.offset_z += adjusted_dz
        editor.do_redraw()
        self.first_click = event.position().toPoint()


class TopdownSelect(ClickDragAction):
    def condition(self, editor, buttons, event):
        return (editor.gizmo.was_hit_at_all is not True) and editor.mousemode == MOUSE_MODE_NONE

    def just_clicked(self, editor, buttons, event):
        super().just_clicked(editor, buttons, event)
        x, y = self.first_click.x(), self.first_click.y()

        selectstartx, selectstartz = editor.mouse_coord_to_world_coord(x, y)

        editor.selectionbox_start = (selectstartx, selectstartz)
        editor.selectionbox_end = None

    def move(self, editor, buttons, event):
        selectendx, selectendz = editor.mouse_coord_to_world_coord(event.x(), event.y())
        editor.selectionbox_end = (selectendx, selectendz)
        editor.do_redraw()

    def just_released(self, editor, buttons, event):
        selectstartx, selectstartz = self.first_click.x(), self.first_click.y()
        selectendx, selectendz = event.x(), event.y()

        startx = min(selectstartx, selectendx)
        endx = max(selectstartx, selectendx)
        startz = min(selectstartz, selectendz)
        endz = max(selectstartz, selectendz)

        editor.selectionqueue.queue_selection(
            int(startx),
            int(endz),
            int(endx - startx) + 1,
            int(endz - startz) + 1,
            editor.shift_is_pressed,
            editor.ctrl_is_pressed,
        )

        editor.do_redraw(force=True)

        editor.selectionbox_start = editor.selectionbox_end = None
        editor.do_redraw()


class Gizmo2DMoveX(ClickDragAction):
    def just_clicked(self, editor, buttons, event):
        super().just_clicked(editor, buttons, event)

        # Generally, selection tasks should be scheduled with the click release event, however, for
        # the gizmo, we want the first press event to already make the gizmo handle interactive.
        # Therefore, the event is scheduled on the press event (instead of in the natural release
        # event).
        editor.selectionqueue.queue_selection(
            event.x(),
            event.y(),
            1,
            1,
            editor.shift_is_pressed,
            editor.ctrl_is_pressed,
            do_gizmo=True,
        )
        editor.do_redraw(force=True)

    def move(self, editor, buttons, event):
        if editor.gizmo.was_hit["gizmo_x"]:
            editor.gizmo.set_render_axis(AXIS_X)
            delta_x = event.x() - self.first_click.x()
            self.first_click = event.position().toPoint()
            editor.move_points.emit(delta_x*editor.zoom_factor, 0, 0)

    def just_released(self, editor, buttons, event):
        super().just_released(editor, buttons, event)
        editor.gizmo.reset_axis()
        editor.gizmo.move_to_average(editor.selected_positions, editor.selected_rotations)


class Gizmo2DMoveXZ(Gizmo2DMoveX):
    def move(self, editor, buttons, event):
        if editor.gizmo.was_hit["middle"]:
            if editor.snapping_enabled and editor.collision is not None:
                radius = 2 * editor.zoom_factor
                coords = editor.get_closest_snapping_point(event.x(),
                                                           event.y(),
                                                           is3d=False,
                                                           radius=radius)
                if coords is not None:
                    editor.move_points_to.emit(
                        coords.x,
                        coords.y,
                        coords.z + editor.editor.snapping_height_offset,
                    )
                return

            #editor.gizmo.set_render_axis(AXIS_X)
            delta_x = event.x() - self.first_click.x()
            delta_z = event.y() - self.first_click.y()
            self.first_click = event.position().toPoint()
            editor.move_points.emit(delta_x*editor.zoom_factor, 0, delta_z*editor.zoom_factor)


class Gizmo2DMoveZ(Gizmo2DMoveX):
    def move(self, editor, buttons, event):
        if editor.gizmo.was_hit["gizmo_z"]:
            editor.gizmo.set_render_axis(AXIS_Z)
            delta_z = event.y() - self.first_click.y()
            self.first_click = event.position().toPoint()
            editor.move_points.emit(0, 0, delta_z*editor.zoom_factor)


class Gizmo2DRotateY(Gizmo2DMoveX):
    def just_clicked(self, editor, buttons, event):
        super().just_clicked(editor, buttons, event)

    def move(self, editor, buttons, event):
        if editor.gizmo.was_hit["rotation_y"]:
            #editor.gizmo.set_render_axis(AXIS_Z)

            x, y = editor.mouse_coord_to_world_coord(self.first_click.x(), self.first_click.y())
            angle_start = atan2(-(y + editor.gizmo.position.z), x - editor.gizmo.position.x)

            x, y = editor.mouse_coord_to_world_coord(event.x(), event.y())
            angle = atan2(-(y + editor.gizmo.position.z), x - editor.gizmo.position.x)
            delta = angle_start - angle


            editor.rotate_current.emit(Vector3(0, delta, 0))

            self.first_click = event.position().toPoint()

    def just_released(self, editor, buttons, event):
        super().just_released(editor, buttons, event)
        editor.gizmo.reset_axis()


class AddObjectTopDown(ClickAction):
    def condition(self, editor, buttons, event):
        return editor.mousemode == MOUSE_MODE_INSERTION

    def just_clicked(self, editor, buttons, event):
        mouse_x, mouse_z = (event.x(), event.y())
        destx, destz = editor.mouse_coord_to_world_coord(mouse_x, mouse_z)

        editor.create_waypoint.emit(destx, -destz)


class View3DScroll(ClickDragAction):
    def move(self, editor, buttons, event):
        d_x, d_y = event.x() - self.first_click.x(), event.y() - self.first_click.y()

        speedup = 1
        if editor.shift_is_pressed:
            speedup = editor._wasdscrolling_speedupfactor

        speed = editor._wasdscrolling_speed * (min(100000.0, editor.camera_height) / 1000000.0)

        forward_vec = Vector3(cos(editor.camera_horiz), sin(editor.camera_horiz), 0)
        forward_move = forward_vec * speed * speedup
        editor.camera_x += forward_move.x * d_y
        editor.camera_z += forward_move.y * d_y

        sideways_vec = Vector3(-sin(editor.camera_horiz), cos(editor.camera_horiz), 0)
        sideways_move = sideways_vec * speed * speedup
        editor.camera_x += sideways_move.x * d_x
        editor.camera_z += sideways_move.y * d_x

        editor.do_redraw()
        self.first_click = event.position().toPoint()


class RotateCamera3D(ClickDragAction):
    def condition(self, editor, buttons, event):
        return not buttons.is_held(event, "Left") #and editor.mousemode == MOUSE_MODE_NONE)

    def move(self, editor, buttons, event):
        curr_x, curr_y = event.x(), event.y()
        last_x, last_y = self.first_click.x(), self.first_click.y()

        diff_x = curr_x - last_x
        diff_y = curr_y - last_y

        self.first_click = QtCore.QPoint(curr_x, curr_y)

        editor.camera_horiz = (editor.camera_horiz - diff_x * (pi / 500)) % (2 * pi)
        editor.camera_vertical = (editor.camera_vertical - diff_y * (pi / 600))
        if editor.camera_vertical > pi / 2.0:
            editor.camera_vertical = pi / 2.0
        elif editor.camera_vertical < -pi / 2.0:
            editor.camera_vertical = -pi / 2.0

        # print(self.camera_vertical, "hello")
        editor.do_redraw()


ufac = 500


class Select3D(ClickDragAction):
    def condition(self, editor, buttons, event):
        if False and not (editor.mousemode == MOUSE_MODE_NONE and not buttons.is_held(event, "Right") and not editor.gizmo.was_hit_at_all):
            print("Wanted to do a select but", editor.mousemode == MOUSE_MODE_NONE,
                  not buttons.is_held(event, "Right"),
                  not editor.gizmo.was_hit_at_all
                  )
        return editor.mousemode == MOUSE_MODE_NONE and not buttons.is_held(event, "Right") and not editor.gizmo.was_hit_at_all

    def just_clicked(self, editor, buttons, event):
        super().just_clicked(editor, buttons, event)

        ray = editor.create_ray_from_mouseclick(event.x(), event.y())
        editor.selectionbox_projected_origin = ray.origin + ray.direction*ufac# * 0.1
        editor.selectionbox_projected_coords = None

    def move(self, editor, buttons, event):
        upleft = editor.create_ray_from_mouseclick(self.first_click.x(), event.y())
        upright = editor.create_ray_from_mouseclick(event.x(), event.y())
        downright = editor.create_ray_from_mouseclick(event.x(), self.first_click.y())

        editor.selectionbox_projected_coords = (
            upleft.origin + upleft.direction*ufac,# * 0.1,
            upright.origin + upright.direction*ufac,# * 0.1,
            downright.origin + downright.direction*ufac# * 0.1
        )

        #selectendx, selectendz = editor.mouse_coord_to_world_coord(event.x(), event.y())
        #editor.selectionbox_end = (selectendx, selectendz)
        editor.do_redraw()

    def just_released(self, editor, buttons, event):
        selectstartx, selectstartz = self.first_click.x(), self.first_click.y()
        selectendx, selectendz = event.x(), event.y()

        startx = min(selectstartx, selectendx)
        endx = max(selectstartx, selectendx)
        startz = min(selectstartz, selectendz)
        endz = max(selectstartz, selectendz)

        editor.selectionqueue.queue_selection(
            int(startx),
            int(endz),
            int(endx - startx) + 1,
            int(endz - startz) + 1,
            editor.shift_is_pressed,
            editor.ctrl_is_pressed,
        )

        editor.do_redraw(force=True)

        editor.selectionbox_projected_origin = None
        editor.selectionbox_projected_coords = None
        editor.do_redraw()


class AddObject3D(ClickAction):
    def condition(self, editor, buttons, event):
        return editor.mousemode == MOUSE_MODE_INSERTION

    def just_clicked(self, editor, buttons, event):
        #print("added object in 3d")
        ray = editor.create_ray_from_mouseclick(event.x(), event.y())
        place_at = None

        if editor.collision is not None:
            place_at = editor.collision.collide_ray(ray)

        if place_at is None:
            #print("colliding with plane")
            plane = Plane.xy_aligned(Vector3(0.0, 0.0, 0.0))

            collision = ray.collide_plane(plane)
            if collision is not None:
                place_at = collision


        if place_at is not None:
            #print("placed at", place_at)
            editor.create_waypoint_3d.emit(place_at.x, place_at.z, -place_at.y)
        #else:
        #    print("nothing collided, aw")


vec = numpy.array([1, 0, 0, 0])


class Gizmo3DMoveX(Gizmo2DMoveX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.axis_name = "gizmo_x"
        self.axis = AXIS_X
        self.dir = numpy.array([1, 0, 0, 0])

    def do_delta(self, delta):
        return delta, 0, 0

    def move(self, editor, buttons, event):
        if editor.gizmo.was_hit[self.axis_name]:
            editor.gizmo.set_render_axis(self.axis)

            proj = numpy.dot(editor.modelviewmatrix, self.dir)
            proj[2] = proj[3] = 0.0
            proj = proj/numpy.linalg.norm(proj)
            delta = numpy.array([
                event.x() - self.first_click.x(),
                event.y() - self.first_click.y(),
                0.0,
                0.0,
            ])
            delta[1] = -delta[1]
            self.first_click = event.position().toPoint()
            delta_x = numpy.dot(delta, proj)

            if editor.shift_is_pressed:
                editor.move_points.emit(*self.do_delta(delta_x))

            else:
                fac = 1/3.0
                editor.move_points.emit(*self.do_delta(delta_x * editor.gizmo_scale * fac))


class Gizmo3DMoveY(Gizmo3DMoveX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.axis_name = "gizmo_y"
        self.axis = AXIS_Y
        self.dir = numpy.array([0, 0, 1, 0])

    def do_delta(self, delta):
        return 0, delta, 0


class Gizmo3DMoveZ(Gizmo3DMoveX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.axis_name = "gizmo_z"
        self.axis = AXIS_Z
        self.dir = numpy.array([0, -1, 0, 0])

    def do_delta(self, delta):
        return 0, 0, delta


class Gizmo3DMove(Gizmo3DMoveX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.axis_name = "middle"

    def move(self, editor, buttons, event):
        if editor.gizmo.was_hit["middle"]:
            if editor.snapping_enabled and editor.collision is not None:
                radius = 25
                coords = editor.get_closest_snapping_point(event.x(), event.y(), radius=radius)
                coords = Vector3(
                    coords.x,
                    coords.y,
                    coords.z + editor.editor.snapping_height_offset,
                )
            else:
                coords = editor.get_3d_coordinates(event.x(), event.y())

            if coords is not None:
                editor.move_points_to.emit(coords.x, coords.y, coords.z)


class Gizmo3DMoveXY(Gizmo2DMoveX):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.plane = None
        self.previous_coords = None

        self.handle_name = "plane_xy"
        self.axes = AXIS_X | AXIS_Y
        self.plane_constructor = Plane.xz_aligned
        self.mask = (1, 1, 0)  # Ensures rounding errors don't cause change in the fixed component.

    def just_clicked(self, editor, buttons, event):
        super().just_clicked(editor, buttons, event)

        gizmo_position = Vector3(
            editor.gizmo.position.x,
            -editor.gizmo.position.z,
            editor.gizmo.position.y,
        )
        self.plane = self.plane_constructor(gizmo_position)
        self.previous_coords = editor.get_3d_coordinates(event.x(), event.y(), self.plane)

    def move(self, editor, buttons, event):
        if not editor.gizmo.was_hit[self.handle_name]:
            return

        if self.previous_coords is None:
            return

        coords = editor.get_3d_coordinates(event.x(), event.y(), self.plane)
        if coords is not None:
            delta_coords = coords - self.previous_coords
            editor.move_points.emit(
                self.mask[0] * delta_coords.x,
                self.mask[1] * delta_coords.z,
                self.mask[2] * -delta_coords.y,
            )
            self.previous_coords = coords

        editor.gizmo.set_render_axis(self.axes)


class Gizmo3DMoveXZ(Gizmo3DMoveXY):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.handle_name = "plane_xz"
        self.axes = AXIS_X | AXIS_Z
        self.plane_constructor = Plane.xy_aligned
        self.mask = (1, 0, 1)


class Gizmo3DMoveYZ(Gizmo3DMoveXY):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.handle_name = "plane_yz"
        self.axes = AXIS_Y | AXIS_Z
        self.plane_constructor = Plane.yz_aligned
        self.mask = (0, 1, 1)


class Gizmo3DRotateY(Gizmo2DRotateY):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.angle_start = None
        self.axis_name = "rotation_y"

    def do_delta(self, delta):
        return 0, delta, 0

    def flip_rot(self, dir):
        vec = numpy.array([0, 0, 1])
        dirvec = numpy.array([dir.x, dir.y, dir.z])

        d = numpy.dot(vec, dirvec)

        if d >= 0:
            return -1
        else:
            return 1

    def move(self, editor, buttons, event):
        if editor.gizmo.was_hit[self.axis_name]:
            proj = numpy.dot(editor.mvp_mat, numpy.array([
                editor.gizmo.position.x,
                -editor.gizmo.position.z,
                editor.gizmo.position.y,
                1]
            ))

            # Dehogomization
            if proj[3] != 0.0:
                proj[0] = proj[0] / proj[3]
                proj[1] = proj[1] / proj[3]
                proj[2] = proj[2] / proj[3]

            # Transform to editor coords
            w = editor.canvas_width/2.0
            h = editor.canvas_height/2.0
            point_x = proj[0] * w + w
            point_y = -proj[1] * h + h

            x, y = event.x() - point_x, event.y() - point_y
            angle = atan2(y, x)
            if self.angle_start is not None:
                delta = self.angle_start - angle
                delta *= self.flip_rot(editor.camera_direction)

                # Sometimes on the first click the delta is too high resulting in
                # a big rotation. We will limit it this way
                if abs(delta) <= 0.3:
                    editor.rotate_current.emit(Vector3(*self.do_delta(delta)))
            self.angle_start = angle


class Gizmo3DRotateX(Gizmo3DRotateY):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.axis_name = "rotation_x"

    def flip_rot(self, dir):
        vec = numpy.array([1, 0, 0])
        dirvec = numpy.array([dir.x, dir.y, dir.z])

        d = numpy.dot(vec, dirvec)

        if d >= 0:
            return -1
        else:
            return 1

    def do_delta(self, delta):
        return delta, 0, 0


class Gizmo3DRotateZ(Gizmo3DRotateY):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.axis_name = "rotation_z"

    def flip_rot(self, dir):
        vec = numpy.array([0, -1, 0])
        dirvec = numpy.array([dir.x, dir.y, dir.z])

        d = numpy.dot(vec, dirvec)

        if d >= 0:
            return -1
        else:
            return 1

    def do_delta(self, delta):
        return 0, 0, delta


class UserControl(object):
    def __init__(self, editor_widget):
        self._editor_widget = editor_widget

        self.shift_pressed = False

        self.buttons = Buttons()

        self.clickdragactions = {"Left": [], "Right": [], "Middle": []}
        self.clickdragactions3d = {"Left": [], "Right": [], "Middle": []}

        self.add_action(TopdownScroll("2DScroll", "Middle"))
        self.add_action(TopdownSelect("2DSelect", "Left"))
        self.add_action(Gizmo2DMoveX("Gizmo2DMoveX", "Left"))
        self.add_action(Gizmo2DMoveZ("Gizmo2DMoveZ", "Left"))
        self.add_action(Gizmo2DMoveXZ("Gizmo2DMoveXZ", "Left"))
        self.add_action(Gizmo2DRotateY("Gizmo2DRotateY", "Left"))
        self.add_action(AddObjectTopDown("AddObject2D", "Left"))

        self.add_action3d(View3DScroll("3DScroll", "Middle"))
        self.add_action3d(RotateCamera3D("RotateCamera", "Right"))
        self.add_action3d(AddObject3D("AddObject3D", "Left"))
        self.add_action3d(Gizmo3DMoveX("Gizmo3DMoveX", "Left"))
        self.add_action3d(Gizmo3DMoveY("Gizmo3DMoveY", "Left"))
        self.add_action3d(Gizmo3DMoveZ("Gizmo3DMoveZ", "Left"))
        self.add_action3d(Gizmo3DMove("Gizmo3DMove", "Left"))
        self.add_action3d(Gizmo3DRotateX("Gizmo3DRotateX", "Left"))
        self.add_action3d(Gizmo3DRotateY("Gizmo3DRotateY", "Left"))
        self.add_action3d(Gizmo3DRotateZ("Gizmo3DRotateZ", "Left"))
        self.add_action3d(Gizmo3DMoveXY("Gizmo3DMoveXY", "Left"))
        self.add_action3d(Gizmo3DMoveXZ("Gizmo3DMoveXZ", "Left"))
        self.add_action3d(Gizmo3DMoveYZ("Gizmo3DMoveYZ", "Left"))
        self.add_action3d(Select3D("Select3D", "Left"))

    def add_action(self, action):
        self.clickdragactions[action.key].append(action)

    def add_action3d(self, action):
        self.clickdragactions3d[action.key].append(action)

    def handle_press(self, event):
        editor = self._editor_widget

        if editor.mode == MODE_TOPDOWN:
            self.handle_press_topdown(event)
        else:
            self.handle_press_3d(event)

    def handle_release(self, event):
        editor = self._editor_widget
        if editor.mode == MODE_TOPDOWN:
            self.handle_release_topdown(event)
        else:
            self.handle_release_3d(event)

        editor.gizmo.reset_hit_status()
        #print("Gizmo hit status was reset!!!!", editor.gizmo.was_hit_at_all)
        editor.do_redraw()

        x = event.x()
        y = event.y()
        QtCore.QTimer.singleShot(0, lambda: self._update_editor_position(x, y))

    def handle_move(self, event):
        editor = self._editor_widget
        if editor.mode == MODE_TOPDOWN:
            self.handle_move_topdown(event)
        else:
            self.handle_move_3d(event)

        self._update_editor_position(event.x(), event.y())

    def handle_press_topdown(self, event):
        editor = self._editor_widget

        for key in key_enums.keys():
            if self.buttons.just_pressed(event, key):
                for action in self.clickdragactions[key]:
                    if action.condition(editor, self.buttons, event):
                        action.just_clicked(editor, self.buttons, event)

    def handle_release_topdown(self, event):
        editor = self._editor_widget

        for key in key_enums.keys():
            if self.buttons.just_released(event, key):
                for action in self.clickdragactions[key]:
                    if action.condition(editor, self.buttons, event):
                        action.just_released(editor, self.buttons, event)

    def handle_move_topdown(self, event):
        editor = self._editor_widget

        for key in key_enums.keys():
            if self.buttons.is_held(event, key):
                for action in self.clickdragactions[key]:
                    if action.condition(editor, self.buttons, event):
                        action.move(editor, self.buttons, event)
        return

    def handle_press_3d(self, event):
        editor = self._editor_widget

        for key in key_enums.keys():
            if self.buttons.just_pressed(event, key):
                for action in self.clickdragactions3d[key]:
                    if action.condition(editor, self.buttons, event):
                        action.just_clicked(editor, self.buttons, event)

    def handle_release_3d(self, event):
        editor = self._editor_widget

        for key in key_enums.keys():
            if self.buttons.just_released(event, key):
                for action in self.clickdragactions3d[key]:
                    if action.condition(editor, self.buttons, event):
                        action.just_released(editor, self.buttons, event)

    def handle_move_3d(self, event):
        editor = self._editor_widget

        for key in key_enums.keys():
            if self.buttons.is_held(event, key):
                for action in self.clickdragactions3d[key]:
                    if action.condition(editor, self.buttons, event):
                        action.move(editor, self.buttons, event)

    def _update_editor_position(self, x, y):
        editor = self._editor_widget

        if editor.mode == MODE_TOPDOWN:
            mapx, mapz = editor.mouse_coord_to_world_coord(x, y)

            if editor.collision is not None:
                height = editor.collision.collide_ray_downwards(mapx, -mapz, editor.editorconfig.getint("topdown_cull_height")-10)

                if height is not None:
                    editor.position_update.emit((round(mapx, 2), round(height, 2), round(-mapz, 2)))
                else:
                    editor.position_update.emit((round(mapx, 2), None, round(-mapz, 2)))
            else:
                editor.position_update.emit((round(mapx, 2), None, round(-mapz, 2)))
        else:
            place_at = editor.get_3d_coordinates(x, y)
            if place_at is not None:
                editor.position_update.emit((round(place_at.x, 2), round(place_at.z,
                                                                         2), round(-place_at.y, 2)))
