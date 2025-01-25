from struct import unpack_from

def read_array(buffer, offset, length):
    return buffer[offset:offset+length]


def read_float(buffer, offset):
    return unpack_from(">f", buffer, offset)[0]


def read_int32(buffer, offset):
    return unpack_from(">i", buffer, offset)[0]


def read_uint32(buffer, offset):
    return unpack_from(">I", buffer, offset)[0]


def read_uint16(buffer, offset):
    return unpack_from(">H", buffer, offset)[0]


def read_uint8(buffer, offset):
    return unpack_from("B", buffer, offset)[0]


class BCOTriangle(object):
    def __init__(self):
        pass

    @classmethod
    def from_array(cls, buffer, offset, i):
        triangle_data = read_array(buffer, offset+i*0x24, 0x24)
        tri = cls()

        tri.v1 = read_uint32(triangle_data, 0x00)
        tri.v2 = read_uint32(triangle_data, 0x04)
        tri.v3 = read_uint32(triangle_data, 0x08)
        tri.d = read_float(triangle_data, 0x0C)
        tri.norm_x = read_uint16(triangle_data, 0x10)
        tri.norm_y = read_uint16(triangle_data, 0x12)
        tri.norm_z = read_uint16(triangle_data, 0x14)
        tri.floor_type = read_uint16(triangle_data, 0x16)
        tri.minmax_lookup = read_uint8(triangle_data, 0x18)
        tri.unknown = read_uint8(triangle_data, 0x19)
        tri.n1 = read_uint16(triangle_data, 0x1A)
        tri.n2 = read_uint16(triangle_data, 0x1C)
        tri.n3 = read_uint16(triangle_data, 0x1E)

        tri.unknown2 = read_uint32(triangle_data, 0x20)

        return tri


class RacetrackCollision(object):
    def __init__(self):
        self._data = None
        self.identifier = b"0003"
        self.grid_xsize = 0
        self.grid_zsize = 0
        self.coordinate1_x = 0
        self.coordinate1_z = 0
        self.coordinate2_x = 0
        self.coordinate2_z = 0
        self.entrycount = 0
        self.padding = 0

        self.gridtable_offset = 0
        self.triangles_indices_offset = 0
        self.trianglesoffset = 0
        self.verticesoffset = 0
        self.unknownoffset = 0

        self.grids = []
        self.triangles = []
        self.vertices = []

    def load_file(self, f):
        data = f.read()
        self._data = data
        if data[:0x4] != b"0003":
            raise RuntimeError("Expected header start 0003, but got {0}. "
                               "Likely not MKDD collision!".format(data[:0x4]))

        self.identifier = data[:0x4]


        self.grid_xsize = read_uint16(data, 0x4)
        self.grid_zsize = read_uint16(data, 0x6)

        self.coordinate1_x = read_int32(data, 0x8)
        self.coordinate1_z = read_int32(data, 0xC)
        self.gridcell_xsize = read_int32(data, 0x10)
        self.gridcell_zsize = read_int32(data, 0x14)

        self.entrycount = read_uint16(data, 0x18)
        self.padding = read_uint16(data, 0x1A)

        self.gridtable_offset = 0x2C
        self.triangles_indices_offset = read_uint32(data, 0x1C)
        self.trianglesoffset = read_uint32(data, 0x20)
        self.verticesoffset = read_uint32(data, 0x24)
        self.unknownoffset = read_uint32(data, 0x28)

        # Parse triangles
        trianglescount = (self.verticesoffset-self.trianglesoffset) // 0x24
        print((self.verticesoffset-self.trianglesoffset)%0x24)

        for i in range(trianglescount):
            self.triangles.append(BCOTriangle.from_array(data, self.trianglesoffset, i))

        # Parse vertices
        vertcount = (self.unknownoffset-self.verticesoffset) // 0xC
        print((self.unknownoffset-self.verticesoffset) % 0xC)

        biggestx = biggestz = -99999999
        smallestx = smallestz = 99999999

        for i in range(vertcount):
            x = read_float(data, self.verticesoffset + i*0xC + 0x00)
            y = read_float(data, self.verticesoffset + i*0xC + 0x04)
            z = read_float(data, self.verticesoffset + i*0xC + 0x08)
            self.vertices.append((x,y,z))

            if x > biggestx:
                biggestx = x
            if x < smallestx:
                smallestx = x

            if z > biggestz:
                biggestz = z
            if z < smallestz:
                smallestz = z
            #print(x,y,z)
        print("smallest/smallest vertex coordinates:",smallestx, smallestz, biggestx, biggestz)
        f.seek(self.unknownoffset)
        self.matentries = []

        for i in range(self.entrycount):
            floor_type, unk, int1, int2 = unpack_from(">HHII", f.read(0xC), 0)
            self.matentries.append((floor_type, unk, int1, int2))



