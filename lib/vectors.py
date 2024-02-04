from math import sqrt

import numpy

class Vector3:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def copy(self):
        return Vector3(self.x, self.y, self.z)

    def norm(self):
        return sqrt(self.x**2 + self.y**2 + self.z**2)

    def length(self):
        return sqrt(self.length2())

    def length2(self):
        return self.x**2 + self.y**2 + self.z**2

    def normalize(self):
        norm = self.norm()
        self.x /= norm
        self.y /= norm
        self.z /= norm

    def normalized(self):
        other = self.copy()
        other.normalize()
        return other

    def unit(self):
        return self/self.norm()

    def cross(self, other_vec):
        return Vector3(self.y*other_vec.z - self.z*other_vec.y,
                       self.z*other_vec.x - self.x*other_vec.z,
                       self.x*other_vec.y - self.y*other_vec.x)

    def dot(self, other_vec):
        return self.x*other_vec.x + self.y*other_vec.y + self.z*other_vec.z

    def __truediv__(self, other):
        return Vector3(self.x/other, self.y/other, self.z/other)

    def __add__(self, other_vec):
        return Vector3(self.x+other_vec.x, self.y+other_vec.y, self.z+other_vec.z)

    def __mul__(self, other):
        return Vector3(self.x*other, self.y*other, self.z*other)

    def __sub__(self, other_vec):
        return Vector3(self.x-other_vec.x, self.y-other_vec.y, self.z-other_vec.z)

    def cos_angle(self, other_vec):
        return self.dot(other_vec)/(self.norm()*other_vec.norm())

    def __iadd__(self, other_vec):
        self.x += other_vec.x
        self.y += other_vec.y
        self.z += other_vec.z
        return self

    def __isub__(self, other_vec):
        self.x -= other_vec.x
        self.y -= other_vec.y
        self.z -= other_vec.z
        return self

    def __imul__(self, other):
        self.x *= other
        self.y *= other
        self.z *= other
        return self

    def __itruediv__(self, other):
        self.x /= other
        self.y /= other
        self.z /= other
        return self

    def __hash__(self):
        return hash((self.x, self.y, self.z))

    def is_zero(self):
        return self.x == self.y == self.z == 0

    def __eq__(self, other_vec):
        return self.x == other_vec.x and self.y == other_vec.y and self.z == other_vec.z

    def __str__(self):
        return str((self.x, self.y, self.z))

    def distance(self, other):
        return sqrt(self.distance2(other))

    def distance2(self, other):
        diff = other - self
        return diff.x**2 + diff.y**2 + diff.z**2


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

    def collide_plane(self, plane: Plane) -> Vector3 | None:
        ndotu = plane.normal.dot(self.direction)
        if abs(ndotu) < 0.000001:
            return None

        w = self.origin - plane.origin
        return w + self.direction * (-plane.normal.dot(w) / ndotu) + plane.origin

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
        if normal.dot(tri.p1_to_p2.cross(C0)) >= 0:
            C1 = intersection_point - tri.p2
            if normal.dot(tri.p2_to_p3.cross(C1)) >= 0:
                C2 = intersection_point - tri.p3
                if normal.dot(tri.p3_to_p1.cross(C2)) >= 0:
                    return intersection_point, d

        return False


def align_z_axis_with_target_dir(target_dir: Vector3, up_dir: Vector3) -> numpy.matrix:
    # Implementation taken from Imath.
    if target_dir.length2() == 0.0:
        target_dir = Vector3(0, 0, 1)

    if up_dir.length2() == 0.0:
        up_dir = Vector3(0, 1, 0)

    if up_dir.cross(target_dir).length2() == 0.0:
        up_dir = target_dir.cross(Vector3(1.0, 0.0, 0.0))
        if up_dir.length2() == 0.0:
            up_dir = target_dir.cross(Vector3(0.0, 0.0, 1.0))

    target_perp_dir = up_dir.cross(target_dir)
    target_up_dir = target_dir.cross(target_perp_dir)

    target_perp_dir.normalize()
    target_up_dir.normalize()
    target_dir.normalize()

    return numpy.matrix([
        [target_perp_dir.x, target_perp_dir.y, target_perp_dir.z, 0],
        [target_up_dir.x, target_up_dir.y, target_up_dir.z, 0],
        [target_dir.x, target_dir.y, target_dir.z, 0],
        [0, 0, 0, 1],
    ])


def rotation_matrix_with_up_dir(from_dir: Vector3, to_dir: Vector3,
                                up_dir: Vector3) -> numpy.matrix:
    # Implementation taken from Imath.
    z_axis2_from_dir = align_z_axis_with_target_dir(from_dir, Vector3(0, 1, 0))
    z_axis2_from_dir.transpose()
    z_axis2_to_dir = align_z_axis_with_target_dir(to_dir, up_dir)
    return z_axis2_from_dir * z_axis2_to_dir
