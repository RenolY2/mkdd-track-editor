import re


def markdown_to_html(title: str, text: str) -> str:
    html = f'<h3>{title}</h3>\n'
    for paragraph in text.split('\n\n'):
        paragraph = paragraph.strip()
        if paragraph.startswith('- '):
            unordered_list = ''
            for line in paragraph.splitlines():
                unordered_list += f'<li>{line[1:].strip()}</li>\n'
            paragraph = f'<ul>{unordered_list}</ul>\n'
        else:
            paragraph = paragraph.replace('\n', ' ')
        paragraph = re.sub(r'^---(.*)', r'<hr/>\1', paragraph)
        paragraph = re.sub(r'\b_(.+)_\b', r'<em>\1</em>', paragraph)
        paragraph = re.sub(r'\*\*([^\*]+)\*\*', r'<b style="white-space: nowrap;">\1</b>',
                           paragraph)
        paragraph = re.sub(
            r'`([^`]+)`', r'<code style="background: #1B1B1B; white-space: nowrap;">'
            r'&nbsp;\1&nbsp;</code>', paragraph)
        html += f'<p>{paragraph}</p>\n'
    return html


def tool_tips_markdown_to_html(tool_tips: dict) -> dict:
    return {name: markdown_to_html(name, tool_tip) for name, tool_tip in tool_tips.items()}


objectdata = tool_tips_markdown_to_html({
    "Route ID": "The ID of the Route Group this object will follow (if supported by the object)",
    "Route Point ID": "The ID of the Route Point this object will start from (if supported by the object)",
    "Game Mode Presence": "Whether the object is present in Battle modes or Time Trials mode.",
    "Player Mode Presence":
    "Whether the object is present in Single Player or Multi Player mode. To hide the object, "
    "uncheck both.",
    "Collision": "Whether the object can be physically interacted with or not (check vanilla courses for your desired object's effect)",
})

enemypoints = tool_tips_markdown_to_html({
    "Link": "Will link the point to another point with the same Link value. Set to -1 for no link.",
    "Scale": "How wide of an area CPUs can drive on",
    "Items Only": "Whether this Point is usable by CPUs or only items (red/blue shells, eggs)",
    "Swerve": "Tells the CPUs to swerve left or right and how strongly",
    "Drift Direction": "Gives CPUs the suggestion to drift at this point",
    "Drift Acuteness": "How sharp the drift should be (in degrees). 250 max, 10 min.",
    "Drift Duration": "How long the drift should last for (in frames). 250 max, 30 min.",
    "Drift Supplement": "Value added to the calculation of all previous settings. Leave as 0 if unsure.",
    "No Mushroom Zone": "Whether CPUs are allowed to use mushrooms at this point or not",
})

checkpoints = tool_tips_markdown_to_html({
    "Shortcut Point ID": "After this point is crossed, all regions containing checkpoint pairs with this ID will cause the lap checker to be halted, allowing for dev-intended shortcuts.\nOnce the region is left, the lap checker will jump to the next standard checkpoint.",
    "Double-sided": "If set, the game will check if this point has been crossed from the opposite side.",
    "Lap Checkpoint": "🧩 Requires the **Sectioned Courses** code patch.\n\nWhen crossed, a lap will be incremented. \nIf this is the last checkpoint of its kind, the race will be finished instead.\nIf **Shortcut Point ID** is set, this flag is ignored, and a lap will _not_ be counted.\n\n---\n<small>**IMPORTANT:** Custom tracks that utilize this property must include `sectioned-courses` in the **code_patches** field in the `trackinfo.ini` file of the custom track.</small>",
})

