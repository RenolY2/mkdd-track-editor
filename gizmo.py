from OpenGL.GL import *

from lib.model_rendering import Model
from lib.vectors import Vector3, Plane
from widgets.editor_widgets import catch_exception

id_to_meshname = {
    0x1: "gizmo_x",
    0x2: "gizmo_y",
    0x3: "gizmo_z",
    0x4: "rotation_x",
    0x5: "rotation_y",
    0x6: "rotation_z",
    0x7: "middle"
}

AXIS_X = 0
AXIS_Y = 1
AXIS_Z = 2

X_COLOR = (233 / 255, 56 / 255, 79 / 255, 1.0)
Y_COLOR = (130 / 255, 204 / 255, 26 / 255, 1.0)
Z_COLOR = (48 / 255, 132 / 255, 235 / 255, 1.0)
MIDDLE_COLOR = (0.5, 0.5, 0.5, 1.0)
HOVER_COLOR = (248 / 255, 185 / 255, 0 / 255, 1.0)


class Gizmo(Model):
    def __init__(self):
        super().__init__()

        self.position = Vector3(0.0, 0.0, 0.0)
        self.hidden = True

        self.callbacks = {}

        self.was_hit = {}
        self.was_hit_at_all = False
        for meshname in id_to_meshname.values():
            self.was_hit[meshname] = False

        self.render_axis = None

        with open("resources/gizmo_collision.obj", "r") as f:
            self.collision = Model.from_obj(f, rotate=True)

    def set_render_axis(self, axis):
        self.render_axis = axis

    def reset_axis(self):
        self.render_axis = None

    def move_to_average(self, positions):
        if len(positions) == 0:
            self.hidden = True
            return
        self.hidden = False

        avgx = None
        avgy = None
        avgz = None

        for position in positions:
            if avgx is None:
                avgx = position.x
                avgy = position.y
                avgz = position.z
            else:
                avgx += position.x
                avgy += position.y
                avgz += position.z
        self.position.x = avgx / len(positions)
        self.position.y = avgy / len(positions)
        self.position.z = avgz / len(positions)
        #print("New position is", self.position, len(objects))

    def render_collision_check(self, scale, is3d=True):
        if not self.hidden:
            glClear(GL_DEPTH_BUFFER_BIT)
            glPushMatrix()
            glTranslatef(self.position.x, -self.position.z, self.position.y)
            glScalef(scale, scale, scale)

            named_meshes = self.named_meshes if is3d else self.collision.named_meshes

            named_meshes["gizmo_x"].render_colorid(0x1)
            if is3d: named_meshes["gizmo_y"].render_colorid(0x2)
            named_meshes["gizmo_z"].render_colorid(0x3)
            if is3d: named_meshes["rotation_x"].render_colorid(0x4)
            named_meshes["rotation_y"].render_colorid(0x5)
            if is3d: named_meshes["rotation_z"].render_colorid(0x6)
            if not is3d: named_meshes["middle"].render_colorid(0x7)
            glPopMatrix()

    def register_callback(self, gizmopart, func):
        assert gizmopart in self.named_meshes

        self.callbacks[gizmopart] = func

    @catch_exception
    def run_callback(self, hit_id):
        if hit_id not in id_to_meshname: return
        meshname = id_to_meshname[hit_id]
        #print("was hit", meshname)
        #assert meshname in self.was_hit
        #assert all(x is False for x in self.was_hit.values())
        self.was_hit[meshname] = True
        self.was_hit_at_all = True
        #if meshname in self.callbacks:
        #    self.callbacks[meshname]()

    def reset_hit_status(self):
        for key in self.was_hit:
            self.was_hit[key] = False
        self.was_hit_at_all = False

    def _draw_line(self, v1, v2):
        glBegin(GL_LINES)  # Bottom, z1
        glVertex3f(v1.x, v1.y, v1.z)
        glVertex3f(v2.x, v2.y, v2.z)
        glEnd()

    @catch_exception
    def render(self, is3d=True, hover_id=0xFF):
        if self.hidden:
            return

        handle_hit = any(self.was_hit.values())

        if not handle_hit or self.was_hit["gizmo_x"]:
            glColor4f(*X_COLOR if hover_id != 0x1 else HOVER_COLOR)
            self.named_meshes["gizmo_x"].render()
        if is3d and (not handle_hit or self.was_hit["gizmo_y"]):
            glColor4f(*Y_COLOR if hover_id != 0x2 else HOVER_COLOR)
            self.named_meshes["gizmo_y"].render()
        if not handle_hit or self.was_hit["gizmo_z"]:
            glColor4f(*Z_COLOR if hover_id != 0x3 else HOVER_COLOR)
            self.named_meshes["gizmo_z"].render()

        if is3d and (not handle_hit or self.was_hit["rotation_x"]):
            glColor4f(*X_COLOR if hover_id != 0x4 else HOVER_COLOR)
            self.named_meshes["rotation_x"].render()
        if not handle_hit or self.was_hit["rotation_y"]:
            glColor4f(*Y_COLOR if hover_id != 0x5 else HOVER_COLOR)
            self.named_meshes["rotation_y"].render()
        if is3d and (not handle_hit or self.was_hit["rotation_z"]):
            glColor4f(*Z_COLOR if hover_id != 0x6 else HOVER_COLOR)
            self.named_meshes["rotation_z"].render()

        if not is3d and (not handle_hit or self.was_hit["middle"]):
            glColor4f(*MIDDLE_COLOR if hover_id != 0x7 else HOVER_COLOR)
            self.named_meshes["middle"].render()

    def render_scaled(self, scale, is3d=True, hover_id=0xFF):
        glPushMatrix()
        glTranslatef(self.position.x, -self.position.z, self.position.y)

        glLineWidth(2)
        if self.render_axis == AXIS_X:
            glColor4f(*X_COLOR)
            self._draw_line(Vector3(-99999, 0, 0), Vector3(99999, 0, 0))
        elif self.render_axis == AXIS_Y:
            glColor4f(*Y_COLOR)
            self._draw_line(Vector3(0, 0, -99999), Vector3(0, 0, 99999))
        elif self.render_axis == AXIS_Z:
            glColor4f(*Z_COLOR)
            self._draw_line(Vector3(0, -99999, 0), Vector3(0, 99999, 0))
        glLineWidth(1)

        glClear(GL_DEPTH_BUFFER_BIT)
        glScalef(scale, scale, scale)
        if not self.hidden:
            self.render(is3d, hover_id=hover_id)


        glPopMatrix()

