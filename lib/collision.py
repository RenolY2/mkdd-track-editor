import math

import numba
import numpy

from .vectors import Vector3, Triangle, Line


class Collision:

    def __init__(self, triangles: tuple[tuple[Vector3, Vector3, Vector3]]):
        self.hash = hash(tuple(triangles))

        self.vertices = []
        self.face_centers = []
        self.edge_centers = []
        self.triangles = []

        for v1, v2, v3 in triangles:
            v1 = Vector3(v1.x, -v1.z, v1.y)
            v2 = Vector3(v2.x, -v2.z, v2.y)
            v3 = Vector3(v3.x, -v3.z, v3.y)

            self.vertices.extend((v1, v2, v3))

            face_center = (v1 + v2 + v3) / 3.0
            self.face_centers.append(face_center)

            for edge_center in ((v1 + v2) / 2.0, (v1 + v3) / 2.0, (v2 + v3) / 2.0):
                self.edge_centers.append(edge_center)

            triangle = Triangle(v1, v2, v3)
            if not triangle.normal.is_zero():
                self.triangles.append(triangle)

        self.flat_triangles = []
        for t in self.triangles:
            self.flat_triangles.extend((t.origin.x, t.origin.y, t.origin.z, t.p2.x, t.p2.y, t.p2.z,
                                        t.p3.x, t.p3.y, t.p3.z))
        self.flat_triangles = numpy.array(self.flat_triangles)

        if self.triangles:
            self.extent = (
                numpy.min(self.flat_triangles[0::3]),
                numpy.min(self.flat_triangles[1::3]),
                numpy.min(self.flat_triangles[2::3]),
                numpy.max(self.flat_triangles[0::3]),
                numpy.max(self.flat_triangles[1::3]),
                numpy.max(self.flat_triangles[2::3]),
            )
        else:
            self.extent = None

    def collide_ray_downwards(self, x, z, y=99999999):
        result = self.collide_ray(Line(Vector3(x, -z, y), Vector3(0.0, 0.0, -1.0)))
        return result.z if result is not None else None

    def collide_ray_closest(self, x, z, y):
        result1 = self.collide_ray(Line(Vector3(x, -z, y), Vector3(0.0, 0.0, -1.0)))
        result2 = self.collide_ray(Line(Vector3(x, -z, y), Vector3(0.0, 0.0, 1.0)))

        if result1 is None and result2 is None:
            return None

        if result1 is None:
            return result2.z
        if result2 is None:
            return result1.z

        dist1 = abs(y - result1.z)
        dist2 = abs(y - result2.z)
        return result2.z if dist1 > dist2 else result1.z

    def collide_ray_legacy(self, ray):
        best_distance = None
        place_at = None

        for tri in self.triangles:
            collision = ray.collide(tri)

            if collision is not False:
                point, distance = collision

                if best_distance is None or distance < best_distance:
                    place_at = point
                    best_distance = distance

        return place_at

    def collide_ray(self, ray):
        place_at = _collide_ray_and_triangles(
            ray.origin.x,
            ray.origin.y,
            ray.origin.z,
            ray.direction.x,
            ray.direction.y,
            ray.direction.z,
            self.flat_triangles,
        )

        if math.isnan(place_at[0]):
            return None

        return Vector3(*place_at)

    @staticmethod
    def get_closest_point(ray, points, clip_y, radius=0):
        squared_distances_and_points = []
        for i, point in enumerate(points):
            if clip_y is not None and point.z > clip_y:
                continue

            try:
                squared_distance = _squared_distance_between_line_and_point(
                    ray.origin.x,
                    ray.origin.y,
                    ray.origin.z,
                    ray.direction.x,
                    ray.direction.y,
                    ray.direction.z,
                    point.x,
                    point.y,
                    point.z,
                )
            except Exception:
                continue
            if squared_distance is not math.nan:
                squared_distances_and_points.append((squared_distance, i))

        if not squared_distances_and_points:
            return None

        squared_distance, closest_point_index = min(squared_distances_and_points)

        squared_distances_and_points = ((points[i].distance2(ray.origin), i)
                                        for d, i in squared_distances_and_points
                                        if abs(squared_distance - d) <= radius * radius)

        squared_distance, closest_point_index = min(squared_distances_and_points)

        return points[closest_point_index]


@numba.jit(nopython=True, nogil=True, cache=True)
def cross(
    x0: float,
    y0: float,
    z0: float,
    x1: float,
    y1: float,
    z1: float,
) -> tuple[float, float, float]:
    return y0 * z1 - z0 * y1, z0 * x1 - x0 * z1, x0 * y1 - y0 * x1


