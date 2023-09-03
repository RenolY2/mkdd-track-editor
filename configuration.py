import configparser


def read_config():
    cfg = configparser.ConfigParser()
    with open("editor_config.ini", "r") as f:
        cfg.read_file(f)
    return cfg


def make_default_config():
    cfg = configparser.ConfigParser()

    cfg["default paths"] = {
        "collision": "",
        "bol": "",
        "dol": "",
        "minimap_image": "",
        "minimap_json": ""
    }

    cfg["editor"] = {
        "InvertZoom": "False",
        "wasdscrolling_speed": "1250",
        "wasdscrolling_speedupfactor": "5",
        "multisampling": "8",
        "3d_background": "90 90 90",
        "hidden_collision_types": "",
        "hidden_collision_type_groups": "",
        "filter_view": "",
        "addi_file_on_load": "Choose",
    }

    with open("editor_config.ini", "w") as f:
        cfg.write(f)

    return cfg


def save_cfg(cfg):
    with open("editor_config.ini", "w") as f:
        cfg.write(f)