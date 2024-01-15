from PIL import Image, ImageDraw

from . import BCOllider

MINIMAP_WIDTH = 128
MINIMAP_HEIGHT = 256

DEFAULT_ORIENTATION = 0
DEFAULT_MARGIN = 10
DEFAULT_OUTLINE = 6
DEFAULT_OUTLINE_VERTICAL_OFFSET = -2000
DEFAULT_MULTISAMPLING = 4

DEFAULT_TERRAIN_COLORS = (
    (0x0000, False, (200, 200, 200)), # Medium Off-road
    (0x0100, True, (255, 255, 255)), # Road
    (0x0200, False, (0, 0, 0)), # Wall
    (0x0300, False, (200, 200, 200)), # Medium Off-road
    (0x0400, True, (255, 255, 255)), # Slippery Ice
    (0x0500, False, (0, 0, 0)), # Dead zone
    (0x0600, False, (0, 0, 0)), # Grassy Wall
    (0x0700, True, (255, 255, 255)), # Boost
    (0x0800, True, (255, 255, 255)), # Boost
    (0x0900, True, (255, 255, 255)), # Cannon Boost
    (0x0A00, False, (0, 0, 0)), # Dead zone
    (0x0C00, False, (200, 200, 200)), # Weak Off-road
    (0x0D00, True, (255, 255, 255)), # Teleport
    (0x0E00, False, (0, 0, 0)), # Sand Dead zone
    (0x0F00, False, (0, 0, 0)), # Wavy Dead zone
    (0x1000, False, (0, 0, 0)), # Quicksand Dead zone
    (0x1100, False, (0, 0, 0)), # Dead zone
    (0x1200, False, (0, 0, 0)), # Kart-Only Wall
    (0x1300, False, (0, 0, 0)), # Heavy Off-road
    (0x3700, True, (255, 255, 255)), # Boost
    (0x4700, True, (255, 255, 255)), # Boost
)
"""
List of 3-tuples containing the terrain type, whether it should be part of the minimap, and its
color.
"""

try:
    RESAMPLING_FILTER = Image.Resampling.LANCZOS
except AttributeError:
    # If the Pillow version is old, the enum class won't be available. Fall back to the deprecated
    # value for now.
    RESAMPLING_FILTER = Image.LANCZOS


def bco_to_minimap(
    filepath: str,
    orientation: int = DEFAULT_ORIENTATION,
    margin: int = DEFAULT_MARGIN,
    horizontal_offset: int = 0,
    vertical_offset: int = 0,
    outline: int = DEFAULT_OUTLINE,
    outline_vertical_offset: int = DEFAULT_OUTLINE_VERTICAL_OFFSET,
    multisampling: int = DEFAULT_MULTISAMPLING,
    terrain_colors: 'tuple[tuple[int, bool, tuple[int, int, int]]]' = DEFAULT_TERRAIN_COLORS,
) -> 'tuple[Image, tuple]':
    collision = BCOllider.RacetrackCollision()
    with open(filepath, 'rb') as f:
        # Temporarily suppress print statements.
        import builtins  # pylint: disable=import-outside-toplevel
        print_bk = builtins.print
        builtins.print = lambda *args, **kwargs: None
        try:
            collision.load_file(f)
        finally:
            builtins.print = print_bk
            del print_bk

    return collision_to_minimap(
        collision,
        orientation,
        margin,
        horizontal_offset,
        vertical_offset,
        outline,
        outline_vertical_offset,
        multisampling,
        terrain_colors,
    )


