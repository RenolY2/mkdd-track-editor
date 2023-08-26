import enum
import random
import traceback
import os
from time import sleep
from timeit import default_timer
from collections import namedtuple
from math import sin, cos, atan2, radians, degrees, pi, tan
import json

from OpenGL.GL import *
from OpenGL.GLU import *

from PySide6 import QtCore, QtGui, QtOpenGLWidgets, QtWidgets

from helper_functions import calc_zoom_in_factor, calc_zoom_out_factor
from lib.collision import Collision
from widgets.editor_widgets import catch_exception, catch_exception_with_dialog, check_checkpoints
from opengltext import draw_collision
from lib.vectors import Vector3, Line, Plane, Triangle
from lib.model_rendering import TexturedPlane, Model, Grid, GenericObject, Material, Minimap
from gizmo import Gizmo
from lib.object_models import ObjectModels
from editor_controls import UserControl
from lib.libbol import BOL
import numpy

ObjectSelectionEntry = namedtuple("ObjectSelectionEntry", ["obj", "pos1", "pos2", "pos3", "rotation"])

MOUSE_MODE_NONE = 0
MOUSE_MODE_MOVEWP = 1
MOUSE_MODE_ADDWP = 2
MOUSE_MODE_CONNECTWP = 3

MODE_TOPDOWN = 0
MODE_3D = 1

#colors = [(1.0, 0.0, 0.0), (0.0, 0.5, 0.0), (0.0, 0.0, 1.0), (1.0, 1.0, 0.0)]
colors = [(0.0,191/255.0,255/255.0), (30/255.0,144/255.0,255/255.0), (0.0,0.0,255/255.0), (0.0,0.0,139/255.0)]

with open("lib/color_coding.json", "r") as f:
    colors_json = json.load(f)
    colors_selection = colors_json["SelectionColor"]
    colors_area  = colors_json["Areas"]


class SelectionQueue(list):

    def queue_selection(self, x, y, width, height, shift_pressed, do_gizmo=False):
        if do_gizmo:
            if any(entry[-1] for entry in self):
                return
        self.append((x, y, width, height, shift_pressed, do_gizmo))


class SnappingMode(enum.Enum):
    VERTICES = 'Vertices'
    EDGE_CENTERS = 'Edge Centers'
    FACE_CENTERS = 'Face Centers'


