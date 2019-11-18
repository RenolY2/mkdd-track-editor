import json
from struct import unpack
from numpy import ndarray, array
from binascii import hexlify
from math import cos, sin
from .vectors import Vector3

def read_uint8(f):
    return unpack(">B", f.read(1))[0]

def read_int16(f):
    return unpack(">h", f.read(2))[0]

def read_uint16(f):
    return unpack(">H", f.read(2))[0]

def read_uint24(f):
    return unpack(">I", b"\x00"+f.read(3))[0]

def read_uint32(f):
    return unpack(">I", f.read(4))[0]

def read_float(f):
    return unpack(">f", f.read(4))[0]


def read_string(f):
    start = f.tell()

    next = f.read(1)
    n = 0

    if next != b"\x00":
        next = f.read(1)
        n += 1
    if n > 0:
        curr = f.tell()
        f.seek(start)
        string = f.read(n)
        f.seek(curr)
    else:
        string = ""

    return string


class Rotation(object):
    def __init__(self, forward, up, left):
        self.mtx = ndarray(shape=(4,4), dtype=float, order="F")

        self.mtx[0][0] = forward.x
        self.mtx[0][1] = -forward.z
        self.mtx[0][2] = forward.y
        self.mtx[0][3] = 0.0

        self.mtx[1][0] = left.x
        self.mtx[1][1] = -left.z
        self.mtx[1][2] = left.y
        self.mtx[1][3] = 0.0

        self.mtx[2][0] = up.x
        self.mtx[2][1] = -up.z
        self.mtx[2][2] = up.y
        self.mtx[2][3] = 0.0

        self.mtx[3][0] = self.mtx[3][1] = self.mtx[3][2] = 0.0
        self.mtx[3][3] = 1.0
        print(forward.x, -forward.z, forward.y)
        print(self.mtx)
        print([x for x in self.mtx])

    def rotate_around_x(self, degrees):
        mtx = ndarray(shape=(4,4), dtype=float, order="F", buffer=array([
            cos(degrees), 0.0, -sin(degrees), 0.0,
            0.0, 1.0, 0.0, 0.0,
            sin(degrees), 0.0, cos(degrees), 0.0,
            0.0, 0.0, 0.0, 1.0
        ]))

        self.mtx = self.mtx.dot(mtx)

    def rotate_around_y(self, degrees):
        mtx = ndarray(shape=(4,4), dtype=float, order="F", buffer=array([
            1.0, 0.0, 0.0, 0.0,
            0.0, cos(degrees), -sin(degrees), 0.0,
            0.0, sin(degrees), cos(degrees), 0.0,
            0.0, 0.0, 0.0, 1.0
        ]))

        self.mtx = self.mtx.dot(mtx)

    def rotate_around_z(self, degrees):
        mtx = ndarray(shape=(4,4), dtype=float, order="F", buffer=array([
            cos(degrees),-sin(degrees), 0.0, 0.0,
            sin(degrees), cos(degrees), 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0
        ]))

        self.mtx = self.mtx.dot(mtx)



    @classmethod
    def default(cls):
        return cls(Vector3(1, 0, 0),
                   Vector3(0, 1, 0),
                   Vector3(0, 0, -1))

    @classmethod
    def from_mkdd_rotation(cls,
                           s16forwardx, s16forwardy, s16forwardz,
                           s16upx, s16upy, s16upz):
        forward = Vector3(s16forwardx * 0.0001, s16forwardy * 0.0001, s16forwardz * 0.0001)
        up = Vector3(s16upx * 0.0001, s16upy * 0.0001, s16upz * 0.0001)
        left = up.cross(forward)

        return cls(forward, up, left)

    @classmethod
    def from_file(cls, f):
        return cls.from_mkdd_rotation(
            read_int16(f), read_int16(f), read_int16(f),
            read_int16(f), read_int16(f), read_int16(f)
        )


class ObjectContainer(list):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_file(cls, f, count, objcls):
        container = cls()

        for i in range(count):
            obj = objcls.from_file(f)
            container.append(obj)

        return container


ENEMYITEMPOINT = 1 
CHECKPOINT = 2
ROUTEGROUP = 3 
ROUTEPOINT = 4 
OBJECTS = 5 
KARTPOINT = 6 
AREA = 7
CAMERA = 8
RESPAWNPOINT = 9
LIGHTPARAM = 10
MINIGAME = 11


class ColorRGB(object):
    def __init__(self, r, g, b):
        self.r = r 
        self.g = g 
        self.b = b 
    
    @classmethod
    def from_file(cls, f):
        return cls(read_uint8(f), read_uint8(f), read_uint8(f))