objectid = tool_tips_markdown_to_html({
    "GeoAirJet": "The blowing wind from Sherbet Land",
    "GeoMarioFlower1": "The flowers with eyes from several tracks",
    "GeoMarioTree1": "The standard trees with eyes from several tracks",
    "GeoSplash": "Creates the water/lava splash effect when falling into it. Must be grounded to the visual model.",
    "GeoNormCar": "Regular car",
    "GeoItemCar": "Car that shoots mushrooms when bumping into it",
    "GeoBus": "Regular bus",
    "GeoTruck": "Regular truck",
    "GeoBombCar": "Bomb Car that explodes when bumping into it",
    "GeoShimmer": "Adds a blur effect to the camera",
    "TLensFlare": "Lens flare effect. Always in the same spot as TMapObjSun.",
    "TMapObjWlArrow": "The bouncing arrows with eyes from Waluigi Stadium",
    "TMapObjDinoTree": "Dancing trees in Dino Dino Jungle. Their animation (.bck) is only used in single-screen modes.",
    "TMapObjDonkyRockGen": "Generates the boulders used in DK Mountain. The rocks get destroyed once they reach the end of the route or fall out of the course, and then a new cycle starts. If a rock gets stuck and does not get destroyed, no new cycles will start.",
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
    "GeoPuller": "Creates a force that pulls you towards it. It's the sand pit in Dry Dry Desert.",
    "GeoItemBox": "Regular Item Box",
    "GeoF_ItemBox": "Item Box on a path",
    "GeoCannon": "Shoots you towards the desired Respawn ID",
})

camtype = tool_tips_markdown_to_html({
    "000 - Fix | StartFix": "Basic unrouted replay camera",
    "001 - FixPath | StartOnlyPath": "Basic routed camera. View direction remains parallel to the camera object's direction.",
    "002 - FixChase": "Unknown",
    "004 - StartFixPath": "Travels along a route, but only focus on the Start Point",
    "005 - DemoPath | StartPath": "Travels along a route, changing its view from the Start Point to the End Point",
    "006 - StartLookPath": "From its position, changes its view from the Start Point to the End Point",
    "007 - FixPala": "Unknown",
})

camdata = tool_tips_markdown_to_html({
    "Camera Duration": "In frames, how long the Grand Prix camera should display for. Total between all cams should be ~600. Set to 0 if not a Grand Prix camera.",
    "Start Camera": "Only check for the first Grand Prix camera",
    "Next Cam": "What the next camera should be. Set to -1 if not a a Grand Prix camera (or last Grand Prix camera).",
    "Route ID": "The ID of the Route Group this camera will travel along (if supported)",
    "Route Speed": "How fast the camera should move along the route (if supported)",
})

respawn = tool_tips_markdown_to_html({
    "Respawn ID": "Determines which water/OoB collision will make the player use this respawn point, e.g. Roadtype_0x0A03, where 3 is the Respawn ID.",
    "Next Enemy Point": "The enemy point that a CPU will drive towards after respawning",
    "Camera Index": "Index of a camera. Remnant that is not used in the game.",
    "Previous Checkpoint": "The ID of the checkpoint right behind the respawn point. Can be left as -1.",
})

areadata = tool_tips_markdown_to_html({
    "Camera Index": "Index into cameras if Area Type is set to 'Camera'. Otherwise, set to -1.",
    "LightParam Index": "Index into a LightParam entry. Only used if Camera Type is set to 'Shadow' or 'Lighting'.",
    "Feather": "Feather at the front and back of the object. Sides can't have feather."
})

area_type = tool_tips_markdown_to_html({
    "Shadow": "For adding shadows while under the area, similar to Lighting",
    "No Dead Zone": "Disables dead zones",
    "Lighting": "For changing lighting while under the area, similar to Shadow",
})

lightparam = ({
    "Light": "RGBA Light Color",
    "Position": "3D Light Source Position",
    "Ambient": "RGBA Ambient Color",
})

kartstartpoints = tool_tips_markdown_to_html({
    "Players":
    "The players that will start from this position. In racing courses, only a single start point "
    "set to **All Players** is expected. In battle courses, eight start points are expected, each "
    "set to a distinct player."
})
