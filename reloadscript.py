import blender_add_on
import importlib

def reload():
    importlib.reload(blender_add_on.bad_globals)
    importlib.reload(blender_add_on.bad_helpers)
    importlib.reload(blender_add_on.bad_menus)
    importlib.reload(blender_add_on.bad_pipeline)
    importlib.reload(blender_add_on.bad_settings)
    importlib.reload(blender_add_on.bad_shaders)
    importlib.reload(blender_add_on)
    return None

