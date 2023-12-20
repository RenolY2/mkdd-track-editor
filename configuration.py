import configparser
import os
import platform
import subprocess


def get_config_directory():
    return os.path.abspath(os.curdir)


def get_config_filepath():
    return os.path.join(get_config_directory(), 'editor_config.ini')


def read_config():
    cfg = configparser.ConfigParser()
    with open(get_config_filepath(), "r", encoding='utf-8') as f:
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
        "topdown_cull_height": 80000
    }

    with open(get_config_filepath(), "w", encoding='utf-8') as f:
        cfg.write(f)

    return cfg


def save_cfg(cfg):
    with open(get_config_filepath(), "w", encoding='utf-8') as f:
        cfg.write(f)


def open_config_directory():
    config_dir = get_config_directory()
    if platform.system() == 'Windows':
        os.startfile(config_dir)  # pylint: disable=no-member
    else:
        subprocess.check_call(('open' if platform.system() == 'Darwin' else 'xdg-open', config_dir))
