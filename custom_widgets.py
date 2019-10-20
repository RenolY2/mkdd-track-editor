import traceback
import math
import xml.etree.ElementTree as etree
from time import sleep
from array import array
from timeit import default_timer
from copy import copy
from math import sin, cos, atan2, radians, degrees
from itertools import chain

from PyQt5.QtGui import QMouseEvent, QWheelEvent, QPainter, QColor, QFont, QFontMetrics, QPolygon, QImage, QPixmap, QKeySequence
from PyQt5.QtWidgets import (QWidget, QListWidget, QListWidgetItem, QDialog, QMenu,
                            QMdiSubWindow, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QTextEdit, QAction, QShortcut)
from PyQt5.QtCore import QSize, pyqtSignal, QPoint, QRect
from PyQt5.QtCore import Qt

from helper_functions import calc_zoom_in_factor, calc_zoom_out_factor
from lib.vectors import Triangle, Vector3
ENTITY_SIZE = 10

DEFAULT_ENTITY = QColor("black")
DEFAULT_MAPZONE = QColor("grey")
DEFAULT_SELECTED = QColor("red")
DEFAULT_ANGLE_MARKER = QColor("blue")

SHOW_TERRAIN_NO_TERRAIN = 0
SHOW_TERRAIN_REGULAR = 1
SHOW_TERRAIN_LIGHT = 2

MOUSE_MODE_NONE = 0
MOUSE_MODE_MOVEWP = 1
MOUSE_MODE_ADDWP = 2
MOUSE_MODE_CONNECTWP = 3






def rotate(corner_x, corner_y, center_x, center_y, angle):
    temp_x = corner_x-center_x
    temp_y = corner_y-center_y
    angle = radians(angle)

    rotated_x = temp_x*cos(angle) - temp_y*sin(angle)
    rotated_y = temp_x*sin(angle) + temp_y*cos(angle)
    #print(sin(radians(angle)))

    return QPoint(int(rotated_x+center_x), int(rotated_y+center_y))


def rotate_rel(corner_x, corner_y, center_x, center_y, angle):
    temp_x = corner_x-center_x
    temp_y = corner_y-center_y
    angle = radians(angle)

    rotated_x = temp_x*cos(angle) - temp_y*sin(angle)
    rotated_y = temp_x*sin(angle) + temp_y*cos(angle)
    #print(sin(radians(angle)))

    return rotated_x, rotated_y


