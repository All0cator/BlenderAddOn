#  ***** GPL LICENSE BLOCK *****
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#  All rights reserved.
#  ***** GPL LICENSE BLOCK *****

# reload submodules if the addon is reloaded 
if "bpy" in locals():
    import importlib
    importlib.reload(bad_globals)
    importlib.reload(bad_helpers)
    importlib.reload(bad_menus)
    importlib.reload(bad_pipeline)
    importlib.reload(bad_settings)
    importlib.reload(bad_shaders)

import bpy
from . import bad_globals
from . import bad_helpers
from . import bad_menus
from . import bad_pipeline
from . import bad_settings
from . import bad_shaders

bl_info = {
    "name": "BlenderAddOn",
    "author": "Allocator",
    "version": (0, 84),
    "blender": (4, 0, 0),
    "location": "Object Mode | View3D > NewAddOn",
    "description": "Object Parameters for Rendering",
    "warning": "",
    "doc_url": "https://github.com/All0cator/BlenderAddOn",
    "tracker_url": "https://github.com/All0cator/BlenderAddOn/issues",
    "category": "Compositing",
}

classes = (
    bad_settings.BAD_PROPERTYGROUP_Settings,
    bad_menus.BAD_PT_MainPanel,
)

#keymaps = []

from bpy.app.handlers import persistent

@persistent
def render_pipeline_handler():
    if bad_pipeline.BAD_PIPELINE.pipeline == None:
        bad_pipeline.BAD_PIPELINE.create_pipeline()

    bad_pipeline.BAD_PIPELINE.pipeline.render(bpy.context)

draw_handler = None

def init_pipeline():
    global draw_handler
    bad_pipeline.BAD_PIPELINE.create_pipeline()

    # update the handler if it is already registered
    if bad_pipeline.mesh_update_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(bad_pipeline.mesh_update_handler)
 
    bpy.app.handlers.depsgraph_update_post.append(bad_pipeline.mesh_update_handler)

    if draw_handler != None:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handler,
                                                  'WINDOW')
        draw_handler = None

    draw_handler = bpy.types.SpaceView3D.draw_handler_add(
        render_pipeline_handler,
        (),
        'WINDOW',
        'POST_PIXEL'
    )

    if render_pipeline_handler in bpy.app.handlers.render_post:
        bpy.app.handlers.render_post.remove()
 
    bpy.app.handlers.render_post.append(render_pipeline_handler)

def register():
    # register classes
    for c in classes:
        if not c.is_registered:
            bpy.utils.register_class(c)

    # register properties
    if "bad_settings" not in bpy.types.Object.__annotations__:
        bpy.types.Object.bad_settings = bpy.props.PointerProperty(type=bad_settings.BAD_PROPERTYGROUP_Settings)

    bpy.app.timers.register(init_pipeline, first_interval = 1.0)

def unregister():
    # remove operators
    for c in reversed(classes):
        if c.is_registered:
            bpy.utils.unregister_class(c)

    bad_pipeline.BAD_PIPELINE.delete_pipeline()

# allows running addon from text editor
if __name__ == '__main__':
    register()