import numpy as np


class Vector3:
    def __init__(self, x, y, z):
        self.array = np.array((x, y, z), dtype=float)

    @property
    def x(self):
        return self.array[0]

    @x.setter
    def x(self, value):
        self.array[0] = value

    @property
    def y(self):
        return self.array[1]

    @y.setter
    def y(self, value):
        self.array[1] = value

    @property
    def z(self):
        return self.array[2]

    @z.setter
    def z(self, value):
        self.array[2] = value

    def copy(self):
        return Vector3(*self.array)

    def norm(self):
        return np.linalg.norm(self.array)

    def normalize(self):
        self.array /= self.norm()

    def normalized(self):
        return Vector3(*(self.array / self.norm()))

    def cross(self, other_vec):
        return Vector3(*np.cross(self.array, other_vec.array))

    def dot(self, other_vec):
        return np.vdot(self.array, other_vec.array)

    def __hash__(self):
        return hash(tuple(self.array))

    def __truediv__(self, other):
        return Vector3(*(self.array / other))

    def __add__(self, other_vec):
        return Vector3(*(self.array + other_vec.array))

    def __mul__(self, other):
        return Vector3(*(self.array * other))

    def __sub__(self, other_vec):
        return Vector3(*(self.array - other_vec.array))

    def cos_angle(self, other_vec):
        return self.dot(other_vec)/(self.norm()*other_vec.norm())

    def __iadd__(self, other_vec):
        self.array += other_vec.array
        return self

    def __isub__(self, other_vec):
        self.array -= other_vec.array
        return self

    def __imul__(self, other):
        self.array *= other
        return self

    def __itruediv__(self, other):
        self.array /= other
        return self

    def is_zero(self):
        return not self.array.any()

    def __eq__(self, other_vec):
        return np.all(self.array == other_vec.array) if isinstance(other_vec, Vector3) else False

    def __str__(self):
        return str(tuple(self.array))

    def __repr__(self):
        return str(tuple(self.array))

    def distance(self, other):
        return (other - self).norm()

    def distance2(self, other):
        return np.sum(np.square(other.array - self.array))


class Plane:
    def __init__(self, origin, vec1, vec2): # a point and two vectors defining the plane
        self.origin = origin
        self._vec1 = vec1
        self._vec2 = vec2
        self.normal = vec1.cross(vec2)

    @classmethod
    def from_implicit(cls, origin, normal):
        dummyvec = Vector3(0.0, 0.0, 0.0)
        plane = cls(origin, dummyvec, dummyvec)
        plane.normal = normal
        return plane

    def point_is_on_plane(self, vec):
        return (vec-self.origin).dot(self.normal) == 0

    def is_parallel(self, vec):
        return self.normal.dot(vec) == 0

    @classmethod
    def xy_aligned(cls, origin):
        return cls(origin, Vector3(1, 0, 0), Vector3(0, 1, 0))

    @classmethod
    def xz_aligned(cls, origin):
        return cls(origin, Vector3(1, 0, 0), Vector3(0, 0, 1))

    @classmethod
    def yz_aligned(cls, origin):
        return cls(origin, Vector3(0, 1, 0), Vector3(0, 0, 1))


class Triangle:
    def __init__(self, p1, p2, p3):
        self.origin = p1
        self.p2 = p2
        self.p3 = p3
        self.p1_to_p2 = p2 - p1
        self.p1_to_p3 = p3 - p1
        self.p2_to_p3 = p3 - p2
        self.p3_to_p1 = p1 - p3

        self.normal = self.p1_to_p2.cross(self.p1_to_p3)

        if not self.normal.is_zero():
            self.normal.normalize()

    def is_parallel(self, vec):
        return self.normal.dot(vec) == 0


class Line:
    def __init__(self, origin, direction):
        self.origin = origin
        self.direction = direction
        self.direction.normalize()

    def collide(self, tri: Triangle):
        normal = tri.normal

        dot = normal.dot(self.direction)
        if dot == 0.0:
            return False

        d = (tri.origin - self.origin).dot(normal) / dot

        if d < 0:
            return False

        intersection_point = self.origin + self.direction * d

        C0 = intersection_point - tri.origin
        if normal.dot(tri.p1_to_p2.cross(C0)) > 0:
            C1 = intersection_point - tri.p2
            if normal.dot(tri.p2_to_p3.cross(C1)) > 0:
                C2 = intersection_point - tri.p3
                if normal.dot(tri.p3_to_p1.cross(C2)) > 0:
                    return intersection_point, d

        return False

    def collide_plane(self, plane: Plane):
        pos = self.origin
        direction = self.direction

        if not plane.is_parallel(direction):
            d = ((plane.origin - pos).dot(plane.normal)) / plane.normal.dot(direction)
            if d >= 0:
                point = pos + (direction * d)
                return point, d

        return False
