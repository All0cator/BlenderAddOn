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

import bpy
from math import log2, pow
from bpy.props import *

class BAD_PROPERTYGROUP_Settings(bpy.types.PropertyGroup):
    guard : BoolProperty(default = False) # used internally to prevent infinite recursion when settings m_render_resolution

    def set_render_resolution_width(self, new_render_resolution_width : int):
        self.guard = True
        self.m_render_resolution_width = int(new_render_resolution_width)
        self.m_render_resolution_width_power = int(log2(float(self.m_render_resolution_width)))
        self.guard = False
        self.m_is_resolution_dirty = True

    def set_render_resolution_height(self, new_render_resolution_height : int):
        self.guard = True
        self.m_render_resolution_height = int(new_render_resolution_height)
        self.m_render_resolution_height_power = int(log2(float(self.m_render_resolution_height)))
        self.guard = False
        self.m_is_resolution_dirty = True

    def set_render_resolution_width_power(self, new_render_resolution_width_power : int):
        self.guard = True
        self.m_render_resolution_width_power = int(new_render_resolution_width_power)
        self.m_render_resolution_width = int(1 << int(self.m_render_resolution_width_power))
        self.guard = False
        self.m_is_resolution_dirty = True

    def set_render_resolution_height_power(self, new_render_resolution_height_power : int):
        self.guard = True
        self.m_render_resolution_height_power = int(new_render_resolution_height_power)
        self.m_render_resolution_height = int(1 << int(self.m_render_resolution_height_power))
        self.guard = False
        self.m_is_resolution_dirty = True

    # Property Update functions

    def update_render_resolution_width(self, context):
        if not self.guard:
            self.set_render_resolution_width(int(self.m_render_resolution_width))

    def update_render_resolution_height(self, context):
        if not self.guard:
            self.set_render_resolution_height(self.m_render_resolution_height)

    def update_render_resolution_width_power(self, context):
        if not self.guard:
            self.set_render_resolution_width_power(int(self.m_render_resolution_width_power))

    def update_render_resolution_height_power(self, context):
        if not self.guard:
            self.set_render_resolution_height_power(self.m_render_resolution_height_power)

    m_is_resolution_dirty : BoolProperty (
        name = "Is Resolution Dirty",
        default = True,
        description = "Shows whether the texture atlas and it's asscociated cell viewports buffer needs to be updated or not"
    )

    m_id : IntProperty (
        name = "ID",
        default = 0,
        description = "ID of current Object"
    )

    m_is_enabled : BoolProperty (
        name = "Enable",
        default = False,
        description = "Enable Compositor Parameters"
    )

    m_render_resolution_width : IntProperty (
        name = "Render Resolution Width",
        default = 64,
        description = "Affects Render Resolution Width parameter when rendering 3D Mesh into Sprite Atlas",
        min = 8,
        max = 512,
        step = 1,
        update = update_render_resolution_width
    )

    m_render_resolution_height : IntProperty (
        name = "Render Resolution Height",
        default = 128,
        description = "Affects Render Resolution Height parameter when rendering 3D Mesh into Sprite Atlas",
        min = 8,
        max = 512,
        step = 1,
        update = update_render_resolution_height
    )

    # These get displayed in UI in case snapping is toggled 
    m_render_resolution_width_power : IntProperty (
        name = "Render Resolution Width Power of 2",
        default = 6,
        description = "Affects Render Resolution Width parameter (in powers of 2) when rendering 3D Mesh into Sprite Atlas",
        min = 3,
        max = 9,
        step = 1,
        update = update_render_resolution_width_power
    )

    m_render_resolution_height_power : IntProperty (
        name = "Render Resolution Height",
        default = 7,
        description = "Affects Render Resolution Height parameter (in powers of 2) when rendering 3D Mesh into Sprite Atlas",
        min = 3,
        max = 9,
        step = 1,
        update = update_render_resolution_height_power
    )

    m_toggle_snapping_width : BoolProperty (
        name = "Toggle Snapping Width",
        default = True,
        description = "Toggle snapping for Render Resolution Width in nearest power of 2",
    )

    m_toggle_snapping_height : BoolProperty (
        name = "Toggle Snapping Height",
        default = True,
        description = "Toggle snapping for Render Resolution Height in nearest power of 2",
    )