import sys
from math import (
    atan2,
    cos,
    degrees,
    pi,
    sin,
)

from OpenGL.GL import (
    GL_LINE_STRIP,
    glBegin,
    glColor3f,
    glEnd,
    glPopMatrix,
    glPushMatrix,
    glRotatef,
    glTranslatef,
    glVertex3f,
)

if sys.platform == "win32":
    from lib.memorylib import Dolphin
else:
    from lib.memorylib_lin import Dolphin

from lib.vectors import Vector3
from mkdd_widgets import (
    BolMapViewer,
    MODE_TOPDOWN,
)


def angle_diff(angle1, angle2):
    angle1 = (angle1 + 2 * pi) % (2 * pi)
    angle2 = (angle2 + 2 * pi) % (2 * pi)
    if angle1 > angle2:
        angle2 = angle2 + 2 * pi
    return angle2 - angle1


class Game:

    def __init__(self):
        self.dolphin = Dolphin()
        self.kart_count = 0
        self.karts = []
        self.human_karts = [False] * 8
        self.kart_targets = []
        self.kart_headings = []

        for _i in range(8):
            self.karts.append([None, Vector3(0.0, 0.0, 0.0)])
            self.kart_targets.append(Vector3(0.0, 0.0, 0.0))
            self.kart_headings.append(Vector3(0.0, 0.0, 0.0))

        self.stay_focused_on_player = -1

        self.last_angle = 0.0

        self.region = None

    def initialize(self):
        self.stay_focused_on_player = -1
        self.dolphin.reset()

        if not self.dolphin.find_dolphin():
            self.dolphin.reset()
            return "Dolphin not found."

        if not self.dolphin.init():
            self.dolphin.reset()
            return "Dolphin found but game isn't running."

        gameid_buffer = self.dolphin.read_ram(0, 4)
        if gameid_buffer is None:
            self.dolphin.reset()
            return "Game ID cannot be read from memory."

        gameid = bytes(gameid_buffer)
        if gameid in (b"GM4P", b"GM4J"):
            return "PAL/NTSC-J version of MKDD currently isn't supported for Dolphin hooking."
        if gameid != b"GM4E":
            gameid_str = str(gameid, encoding="ascii")
            return f"Game doesn't seem to be MKDD: Found Game ID '{gameid_str}'."

        stringcheck = self.dolphin.read_ram(0x80419020 - 0x80000000, 5)
        if stringcheck == b"title":
            self.region = "US_DEBUG"
        else:
            self.region = "US"

        print("Success! Detected region", self.region)
        return ""

    def render_visual(self, renderer: BolMapViewer, selected):
        for p, (valid, kartpos) in enumerate(self.karts[:self.kart_count]):
            if not valid:
                continue

            glPushMatrix()
            horiz = atan2(self.kart_headings[p].x, self.kart_headings[p].z) - pi / 2.0
            glTranslatef(kartpos.x, -kartpos.z, kartpos.y)
            glRotatef(degrees(horiz), 0.0, 0.0, 1.0)
            renderer.models.playercolors[p].render(valid in selected)
            glPopMatrix()

            if not self.human_karts[p]:
                glBegin(GL_LINE_STRIP)
                glColor3f(0.1, 0.1, 0.1)
                glVertex3f(kartpos.x, -kartpos.z, kartpos.y)
                glVertex3f(self.kart_targets[p].x, -self.kart_targets[p].z, self.kart_targets[p].y)
                glEnd()
                renderer.models.render_player_position_colored(self.kart_targets[p], False, p)

    def render_collision(self, renderer: BolMapViewer, objlist, objselectioncls, selected):
        if not self.dolphin.initialized():
            return

        idbase = 0x100000
        offset = len(objlist)
        for ptr, pos in self.karts[:self.kart_count]:
            if ptr in selected:
                continue
            objlist.append(objselectioncls(obj=ptr, pos1=pos, pos2=None, pos3=None, rotation=None))
            renderer.models.render_generic_position_colored_id(pos, idbase + (offset) * 4)
            offset += 1

    def logic(self, renderer: BolMapViewer, delta, diff):
        if not self.dolphin.initialized():
            return

        if self.region == "US":
            kartctrlPtr = self.dolphin.read_uint32(0x803CC588)
        elif self.region == "US_DEBUG":
            kartctrlPtr = self.dolphin.read_uint32(0x804171a0)

        if kartctrlPtr is None or not self.dolphin.address_valid(kartctrlPtr):
            self.dolphin.reset()
            self.kart_count = 0
            for i in range(8):
                self.karts[i][0] = None
            return

        if self.region == "US":
            self.kart_count = max(0, min(8, self.dolphin.read_uint32(0x803CB6B1) >> 24))
        elif self.region == "US_DEBUG":
            self.kart_count = max(0, min(8, self.dolphin.read_uint32(0x80416271) >> 24))

        # Check whether "Player Karts: Enable Auto Pilot [Ralf]" is on.
        if self.region == "US":
            autopilot = self.dolphin.read_uint32(0x802C60F4) == 0x60000000
        elif self.region == "US_DEBUG":
            autopilot = self.dolphin.read_uint32(0x80306644) == 0x60000000

        for i in range(self.kart_count):
            kartPtr = self.dolphin.read_uint32(kartctrlPtr + 0xA0 + i * 4)
            if not self.dolphin.address_valid(kartPtr):
                continue

            x = self.dolphin.read_float(kartPtr + 0x23C)
            y = self.dolphin.read_float(kartPtr + 0x240)
            z = self.dolphin.read_float(kartPtr + 0x244)
            self.karts[i][0] = kartPtr

            if autopilot:
                human = False
            else:
                # Reduced version of ObjUtility::isPlayerDriver().
                if self.region == "US":
                    human = bool(self.dolphin.read_uint32(0x803B145C + 0x34 + 0x18 * i))
                elif self.region == "US_DEBUG":
                    human = bool(self.dolphin.read_uint32(0x803FBFA8 + 0x34 + 0x18 * i))
            self.human_karts[i] = human

            self.kart_headings[i].x = self.dolphin.read_float(kartPtr + 0x308)
            self.kart_headings[i].y = self.dolphin.read_float(kartPtr + 0x30C)
            self.kart_headings[i].z = self.dolphin.read_float(kartPtr + 0x310)

            # This is equivalent to KartCtrl::getKartEnemy() (NTSC-U).
            karttarget = self.dolphin.read_uint32(kartctrlPtr + 0x180 + i * 4)
            if self.dolphin.address_valid(karttarget):
                # 0x3C offset seen at 0x80235c1c (NTSC-U).
                clpoint = self.dolphin.read_uint32(karttarget + 0x3C)
                if self.dolphin.address_valid(clpoint):
                    vec3ptr = clpoint + 0x28  # 0x28 offset seen at 0x802438fc (NTSC-U).
                    if self.dolphin.address_valid(vec3ptr):
                        self.kart_targets[i].x = self.dolphin.read_float(vec3ptr)
                        self.kart_targets[i].y = self.dolphin.read_float(vec3ptr + 4)
                        self.kart_targets[i].z = self.dolphin.read_float(vec3ptr + 8)

            if self.karts[i][0] not in renderer.selected:
                self.karts[i][1].x = x
                self.karts[i][1].y = y
                self.karts[i][1].z = z
            else:
                self.dolphin.write_float(kartPtr + 0x23C, self.karts[i][1].x)
                self.dolphin.write_float(kartPtr + 0x240, self.karts[i][1].y)
                self.dolphin.write_float(kartPtr + 0x244, self.karts[i][1].z)

        if self.stay_focused_on_player >= 0:
            if renderer.mode == MODE_TOPDOWN:
                renderer.offset_x = -self.karts[self.stay_focused_on_player][1].x
                renderer.offset_z = -self.karts[self.stay_focused_on_player][1].z
            else:
                x = self.kart_headings[self.stay_focused_on_player].x
                z = self.kart_headings[self.stay_focused_on_player].z

                angletmp = atan2(x, z) - pi / 2.0
                diff1 = angle_diff(angletmp, self.last_angle)
                diff2 = angle_diff(self.last_angle, angletmp)
                if diff1 < diff2:
                    diff = -diff1
                else:
                    diff = diff2

                if abs(diff) < 0.001:
                    angle = angletmp
                else:
                    angle = self.last_angle + diff * delta * 3

                self.last_angle = angle

                newx = sin(angle + pi / 2.0)
                newz = cos(angle + pi / 2.0)

                renderer.camera_x = self.karts[self.stay_focused_on_player][1].x - newx * 1000
                renderer.camera_z = -(self.karts[self.stay_focused_on_player][1].z - newz * 1000)
                height = self.karts[self.stay_focused_on_player][1].y
                renderer.camera_height = height + 500
                renderer.camera_horiz = angle

        renderer.do_redraw()
