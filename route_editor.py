# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'bw_gui_prototype.ui'
#
# Created by: PyQt5 UI code generator 5.5.1
#
# WARNING! All changes made in this file will be lost!

import traceback

import itertools
import gzip
from copy import copy, deepcopy
import os
from os import path
from timeit import default_timer


from PyQt5.QtCore import Qt, QSize, QRect, QMetaObject, QCoreApplication, QPoint
from PyQt5.QtWidgets import (QWidget, QMainWindow, QFileDialog,
                             QSpacerItem, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QHBoxLayout,
                             QScrollArea, QGridLayout, QMenuBar, QMenu, QAction, QApplication, QStatusBar, QLineEdit)

import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as QtCore

from libpiktxt import RouteTxt
from lib.rarc import Archive

import custom_widgets
from custom_widgets import (MapViewer,
                            catch_exception, CheckableButton)

from opengltext import TempRenderWindow

from py_obj import read_obj, PikminCollision
from configuration import read_config, make_default_config, save_cfg

PIKMIN2PATHS = "Carrying path files (route.txt;*.txt)"


class EditorMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setupUi(self)
        self.retranslateUi(self)

        self.pikmin_routes = RouteTxt()
        self.pikminroutes_screen.pikmin_routes = self.pikmin_routes
        self.collision = None
        self.current_coordinates = None

        self.button_delete_waypoints.pressed.connect(self.action_button_delete_wp)
        self.button_ground_waypoints.pressed.connect(self.action_button_ground_wp)
        self.button_move_waypoints.pressed.connect(self.action_button_move_wp)
        self.button_add_waypoint.pressed.connect(self.action_button_add_wp)
        self.button_connect_waypoints.pressed.connect(self.action_button_connect_wp)

        self.pikminroutes_screen.customContextMenuRequested.connect(self.mapview_showcontextmenu)

        QtWidgets.QShortcut(Qt.Key_M, self).activated.connect(self.action_button_move_wp)
        QtWidgets.QShortcut(Qt.Key_G, self).activated.connect(self.action_button_ground_wp)
        QtWidgets.QShortcut(Qt.CTRL + Qt.Key_A, self).activated.connect(self.action_button_add_wp)
        QtWidgets.QShortcut(Qt.Key_C, self).activated.connect(self.action_button_connect_wp)
        QtWidgets.QShortcut(Qt.Key_Delete, self).activated.connect(self.action_button_delete_wp)

        self.button_delete_waypoints.setToolTip("Shortcut: Delete")
        self.button_move_waypoints.setToolTip("Shortcut: M")
        self.button_ground_waypoints.setToolTip("Shortcut: G")
        self.button_add_waypoint.setToolTip("Shortcut: Ctrl+A")
        self.button_connect_waypoints.setToolTip("Shortcut: C")

        self.lineedit_xcoordinate.editingFinished.connect(self.action_lineedit_change_x)
        self.lineedit_ycoordinate.editingFinished.connect(self.action_lineedit_change_y)
        self.lineedit_zcoordinate.editingFinished.connect(self.action_lineedit_change_z)
        self.lineedit_radius.editingFinished.connect(self.action_lineedit_change_radius)

        self.pikminroutes_screen.connect_update.connect(self.action_connect_waypoints)
        self.pikminroutes_screen.move_points.connect(self.action_move_waypoints)
        self.pikminroutes_screen.create_waypoint.connect(self.action_create_waypoint)
        self.disable_lineedits()
        self.last_render = None
        self.current_route_path = None

        try:
            self.configuration = read_config()
            print("config loaded")
        except FileNotFoundError as e:
            print(e)
            print("creating file...")
            self.configuration = make_default_config()
        #self.ground_wp_when_moving = self.configuration["ROUTES EDITOR"].getboolean("groundwaypointswhenmoving")

        self.pathsconfig = self.configuration["default paths"]
        self.editorconfig = self.configuration["routes editor"]
        self.pikminroutes_screen.editorconfig = self.editorconfig

        print("We are now ready!")

    def reset(self):
        self.current_position = None
        self.resetting = True
        self.statusbar.clearMessage()
        self.dragged_time = None
        self.moving = False
        self.dragging = False
        self.last_x = None
        self.last_y = None
        self.dragged_time = None

        self.moving = False
        self.pikminroutes_screen.reset(keep_collision=True)
        self.current_route_path = None


        self.resetting = False
        self.button_delete_waypoints.setDisabled(False)
        self.button_add_waypoint.setPushed(False)
        self.button_connect_waypoints.setPushed(False)
        self.button_move_waypoints.setPushed(False)
        self.disable_lineedits()

        print("reset done")

    def button_load_level(self):
        try:
            print("ok", self.pathsconfig["routes"])

            filepath, choosentype = QFileDialog.getOpenFileName(
                self, "Open File",
                self.pathsconfig["routes"],
                PIKMIN2PATHS+";;All files (*)")
            print("doooone")
            if filepath:
                print("resetting")
                self.reset()
                print("done")
                print("chosen type:",choosentype)

                with open(filepath, "r") as f:
                    try:
                        pikmin_routes = RouteTxt()
                        pikmin_routes.from_file(f)
                        self.setup_routes(pikmin_routes, filepath)

                    except Exception as error:
                        print("error", error)
                        traceback.print_exc()

        except Exception as er:
            print("errrorrr", er)
            traceback.print_exc()
        print("loaded")

    def setup_routes(self, pikmin_routes, filepath):
        self.pikmin_routes = pikmin_routes
        self.pikminroutes_screen.pikmin_routes = self.pikmin_routes
        self.pikminroutes_screen.update()

        print("ok")
        # self.bw_map_screen.update()
        path_parts = path.split(filepath)
        self.setWindowTitle("Routes Editor - {0}".format(filepath))
        self.pathsconfig["routes"] = filepath
        self.current_route_path = filepath
        save_cfg(self.configuration)

    def button_save_level(self):
        try:
            print("ok", self.pathsconfig["routes"])


            if self.current_route_path is not None:
                filepath = self.current_route_path
                with open(filepath, "w") as f:
                    self.pikmin_routes.write(f)
                self.pathsconfig["routes"] = filepath
                save_cfg(self.configuration)
            else:
                self.button_save_as_level()
        except Exception as err:
            traceback.print_exc()

    def button_save_as_level(self):
        try:
            filepath, choosentype = QFileDialog.getSaveFileName(
                self, "Save File",
                self.pathsconfig["routes"],
                PIKMIN2PATHS+";;All files (*)")

            if filepath:
                with open(filepath, "w") as f:
                    self.pikmin_routes.write(f)
                self.pathsconfig["routes"] = filepath
                self.current_route_path = filepath
                save_cfg(self.configuration)

        except Exception as err:
            traceback.print_exc()

    def button_load_collision(self):
        try:
            filepath, choosentype = QFileDialog.getOpenFileName(
                self, "Open File",
                self.pathsconfig["collision"],
                "Collision (*.obj);;All files (*)")
            with open(filepath, "r") as f:
                verts, faces, normals = read_obj(f)

            self.setup_collision(verts, faces, filepath)
        except:
            traceback.print_exc()

    def button_load_collision_grid(self):
        try:
            filepath, choosentype = QFileDialog.getOpenFileName(
                self, "Open File",
                self.pathsconfig["collision"],
                "Archived grid.bin (*.arc, *.szs);;Grid.bin (*.bin);;All files (*)")
            print(choosentype)

            if choosentype == "Archived grid.bin (texts.arc, texts.szs)" or filepath.endswith(".szs") or filepath.endswith(".arc"):
                load_from_arc = True
            else:
                load_from_arc = False

            with open(filepath, "rb") as f:
                if load_from_arc:
                    archive = Archive.from_file(f)
                    f = archive["text/grid.bin"]
                collision = PikminCollision(f)


            verts = collision.vertices
            faces = [face[0] for face in collision.faces]
            self.setup_collision(verts, faces, filepath)

        except:
            traceback.print_exc()

    def setup_collision(self, verts, faces, filepath):
        width = int(self.configuration["model render"]["Width"])
        height = int(self.configuration["model render"]["Height"])
        print(width, height)

        tmprenderwindow = TempRenderWindow(verts, faces, render_res=(width, height))
        tmprenderwindow.show()

        framebuffer = tmprenderwindow.widget.grabFramebuffer()
        framebuffer.save("tmp_image.png", "PNG")
        self.pikminroutes_screen.level_image = framebuffer

        tmprenderwindow.destroy()

        self.pikminroutes_screen.set_collision(verts, faces)
        self.pathsconfig["routes"] = filepath
        save_cfg(self.configuration)

    @catch_exception
    def event_update_lineedit(self, event):
        selected_count = len(self.pikminroutes_screen.selected_waypoints)
        if selected_count == 1:
            for waypoint in self.pikminroutes_screen.selected_waypoints:
                x, y, z, radius = self.pikmin_routes.waypoints[waypoint]

                self.set_wp_lineedit_coordinates(x, y, z, radius)
                self.enable_lineedits()
                #self.lineedit_xcoordinate
        elif selected_count == 0 or selected_count > 1:
            self.lineedit_xcoordinate.setText("")
            self.lineedit_ycoordinate.setText("")
            self.lineedit_zcoordinate.setText("")
            self.lineedit_radius.setText("")
            self.disable_lineedits()

    def disable_lineedits(self):
        self.lineedit_xcoordinate.setDisabled(True)
        self.lineedit_ycoordinate.setDisabled(True)
        self.lineedit_zcoordinate.setDisabled(True)
        self.lineedit_radius.setDisabled(True)

    def enable_lineedits(self):
        self.lineedit_xcoordinate.setDisabled(False)
        self.lineedit_ycoordinate.setDisabled(False)
        self.lineedit_zcoordinate.setDisabled(False)
        self.lineedit_radius.setDisabled(False)

    def event_update_position(self, event, position):
        x,y,z = position
        self.current_coordinates = position
        if y is None:
            y = "-"
        coordtext = "X: {}, Y: {}, Z: {}".format(x,y,z)
        self.statusbar.showMessage(coordtext)
        #print(coordtext)

    @catch_exception
    def action_button_delete_wp(self):
        if self.pikmin_routes is not None and self.button_delete_waypoints.isEnabled():
            print("removing", self.pikminroutes_screen.selected_waypoints)
            for wp in self.pikminroutes_screen.selected_waypoints:
                self.pikmin_routes.remove_waypoint(wp)
            self.pikminroutes_screen.selected_waypoints = {}

            self.pikminroutes_screen.update()

    def action_button_ground_wp(self):
        if self.pikmin_routes is not None and self.pikminroutes_screen.collision is not None:
            for wp in self.pikminroutes_screen.selected_waypoints:
                x, y, z, radius = self.pikmin_routes.waypoints[wp]

                height = self.pikminroutes_screen.collision.collide_ray_downwards(x, z)

                if height is not None:
                    self.pikmin_routes.waypoints[wp][1] = height
                self.set_wp_lineedit_coordinates(x,height,z,radius)
            self.pikminroutes_screen.update()

    def action_button_move_wp(self):
        if self.button_move_waypoints.ispushed:

            self.button_move_waypoints.setPushed(False)
            self.pikminroutes_screen.set_mouse_mode(custom_widgets.MOUSE_MODE_NONE)
            self.button_delete_waypoints.setDisabled(False)
        else:
            self.button_add_waypoint.setPushed(False)
            self.button_move_waypoints.setPushed(True)
            self.button_connect_waypoints.setPushed(False)
            self.pikminroutes_screen.set_mouse_mode(custom_widgets.MOUSE_MODE_MOVEWP)
            self.button_delete_waypoints.setDisabled(False)

    def action_button_add_wp(self):
        if self.button_add_waypoint.ispushed:

            self.button_add_waypoint.setPushed(False)
            self.pikminroutes_screen.set_mouse_mode(custom_widgets.MOUSE_MODE_NONE)
            self.button_delete_waypoints.setDisabled(False)
        else:
            self.button_add_waypoint.setPushed(True)
            self.button_move_waypoints.setPushed(False)
            self.button_connect_waypoints.setPushed(False)
            self.pikminroutes_screen.set_mouse_mode(custom_widgets.MOUSE_MODE_ADDWP)
            self.button_delete_waypoints.setDisabled(True)

    def action_button_connect_wp(self):
        if self.button_connect_waypoints.ispushed:

            self.button_connect_waypoints.setPushed(False)
            self.pikminroutes_screen.set_mouse_mode(custom_widgets.MOUSE_MODE_NONE)
            self.button_delete_waypoints.setDisabled(False)
        else:
            self.button_add_waypoint.setPushed(False)
            self.button_move_waypoints.setPushed(False)
            self.button_connect_waypoints.setPushed(True)
            self.pikminroutes_screen.set_mouse_mode(custom_widgets.MOUSE_MODE_CONNECTWP)
            self.button_delete_waypoints.setDisabled(True)

    def action_lineedit_change_x(self):
        try:
            value = float(self.lineedit_xcoordinate.text())
        except Exception as e:
            print(e)
        else:
            if len(self.pikminroutes_screen.selected_waypoints) == 1:
                for wp in self.pikminroutes_screen.selected_waypoints:
                    self.pikmin_routes.waypoints[wp][0] = value
                self.pikminroutes_screen.update()

    def action_lineedit_change_y(self):
        try:
            value = float(self.lineedit_ycoordinate.text())
        except Exception as e:
            print(e)
        else:
            if len(self.pikminroutes_screen.selected_waypoints) == 1:
                for wp in self.pikminroutes_screen.selected_waypoints:
                    self.pikmin_routes.waypoints[wp][1] = value
                self.pikminroutes_screen.update()

    def action_lineedit_change_z(self):
        try:
            value = float(self.lineedit_zcoordinate.text())
        except Exception as e:
            print(e)
        else:
            if len(self.pikminroutes_screen.selected_waypoints) == 1:
                for wp in self.pikminroutes_screen.selected_waypoints:
                    self.pikmin_routes.waypoints[wp][2] = value
                self.pikminroutes_screen.update()

    def action_lineedit_change_radius(self):
        try:
            value = float(self.lineedit_radius.text())
        except Exception as e:
            print(e)
        else:
            if len(self.pikminroutes_screen.selected_waypoints) == 1:
                for wp in self.pikminroutes_screen.selected_waypoints:
                    self.pikmin_routes.waypoints[wp][3] = value
                self.pikminroutes_screen.update()

    @catch_exception
    def action_connect_waypoints(self, firstwp, secondwp):
        if self.pikmin_routes is not None:
            if firstwp in self.pikmin_routes.links:
                if secondwp in self.pikmin_routes.links[firstwp]:
                    self.pikmin_routes.remove_link(firstwp, secondwp)
                else:
                    self.pikmin_routes.add_link(firstwp, secondwp)
            else:
                self.pikmin_routes.add_link(firstwp, secondwp)
            self.pikminroutes_screen.update()

    @catch_exception
    def action_move_waypoints(self, deltax, deltaz):
        if self.pikmin_routes is not None:
            for wp in self.pikminroutes_screen.selected_waypoints:
                self.pikmin_routes.waypoints[wp][0] += deltax
                self.pikmin_routes.waypoints[wp][2] += deltaz

            if len(self.pikminroutes_screen.selected_waypoints) == 1:
                do_ground = self.editorconfig.getboolean("GroundWaypointsWhenMoving")
                for wp in self.pikminroutes_screen.selected_waypoints:
                    x,y,z,radius = self.pikmin_routes.waypoints[wp]
                    if do_ground is True and self.pikminroutes_screen.collision is not None:
                        height = self.pikminroutes_screen.collision.collide_ray_downwards(x, z)
                        if height is not None:
                            y = height
                            self.pikmin_routes.waypoints[wp][1] = y
                    self.set_wp_lineedit_coordinates(x, y, z, radius)

            self.pikminroutes_screen.update()

    def set_wp_lineedit_coordinates(self, x, y, z, radius):
        self.lineedit_xcoordinate.setText(str(round(x, 6)))
        self.lineedit_ycoordinate.setText(str(round(y, 6)))
        self.lineedit_zcoordinate.setText(str(round(z, 6)))
        self.lineedit_radius.setText(str(round(radius, 6)))

    @catch_exception
    def action_create_waypoint(self, x, z):
        if self.pikminroutes_screen.collision is None:
            y = 100
        else:
            height = self.pikminroutes_screen.collision.collide_ray_downwards(x, z)
            print("hmm, shot a ray downwards at", x, z)
            print("we got", height)
            if height is None:
                y = 100
            else:
                y = height
        radius = float(self.editorconfig["defaultradius"])
        self.pikmin_routes.add_waypoint(x, y, z, radius)
        self.pikminroutes_screen.update()
        print("created")

    @catch_exception
    def mapview_showcontextmenu(self, position):
        context_menu = QMenu(self)
        action = QAction("Copy Coordinates", self)
        action.triggered.connect(self.action_copy_coords_to_clipboard)
        context_menu.addAction(action)
        context_menu.exec(self.mapToGlobal(position))
        context_menu.destroy()

    def action_copy_coords_to_clipboard(self):
        if self.current_coordinates is not None:
            QApplication.clipboard().setText(", ".join(str(x) for x in self.current_coordinates))

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1200, 850)
        MainWindow.setMinimumSize(QSize(930, 850))
        MainWindow.setWindowTitle("Pikmin 2 Routes Editor")

        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        MainWindow.setCentralWidget(self.centralwidget)

        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName("horizontalLayout")

        self.pikminroutes_screen = MapViewer(self.centralwidget)
        self.pikminroutes_screen.position_update.connect(self.event_update_position)
        self.pikminroutes_screen.select_update.connect(self.event_update_lineedit)
        self.horizontalLayout.addWidget(self.pikminroutes_screen)

        spacerItem = QSpacerItem(10, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.horizontalLayout.addItem(spacerItem)

        self.vertLayoutWidget = QWidget(self.centralwidget)
        self.vertLayoutWidget.setMaximumSize(QSize(250, 1200))
        self.verticalLayout = QVBoxLayout(self.vertLayoutWidget)
        self.verticalLayout.setObjectName("verticalLayout")

        self.button_add_waypoint = CheckableButton(self.centralwidget)
        self.button_delete_waypoints = QPushButton(self.centralwidget)
        self.button_ground_waypoints = QPushButton(self.centralwidget)
        self.button_move_waypoints = CheckableButton(self.centralwidget)
        self.button_connect_waypoints = CheckableButton(self.centralwidget)

        self.lineedit_xcoordinate = QLineEdit(self.centralwidget)
        self.lineedit_ycoordinate = QLineEdit(self.centralwidget)
        self.lineedit_zcoordinate = QLineEdit(self.centralwidget)
        self.lineedit_radius = QLineEdit(self.centralwidget)


        self.verticalLayout.addWidget(self.button_add_waypoint)
        self.verticalLayout.addWidget(self.button_delete_waypoints)
        self.verticalLayout.addWidget(self.button_ground_waypoints)
        self.verticalLayout.addWidget(self.button_move_waypoints)
        self.verticalLayout.addWidget(self.button_connect_waypoints)

        self.verticalLayout.addWidget(self.lineedit_xcoordinate)
        self.verticalLayout.addWidget(self.lineedit_ycoordinate)
        self.verticalLayout.addWidget(self.lineedit_zcoordinate)
        self.verticalLayout.addWidget(self.lineedit_radius)

        spacerItem1 = QSpacerItem(10, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.verticalLayout.addItem(spacerItem1)

        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")


        self.label_waypoint_info = QLabel(self.centralwidget)
        self.label_waypoint_info.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)


        self.verticalLayout_2.addWidget(self.label_waypoint_info)


        self.verticalLayout.addLayout(self.verticalLayout_2)

        self.horizontalLayout.addWidget(self.vertLayoutWidget)

        self.menubar = QMenuBar(MainWindow)
        self.menubar.setGeometry(QRect(0, 0, 820, 29))
        self.menubar.setObjectName("menubar")
        self.file_menu = QMenu(self.menubar)
        self.file_menu.setObjectName("menuLoad")

        # ------
        # File menu buttons
        self.file_load_action = QAction("Load", self)
        self.file_load_action.setShortcut("Ctrl+O")
        self.file_load_action.triggered.connect(self.button_load_level)
        self.file_menu.addAction(self.file_load_action)
        self.file_save_action = QAction("Save", self)
        self.file_save_action.setShortcut("Ctrl+S")
        self.file_save_action.triggered.connect(self.button_save_level)
        self.file_menu.addAction(self.file_save_action)
        self.file_save_as_action = QAction("Save As", self)
        self.file_save_as_action.setShortcut("Ctrl+Alt+S")
        self.file_save_as_action.triggered.connect(self.button_save_as_level)
        self.file_menu.addAction(self.file_save_as_action)


        # ------ Collision Menu
        self.collision_menu = QMenu(self.menubar)
        self.collision_menu.setObjectName("menuCollision")
        self.collision_load_action = QAction("Load .OBJ", self)
        self.collision_load_action.triggered.connect(self.button_load_collision)
        self.collision_menu.addAction(self.collision_load_action)
        self.collision_load_grid_action = QAction("Load GRID.BIN", self)
        self.collision_load_grid_action.triggered.connect(self.button_load_collision_grid)
        self.collision_menu.addAction(self.collision_load_grid_action)

        # ----- Set up menu bar and add the file menus
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.menubar.addAction(self.file_menu.menuAction())
        self.menubar.addAction(self.collision_menu.menuAction())
        self.retranslateUi(MainWindow)
        QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QCoreApplication.translate
        self.file_menu.setTitle(_translate("MainWindow", "File"))
        self.button_add_waypoint.setText("Add Waypoint")
        self.button_connect_waypoints.setText("Connect Waypoint")
        self.button_delete_waypoints.setText("Delete Waypoint(s)")
        self.button_move_waypoints.setText("Move Waypoint(s)")
        self.button_ground_waypoints.setText("Ground Waypoint(s)")
        self.collision_menu.setTitle("Collision")

if __name__ == "__main__":
    import sys
    import platform
    import argparse
    from PyQt5 import QtGui

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputroute", default=None,
                        help="Path to route file to be loaded.")
    parser.add_argument("--collision", default=None,
                        help="Path to collision to be loaded.")

    args = parser.parse_args()

    app = QApplication(sys.argv)

    if platform.system() == "Windows":
        import ctypes
        myappid = 'P2RoutesEditor'  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    route_gui = EditorMainWindow()
    route_gui.setWindowIcon(QtGui.QIcon('resources/route_editor_icon.ico'))

    if args.inputroute is not None:
        with open(args.inputroute, "r") as f:
            pikmin_routes = RouteTxt()
            pikmin_routes.from_file(f)
            route_gui.setup_routes(pikmin_routes, args.inputroute)

    if args.collision is not None:
        if args.collision.endswith(".bin"):
            with open(args.collision, "rb") as f:
                collision = PikminCollision(f)

            verts = collision.vertices
            faces = [face[0] for face in collision.faces]

        elif args.collision.endswith(".szs") or args.collision.endswith(".arc"):
            with open(args.collision, "rb") as f:
                archive = Archive.from_file(f)
                f = archive["text/grid.bin"]
                collision = PikminCollision(f)

            verts = collision.vertices
            faces = [face[0] for face in collision.faces]

        elif args.collision.endswith(".obj"):
            with open(args.collision, "r") as f:
                verts, faces, normals = read_obj(f)

        else:
            raise RuntimeError("Unknown filetype:", args.collision)

        route_gui.setup_collision(verts, faces, args.collision)

    route_gui.show()
    err_code = app.exec()
    #traceback.print_exc()
    sys.exit(err_code)