class ColorRGBA(ColorRGB):
    def __init__(self, r, g, b, a):
        super().__init__(r, g, b)
        self.a = a 
    
    @classmethod
    def from_file(cls, f):
        return cls(*unpack(">BBBB", f.read(4)))


# Section 1
# Enemy/Item Route Code Start
class EnemyPoint(object):
    def __init__(self, position, pointsetting, link, scale, groupsetting, group, pointsetting2, unk1=0, unk2=0):
        self.position = position 
        self.pointsetting = pointsetting 
        self.link = link
        self.scale = scale 
        self.groupsetting = groupsetting
        self.group = group 
        self.pointsetting2 = pointsetting2
        self.unk1 = unk1 
        self.unk2 = unk2

    @classmethod
    def from_file(cls, f):
        args = [Vector3(*unpack(">fff", f.read(12)))]
        args.extend(unpack(">HhfHBBBH", f.read(15)))
        f.read(5) #padding
        return cls(*args)


class EnemyPointGroup(object):
    def __init__(self):
        self.points = []
        self.index = None
    
    def insert_point(self, enemypoint, index=-1):
        self.points.insert(index, enemypoint)

    def move_point(self, index, targetindex):
        point = self.points.pop(index)
        self.points.insert(targetindex, point)


class EnemyPointGroups(object):
    def __init__(self):
        self.groups = {}
    
    @classmethod
    def from_file(cls, f, count):
        enemypointgroups = cls()
        curr_group = None
        
        for i in range(count):
            enemypoint = EnemyPoint.from_file(f)
            print("Point", i, "in group", enemypoint.group, "links to", enemypoint.link)
            if enemypoint.group not in enemypointgroups.groups:
                # start of group 
                curr_group = EnemyPointGroup()
                curr_group.index = enemypoint.group
                enemypointgroups.groups[enemypoint.group] = curr_group
                curr_group.points.append(enemypoint)
            else:
                enemypointgroups.groups[enemypoint.group].points.append(enemypoint)

        return enemypointgroups

    def points(self):
        for group in self.groups.values():
            for point in group.points:
                yield point

# Enemy/Item Route Code End


##########
# Section 2
# Checkpoint Group Code Start
class CheckpointGroup(object):
    def __init__(self, grouplink):
        self.points = []
        self._pointcount = 0
        self.grouplink = grouplink
        self.prevgroup = [0, -1, -1, -1]
        self.nextgroup = [0, -1, -1, -1]

    @classmethod
    def from_file(cls, f):
        pointcount = read_uint16(f)
        checkpointgroup = cls(read_uint16(f))
        checkpointgroup._pointcount = pointcount

        for i in range(4):
            checkpointgroup.prevgroup[i] = read_int16(f)

        for i in range(4):
            checkpointgroup.nextgroup[i] = read_int16(f)

        return checkpointgroup


class Checkpoint(object):
    def __init__(self, start, end, unk1=0, unk2=0, unk3=0, unk4=0):
        self.start = start
        self.end = end
        self.mid = (start+end)/2.0
        self.unk1 = unk1
        self.unk2 = unk2
        self.unk3 = unk3
        self.unk4 = unk4

    @classmethod
    def from_file(cls, f):
        start = Vector3(*unpack(">fff", f.read(12)))
        end = Vector3(*unpack(">fff", f.read(12)))
        unk1, unk2, unk3, unk4 = unpack(">BBBB", f.read(4))

        return cls(start, end, unk1, unk2, unk3, unk4)


class CheckpointGroups(object):
    def __init__(self):
        self.groups = []

    @classmethod
    def from_file(cls, f, count):
        checkpointgroups = cls()

        for i in range(count):
            group = CheckpointGroup.from_file(f)
            checkpointgroups.groups.append(group)

        for group in checkpointgroups.groups:
            for i in range(group._pointcount):
                checkpoint = Checkpoint.from_file(f)
                group.points.append(checkpoint)

        return checkpointgroups

    def points(self):
        for group in self.groups:
            for point in group.points:
                yield point


# Section 3
# Routes/Paths for cameras, objects and other things
class Route(object):
    def __init__(self):
        self.points = []
        self._pointcount = 0
        self._pointstart = 0
        self.unk1 = 0
        self.unk2 = 0
    
    @classmethod
    def from_file(cls, f):
        route = cls()
        route._pointcount = read_uint16(f)
        route._pointstart = read_uint16(f)
        #pad = f.read(4)
        #assert pad == b"\x00\x00\x00\x00"
        route.unk1 = read_uint32(f)
        route.unk2 = read_uint8(f)
        pad = f.read(7)
        assert pad == b"\x00"*7
        
        return route

    def add_routepoints(self, points):
        for i in range(self._pointcount):
            self.points.append(points[self._pointstart+i])