@numba.jit(nopython=True, nogil=True, cache=True)
def dot(
    x0: float,
    y0: float,
    z0: float,
    x1: float,
    y1: float,
    z1: float,
) -> tuple[float, float, float]:
    return x0 * x1 + y0 * y1 + z0 * z1


@numba.jit(nopython=True, nogil=True, cache=True)
def length(x: float, y: float, z: float) -> float:
    return math.sqrt(x * x + y * y + z * z)


@numba.jit(nopython=True, nogil=True, cache=True)
def length2(x: float, y: float, z: float) -> float:
    return x * x + y * y + z * z


@numba.jit(nopython=True, nogil=True, cache=True)
def normal(
    x0: float,
    y0: float,
    z0: float,
    x1: float,
    y1: float,
    z1: float,
    x2: float,
    y2: float,
    z2: float,
) -> tuple[float, float, float]:
    x, y, z = cross(x2 - x0, y2 - y0, z2 - z0, x1 - x0, y1 - y0, z1 - z0)
    size = length(x, y, z)
    x /= size
    y /= size
    z /= size
    return -x, -y, -z


@numba.jit(nopython=True, nogil=True, cache=True)
def subtract(
    x0: float,
    y0: float,
    z0: float,
    x1: float,
    y1: float,
    z1: float,
) -> tuple[float, float, float]:
    return x0 - x1, y0 - y1, z0 - z1


@numba.jit(nopython=True, nogil=True, cache=True)
def _squared_distance_between_line_and_point(
    x: float,
    y: float,
    z: float,
    dx: float,
    dy: float,
    dz: float,
    px: float,
    py: float,
    pz: float,
) -> float:
    p1_to_p2 = subtract(dx + x, dy + y, dz + z, x, y, z)
    p3_to_p1 = subtract(x, y, z, px, py, pz)
    return length2(*cross(*p1_to_p2, *p3_to_p1)) / length2(*p1_to_p2)


@numba.jit(nopython=True, nogil=True, cache=True)
def _collide_ray_and_triangle(
    x: float,
    y: float,
    z: float,
    dx: float,
    dy: float,
    dz: float,
    x0: float,
    y0: float,
    z0: float,
    x1: float,
    y1: float,
    z1: float,
    x2: float,
    y2: float,
    z2: float,
) -> tuple[float, float, float, float]:
    nx, ny, nz = normal(x0, y0, z0, x1, y1, z1, x2, y2, z2)

    d = dot(nx, ny, nz, dx, dy, dz)
    if d == 0.0:
        return -1.0, 0.0, 0.0, 0.0

    d = dot(*subtract(x0, y0, z0, x, y, z), nx, ny, nz) / d
    if d < 0.0:
        return -1.0, 0.0, 0.0, 0.0

    intersection_point = x + dx * d, y + dy * d, z + dz * d

    C0 = intersection_point[0] - x0, intersection_point[1] - y0, intersection_point[2] - z0
    if dot(nx, ny, nz, *cross(*subtract(x1, y1, z1, x0, y0, z0), *C0)) >= 0.0:
        C1 = intersection_point[0] - x1, intersection_point[1] - y1, intersection_point[2] - z1
        if dot(nx, ny, nz, *cross(*subtract(x2, y2, z2, x1, y1, z1), *C1)) >= 0.0:
            C2 = intersection_point[0] - x2, intersection_point[1] - y2, intersection_point[2] - z2
            if dot(nx, ny, nz, *cross(*subtract(x0, y0, z0, x2, y2, z2), *C2)) >= 0.0:
                return d, *intersection_point

    return -1.0, 0.0, 0.0, 0.0


@numba.jit(nopython=True, nogil=True, cache=True)
def _collide_ray_and_triangles(
    x: float,
    y: float,
    z: float,
    dx: float,
    dy: float,
    dz: float,
    triangles: numpy.array,
) -> tuple[float, float, float]:
    collisions = []
    for t in range(len(triangles) // 9):
        collision = _collide_ray_and_triangle(
            x,
            y,
            z,
            dx,
            dy,
            dz,
            triangles[t * 9 + 0],
            triangles[t * 9 + 1],
            triangles[t * 9 + 2],
            triangles[t * 9 + 3],
            triangles[t * 9 + 4],
            triangles[t * 9 + 5],
            triangles[t * 9 + 6],
            triangles[t * 9 + 7],
            triangles[t * 9 + 8],
        )

        if collision[0] >= 0.0:
            collisions.append(collision)

    if collisions:
        return min(collisions)[1:]

    return math.nan, math.nan, math.nan
