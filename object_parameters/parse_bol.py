import sys
from os import listdir, getcwd
from os.path import isfile, join, abspath
from libbol import *

class ObjData():
    def __init__(self, route, userdata, course) -> None:
        self.route = route
        self.userdata = userdata
        self.course = course

    def __str__(self) -> str:
        return "{}, {}".format(self.route, self.userdata)

mypath = join(getcwd(), "object_parameters\\bolfiles")
onlyfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]

objdict = {}

for file in onlyfiles:
    with open(join(mypath, file), "rb") as f:
        f.seek(0)
        bol = BOL.from_file(f)
        for obj in bol.objects.objects:
            objdata = ObjData(obj.pathid, obj.userdata, file)
            if obj.objectid in objdict.keys():
                objdict[obj.objectid].append(objdata)
            else:
                objdict[obj.objectid] = [objdata]
for key, value in objdict.items():
    if key not in OBJECTNAMES:
        continue

    has_route = any([obj.route != -1 for obj in value])
    has_shared_route = len(set([(obj.route, obj.course) for obj in value])) != len(value)
    userdata = [0] * 8
    for objins in value:
        userdata = [sum(x) for x in zip(userdata, objins.userdata)]
    userdata = [int(val / len(value)) for val in userdata]

    print(OBJECTNAMES[key], has_route, has_shared_route, userdata)

    filepath = join(getcwd(), "object_parameters", OBJECTNAMES[key] + ".json")
    with open(filepath, "r") as f:
        json_data = json.load(f)
    #print(json_data)
    if not has_route:
        json_data["RouteInfo"] = "None"
    else:
        if has_shared_route:
            json_data["RouteInfo"] = "Shared"
        else:
            json_data["RouteInfo"] = "Indiv"

    json_data["DefaultValues"] = userdata

    with open(filepath, "w") as f:
        json.dump(json_data, f, indent=4)