# Section 4
# Route point for use with routes from section 3
class RoutePoint(object):
    def __init__(self, position):
        self.position = position 
    
    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))
        padding = f.read(20)
        
        return cls(position)


# Section 5
# Objects
class MapObject(object):
    def __init__(self, position, objectid):
        self.position = position
        self.scale = Vector3(1.0, 1.0, 1.0)
        self.rotation = Rotation.default()
        self.objectid = objectid
        self.pathid = 0xFFFF
        self.unk_28 = 0
        self.unk_2a = 0
        self.presence_filter = 0
        self.presence = 0x3
        self.unk_flag = 0
        self.unk_2f = 0
        self.userdata = [0 for i in range(8)]

    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))
        scale = Vector3(*unpack(">fff", f.read(12)))
        fx, fy, fz = read_int16(f), read_int16(f), read_int16(f)
        ux, uy, uz = read_int16(f), read_int16(f), read_int16(f)

        objectid = read_uint16(f)

        obj = MapObject(position, objectid)
        obj.scale = scale
        obj.rotation = Rotation.from_mkdd_rotation(fx, fy, fz, ux, uy, uz)
        obj.pathid = read_uint16(f)
        obj.unk_28 = read_uint16(f)
        obj.unk_2a = read_uint16(f)
        obj.presence_filter = read_uint8(f)
        obj.presence = read_uint8(f)
        obj.unk_flag = read_uint8(f)
        obj.unk_2f = read_uint8(f)

        for i in range(8):
            obj.userdata[i] = read_int16(f)

        return obj


class MapObjects(object):
    def __init__(self):
        self.objects = []

    def reset(self):
        del self.objects
        self.objects = []

    @classmethod
    def from_file(cls, f, objectcount):
        mapobjs = cls()

        for i in range(objectcount):
            obj = MapObject.from_file(f)
            mapobjs.objects.append(obj)

        return mapobjs


# Section 6
# Kart/Starting positions
POLE_LEFT = 0
POLE_RIGHT = 1


class KartStartPoint(object):
    def __init__(self, position):
        self.position = position
        self.scale = Vector3(1.0, 1.0, 1.0)
        self.rotation = Rotation.default()
        self.poleposition = POLE_LEFT

        # 0xFF = All, otherwise refers to player who starts here
        # Example: 0 = Player 1
        self.playerid = 0xFF

        self.padding = 0

    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))

        kstart = cls(position)
        kstart.scale = Vector3(*unpack(">fff", f.read(12)))
        kstart.rotation = Rotation.from_file(f)
        kstart.poleposition = read_uint8(f)
        kstart.playerid = read_uint8(f)
        kstart.padding = read_uint16(f)

        return kstart


class KartStartPoints(object):
    def __init__(self):
        self.positions = []

    @classmethod
    def from_file(cls, f, count):
        kspoints = cls()

        for i in range(count):
            kstart = KartStartPoint.from_file(f)
            kspoints.positions.append(kstart)

        return kspoints


# Section 7
# Areas
class Area(object):
    def __init__(self, position):
        self.position = position
        self.scale = Vector3(1.0, 1.0, 1.0)
        self.rotation = Rotation.default()
        self.check_flag = 0
        self.area_type = 0
        self.camera_index = 0xFFFF
        self.unk1 = 0
        self.unk2 = 0
        self.unkfixedpoint = 0
        self.unkshort = 0
        self.shadow_id = 0
        self.lightparam_index = 0

    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))

        area = cls(position)
        area.scale = Vector3(*unpack(">fff", f.read(12)))
        area.rotation = Rotation.from_file(f)
        area.check_flag = read_uint8(f)
        area.area_type = read_uint8(f)
        area.camera_index = read_uint16(f)
        area.unk1 = read_uint32(f)
        area.unk2 = read_uint32(f)
        area.unkfixedpoint = read_int16(f)
        area.unkshort = read_int16(f)
        area.shadow_id = read_int16(f)
        area.lightparam_index = read_int16(f)

        return area


class Areas(object):
    def __init__(self):
        self.areas = []

    @classmethod
    def from_file(cls, f, count):
        areas = cls()
        for i in range(count):
            areas.areas.append(Area.from_file(f))

        return areas


