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

from .bad_globals import *

import bpy
import gpu
import gpu_extras
from gpu.types import GPUTexture, GPUFrameBuffer, GPUShaderCreateInfo, \
    GPUVertFormat, GPUVertBuf, GPUIndexBuf, GPUBatch, GPUStageInterfaceInfo, GPUOffScreen
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
            
            if BAD_PIPELINE.pipeline != None:
                BAD_PIPELINE.pipeline.update_vertex_buffer_data(mesh)
                BAD_PIPELINE.pipeline.update_index_buffer_data(mesh)

# does not support split views(multiple view 3ds)
# TODO: add support for split views
class BAD_PIPELINE:

    pipeline = None

    @staticmethod
    def create_pipeline():
        BAD_PIPELINE.pipeline = BAD_PIPELINE()
        BAD_PIPELINE.pipeline.initialize()

    @staticmethod
    def delete_pipeline():
        BAD_PIPELINE.pipeline.deinitialize()
        BAD_PIPELINE.pipeline = None

    def __init__(self):
        # declare member variables
        self.texture_color_attachment_object_id = None
        self.texture_color_attachment_linearized_depth = None
        self.texture_depth_attachment = None
        self.viewport_dimensions = (0, 0)
        self.framebuffer_view_3d = None
        self.framebuffer_offscreen = None
        self.is_in_image_debug_mode = True
        self.image_object_id = None
        self.image_depth_texture = None # uses linearized_depth to debug depth

        self.texture_name_to_texture = {}

        self.program_object_id_depth = None

        # TODO: currently we are not deleting buffers for meshes that get deleted
        self.vertex_buffers_data = {}
        self.index_buffers_data = {}
        
        self.vertex_buffer_format = GPUVertFormat()
        self.vertex_buffer_format.attr_add(id = "pos", comp_type = "F32", len = 3, fetch_mode = "FLOAT")
        
        self.vertex_buffers = {}
        self.index_buffers = {}
        self.batches = {}

        self.update_image_counter = 0

    def initialize(self):
        self.create_textures(None)
        self.create_framebuffers()
        self.create_images()
        self.create_shaders()
        self.create_vertex_index_buffers_batches()

    def deinitialize(self):
        self.vertex_buffers_data.clear()
        self.index_buffers_data.clear()

        self.vertex_buffers.clear()
        self.index_buffers.clear()
        self.batches.clear()

        self.framebuffer_offscreen.free()

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
                            

        if not is_render_valid: # do not render there is no ative VIEW_3D area active
            return

        queried_viewport_dimensions = self.query_view_3d_dimensions(context)

        if(queried_viewport_dimensions[0] != self.viewport_dimensions[0] or queried_viewport_dimensions[1] != self.viewport_dimensions[1]):
            # recreate framebuffer with new viewport dimensions
            self.viewport_dimensions = queried_viewport_dimensions
            self.create_textures(context)
            self.create_framebuffers()
            #self.create_images()

        # bind framebuffer and render
        default_framebuffer = gpu.state.active_framebuffer_get()

        with self.framebuffer_view_3d.bind():
            
            #self.render_uid_to_object_id.clear()

            fb = gpu.state.active_framebuffer_get()

            fb.clear(color = (0.0, 0.0, 0.0, 0.0), depth = 1.0)
            
            self.program_object_id_depth.bind()
            
            self.program_object_id_depth.uniform_float("near", near)
            self.program_object_id_depth.uniform_float("far", far)
            self.program_object_id_depth.uniform_float("numObjects", float(len(self.vertex_buffers)))

            object_id = 1.0
            
            for obj in context.scene.objects:
                if isinstance(obj.data, bpy.types.Mesh) and obj.visible_get(): # and obj.bad_settings.m_is_enabled  TODO:
                    mesh = obj.data
                    uid = mesh.as_pointer()

                    if not uid in self.vertex_buffers_data:
                        self.create_vertex_index_buffer_batch(mesh)

                    #self.render_uid_to_object_id[uid] = object_id
                    self.program_object_id_depth.uniform_float("id", object_id)
                    object_id = object_id + 1.0

                    # set MVP
                    mvp = vp @ obj.matrix_world

                    self.program_object_id_depth.uniform_float("mvp", mvp)

                    self.batches[uid].draw(self.program_object_id_depth)

        self.framebuffer_offscreen.bind()
        self.framebuffer_offscreen.draw_view3d(context.scene, context.view_layer, view3d_space, 
                                                   view3d_window_region, view_matrix, projection_matrix,
                                                   do_color_management = False,
                                                  draw_background = True)
        self.framebuffer_offscreen.unbind(restore = True)

        # draw Image 2D in Image Editor
        # for now draw the Object ID
        if texture_name != None and image_editor_aspect_ratio != 0:
            texture = self.texture_name_to_texture[texture_name]

            # center texture with fixed aspect ratio
            texture_width = texture.width
            texture_height = texture.height
            texture_aspect_ratio = texture_width / texture_height

            d = texture_aspect_ratio / image_editor_aspect_ratio
            
            if texture_width >= texture_height:
                pos = ((-1.0, -1.0 / d), (1.0, -1.0 / d), (1.0, 1.0 / d), (-1.0, 1.0 / d))
            else: # texture_height > texture_width:
                pos = ((-1.0 * d, -1.0), (1.0 * d, -1.0), (1.0 * d, 1.0), (-1.0 * d, 1.0))
            batch = gpu_extras.batch.batch_for_shader(self.program_texture_display, "TRI_FAN",
                                                    {
                                                        "pos" : pos,
                                                        "texCoord" :((0, 0), (1, 0), (1, 1), (0, 1))
                                                    })
            
            self.program_texture_display.bind()
            self.program_texture_display.uniform_sampler("tex", texture)

            is_multiple_channels = 0.0
            if texture_name == "Color":
                is_multiple_channels = 1.0

            self.program_texture_display.uniform_float("isMultipleChannels", is_multiple_channels)
            batch.draw(self.program_texture_display)

    def copy_texture_data_to_image(self):
        linearized_depth_buffer_2d = [(c, c, c, 1.0) for r in self.texture_color_attachment_linearized_depth.read().to_list() for c in r]
        object_id_buffer_2d = [(0 if len(self.vertex_buffers) == 0 else c / len(self.vertex_buffers), 
                             0 if len(self.vertex_buffers) == 0 else c / len(self.vertex_buffers),
                             0 if len(self.vertex_buffers) == 0 else c / len(self.vertex_buffers), 1.0) for r in self.texture_color_attachment_object_id.read().to_list() for c in r]

        linearized_depth_buffer = [c for r in linearized_depth_buffer_2d for c in r]
        object_id_buffer = [c for r in object_id_buffer_2d for c in r]

        self.image_depth_texture.pixels[:] = linearized_depth_buffer[:]
        self.image_object_id.pixels[:] = object_id_buffer[:]

        self.image_depth_texture.update()
        self.image_object_id.update()
                     

    # this 
    def create_textures(self, context : bpy.types.Context):
        self.viewport_dimensions = self.query_view_3d_dimensions(context)
        self.texture_color_attachment_object_id = GPUTexture(self.viewport_dimensions, format = "R32F")
        self.texture_color_attachment_object_id.clear(format = "FLOAT", value = (0.0,))
        self.texture_color_attachment_linearized_depth = GPUTexture(self.viewport_dimensions, format = "R32F")
        self.texture_color_attachment_linearized_depth.clear(format = "FLOAT", value = (0.0,))
        self.texture_depth_attachment = GPUTexture(self.viewport_dimensions, format = "DEPTH_COMPONENT24")
        self.texture_depth_attachment.clear(format = "FLOAT", value = (1.0,))

        self.texture_name_to_texture["Object ID"] = self.texture_color_attachment_object_id
        self.texture_name_to_texture["Depth Linearized"] = self.texture_color_attachment_linearized_depth
        # create texture atlas

    def create_framebuffers(self):
        self.framebuffer_view_3d = GPUFrameBuffer(depth_slot = self.texture_depth_attachment, color_slots = (self.texture_color_attachment_object_id, self.texture_color_attachment_linearized_depth))
        
        if self.framebuffer_offscreen != None:
            self.framebuffer_offscreen.free()
        
        self.framebuffer_offscreen = GPUOffScreen(self.viewport_dimensions[0], self.viewport_dimensions[1], format = "RGBA8")

        self.texture_name_to_texture["Color"] = self.framebuffer_offscreen.texture_color

    def create_images(self):
        if ((BAD_PREFIX + "Object ID") in bpy.data.images):
            bpy.data.images.remove(bpy.data.images[BAD_PREFIX + "Object ID"])
        if ((BAD_PREFIX + "Depth Linearized") in bpy.data.images):
            bpy.data.images.remove(bpy.data.images[BAD_PREFIX + "Depth Linearized"])
        if ((BAD_PREFIX + "Color") in bpy.data.images):
            bpy.data.images.remove(bpy.data.images[BAD_PREFIX + "Color"])

        self.image_object_id = bpy.data.images.new(BAD_PREFIX + "Object ID", self.viewport_dimensions[0], self.viewport_dimensions[1], alpha = True, float_buffer = True)
        self.image_depth_texture = bpy.data.images.new(BAD_PREFIX + "Depth Linearized", self.viewport_dimensions[0], self.viewport_dimensions[1], alpha = True, float_buffer = True)
        self.image_color = bpy.data.images.new(BAD_PREFIX + "Color", self.viewport_dimensions[0], self.viewport_dimensions[1], alpha = True, float_buffer = True)

        # create texture atlas image

    def create_shaders(self):
        shader_create_info_object_id_depth = GPUShaderCreateInfo()

        shader_create_info_object_id_depth.push_constant("FLOAT", "near")
        shader_create_info_object_id_depth.push_constant("FLOAT", "far")
        shader_create_info_object_id_depth.push_constant("FLOAT", "id")
        shader_create_info_object_id_depth.push_constant("FLOAT", "numObjects")

        shader_create_info_object_id_depth.vertex_in(0, "VEC3", "pos")

        shader_create_info_object_id_depth.push_constant("MAT4", "mvp")
        
        shader_create_info_object_id_depth.fragment_out(0, "FLOAT", "objectID")
        shader_create_info_object_id_depth.fragment_out(1, "FLOAT", "linearizedDepth")

        shader_create_info_object_id_depth.vertex_source(vertex_shader_source_object_id_depth)
        shader_create_info_object_id_depth.fragment_source(fragment_shader_source_object_id_depth)

        self.program_object_id_depth = gpu.shader.create_from_info(shader_create_info_object_id_depth)

        del shader_create_info_object_id_depth

        shader_create_info_texture_display = GPUShaderCreateInfo()

        shader_create_info_texture_display.push_constant("FLOAT", "isMultipleChannels")
        shader_create_info_texture_display.sampler(0, "FLOAT_2D", "tex")

        shader_create_info_texture_display.vertex_in(0, "VEC2", "pos")
        shader_create_info_texture_display.vertex_in(1, "VEC2", "texCoord")

        vertex_out = GPUStageInterfaceInfo("texture_display_interface")
        vertex_out.smooth("VEC2", "fragTex")

        shader_create_info_texture_display.vertex_out(vertex_out)

        shader_create_info_texture_display.fragment_out(0, "VEC4", "fragOut")

        shader_create_info_texture_display.vertex_source(vertex_shader_source_texture_display)
        shader_create_info_texture_display.fragment_source(fragment_shader_source_texture_display)

        self.program_texture_display = gpu.shader.create_from_info(shader_create_info_texture_display)

        del shader_create_info_texture_display

    def create_vertex_index_buffers_batches(self):
        for obj in bpy.data.objects:
            if obj.type == "MESH":
                mesh = obj.data
                self.create_vertex_index_buffer_batch(mesh)

    def create_vertex_index_buffer_batch(self, mesh : bpy.types.Mesh):
        mesh.calc_loop_triangles()
        
        self.update_vertex_buffer_data(mesh)
        self.update_index_buffer_data(mesh)

        uid = mesh.as_pointer()

        self.vertex_buffers[uid] = GPUVertBuf(self.vertex_buffer_format, len(self.vertex_buffers_data[uid]))
        self.vertex_buffers[uid].attr_fill(id = "pos", data = self.vertex_buffers_data[uid])
        self.index_buffers[uid] = GPUIndexBuf(type = "TRIS", seq = self.index_buffers_data[uid])

        self.batches[uid] = GPUBatch(type = "TRIS", buf = self.vertex_buffers[uid], elem = self.index_buffers[uid])
        
    # this function is called after depsgraph update post handler is called for a specific object and mesh
    def update_vertex_buffer_data(self, mesh : bpy.types.Mesh):
        vertices = []
        for mesh_vertex in mesh.vertices:
            vertices.append(mesh_vertex.co.to_tuple())
    
        self.vertex_buffers_data[mesh.as_pointer()] = vertices
    
    def update_index_buffer_data(self, mesh : bpy.types.Mesh):
        indices = []
        for triangle in mesh.loop_triangles:
            # triangle vertices give indices for every triangle vertex
            indices.append(triangle.vertices)
    
        self.index_buffers_data[mesh.as_pointer()] = indices

    def query_view_3d_dimensions(self, context : bpy.types.Context) -> (int, int):

        if context == None:
            return (1, 1)

        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                return (area.width, area.height)