def collision_to_minimap(
    collision: BCOllider.RacetrackCollision,
    orientation: int = DEFAULT_ORIENTATION,
    margin: int = DEFAULT_MARGIN,
    horizontal_offset: int = 0,
    vertical_offset: int = 0,
    outline: int = DEFAULT_OUTLINE,
    outline_vertical_offset: int = DEFAULT_OUTLINE_VERTICAL_OFFSET,
    multisampling: int = DEFAULT_MULTISAMPLING,
    terrain_colors: 'tuple[tuple[int, bool, tuple[int, int, int]]]' = DEFAULT_TERRAIN_COLORS,
) -> 'tuple[Image, tuple]':
    # Transpose dimensions depending on the orientation.
    if orientation in (0, 2):
        minimap_width = MINIMAP_WIDTH
        minimap_height = MINIMAP_HEIGHT
    else:
        minimap_width = MINIMAP_HEIGHT
        minimap_height = MINIMAP_WIDTH
    minimap_aspect_ratio = minimap_width / minimap_height

    canvas_width = minimap_width * multisampling
    canvas_height = minimap_height * multisampling
    canvas_margin = margin * multisampling
    canvas_outline = outline * multisampling

    # Map terrain type to color, discarding the ones not visible.
    terrain_colors = {
        terrain_type: color
        for terrain_type, visible, color in terrain_colors if visible
    }

    # Filter triangles by terrain type and convert vertex indexes to vertex points.
    triangles = []
    for vi1, vi2, vi3, terrain_type, _rest in collision.triangles:
        terrain_color = terrain_colors.get(terrain_type & 0xFF00)
        if terrain_color is None:
            continue
        v1 = collision.vertices[vi1]
        v2 = collision.vertices[vi2]
        v3 = collision.vertices[vi3]
        triangles.append((terrain_color, v1, v2, v3))

    min_x = min(min(v1[0], v2[0], v3[0]) for _terrain_type, v1, v2, v3 in triangles)
    max_x = max(max(v1[0], v2[0], v3[0]) for _terrain_type, v1, v2, v3 in triangles)
    min_y = min(min(v2[1], v2[1], v3[1]) for _terrain_type, v1, v2, v3 in triangles)
    max_y = max(max(v2[1], v2[1], v3[1]) for _terrain_type, v1, v2, v3 in triangles)
    min_z = min(min(v3[2], v2[2], v3[2]) for _terrain_type, v1, v2, v3 in triangles)
    max_z = max(max(v3[2], v2[2], v3[2]) for _terrain_type, v1, v2, v3 in triangles)
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    center_z = (min_z + max_z) / 2.0
    box_width = max_x - min_x
    box_height = max_z - min_z

    # Fit triangles in canvas.
    scale_x = (canvas_width / 2 - canvas_margin) / (max_x - center_x)
    scale_z = (canvas_height / 2 - canvas_margin) / (max_z - center_z)
    scale = min(scale_x, scale_z)
    fit_triangles = []
    for terrain_color, v1, v2, v3 in triangles:
        centered_v1 = ((v1[0] - center_x) * scale, v1[1] - center_y, (v1[2] - center_z) * scale)
        centered_v2 = ((v2[0] - center_x) * scale, v2[1] - center_y, (v2[2] - center_z) * scale)
        centered_v3 = ((v3[0] - center_x) * scale, v3[1] - center_y, (v3[2] - center_z) * scale)
        fit_triangles.append((terrain_color, centered_v1, centered_v2, centered_v3))
    triangles = fit_triangles

    image = Image.new('RGBA', (canvas_width, canvas_height))

    # Rasterize triangles.
    draw = ImageDraw.Draw(image)
    if outline and outline_vertical_offset is not None:
        # Outline and fill of the triangles are rendered in a single pass, using the triangles'
        # height to determine what is rasterized first. This allows the outline to overlap triangles
        # that are at a lower height.
        outline_points = [(terrain_color, (v1[0] + canvas_width / 2, v1[2] + canvas_height / 2),
                           (v2[0] + canvas_width / 2, v2[2] + canvas_height / 2),
                           (v3[0] + canvas_width / 2, v3[2] + canvas_height / 2),
                           min(v1[1], v2[1], v3[1]) + outline_vertical_offset, True)
                          for terrain_color, v1, v2, v3 in triangles]
        fill_points = [(terrain_color, (v1[0] + canvas_width / 2, v1[2] + canvas_height / 2),
                        (v2[0] + canvas_width / 2, v2[2] + canvas_height / 2),
                        (v3[0] + canvas_width / 2, v3[2] + canvas_height / 2),
                        max(v1[1], v2[1], v3[1]), False) for terrain_color, v1, v2, v3 in triangles]
        triangle_points = sorted(outline_points + fill_points, key=lambda entry: entry[4])
        for terrain_color, p0, p1, p2, _height, as_line in triangle_points:
            if as_line:
                draw.line((p0, p1, p1, p2, p2, p0, p0, p1),
                          fill=(0, 0, 0),
                          width=canvas_outline,
                          joint='curve')
            else:
                draw.polygon((p0, p1, p2), fill=terrain_color)
    else:
        # Outline and fill of the triangles are rendered in separate passes: in the first, pass all
        # the outline is rasterized; in the second pass, the fill of the triangles is rasterized.
        triangle_points = tuple(
            (terrain_color, (v1[0] + canvas_width / 2, v1[2] + canvas_height / 2),
             (v2[0] + canvas_width / 2, v2[2] + canvas_height / 2),
             (v3[0] + canvas_width / 2, v3[2] + canvas_height / 2), min(v1[1], v2[1], v3[1]))
            for terrain_color, v1, v2, v3 in triangles)
        triangle_points = sorted(triangle_points, key=lambda entry: entry[4])
        if outline:
            for _terrain_color, p0, p1, p2, _height in triangle_points:
                draw.line((p0, p1, p1, p2, p2, p0, p0, p1),
                          fill=(0, 0, 0),
                          width=canvas_outline,
                          joint='curve')
        for terrain_color, p0, p1, p2, _height in triangle_points:
            draw.polygon((p0, p1, p2), fill=terrain_color)

    # Downscale to the final dimensions.
    image = image.resize((minimap_width, minimap_height),
                         resample=RESAMPLING_FILTER,
                         reducing_gap=3.0)

    # Rotate image to match its orientation.
    if orientation:
        if orientation == 1:
            method = Image.ROTATE_270
        elif orientation == 2:
            method = Image.ROTATE_180
        else:
            method = Image.ROTATE_90
        image = image.transpose(method)

    # Apply offset.
    if horizontal_offset or vertical_offset:
        offset_image = Image.new(image.mode, image.size)
        offset_image.alpha_composite(image, (horizontal_offset, vertical_offset))
        image = offset_image

    # Calculate coordinates based on aspect ratio and margin.
    if scale_x < scale_z:
        coordinates_margin = box_width * (minimap_width / (minimap_width - margin * 2) - 1) / 2
        coordinates_vertical_increment = (
            box_width + coordinates_margin * 2) / minimap_aspect_ratio - (box_height +
                                                                          coordinates_margin * 2)
        coordinates = (min_x - coordinates_margin,
                       min_z - coordinates_margin - coordinates_vertical_increment / 2,
                       max_x + coordinates_margin,
                       max_z + coordinates_margin + coordinates_vertical_increment / 2)
    else:
        coordinates_margin = box_height * (minimap_height / (minimap_height - margin * 2) - 1) / 2
        coordinates_horizontal_increment = (
            box_height + coordinates_margin * 2) * minimap_aspect_ratio - (box_width +
                                                                           coordinates_margin * 2)
        coordinates = (min_x - coordinates_margin - coordinates_horizontal_increment / 2,
                       min_z - coordinates_margin,
                       max_x + coordinates_margin + coordinates_horizontal_increment / 2,
                       max_z + coordinates_margin)

    # Apply offset to coordinates.
    adjusted_box_width = coordinates[2] - coordinates[0]
    adjusted_box_height = coordinates[3] - coordinates[1]
    if orientation == 0:
        adjusted_horizontal_offset = adjusted_box_width * horizontal_offset / MINIMAP_WIDTH
        adjusted_vertical_offset = adjusted_box_height * vertical_offset / MINIMAP_HEIGHT
    elif orientation == 1:
        adjusted_horizontal_offset = adjusted_box_height * vertical_offset / MINIMAP_WIDTH
        adjusted_vertical_offset = -adjusted_box_width * horizontal_offset / MINIMAP_HEIGHT
    elif orientation == 2:
        adjusted_horizontal_offset = -adjusted_box_width * horizontal_offset / MINIMAP_WIDTH
        adjusted_vertical_offset = -adjusted_box_height * vertical_offset / MINIMAP_HEIGHT
    else:
        adjusted_horizontal_offset = -adjusted_box_height * vertical_offset / MINIMAP_WIDTH
        adjusted_vertical_offset = adjusted_box_width * horizontal_offset / MINIMAP_HEIGHT
    coordinates = (
        coordinates[0] - adjusted_horizontal_offset,
        coordinates[1] - adjusted_vertical_offset,
        coordinates[2] - adjusted_horizontal_offset,
        coordinates[3] - adjusted_vertical_offset,
    )

    return image, coordinates
