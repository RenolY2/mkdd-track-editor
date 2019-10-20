from io import BytesIO
from struct import pack
from collections import OrderedDict
import time
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), os.path.pardir))

from lib.yaz0 import decompress, read_uint32, read_uint16, compress_fast


def write_uint32(f, val):
    f.write(pack(">I", val))


def write_uint16(f, val):
    f.write(pack(">H", val))


def write_pad(f, multiple=0x20):
    next_aligned_pos = (f.tell() + (multiple-1)) & ~(multiple-1)

    f.write(b"\x00"*(next_aligned_pos - f.tell()))


def stringtable_get_name(f, stringtable_offset, offset):
    current = f.tell()
    f.seek(stringtable_offset+offset)

    stringlen = 0
    while f.read(1) != b"\x00":
        stringlen += 1

    f.seek(stringtable_offset+offset)

    filename = f.read(stringlen)
    try:
        decodedfilename = filename.decode("shift-jis")
    except:
        print("filename", filename)
        print("failed")
        raise
    f.seek(current)

    return decodedfilename


def calc_hash(name, key):
    result = 0
    for char in bytes(name, encoding="shift-jis"):
        result = (result * key + char) & 0xFFFFFFFF
    return result


class StringTable(object):
    def __init__(self):
        self._strings = BytesIO()
        self._stringmap = {}

    def write_string(self, string):
        if string not in self._stringmap:
            offset = self._strings.tell()
            self._strings.write(string.encode("shift-jis"))
            self._strings.write(b"\x00")
            write_pad(self._strings, 0x4)

            self._stringmap[string] = offset

    def get_string_offset(self, string):
        return self._stringmap[string]

    def size(self):
        return self._strings.tell()#len(self._strings.getvalue())

    def write_to(self, f):
        f.write(self._strings.getvalue())


class File(BytesIO):
    def __init__(self, filename, attributes=0):
        super().__init__()

        self.name = filename
        self.attributes = attributes

    @classmethod
    def from_file(cls, filename, f):
        file = cls(filename)

        file.write(f.read())
        file.seek(0)

        return file

    @classmethod
    def from_node(cls, filename, attributes, f, offsetstart, offsetend):
        file = cls(filename, attributes)
        curr = f.tell()
        f.seek(offsetstart)
        print(hex(offsetstart))
        file.write(f.read(offsetend-offsetstart))
        file.seek(0)
        f.seek(curr)

        return file


