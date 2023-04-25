objectdata = {
    "Route ID": "The ID of the Route Group this object will follow (if supported by the object)",
    "Route Point ID": "The ID of the Route Point this object will start from (if supported by the object)",
    "Presence Mask": "255 = will show up in time trial and other modes. 15 = won't show up in time trial.",
    "Presence": "1 = only single screen modes. 2 = only split screen modes. 3 = both modes.",
    "Collision": "Whether the object can be physically interacted with or not (check vanilla\ncourses for your desired object's effect)",
}

enemypoints = {
    "Link": "Will link the point to another point with the same Link value.\nSet to -1 for no link.",
    "Scale": "How wide of an area CPUs can drive on",
    "Items Only": "Whether this Point is usable by CPUs or only items (red/blue shells, eggs)",
    "Swerve": "Tells the CPUs to swerve left or right and how strongly",
    "Drift Direction": "Gives CPUs the suggestion to drift at this point",
    "Drift Acuteness": "How sharp the drift should be (in degrees). 250 max, 10 min.",
    "Drift Duration": "How long the drift should last for (in frames). 250 max, 30 min.",
    "Drift Supplement": "Value added to the calculation of all previous settings. Leave as 0 if unsure.",
    "No Mushroom Zone": "Whether CPUs are allowed to use mushrooms at this point or not",
}

objectid = {
    "GeoAirJet": "The blowing wind from Sherbet Land",
    "GeoMarioFlower1": "The flowers with eyes from several tracks",
    "GeoMarioTree1": "The standard trees with eyes from several tracks",
    "GeoSplash": "Creates the water/lava splash effect when falling into it. Must be grounded to\nthe visual model.",
    "GeoNormCar": "Regular car",
    "GeoItemCar": "Car that shoots mushrooms when bumping into it",
    "GeoBus": "Regular bus",
    "GeoTruck": "Regular truck",
    "GeoBombCar": "Bomb Car that explodes when bumping into it",
    "GeoShimmer": "Adds a blur effect to the camera",
    "TLensFlare": "Lens flare effect. Always in the same spot as TMapObjSun.",
    "TMapObjWlArrow": "The bouncing arrows with eyes from Waluigi Stadium",
    "TMapObjDinoTree": "Dancing trees in Dino Dino Jungle. Their animation (.bck) is only used in\nsingle-screen modes.",
    "TMapObjDonkyRockGen": "The giant boulders from DK Mountain",
    "TMapObjFireCircle": "The fire circle obstacles from Wario Colosseum & Waluigi Stadium",
    "TMapObjFireBar": "The rotating fire bars from Bowser's Castle",
    "TMapObjFerrisWheel": "The ferris wheel in Baby Park",
    "TMapObjFountain": "The fountain from Peach Beach",
    "TMapObjGeyser": "The geysers from Dino Dino Jungle",
    "TMapObjMareA": "Male Noki",
    "TMapObjMareB": "Male Noki alt 1",
    "TMapObjMareC": "Female Noki alt 1",
    "TMapObjMareM_A": "Male Noki playing flute",
    "TMapObjMareM_B": "Male Noki playing flute alt 1",
    "TMapObjMareM_C": "Male Noki playing flute alt 2",
    "TMapObjMareW_A": "Dancing Female Noki",
    "TMapObjMareW_B": "Dancing Female Noki alt 1",
    "TMapObjMareW_C": "Dancing Female Noki alt 2",
    "TMapObjMonteA": "Male Pianta",
    "TMapObjMonteB": "Male yellow Pianta",
    "TMapObjMonteC": "Male brown Pianta",
    "TMapObjMonteD": "Female pink Pianta",
    "TMapObjMonteE": "Female red Pianta",
    "TMapObjNoMove_Lights": "Lights from Sherbet Land",
    "TMapObjPeachTree": "Palm trees from Peach Beach",
    "TMapObjPoihana": "Cataquack from Peach Beach",
    "TMapObjPool": "The pool from Daisy Cruiser",
    "TMapObjSnowman": "The snowmen from Sherbet Land",
    "TMapObjSun": "Sun object",
    "TMapObjWanwan": "Chain Chomps",
    "TMapObjYoshiHeli": "Helicopter from Yoshi Circuit",
    "GeoKuribo": "Goombas",
    "GeoPull": "Creates a force that pulls you towards it. It's the sand pit in Dry Dry Desert.",
    "GeoItemBox": "Regular Item Box",
    "GeoF_ItemBox": "Item Box on a path",
    "GeoCannon": "Shoots you towards the desired Respawn ID",
}

camtype = {
    "000 - Fix | StartFix": "Basic unrouted replay camera",
    "001 - FixPath | StartOnlyPath": "Basic routed camera. View direction remains parallel to the camera\nobject's direction.",
    "002 - FixChase": "Unknown",
    "004 - StartFixPath": "Travels along a route, but only focus on the Start Point",
    "005 - DemoPath | StartPath": "Travels along a route, changing its view from the Start Point to the End Point",
    "006 - StartLookPath": "From its position, changes its view from the Start Point to the End Point",
    "007 - FixPala": "Unknown",
}

camdata = {
    "Camera Duration": "In frames, how long the Grand Prix camera should display for. Total between all\ncams should be ~600. Set to 0 if not a Grand Prix camera.",
    "Start Camera": "Only check for the first Grand Prix camera",
    "Next Cam": "What the next camera should be. Set to -1 if not a a Grand Prix camera (or\nlast Grand Prix camera).",
    "Route ID": "The ID of the Route Group this camera will travel along (if supported)",
    "Route Speed": "How fast the camera should move along the route (if supported)",
}

respawn = {
    "Respawn ID": "Determines which water/OoB collision will make the player use this respawn point,\ne.g. Roadtype_0x0A03, where 3 is the Respawn ID.",
    "Next Enemy Point": "The enemy point that a CPU will drive towards after respawning",
    "Previous Checkpoint": "The ID of the checkpoint right behind the respawn point. Can be left as -1.",
}

areadata = {
    "Camera Index": "Index into cameras if Area Type is set to 'Camera'. Otherwise, set to -1.",
    "LightParam Index": "Index into a LightParam entry. Only used if Camera Type is set to 'Shadow'\nor 'Lighting'.",
    "Feather": "Feather at the front and back of the object. Sides can't have feather."
}

area_type = {
    "Shadow": "For adding shadows while under the area, similar to Lighting",
    "No Dead Zone": "Disables dead zones",
    "Lighting": "For changing lighting while under the area, similar to Shadow",
}

lightparam = {
    "Light": "RGBA Light Color",
    "Position": "3D Light Source Position",
    "Ambient": "RGBA Ambient Color",
}