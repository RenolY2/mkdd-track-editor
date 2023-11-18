import contextlib
import io
import sys
import time

from struct import pack

from math import (
    atan2,
    cos,
    degrees,
    pi,
    sin,
)

from OpenGL.GL import (
    GL_LINE_STIPPLE,
    GL_LINES,
    glBegin,
    glColor3f,
    glDisable,
    glEnable,
    glEnd,
    glLineStipple,
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
        self.item_targets = []
        self.kart_headings = []

        for _i in range(8):
            self.karts.append([None, Vector3(0.0, 0.0, 0.0)])
            self.kart_targets.append(Vector3(0.0, 0.0, 0.0))
            self.item_targets.append(Vector3(0.0, 0.0, 0.0))
            self.kart_headings.append(Vector3(0.0, 0.0, 0.0))

        self.stay_focused_on_player = -1

        self.show_target_enemy_path_points = True
        self.show_target_item_points = True

        self.last_angle = 0.0

        self.region = None

        self.autoconnect = False
        self.last_autoconnect = time.monotonic()

    def reset(self):
        self.dolphin.reset()
        self.kart_count = 0
        for i in range(8):
            self.karts[i][0] = None

    def initialize(self):
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

    def render_visual(self, renderer: BolMapViewer, selected, zf_or_campos):
        topdown = renderer.mode == MODE_TOPDOWN

        for p, (valid, kartpos) in enumerate(self.karts[:self.kart_count]):
            if not valid:
                continue

            glPushMatrix()
            horiz = atan2(self.kart_headings[p].x, self.kart_headings[p].z) - pi / 2.0
            glTranslatef(kartpos.x, -kartpos.z, kartpos.y)
            glRotatef(degrees(horiz), 0.0, 0.0, 1.0)
            renderer.models.playercolors[p].render(valid in selected)
            glPopMatrix()

            if self.show_target_enemy_path_points and not self.human_karts[p]:
                kart_target = self.kart_targets[p]
                glColor3f(0.1, 0.1, 0.1)
                glBegin(GL_LINES)
                glVertex3f(kartpos.x, -kartpos.z, kartpos.y)
                glVertex3f(kart_target.x, -kart_target.z, kart_target.y)
                glEnd()
                distance = (kart_target - kartpos).length()
                direction = (kart_target - kartpos) / distance
                arrowpos = kartpos + direction * max(0, distance - 150)
                if topdown:
                    up_dir = Vector3(0.0, 1.0, 0.0)
                else:
                    up_dir = (arrowpos - zf_or_campos).normalized()
                renderer.models.draw_arrow_head(kartpos, arrowpos, up_dir, 100.0)
                renderer.models.render_player_position_colored(kart_target, False, p)

            if self.show_target_item_points:
                item_target = self.item_targets[p]
                glColor3f(0.2, 0.2, 0.2)
                glEnable(GL_LINE_STIPPLE)
                glLineStipple(1, 0b1111000011110000)
                glBegin(GL_LINES)
                glVertex3f(kartpos.x, -kartpos.z, kartpos.y)
                glVertex3f(item_target.x, -item_target.z, item_target.y)
                glEnd()
                glDisable(GL_LINE_STIPPLE)
                renderer.models.render_player_position_colored_smaller(item_target, False, p)

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
            if self.autoconnect and (time.monotonic() - self.last_autoconnect > 1.0):
                self.last_autoconnect = time.monotonic()

                sink = io.StringIO()
                with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                    self.initialize()

                if not self.dolphin.initialized():
                    return
            else:
                return

        if self.region == "US_DEBUG":
            # Compare address 801bc4c4 in US Debug
            racemgrPtr = self.dolphin.read_uint32(0x8041bf80-0x5BD8)
            coursePtr = self.dolphin.read_uint32(racemgrPtr+0x44)
            courseDataPtr = self.dolphin.read_uint32(coursePtr+0x04DC)
            bolPtr = self.dolphin.read_uint32(courseDataPtr+4)  # This is the pointer to BOL data

            pathpointoffset = bolPtr+self.dolphin.read_uint32(bolPtr+0x50)
            objectsoffset = bolPtr+self.dolphin.read_uint32(bolPtr+0x54)
            startpoints = bolPtr + self.dolphin.read_uint32(bolPtr + 0x58)
            bolareas = bolPtr + self.dolphin.read_uint32(bolPtr + 0x5C)
            cameras = bolPtr + self.dolphin.read_uint32(bolPtr + 0x60)
            respawnpoints = bolPtr + self.dolphin.read_uint32(bolPtr + 0x64)
            lightparams = bolPtr + self.dolphin.read_uint32(bolPtr + 0x68)

            count = (objectsoffset-pathpointoffset)//0x20
            geographyMgrPtr = self.dolphin.read_uint32(0x8041bf80-0x54B0)

            areas = self.dolphin.read_uint32(coursePtr+0x0528)


            renderer.level_file.routes
            pointoffset = 0

            for route in renderer.level_file.routes:
                for i, point in enumerate(route.points):
                    j = i + pointoffset
                    if pathpointoffset+j*0x20 < objectsoffset:
                        self.dolphin.write_float(pathpointoffset+j*0x20, point.position.x)
                        self.dolphin.write_float(pathpointoffset+j*0x20+4, point.position.y)
                        self.dolphin.write_float(pathpointoffset+j*0x20+8, point.position.z)
                    else:
                        print("exceeded route points")


                pointoffset += len(route.points)

            for objoffset in (0x350, 0x380): # , 0x398): 398 is stringbridge but won't move
                next = self.dolphin.read_uint32(geographyMgrPtr+objoffset)
                start = next
                while next != 0:
                    currobj = self.dolphin.read_uint32(next)
                    next = self.dolphin.read_uint32(next+12)
                    """if objoffset == 0x398:
                        print(hex(start), hex(next), hex(currobj), hex(self.dolphin.read_uint32(currobj)))
                        print(hex(self.dolphin.read_uint32(currobj+232)))"""

                    # Trick: Use sobj pointer to calculate index into BOL object data
                    sobj = self.dolphin.read_uint32(currobj+232)
                    if sobj != 0:
                        if (sobj - objectsoffset) % 0x40 == 0:
                            objindex = (sobj - objectsoffset)//0x40
                            objs = renderer.level_file.objects.objects
                            obj = objs[objindex]
                            if obj in renderer.selected:
                                if obj.route is None:
                                    self.dolphin.write_float(currobj+4, obj.position.x)

                                    if obj.objectid in (1, ):
                                        self.dolphin.write_float(currobj + 8, obj.position.y+obj.userdata[0])
                                    else:
                                        self.dolphin.write_float(currobj+8, obj.position.y)
                                    self.dolphin.write_float(currobj+12, obj.position.z)
                                    if obj in renderer.selected:
                                        print(hex(currobj))

                                    f, u, l = obj.rotation.get_vectors()
                                    self.dolphin.write_float(currobj + 0x10, l.x)
                                    self.dolphin.write_float(currobj + 0x10 + 4, u.x)
                                    self.dolphin.write_float(currobj + 0x10 + 8, f.x)

                                    self.dolphin.write_float(currobj + 0x20, l.y)
                                    self.dolphin.write_float(currobj + 0x20 + 4, u.y)
                                    self.dolphin.write_float(currobj + 0x20 + 8, f.y)

                                    self.dolphin.write_float(currobj + 0x30, l.z)
                                    self.dolphin.write_float(currobj + 0x30 + 4, u.z)
                                    self.dolphin.write_float(currobj + 0x30 + 8, f.z)

                                #f, u, l = obj.rotation.get_vectors()
                                self.dolphin.write_ram(sobj-0x80000000+0x30, pack(">hhhhhhhh",
                                                                             *obj.userdata))


                                self.dolphin.write_float(currobj + 0x40, obj.scale.x)
                                self.dolphin.write_float(currobj + 0x40 + 4, obj.scale.y)
                                self.dolphin.write_float(currobj + 0x40 + 8, obj.scale.z)

                        else:
                            print("failed to calc obj index")

                    if next == start:
                        print("hit the start, oops")
                        break

            for i, area in enumerate(renderer.level_file.areas.areas):
                self.dolphin.write_float(areas + i*0x4C+4, area.position.x)
                self.dolphin.write_float(areas + i*0x4C+8, area.position.y)
                self.dolphin.write_float(areas + i*0x4C+12, area.position.z)

                f,u,l = area.rotation.get_vectors()
                self.dolphin.write_float(areas + i * 0x4C + 0x10, f.x)
                self.dolphin.write_float(areas + i * 0x4C + 0x10+4, f.y)
                self.dolphin.write_float(areas + i * 0x4C + 0x10+8, f.z)

                self.dolphin.write_float(areas + i * 0x4C + 0x1C, u.x)
                self.dolphin.write_float(areas + i * 0x4C + 0x1C+4, u.y)
                self.dolphin.write_float(areas + i * 0x4C + 0x1C+8, u.z)

                self.dolphin.write_float(areas + i * 0x4C + 0x28, l.x)
                self.dolphin.write_float(areas + i * 0x4C + 0x28+4, l.y)
                self.dolphin.write_float(areas + i * 0x4C + 0x28+8, l.z)

                self.dolphin.write_float(areas + i * 0x4C + 0x34, area.scale.x*50)
                self.dolphin.write_float(areas + i * 0x4C + 0x38, area.scale.y*100)
                self.dolphin.write_float(areas + i * 0x4C + 0x3C, area.scale.z*50)

            for i, camera in enumerate(renderer.level_file.cameras):
                self.dolphin.write_vector(cameras + i*0x48, camera.position)
                self.dolphin.write_vector(cameras + i*0x48+0x18, camera.position2)
                self.dolphin.write_vector(cameras + i*0x48+0x24, camera.position3)

                f, u, l = camera.rotation.get_vectors()
                self.dolphin.write_ram(cameras + i*0x48+0x8-0x80000000,
                                                                pack(">hhhhhh",
                                                                int(f.x*10000),
                                                                    int(f.y*10000),
                                                                    int(f.z*10000),
                                                                    int(u.x*10000),
                                                                    int(u.y*10000),
                                                                    int(u.z*10000)))

                self.dolphin.write_ushort(cameras + i*0x48+0x30, camera.camtype)
                self.dolphin.write_ushort(cameras + i*0x48+0x32, camera.fov.start)
                self.dolphin.write_ushort(cameras + i*0x48+0x3E, camera.routespeed)
                self.dolphin.write_ushort(cameras + i*0x48+0x40, camera.fov.end)

        if self.region == "US":
            kartctrlPtr = self.dolphin.read_uint32(0x803CC588)
        elif self.region == "US_DEBUG":
            kartctrlPtr = self.dolphin.read_uint32(0x804171a0)
        else:
            kartctrlPtr = None

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
                # Equivalent to KartCheck::CheckAllClearKey().
                checkallclearkey_arg = self.dolphin.read_uint32(kartPtr + 200)
                checkallclearkey_local = self.dolphin.read_uint32(
                    self.dolphin.read_uint32(checkallclearkey_arg) + 0x578)
                cpu_managed = checkallclearkey_local & 4 and checkallclearkey_local & 8
                human = not cpu_managed
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

            itemtarget = self.dolphin.read_uint32(kartctrlPtr + 0x1C0 + i * 4)
            if self.dolphin.address_valid(itemtarget):
                clpoint = self.dolphin.read_uint32(itemtarget)
                if self.dolphin.address_valid(clpoint):
                    vec3ptr = self.dolphin.read_uint32(clpoint + 4)
                    if self.dolphin.address_valid(vec3ptr):
                        self.item_targets[i].x = self.dolphin.read_float(vec3ptr)
                        self.item_targets[i].y = self.dolphin.read_float(vec3ptr + 4)
                        self.item_targets[i].z = self.dolphin.read_float(vec3ptr + 8)

            if (self.karts[i][0] in renderer.selected
                or (i == 0 and renderer.editor.freeze_player_action.isChecked())):
                self.dolphin.write_float(kartPtr + 0x23C, self.karts[i][1].x)
                self.dolphin.write_float(kartPtr + 0x240, self.karts[i][1].y)
                self.dolphin.write_float(kartPtr + 0x244, self.karts[i][1].z)
            else:
                self.karts[i][1].x = x
                self.karts[i][1].y = y
                self.karts[i][1].z = z

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
