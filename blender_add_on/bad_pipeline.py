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

from math import ceil
from .bad_globals import *

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from gpu.types import GPUTexture, GPUFrameBuffer, GPUShaderCreateInfo, \
    GPUVertFormat, GPUVertBuf, GPUIndexBuf, GPUBatch, GPUStageInterfaceInfo, GPUOffScreen, Buffer, GPUUniformBuf
from .bad_shaders import *
import gpu

from .bad_helpers import *

from bpy.app.handlers import persistent

# TODO: add support for realtime mesh editing 
@persistent
def mesh_update_handler(scene, depsgraph):
    for update in depsgraph.updates:
        if isinstance(update.id, bpy.types.Object) and isinstance(update.id, bpy.types.Mesh):
            mesh = update.id
            mesh.calc_loop_triangles()
            
            if BAD_Pipeline.pipeline != None:
                BAD_Pipeline.pipeline.update_vertex_buffer_data(mesh)
                BAD_Pipeline.pipeline.update_index_buffer_data(mesh)

# does not support split views(multiple view 3ds)
# TODO: add support for split views
class BAD_Pipeline:

    pipeline = None

    @staticmethod
    def create_pipeline():
        if BAD_Pipeline.pipeline == None:
            BAD_Pipeline.pipeline = BAD_Pipeline()
            BAD_Pipeline.pipeline.initialize()


    @staticmethod
    def delete_pipeline():
        if BAD_Pipeline.pipeline != None:
            BAD_Pipeline.pipeline.deinitialize()
        BAD_Pipeline.pipeline = None

    def __init__(self):
        self.m_object_id_counter = 1 # ids are not zero indexed, 0 means not an object
        # declare member variables
        self.m_texture_color_attachment_object_id = None
        self.m_texture_color_attachment_linearized_depth = None
        self.m_texture_depth_attachment = None

        self.m_texture_sprite_atlas_r = None
        self.m_texture_sprite_atlas_g = None
        self.m_texture_sprite_atlas_b = None
        self.m_texture_sprite_atlas = None

        self.m_viewport_dimensions = (0, 0)
        self.m_framebuffer_view_3d = None
        self.m_framebuffer_offscreen = None
        self.m_is_in_image_debug_mode = True
        self.m_image_object_id = None
        self.m_image_depth_texture = None # uses linearized_depth to debug depth
        self.m_image_color = None
        self.m_image_sprite_atlas = None

        self.m_texture_name_to_display_texture_info = {}

        self.m_program_object_id_depth = None
        self.m_program_texture_display = None
        self.m_program_sprite_atlas_render_channels = None
        self.m_program_sprite_atlas_merge_channels_to_texture = None

        # TODO: currently we are not deleting buffers for meshes that get deleted
        self.m_vertex_buffers_data = {}
        self.m_index_buffers_data = {}
        
        self.m_vertex_buffer_format = GPUVertFormat()
        self.m_vertex_buffer_format.attr_add(id = "pos", comp_type = "F32", len = 3, fetch_mode = "FLOAT")
        
        self.m_vertex_buffers = {}
        self.m_index_buffers = {}
        self.m_batches = {}

        self.m_texture_atlas_dimensions = (BAD_MAX_TEXTURE_SPRITE_ATLAS_WIDTH, BAD_MAX_TEXTURE_SPRITE_ATLAS_HEIGHT)
        self.m_cell_viewports = None
        self.m_buffer_cell_viewports = None
        self.m_uniform_buffer_cell_viewports = None

    def initialize(self):
        self.create_vertex_index_buffers_batches(bpy.context)
        self.create_textures(bpy.context)
        self.create_sprite_atlas_textures()
        self.create_framebuffers()
        self.create_images()
        self.create_shaders()

    def deinitialize(self):
        self.m_vertex_buffers_data.clear()
        self.m_index_buffers_data.clear()

        self.m_vertex_buffers.clear()
        self.m_index_buffers.clear()
        self.m_batches.clear()

        self.m_framebuffer_offscreen.free()

    # TODO: currently cannot handle instanced meshes
    # function should be called from UI thread
    def render(self, context : bpy.types.Context):
        near = None
        far = None
        vp = None
        view_matrix = None
        projection_matrix = None
        view3d_space = None
        view3d_window_region = None

        is_render_valid = False

        texture_name = None
        image_editor_aspect_ratio = 0
        
        # Get near and far view plane values
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                view3d_space = area.spaces.active
                near = view3d_space.clip_start
                far = view3d_space.clip_end
                vp = view3d_space.region_3d.perspective_matrix # Window Matrix @ View Matrix
                view_matrix = view3d_space.region_3d.view_matrix
                projection_matrix = view3d_space.region_3d.window_matrix


                for region in area.regions:
                    if region.type == "WINDOW":
                        view3d_window_region = region
                        is_render_valid = True
                        break

            if area.type == "IMAGE_EDITOR":
                # query image selected in image editor
                if area.height != 0:
                    image_editor_aspect_ratio = area.width / area.height

                for space in area.spaces:
                    if space.type == "IMAGE_EDITOR":
                        image = space.image

                        if image != None:
                            if contains_prefix(image.name):
                                texture_name = get_name_from_prefixed_name(image.name)
                            

        if not is_render_valid and texture_name == None and image_editor_aspect_ratio == 0: # do not render there is no ative VIEW_3D area active
            return

        queried_viewport_dimensions = self.query_view_3d_dimensions(context)

        if(queried_viewport_dimensions[0] != self.m_viewport_dimensions[0] or queried_viewport_dimensions[1] != self.m_viewport_dimensions[1]):
            # recreate framebuffer with new viewport dimensions
            self.m_viewport_dimensions = queried_viewport_dimensions
            self.create_textures(context)
            self.create_framebuffers()

        # bind framebuffer and render
        default_framebuffer = gpu.state.active_framebuffer_get()

        with self.m_framebuffer_view_3d.bind():
            
            #self.render_uid_to_object_id.clear()

            fb = gpu.state.active_framebuffer_get()

            fb.clear(color = (0.0, 0.0, 0.0, 0.0), depth = 1.0)
            
            self.m_program_object_id_depth.bind()
            
            self.m_program_object_id_depth.uniform_float("near", near)
            self.m_program_object_id_depth.uniform_float("far", far)
            
            for obj in context.scene.objects:
                if isinstance(obj.data, bpy.types.Mesh) and obj.visible_get(): # and obj.bad_settings.m_is_enabled  TODO:
                    mesh = obj.data
                    uid = mesh.as_pointer()

                    if not uid in self.m_vertex_buffers_data:
                        obj.bad_settings.m_id = self.m_object_id_counter
                        self.m_object_id_counter += 1
                        self.create_vertex_index_buffer_batch(mesh, context)

                    #self.render_uid_to_object_id[uid] = object_id
                    settings = obj.bad_settings
                    object_id = settings.m_id
                    self.m_program_object_id_depth.uniform_float("id", object_id)

                    # set MVP
                    mvp = vp @ obj.matrix_world

                    self.m_program_object_id_depth.uniform_float("mvp", mvp)

                    self.m_batches[uid].draw(self.m_program_object_id_depth)

        self.m_framebuffer_offscreen.bind()
        self.m_framebuffer_offscreen.draw_view3d(context.scene, context.view_layer, view3d_space, 
                                                   view3d_window_region, view_matrix, projection_matrix,
                                                   do_color_management = False,
                                                  draw_background = True)
        self.m_framebuffer_offscreen.unbind(restore = True)


        # TODO: For now update object_id_to_cell_viewport ssbo every frame optimize it to change only when needed
        # TODO: In the future support multiple texture atlases for for faster ssbo data update
        self.create_uniform_buffer_cell_viewports()

        self.m_program_sprite_atlas_render_channels.bind()

        self.m_program_sprite_atlas_render_channels.uniform_float("viewportWidth", float(self.m_viewport_dimensions[0]))
        self.m_program_sprite_atlas_render_channels.uniform_float("viewportHeight", float(self.m_viewport_dimensions[1]))
        

        self.m_program_sprite_atlas_render_channels.uniform_block("cellViewports", self.m_uniform_buffer_cell_viewports)

        self.m_program_sprite_atlas_render_channels.image("objectIDs", self.m_texture_name_to_display_texture_info["Object ID"]["texture"])
        self.m_program_sprite_atlas_render_channels.image("colors", self.m_texture_name_to_display_texture_info["Color"]["texture"])
        self.m_program_sprite_atlas_render_channels.image("spriteAtlasR", self.m_texture_name_to_display_texture_info["Sprite Atlas R"]["texture"])
        self.m_program_sprite_atlas_render_channels.image("spriteAtlasG", self.m_texture_name_to_display_texture_info["Sprite Atlas G"]["texture"])
        self.m_program_sprite_atlas_render_channels.image("spriteAtlasB", self.m_texture_name_to_display_texture_info["Sprite Atlas B"]["texture"])

        gpu.compute.dispatch(self.m_program_sprite_atlas_render_channels, ceil(self.m_viewport_dimensions[0] / 32), ceil(self.m_viewport_dimensions[1] / 32), 1)


        
        self.m_program_sprite_atlas_merge_channels_to_texture.bind()

        self.m_program_sprite_atlas_merge_channels_to_texture.uniform_float("atlasWidth", float(self.m_texture_atlas_dimensions[0]))
        self.m_program_sprite_atlas_merge_channels_to_texture.uniform_float("atlasHeight", float(self.m_texture_atlas_dimensions[1]))

        self.m_program_sprite_atlas_merge_channels_to_texture.image("spriteAtlasR", self.m_texture_name_to_display_texture_info["Sprite Atlas R"]["texture"])
        self.m_program_sprite_atlas_merge_channels_to_texture.image("spriteAtlasG", self.m_texture_name_to_display_texture_info["Sprite Atlas G"]["texture"])
        self.m_program_sprite_atlas_merge_channels_to_texture.image("spriteAtlasB", self.m_texture_name_to_display_texture_info["Sprite Atlas B"]["texture"])
        self.m_program_sprite_atlas_merge_channels_to_texture.image("spriteAtlas", self.m_texture_name_to_display_texture_info["Sprite Atlas"]["texture"])

        gpu.compute.dispatch(self.m_program_sprite_atlas_merge_channels_to_texture, ceil((self.m_texture_atlas_dimensions[0] * self.m_texture_atlas_dimensions[1]) / 32), 1, 1)

        self.m_texture_name_to_display_texture_info["Object ID"]["channel_max"] = len(self.m_vertex_buffers)
        self.m_texture_name_to_display_texture_info["Depth Linearized"]["channel_min"] = near
        self.m_texture_name_to_display_texture_info["Depth Linearized"]["channel_max"] = far

        # draw Image 2D in Image Editor
        # for now draw the Object ID
        if texture_name != None and image_editor_aspect_ratio != 0:
            texture_info = self.m_texture_name_to_display_texture_info[texture_name]

            # center texture with fixed aspect ratio
            texture_width = texture_info["texture"].width
            texture_height = texture_info["texture"].height
            texture_aspect_ratio = texture_width / texture_height

            d = texture_aspect_ratio / image_editor_aspect_ratio
            
            if texture_width >= texture_height:
                pos = ((-1.0, -1.0 / d), (1.0, -1.0 / d), (1.0, 1.0 / d), (-1.0, 1.0 / d))
            else: # texture_height > texture_width:
                pos = ((-1.0 * d, -1.0), (1.0 * d, -1.0), (1.0 * d, 1.0), (-1.0 * d, 1.0))
            batch = batch_for_shader(self.m_program_texture_display, "TRI_FAN",
                                                    {
                                                        "pos" : pos,
                                                        "texCoord" :((0, 0), (1, 0), (1, 1), (0, 1))
                                                    })
            
            self.m_program_texture_display.bind()
            self.m_program_texture_display.uniform_sampler("tex", texture_info["texture"])

            is_multiple_channels = texture_info["is_multiple_channels"]
            channel_min = texture_info["channel_min"]
            channel_max = texture_info["channel_max"]

            self.m_program_texture_display.uniform_float("isMultipleChannels", is_multiple_channels)
            self.m_program_texture_display.uniform_float("channelMin", channel_min)
            self.m_program_texture_display.uniform_float("channelMax", channel_max)
            batch.draw(self.m_program_texture_display)
    
    def create_textures(self, context : bpy.types.Context):
        self.m_viewport_dimensions = self.query_view_3d_dimensions(context)
        self.m_texture_color_attachment_object_id = GPUTexture(self.m_viewport_dimensions, format = "R32F")
        self.m_texture_color_attachment_object_id.clear(format = "FLOAT", value = (0.0,))
        self.m_texture_color_attachment_linearized_depth = GPUTexture(self.m_viewport_dimensions, format = "R32F")
        self.m_texture_color_attachment_linearized_depth.clear(format = "FLOAT", value = (0.0,))
        self.m_texture_depth_attachment = GPUTexture(self.m_viewport_dimensions, format = "DEPTH_COMPONENT24")
        self.m_texture_depth_attachment.clear(format = "FLOAT", value = (1.0,))

        self.m_texture_name_to_display_texture_info["Object ID"] = { "texture" : self.m_texture_color_attachment_object_id,
                                                                     "is_multiple_channels" : 0.0,
                                                                     "channel_min" : 0.0,
                                                                     "channel_max" : 0.0} # set to default values they are going to be updated in render
        self.m_texture_name_to_display_texture_info["Depth Linearized"] = { "texture" : self.m_texture_color_attachment_linearized_depth,
                                                                            "is_multiple_channels" : 0.0,
                                                                            "channel_min" : 0.0, # set to default values they are going to be updated in render
                                                                            "channel_max" : 0.0}

    def create_sprite_atlas_textures(self):
        self.m_texture_sprite_atlas_r = GPUTexture(self.m_texture_atlas_dimensions, format = "R32UI")
        self.m_texture_sprite_atlas_r.clear(format = "UINT", value = (0,))
        self.m_texture_sprite_atlas_g = GPUTexture(self.m_texture_atlas_dimensions, format = "R32UI")
        self.m_texture_sprite_atlas_g.clear(format = "UINT", value = (0,))
        self.m_texture_sprite_atlas_b = GPUTexture(self.m_texture_atlas_dimensions, format = "R32UI")
        self.m_texture_sprite_atlas_b.clear(format = "UINT", value = (0,))
        self.m_texture_sprite_atlas = GPUTexture(self.m_texture_atlas_dimensions, format = "RGBA8")
        self.m_texture_sprite_atlas.clear(format = "FLOAT", value = (0.0, 0.0, 0.0, 1.0))

        self.m_texture_name_to_display_texture_info["Sprite Atlas R"] = { "texture" : self.m_texture_sprite_atlas_r,
                                                                     "is_multiple_channels" : 0.0,
                                                                     "channel_min" : 0.0,
                                                                     "channel_max" : 255.0}
        self.m_texture_name_to_display_texture_info["Sprite Atlas G"] = { "texture" : self.m_texture_sprite_atlas_g,
                                                                            "is_multiple_channels" : 0.0,
                                                                            "channel_min" : 0.0,
                                                                            "channel_max" : 255.0}
        
        self.m_texture_name_to_display_texture_info["Sprite Atlas B"] = { "texture" : self.m_texture_sprite_atlas_b,
                                                                     "is_multiple_channels" : 0.0,
                                                                     "channel_min" : 0.0,
                                                                     "channel_max" : 255.0}
        self.m_texture_name_to_display_texture_info["Sprite Atlas"] = { "texture" : self.m_texture_sprite_atlas,
                                                                            "is_multiple_channels" : 1.0,
                                                                            "channel_min" : 0.0,
                                                                            "channel_max" : 1.0}

    def create_uniform_buffer_cell_viewports(self):
        self.m_cell_viewports = [[0.0, 0.0, 0.0, 0.0] for i in range(BAD_MAX_CELL_VIEWPORTS_SIZE)]

        for obj in bpy.data.objects:
            if obj.bad_settings.m_is_enabled:
                self.m_cell_viewports[obj.bad_settings.m_id][2] = float(obj.bad_settings.m_render_resolution_width)
                self.m_cell_viewports[obj.bad_settings.m_id][3] = float(obj.bad_settings.m_render_resolution_height)

        width_counter = 0
        height_counter = 0
        max_resolution_height = 0
        #max_resolution_width = 0

        for i in range(1, self.m_object_id_counter):
            if i >= BAD_MAX_CELL_VIEWPORTS_SIZE:
                print(f"Warning: Uniform Buffer is full more than:{BAD_MAX_CELL_VIEWPORTS_SIZE} objects exist\n")
                break # uniform  buffer is full
            self.m_cell_viewports[i][0] = float(width_counter)
            self.m_cell_viewports[i][1] = float(height_counter)
            width_counter = width_counter + self.m_cell_viewports[i][2]
            if max_resolution_height < height_counter + self.m_cell_viewports[i][3]:
                max_resolution_height = height_counter + self.m_cell_viewports[i][3]
            if width_counter >= BAD_MAX_TEXTURE_SPRITE_ATLAS_WIDTH:
                width_counter = 0
                height_counter = max_resolution_height
                if height_counter >= BAD_MAX_TEXTURE_SPRITE_ATLAS_HEIGHT:
                    print(f"Warning: Texture atlas with size({BAD_MAX_TEXTURE_SPRITE_ATLAS_WIDTH}, {BAD_MAX_TEXTURE_SPRITE_ATLAS_HEIGHT}) is full, reduce resolutions\n")
                    break # texture atlas is full #TODO: Create new texture atlas and put it into texture atlas map and map all ids 
            #if max_resolution_width < width_counter + self.m_cell_viewports[i][2]:
            #    max_resolution_width = width_counter + self.m_cell_viewports[i][2]

        self.m_buffer_cell_viewports = Buffer("FLOAT", (BAD_MAX_CELL_VIEWPORTS_SIZE, 4), self.m_cell_viewports)
        self.m_uniform_buffer_cell_viewports = GPUUniformBuf(self.m_buffer_cell_viewports)

    def create_framebuffers(self):
        self.m_framebuffer_view_3d = GPUFrameBuffer(depth_slot = self.m_texture_depth_attachment, color_slots = (self.m_texture_color_attachment_object_id, self.m_texture_color_attachment_linearized_depth))
        
        if self.m_framebuffer_offscreen != None:
            self.m_framebuffer_offscreen.free()
        
        self.m_framebuffer_offscreen = GPUOffScreen(self.m_viewport_dimensions[0], self.m_viewport_dimensions[1], format = "RGBA8")

        self.m_texture_name_to_display_texture_info["Color"] = { "texture" : self.m_framebuffer_offscreen.texture_color,
                                                                 "is_multiple_channels" : 1.0,
                                                                 "channel_min" : 0.0,
                                                                 "channel_max" : 1.0}

    def create_images(self):
        if ((BAD_PREFIX + "Object ID") in bpy.data.images):
            bpy.data.images.remove(bpy.data.images[BAD_PREFIX + "Object ID"])
        if ((BAD_PREFIX + "Depth Linearized") in bpy.data.images):
            bpy.data.images.remove(bpy.data.images[BAD_PREFIX + "Depth Linearized"])
        if ((BAD_PREFIX + "Color") in bpy.data.images):
            bpy.data.images.remove(bpy.data.images[BAD_PREFIX + "Color"])
        if ((BAD_PREFIX + "Sprite Atlas") in bpy.data.images):
            bpy.data.images.remove(bpy.data.images[BAD_PREFIX + "Sprite Atlas"])

        # we only care for their selection we do not display any data to the images
        self.m_image_object_id = bpy.data.images.new(BAD_PREFIX + "Object ID", 1, 1)
        self.m_image_depth_texture = bpy.data.images.new(BAD_PREFIX + "Depth Linearized", 1, 1)
        self.m_image_color = bpy.data.images.new(BAD_PREFIX + "Color", 1, 1)
        self.m_image_sprite_atlas = bpy.data.images.new(BAD_PREFIX + "Sprite Atlas", 1, 1)

    def create_shaders(self):
        shader_create_info_object_id_depth = GPUShaderCreateInfo()

        shader_create_info_object_id_depth.push_constant("FLOAT", "near")
        shader_create_info_object_id_depth.push_constant("FLOAT", "far")
        shader_create_info_object_id_depth.push_constant("FLOAT", "id")

        shader_create_info_object_id_depth.vertex_in(0, "VEC3", "pos")

        shader_create_info_object_id_depth.push_constant("MAT4", "mvp")
        
        shader_create_info_object_id_depth.fragment_out(0, "FLOAT", "objectID")
        shader_create_info_object_id_depth.fragment_out(1, "FLOAT", "linearizedDepth")

        shader_create_info_object_id_depth.vertex_source(vertex_shader_source_object_id_depth)
        shader_create_info_object_id_depth.fragment_source(fragment_shader_source_object_id_depth)

        self.m_program_object_id_depth = gpu.shader.create_from_info(shader_create_info_object_id_depth)

        del shader_create_info_object_id_depth

        shader_create_info_texture_display = GPUShaderCreateInfo()

        shader_create_info_texture_display.push_constant("FLOAT", "isMultipleChannels")
        shader_create_info_texture_display.push_constant("FLOAT", "channelMin")
        shader_create_info_texture_display.push_constant("FLOAT", "channelMax")

        shader_create_info_texture_display.sampler(0, "FLOAT_2D", "tex")

        shader_create_info_texture_display.vertex_in(0, "VEC2", "pos")
        shader_create_info_texture_display.vertex_in(1, "VEC2", "texCoord")

        vertex_out = GPUStageInterfaceInfo("texture_display_interface")
        vertex_out.smooth("VEC2", "fragTex")

        shader_create_info_texture_display.vertex_out(vertex_out)

        shader_create_info_texture_display.fragment_out(0, "VEC4", "fragOut")

        shader_create_info_texture_display.vertex_source(vertex_shader_source_texture_display)
        shader_create_info_texture_display.fragment_source(fragment_shader_source_texture_display)

        self.m_program_texture_display = gpu.shader.create_from_info(shader_create_info_texture_display)

        del shader_create_info_texture_display

        shader_create_info_sprite_atlas_render_channels = GPUShaderCreateInfo()
        shader_create_info_sprite_atlas_render_channels.compute_source(compute_shader_source_sprite_atlas_render_channels)
        shader_create_info_sprite_atlas_render_channels.define("MAX_CELL_VIEWPORTS", str(BAD_MAX_CELL_VIEWPORTS_SIZE))
        shader_create_info_sprite_atlas_render_channels.local_group_size(8, 8, 1)

        shader_create_info_sprite_atlas_render_channels.push_constant("FLOAT", "viewportWidth")
        shader_create_info_sprite_atlas_render_channels.push_constant("FLOAT", "viewportHeight")

        shader_create_info_sprite_atlas_render_channels.uniform_buf(0, "vec4[" + str(BAD_MAX_CELL_VIEWPORTS_SIZE) + "]", "cellViewports")
        shader_create_info_sprite_atlas_render_channels.image(1, "R32F", "FLOAT_2D", "objectIDs", qualifiers = {"READ"})
        shader_create_info_sprite_atlas_render_channels.image(2, "RGBA8", "FLOAT_2D", "colors", qualifiers = {"READ"})
        shader_create_info_sprite_atlas_render_channels.image(3, "R32UI", "UINT_2D", "spriteAtlasR", qualifiers = {"READ", "WRITE"})
        shader_create_info_sprite_atlas_render_channels.image(4, "R32UI", "UINT_2D", "spriteAtlasG", qualifiers = {"READ", "WRITE"})
        shader_create_info_sprite_atlas_render_channels.image(5, "R32UI", "UINT_2D", "spriteAtlasB", qualifiers = {"READ", "WRITE"})

        self.m_program_sprite_atlas_render_channels = gpu.shader.create_from_info(shader_create_info_sprite_atlas_render_channels)

        shader_create_info_sprite_atlas_merge_channels_to_texture = GPUShaderCreateInfo()
        shader_create_info_sprite_atlas_merge_channels_to_texture.compute_source(compute_shader_source_sprite_atlas_merge_channels_to_texture)

        shader_create_info_sprite_atlas_merge_channels_to_texture.local_group_size(32, 1, 1)
        
        shader_create_info_sprite_atlas_merge_channels_to_texture.push_constant("FLOAT", "atlasWidth")
        shader_create_info_sprite_atlas_merge_channels_to_texture.push_constant("FLOAT", "atlasHeight")

        shader_create_info_sprite_atlas_merge_channels_to_texture.image(3, "R32UI", "UINT_2D", "spriteAtlasR", qualifiers = {"READ", "WRITE"})
        shader_create_info_sprite_atlas_merge_channels_to_texture.image(4, "R32UI", "UINT_2D", "spriteAtlasG", qualifiers = {"READ", "WRITE"})
        shader_create_info_sprite_atlas_merge_channels_to_texture.image(5, "R32UI", "UINT_2D", "spriteAtlasB", qualifiers = {"READ", "WRITE"})
        shader_create_info_sprite_atlas_merge_channels_to_texture.image(6, "RGBA8", "FLOAT_2D", "spriteAtlas", qualifiers = {"WRITE"})

        self.m_program_sprite_atlas_merge_channels_to_texture = gpu.shader.create_from_info(shader_create_info_sprite_atlas_merge_channels_to_texture)
       
    def create_vertex_index_buffers_batches(self, context : bpy.context):
        for obj in bpy.data.objects:
            if obj.type == "MESH":
                obj.bad_settings.m_id = self.m_object_id_counter
                self.m_object_id_counter += 1
                mesh = obj.data
                self.create_vertex_index_buffer_batch(mesh, context)

    def create_vertex_index_buffer_batch(self, mesh : bpy.types.Mesh, context : bpy.context):
        mesh.calc_loop_triangles()
        
        self.update_vertex_buffer_data(mesh)
        self.update_index_buffer_data(mesh)

        uid = mesh.as_pointer()

        self.m_vertex_buffers[uid] = GPUVertBuf(self.m_vertex_buffer_format, len(self.m_vertex_buffers_data[uid]))
        self.m_vertex_buffers[uid].attr_fill(id = "pos", data = self.m_vertex_buffers_data[uid])
        self.m_index_buffers[uid] = GPUIndexBuf(type = "TRIS", seq = self.m_index_buffers_data[uid])

        self.m_batches[uid] = GPUBatch(type = "TRIS", buf = self.m_vertex_buffers[uid], elem = self.m_index_buffers[uid])

    # this function is called after depsgraph update post handler is called for a specific object and mesh
    def update_vertex_buffer_data(self, mesh : bpy.types.Mesh):
        vertices = []
        for mesh_vertex in mesh.vertices:
            vertices.append(mesh_vertex.co.to_tuple())
    
        self.m_vertex_buffers_data[mesh.as_pointer()] = vertices
    
    def update_index_buffer_data(self, mesh : bpy.types.Mesh):
        indices = []
        for triangle in mesh.loop_triangles:
            # triangle vertices give indices for every triangle vertex
            indices.append(triangle.vertices)
    
        self.m_index_buffers_data[mesh.as_pointer()] = indices

    def query_view_3d_dimensions(self, context : bpy.types.Context) -> (int, int):

        if context == None:
            return (1, 1)

        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                return (area.width, area.height)