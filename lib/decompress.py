import sys 
from yaz0 import decompress
from io import BytesIO
inputfile = sys.argv[1]

with open(inputfile, "rb") as f:
    out = BytesIO()
    decompress(f, out)
    with open(inputfile+".bin", "wb") as g:
        g.write(out.getvalue())