def read_gridtable_entry(data, offset):
    unk1 = read_uint8(data, offset+0)
    unk2 = read_uint8(data, offset+1)
    gridtableindex = read_uint16(data, offset+2)
    triangleindices_index = read_int32(data, offset+4)

    return unk1, unk2, gridtableindex, triangleindices_index


def get_grid_entries(data, index, offset, limit, f, indent, gottem):
    unk1, unk2, nextindex, triangleindex_offset = read_gridtable_entry(data, offset)
    f.write("{0}index: {1}| {2} {3} {4} {5}\n".format(indent*4*" ", index, unk1, unk2, nextindex, triangleindex_offset))

    if nextindex != 0:
        for i in range(4):
            offset = 0x2C + (nextindex+i)*8
            print(nextindex, offset, limit)
            assert offset < limit
            gottem[nextindex+i] = True
            get_grid_entries(data, nextindex+i, offset, limit, f, indent+1, gottem)

def create_col(f, soundfile, mkdd_collision, soundfile_format = False):
    f.write("o somecustomtrack\n")
    for v_x, v_y, v_z in mkdd_collision.vertices:
        f.write("v {0} {1} {2}\n".format(v_x, v_y, v_z))

    lasttype = None
    """for ix in range(mkdd_collision.grid_xsize):
        for iz in range(mkdd_collision.grid_zsize):
            index = ix + iz*mkdd_collision.grid_xsize

            offset = index*8

            tricount = read_uint8(mkdd_collision._data, mkdd_collision.gridtable_offset + offset + 0x00)
            trioffset = read_uint32(mkdd_collision._data, mkdd_collision.gridtable_offset + offset + 0x04) * 2
            f.write("g {:04}-{:04}\n".format(ix, iz))
            for i in range(tricount):
                triindex = read_uint16(mkdd_collision._data, mkdd_collision.triangles_indices_offset + trioffset + i*2)
                v1,v2,v3,rest = mkdd_collision.triangles[triindex]
                f.write("f {0} {1} {2}\n".format(v1+1,v2+1,v3+1))"""
    i = 1
    floortypes = {}

    #with open("neighbours2.txt", "w") as fasd:
    if True:
        for tri in mkdd_collision.triangles:

            floor_type = tri.floor_type#read_uint16(rest, 0x16-0xC)
            #unk = read_uint32(rest, 0x20-0xC)
            #unk1, unk2, unk3 = read_uint16(rest, 0x1A-0xC),read_uint16(rest, 0x1C-0xC),read_uint16(rest, 0x1E-0xC)
            for val in (tri.n1, tri.n2, tri.n3):
                assert val == 65535 or val < len(mkdd_collision.triangles)
            #if floor_type in (0x1200, 0x200, 0x201):
            #if True:
            #print(i, hex(floor_type),unk1+1,unk2+1,unk3+1, len(mkdd_collision.triangles))
            #fasd.write("{0} {1} {2} {3} {4} {5} {6}\n".format(i, hex(floor_type),unk1+1,unk2+1,unk3+1, len(mkdd_collision.triangles), (v1,v2,v3)))
            currenttype = (tri.floor_type, tri.unknown, tri.unknown2)
            if currenttype != lasttype:
                f.write("usemtl Roadtype_0x{0:04X}_0x{1:02X}_0x{2:08X}\n".format(floor_type, tri.unknown, tri.unknown2))
                lasttype = currenttype

            f.write("f {0} {1} {2}\n".format(tri.v1+1,tri.v2+1,tri.v3+1))
            i += 1
    
    if soundfile_format:
        for entry in mkdd_collision.matentries:
            soundfile.write("0x{:04X}=0x{:X}, 0x{:X}, 0x{:X}\n".format(*entry))
    else:
        for entry in mkdd_collision.matentries:
            soundfile.write("0x{:04X}=(0x{:X}, 0x{:X}, 0x{:X})\n".format(*entry))


def convert(input_path, output_path=None, remap_format=False):
    # with open("F:/Wii games/MKDDModdedFolder/P-GM4E/files/Course/luigi2/luigi_course.bco", "rb") as f:
    with open(input_path, "rb") as f:
        # with open("F:/Wii games/MKDDModdedFolder/P-GM4E/files/Course/daisy/daisy_course.bco", "rb") as f:
        col = RacetrackCollision()
        col.load_file(f)
    print("Collision loaded")
    if output_path is None:
        output = input_path + ".obj"
    else:
        output = output_path

    txt_dump = "_remap.txt" if remap_format else "_soundfile.txt"
    with open(output, "w") as f:
        with open(output + txt_dump, "w") as g:
            create_col(f, g, col, not remap_format)
    print("Written obj to", output)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument("input",
                        help="Filepath to bco file to be converted to obj")
    parser.add_argument("output", default=None, nargs = '?',
                        help="Output path of the created collision file")
    parser.add_argument("--remap_format", action="store_true",
                        help="Output path of the created collision file")

    args = parser.parse_args()
    convert(args.input, args.output, args.remap_format)