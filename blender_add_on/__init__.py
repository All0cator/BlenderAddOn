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
    importlib.reload(bad_menus)
    importlib.reload(bad_settings)

import bpy
from . import bad_menus
from . import bad_settings

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
    bad_menus.BAD_PT_MainPanel
)

#keymaps = []

def register():
    # register classes
    for c in classes:
        if not c.is_registered:
            bpy.utils.register_class(c)

    # register properties
    if "bad_settings" not in bpy.types.Object.__annotations__:
        bpy.types.Object.bad_settings = bpy.props.PointerProperty(type=bad_settings.BAD_PROPERTYGROUP_Settings)

def unregister():
    # remove operators
    for c in reversed(classes):
        if c.is_registered:
            bpy.utils.unregister_class(c)

# allows running addon from text editor
if __name__ == '__main__':
    register()