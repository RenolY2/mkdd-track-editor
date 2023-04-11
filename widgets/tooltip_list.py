objectdata = {
    "Route ID": "The ID of the Route Group this object will follow (if supported by the object)",
    "Route Point ID": "The ID of the Route Point this object will start from (if supported by the object)",
    "Presence Mask": "255 = will show up in time trial and other modes. 15 = won't show up in time trial",
    "Presence": "1 = only single screen modes. 2 = only split screen modes. 3 = both modes",
    "Collision": "Whether the object can be physically interacted with or not (check vanilla courses for your desired object's effect)"
}

enemypoints = {
    "Link": "Will link the point to another point with the same Link value. Set to -1 for no link.",
    "Scale": "How wide of an area CPUs can drive on",
    "Items Only": "Whether this Point is usable by CPUs or only items (red/blue shells, eggs)",
    "Swerve": "Tells the CPUs to swerve left or right and how strongly",
    "Drift Direction": "Gives CPUs the suggestion to drift at this point",
    "Drift Acuteness": "How sharp the drift should be (in degrees). 250 max, 10 min",
    "Drift Duration": "How long the drift should last for (in frames). 250 max, 30 min",
    "Drift Supplement": "Value added to the calculation of all previous settings. Leave as 0 if unsure",
    "No Mushroom Zone": "Whether CPUs are allowed to use mushrooms at this point or not"
}