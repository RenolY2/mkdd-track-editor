import libpiktxt
from copy import deepcopy
from struct import pack
from itertools import chain
from io import StringIO

class TextRoot(list):
    pass


class TextNode(list):
    pass


ONYN_ROCKET = "Rocket"
ONYN_REDONION = "Red Onion"
ONYN_YELLOWONION = "Yellow Onion"
ONYN_BLUEONION = "Blue Onion"

BRIDGE_SHORT = "Short Bridge"
BRIDGE_SHORT_UP = "Short Bridge (Slanted)"
BRIDGE_LONG = "Long Bridge"
BRIDGES = {"0": BRIDGE_SHORT,
           "1": BRIDGE_SHORT_UP,
           "2": BRIDGE_LONG}

GATE_SAND = "Gate"
GATE_ELECTRIC = "Electric Gate"

TEKIS = {
    "0": "Pellet Posy",
    "1": "Dwarf Red Bulborb",
    "2": "Red Bulborb",
    "3": "Lapis Lazuli Candypop Bud",
    "4": "Crimson Candypop Bud",
    "5": "Golden Candypop Bud",
    "6": "Violet Candypop Bud",
    "7": "Ivory Candypop Bud",
    "8": "Queen Candypop Bud",
    "9": "Iridescent Flint Beetle",
    "10": "Iridescent Glint Beetle",
    "11": "Doodlebug",
    "12": "Female Sheargrub",
    "13": "Male Sheargrub",
    "14": "Shearwig",
    "15": "Cloaking Burrow",
    "16": "Honeywisp",
    "17": "Yellow Wollywog",
    "18": "Wollywog",
    "19": "Falling boulder",
    "20": "Fire geyser",
    "21": "Gas pipe",
    "22": "Electrical wire",
    "23": "Swooping Snitchbug",
    "24": "Fiery Blowhog",
    "25": "Watery Blowhog",
    "26": "Water Dumple",
    "27": "Wogpole",
    "28": "Anode Beetle",
    "29": "Puffy Blowhog",
    "30": "Empress Bulblax",
    "31": "Bulborb Larva",
    "32": "Bumbling Snitchbug",
    "33": "Fiery Bulblax",
    "34": "Burrowing Snagret",
    "35": "Spotty Bulbear",
    "36": "Bomb rock",
    "37": "Egg",
    "38": "Breadbug",
    "40": "Giant Breadbug and base",
    "41": "Antenna Beetle",
    "42": "Orange Bulborb",
    "43": "Hairy Bulborb",
    "44": "Dwarf Orange Bulborb",
    "45": "Snow Bulborb",
    "46": "Dandelion",
    "47": "Clover",
    "48": "Common Glowcap",
    "49": "Figwort",
    "50": "Figwort",
    "51": "Shoot",
    "52": "Shoot",
    "53": "Emperor Bulblax",
    "54": "Mamuta",
    "55": "Withering Blowhog",
    "56": "Beady Long Legs",
    "57": "Lesser Spotted Jellyfloat",
    "58": "Careening Dirigibug",
    "59": "Fiery Dweevil",
    "60": "Caustic Dweevil",
    "61": "Munge Dweevil",
    "62": "Anode Dweevil",
    "63": "Hermit Crawmad",
    "65": "Ravenous Whiskerpillar",
    "66": "Man",
    "67": "Bulbmin",
    "68": "Mitite",
    "69": "Raging Long Legs",
    "70": "Pileated Snagret",
    "71": "Ranging Bloyster",
    "72": "Greater Spotted Jellyfloat",
    "73": "Titan Dweevil",
    "75": "Armored Cannon Beetle Larva",
    "76": "Dwarf Bulbear",
    "77": "Group of 9 Unmarked Spectralids",
    "78": "Gatling Groink",
    "79": "Skitter Leaf",
    "80": "Horsetail",
    "81": "Seeding Dandelion",
    "84": "Creeping Chrysanthemum",
    "85": "Glowstem",
    "86": "Glowstem",
    "87": "Margaret",
    "88": "Foxtail",
    "89": "Chigoyami paper",
    "90": "Fiddlehead",
    "91": "Figwort",
    "92": "Figwort",
    "93": "Volatile Dweevil",
    "94": "Segmented Crawbster",
    "95": "Decorated Cannon Beetle",
    "96": "Armored Cannon Beetle Larva",
    "97": "Gatling Groink",
    "98": "Waterwraith rollers",
    "99": "Waterwraith",
    "101": "Toady Bloyster"
}
TREASURES = {
    "0": "Rubber Ugly",
    "1": "Insect Condo",
    "2": "Meat Satchel",
    "3": "Coiled Launcher",
    "4": "Confection Hoop",
    "5": "Omniscient Sphere",
    "6": "Love Sphere",
    "7": "Mirth Sphere",
    "8": "Maternal Sculpture",
    "9": "Stupendous Lens",
    "10": "Leviathan Feather",
    "11": "Superstrong Stabilizer",
    "12": "Space Wave Receiver",
    "13": "Joy Receptacle",
    "14": "Worthless Statue",
    "15": "Priceless Statue",
    "16": "Triple Sugar Threat",
    "17": "King of Sweets",
    "18": "Diet Doomer",
    "19": "Pale Passion",
    "20": "Boom Cone",
    "21": "Bug Bait",
    "22": "Milk Tub",
    "23": "Petrified Heart",
    "24": "Regal Diamond",
    "25": "Princess Pearl",
    "26": "Silencer",
    "27": "Armored Nut",
    "28": "Chocolate Cushion",
    "29": "Sweet Dreamer",
    "30": "Cosmic Archive",
    "31": "Cupid",
    "32": "Science Project",
    "33": "Manual Honer",
    "34": "Broken Food Master",
    "35": "Sud Generator",
    "36": "Wiggle Noggin",
    "37": "Omega Flywheel",
    "38": "Lustrous Element",
    "39": "Superstick Textile",
    "40": "Possessed Squash",
    "41": "Gyroid Bust",
    "42": "Sunseed Berry",
    "43": "Glee Spinner",
    "44": "Decorative Goo",
    "45": "Anti",
    "46": "Crystal King",
    "47": "Fossilized Ursidae",
    "48": "Time Capsule",
    "49": "Olimarnite Shell",
    "50": "Conifer Spire",
    "51": "Abstract Masterpiece",
    "52": "Arboreal Frippery",
    "53": "Onion Replica",
    "54": "Infernal Vegetable",
    "55": "Adamantine Girdle",
    "56": "Directory of Destiny",
    "57": "Colossal Fossil",
    "58": "Invigorator",
    "59": "Vacuum Processor",
    "60": "Mirrored Element",
    "61": "Nouveau Table",
    "62": "Pink Menace",
    "63": "Frosty Bauble",
    "64": "Gemstar Husband",
    "65": "Gemstar Wife",
    "66": "Universal Com",
    "67": "Joyless Jewel",
    "68": "Fleeting Art Form",
    "69": "Innocence Lost",
    "70": "Icon of Progress",
    "71": "Unspeakable Wonder",
    "72": "Aquatic Mine",
    "73": "Temporal Mechanism",
    "74": "Essential Furnishing",
    "75": "Flame Tiller",
    "76": "Doomsday Apparatus",
    "77": "Impediment Scourge",
    "78": "Future Orb",
    "79": "Shock Therapist",
    "80": "Flare Cannon",
    "81": "Comedy Bomb",
    "82": "Monster Pump",
    "83": "Mystical Disc",
    "84": "Vorpal Platter",
    "85": "Taste Sensation",
    "86": "Lip Service",
    "87": "Utter Scrap",
    "88": "Paradoxical Enigma",
    "89": "King of Bugs",
    "90": "Essence of Rage",
    "91": "Essence of Despair",
    "92": "Essence of True Love",
    "93": "Essence of Desire",
    "94": "Citrus Lump",
    "95": "Behemoth Jaw",
    "96": "Anxious Sprout",
    "97": "Implement of Toil",
    "98": "Luck Wafer",
    "99": "Meat of Champions",
    "100": "Talisman of Life",
    "101": "Strife Monolith",
    "102": "Boss Stone",
    "103": "Toxic Toadstool",
    "104": "Growshroom",
    "105": "Indomitable CPU",
    "106": "Network Mainbrain",
    "107": "Repair Juggernaut",
    "108": "Exhausted Superstick",
    "109": "Pastry Wheel",
    "110": "Combustion Berry",
    "111": "Imperative Cookie",
    "112": "Compelling Cookie",
    "113": "Impenetrable Cookie",
    "114": "Comfort Cookie",
    "115": "Succulent Mattress",
    "116": "Corpulent Nut",
    "117": "Alien Billboard",
    "118": "Massage Girdle",
    "119": "Crystallized Telepathy",
    "120": "Crystallized Telekinesis",
    "121": "Crystallized Clairvoyance",
    "122": "Eternal Emerald Eye",
    "123": "Tear Stone",
    "124": "Crystal Clover",
    "125": "Danger Chime",
    "126": "Sulking Antenna",
    "127": "Spouse Alert",
    "128": "Master",
    "129": "Extreme Perspirator",
    "130": "Pilgrim Bulb",
    "131": "Stone of Glory",
    "132": "Furious Adhesive",
    "133": "Quenching Emblem",
    "134": "Flame of Tomorrow",
    "135": "Love Nugget",
    "136": "Child of the Earth",
    "137": "Disguised Delicacy",
    "138": "Proton AA",
    "139": "Fuel Reservoir",
    "140": "Optical Illustration",
    "141": "Durable Energy Cell",
    "142": "Courage Reactor",
    "143": "Thirst Activator",
    "144": "Harmonic Synthesizer",
    "145": "Merciless Extractor",
    "146": "Remembered Old Buddy",
    "147": "Fond Gyro Block",
    "148": "Memorable Gyro Block",
    "149": "Lost Gyro Block",
    "150": "Favorite Gyro Block",
    "151": "Treasured Gyro Block",
    "152": "Fortified Delicacy",
    "153": "Scrumptious Shell",
    "154": "Memorial Shell",
    "155": "Chance Totem",
    "156": "Dream Architect",
    "157": "Spiny Alien Treat",
    "158": "Spirit Flogger",
    "159": "Mirrored Stage",
    "160": "Enamel Buster",
    "161": "Drought Ender",
    "162": "White Goodness",
    "163": "Salivatrix",
    "164": "Creative Inspiration",
    "165": "Massive Lid",
    "166": "Happiness Emblem",
    "167": "Survival Ointment",
    "168": "Mysterious Remains",
    "169": "Dimensional Slicer",
    "170": "Yellow Taste Tyrant",
    "171": "Hypnotic Platter",
    "172": "Gherkin Gate",
    "173": "Healing Cask",
    "174": "Pondering Emblem",
    "175": "Activity Arouser",
    "176": "Stringent Container",
    "177": "Patience Tester",
    "178": "Endless Repository",
    "179": "Fruit Guard",
    "180": "Nutrient Silo",
    "181": "Drone Supplies",
    "182": "Unknown Merit",
    "183": "Seed of Greed",
    "184": "Heavy",
    "185": "Air Brake",
    "186": "Hideous Victual",
    "187": "Emperor Whistle"
}