class MapViewer(QWidget):
    mouse_clicked = pyqtSignal(QMouseEvent)
    entity_clicked = pyqtSignal(QMouseEvent, str)
    mouse_dragged = pyqtSignal(QMouseEvent)
    mouse_released = pyqtSignal(QMouseEvent)
    mouse_wheel = pyqtSignal(QWheelEvent)
    position_update = pyqtSignal(QMouseEvent, tuple)
    select_update = pyqtSignal(QMouseEvent)
    move_points = pyqtSignal(float, float)
    connect_update = pyqtSignal(int, int)
    create_waypoint = pyqtSignal(float, float)
    ENTITY_SIZE = ENTITY_SIZE



    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._zoom_factor = 10

        self.SIZEX = 1024#768#1024
        self.SIZEY = 1024#768#1024


        #self.setMinimumSize(QSize(self.SIZEX, self.SIZEY))
        #self.setMaximumSize(QSize(self.SIZEX, self.SIZEY))
        self.setObjectName("bw_map_screen")


        self.origin_x = self.SIZEX//2
        self.origin_z = self.SIZEY//2

        self.offset_x = 0
        self.offset_z = 0

        self.point_x = 0
        self.point_y = 0
        self.polygon_cache = {}

        # This value is used for switching between several entities that overlap.
        self.next_selected_index = 0

        #self.entities = [(0,0, "abc")]
        self.waypoints = {}#{"abc": (0, 0)}
        self.paths = []

        self.left_button_down = False
        self.mid_button_down = False
        self.right_button_down = False
        self.drag_last_pos = None

        self.current_waypoint = None
        self.selected_waypoints = {}

        self.terrain = None
        self.terrain_scaled = None
        self.terrain_buffer = QImage()

        self.p = QPainter()
        self.p2 = QPainter()
        self.show_terrain_mode = SHOW_TERRAIN_REGULAR

        self.selectionbox_start = None
        self.selectionbox_end = None

        self.visualize_cursor = None

        self.click_mode = 0

        self.level_image = None

        self.collision = None

        self.highlighttriangle = None

        self.setMouseTracking(True)

        self.pikmin_routes = None

        self.mousemode = MOUSE_MODE_NONE

        self.connect_first_wp = None
        self.connect_second_wp = None

        self.move_startpos = []
        self.overlapping_wp_index = 0
        self.editorconfig = None
        self.setContextMenuPolicy(Qt.CustomContextMenu)

    def set_visibility(self, visibility):
        self.visibility_toggle = visibility

    def reset(self, keep_collision=False):
        del self.waypoints
        del self.paths
        self.overlapping_wp_index = 0

        self.waypoints = {}
        self.paths = []

        self.SIZEX = 1024#768#1024
        self.SIZEY = 1024
        self.origin_x = self.SIZEX//2
        self.origin_z = self.SIZEY//2

        if not keep_collision:
            self.offset_x = 0
            self.offset_z = 0

            self._zoom_factor = 10
            self.level_image = None

        self.left_button_down = False
        self.mid_button_down = False
        self.right_button_down = False
        self.drag_last_pos = None

        self.selectionbox_start = None
        self.selectionbox_end = None

        self.selected_waypoints = []
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        #self.setMinimumSize(QSize(self.SIZEX, self.SIZEY))
        #self.setMaximumSize(QSize(self.SIZEX, self.SIZEY))


        #del self.collision
        #self.collision = None

        self.highlighttriangle = None

        self.pikmin_routes = None

        self.mousemode = MOUSE_MODE_NONE
        self.connect_first_wp = None
        self.connect_second_wp = None

        self.move_startpos = []

    def set_collision(self, verts, faces):
        self.collision = Collision(verts, faces)

    def set_mouse_mode(self, mode):
        assert mode in (MOUSE_MODE_NONE, MOUSE_MODE_ADDWP, MOUSE_MODE_CONNECTWP, MOUSE_MODE_MOVEWP)

        self.connect_first_wp = None
        self.connect_second_wp = None

        self.mousemode = mode

        if mode == MOUSE_MODE_NONE:
            self.setContextMenuPolicy(Qt.CustomContextMenu)
        else:
            self.setContextMenuPolicy(Qt.DefaultContextMenu)
    @property
    def zoom_factor(self):
        return self._zoom_factor/10.0

    def zoom(self, fac):
        if (self.zoom_factor + fac) > 0.1 and (self.zoom_factor + fac) <= 25:
            self._zoom_factor += int(fac*10)
            #self.zoom_factor = round(self.zoom_factor, 2)
            zf = self.zoom_factor
            #self.setMinimumSize(QSize(self.SIZEX*zf, self.SIZEY*zf))
            #self.setMaximumSize(QSize(self.SIZEX*zf, self.SIZEY*zf))

            #self.terrain_buffer = QImage()
            self.update()
            """if self.terrain is not None:
                if self.terrain_scaled is None:
                    self.terrain_scaled = self.terrain
                self.terrain_scaled = self.terrain_scaled.scaled(self.height(), self.width())"""

    @catch_exception
    def paintEvent(self, event):
        start = default_timer()
        #print("painting")

        p = self.p
        p.begin(self)
        h = self.height()
        w = self.width()
        p.setBrush(QColor("white"))
        p.drawRect(0, 0, w-1, h-1)

        zf = self.zoom_factor
        current_entity = self.current_waypoint
        last_color = None
        draw_bound = event.rect().adjusted(-ENTITY_SIZE//2, -ENTITY_SIZE//2, ENTITY_SIZE//2, ENTITY_SIZE//2)
        #contains = draw_bound.contains
        selected_entities = self.selected_waypoints

        startx, starty = draw_bound.topLeft().x(), draw_bound.topLeft().y()
        endx, endy = startx+draw_bound.width(), starty+draw_bound.height()


        pen = p.pen()
        defaultwidth = pen.width()
        pen.setWidth(1)
        p.setPen(pen)
        offsetx, offsetz = (-self.origin_x-self.origin_x-self.offset_x,
                            -self.origin_z-self.origin_z-self.offset_z) # (self.origin_x)+self.offset_x, self.origin_z+self.offset_z
        #print(startx,starty, endx,endy, zf, offsetx, offsetz)

        drawstartx = 0+offsetx - (zf-1.0)*(w//2)
        drawstartz = 0+offsetz - (zf-1.0)*(h//2)

        drawendx = drawstartx + w + (zf-1.0)*(w//2)
        drawendz = drawstartz + h + (zf-1.0)*(h//2)

        drawendxView = drawstartx + w + (zf - 1.0) * (w)
        drawendzView = drawstartz + h + (zf - 1.0) * (h)

        viewportwidth = drawendx-drawstartx
        viewportheight = drawendz-drawstartz

        midx = (drawendx+drawstartx)/2.0
        midz = (drawendz+drawstartz)/2.0

        scalex = (w/viewportwidth)#/2.0
        scalez = (h/viewportheight)#/2.0

        if self.level_image is not None:
            #print("drawing things")
            startx = (-6000 - midx) * scalex
            startz = (-6000 - midz) * scalez
            endx = (6000 - midx) * scalex
            endz = (6000 - midz) * scalez
            p.drawImage(QRect(startx, startz, endx-startx, endz-startz),
                        self.level_image)

        pen = p.pen()
        prevwidth = pen.width()
        pen.setWidth(5)
        p.setPen(pen)
        # DRAW COORDINATE FIELD
        if True:#drawstartx <= 0 <= drawendx:
            x = (0-midx)*scalex
            #p.drawLine(QPoint(x-2,-5000), QPoint(x-2,+5000))
            #p.drawLine(QPoint(x-1,-5000), QPoint(x-1,+5000))
            p.drawLine(QPoint(x,-5000), QPoint(x,+5000))
            #p.drawLine(QPoint(x+1,-5000), QPoint(x+1,+5000))
            #p.drawLine(QPoint(x+2,-5000), QPoint(x+2,+5000))
        if True:#drawstartz <= 0 <= drawendz:
            z = (0-midz)*scalez
            #p.drawLine(QPoint(-5000, z-2), QPoint(+5000, z-2))
            #p.drawLine(QPoint(-5000, z-1), QPoint(+5000, z-1))
            p.drawLine(QPoint(-5000, z), QPoint(+5000, z))
            #p.drawLine(QPoint(-5000, z+1), QPoint(+5000, z+1))
            #p.drawLine(QPoint(-5000, z+2), QPoint(+5000, z+2))

        pen.setWidth(prevwidth)
        p.setPen(pen)
        step = 500

        loop_startx = int(drawstartx-drawstartx%step)
        loop_endx = int((drawendxView+step) - (drawendxView+step) % step)
        for x in range(loop_startx, loop_endx + 4*500, 500):
            x = (x-midx)*scalex
            if 0 <= x <= w or True:
                p.drawLine(QPoint(x, -5000), QPoint(x, +5000))

        loop_startz = int(drawstartz - drawstartz % step)
        loop_endz = int((drawendzView + step) - (drawendzView + step) % step)
        for z in range(loop_startz, loop_endz + 2*500, 500):
            z = (z-midz)*scalez
            if 0 <= z <= h or True:
                p.drawLine(QPoint(-5000, z), QPoint(+5000, z))

        if self.pikmin_routes is not None:
            selected = self.selected_waypoints
            waypoints = self.pikmin_routes.waypoints
            links = self.pikmin_routes.links
            #for waypoint, wp_info in self.waypoints.items():
            for wp_index, wp_data in waypoints.items():
                x,y,z,radius = wp_data
                color = DEFAULT_ENTITY
                if wp_index in selected:
                    #print("vhanged")
                    color = QColor("red")

                radius = radius*scalex
                #x, z = offsetx + x*zf, offsetz + z*zf
                x, z = (x-midx)*scalex, (z-midz)*scalez


                if last_color != color:

                    p.setBrush(color)
                    p.setPen(color)
                    #p.setPen(QColor(color))
                    last_color = color
                size=8
                p.drawRect(x-size//2, z-size//2, size, size)

                if radius > 0:
                    pen = p.pen()
                    prevwidth = pen.width()
                    pen.setWidth(2)
                    p.setPen(pen)
                    radius *= 2
                    p.drawArc(x-radius//2, z-radius//2, radius, radius, 0, 16*360)
                    pen.setWidth(prevwidth)
                    p.setPen(pen)

            arrows = []
            pen = p.pen()
            prevwidth = pen.width()
            pen.setWidth(5)
            pen.setColor(DEFAULT_ENTITY)
            p.setPen(pen)
            #for start_wp, end_wp in self.paths:
            for start_wp, linksto in links.items():
                startx, y, startz, radius = waypoints[start_wp]
                startx = (startx-midx)*scalex
                startz = (startz-midz)*scalez

                startpoint = QPoint(startx, startz)

                for end_wp in linksto:
                    endx, y, endz, radius = waypoints[end_wp]

                    endx = (endx-midx)*scalex
                    endz = (endz-midz)*scalez

                    p.drawLine(startpoint,
                               QPoint(endx, endz))

                    #angle = degrees(atan2(endx-startx, endz-startz))
                    angle = degrees(atan2(endz-startz, endx-startx))

                    centerx, centery = (endx)*0.8 + (startx)*0.2, \
                                       (endz)*0.8 + (startz)*0.2
                    p1 = rotate(centerx-15, centery, centerx, centery, angle+40)
                    p2 = rotate(centerx-15, centery, centerx, centery, angle-40)
                    #p.setPen(QColor("green"))
                    """pen = p.pen()
                    pen.setColor(QColor("blue"))
                    prevwidth = pen.width()
                    pen.setWidth(3)
                    p.setPen(pen)
                    p.drawLine(QPoint(centerx, centery),
                               p1)
                    p.drawLine(QPoint(centerx, centery),
                               p2)
                    pen.setColor(DEFAULT_ENTITY)
                    pen.setWidth(prevwidth)
                    p.setPen(pen)"""
                    arrows.append((QPoint(centerx, centery), p1, p2))
            pen = p.pen()
            pen.setColor(QColor("green"))
            pen.setWidth(4)
            p.setPen(pen)

            for arrow in arrows:
                p.drawLine(arrow[0], arrow[1])
                p.drawLine(arrow[0], arrow[2])

        if self.visualize_cursor is not None:
            a, b = self.visualize_cursor
            size = 5
            p.drawRect(a-size//2, b-size//2, size, size)

        pen.setColor(QColor("red"))
        pen.setWidth(2)
        p.setPen(pen)

        if self.selectionbox_start is not None and self.selectionbox_end is not None:
            startx, startz = ((self.selectionbox_start[0] - midx)*scalex,
                              (self.selectionbox_start[1] - midz)*scalez)

            endx, endz = (  (self.selectionbox_end[0] - midx)*scalex,
                            (self.selectionbox_end[1] - midz)*scalez)

            startpoint, endpoint = QPoint(startx, startz), QPoint(endx, endz)

            corner_horizontal = QPoint(endx, startz)
            corner_vertical = QPoint(startx, endz)
            selectionbox_polygon = QPolygon([startpoint, corner_horizontal, endpoint, corner_vertical,
                                            startpoint])
            p.drawPolyline(selectionbox_polygon)
        if self.highlighttriangle is not None:
            p1, p2, p3 = self.highlighttriangle
            p1x = (p1[0] - midx)*scalex
            p2x = (p2[0] - midx)*scalex
            p3x = (p3[0] - midx)*scalex
            p1z = (p1[2] - midz)*scalez
            p2z = (p2[2] - midz)*scalez
            p3z = (p3[2] - midz)*scalez

            selectionbox_polygon = QPolygon([QPoint(p1x, p1z), QPoint(p2x, p2z), QPoint(p3x, p3z),
                                             QPoint(p1x, p1z)])
            p.drawPolyline(selectionbox_polygon)

        p.end()
        end = default_timer()

        #print("time taken:", end-start, "sec")
        self.last_render = end
        #if end-start < 1/60.0:
        #    sleep(1/60.0 - (end-start))

    """def update(self):
        current = default_timer()

        if current-self.last_render < 1/90.0:
            pass
        else:
            self.repaint()"""

    @catch_exception
    def mousePressEvent(self, event):
        # Set up values for checking if the mouse hit a node
        offsetx, offsetz = (-self.origin_x-self.origin_x-self.offset_x,
                            -self.origin_z-self.origin_z-self.offset_z)
        h, w, zf = self.height(), self.width(), self.zoom_factor
        drawstartx = 0+offsetx - (zf-1.0)*(w//2)
        drawstartz = 0+offsetz - (zf-1.0)*(h//2)

        drawendx = drawstartx + w + (zf-1.0)*(w//2)
        drawendz = drawstartz + h + (zf-1.0)*(h//2)

        viewportwidth = drawendx-drawstartx
        viewportheight = drawendz-drawstartz

        midx = (drawendx+drawstartx)/2.0
        midz = (drawendz+drawstartz)/2.0

        scalex = (w/viewportwidth)#/2.0
        scalez = (h/viewportheight)#/2.0
        # Set up end
        # -------------
        if (event.buttons() & Qt.LeftButton and not self.left_button_down):
            mouse_x, mouse_z = (event.x(), event.y())
            selectstartx = mouse_x/scalex + midx
            selectstartz = mouse_z/scalez + midz

            if (self.mousemode == MOUSE_MODE_MOVEWP or self.mousemode == MOUSE_MODE_NONE):
                self.left_button_down = True
                self.selectionbox_start = (selectstartx, selectstartz)

            if self.pikmin_routes is not None:
                hit = False
                all_hit_waypoints = []
                for wp_index, wp_data in self.pikmin_routes.waypoints.items():
                    way_x, y, way_z, radius_actual = wp_data
                    radius = radius_actual*scalex

                    #x, z = (way_x - midx)*scalex, (way_z - midz)*scalez
                    x, z = selectstartx, selectstartz
                    #print("checking", abs(x-mouse_x), abs(z-mouse_z), radius)
                    #if abs(x-mouse_x) < radius and abs(z-mouse_z) < radius:
                    if ((x-way_x)**2 + (z-way_z)**2)**0.5 < radius_actual:
                        all_hit_waypoints.append(wp_index)

                if len(all_hit_waypoints) > 0:
                    wp_index = all_hit_waypoints[self.overlapping_wp_index%len(all_hit_waypoints)]
                    self.selected_waypoints = [wp_index]
                    print("hit")
                    hit = True
                    self.select_update.emit(event)

                    if self.connect_first_wp is not None and self.mousemode == MOUSE_MODE_CONNECTWP:
                        self.connect_update.emit(self.connect_first_wp, wp_index)
                    self.connect_first_wp = wp_index
                    self.move_startpos = [wp_index]
                    self.update()
                    self.overlapping_wp_index = (self.overlapping_wp_index+1)%len(all_hit_waypoints)


                if not hit:
                    self.selected_waypoints = []
                    self.select_update.emit(event)
                    self.connect_first_wp = None
                    self.move_startpos = []
                    self.update()




        if event.buttons() & Qt.MiddleButton and not self.mid_button_down:
            self.mid_button_down = True
            self.drag_last_pos = (event.x(), event.y())

        if event.buttons() & Qt.RightButton:
            self.right_button_down = True

            if self.mousemode == MOUSE_MODE_MOVEWP:
                mouse_x, mouse_z = (event.x(), event.y())
                movetox = mouse_x/scalex + midx
                movetoz = mouse_z/scalez + midz

                if len(self.move_startpos) > 0:
                    sumx,sumz = 0, 0
                    wpcount = len(self.move_startpos)
                    waypoints = self.pikmin_routes.waypoints
                    for wp_index in self.move_startpos:
                        sumx += waypoints[wp_index][0]
                        sumz += waypoints[wp_index][2]

                    x = sumx/float(wpcount)
                    z = sumz/float(wpcount)

                    self.move_points.emit(movetox-x, movetoz-z)

                    #self.move_startpos = (movetox, movetoz)
            elif self.mousemode == MOUSE_MODE_ADDWP:
                mouse_x, mouse_z = (event.x(), event.y())
                destx = mouse_x/scalex + midx
                destz = mouse_z/scalez + midz

                self.create_waypoint.emit(destx, destz)

    @catch_exception
    def mouseMoveEvent(self, event):
        offsetx, offsetz = (-self.origin_x-self.origin_x-self.offset_x,
                            -self.origin_z-self.origin_z-self.offset_z)
        h, w, zf = self.height(), self.width(), self.zoom_factor
        drawstartx = 0+offsetx - (zf-1.0)*(w//2)
        drawstartz = 0+offsetz - (zf-1.0)*(h//2)

        drawendx = drawstartx + w + (zf-1.0)*(w//2)
        drawendz = drawstartz + h + (zf-1.0)*(h//2)

        viewportwidth = drawendx-drawstartx
        viewportheight = drawendz-drawstartz

        midx = (drawendx+drawstartx)/2.0
        midz = (drawendz+drawstartz)/2.0

        scalex = (w/viewportwidth)#/2.0
        scalez = (h/viewportheight)#/2.0

        if self.mid_button_down:
            x, y = event.x(), event.y()
            d_x, d_y  = x - self.drag_last_pos[0], y - self.drag_last_pos[1]


            if self.zoom_factor > 1.0:
                self.offset_x += d_x*(1.0 + (self.zoom_factor-1.0)/2.0)
                self.offset_z += d_y*(1.0 + (self.zoom_factor-1.0)/2.0)
            else:
                self.offset_x += d_x
                self.offset_z += d_y


            self.drag_last_pos = (event.x(), event.y())
            self.update()

        if self.left_button_down:
            # -----------------------
            # Set up values for checking if the mouse hit a node
            offsetx, offsetz = (-self.origin_x-self.origin_x-self.offset_x,
                                -self.origin_z-self.origin_z-self.offset_z)
            h, w, zf = self.height(), self.width(), self.zoom_factor
            drawstartx = 0+offsetx - (zf-1.0)*(w//2)
            drawstartz = 0+offsetz - (zf-1.0)*(h//2)

            drawendx = drawstartx + w + (zf-1.0)*(w//2)
            drawendz = drawstartz + h + (zf-1.0)*(h//2)

            viewportwidth = drawendx-drawstartx
            viewportheight = drawendz-drawstartz

            midx = (drawendx+drawstartx)/2.0
            midz = (drawendz+drawstartz)/2.0

            scalex = (w/viewportwidth)#/2.0
            scalez = (h/viewportheight)#/2.0
            # Set up end
            # -------------

            mouse_x, mouse_z = event.x(), event.y()

            selectendx = mouse_x/scalex + midx
            selectendz = mouse_z/scalez + midz

            selectstartx, selectstartz = self.selectionbox_start
            self.selectionbox_end = (selectendx, selectendz)
            #self.selectionbox_end = (selectendx, selectendz)

            if selectendx <= selectstartx:
                tmp = selectendx
                selectendx = selectstartx
                selectstartx = tmp
            if selectendz <= selectstartz:
                tmp = selectendz
                selectendz = selectstartz
                selectstartz = tmp

            selected = []

            if self.pikmin_routes is not None:
                for wp_index, wp_data in self.pikmin_routes.waypoints.items():
                    way_x, y, way_z, radius = wp_data

                    if (
                                (selectstartx <= way_x <= selectendx and selectstartz <= way_z <= selectendz) or
                                (way_x - radius) <= selectstartx and selectendx <= (way_x+radius) and
                                (way_z - radius) <= selectstartz and selectendz <= (way_z+radius)
                    ):
                        selected.append(wp_index)

            if len(selected) == 0:
                self.move_startpos = []
            else:
                count = float(len(selected))
                self.move_startpos = selected

            self.selected_waypoints = selected
            self.select_update.emit(event)
            self.update()

        if self.right_button_down:
            if self.mousemode == MOUSE_MODE_MOVEWP:
                mouse_x, mouse_z = (event.x(), event.y())
                movetox = mouse_x/scalex + midx
                movetoz = mouse_z/scalez + midz

                if len(self.move_startpos) > 0:
                    sumx,sumz = 0, 0
                    wpcount = len(self.move_startpos)
                    waypoints = self.pikmin_routes.waypoints
                    for wp_index in self.move_startpos:
                        sumx += waypoints[wp_index][0]
                        sumz += waypoints[wp_index][2]

                    x = sumx/float(wpcount)
                    z = sumz/float(wpcount)

                    self.move_points.emit(movetox-x, movetoz-z)

        if True:#self.highlighttriangle is not None:
            mouse_x, mouse_z = (event.x(), event.y())
            mapx = mouse_x/scalex + midx
            mapz = mouse_z/scalez + midz

            if self.collision is not None:
                height = self.collision.collide_ray_downwards(mapx, mapz)

                if height is not None:
                    #self.highlighttriangle = res[1:]
                    #self.update()
                    self.position_update.emit(event, (round(mapx, 2), round(height, 2), round(mapz, 2)))
                else:
                    self.position_update.emit(event, (round(mapx, 2), None, round(mapz,2)))
            else:
                self.position_update.emit(event, (round(mapx, 2), None, round(mapz, 2)))


    @catch_exception
    def mouseReleaseEvent(self, event):
        """if self.left_button_down:
            self.left_button_down = False
            self.last_pos = None
        if self.left_button_down:
            self.left_button_down = False"""
        #print("hm")
        if not event.buttons() & Qt.MiddleButton and self.mid_button_down:
            #print("releasing")
            self.mid_button_down = False
            self.drag_last_pos = None
        if not event.buttons() & Qt.LeftButton and self.left_button_down:
            #print("releasing left")
            self.left_button_down = False
            self.selectionbox_start = self.selectionbox_end = None
            self.update()
        if not event.buttons() & Qt.RightButton and self.right_button_down:
            #print("releasing right")
            self.right_button_down = False
            self.update()
        #self.mouse_released.emit(event)

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
        current = self.zoom_factor

        fac = calc_zoom_out_factor(current)

        self.zoom(fac)

    def zoom_out(self):
        current = self.zoom_factor
        fac = calc_zoom_in_factor(current)

        self.zoom(fac)


class MenuDontClose(QMenu):
    def mouseReleaseEvent(self, e):
        try:
            action = self.activeAction()
            if action and action.isEnabled():
                action.trigger()
            else:
                QMenu.mouseReleaseEvent(self, e)
        except:
            traceback.print_exc()

class ActionWithOwner(QAction):
    triggered_owner = pyqtSignal(object)

    def __init__(self, *args, **kwargs):
        self.action_owner = kwargs["action_owner"]
        del kwargs["action_owner"]

        super().__init__(*args, **kwargs)

        self.triggered.connect(self.triggered_with_owner)

    def triggered_with_owner(self):
        self.triggered_owner.emit(self.action_owner)

class CheckableButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ispushed = False
        self.unpushed_text = None

    def setPushed(self, pushed):

        if pushed is True and self.ispushed is False:
            self.unpushed_text = self.text()
            self.setText("[ {} ]".format(self.unpushed_text))
            self.ispushed = True
        elif self.ispushed is True:
            self.setText(self.unpushed_text)
            self.ispushed = False