# Section 8
# Cameras
class Camera(object):
    def __init__(self, position):
        self.position = position
        self.position2 = Vector3(0.0, 0.0, 0.0)
        self.position3 = Vector3(0.0, 0.0, 0.0)
        self.rotation = Rotation.default()

        self.unkbyte = 0
        self.camtype = 0
        self.startzoom = 0
        self.camduration = 0
        self.startcamera = 0
        self.unk2 = 0
        self.unk3 = 0
        self.route = -1
        self.routespeed = 0
        self.endzoom = 0
        self.nextcam = -1
        self.name = "null"

    @classmethod
    def from_file(cls, f):
        start = f.tell()
        hexd = f.read(4*3*4)
        f.seek(start)
        print(hexlify(hexd))


        position = Vector3(*unpack(">fff", f.read(12)))

        cam = cls(position)
        cam.rotation = Rotation.from_file(f)
        cam.position2 = Vector3(*unpack(">fff", f.read(12)))
        cam.position3 = Vector3(*unpack(">fff", f.read(12)))
        cam.unkbyte = read_uint8(f)
        cam.camtype = read_uint8(f)
        cam.startzoom = read_uint16(f)
        cam.camduration = read_uint16(f)
        cam.startcamera = read_uint16(f)
        cam.unk2 = read_uint16(f)
        cam.unk3 = read_uint16(f)
        cam.route = read_int16(f)
        cam.routespeed = read_uint16(f)
        cam.endzoom = read_uint16(f)
        cam.nextcam = read_int16(f)
        cam.name = f.read(4)

        return cam


# Section 9
# Jugem Points
class JugemPoint(object):
    def __init__(self, position):
        self.position = position
        self.rotation = Rotation.default()
        self.respawn_id = 0
        self.unk1 = 0
        self.unk2 = 0
        self.unk3 = 0

    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))
        jugem = cls(position)
        jugem.rotation = Rotation.from_file(f)
        jugem.respawn_id = read_uint16(f)
        jugem.unk1 = read_uint16(f)
        jugem.unk2 = read_int16(f)
        jugem.unk3 = read_int16(f)

        return jugem


# Section 10
# LightParam
class LightParam(object):
    def __init__(self):
        self.unk1 = 0
        self.unk2 = 0
        self.unkvec = Vector3(0.0, 0.0, 0.0)
        self.unk3 = 0
        self.unk4 = 0

    @classmethod
    def from_file(cls, f):
        lp = cls()
        lp.unk1 = read_int16(f)
        lp.unk2 = read_int16(f)
        lp.unkvec = Vector3(*unpack(">fff", f.read(12)))
        lp.unk3 = read_int16(f)
        lp.unk4 = read_int16(f)

        return lp


# Section 11
# MG (MiniGame?)
class MGEntry(object):
    def __init__(self):
        self.unk1 = 0
        self.unk2 = 0
        self.unk3 = 0
        self.unk4 = 0

    @classmethod
    def from_file(cls, f):
        mgentry = MGEntry()
        mgentry.unk1 = read_int16(f)
        mgentry.unk2 = read_int16(f)
        mgentry.unk3 = read_int16(f)
        mgentry.unk4 = read_int16(f)

        return mgentry


