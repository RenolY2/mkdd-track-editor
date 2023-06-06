from struct import unpack

def read_vertex(v_data):
    split = v_data.split("/")
    if len(split) == 3:
        vnormal = int(split[2])
    else:
        vnormal = None
    v = int(split[0])
    return v, vnormal

def read_obj(objfile):

    vertices = []
    faces = []
    face_normals = []
    normals = []

    for line in objfile:
        line = line.strip()
        args = line.split(" ")

        if len(args) == 0 or line.startswith("#"):
            continue
        cmd = args[0]

        if cmd == "v":
            if "" in args:
                args.remove("")
            x,y,z = map(float, args[1:4])
            vertices.append((x,y,z))
        elif cmd == "f":
            # if it uses more than 3 vertices to describe a face then we panic!
            # no triangulation yet.
            if len(args) == 5:
                v1, v2, v3, v4 = map(read_vertex, args[1:5])
                faces.append((v1, v3, v2))
                faces.append((v3, v1, v4))
            elif len(args) == 4:
                v1, v2, v3 = map(read_vertex, args[1:4])
                faces.append((v1, v2, v3))
            elif len(args) > 5:
                raise RuntimeError("Mesh has faces with more than 4 polygons! Only Tris and Quads supported.")
        elif cmd == "vn":
            nx,ny,nz = map(float, args[1:4])
            normals.append((nx,ny,nz))


    #objects.append((current_object, vertices, faces))

    return vertices, faces, normals

def read_uint32(f):
    val = f.read(0x4)
    return unpack(">I", val)[0]

def read_float_tripple(f):
    val = f.read(0xC)
    return unpack(">fff", val)

def read_uint16(f):
    return unpack(">H", f.read(2))[0]
