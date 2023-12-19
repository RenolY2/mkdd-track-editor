import os
import json
from OpenGL.GL import *
from .model_rendering import (GenericObject, Model, TexturedModel, Cube, Cylinder)

from .vectors import Vector3, rotation_matrix_with_up_dir

with open("lib/color_coding.json", "r") as f:
    colors = json.load(f)


class ObjectModels(object):
    def __init__(self):
        self.models = {}
        self.generic = GenericObject()
        self.cylinder = Cylinder()
        self.checkpointleft = Cylinder(colors["CheckpointLeft"])
        self.checkpointright = Cylinder(colors["CheckpointRight"])
        self.objectroute = Cylinder(colors["ObjectRoutes"])
        self.cameraroute = Cylinder(colors["CameraRoutes"])
        self.unassignedroute = Cylinder(colors["UnassignedRoutes"])
        self.sharedroute = Cylinder(colors["SharedRoutes"])
        self.enemypoint = Cylinder(colors["EnemyPaths"])
        self.camera = GenericObject(colors["Camera"])
        self.areas = GenericObject(colors["Areas"])
        self.objects = GenericObject(colors["Objects"])
        self.respawn = GenericObject(colors["Respawn"])
        self.startpoints = GenericObject(colors["StartPoints"])
        self.minimap = Cylinder(colors["Minimap"])
        #self.purplecube = Cube((0.7, 0.7, 1.0, 1.0))

        PLAYER_COLORS = (
            (1.0, 0.0, 0.0, 1.0),
            (0.0, 0.0, 1.0, 1.0),
            (1.0, 1.0, 0.0, 1.0),
            (0.0, 1.0, 1.0, 1.0),
            (1.0, 0.0, 1.0, 1.0),
            (1.0, 0.5, 0.0, 1.0),
            (0.0, 0.5, 1.0, 1.0),
            (1.0, 0.0, 0.5, 1.0),
        )
        self.playercolors = [GenericObject(color) for color in PLAYER_COLORS]
        self.playercolors_cylinder = [Cylinder(color) for color in PLAYER_COLORS]
        self.playercolors_cylinder_smaller = [
            Cylinder(color, scale=(0.5, 0.5, 2.0)) for color in PLAYER_COLORS
        ]

        with open("resources/unitsphere.obj", "r") as f:
            self.sphere = Model.from_obj(f, rotate=True)

        with open("resources/unitspheresolid.obj", "r") as f:
            self.sphere_solid = Model.from_obj(f, rotate=True)

        with open("resources/unitcylinder.obj", "r") as f:
            self.unitcylinder = Model.from_obj(f, rotate=True)

        with open("resources/unitcube_wireframe.obj", "r") as f:
            self.wireframe_cube = Model.from_obj(f, rotate=True)

        with open("resources/arrow_head.obj", "r") as f:
            self.arrow_head = Model.from_obj(f, rotate=True, scale=3.0)

    def init_gl(self):
        for dirpath, dirs, files in os.walk("resources/objectmodels"):
            for file in files:
                if file.endswith(".obj"):
                    filename = os.path.basename(file)
                    objectname = filename.rsplit(".", 1)[0]
                    self.models[objectname] = TexturedModel.from_obj_path(os.path.join(dirpath, file), rotate=True)
        for model in (self.cylinder, self.checkpointleft, self.checkpointright, self.objectroute,
                      self.cameraroute, self.unassignedroute, self.sharedroute, self.enemypoint,
                      self.objects, self.areas, self.respawn, self.startpoints, self.camera,
                      self.minimap):
            model.generate_displists()

        for model in self.playercolors:
            model.generate_displists()
        for model in self.playercolors_cylinder:
            model.generate_displists()
        for model in self.playercolors_cylinder_smaller:
            model.generate_displists()

        self.generic.generate_displists()

    def draw_arrow_head(self, frompos, topos, up_dir, scale):
        # Convert to GL base.
        frompos = Vector3(frompos.x, -frompos.z, frompos.y)
        topos = Vector3(topos.x, -topos.z, topos.y)
        up_dir = Vector3(up_dir.x, -up_dir.z, up_dir.y)

        glPushMatrix()

        glTranslatef(topos.x, topos.y, topos.z)

        direction = topos - frompos
        if not direction.is_zero() and not up_dir.is_zero():
            matrix = rotation_matrix_with_up_dir(Vector3(-1, 0, 0), direction, up_dir)
            glMultMatrixf(matrix.flatten())

        glScale(scale, scale, scale)

        self.arrow_head.render()

        glPopMatrix()

    def draw_sphere(self, position, scale, solid=False):
        glPushMatrix()

        glTranslatef(position.x, -position.z, position.y)
        glScalef(scale, scale, scale)

        if solid:
            self.sphere_solid.render()
        else:
            self.sphere.render()
        glPopMatrix()

    def draw_sphere_last_position(self, scale):
        glPushMatrix()

        glScalef(scale, scale, scale)

        self.sphere.render()
        glPopMatrix()

    def draw_cylinder(self,position, radius, height):
        glPushMatrix()

        glTranslatef(position.x, -position.z, position.y)
        glScalef(radius, height, radius)

        self.unitcylinder.render()
        glPopMatrix()

    def draw_wireframe_cube(self, position, rotation, scale):
        glPushMatrix()
        glTranslatef(position.x, -position.z, position.y)
        mtx = rotation.mtx
        glMultMatrixf(mtx)
        glTranslatef(0, 0, scale.y / 2)
        glScalef(-scale.z, scale.x, scale.y)
        self.wireframe_cube.render()
        glPopMatrix()

    def draw_wireframe_cylinder(self, position, rotation, scale):
        glPushMatrix()
        glTranslatef(position.x, -position.z, position.y)
        mtx = rotation.mtx
        glMultMatrixf(mtx)
        glTranslatef(0.0, 0.0, scale.y / 2.0)
        glScalef(-scale.z, scale.x, scale.y)
        self.unitcylinder.render()
        glPopMatrix()

    def draw_cylinder_last_position(self, radius, height):
        glPushMatrix()

        glScalef(radius, radius, height)

        self.unitcylinder.render()
        glPopMatrix()

    def render_generic_position(self, position, selected):
        self._render_generic_position(self.cylinder, position, selected)

    def render_generic_position_colored(self, position, selected, cubename):
        self._render_generic_position(getattr(self, cubename), position, selected)

    def render_player_position_colored(self, position, selected, player):
        self._render_generic_position(self.playercolors_cylinder[player], position, selected)

    def render_player_position_colored_smaller(self, position, selected, player):
        self._render_generic_position(self.playercolors_cylinder_smaller[player], position, selected)

    def render_generic_position_rotation(self, position, rotation, selected):
        self._render_generic_position_rotation("generic", position, rotation, selected)

    def render_generic_position_rotation_colored(self, objecttype, position, rotation, selected):
        self._render_generic_position_rotation(objecttype, position, rotation, selected)

    def _render_generic_position_rotation(self, name, position, rotation, selected):
        glPushMatrix()
        glTranslatef(position.x, -position.z, position.y)
        mtx = rotation.mtx
        #glBegin(GL_LINES)
        #glVertex3f(0.0, 0.0, 0.0)
        #glVertex3f(mtx[0][0] * 2000, mtx[0][1] * 2000, mtx[0][2] * 2000)
        #glEnd()

        glMultMatrixf(mtx)

        glColor3f(0.0, 0.0, 0.0)
        glBegin(GL_LINE_STRIP)
        glVertex3f(0.0, 0.0, 750.0)
        glVertex3f(0.0, 0.0, 0.0)
        glVertex3f(1000.0, 0.0, 0.0)
        glEnd()


        #glMultMatrixf(rotation.mtx[])
        getattr(self, name).render(selected=selected)

        glPopMatrix()

    def _render_generic_position(self, cube, position, selected):
        glPushMatrix()
        glTranslatef(position.x, -position.z, position.y)
        cube.render(selected=selected)

        glPopMatrix()

    def render_generic_position_colored_id(self, position, id):
        glPushMatrix()
        glTranslatef(position.x, -position.z, position.y)
        self.cylinder.render_coloredid(id)

        glPopMatrix()

    def render_generic_position_rotation_colored_id(self, position, rotation, id):
        glPushMatrix()
        glTranslatef(position.x, -position.z, position.y)
        mtx = rotation.mtx
        glMultMatrixf(mtx)
        self.generic.render_coloredid(id)

        glPopMatrix()

    def render_line(self, pos1, pos2):
        pass