class SARCArchive(object):
    def __init__(self):
        self.files = OrderedDict()
        self.unnamed_files = []

    @classmethod
    def from_folder(cls, folderpath):
        arc = cls()
        skip = len(folderpath)

        for dirpath, directories, files in os.walk(folderpath):
            print(dirpath)
            relpath = dirpath[skip:]
            if relpath != "":
                relpath = relpath[1:]+"/"


            print(relpath)

            for filename in files:
                try:
                    with open(os.path.join(dirpath, filename), "rb") as f:
                        file = File.from_file(relpath+filename, f)

                    arc.files[relpath+filename] = file
                except PermissionError:
                    print("Permission denied:", os.path.join(dirpath, filename), "skipping...")
        return arc

    def to_file(self, f, compress=False, padding=0x20):
        if compress:
            file = BytesIO()
        else:
            file = f

        file.write(b"SARC")
        write_uint16(file, 0x14) # size
        write_uint16(file, 0xFEFF) # byte order mark
        archivesize_offset = file.tell()
        file.write(b"ABCDEFGH") # fill in file size and data offset later
        write_uint16(file, 0x100)  # size
        write_uint16(file, 0)  # reserved

        file.write(b"SFAT")
        write_uint16(file, 0xC)
        write_uint16(file, len(self.files))
        write_uint32(file, 0x00000065)

        filedata = BytesIO()
        stringtable = StringTable()
        n = 0 
        for filepath, _file in self.files.items():
            write_pad(filedata, padding)
            offset = filedata.tell()
            filedata.write(_file.getvalue())
            endoffset = filedata.tell()
            
            stringtable.write_string(filepath)
            stringpos = stringtable.get_string_offset(filepath)
            assert stringpos % 4 == 0
            stringpos = stringpos//4
            namehash = calc_hash(filepath, 0x65)

            if stringpos > 0xFFFF:
                raise RuntimeError("String table grew too big!")

            write_uint32(file, namehash)
            write_uint32(file, (0x0100 << 16) | stringpos)
            write_uint32(file, offset)
            write_uint32(file, endoffset)

        file.write(b"SFNT")
        write_uint16(file, 0x8)
        write_uint16(file, 0x0)
        stringtable.write_to(file)

        write_pad(file, padding)
        dataoffset = file.tell()
        file.write(filedata.getvalue())
        totalsize = file.tell()

        file.seek(archivesize_offset)
        write_uint32(file, totalsize)
        write_uint32(file, dataoffset)

        if compress:
            file.seek(0)
            compress_fast(file, f)


    @classmethod
    def from_file(cls, f):
        newarc = cls()
        print("ok")
        header = f.read(4)

        if header == b"Yaz0":
            # Decompress first
            print("Yaz0 header detected, decompressing...")
            start = time.time()
            tmp = BytesIO()
            f.seek(0)
            decompress(f, tmp)
            #with open("decompressed.bin", "wb") as g:
            #    decompress(f,)
            f = tmp
            f.seek(0)

            header = f.read(4)
            print("Finished decompression.")
            print("Time taken:", time.time() - start)

        if header == b"SARC":
            pass
        else:
            raise RuntimeError("Unknown file header: {} should be Yaz0 or SARC".format(header))

        header_size = read_uint16(f)
        assert read_uint16(f) == 0xFEFF # BOM: Big endian
        size = read_uint32(f)

        data_offset = read_uint32(f)
        version = read_uint16(f)
        reserved = read_uint16(f)

        print("Archive version", hex(version), "reserved:", reserved)


        # SFAT header
        sfat = f.read(4)
        assert sfat == b"SFAT"
        sfat_header_size = read_uint16(f)
        assert sfat_header_size == 0xC
        node_count = read_uint16(f)
        hash_key = read_uint32(f)
        assert hash_key == 0x65

        nodes = []
        for i in range(node_count):
            filehash = read_uint32(f)
            fileattr = read_uint32(f)
            node_data_start = read_uint32(f)
            node_data_end = read_uint32(f)
            nodes.append((fileattr, node_data_start, node_data_end, filehash))

        # String table
        assert f.read(4) == b"SFNT"
        assert read_uint16(f) == 0x8
        read_uint16(f) # reserved

        string_table_start = f.tell()

        for fileattr, start, end, hash in nodes:
            if fileattr & 0x01000000:
                stringoffset = (fileattr & 0xFFFF) * 4
                path = stringtable_get_name(f, string_table_start, stringoffset)
            else:
                path = None

            file = File.from_node(path, fileattr, f, data_offset+start, data_offset+end)
            print(hash, calc_hash(path, 0x65))
            if path is not None:
                assert path not in newarc.files
                newarc.files[path] = file
            else:
                newarc.unnamed_files.append(file)
        print(len(newarc.unnamed_files))
        return newarc


if __name__ == "__main__":
    """
    import sys
    import os


    infile = sys.argv[1]

    with open(infile, "rb") as f:
        sarc = SARCArchive.from_file(f)

    out = infile+"_extracted"

    for path, file in sarc.files.items():
        os.makedirs(os.path.join(out, os.path.dirname(path)), exist_ok=True)
        with open(os.path.join(out, path), "wb") as f:
            f.write(file.getvalue())"""
    path = "C:\\Users\\User\\Documents\\GitHub\\pikmin3-tools\\lib\\test"


    import argparse
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("input",
                        help="Path to the archive file (usually .arc or .szs) to be extracted or the directory to be packed into an archive file.")
    parser.add_argument("--yaz0fast", action="store_true",
                        help="Encode archive as yaz0 when doing directory->.arc/.szs")
    parser.add_argument("output", default=None, nargs='?',
                        help="Output path to which the archive is extracted or a new archive file is written, depending on input.")
    parser.add_argument("--padding", default=0x20, type=int,
                        help="How much padding there should be when writing file data. Default is 32 bytes")

    args = parser.parse_args()

    inputpath = os.path.normpath(args.input)
    if os.path.isdir(inputpath):
        dir2arc = True
    else:
        dir2arc = False

    if args.output is None:
        path, name = os.path.split(inputpath)

        if dir2arc:
            if args.yaz0fast:
                ending = ".szs"
            else:
                ending = ".arc"

            if inputpath.endswith("_ext"):
                outputpath = inputpath[:-4]
            else:
                outputpath = inputpath + ending
        else:
            outputpath = os.path.join(path, name + "_ext")
    else:
        outputpath = args.output

    if dir2arc:
        sarc = SARCArchive.from_folder(inputpath)
        with open(outputpath, "wb") as f:
            sarc.to_file(f, padding=args.padding, compress=args.yaz0fast)
    else:
        with open(inputpath, "rb") as f:
            sarc = SARCArchive.from_file(f)

        out = inputpath + "_ext"

        for path, file in sarc.files.items():
            print(path, file, hex(file.attributes))
            os.makedirs(os.path.join(out, os.path.dirname(path)), exist_ok=True)
            with open(os.path.join(out, path), "wb") as f:
                f.write(file.getvalue())
