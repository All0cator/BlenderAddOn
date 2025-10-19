import blender_add_on
import importlib

def reload():
    importlib.reload(blender_add_on.bad_menus)
    importlib.reload(blender_add_on.bad_settings)
    importlib.reload(blender_add_on)
    return None

