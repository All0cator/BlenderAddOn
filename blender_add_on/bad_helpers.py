from .bad_globals import *

def get_scene_name_from_prefixed_scene_name(prefixed_scene_name : str) -> str:
    return prefixed_scene_name[len(BAD_PREFIX):]