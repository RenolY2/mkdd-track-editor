import configparser


def read_config():
    print("reading")
    cfg = configparser.ConfigParser()
    with open("editor_config.ini", "r") as f:
        cfg.read_file(f)
    print("read")
    return cfg


def make_default_config():
    cfg = configparser.ConfigParser()

    cfg["default paths"] = {
        "collision": "",
        "gen": ""
    }

    cfg["editor"] = {
        "InvertZoom": "False",
        "wasdscrolling_speed": "1250",
        "wasdscrolling_speedupfactor": "5"
    }

    with open("editor_config.ini", "w") as f:
        cfg.write(f)

    return cfg


def save_cfg(cfg):
    with open("editor_config.ini", "w") as f:
        cfg.write(f)