class BolMapViewer(QtOpenGLWidgets.QOpenGLWidget):
    mouse_clicked = QtCore.Signal(QtGui.QMouseEvent)
    entity_clicked = QtCore.Signal(QtGui.QMouseEvent, str)
    mouse_dragged = QtCore.Signal(QtGui.QMouseEvent)
    mouse_released = QtCore.Signal(QtGui.QMouseEvent)
    mouse_wheel = QtCore.Signal(QtGui.QWheelEvent)
    position_update = QtCore.Signal(tuple)
    move_points = QtCore.Signal(float, float, float)
    move_points_to = QtCore.Signal(float, float, float)
    connect_update = QtCore.Signal(int, int)
    create_waypoint = QtCore.Signal(float, float)
    create_waypoint_3d = QtCore.Signal(float, float, float)

    rotate_current = QtCore.Signal(Vector3)

    def __init__(self, samples, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.editor = None

        # Enable multisampling by setting the number of configured samples in the surface format.
        self.samples = samples
        if self.samples > 1:
            surface_format = self.format()
            surface_format.setSamples(samples)
            self.setFormat(surface_format)

        # Secondary framebuffer (and its associated mono-sampled texture) that is used when
        # multisampling is enabled.
        self.pick_framebuffer = None
        self.pick_texture = None
        self.pick_depth_texture = None

        self._zoom_factor = 80
        self.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.SIZEX = 1024#768#1024
        self.SIZEY = 1024#768#1024

        self.canvas_width, self.canvas_height = self.width(), self.height()
        self.resize(600, self.canvas_height)
        #self.setMinimumSize(QtCore.QSize(self.SIZEX, self.SIZEY))
        #self.setMaximumSize(QtCore.QSize(self.SIZEX, self.SIZEY))
        self.setObjectName("bw_map_screen")

        self.origin_x = self.SIZEX//2
        self.origin_z = self.SIZEY//2

        self.offset_x = 0
        self.offset_z = 0

        self.left_button_down = False
        self.mid_button_down = False
        self.right_button_down = False
        self.drag_last_pos = None

        self.selected = []
        self.selected_positions = []
        self.selected_rotations = []

        #self.p = QPainter()
        #self.p2 = QPainter()
        # self.show_terrain_mode = SHOW_TERRAIN_REGULAR

        self.selectionbox_start = None
        self.selectionbox_end = None

        self.visualize_cursor = None

        self.click_mode = 0

        self.level_image = None

        self.collision = None

        self.highlighttriangle = None

        self.setMouseTracking(True)

        self.level_file:BOL = None
        self.waterboxes = []

        self.mousemode = MOUSE_MODE_NONE

        self.overlapping_wp_index = 0
        self.editorconfig = None
        self.visibility_menu = None

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        self.spawnpoint = None
        self.alternative_mesh = None
        self.highlight_colltype = None
        self.cull_faces = False

        self.shift_is_pressed = False
        self.rotation_is_pressed = False
        self.last_drag_update = 0
        self.change_height_is_pressed = False
        self.last_mouse_move = None

        self.timer = QtCore.QTimer()
        self.timer.setInterval(2)
        self.timer.timeout.connect(self.render_loop)
        self.timer.start()
        self._lastrendertime = 0
        self._lasttime = 0

        self._frame_invalid = False
        self._mouse_pos_changed = False

        self.MOVE_UP = 0
        self.MOVE_DOWN = 0
        self.MOVE_LEFT = 0
        self.MOVE_RIGHT = 0
        self.MOVE_FORWARD = 0
        self.MOVE_BACKWARD = 0
        self.SPEEDUP = 0

        self._wasdscrolling_speed = 1
        self._wasdscrolling_speedupfactor = 3

        self.main_model = None
        self.buffered_deltas = []

        # 3D Setup
        self.mode = MODE_TOPDOWN
        self.camera_horiz = pi*(1/2)
        self.camera_vertical = -pi*(1/4)
        self.camera_height = 1000
        self.last_move = None
        self.backgroundcolor = (255, 255, 255, 255)

        look_direction = Vector3(cos(self.camera_horiz), sin(self.camera_horiz),
                                 sin(self.camera_vertical))
        fac = 1.01 - abs(look_direction.z)
        self.camera_direction = Vector3(look_direction.x * fac, look_direction.y * fac,
                                        look_direction.z)

        #self.selection_queue = []
        self.selectionqueue = SelectionQueue()

        self.selectionbox_projected_start = None
        self.selectionbox_projected_end = None

        #self.selectionbox_projected_2d = None
        self.selectionbox_projected_origin = None
        self.selectionbox_projected_up = None
        self.selectionbox_projected_right = None
        self.selectionbox_projected_coords = None
        self.move_collision_plane = Plane(Vector3(0.0, 0.0, 0.0), Vector3(1.0, 0.0, 0.0), Vector3(0.0, 1.0, 0.0))

        self.usercontrol = UserControl(self)

        self.snapping_enabled = False
        self.snapping_mode = SnappingMode.VERTICES
        self.snapping_last_hash = None
        self.snapping_display_list = None

        # Initialize some models
        with open("resources/gizmo.obj", "r") as f:
            self.gizmo = Gizmo.from_obj(f, rotate=True)

        #self.generic_object = GenericObject()
        self.models = ObjectModels()
        self.grid = Grid(100000, 100000, 10000)

        self.modelviewmatrix = None
        self.projectionmatrix = None

        self.minimap = Minimap(Vector3(-1000.0, 0.0, -1000.0), Vector3(1000.0, 0.0, 1000.0), 0,
                               None)

    @catch_exception_with_dialog
    def initializeGL(self):
        self.rotation_visualizer = glGenLists(1)
        glNewList(self.rotation_visualizer, GL_COMPILE)
        glColor4f(0.0, 0.0, 1.0, 1.0)

        glBegin(GL_LINES)
        glVertex3f(0.0, 0.0, 0.0)
        glVertex3f(0.0, 40.0, 0.0)
        glEnd()
        glEndList()

        self.models.init_gl()

        # If multisampling is enabled, a secondary mono-sampled framebuffer needs to be created, as
        # reading pixels from multisampled framebuffers is not a supported GL operation.
        if self.samples > 1:
            self.pick_framebuffer = glGenFramebuffers(1)
            self.pick_texture = glGenTextures(1)
            self.pick_depth_texture = glGenTextures(1)
            glBindFramebuffer(GL_FRAMEBUFFER, self.pick_framebuffer)
            glBindTexture(GL_TEXTURE_2D, self.pick_texture)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, self.canvas_width, self.canvas_height, 0,
                         GL_RGBA, GL_UNSIGNED_BYTE, None)
            glBindTexture(GL_TEXTURE_2D, 0)
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D,
                                   self.pick_texture, 0)
            glBindTexture(GL_TEXTURE_2D, self.pick_depth_texture)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT, self.canvas_width,
                         self.canvas_height, 0, GL_DEPTH_COMPONENT, GL_FLOAT, None)
            glBindTexture(GL_TEXTURE_2D, 0)
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D,
                                   self.pick_depth_texture, 0)
            glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def resizeGL(self, width, height):
        # Called upon window resizing: reinitialize the viewport.
        # update the window size
        self.canvas_width, self.canvas_height = width, height
        # paint within the whole window
        glEnable(GL_DEPTH_TEST)
        glViewport(0, 0, self.canvas_width, self.canvas_height)

        # The mono-sampled texture for the secondary framebuffer needs to be resized as well.
        if self.pick_texture is not None:
            glBindTexture(GL_TEXTURE_2D, self.pick_texture)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE,
                         None)
            glBindTexture(GL_TEXTURE_2D, 0)
        if self.pick_depth_texture is not None:
            glBindTexture(GL_TEXTURE_2D, self.pick_depth_texture)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT, width, height, 0, GL_DEPTH_COMPONENT,
                         GL_FLOAT, None)
            glBindTexture(GL_TEXTURE_2D, 0)

    @catch_exception
    def set_editorconfig(self, config):
        self.editorconfig = config
        self._wasdscrolling_speed = config.getfloat("wasdscrolling_speed")
        self._wasdscrolling_speedupfactor = config.getfloat("wasdscrolling_speedupfactor")
        backgroundcolor = config["3d_background"].split(" ")
        self.backgroundcolor = (int(backgroundcolor[0])/255.0,
                                int(backgroundcolor[1])/255.0,
                                int(backgroundcolor[2])/255.0,
                                1.0)

    def change_from_topdown_to_3d(self):
        if self.mode == MODE_3D:
            return
        else:
            self.mode = MODE_3D

            if self.mousemode == MOUSE_MODE_NONE:
                self.setContextMenuPolicy(QtCore.Qt.DefaultContextMenu)

            # This is necessary so that the position of the 3d camera equals the middle of the topdown view
            self.offset_x *= -1
            self.do_redraw()

    def change_from_3d_to_topdown(self):
        if self.mode == MODE_TOPDOWN:
            return
        else:
            self.mode = MODE_TOPDOWN
            if self.mousemode == MOUSE_MODE_NONE:
                self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

            self.offset_x *= -1
            self.do_redraw()

    def logic(self, delta, diff):
        self.dolphin.logic(self, delta, diff)

    @catch_exception
    def render_loop(self):
        now = default_timer()

        diff = now-self._lastrendertime
        timedelta = now-self._lasttime

        if self.mode == MODE_TOPDOWN:
            self.handle_arrowkey_scroll(timedelta)
        else:
            self.handle_arrowkey_scroll_3d(timedelta)

        self.logic(timedelta, diff)

        if diff > 1 / 60.0:
            check_gizmo_hover_id = self._mouse_pos_changed and self.should_check_gizmo_hover_id()
            self._mouse_pos_changed = False

            if self._frame_invalid or check_gizmo_hover_id:
                self.update()
                self._lastrendertime = now
                self._frame_invalid = False
        self._lasttime = now

    def should_check_gizmo_hover_id(self):
        if self.gizmo.hidden or self.gizmo.was_hit_at_all:
            return False

        return (not QtWidgets.QApplication.mouseButtons()
                and not QtWidgets.QApplication.keyboardModifiers())

    def toggle_snapping(self):
        self.snapping_enabled = not self.snapping_enabled
        self.do_redraw()

    def cycle_snapping_mode(self):
        self.snapping_enabled = True
        mode_names = [mode.name for mode in SnappingMode]
        index = mode_names.index(self.snapping_mode.name)
        next_index = (index + 1) % len(SnappingMode)
        self.snapping_mode = SnappingMode[mode_names[next_index]]
        self.do_redraw()

    def set_snapping_mode(self, snapping_mode):
        if isinstance(snapping_mode, SnappingMode):
            self.snapping_mode = snapping_mode
            self.snapping_enabled = True
        elif snapping_mode in [mode.name for mode in SnappingMode]:
            self.snapping_mode = SnappingMode[snapping_mode]
            self.snapping_enabled = True
        elif snapping_mode in [mode.value for mode in SnappingMode]:
            for mode in SnappingMode:
                if mode.value == snapping_mode:
                    self.snapping_mode = mode
                    break
            self.snapping_enabled = True
        else:
            self.snapping_enabled = False
        self.do_redraw()

    def _get_snapping_points(self):
        if self.snapping_mode == SnappingMode.EDGE_CENTERS:
            return self.collision.edge_centers
        if self.snapping_mode == SnappingMode.FACE_CENTERS:
            return self.collision.face_centers
        return self.collision.vertices

    def handle_arrowkey_scroll(self, timedelta):
        if self.selectionbox_projected_coords is not None:
            return

        diff_x = diff_y = 0
        #print(self.MOVE_UP, self.MOVE_DOWN, self.MOVE_LEFT, self.MOVE_RIGHT)
        speedup = 1

        if self.shift_is_pressed:
            speedup = self._wasdscrolling_speedupfactor

        if self.MOVE_FORWARD == 1 and self.MOVE_BACKWARD == 1:
            diff_y = 0
        elif self.MOVE_FORWARD == 1:
            diff_y = 1*speedup*self._wasdscrolling_speed*timedelta
        elif self.MOVE_BACKWARD == 1:
            diff_y = -1*speedup*self._wasdscrolling_speed*timedelta

        if self.MOVE_LEFT == 1 and self.MOVE_RIGHT == 1:
            diff_x = 0
        elif self.MOVE_LEFT == 1:
            diff_x = 1*speedup*self._wasdscrolling_speed*timedelta
        elif self.MOVE_RIGHT == 1:
            diff_x = -1*speedup*self._wasdscrolling_speed*timedelta

        if diff_x != 0 or diff_y != 0:
            if self.zoom_factor > 1.0:
                self.offset_x += diff_x * (1.0 + (self.zoom_factor - 1.0) / 2.0)
                self.offset_z += diff_y * (1.0 + (self.zoom_factor - 1.0) / 2.0)
            else:
                self.offset_x += diff_x
                self.offset_z += diff_y
            # self.update()

            self.do_redraw()

    def handle_arrowkey_scroll_3d(self, timedelta):
        if self.selectionbox_projected_coords is not None:
            return

        diff_x = diff_y = diff_height = 0
        #print(self.MOVE_UP, self.MOVE_DOWN, self.MOVE_LEFT, self.MOVE_RIGHT)
        speedup = 1

        forward_vec = Vector3(cos(self.camera_horiz), sin(self.camera_horiz), 0)
        sideways_vec = Vector3(sin(self.camera_horiz), -cos(self.camera_horiz), 0)

        if self.shift_is_pressed:
            speedup = self._wasdscrolling_speedupfactor

        if self.MOVE_FORWARD == 1 and self.MOVE_BACKWARD == 1:
            forward_move = forward_vec*0
        elif self.MOVE_FORWARD == 1:
            forward_move = forward_vec*(1*speedup*self._wasdscrolling_speed*timedelta)
        elif self.MOVE_BACKWARD == 1:
            forward_move = forward_vec*(-1*speedup*self._wasdscrolling_speed*timedelta)
        else:
            forward_move = forward_vec*0

        if self.MOVE_LEFT == 1 and self.MOVE_RIGHT == 1:
            sideways_move = sideways_vec*0
        elif self.MOVE_LEFT == 1:
            sideways_move = sideways_vec*(-1*speedup*self._wasdscrolling_speed*timedelta)
        elif self.MOVE_RIGHT == 1:
            sideways_move = sideways_vec*(1*speedup*self._wasdscrolling_speed*timedelta)
        else:
            sideways_move = sideways_vec*0

        if self.MOVE_UP == 1 and self.MOVE_DOWN == 1:
            diff_height = 0
        elif self.MOVE_UP == 1:
            diff_height = 1*speedup*self._wasdscrolling_speed*timedelta
        elif self.MOVE_DOWN == 1:
            diff_height = -1 * speedup * self._wasdscrolling_speed * timedelta

        if not forward_move.is_zero() or not sideways_move.is_zero() or diff_height != 0:
            #if self.zoom_factor > 1.0:
            #    self.offset_x += diff_x * (1.0 + (self.zoom_factor - 1.0) / 2.0)
            #    self.offset_z += diff_y * (1.0 + (self.zoom_factor - 1.0) / 2.0)
            #else:
            self.offset_x += (forward_move.x + sideways_move.x)
            self.offset_z += (forward_move.y + sideways_move.y)
            self.camera_height += diff_height
            # self.update()

            self.do_redraw()

    def set_arrowkey_movement(self, up, down, left, right):
        self.MOVE_UP = up
        self.MOVE_DOWN = down
        self.MOVE_LEFT = left
        self.MOVE_RIGHT = right

    def do_redraw(self, force=False):
        self._frame_invalid = True
        if force:
            self._lastrendertime = 0
            self.update()

    def reset(self, keep_collision=False):
        self.highlight_colltype = None
        self.overlapping_wp_index = 0
        self.shift_is_pressed = False
        self.SIZEX = 1024
        self.SIZEY = 1024
        self.origin_x = self.SIZEX//2
        self.origin_z = self.SIZEY//2
        self.last_drag_update = 0

        self.left_button_down = False
        self.mid_button_down = False
        self.right_button_down = False
        self.drag_last_pos = None

        self.selectionbox_start = None
        self.selectionbox_end = None

        self.selected = []

        if not keep_collision:
            # Potentially: Clear collision object too?
            self.level_image = None
            self.offset_x = 0
            self.offset_z = 0
            self._zoom_factor = 80

        self.mousemode = MOUSE_MODE_NONE
        self.spawnpoint = None
        self.rotation_is_pressed = False

        self._frame_invalid = False
        self._mouse_pos_changed = False

        self.MOVE_UP = 0
        self.MOVE_DOWN = 0
        self.MOVE_LEFT = 0
        self.MOVE_RIGHT = 0
        self.SPEEDUP = 0

    def clear_collision(self):
        self.alternative_mesh = None
        self.collision = None

        if self.main_model is not None:
            glDeleteLists(self.main_model, 1)
            self.main_model = None

    def set_collision(self, verts, faces, alternative_mesh):
        self.collision = Collision(verts, faces)

        if self.main_model is None:
            self.main_model = glGenLists(1)

        self.alternative_mesh = alternative_mesh

        glNewList(self.main_model, GL_COMPILE)
        #glBegin(GL_TRIANGLES)
        draw_collision(verts, faces)
        #glEnd()
        glEndList()

    def set_mouse_mode(self, mode):
        assert mode in (MOUSE_MODE_NONE, MOUSE_MODE_ADDWP, MOUSE_MODE_CONNECTWP, MOUSE_MODE_MOVEWP)

        self.mousemode = mode

        if self.mousemode == MOUSE_MODE_NONE and self.mode == MODE_TOPDOWN:
            self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        else:
            self.setContextMenuPolicy(QtCore.Qt.DefaultContextMenu)

        cursor_shape = QtCore.Qt.ArrowCursor if mode == MOUSE_MODE_NONE else QtCore.Qt.CrossCursor
        self.setCursor(cursor_shape)

    @property
    def zoom_factor(self):
        return self._zoom_factor/10.0

    def zoom(self, fac):
        if self._zoom_factor <= 60:
            mult = 20.0
        elif self._zoom_factor >= 600:
            mult = 100.0
        else:
            mult = 40.0

        if 10 < (self._zoom_factor + fac*mult):
            self._zoom_factor += int(fac*mult)
            #self.update()
            self.do_redraw()

    def mouse_coord_to_world_coord(self, mouse_x, mouse_y):
        zf = self.zoom_factor
        width, height = self.canvas_width, self.canvas_height
        camera_width = width * zf
        camera_height = height * zf

        topleft_x = -camera_width / 2 - self.offset_x
        topleft_y = camera_height / 2 + self.offset_z

        relx = mouse_x / width
        rely = mouse_y / height
        res = (topleft_x + relx*camera_width, topleft_y - rely*camera_height)

        return res

    #@catch_exception_with_dialog
    #@catch_exception
    def paintGL(self):
        offset_x = self.offset_x
        offset_z = self.offset_z

        glClearColor(1.0, 1.0, 1.0, 0.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        width, height = self.canvas_width, self.canvas_height

        if self.mode == MODE_TOPDOWN:
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            zf = self.zoom_factor
            #glOrtho(-6000.0, 6000.0, -6000.0, 6000.0, -3000.0, 2000.0)
            camera_width = width*zf
            camera_height = height*zf

            glOrtho(-camera_width / 2 - offset_x, camera_width / 2 - offset_x,
                    -camera_height / 2 + offset_z, camera_height / 2 + offset_z, -120000.0, 80000.0)

            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()
        else:
            #glEnable(GL_CULL_FACE)
            # set yellow color for subsequent drawing rendering calls

            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(75, width / height, 256.0, 160000.0)

            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()

            look_direction = Vector3(cos(self.camera_horiz), sin(self.camera_horiz), sin(self.camera_vertical))
            # look_direction.unify()
            fac = 1.01 - abs(look_direction.z)
            # print(fac, look_direction.z, look_direction)

            gluLookAt(self.offset_x, self.offset_z, self.camera_height,
                      self.offset_x + look_direction.x * fac, self.offset_z + look_direction.y * fac,
                      self.camera_height + look_direction.z,
                      0, 0, 1)

            self.camera_direction = Vector3(look_direction.x * fac, look_direction.y * fac, look_direction.z)

            #print(self.camera_direction)

        self.modelviewmatrix = numpy.transpose(numpy.reshape(glGetFloatv(GL_MODELVIEW_MATRIX), (4,4)))
        self.projectionmatrix = numpy.transpose(numpy.reshape(glGetFloatv(GL_PROJECTION_MATRIX), (4,4)))
        self.mvp_mat = numpy.dot(self.projectionmatrix, self.modelviewmatrix)
        self.modelviewmatrix_inv = numpy.linalg.inv(self.modelviewmatrix)

        campos = Vector3(self.offset_x, self.camera_height, -self.offset_z)
        self.campos = campos

        if self.mode == MODE_TOPDOWN:
            gizmo_scale = 3*zf
        else:
            gizmo_scale = (self.gizmo.position - campos).norm() / 130.0


        self.gizmo_scale = gizmo_scale

        check_gizmo_hover_id = self.should_check_gizmo_hover_id()

        # If multisampling is enabled, the draw/read operations need to happen on the mono-sampled
        # framebuffer.
        use_pick_framebuffer = (self.selectionqueue or check_gizmo_hover_id) and self.samples > 1
        if use_pick_framebuffer:
            glBindFramebuffer(GL_FRAMEBUFFER, self.pick_framebuffer)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        gizmo_hover_id = 0xFF
        if not self.selectionqueue and check_gizmo_hover_id:
            self.gizmo.render_collision_check(gizmo_scale, is3d=self.mode == MODE_3D)
            mouse_pos = self.mapFromGlobal(QtGui.QCursor.pos())
            pixels = glReadPixels(mouse_pos.x(), self.canvas_height - mouse_pos.y(), 1, 1, GL_RGB, GL_UNSIGNED_BYTE)
            gizmo_hover_id = pixels[2]

        vismenu: FilterViewMenu = self.visibility_menu

        if self.selectionqueue:
            glClearColor(1.0, 1.0, 1.0, 1.0)
            glDisable(GL_TEXTURE_2D)

        while len(self.selectionqueue) > 0:
            click_x, click_y, clickwidth, clickheight, shiftpressed, do_gizmo = self.selectionqueue.pop()
            click_y = height - click_y

            # Clamp to viewport dimensions.
            if click_x < 0:
                clickwidth += click_x
                click_x = 0
            if click_y < 0:
                clickheight += click_y
                click_y = 0
            clickwidth = max(0, min(clickwidth, width - click_x))
            clickheight = max(0, min(clickheight, height - click_y))
            if not clickwidth or not clickheight:
                continue

            if do_gizmo and clickwidth == 1 and clickheight == 1:
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

                self.gizmo.render_collision_check(gizmo_scale, is3d=self.mode == MODE_3D)
                pixels = glReadPixels(click_x, click_y, clickwidth, clickheight, GL_RGB, GL_UNSIGNED_BYTE)

                hit = pixels[2]
                if hit != 0xFF:
                    self.gizmo.run_callback(hit)
                    self.gizmo.was_hit_at_all = True

                    # Clear the potential marquee selection, which may have been just created as a
                    # result of a mouse move event that was processed slightly earlier than this
                    # current paint event.
                    self.selectionbox_start = self.selectionbox_end = None
                    self.selectionbox_projected_origin = self.selectionbox_projected_coords = None

                    # If the gizmo was hit, it takes priority over the rest of the potential items
                    # in the queue.
                    self.selectionqueue.clear()
                    break

                continue

            selected = {}
            selected_positions = []
            selected_rotations = []

            continue_picking = not do_gizmo
            while continue_picking:
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

                id = 0x100000

                objlist = []
                offset = 0

                if (self.minimap is not None and vismenu.minimap.is_selectable()
                        and self.minimap.is_available() and self.minimap not in selected):
                    objlist.append(
                        ObjectSelectionEntry(obj=self.minimap,
                                             pos1=self.minimap.corner1,
                                             pos2=self.minimap.corner2,
                                             pos3=None,
                                             rotation=None)
                    )
                    self.models.render_generic_position_colored_id(self.minimap.corner1, id + (offset) * 4)
                    self.models.render_generic_position_colored_id(self.minimap.corner2, id + (offset) * 4 + 1)
                    offset = 1

                self.dolphin.render_collision(self, objlist, ObjectSelectionEntry, selected)
                offset = len(objlist)

                if vismenu.enemyroute.is_selectable():
                    for i, obj in enumerate(obj for obj in self.level_file.enemypointgroups.points() if obj not in selected):
                        objlist.append(
                            ObjectSelectionEntry(obj=obj,
                                                 pos1=obj.position,
                                                 pos2=None,
                                                 pos3=None,
                                                 rotation=None)
                        )
                        self.models.render_generic_position_colored_id(obj.position, id + (offset+i) * 4)

                    offset = len(objlist)

                selectable_objectroutes = vismenu.objectroutes.is_selectable()
                selectable_cameraroutes = vismenu.cameraroutes.is_selectable()
                selectable_unassignedroutes = vismenu.unassignedroutes.is_selectable()

                if selectable_objectroutes or selectable_cameraroutes or selectable_unassignedroutes:
                    camera_routes = set(camera.route for camera in self.level_file.cameras)
                    object_routes = set(obj.route for obj in self.level_file.objects.objects)
                    assigned_routes = camera_routes.union(object_routes)
                    i = 0
                    for route in self.level_file.routes:
                        for obj in route.points:
                            if obj in selected:
                                continue
                            if (not ((route in object_routes and selectable_objectroutes) or
                                     (route in camera_routes and selectable_cameraroutes) or
                                     (route not in assigned_routes and selectable_unassignedroutes))):
                                continue
                            objlist.append(
                                ObjectSelectionEntry(obj=obj,
                                                 pos1=obj.position,
                                                 pos2=None,
                                                 pos3=None,
                                                 rotation=None))
                            self.models.render_generic_position_colored_id(obj.position, id + (offset+i) * 4)
                            i += 1

                    offset = len(objlist)

                if vismenu.checkpoints.is_selectable():
                    for i, obj in enumerate(obj for obj in self.level_file.objects_with_2positions() if obj not in selected):
                        objlist.append(
                            ObjectSelectionEntry(obj=obj,
                                             pos1=obj.start,
                                             pos2=obj.end,
                                             pos3=None,
                                             rotation=None))
                        self.models.render_generic_position_colored_id(obj.start, id+(offset+i)*4)
                        self.models.render_generic_position_colored_id(obj.end, id+(offset+i)*4 + 1)

                    offset = len(objlist)

                if vismenu.cameras.is_selectable():
                    for i, obj in enumerate(obj for obj in self.level_file.cameras if obj not in selected):
                        if obj.name == "para":
                            continue
                        if obj.camtype in (5, 6):
                            objlist.append(
                                ObjectSelectionEntry(obj=obj,
                                                     pos1=obj.position,
                                                     pos2=obj.position2,
                                                     pos3=obj.position3,
                                                     rotation=obj.rotation))
                            self.models.render_generic_position_rotation_colored_id(obj.position, obj.rotation,
                                                                                    id + (offset + i) * 4)
                            self.models.render_generic_position_colored_id(obj.position2, id + (offset + i) * 4 + 1)
                            self.models.render_generic_position_colored_id(obj.position3, id + (offset + i) * 4 + 2)
                        elif obj.camtype == 4:
                            objlist.append(
                                ObjectSelectionEntry(obj=obj,
                                                     pos1=obj.position,
                                                     pos2=None,
                                                     pos3=obj.position3,
                                                     rotation=obj.rotation))
                            self.models.render_generic_position_rotation_colored_id(obj.position, obj.rotation,
                                                                                    id + (offset + i) * 4)
                            self.models.render_generic_position_colored_id(obj.position3, id + (offset + i) * 4 + 1)
                        else:
                            objlist.append(
                                ObjectSelectionEntry(obj=obj,
                                                     pos1=obj.position,
                                                     pos2=None,
                                                     pos3=None,
                                                     rotation=obj.rotation))
                            self.models.render_generic_position_rotation_colored_id(obj.position, obj.rotation,
                                                                                    id + (offset + i) * 4)

                    offset = len(objlist)

                for is_selectable, collection in (
                        (vismenu.objects.is_selectable(), self.level_file.objects.objects),
                        (vismenu.kartstartpoints.is_selectable(), self.level_file.kartpoints.positions),
                        (vismenu.areas.is_selectable(), self.level_file.areas.areas),
                        (vismenu.respawnpoints.is_selectable(), self.level_file.respawnpoints)
                        ):
                    if not is_selectable:
                        continue

                    for i, obj in enumerate(obj for obj in collection if obj not in selected):
                        objlist.append(
                            ObjectSelectionEntry(obj=obj,
                                                 pos1=obj.position,
                                                 pos2=None,
                                                 pos3=None,
                                                 rotation=obj.rotation))
                        self.models.render_generic_position_rotation_colored_id(obj.position, obj.rotation,
                                                                                id + (offset + i) * 4)

                    offset = len(objlist)

                pixels = glReadPixels(click_x, click_y, clickwidth, clickheight, GL_RGB, GL_UNSIGNED_BYTE)

                indexes = set()
                for i in range(0, clickwidth * clickheight):
                    if pixels[i * 3] != 0xFF:
                        upper = pixels[i * 3] & 0x0F
                        index = (upper << 16) | (pixels[i * 3 + 1] << 8) | pixels[i * 3 + 2]
                        indexes.add(index)

                for index in indexes:
                    entry: ObjectSelectionEntry = objlist[index // 4]
                    obj = entry.obj
                    if obj not in selected:
                        selected[obj] = 0

                    elements_exist = selected[obj]

                    if index & 0b11 == 0:  # First object position
                        if entry.pos1 is not None and (elements_exist & 1) == 0:
                            selected_positions.append(entry.pos1)
                            if entry.rotation is not None:
                                selected_rotations.append(entry.rotation)
                            elements_exist |= 1
                    if index & 0b11 == 1:  # Second object position
                        if entry.pos2 is not None and (elements_exist & 2) == 0:
                            selected_positions.append(entry.pos2)
                            elements_exist |= 2
                    if index & 0b11 == 2:  # Third object position
                        if entry.pos3 is not None and (elements_exist & 4) == 0:
                            selected_positions.append(entry.pos3)
                            elements_exist |= 4

                    selected[obj] = elements_exist

                # In a marquee selection, if there was a selection, do another iteration for
                # selecting potentially-overlapping objects.
                continue_picking = (clickwidth > 1 or clickheight > 1) and indexes

            selected = list(selected)
            if not shiftpressed:
                self.selected = selected
                self.selected_positions = selected_positions
                self.selected_rotations = selected_rotations

            else:
                for obj in selected:
                    if obj not in self.selected:
                        self.selected.append(obj)
                for pos in selected_positions:
                    if pos not in self.selected_positions:
                        self.selected_positions.append(pos)

                for rot in selected_rotations:
                    if rot not in self.selected_rotations:
                        self.selected_rotations.append(rot)

            # Store selection in a logical order that matches the order of the objects in their
            # respective groups. This is relevant to ensure that potentially copied, route-like
            # objects, where order matters, are pasted in the same order.
            # Objects that are not part of the BOL document are kept at the end of the list in
            # the same initial, arbitrary pick order.
            selected = self.selected
            self.selected = []
            selected_set = set(selected)
            for obj in self.level_file.get_all_objects():
                if obj in selected_set:
                    self.selected.append(obj)
                    selected_set.remove(obj)
            for obj in selected:
                if obj in selected_set:
                    self.selected.append(obj)

            self.editor.select_from_3d_to_treeview()

            self.gizmo.move_to_average(self.selected_positions, self.selected_rotations)
            if len(selected) == 0:
                self.gizmo.hidden = True
            if self.mode == MODE_3D: # In case of 3D mode we need to update scale due to changed gizmo position
                gizmo_scale = (self.gizmo.position - campos).norm() / 130.0

        # Restore the default framebuffer of the GL widget.
        if use_pick_framebuffer:
            glBindFramebuffer(GL_FRAMEBUFFER, self.defaultFramebufferObject())

        #print("gizmo status", self.gizmo.was_hit_at_all)
        #glClearColor(1.0, 1.0, 1.0, 0.0)
        glClearColor(*self.backgroundcolor)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glEnable(GL_DEPTH_TEST)
        glDisable(GL_TEXTURE_2D)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        if self.main_model is not None:
            if self.alternative_mesh is None:
                glCallList(self.main_model)
            else:
                if self.mode != MODE_TOPDOWN:
                    light0_position = (campos.x, -campos.z, campos.y, 1.0)
                    light0_diffuse = (5.0, 5.0, 5.0, 1.0)
                    light0_specular = (0.8, 0.8, 0.8, 1.0)
                    light0_ambient = (1.8, 1.8, 1.8, 1.0)
                    glLightfv(GL_LIGHT0, GL_POSITION, light0_position)
                    glLightfv(GL_LIGHT0, GL_DIFFUSE, light0_diffuse)
                    glLightfv(GL_LIGHT0, GL_DIFFUSE, light0_specular)
                    glLightfv(GL_LIGHT0, GL_AMBIENT, light0_ambient)
                    glShadeModel(GL_SMOOTH)
                    glEnable(GL_LIGHT0)
                    glEnable(GL_RESCALE_NORMAL)
                    glEnable(GL_NORMALIZE)
                    glEnable(GL_LIGHTING)

                glPushMatrix()
                glScalef(1.0, -1.0, 1.0)
                self.alternative_mesh.render(selectedPart=self.highlight_colltype,
                                             cull_faces=self.cull_faces)
                glPopMatrix()

                if self.mode != MODE_TOPDOWN:
                    glDisable(GL_LIGHTING)

        glDisable(GL_TEXTURE_2D)

        if self.snapping_enabled and self.collision is not None:
            snapping_hash = hash((self.snapping_mode, self.collision.hash))
            if self.snapping_last_hash != snapping_hash:
                self.snapping_last_hash = snapping_hash

                # Clear previous display list.
                if self.snapping_display_list is not None:
                    glDeleteLists(self.snapping_display_list, 1)
                    self.snapping_display_list = None

                # Create and compile the display list.
                self.snapping_display_list = glGenLists(1)
                glNewList(self.snapping_display_list, GL_COMPILE)

                glDisable(GL_DEPTH_TEST)

                glDisable(GL_ALPHA_TEST)
                glEnable(GL_BLEND)
                glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

                # Draw wireframe.
                glColor4f(0.1, 0.1, 0.1, 0.3)
                glBegin(GL_LINES)
                for triangle in self.collision.triangles:
                    glVertex3f(triangle.origin.x, triangle.origin.y, triangle.origin.z)
                    glVertex3f(triangle.p2.x, triangle.p2.y, triangle.p2.z)
                    glVertex3f(triangle.origin.x, triangle.origin.y, triangle.origin.z)
                    glVertex3f(triangle.p3.x, triangle.p3.y, triangle.p3.z)
                    glVertex3f(triangle.p2.x, triangle.p2.y, triangle.p2.z)
                    glVertex3f(triangle.p3.x, triangle.p3.y, triangle.p3.z)
                glEnd()

                glBlendFunc(GL_ONE, GL_ZERO)
                glDisable(GL_BLEND)
                glEnable(GL_ALPHA_TEST)

                # Draw points.
                glPointSize(5)
                glColor3f(0.0, 0.0, 0.0)
                glBegin(GL_POINTS)
                points = self._get_snapping_points()
                for point in points:
                    glVertex3f(*point)
                glEnd()
                glPointSize(3)
                glColor3f(1.0, 1.0, 1.0)
                glBegin(GL_POINTS)
                for point in points:
                    glVertex3f(*point)
                glEnd()
                glPointSize(1)

                glEnable(GL_DEPTH_TEST)

                glEndList()

            glCallList(self.snapping_display_list)

        glColor4f(1.0, 1.0, 1.0, 1.0)
        self.grid.render()
        if self.mode == MODE_TOPDOWN:
            glClear(GL_DEPTH_BUFFER_BIT)

            if self.minimap is not None and vismenu.minimap.is_visible() and self.minimap.is_available():
                self.minimap.render()
                glClear(GL_DEPTH_BUFFER_BIT)
        #else:
        #    if self.minimap is not None and vismenu.minimap.is_visible():
        #        self.minimap.render()
        #    glDisable(GL_DEPTH_TEST)

        glEnable(GL_ALPHA_TEST)
        glAlphaFunc(GL_GEQUAL, 0.5)
        p = 0

        self.dolphin.render_visual(self, self.selected)

        """for valid, kartpos in self.karts:
            if valid:
                self.models.render_player_position_colored(kartpos, valid in self.selected, p)
            p += 1"""

        if self.level_file is not None:
            selected = self.selected
            positions = self.selected_positions

            select_optimize = {x:True for x in selected}

            visible_objectroutes = vismenu.objectroutes.is_visible()
            visible_cameraroutes = vismenu.cameraroutes.is_visible()
            visible_unassignedroutes = vismenu.unassignedroutes.is_visible()

            if visible_objectroutes or visible_cameraroutes or visible_unassignedroutes:
                routes_to_highlight = set()
                camera_routes = set()
                object_routes = set()

                for camera in self.level_file.cameras:
                    if camera.route is not None and camera in select_optimize:
                        routes_to_highlight.add(camera.route)
                    camera_routes.add(camera.route)

                for obj in self.level_file.objects.objects:
                    if obj.route is not None and obj in select_optimize:
                        routes_to_highlight.add(obj.route)
                    object_routes.add(obj.route)

                assigned_routes = camera_routes.union(object_routes)
                shared_routes = camera_routes.intersection(object_routes)

                for route in self.level_file.routes:
                    if (not ((route in object_routes and visible_objectroutes) or
                             (route in camera_routes and visible_cameraroutes) or
                             (route not in assigned_routes and visible_unassignedroutes))):
                        continue

                    selected = route in routes_to_highlight
                    route_color = "unassignedroute"
                    if route in shared_routes:
                        route_color = "sharedroute"
                    elif route in object_routes:
                        route_color = "objectroute"
                    elif route in camera_routes:
                        route_color = "cameraroute"
                    for point in route.points:
                        point_selected = point in select_optimize
                        self.models.render_generic_position_colored(point.position, point_selected, route_color)
                        selected = selected or point_selected

                    if selected:
                        glLineWidth(3.0)
                    glBegin(GL_LINE_STRIP)
                    glColor3f(0.0, 0.0, 0.0)
                    for point in route.points:
                        pos = point.position
                        glVertex3f(pos.x, -pos.z, pos.y)
                    glEnd()
                    if selected:
                        glLineWidth(1.0)

            if vismenu.enemyroute.is_visible():
                enemypoints_to_highlight = set()
                for respawn_point in self.level_file.respawnpoints:
                    if respawn_point not in select_optimize:
                        continue
                    next_enemy_point = respawn_point.unk1
                    if next_enemy_point != -1:
                        enemypoints_to_highlight.add(next_enemy_point)

                point_index = 0
                for group in self.level_file.enemypointgroups.groups:
                    if len(group.points) == 0:
                        continue

                    group_selected = False
                    for point in group.points:
                        if point in select_optimize:
                            group_selected = True
                            glColor3f(0.3, 0.3, 0.3)
                            self.models.draw_sphere(point.position, point.scale)

                        if point_index in enemypoints_to_highlight:
                            glColor3f(1.0, 1.0, 0.0)
                            self.models.draw_sphere(point.position, 600)

                        self.models.render_generic_position_colored(point.position, point in select_optimize, "enemypoint")

                        if point.itemsonly:
                            glColor3f(1.0, 0.5, 0.1)
                            self.models.draw_cylinder(point.position, 1600, 1600)
                        if point.driftdirection:
                            glColor3f(0.9, 0.0, 0.1)
                            self.models.draw_cylinder(point.position, 1400, 1400)
                        if point.driftacuteness:
                            glColor3f(0.1, 0.1, 1.0)
                            self.models.draw_cylinder(point.position, 1200, 1200)
                        if point.driftduration:
                            glColor3f(0.9, 0.9, 0.1)
                            self.models.draw_cylinder(point.position, 1000, 1000)
                        if point.swerve:
                            glColor3f(0.1, 0.9, 0.2)
                            self.models.draw_cylinder(point.position, 800, 800)
                        if point.driftsupplement:
                            glColor3f(0.9, 0.0, 0.9)
                            self.models.draw_cylinder(point.position, 600, 600)
                        if point.nomushroomzone:
                            glColor3f(0.1, 0.8, 1.0)
                            self.models.draw_cylinder(point.position, 1800, 1800)

                        point_index += 1

                    # Draw the connections between each enemy point.
                    if group_selected:
                        glLineWidth(3.0)
                    glBegin(GL_LINE_STRIP)
                    glColor3f(0.0, 0.0, 0.0)
                    for point in group.points:
                        pos = point.position
                        glVertex3f(pos.x, -pos.z, pos.y)
                    glEnd()
                    if group_selected:
                        glLineWidth(1.0)

                    # Draw the connections between each enemy point group.
                    pointA = group.points[-1]
                    color_gen = random.Random(group.id)
                    color_components = [
                        color_gen.random() * 0.5,
                        color_gen.random() * 0.5,
                        color_gen.random() * 0.2,
                    ]
                    color_gen.shuffle(color_components)
                    color_components[2] += 0.5
                    glColor3f(*color_components)
                    for groupB in self.level_file.enemypointgroups.groups:
                        if group is groupB or len(groupB.points) == 0:
                            continue
                        pointB = groupB.points[0]
                        if pointA.link == pointB.link:
                            groupB_selected = any(map(lambda p: p in select_optimize, groupB.points))
                            if group_selected or groupB_selected:
                                glLineWidth(3.0)
                            glBegin(GL_LINES)
                            glVertex3f(pointA.position.x, -pointA.position.z, pointA.position.y)
                            glVertex3f(pointB.position.x, -pointB.position.z, pointB.position.y)
                            glEnd()
                            if group_selected or groupB_selected:
                                glLineWidth(1.0)

            if vismenu.checkpoints.is_visible():
                checkpoints_to_highlight = set()
                count = 0

                # Get all concave checkpoints
                concave_checkpoints = set()
                checkpoint_groups = self.level_file.checkpoints.groups
                for group in self.level_file.checkpoints.groups:
                    if not group.points:
                        continue
                    for c1, c2 in zip(group.points, group.points[1:]):
                        if not check_checkpoints(c1, c2):
                            concave_checkpoints.add(c1)
                            concave_checkpoints.add(c2)
                    next_groups = [checkpoint_groups[next] for next in group.nextgroup if 0 <= next < len(checkpoint_groups)]
                    next_points = [next_group.points[0] for next_group in next_groups if next_group.points]
                    c1 = group.points[-1]
                    for c2 in next_points:
                        if not check_checkpoints(c1, c2):
                            concave_checkpoints.add(c1)
                            concave_checkpoints.add(c2)

                for i, group in enumerate(self.level_file.checkpoints.groups):
                    prev = None
                    # Draw the endpoints
                    for checkpoint in group.points:
                        start_point_selected = checkpoint.start in positions
                        end_point_selected = checkpoint.end in positions
                        self.models.render_generic_position_colored(checkpoint.start,
                                                                    start_point_selected,
                                                                    "checkpointleft")
                        self.models.render_generic_position_colored(checkpoint.end,
                                                                    end_point_selected,
                                                                    "checkpointright")

                        if start_point_selected or end_point_selected:
                            checkpoints_to_highlight.add(count)
                        count += 1

                    # Draw the lines between the points
                    glBegin(GL_LINES)
                    for checkpoint in group.points:
                        if checkpoint in concave_checkpoints:
                            glColor3f(1.0, 0.0, 0.0)
                        else:
                            glColor3f(*colors[i % 4])

                        pos1 = checkpoint.start
                        pos2 = checkpoint.end

                        #self.models.render_generic_position(pos1, False)
                        #self.models.render_generic_position(pos2, False)

                        glVertex3f(pos1.x, -pos1.z, pos1.y)
                        glVertex3f(pos2.x, -pos2.z, pos2.y)
                        #glColor3f(0.0, 0.0, 0.0)

                        if prev is not None:
                            if prev not in concave_checkpoints:
                                glColor3f(*colors[i % 4])
                            pos3 = prev.start
                            pos4 = prev.end

                            glVertex3f(pos1.x, -pos1.z, pos1.y)
                            glVertex3f(pos3.x, -pos3.z, pos3.y)
                            glVertex3f(pos2.x, -pos2.z, pos2.y)
                            glVertex3f(pos4.x, -pos4.z, pos4.y)

                        prev = checkpoint

                    glEnd()

                for respawn_point in self.level_file.respawnpoints:
                    if respawn_point not in select_optimize:
                        continue
                    preceding_checkpoint_index = respawn_point.unk3
                    if preceding_checkpoint_index != -1:
                        checkpoints_to_highlight.add(preceding_checkpoint_index)
                    # What about unk2? In Daisy Cruiser, a respawn point has its unk2 set instead.
                    # Was that an oversight by the original maker?

                if checkpoints_to_highlight:
                    glLineWidth(4.0)
                    point_index = 0
                    for i, group in enumerate(self.level_file.checkpoints.groups):
                        for checkpoint in group.points:
                            if point_index in checkpoints_to_highlight:
                                if checkpoint in concave_checkpoints:
                                    glColor3f(1.0, 0.0, 0.0)
                                else:
                                    glColor3f(*colors[i % 4])

                                pos1 = checkpoint.start
                                pos2 = checkpoint.end
                                glBegin(GL_LINES)
                                glVertex3f(pos1.x, -pos1.z, pos1.y)
                                glVertex3f(pos2.x, -pos2.z, pos2.y)
                                glEnd()
                            point_index += 1
                    glLineWidth(1.0)

                for i, group in enumerate(self.level_file.checkpoints.groups):
                    glColor3f(*colors[i % 4])
                    prev = None
                    for checkpoint in group.points:
                        if prev is None:
                            prev = checkpoint
                        else:
                            mid1 = (prev.start + prev.end) / 2.0
                            mid2 = (checkpoint.start + checkpoint.end) / 2.0

                            self.models.draw_arrow_head(mid1, mid2)
                            prev = checkpoint

                glBegin(GL_LINES)
                for i, group in enumerate(self.level_file.checkpoints.groups):
                    glColor3f(*colors[i % 4])
                    prev = None
                    for checkpoint in group.points:
                        if prev is None:
                            prev = checkpoint
                        else:
                            mid1 = (prev.start+prev.end)/2.0
                            mid2 = (checkpoint.start+checkpoint.end)/2.0
                            glVertex3f(mid1.x, -mid1.z, mid1.y)
                            glVertex3f(mid2.x, -mid2.z, mid2.y)
                            prev = checkpoint
                glEnd()

                if self.editor.next_checkpoint_start_position is not None:
                    self.models.render_generic_position_colored(
                        Vector3(*self.editor.next_checkpoint_start_position), True,
                        "checkpointleft")

            if vismenu.objects.is_visible():
                for object in self.level_file.objects.objects:
                    self.models.render_generic_position_rotation_colored("objects",
                                                                 object.position, object.rotation,
                                                                 object in select_optimize)
            if vismenu.kartstartpoints.is_visible():
                for object in self.level_file.kartpoints.positions:
                    self.models.render_generic_position_rotation_colored("startpoints",
                                                                object.position, object.rotation,
                                                                object in select_optimize)
            if vismenu.areas.is_visible():
                for object in self.level_file.areas.areas:
                    self.models.render_generic_position_rotation_colored("areas",
                                                                object.position, object.rotation,
                                                                object in select_optimize)
                    if object in select_optimize:
                        glColor4f(*colors_selection)
                    else:
                        glColor4f(*colors_area)

                    self.models.draw_wireframe_cube(object.position, object.rotation, object.scale*100)
            if vismenu.cameras.is_visible():
                for object in self.level_file.cameras:
                    if object.name == "para":
                        continue
                    self.models.render_generic_position_rotation_colored("camera",
                                                                object.position, object.rotation,
                                                                 object in select_optimize)

                    if object.camtype in (4, 5, 6):
                        glColor3f(0.0, 1.0, 0.0)
                        self.models.draw_sphere(object.position3, 600, object in select_optimize)
                        if object.camtype != 4:
                            glColor3f(1.0, 0.0, 0.0)
                            self.models.draw_sphere(object.position2, 600, object in select_optimize)

                            glBegin(GL_LINES)
                            glColor3f(0, 0, 0)
                            glVertex3f(object.position3.x, -object.position3.z, object.position3.y)
                            glVertex3f(object.position2.x, -object.position2.z, object.position2.y)
                            glEnd()

                            self.models.draw_arrow_head(object.position3, object.position2)


            if vismenu.respawnpoints.is_visible():
                for object in self.level_file.respawnpoints:
                    self.models.render_generic_position_rotation_colored("respawn",
                                                                object.position, object.rotation,
                                                                 object in select_optimize)
            if self.minimap is not None and self.minimap.is_available() and vismenu.minimap.is_visible():
                self.models.render_generic_position_colored(self.minimap.corner1,
                                                            self.minimap.corner1 in positions,
                                                            'minimap')
                self.models.render_generic_position_colored(self.minimap.corner2,
                                                            self.minimap.corner2 in positions,
                                                            'minimap')

        self.gizmo.render_scaled(gizmo_scale, is3d=self.mode == MODE_3D, hover_id=gizmo_hover_id)

        glDisable(GL_DEPTH_TEST)
        if self.selectionbox_start is not None and self.selectionbox_end is not None:
            #print("drawing box")
            startx, startz = self.selectionbox_start
            endx, endz = self.selectionbox_end
            glColor4f(1.0, 0.0, 0.0, 1.0)
            glLineWidth(2.0)
            glBegin(GL_LINE_LOOP)
            glVertex3f(startx, startz, 0)
            glVertex3f(startx, endz, 0)
            glVertex3f(endx, endz, 0)
            glVertex3f(endx, startz, 0)

            glEnd()
            glLineWidth(1.0)

        if self.selectionbox_projected_origin is not None and self.selectionbox_projected_coords is not None:
            #print("drawing box")
            origin = self.selectionbox_projected_origin
            point2, point3, point4 = self.selectionbox_projected_coords
            glColor4f(1.0, 0.0, 0.0, 1.0)
            glLineWidth(2.0)

            point1 = origin

            glBegin(GL_LINE_LOOP)
            glVertex3f(point1.x, point1.y, point1.z)
            glVertex3f(point2.x, point2.y, point2.z)
            glVertex3f(point3.x, point3.y, point3.z)
            glVertex3f(point4.x, point4.y, point4.z)
            glEnd()

            glLineWidth(1.0)

        glEnable(GL_DEPTH_TEST)
        glFinish()

    @catch_exception
    def mousePressEvent(self, event):
        self.usercontrol.handle_press(event)

    @catch_exception
    def mouseMoveEvent(self, event):
        self.usercontrol.handle_move(event)

        self._mouse_pos_changed = True

    @catch_exception
    def mouseReleaseEvent(self, event):
        self.usercontrol.handle_release(event)

    def wheelEvent(self, event):
        wheel_delta = event.angleDelta().y()

        if self.editorconfig is not None:
            invert = self.editorconfig.getboolean("invertzoom")
            if invert:
                wheel_delta = -1*wheel_delta

        if wheel_delta < 0:
            self.zoom_out()

        elif wheel_delta > 0:
            self.zoom_in()

    def zoom_in(self):
        if self.mode == MODE_TOPDOWN:
            current = self.zoom_factor
            fac = calc_zoom_out_factor(current)
            self.zoom(fac)
        else:
            self.zoom_inout_3d(True)

    def zoom_out(self):
        if self.mode == MODE_TOPDOWN:
            current = self.zoom_factor
            fac = calc_zoom_in_factor(current)
            self.zoom(fac)
        else:
            self.zoom_inout_3d(False)

    def zoom_inout_3d(self, zoom_in):
        speedup = 1 if zoom_in else -1
        if self.shift_is_pressed:
            speedup *= self._wasdscrolling_speedupfactor
        speed = self._wasdscrolling_speed / 2

        self.camera_direction.normalize()
        view = self.camera_direction.copy()
        view = view * speed * speedup

        self.offset_x += view.x
        self.camera_height += view.z
        self.offset_z += view.y

        self.do_redraw()

    def create_ray_from_mouseclick(self, mousex, mousey, yisup=False):
        self.camera_direction.normalize()
        height = self.canvas_height
        width = self.canvas_width

        view = self.camera_direction.copy()

        h = view.cross(Vector3(0, 0, 1))
        v = h.cross(view)

        h.normalize()
        v.normalize()

        rad = 75 * pi / 180.0
        vLength = tan(rad / 2) * 1.0
        hLength = vLength * (width / height)

        v *= vLength
        h *= hLength

        x = mousex - width / 2
        y = height - mousey- height / 2

        x /= (width / 2)
        y /= (height / 2)
        camerapos = Vector3(self.offset_x, self.offset_z, self.camera_height)

        pos = camerapos + view * 1.0 + h * x + v * y
        dir = pos - camerapos

        if yisup:
            tmp = pos.y
            pos.y = -pos.z
            pos.z = tmp

            tmp = dir.y
            dir.y = -dir.z
            dir.z = tmp

        return Line(pos, dir)

    def get_3d_coordinates(self, mousex, mousey):
        ray = self.create_ray_from_mouseclick(mousex, mousey)
        pos = None

        if self.collision is not None:
            pos = self.collision.collide_ray(ray)

        if pos is None:
            plane = Plane.xy_aligned(Vector3(0.0, 0.0, 0.0))

            collision = ray.collide_plane(plane)
            if collision is not False:
                pos, _ = collision

        return pos

    def get_closest_snapping_point(self, mousex, mousey, is3d=True):
        if is3d:
            ray = self.create_ray_from_mouseclick(mousex, mousey)
        else:
            mapx, mapz = self.mouse_coord_to_world_coord(mousex, mousey)
            ray = Line(Vector3(mapx, mapz, 99999999.0), Vector3(0.0, 0.0, -1.0))
        return self.collision.get_closest_point(ray, self._get_snapping_points())


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
        points = [(cos(2.0 * pi / POINT_COUNT * x) * radius + radius,
                   sin(2.0 * pi / POINT_COUNT * x) * radius + radius)
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


class ObjectViewSelectionToggle(object):
    def __init__(self, name, menuparent, directed, colors):
        self.name = name
        self.menuparent = menuparent

        icon = QtGui.QIcon()
        for size in (16, 22, 24, 28, 32, 40, 48, 64, 80, 96):
            icon.addPixmap(create_object_type_pixmap(size, directed, colors))

        self.action_view_toggle = QtGui.QAction("{0}".format(name), menuparent)
        self.action_select_toggle = QtGui.QAction("{0} selectable".format(name), menuparent)
        self.action_view_toggle.setCheckable(True)
        self.action_view_toggle.setChecked(True)
        self.action_view_toggle.setIcon(icon)
        self.action_select_toggle.setCheckable(True)
        self.action_select_toggle.setChecked(True)
        self.action_select_toggle.setIcon(icon)

        self.action_view_toggle.triggered.connect(self.handle_view_toggle)
        self.action_select_toggle.triggered.connect(self.handle_select_toggle)

        menuparent.addAction(self.action_view_toggle)
        menuparent.addAction(self.action_select_toggle)

    def handle_view_toggle(self, val):
        if not val:
            self.action_select_toggle.setChecked(False)
        else:
            self.action_select_toggle.setChecked(True)

    def handle_select_toggle(self, val):
        if val:
            self.action_view_toggle.setChecked(True)

    def is_visible(self):
        return self.action_view_toggle.isChecked()

    def is_selectable(self):
        return self.action_select_toggle.isChecked()


class FilterViewMenu(QtWidgets.QMenu):
    filter_update = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setTitle("Filter View")

        self.show_all = QtGui.QAction("Show All", self)
        self.show_all.triggered.connect(self.handle_show_all)
        self.addAction(self.show_all)

        self.hide_all = QtGui.QAction("Hide All", self)
        self.hide_all.triggered.connect(self.handle_hide_all)
        self.addAction(self.hide_all)

        self.addSeparator()

        with open("lib/color_coding.json", "r") as f:
            colors = json.load(f)
            colors = {k: (round(r * 255), round(g * 255), round(b * 255)) for k, (r, g, b, _a) in colors.items()}

        self.enemyroute = ObjectViewSelectionToggle("Enemy Paths", self, False,
                                                    [colors["EnemyPaths"]])
        self.objectroutes = ObjectViewSelectionToggle("Object Routes", self, False,
                                                      [colors["ObjectRoutes"]])
        self.cameraroutes = ObjectViewSelectionToggle("Camera Routes", self, False,
                                                      [colors["CameraRoutes"]])
        self.unassignedroutes = ObjectViewSelectionToggle("Unassigned Routes", self, False,
                                                          [colors["UnassignedRoutes"]])
        self.checkpoints = ObjectViewSelectionToggle(
            "Checkpoints", self, False, [colors["CheckpointLeft"], colors["CheckpointRight"]])
        self.objects = ObjectViewSelectionToggle("Objects", self, True, [colors["Objects"]])
        self.areas = ObjectViewSelectionToggle("Areas", self, True, [colors["Areas"]])
        self.cameras = ObjectViewSelectionToggle("Cameras", self, True, [colors["Camera"]])
        self.respawnpoints = ObjectViewSelectionToggle("Respawn Points", self, True,
                                                       [colors["Respawn"]])
        self.kartstartpoints = ObjectViewSelectionToggle("Kart Start Points", self, True,
                                                         [colors["StartPoints"]])
        self.minimap = ObjectViewSelectionToggle("Minimap", self, False, [colors["Minimap"]])

        for action in self.get_entries():
            action.action_view_toggle.triggered.connect(self.emit_update)
            action.action_select_toggle.triggered.connect(self.emit_update)

    def get_entries(self):
        return (self.enemyroute,
                self.objectroutes,
                self.cameraroutes,
                self.unassignedroutes,
                self.checkpoints,
                self.objects,
                self.areas,
                self.cameras,
                self.respawnpoints,
                self.kartstartpoints,
                self.minimap)

    def handle_show_all(self):
        for action in self.get_entries():
            action.action_view_toggle.setChecked(True)
            action.action_select_toggle.setChecked(True)
        self.filter_update.emit()

    def handle_hide_all(self):
        for action in self.get_entries():
            action.action_view_toggle.setChecked(False)
            action.action_select_toggle.setChecked(False)
        self.filter_update.emit()

    def emit_update(self, val):
        self.filter_update.emit()

    def mouseReleaseEvent(self, e):
        try:
            action = self.activeAction()
            if action and action.isEnabled():
                action.trigger()
            else:
                QtWidgets.QMenu.mouseReleaseEvent(self, e)
        except:
            traceback.print_exc()
