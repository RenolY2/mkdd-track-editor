

## Implementation of a yaz0 decoder/encoder in Python, by Yoshi2
## Using the specifications in http://www.amnoid.de/gc/yaz0.txt

from struct import unpack, pack
import os
import re
import hashlib
import math

from timeit import default_timer as time
from io import BytesIO
#from cStringIO import StringIO

#class yaz0():
#    def __init__(self, inputobj, outputobj = None, compress = False):

def read_uint32(f):
    return unpack(">I", f.read(4))[0]
    
def read_uint16(f):
    #return unpack(">H", f.read(2))[0]
    data = f.read(2)
    return data[0] << 8 | data[1]


def read_uint8(f):
    return f.read(1)[0]

def write_limited(f, data, limit):
    if f.tell() >= limit:
        pass
    else:
        f.write(data)
    
def decompress(f, out):
    #if out is None:
    #    out = BytesIO()
    
    # A way to discover the total size of the input data that
    # should be compatible with most file-like objects.
    f.seek(0, 2)
    maxsize = f.tell()
    f.seek(0)
    
    #data = f.read()
    #assert len(data) == maxsize
    #f.seek(0)


    header = f.read(4)
    if header != b"Yaz0":
        raise RuntimeError("File is not Yaz0-compressed! Header: {0}".format(header))
    
    decompressed_size = read_uint32(f)
    f.read(8) # padding
        
    eof = False

    # Some micro optimization, can save up to a second on bigger files
    file_read = f.read
    file_tell = f.tell

    out_read = out.read
    out_write = out.write
    out_tell = out.tell
    out_seek = out.seek

    range_8 = [i for i in range(8)]

    while out_tell() < decompressed_size and not eof:
        code_byte = file_read(1)[0]
        
        for i in range_8:
            #is_set = ((code_byte << i) & 0x80) != 0
            
            if (code_byte << i) & 0x80:
                out_write(file_read(1)) # Write next byte as-is without requiring decompression
            else:
                if file_tell() >= maxsize-1:
                    eof = True
                    break

                data = file_read(2)
                infobyte = data[0] << 8 | data[1]
                

                bytecount = infobyte >> 12 
                
                if bytecount == 0:
                    if file_tell() > maxsize-1:
                        eof = True
                        break
                    bytecount = file_read(1)[0] + 0x12
                else:
                    bytecount += 2
                
                offset = infobyte & 0x0FFF
                
                current = out_tell()
                seekback = current - (offset+1)
                
                if seekback < 0:
                    raise RuntimeError("Malformed Yaz0 file: Seek back position goes below 0")

                out_seek(seekback)
                copy = out_read(bytecount)
                out_seek(current)
                
                write_limited(out, copy, decompressed_size)

                copy_length = len(copy)
                
                if copy_length < bytecount:
                    # Copy source and copy distance overlap which essentially means that
                    # we have to repeat the copied source to make up for the difference
                    j = 0
                    for i in range(bytecount-copy_length):
                        #write_limited(out, copy[j:j+1], decompressed_size)
                        if out_tell() < decompressed_size:
                            out_write(copy[j:j+1])
                        else:
                            break

                        j = (j+1) % copy_length
                
    if out.tell() < decompressed_size:
        #print("this isn't right")
        raise RuntimeError("Didn't decompress correctly, notify the developer!")
    if out.tell() > decompressed_size:
        print(  "Warning: output is longer than decompressed size for some reason: "
                "{}/decompressed: {}".format(out.tell(), decompressed_size))


def compress_fast(f, out):
    data = f.read()
    
    maxsize = len(data)
    
    out.write(b"Yaz0")
    out.write(pack(">I", maxsize))
    out.write(b"\x00"*8)

    out_write = out.write
    print("size:", hex(maxsize))
    print(maxsize//8, maxsize/8.0)
    for i in range(int(math.ceil(maxsize/8))):
        start = i*8 
        end = (i+1)*8
        print(hex(start), hex(end))
        if end > maxsize:
            # Pad data with 0's up to 8 bytes
            tocopy = data[start:maxsize] + b"\x00"*(end-maxsize)
            print("padded")
        else:
            tocopy = data[start:end]
        
        out_write(b"\xFF") # Set all bits in the code byte to 1 to mark the following 8 bytes as copy
        out_write(tocopy)
