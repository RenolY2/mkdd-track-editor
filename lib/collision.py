from .vectors import Vector3, Triangle, Line


class Collision:

    def __init__(self, verts, faces):
        self.verts = verts
        self.faces = faces
        self.triangles = []
        for v1i, v2i, v3i in self.faces:
            x, y, z = verts[v1i[0] - 1]
            v1 = Vector3(x, -z, y)
            x, y, z = verts[v2i[0] - 1]
            v2 = Vector3(x, -z, y)
            x, y, z = verts[v3i[0] - 1]
            v3 = Vector3(x, -z, y)

            triangle = Triangle(v1, v2, v3)
            if not triangle.normal.is_zero():
                self.triangles.append(triangle)

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

    def collide_ray(self, ray):
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