class BOL(object):
    def __init__(self):
        self.roll = False 
        self.ambient = ColorRGB(0x64, 0x64, 0x64)
        self.light = ColorRGBA(0xFF, 0xFF, 0xFF, 0xFF)
        self.lightsource = Vector3(0.0, 0.0, 0.0)
        self.fog_type = 0
        self.fog_color = ColorRGB(0x64, 0x64, 0x64)
        self.fog_startz = 12800.0
        self.fog_endz = 12800.0
        self.unk1 = 0
        self.unk2 = 0
        self.unk3 = 0
        self.unk4 = 0
        self.unk5 = 0
        self.unk6 = 0
        
        self.shadow_color = ColorRGB(0x00, 0x00, 0x00)
        
        
        self.sections = {}
        
        self.lap_count = 0
        self.music_id = 0

        self.enemypointgroups = EnemyPointGroups()
        self.checkpoints = CheckpointGroups()
        self.routes = ObjectContainer()
        self.objects = MapObjects()
        self.kartpoints = KartStartPoints()
        self.areas = Areas()
        self.cameras = ObjectContainer()
        self.respawnpoints = ObjectContainer()
        self.lightparams = ObjectContainer()
        self.mgentries = ObjectContainer()

    def objects_with_position(self):
        for group in self.enemypointgroups.groups.values():
            for point in group.points:
                yield point

        for route in self.routes:
            for point in route.points:
                yield point

    def objects_with_2positions(self):
        for group in self.checkpoints.groups:
            for point in group.points:
                yield point

    def objects_with_rotations(self):
        for object in self.objects.objects:
            assert object is not None
            yield object

        for kartpoint in self.kartpoints.positions:
            assert kartpoint is not None
            yield kartpoint

        for area in self.areas.areas:
            assert area is not None
            yield area

        for camera in self.cameras:
            assert camera is not None
            yield camera

        for respawn in self.respawnpoints:
            assert respawn is not None
            yield respawn


    @classmethod 
    def from_file(cls, f):
        bol = cls()
        magic = f.read(4)
        print(magic, type(magic))
        assert magic == b"0015"
        
        bol.roll = read_uint8(f)
        bol.rgb_ambient = ColorRGB.from_file(f)
        bol.rgba_light = ColorRGBA.from_file(f)
        
        bol.lightsource = Vector3(read_float(f), read_float(f), read_float(f))
        
        bol.lap_count = read_uint8(f)
        bol.music_id = read_uint8(f)

        sectioncounts = {}
        for i in (ENEMYITEMPOINT, CHECKPOINT, OBJECTS, AREA, CAMERA, ROUTEGROUP, RESPAWNPOINT):
            sectioncounts[i] = read_uint16(f)
        
        bol.fog_type = read_uint8(f)
        bol.fog_color = ColorRGB.from_file(f)
        
        bol.fog_startz = read_float(f)
        bol.fog_endz = read_float(f)
        bol.unk1 = read_uint16(f)
        bol.unk2 = read_uint8(f)
        bol.unk3 = read_uint8(f)
        bol.shadow_color = ColorRGB.from_file(f)
        bol.unk4 = read_uint8(f)
        bol.unk5 = read_uint8(f)
        
        sectioncounts[LIGHTPARAM] = read_uint8(f)
        sectioncounts[MINIGAME] = read_uint8(f)
        bol.unk6 = read_uint8(f)
        
        filestart = read_uint32(f)
        assert filestart == 0
        
        sectionoffsets = {}
        for i in range(11):
            sectionoffsets[i+1] = read_uint32(f)
        
        f.read(12) # padding
        
        endofheader = f.tell()
        

        #calculated_count = (sectionoffsets[CHECKPOINT] - sectionoffsets[ENEMYITEMPOINT])//0x20
        #assert sectioncounts[ENEMYITEMPOINT] == calculated_count
        f.seek(sectionoffsets[ENEMYITEMPOINT])
        bol.enemypointgroups = EnemyPointGroups.from_file(f, sectioncounts[ENEMYITEMPOINT])

        f.seek(sectionoffsets[CHECKPOINT])
        bol.checkpoints = CheckpointGroups.from_file(f, sectioncounts[CHECKPOINT])

        f.seek(sectionoffsets[ROUTEGROUP])
        bol.routes = ObjectContainer.from_file(f, sectioncounts[ROUTEGROUP], Route)

        f.seek(sectionoffsets[ROUTEPOINT])
        routepoints = []
        count = (sectionoffsets[OBJECTS] - sectionoffsets[ROUTEPOINT])//0x20
        for i in range(count):
            routepoints.append(RoutePoint.from_file(f))

        for route in bol.routes:
            route.add_routepoints(routepoints)

        f.seek(sectionoffsets[OBJECTS])
        bol.objects = MapObjects.from_file(f, sectioncounts[OBJECTS])

        f.seek(sectionoffsets[KARTPOINT])
        bol.kartpoints = KartStartPoints.from_file(f, (sectionoffsets[AREA] - sectionoffsets[KARTPOINT])//0x28)

        f.seek(sectionoffsets[AREA])
        bol.areas = Areas.from_file(f, sectioncounts[AREA])

        f.seek(sectionoffsets[CAMERA])
        bol.cameras = ObjectContainer.from_file(f, sectioncounts[CAMERA], Camera)

        f.seek(sectionoffsets[RESPAWNPOINT])
        bol.respawnpoints = ObjectContainer.from_file(f, sectioncounts[RESPAWNPOINT], JugemPoint)

        f.seek(sectionoffsets[LIGHTPARAM])
        bol.lightparams = ObjectContainer.from_file(f, sectioncounts[LIGHTPARAM], LightParam)

        f.seek(sectionoffsets[MINIGAME])
        bol.mgentries = ObjectContainer.from_file(f, sectioncounts[MINIGAME], MGEntry)

        return bol


with open("lib/mkddobjects.json", "r") as f:
    tmp = json.load(f)
    OBJECTNAMES = {}
    for key, val in tmp.items():
        OBJECTNAMES[int(key)] = val
    del tmp


def get_full_name(id):
    if id not in OBJECTNAMES:
        return "Unknown {0}".format(id)
    else:
        return OBJECTNAMES[id]


if __name__ == "__main__":
    with open("mario_course.bol", "rb") as f:
        bol = BOL.from_file(f)