EXPKIT_TREASURES = {
    "0": "Brute Knuckles",
    "1": "Dream Material",
    "2": "Amplified Amplifier",
    "3": "Professional Noisemaker",
    "4": "Stellar Orb",
    "5": "Justice Alloy",
    "6": "Forged Courage",
    "7": "Repugnant Appendage",
    "8": "Prototype Detector",
    "9": "Five-man Napsack",
    "10": "Spherical Atlas",
    "11": "Geographic Projection",
    "12": "The Key"
}

def assert_notlist(val):
    assert not isinstance(val, list)

class PikminObject(object):
    def __init__(self):
        self.version = "{v0.3}"
        self.reserved = 0
        self.days_till_resurrection = 0
        self.arguments = [0 for i in range(32)]

        self.position_x = self.position_y = self.position_z = 0.0
        self.offset_x = self.offset_y = self.offset_z = 0.0
        self.x = self.y = self.z = 0.0

        self.object_type = None
        self.identifier = None
        self.identifier_misc = None
        self._object_data = TextNode()
        self.preceeding_comment = []

        self._horizontal_rotation = None

        self._useful_name = "None"

    def from_text(self, text):
        node = libpiktxt.PikminTxt()
        node.from_text(text)

        if len(node._root) == 1:
            self.from_textnode(node._root[0])
        else:
            self.from_textnode(node._root)

        f = StringIO(text)

        comments = []
        for line in f:
            if line.startswith("#"):
                comments.append(line)
            elif line[0] != "#":
                break

        self.set_preceeding_comment(comments)
        if self.get_rotation() is not None:
            self._horizontal_rotation = float(self.get_rotation()[1])
        else:
            self._horizontal_rotation = None
        self.update_useful_name()

    def from_textnode(self, textnode):
        self.version = textnode[0]  # Always v0.3?
        self.reserved = int(textnode[1])  # Unknown
        self.days_till_resurrection = int(textnode[2])  # Probably how many days till an object reappears.
        self.arguments = [int(x) for x in textnode[3]]  # 32 byte shift-jis encoded identifier string
        self.position_x, self.position_y, self.position_z = map(float, textnode[4])  # XYZ Position
        self.offset_x, self.offset_y, self.offset_z = map(float, textnode[5])  # XYZ offset

        self.x = self.position_x + self.offset_x
        self.y = self.position_y + self.offset_y
        self.z = self.position_z + self.offset_z

        # Sometimes the identifier information has 2 or 3 arguments so we handle it like this
        self.object_type = textnode[6][0]  # Commonly a 4 character string
        self.identifier_misc = textnode[6][1:]  # Sometimes just a 4 digit number with preceeding

        self._object_data = textnode[7:]  # All the remaining data, differs per object type
        if self.get_rotation() is not None:
            self._horizontal_rotation = float(self.get_rotation()[1])
        else:
            self._horizontal_rotation = None
        #print("Object", self.identifier, "with position", self.position_x, self.position_y, self.position_z)
        self.update_useful_name()

    def from_pikmin_object(self, other_pikminobj):
        self.version = other_pikminobj.version
        self.reserved = other_pikminobj.reserved
        self.days_till_resurrection = other_pikminobj.days_till_resurrection
        self.arguments = other_pikminobj.arguments

        self.position_x = other_pikminobj.position_x
        self.position_y = other_pikminobj.position_y
        self.position_z = other_pikminobj.position_z

        self.offset_x = other_pikminobj.offset_x
        self.offset_y = other_pikminobj.offset_y
        self.offset_z = other_pikminobj.offset_z

        self.x = self.position_x + self.offset_x
        self.y = self.position_y + self.offset_y
        self.z = self.position_z + self.offset_z

        self.object_type = other_pikminobj.object_type
        self.identifier_misc = other_pikminobj.identifier_misc

        self._object_data = other_pikminobj._object_data
        self.set_preceeding_comment(other_pikminobj.preceeding_comment)

        if self.get_rotation() is not None:
            self._horizontal_rotation = float(self.get_rotation()[1])
        else:
            self._horizontal_rotation = None
        self.update_useful_name()

    def copy(self):
        #newobj = PikminObject()
        #newobj.from_pikmin_object(self)
        return deepcopy(self)#newobj

    def get_rotation(self):
        if self.object_type == "{item}":
            itemdata = self._object_data[0]

            return tuple(float(x) for x in itemdata[1])

        elif self.object_type == "{teki}":
            return 0.0, float(self._object_data[2]), 0.0
        elif self.object_type == "{pelt}":
            peltdata = self._object_data[0]

            return tuple(float(x) for x in peltdata[1])
        else:
            return None

    def update_useful_name(self):
        self._useful_name = self._get_useful_object_name()

    def get_useful_object_name(self):
        return self._useful_name

    def _get_useful_object_name(self):
        if self.object_type == "{item}":
            itemdata = self._object_data[0]
            subtype = itemdata[0]

            if subtype == "{onyn}":
                oniontype = itemdata[3]
                if oniontype == "4":
                    return ONYN_ROCKET
                elif oniontype == "2":
                    return ONYN_YELLOWONION
                elif oniontype == "1":
                    return ONYN_REDONION
                elif oniontype == "0":
                    return ONYN_BLUEONION

            elif subtype == "{brdg}":
                bridgetype = itemdata[3]
                if bridgetype in BRIDGES:
                    return BRIDGES[bridgetype]
                else:
                    return "<invalid bridge type>"
            elif subtype == "{gate}":
                return GATE_SAND
            elif subtype == "{dgat}":
                return GATE_ELECTRIC
            elif subtype == "{dwfl}":
                blocktype = itemdata[4]
                is_seesaw = itemdata[5]
                suffix = ""

                if is_seesaw == "1":
                    suffix = " [Seesaw]"
                elif is_seesaw != "0":
                    suffix = " [Invalid]"

                if blocktype == "0":
                    return "Small Block"+suffix
                elif blocktype == "1":
                    return "Normal Block"+suffix
                elif blocktype == "2":
                    return "Paper Bag"+suffix
                else:
                    return "Invalid dwfl"
            elif subtype == "{plnt}":
                name = "Burg. Spiderwort"
                planttype = itemdata[3]
                if planttype == "0":
                    name += " (Red Berry)"
                elif planttype == "1":
                    name += " (Purple Berry)"
                elif planttype == "2":
                    name += " (Mixed)"
                else:
                    name += " (Invalid)"

                return name

            return self.object_type+subtype

        elif self.object_type == "{teki}":
            identifier = self.identifier_misc[1][1:]
            if identifier in TEKIS:
                return "Teki: "+TEKIS[identifier]
            else:
                return "Unknown Teki: {0}".format(identifier)

        elif self.object_type == "{pelt}":
            mgrid = self._object_data[0][0]

            if mgrid == "0":
                treasureid = self._object_data[0][3]
                if isinstance(treasureid, list):
                    pellet_type = treasureid[0]

                    if pellet_type == "0":
                        return "Blue Pellet"
                    elif pellet_type == "1":
                        return "Red Pellet"
                    elif pellet_type == "2":
                        return "Yellow Pellet"
                    else:
                        return "Unknown Pellet"
                else:
                    return "Invalid Pellet"

            if mgrid == "3":
                treasureid = self._object_data[0][3]
                if treasureid in TREASURES:
                    return "Treasure: "+TREASURES[treasureid]
                else:
                    return "Unknown treasure: {0}".format(treasureid)
            elif mgrid == "4":
                treasureid = self._object_data[0][3]
                if treasureid in EXPKIT_TREASURES:
                    return "ExpKit Treasure: "+EXPKIT_TREASURES[treasureid]
                else:
                    return "Unknown exploration kit treasure: {0}".format(treasureid)
            return self.object_type

        else:
            return self.object_type

    def get_horizontal_rotation(self):
        """if self.object_type == "{item}":
            return float(self._object_data[0][1][1])
        elif self.object_type == "{teki}":
            return float(self._object_data[2])
        elif self.object_type == "{pelt}":
            return float(self._object_data[0][1][1])
        else:
            return None"""
        return self._horizontal_rotation

    def set_rotation(self, rotation):
        if self.object_type == "{item}":
            itemdata = self._object_data[0]
            for i, val in enumerate(rotation):
                if val is not None:
                    itemdata[1][i] = val
                    if i == 1:
                        self._horizontal_rotation = float(val)

        elif self.object_type == "{teki}":
            self._object_data[2] = rotation[1]
            self._horizontal_rotation = float(rotation[1])
        elif self.object_type == "{pelt}":
            peltdata = self._object_data[0]
            for i, val in enumerate(rotation):
                if val is not None:
                    peltdata[1][i] = val
                    if i == 1:
                        self._horizontal_rotation = float(val)

    def set_preceeding_comment(self, comments):
        self.preceeding_comment = comments

    def get_identifier(self):
        try:
            name = pack(32 * "B", *self.arguments).split(b"\x00")[0]
            name = name.decode("shift_jis-2004", errors="backslashreplace")
        except:
            name = "<failed to decode identifier>"

        return name

    def to_textnode(self):
        textnode = TextNode()

        #for comment in self.preceeding_comment:
        #    assert comment.startswith("#")
        #    textnode.append([comment.strip()])
        current_progress = 0

        try:
            assert_notlist(self.version)
            assert_notlist(self.reserved)
            assert_notlist(self.days_till_resurrection)
        except:
            textnode.append(self.version)
            textnode.append(self.reserved)
            textnode.append(self.days_till_resurrection)
        else:
            textnode.append([self.version, "# Version"])
            textnode.append([self.reserved, "# Reserved"])
            textnode.append([self.days_till_resurrection, "# Days till resurrection"])

        #current_progress = len(textnode)

        name = self.get_identifier()
        argsversion = self.identifier_misc[0]
        textnode.append(list(chain(self.arguments, ["# {0}".format(name)])))

        textnode.append([self.position_x, self.position_y, self.position_z, "# Position"])
        textnode.append([self.offset_x, self.offset_y, self.offset_z, "# Offset"])
        current_progress = len(textnode)
        if isinstance(self.object_type, list):
            identifier = []
            identifier.extend(self.object_type)
        else:
            identifier = [self.object_type]
        identifier.extend(self.identifier_misc)
        textnode.append(identifier)
        current_progress = len(textnode)

        try:
            if self.object_type == "{teki}" and argsversion == "{0005}":
                for i in range(12):
                    assert_notlist(self._object_data[i])
                textnode.append([self._object_data[0], "# Teki Birth Type"])
                textnode.append([self._object_data[1], "# Teki Number"])
                textnode.append([self._object_data[2], "# Face Direction"])
                textnode.append([self._object_data[3], "# 0: Point, 1: Circle"])
                textnode.append([self._object_data[4], "# appear radius"])
                textnode.append([self._object_data[5], "# enemy size"])
                textnode.append([self._object_data[6], "# Treasure item code"])
                textnode.append([self._object_data[7], "# Pellet color"])
                textnode.append([self._object_data[8], "# Pellet size"])
                textnode.append([self._object_data[9], "# Pellet Min"])
                textnode.append([self._object_data[10], "# Pellet Max"])
                textnode.append([self._object_data[11], "# Pellet Min"])
                textnode.extend(self._object_data[12:])

            elif self.object_type == "{item}":
                itemdata = self._object_data[0]
                itemid = itemdata[0].strip()
                newitemdata = TextNode()
                newitemdata.append([itemid, "# Item ID"])
                newitemdata.append([itemdata[1][0],itemdata[1][1], itemdata[1][2],  "# rotation"])
                newitemdata.append([itemdata[2], "# item local version"])
                assert_notlist(itemdata[2])

                if itemid == "{dwfl}":
                    for i in range(3, 7): assert_notlist(itemdata[i])
                    newitemdata.append([itemdata[3], "# Required pikmin count for weighting down the downfloor (if behaviour=0)"])
                    newitemdata.append([itemdata[4], "# Type: 0=small block, 1=large block, 2=paper bag"])
                    newitemdata.append([itemdata[5], "# Behaviour: 0=normal, 1=seesaw"])
                    newitemdata.append([itemdata[6],
                                        "# ID of this downfloor. If set to seesaw, there needs to be another dwfl with same ID."])
                elif itemid == "{brdg}":
                    assert_notlist(itemdata[3])
                    newitemdata.append([itemdata[3], "# Bridge type: 0=short, 1=slanted, 2=long"])
                elif itemid == "{dgat}":
                    assert_notlist(itemdata[3])
                    newitemdata.append([itemdata[3], "# Gate Health"])
                elif itemid == "{gate}":
                    assert_notlist(itemdata[3])
                    assert_notlist(itemdata[4])
                    newitemdata.append([itemdata[3], "# Gate Health"])
                    newitemdata.append([itemdata[4], "# Color: 0=bright, 1=dark"])
                elif itemid == "{onyn}":
                    assert_notlist(itemdata[3])
                    assert_notlist(itemdata[4])
                    newitemdata.append([itemdata[3], "# Onion type: 0=blue, 1=red, 2=yellow, 4=rocket"])
                    newitemdata.append([itemdata[4], "# after boot? true==1"])
                elif itemid == "{plnt}":
                    assert_notlist(itemdata[3])
                    newitemdata.append([itemdata[3], "# Berry type: 0=Red, 1=purple, 2=mixed"])
                else:
                    if len(itemdata) > 2:
                        newitemdata.extend(itemdata[3:])

                textnode.append(newitemdata)
                if len(self._object_data) > 1:
                    textnode.extend(self._object_data[1:])

            elif self.object_type == "{pelt}":
                pelt_data = self._object_data[0]
                new_pelt = TextNode()
                mgrid = pelt_data[0]
                assert_notlist(mgrid)
                assert_notlist(pelt_data[2])
                if mgrid == "0":
                    new_pelt.append([mgrid, "# Pellet"])
                else:
                    new_pelt.append([mgrid, "# Treasure category: 3=regular, 4=exploration kit"])
                new_pelt.append([pelt_data[1][0], pelt_data[1][1], pelt_data[1][2], "# Rotation"])
                new_pelt.append([pelt_data[2], "# Local version"])
                if mgrid == "0":
                    #tmp = []
                    #tmp.extend(pelt_data[3])
                    new_pelt.append([pelt_data[3][0], pelt_data[3][1], "# Pellet type (0,1,2 = B,R,Y respectively) and pellet size (1,5,10,20)"])
                else:
                    assert_notlist(pelt_data[3])
                    new_pelt.append([pelt_data[3], "# Identifier of treasure, see https://pikmintkb.com/wiki/Pikmin_2_identifiers	"])

                textnode.append(new_pelt)
                if len(self._object_data) > 1:
                    textnode.extend(self._object_data[1:])
            else:
                textnode.extend(self._object_data)
        except Exception as e:
            print(e)

            newtextnode = TextNode()
            newtextnode.extend(textnode[:current_progress])
            newtextnode.extend(self._object_data)

            textnode = newtextnode

        return textnode
