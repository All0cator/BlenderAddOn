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
from . import bad_settings
from . import bad_menus

class BAD_PT_MainPanel(bpy.types.Panel):
    bl_label = 'BlenderAddOn'
    bl_idname = 'BAD_PT_MainPanel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category =  'BAD'
    bl_context = 'objectmode'

    def draw(self, context):
        layout = self.layout
        settings = context.object.bad_settings
        #print("lol")
        layout.prop(settings, "m_is_enabled", text = "Is Enabled")
        col = layout.column(align = False)
        row = col.row(align = True)
        if settings.m_toggle_snapping_width:
            row.prop(settings, "m_render_resolution_width_power", text = "Resolution Width")
        else:
            row.prop(settings, "m_render_resolution_width", text = "Resolution Width")
        row.prop(settings, "m_toggle_snapping_width", text = "")
        
        col = layout.column(align = False)
        row = col.row(align = True)
        if settings.m_toggle_snapping_height:
            row.prop(settings, "m_render_resolution_height_power", text = "Resolution Height")
        else:
            row.prop(settings, "m_render_resolution_height", text = "Resolution Height")
        row.prop(settings, "m_toggle_snapping_height", text = "")
        #layout.prop(settings, "m_render_resolution_width", text = "Resolution ")
        #layout.prop(settings, "m_render_resolution_width", text = "Resolution Width")