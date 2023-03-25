ZOOMVALUES = ((0, 0.2), (1, 0.3), (1.6, 0.6))


def calc_zoom_in_factor(current):
    zoom = 0.2
    for val, zoomfac in ZOOMVALUES:
        if val <= current:
            zoom = zoomfac
        elif val > current:
            break

    return zoom


def calc_zoom_out_factor(current):
    zoom = -0.2
    for val, zoomfac in reversed(ZOOMVALUES):
        if val >= current:
            pass
        elif val < current:
            zoom = zoomfac
            break
    return -zoom
