import os
from io import TextIOWrapper, BytesIO, StringIO
from sarc import SARCArchive
from libgen import GeneratorFile, GeneratorWriter

skip = ["camera.txt", "path.txt"]

for path, dirs, files in os.walk("D:\\Wii games\\WiiU\\DATA\\EMULATORS\\Cemu\\GAMES\\PIKMIN 3 [AC3P01]\\content\\CMCmn\\generator"):
    for filename in files:
        if filename.endswith(".szs"):
            filepath = os.path.join(path, filename)
            print(filepath)
            with open(filepath, "rb") as f:
                arc = SARCArchive.from_file(f)

            for arcfilename, data in arc.files.items():
                if arcfilename in skip:
                    continue
                print(arcfilename)

                pikmin_gen_file = GeneratorFile.from_file(
                    TextIOWrapper(BytesIO(data.getvalue()), encoding="shift-jis-2004", errors="replace")
                )

                """tmp = StringIO()

                writer = GeneratorWriter(tmp)
                pikmin_gen_file.write(writer)

                tmp.seek(0)

                pikmin_gen_file = GeneratorFile.from_file(tmp)

                del tmp
                del writer
                del pikmin_gen_file"""

